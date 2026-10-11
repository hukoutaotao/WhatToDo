"""Detached exact stage effects; no SQL, permit or inferred final completion."""
from copy import deepcopy
from dataclasses import dataclass, field, asdict
from datetime import datetime
from hashlib import sha256

from src.application.command_validation import PreparedUserEstimate
from src.application.definitions import canonical, identity, strict_json
from src.application.relationship_storage import RelationStorageRecord
from src.application.relationship_validation import GraphLimits
from src.application.task_storage import TaskStorageRecord, admit_storage
from src.application.transactions import require
from src.domain.authorization import CallerIdentity
from src.domain.relationships import Endpoint
from src.domain.task_aggregate import instant

VERSION='0.1.0-stage-command'
MAX_REVISION=9223372036854775807
FIELDS={'intent','parent_remaining_seconds','stage_remaining_seconds','completed_at'}


def serial_time(value):
    if isinstance(value,datetime):return value.isoformat()
    if isinstance(value,dict):return {k:serial_time(v) for k,v in value.items()}
    if isinstance(value,(list,tuple)):return [serial_time(v) for v in value]
    return value


@dataclass(frozen=True)
class StageCommand:
    command_id: str
    principal_id: str
    authority_ref: str
    task_id: str
    expected_revision: int
    stage_id: str
    expected_stage_revision: int
    operation: str
    fields_json: str = field(repr=False)

    def __post_init__(self):
        require(all(identity(v) for v in (self.command_id,self.principal_id,self.authority_ref,self.task_id,self.stage_id)), 'STAGE_COMMAND_IDENTITY')
        require(all(type(v) is int and 0<v<=MAX_REVISION for v in (self.expected_revision,self.expected_stage_revision)), 'STAGE_COMMAND_REVISION')
        require(self.operation in ('REWORK','COMPLETE') and isinstance(self.fields_json,str) and len(self.fields_json.encode())<=262144, 'STAGE_COMMAND_OPERATION_OR_SIZE')
        f=strict_json(self.fields_json)
        require(isinstance(f,dict) and set(f)<=FIELDS and f.get('intent') in (None,'UNRESOLVED','SAME_OBLIGATION','CORRECTION','NEW_OBLIGATION'), 'STAGE_COMMAND_FIELDS')
        for k in ('parent_remaining_seconds','stage_remaining_seconds'):
            if k in f:require(f[k] is None or type(f[k]) is int and 0<=f[k]<=MAX_REVISION,'STAGE_COMMAND_REMAINING')
        if 'completed_at' in f:
            require(self.operation=='COMPLETE','STAGE_REWORK_CANNOT_REPORT_COMPLETION_TIME')
            if f['completed_at'] is not None:
                try:instant(f['completed_at'])
                except (ValueError,TypeError,OverflowError):require(False,'STAGE_REPORTED_TIME')
        if self.operation=='COMPLETE' and 'stage_remaining_seconds' in f:
            require(type(f['stage_remaining_seconds']) is int and f['stage_remaining_seconds']==0,'STAGE_COMPLETION_ZERO_REQUIRED')
        object.__setattr__(self,'fields_json',canonical(f))

    @property
    def fields(self):return strict_json(self.fields_json)
    def as_record(self):
        return dict(schema_version=VERSION,command_id=self.command_id,principal_id=self.principal_id,origin='USER_COMMAND',authority_ref=self.authority_ref,
            target_ref=dict(task_id=self.task_id,revision=self.expected_revision,stage_id=self.stage_id,stage_revision=self.expected_stage_revision),operation=self.operation,fields=self.fields)
    @property
    def fingerprint(self):return sha256(canonical(self.as_record()).encode()).hexdigest()


def admit_stage_command(codec,raw):
    require(isinstance(raw,bytes) and 0<len(raw)<=262144,'STAGE_COMMAND_SIZE')
    admitted=codec.admit('stage-command',raw)
    require(admitted.status=='SUPPORTED_SHAPE','STAGE_COMMAND_SHAPE_UNSUPPORTED')
    v=admitted.payload;t=v['target_ref']
    return StageCommand(v['command_id'],v['principal_id'],v['authority_ref'],t['task_id'],t['revision'],t['stage_id'],t['stage_revision'],v['operation'],canonical(v['fields']))


