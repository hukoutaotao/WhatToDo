"""Strict command admission and complete Task effects bound to trusted grants."""
from copy import deepcopy
from dataclasses import dataclass,field
from datetime import datetime,timedelta
from hashlib import sha256
import json

from src.application.ports import AggregateKey,CommitRequest,TransactionPermit
from src.application.task_storage import TaskStorageRecord,admit_storage
from src.application.transactions import require
from src.application.definitions import identity,strict_json
from src.domain.authorization import (AuthorityGrant,Command,RuleScope,TaskState,
    authorize,change)
from src.domain.task_aggregate import instant


@dataclass(frozen=True)
class AdmittedCommand:
    command: Command = field(repr=False)
    raw_bytes: bytes = field(repr=False)
    raw_hash: str


def admit_command(codec,raw):
    require(isinstance(raw,bytes) and 0<len(raw)<=1048576,'COMMAND_SIZE_LIMIT')
    wire=codec.admit('command',raw)
    require(wire.status=='SUPPORTED_SHAPE','COMMAND_SHAPE_UNSUPPORTED')
    value=wire.payload
    require(len(value['changes'])<=100,'COMMAND_SIZE_LIMIT')
    try:
        command=Command(value['command_id'],value['principal_id'],value['origin'],
            value['authority_ref'],tuple(change(**item) for item in value['changes']),
            RuleScope(**value['rule_scope']) if value['rule_scope'] is not None else None,
            value['batch_ref'],tuple(value['batch_members']))
    except (TypeError,ValueError):
        require(False,'COMMAND_DOMAIN_INVALID')
    return AdmittedCommand(command,raw,sha256(raw).hexdigest())


def grant_record(grant):
    command=Command(grant.command_id,grant.principal_id,grant.origin,grant.grant_id,
        grant.changes,grant.rule_scope,grant.batch_ref,grant.batch_members)
    return dict(command=command.as_record(),active=grant.active,
        essential_fields=sorted(grant.essential_fields))


def task_state(record):
    core=record.aggregate.as_record()['core']
    return TaskState(record.task_id,record.revision,core['requiredness'],core['completion'],
        core['disposition'],core['expiration']['condition_ref'] if core['expiration'] else None)


@dataclass(frozen=True)
class AuthorizedEffects:
    permit: TransactionPermit = field(repr=False)
    context_json: str = field(repr=False)

    @property
    def context(self):return json.loads(self.context_json)


@dataclass(frozen=True)
class CreationProvenance:
    task_id: str
    seed_hash: str
    details_json: str = field(repr=False)

    def __post_init__(self):
        require(identity(self.task_id) and isinstance(self.seed_hash,str) and
            len(self.seed_hash)==64 and all(c in '0123456789abcdef' for c in self.seed_hash),
            'COMMAND_CREATION_PROVENANCE')
        require(isinstance(self.details_json,str) and len(self.details_json.encode('utf-8'))<=1048576
            and isinstance(strict_json(self.details_json),dict),'COMMAND_CREATION_PROVENANCE')

    @property
    def details(self):return strict_json(self.details_json)


@dataclass(frozen=True)
class PreparedUserEstimate:
    observation_id: str
    task_id: str
    seconds: int
    observed_at: datetime
    source_ref: str
    authority_ref: str

    def __post_init__(self):
        require(all(identity(s) for s in (self.observation_id,self.task_id,self.source_ref,self.authority_ref))
            and type(self.seconds) is int and self.seconds>=0 and isinstance(self.observed_at,datetime)
            and self.observed_at.utcoffset() is not None,'COMMAND_USER_OBSERVATION')

    @property
    def row(self):return (self.observation_id,self.task_id,'USER_REMAINING',self.seconds,
        self.observed_at,self.source_ref,self.authority_ref)


