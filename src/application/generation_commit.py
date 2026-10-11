"""Composite generation preparation; exact fingerprints, never mutation permits."""
from dataclasses import dataclass,field,replace,asdict
from hashlib import sha256
import re

from src.application.definitions import canonical,strict_json,identity
from src.application.generation_evaluator import (GenerationSource,AcceptedGenerationRule,
    GenerationDraft,evaluate_generation,require)
from src.application.ports import (AggregateKey,RecordWrite,CommitRequest,CommitReceipt,RequestContext)
from src.application.task_storage import TaskStorageRecord
from src.application.relationship_storage import RelationStorageRecord,EndpointBinding
from src.domain.authorization import RuleScope
from src.domain.relationships import TaskRelation,Endpoint


def digest(value):return sha256(canonical(value).encode()).hexdigest()


def generation_scope(source,use):
    require(isinstance(source,GenerationSource) and isinstance(use,AcceptedGenerationRule)
        and source.event.principal_id==use.principal_id,'GENERATION_COMMIT_SOURCE_SCOPE')
    r=use.record.rule;e=source.event
    return RuleScope(r.rule_id,r.version,e.task_id,e.event_id,e.event_id,r.target_role)


def target_identity(scope,obligation_kind):
    require(isinstance(scope,RuleScope) and obligation_kind in ('SEPARATE_TASK','STAGE'),'GENERATION_COMMIT_IDENTITY')
    return ('generated-task-' if obligation_kind=='SEPARATE_TASK' else 'generated-stage-')+digest(scope.generation_key)


def relation_spec(body,obligation_kind):
    value=body.get('relation')
    if value is None:
        return dict(kind='STAGE_MEMBERSHIP',direction='SOURCE_TO_TARGET') if obligation_kind=='STAGE' else None
    require(isinstance(value,dict) and set(value)=={'kind','direction'} and
        value['direction'] in ('SOURCE_TO_TARGET','TARGET_TO_SOURCE'),'GENERATION_COMMIT_RELATION_SPEC')
    require((obligation_kind=='STAGE' and value==dict(kind='STAGE_MEMBERSHIP',direction='SOURCE_TO_TARGET')) or
        (obligation_kind=='SEPARATE_TASK' and value['kind'] in ('COMPLETION_ORDER','START_PREREQUISITE','SOFT_SEQUENCE')),
        'GENERATION_COMMIT_RELATION_SPEC')
    return dict(value)


@dataclass(frozen=True)
class GenerationOccurrenceRecord:
    scope: RuleScope
    source_task_revision: int
    creation_transaction_ref: str
    obligation_kind: str
    state: str
    revision: int
    target_task_ref: str | None = None
    target_stage_ref: str | None = None
    target_stage_revision: int | None = None
    failure_code: str | None = None
    missing_fields: tuple[str,...] = ()
    relation_ref: str | None = None
    relation_revision: int | None = None
    manifest_json: str = field(default='{}',repr=False)

    def __post_init__(self):
        require(isinstance(self.scope,RuleScope) and type(self.source_task_revision) is int and 0<self.source_task_revision<=9223372036854775807
            and identity(self.creation_transaction_ref) and type(self.revision) is int and 0<self.revision<=9223372036854775807
            and self.obligation_kind in ('SEPARATE_TASK','STAGE'),'GENERATION_OCCURRENCE_IDENTITY')
        require(self.scope.occurrence_key==self.scope.creation_event_ref,'GENERATION_OCCURRENCE_SOURCE_EVENT')
        require(isinstance(self.missing_fields,tuple) and self.missing_fields==tuple(sorted(set(self.missing_fields)))
            and len(self.missing_fields)<=100 and all(isinstance(p,str) and p.startswith('/') and len(p)<=4096 for p in self.missing_fields),
            'GENERATION_OCCURRENCE_MISSING_FIELDS')
        created=self.state=='CREATED'
        require((created and not self.missing_fields and self.failure_code is None and
            ((self.obligation_kind=='SEPARATE_TASK' and identity(self.target_task_ref) and self.target_stage_ref is None and self.target_stage_revision is None)
             or (self.obligation_kind=='STAGE' and self.target_task_ref is None and identity(self.target_stage_ref)
                 and type(self.target_stage_revision) is int and self.target_stage_revision==1)))
            or (self.state=='PENDING' and bool(self.missing_fields) and self.failure_code is None)
            or (self.state=='FAILED' and not self.missing_fields and isinstance(self.failure_code,str) and re.fullmatch('[A-Z][A-Z0-9_]{0,63}',self.failure_code)),
            'GENERATION_OCCURRENCE_STATE')
        if not created:require(all(v is None for v in (self.target_task_ref,self.target_stage_ref,self.target_stage_revision,self.relation_ref,self.relation_revision)),
                               'GENERATION_OCCURRENCE_UNCREATED_TARGET')
        require((self.relation_ref is None and self.relation_revision is None) or
            (created and identity(self.relation_ref) and type(self.relation_revision) is int and self.relation_revision==1),'GENERATION_OCCURRENCE_RELATION')
        require(isinstance(self.manifest_json,str) and 0<len(self.manifest_json.encode())<=8388608
            and isinstance(strict_json(self.manifest_json),dict),'GENERATION_OCCURRENCE_MANIFEST')

    @property
    def payload(self):
        s=self.scope
        return dict(generation_key=s.generation_key,rule_id=s.rule_id,rule_version=s.version,source_task_id=s.source_task_id,
            source_task_revision=self.source_task_revision,creation_transaction_ref=self.creation_transaction_ref,
            source_event_ref=s.creation_event_ref,occurrence_key=s.occurrence_key,target_role=s.target_role,
            obligation_kind=self.obligation_kind,state=self.state,revision=self.revision,target_task_ref=self.target_task_ref,
            target_stage_ref=self.target_stage_ref,target_stage_revision=self.target_stage_revision,failure_code=self.failure_code,
            missing_fields=list(self.missing_fields),relation_ref=self.relation_ref,relation_revision=self.relation_revision,
            manifest=strict_json(self.manifest_json))

    def sql_row(self,transaction_ref,audit_change_ref):
        require(identity(transaction_ref) and identity(audit_change_ref),'GENERATION_OCCURRENCE_TRANSACTION')
        p=self.payload;return {k:v for k,v in p.items() if k not in ('missing_fields','manifest')} | dict(
            missing_facts=dict(fields=p['missing_fields']),transaction_ref=transaction_ref,audit_change_ref=audit_change_ref,
            aggregate_kind='GENERATION_OCCURRENCE',runtime_payload=p)

    @classmethod
    def from_payload(cls,value):
        require(isinstance(value,dict),'GENERATION_OCCURRENCE_PAYLOAD')
        try:
            p=dict(value);key=p.pop('generation_key');manifest=p.pop('manifest');p['manifest_json']=canonical(manifest)
            scope=RuleScope(p.pop('rule_id'),p.pop('rule_version'),p.pop('source_task_id'),p.pop('source_event_ref'),p.pop('occurrence_key'),p.pop('target_role'))
            p['scope']=scope;p['missing_fields']=tuple(p['missing_fields']);record=cls(**p)
        except (TypeError,KeyError,ValueError):require(False,'GENERATION_OCCURRENCE_PAYLOAD')
        require(key==scope.generation_key and record.payload==value,'GENERATION_OCCURRENCE_PAYLOAD')
        return record