@dataclass(frozen=True)
class StageCommandGrant:
    command: StageCommand = field(repr=False)
    evidence_ref: str
    issued_at: datetime
    source_observed_at: datetime
    expires_at: datetime | None = None
    active: bool = True

    def __post_init__(self):
        require(isinstance(self.command,StageCommand) and identity(self.evidence_ref) and type(self.active) is bool,'STAGE_TYPED_GRANT')
        require(all(isinstance(t,datetime) and t.utcoffset() is not None for t in (self.issued_at,self.source_observed_at))
            and (self.expires_at is None or isinstance(self.expires_at,datetime) and self.expires_at.utcoffset() is not None and self.issued_at<self.expires_at),'STAGE_GRANT_TIME')

    def as_record(self):return dict(contract='stage-command',command=self.command.as_record(),active=self.active,source_observed_at=self.source_observed_at.isoformat())


@dataclass(frozen=True)
class StageExecutionEvidence:
    endpoint: Endpoint
    task_id: str
    task_revision: int
    completion: str
    stage_revision: int | None = None
    started_at: datetime | None = None
    completed_at: datetime | None = None

    def __post_init__(self):
        require(isinstance(self.endpoint,Endpoint) and identity(self.task_id) and type(self.task_revision) is int and 0<self.task_revision<=MAX_REVISION
            and self.completion in ('COMPLETE','INCOMPLETE'),'STAGE_EXECUTION_EVIDENCE')
        require(self.endpoint.kind=='TASK' and self.endpoint.id==self.task_id and self.stage_revision is None
            or self.endpoint.kind=='STAGE' and type(self.stage_revision) is int and 0<self.stage_revision<=MAX_REVISION,'STAGE_EXECUTION_OWNER')
        require(all(t is None or isinstance(t,datetime) and t.utcoffset() is not None for t in (self.started_at,self.completed_at))
            and (self.completed_at is None or self.completion=='COMPLETE')
            and (self.started_at is None or self.completed_at is None or self.started_at<=self.completed_at),'STAGE_EXECUTION_TIME')


@dataclass(frozen=True)
class StageOrderSnapshot:
    relations: tuple[RelationStorageRecord,...] = ()
    executions: tuple[StageExecutionEvidence,...] = ()
    limits: GraphLimits = GraphLimits()

    def __post_init__(self):
        require(isinstance(self.limits,GraphLimits) and isinstance(self.relations,tuple) and all(isinstance(r,RelationStorageRecord) for r in self.relations)
            and isinstance(self.executions,tuple) and all(isinstance(e,StageExecutionEvidence) for e in self.executions),'STAGE_ORDER_TYPED_SNAPSHOT')
        require(len({r.relation.relation_id for r in self.relations})==len(self.relations)
            and len({e.endpoint for e in self.executions})==len(self.executions),'STAGE_ORDER_DUPLICATE_IDENTITY')
        require(len(self.relations)<=self.limits.max_relations and len(self.executions)<=self.limits.max_endpoints
            and len(self.relations)+len(self.executions)<=self.limits.max_traversal_work,'STAGE_ORDER_RESOURCE_LIMIT')
        require(len(canonical(self.payload).encode())<=self.limits.max_payload_bytes,'STAGE_ORDER_PAYLOAD_LIMIT')

    @property
    def payload(self):return serial_time(dict(relations=[r.payload for r in self.relations],executions=[asdict(e) for e in self.executions]))


@dataclass(frozen=True)
class PreparedStageCommand:
    state: str
    code: str
    record: TaskStorageRecord | None = field(default=None,repr=False)
    estimates: tuple[PreparedUserEstimate,...] = ()
    transition_json: str | None = field(default=None,repr=False)
    missing_fields: tuple[str,...] = ()

    def __post_init__(self):
        require(self.state in ('PREPARED','PENDING'),'STAGE_PREPARATION_STATE')
        require((self.state=='PREPARED' and isinstance(self.record,TaskStorageRecord) and self.transition_json is not None and not self.missing_fields)
            or (self.state=='PENDING' and self.record is None and not self.estimates and self.transition_json is None),'STAGE_PREPARATION_EFFECTS')

    @property
    def transition(self):return strict_json(self.transition_json) if self.transition_json is not None else None


