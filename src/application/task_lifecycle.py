"""Explicit parent completion/cancellation; no inferred work or timestamps."""
from copy import deepcopy
from dataclasses import dataclass,field
from datetime import datetime
from hashlib import sha256

from src.application.command_validation import AdmittedCommand,PreparedUserEstimate,admit_command,task_state
from src.application.definitions import canonical
from src.application.task_storage import TaskStorageRecord,admit_storage
from src.application.transactions import require
from src.domain.authorization import AuthorityGrant,authorize


def admit_lifecycle_command(codec,raw,operation):
    require(operation in ('COMPLETE','CANCEL'),'LIFECYCLE_OPERATION_REQUIRED')
    admitted=admit_command(codec,raw);command=admitted.command
    require(command.origin=='USER_COMMAND' and len(command.changes)==1 and command.batch_ref is None,
        'LIFECYCLE_SINGLE_USER_COMMAND_REQUIRED')
    c=command.changes[0];f=c.fields
    require(c.action=='UPDATE_TASK','LIFECYCLE_EXISTING_TASK_REQUIRED')
    if operation=='COMPLETE':
        require(f.get('completion')=='COMPLETE' and set(f)<= {'completion','user_remaining_seconds','disposition'}
            and ('user_remaining_seconds' not in f or type(f['user_remaining_seconds']) is int and f['user_remaining_seconds']==0)
            and ('disposition' not in f or f['disposition']=='ACTIVE'),'LIFECYCLE_COMPLETION_SCOPE_REQUIRED')
    else:
        require(f=={'disposition':'CANCELLED'},'LIFECYCLE_CANCELLATION_SCOPE_REQUIRED')
    return admitted


@dataclass(frozen=True)
class PreparedLifecycleTask:
    record: TaskStorageRecord = field(repr=False)
    estimates: tuple[PreparedUserEstimate,...]


def prepare_lifecycle_task(codec,admitted,grant,before,*,operation,caller,source_observed_at,now):
    require(isinstance(admitted,AdmittedCommand) and isinstance(grant,AuthorityGrant),'LIFECYCLE_TYPED_AUTHORITY_REQUIRED')
    # Re-admit to make this public pure helper enforce the endpoint's allowlist,
    # even when its caller obtained AdmittedCommand from the general service.
    checked=admit_lifecycle_command(codec,admitted.raw_bytes,operation)
    require(checked.command==admitted.command,'LIFECYCLE_COMMAND_DRIFT')
    command=admitted.command;c=command.changes[0]
    require(isinstance(before,TaskStorageRecord) and before.task_id==c.task_id,'UNKNOWN_TARGET')
    decision=authorize(command,caller=caller,grants={grant.grant_id:grant},tasks={before.task_id:task_state(before)},now=now)
    require(decision.allowed,decision.reason)
    v=deepcopy(before.aggregate.as_record());original=before.aggregate.as_record();sources={};estimates=[]
    v['core']['revision']=v['effort']['task_revision']=before.revision+1
    if v['effort']['prediction'] is not None:
        v['effort']['prediction']['valid']=False;v['effort']['prediction']['applicable']=False
    if operation=='COMPLETE':
        require(v['core']['disposition']=='ACTIVE' or c.fields.get('disposition')=='ACTIVE',
            'LIFECYCLE_REACTIVATION_REQUIRED')
        if 'disposition' in c.fields:
            v['core']['disposition']=v['effort']['disposition']='ACTIVE'
            sources['/core/disposition']=grant.evidence_ref;sources['/effort/disposition']=grant.evidence_ref
        needs_zero=original['core']['completion']!='COMPLETE' or 'user_remaining_seconds' in c.fields
        incomplete=[(i,s) for i,s in enumerate(v['effort']['stages']) if s['completion']=='INCOMPLETE']
        if needs_zero or incomplete:
            require(isinstance(source_observed_at,datetime) and source_observed_at.utcoffset() is not None
                and source_observed_at<=now,'LIFECYCLE_SOURCE_OBSERVATION_TIME_REQUIRED')
        def zero(role):
            observation=PreparedUserEstimate('observation-'+sha256(canonical([command.fingerprint,grant.evidence_ref,role,'COMPLETE']).encode()).hexdigest(),
                before.task_id,0,source_observed_at,grant.evidence_ref,grant.grant_id)
            estimates.append(observation)
            return dict(seconds=0,observation_id=observation.observation_id,observed_at=source_observed_at.isoformat(),
                verified_at=source_observed_at.isoformat())
        v['core']['completion']=v['effort']['completion']='COMPLETE'
        sources['/core/completion']=sources['/effort/completion']=grant.evidence_ref
        if needs_zero:
            v['effort']['user_remaining']=zero('PARENT');sources['/effort/user_remaining']=grant.evidence_ref
        for index,stage in incomplete:
            stage['completion']='COMPLETE';stage['user_remaining']=zero('STAGE:'+stage['stage_id'])
            detail=next(d for d in v['stage_details'] if d['stage_id']==stage['stage_id']);detail['revision']+=1
            sources[f'/effort/stages/{index}/completion']=grant.evidence_ref
            sources[f'/effort/stages/{index}/user_remaining']=grant.evidence_ref
        # No reported actual completion timestamp exists in this contract.
        # Capturing the confirmation does not supply the work's finished_at.
    else:
        v['core']['disposition']=v['effort']['disposition']='CANCELLED'
        sources['/core/disposition']=sources['/effort/disposition']=grant.evidence_ref
    if original['core']['disposition']=='EXPIRED' and v['core']['disposition']!='EXPIRED':
        v['core']['expiration']['notice_ref']=None;sources['/core/expiration']=grant.evidence_ref
    provenance={p['field']:p['source_ref'] for p in v['provenance']
        if not any(p['field'].startswith(path+'/') for path in sources)};provenance.update(sources)
    v['provenance']=[dict(field=path,source_ref=source) for path,source in sorted(provenance.items())]
    return PreparedLifecycleTask(admit_storage(codec,canonical(v).encode()),tuple(estimates))