def validate_effects(codec,admitted,request,*,caller,grant,records,seeds=(),
                     observations=(),creations=(),notices=(),now):
    require(isinstance(admitted,AdmittedCommand) and isinstance(request,CommitRequest),
        'COMMAND_TYPED_VALUES_REQUIRED')
    command=admitted.command
    require(isinstance(grant,AuthorityGrant),'UNREGISTERED_AUTHORITY')
    require((request.context.request_id,request.principal_id,request.source_ref)==
        (command.command_id,command.principal_id,grant.evidence_ref),'COMMAND_REQUEST_BINDING_MISMATCH')
    require({w.key for w in request.writes}=={AggregateKey('TASK',c.task_id) for c in command.changes},
        'COMMAND_EFFECT_TARGET_MISMATCH')
    by_id={r.task_id:r for r in records};seed_by_id={r.task_id:r for r in seeds}
    decision=authorize(command,caller=caller,grants={grant.grant_id:grant},
        tasks={k:task_state(r) for k,r in by_id.items()},now=now,
        creations={c.event_id:c for c in creations},notices={n.notice_id:n for n in notices})
    require(decision.allowed,decision.reason)
    writes={w.key.id:w for w in request.writes}
    for item in command.changes:
        write=writes[item.task_id]
        require(write.expected_revision==item.expected_revision,'COMMAND_EFFECT_REVISION_MISMATCH')
        after=admit_storage(codec,write.body_json.encode('utf-8'))
        require((after.task_id,after.revision)==(item.task_id,(item.expected_revision or 0)+1),
            'COMMAND_EFFECT_REVISION_MISMATCH')
        if item.action=='CREATE_TASK':
            seed=seed_by_id.get(item.task_id)
            require(isinstance(seed,TaskStorageRecord),'COMMAND_TRUSTED_CREATION_SEED_REQUIRED')
            seed=admit_storage(codec,seed.raw_bytes)
            require(seed.revision==1 and seed.aggregate.as_record()['core']['acceptance']==
                dict(state='ACCEPTED',authority_ref=grant.grant_id),'COMMAND_CREATION_ACCEPTANCE_MISMATCH')
            expected=deepcopy(seed.aggregate.as_record())
            require(expected['core']['completion']=='INCOMPLETE' and
                expected['core']['disposition']=='ACTIVE' and
                expected['effort']['user_remaining'] is None and expected['effort']['prediction'] is None and
                all(s['completion']=='INCOMPLETE' and s['user_remaining'] is None
                    for s in expected['effort']['stages']) and
                all(v is None for v in expected['timing'].values()) and
                (expected['core']['expiration'] is None or
                    expected['core']['expiration']['notice_ref'] is None),
                'COMMAND_CREATION_SEED_CANNOT_ASSERT_OUTCOME')
        else:
            expected=deepcopy(by_id[item.task_id].aggregate.as_record())
        expected['core']['revision']=expected['effort']['task_revision']=after.revision
        if expected['effort']['prediction'] is not None and \
                expected['effort']['prediction']['task_revision']!=after.revision:
            expected['effort']['prediction']['valid']=False
            expected['effort']['prediction']['applicable']=False
        actual=after.aggregate.as_record();fields=item.fields
        for name in ('title','requiredness','importance','difficulty','completion','disposition'):
            if name in fields:expected['core'][name]=deepcopy(fields[name])
        for name in ('completion','disposition'):
            if name in fields:expected['effort'][name]=fields[name]
        if 'expiration_condition_ref' in fields:
            ref=fields['expiration_condition_ref']
            if ref is None:expected['core']['expiration']=None
            elif expected['core']['expiration'] is None:
                expected['core']['expiration']=dict(condition_ref=ref,notice_ref=None)
            else:expected['core']['expiration']['condition_ref']=ref
        if 'expiration_notice_ref' in fields:
            require(expected['core']['expiration'] is not None,'COMMAND_EXPIRATION_BINDING_REQUIRED')
            expected['core']['expiration']['notice_ref']=fields['expiration_notice_ref']
        # Removing EXPIRING also removes its condition, never an unrelated fact.
        if 'requiredness' in fields and fields['requiredness']!='EXPIRING':
            expected['core']['expiration']=None
        clears_notice=(item.action=='UPDATE_TASK' and by_id[item.task_id].aggregate.as_record()['core']['disposition']=='EXPIRED'
            and fields.get('disposition') in ('ACTIVE','CANCELLED'))
        if clears_notice and expected['core']['expiration'] is not None:
            expected['core']['expiration']['notice_ref']=None
        requested_u=fields.get('user_remaining_seconds','UNCHANGED')
        if fields.get('completion')=='COMPLETE':
            require(requested_u in ('UNCHANGED',0),'COMMAND_COMPLETION_REQUIRES_ZERO_U')
            requested_u=0
        if requested_u!='UNCHANGED':
            candidate=actual['effort']['user_remaining']
            require((candidate['seconds'] if candidate else None)==requested_u,'COMMAND_EFFECT_VALUE_MISMATCH')
            if candidate!=expected['effort']['user_remaining']:
                _estimate(candidate,item.task_id,grant,observations,now)
            expected['effort']['user_remaining']=deepcopy(candidate)
        if fields.get('completion')=='COMPLETE':
            require(len(actual['effort']['stages'])==len(expected['effort']['stages']),
                'COMMAND_UNAUTHORIZED_EFFECT')
            for stage,new in zip(expected['effort']['stages'],actual['effort']['stages']):
                if stage['completion']=='INCOMPLETE':
                    require(new['user_remaining'] is not None and new['user_remaining']['seconds']==0,
                        'COMMAND_COMPLETION_REQUIRES_ZERO_U')
                    _estimate(new['user_remaining'],item.task_id,grant,observations,now)
                    stage['completion']='COMPLETE'
                    detail=next(d for d in expected['stage_details'] if d['stage_id']==stage['stage_id'])
                    detail['revision']+=1
                    stage['user_remaining']=deepcopy(new['user_remaining'])
        # Provenance may change only for the declared fields, to this exact statement.
        pointers={'/core/'+name for name in fields if name in
            ('title','requiredness','importance','difficulty','completion','disposition')}
        pointers.update('/effort/'+name for name in ('completion','disposition') if name in fields)
        if fields.get('completion')=='COMPLETE':
            old_stages=by_id[item.task_id].aggregate.as_record()['effort']['stages'] if item.action!='CREATE_TASK' else []
            for index,stage in enumerate(old_stages):
                if stage['completion']=='INCOMPLETE':
                    pointers.update((f'/effort/stages/{index}/completion',f'/effort/stages/{index}/user_remaining'))
        if requested_u!='UNCHANGED':pointers.add('/effort/user_remaining')
        if any(n.startswith('expiration_') for n in fields):pointers.add('/core/expiration')
        if clears_notice:pointers.add('/core/expiration')
        old_prov={p['field']:p for p in expected['provenance']}
        new_prov={p['field']:p for p in actual['provenance']}
        for pointer in set(old_prov)|set(new_prov):
            if old_prov.get(pointer)!=new_prov.get(pointer):
                direct=pointer in pointers
                parents=[p for p in pointers if pointer.startswith(p+'/')]
                require((direct or parents) and
                    ((pointer in new_prov and new_prov[pointer]['source_ref']==grant.evidence_ref) or
                    (not direct and pointer not in new_prov and any(p in new_prov and
                    new_prov[p]['source_ref']==grant.evidence_ref for p in parents))),
                    'COMMAND_UNAUTHORIZED_PROVENANCE')
        expected['provenance']=deepcopy(actual['provenance'])
        require(actual==expected,'COMMAND_UNAUTHORIZED_EFFECT')
    end=now+timedelta(minutes=5)
    if grant.expires_at is not None:end=min(end,grant.expires_at)
    permit_ref='permit-'+sha256((command.fingerprint+request.fingerprint).encode()).hexdigest()
    permit=TransactionPermit(permit_ref,caller.principal_id,caller.origin,request.fingerprint,now,end)
    context=dict(command_fingerprint=command.fingerprint,command_wire_hash=admitted.raw_hash,
        grant_ref=grant.grant_id,command=command.as_record())
    return AuthorizedEffects(permit,json.dumps(context,sort_keys=True,separators=(',',':')))


def _estimate(value,task_id,grant,observations,now):
    if value is None:return
    found=next((o for o in observations if o[0]==value['observation_id']),None)
    require(found is not None and found[1:]==(task_id,'USER_REMAINING',value['seconds'],
        instant(value['observed_at']),grant.evidence_ref,grant.grant_id),'COMMAND_UNRESOLVED_EFFORT_FACT')
    require(instant(value['observed_at'])<=instant(value['verified_at'])<=now,
        'COMMAND_UNRESOLVED_EFFORT_FACT')