def prepare_stage_command(codec,command,grant,before,*,caller,now,order=StageOrderSnapshot()):
    require(isinstance(command,StageCommand) and isinstance(grant,StageCommandGrant),'STAGE_INDEPENDENT_GRANT_REQUIRED')
    require(isinstance(caller,CallerIdentity) and caller.authenticated and caller.origin=='USER_COMMAND' and caller.principal_id==command.principal_id,'STAGE_TRUSTED_USER_CALLER')
    require(isinstance(now,datetime) and now.utcoffset() is not None,'STAGE_CLOCK_REQUIRED')
    require(grant.command.fingerprint==command.fingerprint,'STAGE_EXACT_SCOPE_MISMATCH')
    require(grant.active and grant.issued_at<=now and (grant.expires_at is None or now<grant.expires_at),'STAGE_INACTIVE_AUTHORITY')
    require(grant.source_observed_at<=now,'STAGE_FUTURE_OBSERVATION')
    require(isinstance(before,TaskStorageRecord) and before.task_id==command.task_id,'STAGE_UNKNOWN_PARENT')
    require(before.revision==command.expected_revision,'STAGE_STALE_PARENT')
    original=before.aggregate.as_record();details=original['stage_details']
    index=next((i for i,s in enumerate(original['effort']['stages']) if s['stage_id']==command.stage_id),None)
    require(index is not None,'STAGE_UNKNOWN_TARGET')
    detail=next(d for d in details if d['stage_id']==command.stage_id)
    require(detail['revision']==command.expected_stage_revision,'STAGE_STALE_TARGET')
    f=command.fields;intent=f.get('intent')
    if intent!='SAME_OBLIGATION':
        code={'NEW_OBLIGATION':'STAGE_NEW_OBLIGATION_REQUIRES_CREATION','CORRECTION':'STAGE_CORRECTION_REQUIRES_RECONCILIATION'}.get(intent,'STAGE_INTENT_UNRESOLVED')
        return PreparedStageCommand('PENDING',code,missing_fields=('intent',))
    if original['core']['disposition']!='ACTIVE':return PreparedStageCommand('PENDING','STAGE_PARENT_INACTIVE',missing_fields=('parent_reactivation',))
    old_stage=original['effort']['stages'][index];old_u=original['effort']['user_remaining']
    if command.operation=='REWORK':
        require(old_stage['completion']=='COMPLETE','STAGE_REWORK_REQUIRES_COMPLETED_TARGET')
        needed=original['core']['completion']=='COMPLETE' or old_u is None or old_u['seconds']==0
        if needed and (f.get('parent_remaining_seconds') is None or f['parent_remaining_seconds']==0):
            return PreparedStageCommand('PENDING','STAGE_REWORK_REMAINING_REQUIRED',missing_fields=('parent_remaining_seconds',))
        if 'parent_remaining_seconds' in f and (f['parent_remaining_seconds'] is None or f['parent_remaining_seconds']==0):
            return PreparedStageCommand('PENDING','STAGE_REWORK_REMAINING_REQUIRED',missing_fields=('parent_remaining_seconds',))
    elif original['core']['completion']=='COMPLETE' and 'parent_remaining_seconds' in f and f['parent_remaining_seconds']!=0:
        return PreparedStageCommand('PENDING','STAGE_PARENT_COMPLETION_CONFLICT',missing_fields=('parent_rework_intent',))
    require(isinstance(order,StageOrderSnapshot),'STAGE_ORDER_TYPED_SNAPSHOT')
    executions={e.endpoint:e for e in order.executions};target=Endpoint('STAGE',command.stage_id)
    target_evidence=executions.get(target)
    if target_evidence is not None:
        require((target_evidence.task_id,target_evidence.task_revision,target_evidence.stage_revision,target_evidence.completion)==
            (command.task_id,command.expected_revision,command.expected_stage_revision,old_stage['completion']),'STAGE_ORDER_TARGET_DRIFT')
    for e in order.executions:require(all(t is None or t<=now for t in (e.started_at,e.completed_at)),'STAGE_FUTURE_EXECUTION')
    reported=f.get('completed_at')
    if reported is not None:require(instant(reported)<=now and (target_evidence is None or target_evidence.started_at is None or target_evidence.started_at<=instant(reported)),'STAGE_REPORTED_TIME_CONFLICT')
    issues=[];relation_pins=[]
    if command.operation=='COMPLETE':
        for r in order.relations:
            if r.relation.after!=target or r.relation.kind not in ('COMPLETION_ORDER','START_PREREQUISITE'):continue
            prior=executions.get(r.relation.before)
            if prior is None:return PreparedStageCommand('PENDING','STAGE_ORDER_EVIDENCE_UNRESOLVED',missing_fields=('execution:'+r.relation.before.id,))
            require(prior.task_id==r.before.task_id and r.after.task_id==command.task_id,'STAGE_ORDER_OWNER_DRIFT')
            threshold=instant(reported) if r.relation.kind=='COMPLETION_ORDER' and reported is not None else target_evidence.started_at if r.relation.kind=='START_PREREQUISITE' and target_evidence is not None else None
            code='PREREQUISITE_INCOMPLETE' if prior.completion=='INCOMPLETE' else 'ORDER_EVIDENCE_MISSING' if prior.completed_at is None or threshold is None else 'ORDER_VIOLATION' if prior.completed_at>threshold else None
            if code:issues.append(dict(code=code,relation_id=r.relation.relation_id,relation_revision=r.relation.revision,kind=r.relation.kind))
            relation_pins.append(dict(payload=r.payload,execution=asdict(prior)))
    require(before.revision<MAX_REVISION and detail['revision']<MAX_REVISION,'STAGE_REVISION_LIMIT')
    value=deepcopy(original);stage=value['effort']['stages'][index];detail=next(d for d in value['stage_details'] if d['stage_id']==command.stage_id)
    value['core']['revision']=value['effort']['task_revision']=before.revision+1;sources={};estimates=[]
    def estimate(role,seconds):
        observation=PreparedUserEstimate('observation-'+sha256(canonical([command.fingerprint,grant.evidence_ref,role]).encode()).hexdigest(),before.task_id,seconds,grant.source_observed_at,grant.evidence_ref,command.authority_ref)
        estimates.append(observation)
        return dict(seconds=seconds,observation_id=observation.observation_id,observed_at=grant.source_observed_at.isoformat(),verified_at=grant.source_observed_at.isoformat())
    if 'parent_remaining_seconds' in f:
        value['effort']['user_remaining']=estimate('PARENT',f['parent_remaining_seconds']) if f['parent_remaining_seconds'] is not None else None
        sources['/effort/user_remaining']=grant.evidence_ref
    if command.operation=='REWORK':
        stage['completion']='INCOMPLETE';stage['user_remaining']=estimate('STAGE',f['stage_remaining_seconds']) if f.get('stage_remaining_seconds') is not None else None
        value['core']['completion']=value['effort']['completion']='INCOMPLETE';value['timing']['completed_at']=None
        sources.update({'/core/completion':grant.evidence_ref,'/effort/completion':grant.evidence_ref,'/timing/completed_at':grant.evidence_ref})
    else:
        stage['completion']='COMPLETE'
        if old_stage['completion']!='COMPLETE' or 'stage_remaining_seconds' in f:stage['user_remaining']=estimate('STAGE',0)
    if stage!=old_stage:detail['revision']+=1
    sources[f'/effort/stages/{index}/completion']=grant.evidence_ref
    if stage['user_remaining']!=old_stage['user_remaining']:sources[f'/effort/stages/{index}/user_remaining']=grant.evidence_ref
    if value['effort']['prediction'] is not None:value['effort']['prediction'].update(valid=False,applicable=False)
    provenance={p['field']:p['source_ref'] for p in value['provenance'] if not any(p['field'].startswith(k+'/') for k in sources)}
    provenance.update(sources);value['provenance']=[dict(field=k,source_ref=v) for k,v in sorted(provenance.items())]
    transition=dict(command=command.as_record(),command_fingerprint=command.fingerprint,source_ref=grant.evidence_ref,source_observed_at=grant.source_observed_at.isoformat(),
        previous_parent_revision=before.revision,parent_revision=before.revision+1,previous_stage_revision=command.expected_stage_revision,stage_revision=detail['revision'],
        previous_parent_completion=original['core']['completion'],previous_stage_completion=old_stage['completion'],previous_parent_completed_at=original['timing']['completed_at'],
        reported_completed_at=reported,issues=issues,order_snapshot=serial_time(relation_pins))
    return PreparedStageCommand('PREPARED','STAGE_EFFECTS_PREPARED',admit_storage(codec,canonical(value).encode()),tuple(estimates),canonical(transition))