@dataclass(frozen=True)
class GenerationAuditChange:
    change_ref: str
    key: AggregateKey
    before_revision: int | None
    after_revision: int
    before_json: str | None = field(repr=False)
    after_json: str = field(repr=False)

    @property
    def tuple(self):
        return (self.key.kind,self.key.id,self.before_revision,self.after_revision,
                strict_json(self.before_json) if self.before_json is not None else None,strict_json(self.after_json))


@dataclass(frozen=True)
class GenerationCommitPlan:
    request: CommitRequest
    receipt: CommitReceipt
    permit_ref: str
    draft: GenerationDraft = field(repr=False)
    occurrence: GenerationOccurrenceRecord = field(repr=False)
    relation: RelationStorageRecord | None = field(repr=False)
    audits: tuple[GenerationAuditChange,...] = field(repr=False)
    observations: tuple = field(repr=False)

    @property
    def receipt_body(self):return asdict(self.receipt)

    @property
    def authorization_context(self):
        return dict(generation=self.occurrence.payload,rule_hash=self.draft.manifest['rule_hash'],
            observation_rows=[dict(observation_id=o.observation_id,task_id=o.task_id,seconds=o.seconds,
                observed_at=o.observed_at.isoformat(),source_ref=o.source_ref,authority_ref=o.authority_ref) for o in self.observations])


@dataclass(frozen=True)
class GenerationPreparation:
    state: str
    code: str
    plan: GenerationCommitPlan | None = field(default=None,repr=False)
    recorded: GenerationOccurrenceRecord | None = field(default=None,repr=False)


def prepare_generation_commit(codec,source,use,definitions,*,expected_store_revision,previous=None,
                              current_source=None,current_bindings=None,correlation_ref):
    """Re-evaluate a draft; compose all effects for a future scoped coordinator."""
    require(type(expected_store_revision) is int and 0<expected_store_revision<9223372036854775807 and identity(correlation_ref),
            'GENERATION_COMMIT_CONTEXT')
    scope=generation_scope(source,use);kind=use.record.rule.obligation_kind
    if previous is not None:
        require(isinstance(previous,GenerationOccurrenceRecord) and previous.scope.generation_key==scope.generation_key and
            (previous.source_task_revision,previous.creation_transaction_ref,previous.scope.creation_event_ref)==
            (source.event.task_revision,source.event.creation_transaction_ref,source.event.event_id),'GENERATION_COMMIT_PREVIOUS_SCOPE')
        require(previous.payload['manifest'].get('principal_id')==use.principal_id,'GENERATION_COMMIT_PREVIOUS_PRINCIPAL')
        if previous.state=='CREATED':return GenerationPreparation('ALREADY_RECORDED','GENERATION_CREATION_REPLAY',recorded=previous)
        require(previous.obligation_kind==kind,'GENERATION_COMMIT_OBLIGATION_CONFLICT')
    target_id=target_identity(scope,kind)
    draft=evaluate_generation(codec,source,use,definitions,target_id=target_id,parent=current_source,parent_bindings=current_bindings)
    if draft.state=='NOT_ELIGIBLE':return GenerationPreparation(draft.state,draft.code)
    state='CREATED' if draft.ready else 'FAILED' if draft.state=='CONFLICT' else 'PENDING'
    missing=draft.missing_fields if state=='PENDING' else ()
    require(state!='PENDING' or bool(missing),'GENERATION_COMMIT_PENDING_FACTS_REQUIRED')
    revision=1 if previous is None else previous.revision+1
    source_current=current_source or source.task
    require(isinstance(source_current,TaskStorageRecord) and source_current.task_id==source.event.task_id
        and source_current.revision>=source.event.task_revision,'GENERATION_COMMIT_CURRENT_SOURCE')
    spec=None
    if draft.ready:
        cached=definitions.get(use.record.template)
        spec=relation_spec(cached.body,kind)
    stamp=digest(dict(scope=scope.generation_key,revision=revision,epoch=expected_store_revision,draft=draft.manifest,
        state=state,current_source_hash=source_current.content_hash,relation=spec))
    transaction='generation-transaction-'+stamp;audit='generation-audit-'+stamp;permit='generation-permit-'+stamp
    relation=None
    if draft.ready and spec is not None:
        if kind=='STAGE':
            parent=draft.parent_after
            before=EndpointBinding(Endpoint('TASK',parent.task_id),parent.task_id,parent.revision)
            after=EndpointBinding(Endpoint('STAGE',target_id),parent.task_id,parent.revision,1)
        else:
            target=draft.target
            before=EndpointBinding(Endpoint('TASK',source_current.task_id),source_current.task_id,source_current.revision)
            after=EndpointBinding(Endpoint('TASK',target.task_id),target.task_id,target.revision)
            if spec['direction']=='TARGET_TO_SOURCE':before,after=after,before
        relation=RelationStorageRecord(TaskRelation('generation-link-'+digest(scope.generation_key),1,spec['kind'],
            before.endpoint,after.endpoint,permit,use.record.rule.rule_id,use.record.rule.version),before,after)
    manifest=draft.manifest | dict(principal_id=use.principal_id,relation=spec,
        source_current_revision=source_current.revision,source_current_hash=source_current.content_hash,
        target_payload_hash=draft.target.content_hash if draft.target else None,
        parent_payload_hash=draft.parent_after.content_hash if draft.parent_after else None)
    occurrence=GenerationOccurrenceRecord(scope,source.event.task_revision,source.event.creation_transaction_ref,kind,state,revision,
        target_task_ref=target_id if state=='CREATED' and kind=='SEPARATE_TASK' else None,
        target_stage_ref=target_id if state=='CREATED' and kind=='STAGE' else None,
        target_stage_revision=1 if state=='CREATED' and kind=='STAGE' else None,
        failure_code=draft.code if state=='FAILED' else None,missing_fields=missing,
        relation_ref=relation.relation.relation_id if relation else None,relation_revision=1 if relation else None,manifest_json=canonical(manifest))
    changes=[]
    if draft.ready:
        target=draft.target if kind=='SEPARATE_TASK' else draft.parent_after
        old=None if kind=='SEPARATE_TASK' else source_current
        changes.append((AggregateKey('TASK',target.task_id),old.revision if old else None,target.revision,
            old.aggregate.as_record() if old else None,target.aggregate.as_record()))
        if relation:changes.append((AggregateKey('TASK_RELATION',relation.relation.relation_id),None,1,None,relation.payload))
    changes.append((AggregateKey('GENERATION_OCCURRENCE',scope.generation_key),previous.revision if previous else None,revision,
        previous.payload if previous else None,occurrence.payload))
    changes.sort(key=lambda c:(c[0].kind,c[0].id))
    writes=tuple(RecordWrite(k,b,canonical(new)) for k,b,a,old,new in changes)
    request=CommitRequest(RequestContext(transaction,correlation_ref),use.principal_id,expected_store_revision,writes,audit,use.source_record_ref)
    require(sum(len(w.body_json.encode()) for w in writes)<=8388608,'GENERATION_COMMIT_SIZE_LIMIT')
    receipt=CommitReceipt(transaction,request.fingerprint,expected_store_revision+1,audit,tuple(w.key for w in writes))
    audits=tuple(GenerationAuditChange('change-'+digest([audit,k.kind,k.id,a]),k,b,a,
        canonical(old) if old is not None else None,canonical(new)) for k,b,a,old,new in changes)
    observations=tuple(replace(o,authority_ref=permit) for o in draft.observations)
    return GenerationPreparation('PREPARED','GENERATION_COMPOSITE_NOT_AUTHORIZED',
        GenerationCommitPlan(request,receipt,permit,draft,occurrence,relation,audits,observations))
