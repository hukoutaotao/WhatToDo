"""Exact single-Task fact edits; schema support never supplies user authority."""
from copy import deepcopy
from dataclasses import dataclass,field
from datetime import datetime
from hashlib import sha256
import re

from src.application.command_validation import PreparedUserEstimate
from src.application.definitions import canonical,identity,strict_json
from src.application.task_storage import TaskStorageRecord,admit_storage
from src.application.transactions import require
from src.domain.time_windows import NormalizedDue,normalize_due

VERSION='0.1.0-task-fact-patch'
FIELDS=frozenset(('title','importance','difficulty','requiredness','expiration_condition_ref','user_remaining_seconds','deadline'))


@dataclass(frozen=True)
class FactPatch:
    command_id: str
    principal_id: str
    authority_ref: str
    task_id: str
    expected_revision: int
    fields_json: str = field(repr=False)

    def __post_init__(self):
        require(all(identity(v) for v in (self.command_id,self.principal_id,self.authority_ref,self.task_id))
            and type(self.expected_revision) is int and self.expected_revision>0,'FACT_PATCH_IDENTITY')
        require(isinstance(self.fields_json,str) and len(self.fields_json.encode())<=262144,'FACT_PATCH_SIZE_LIMIT')
        f=self.fields;require(isinstance(f,dict) and f and not set(f)-FIELDS,'FACT_PATCH_FIELDS')
        if 'title' in f:require(isinstance(f['title'],str) and f['title'].strip() and '\x00' not in f['title'] and len(f['title'])<=500,'FACT_PATCH_VALUE')
        if 'importance' in f:require(type(f['importance']) is int and 1<=f['importance']<=5,'FACT_PATCH_VALUE')
        if 'difficulty' in f:
            d=f['difficulty'];require(isinstance(d,dict) and set(d)=={'thinking_depth','repetitive_volume','new_learning_load'}
                and all(type(v) is int and 1<=v<=5 for v in d.values()),'FACT_PATCH_VALUE')
        if 'requiredness' in f:require(f['requiredness'] in ('REQUIRED','OPTIONAL','EXPIRING'),'FACT_PATCH_VALUE')
        if 'expiration_condition_ref' in f:require(f['expiration_condition_ref'] is None or identity(f['expiration_condition_ref']),'FACT_PATCH_VALUE')
        if 'user_remaining_seconds' in f:require(f['user_remaining_seconds'] is None or type(f['user_remaining_seconds']) is int and f['user_remaining_seconds']>=0,'FACT_PATCH_VALUE')
        if f.get('deadline') is not None:
            v=f['deadline'];require(isinstance(v,str) and re.fullmatch(r'\d{4}-\d{2}-\d{2}(?:T\d{2}:\d{2}:\d{2}(?:\.\d{1,6})?(?:Z|[+-]\d{2}:\d{2}))?',v),
                'FACT_PATCH_SOURCE_TIME')
            try:normalize_due(v,source_ref=self.authority_ref)
            except ValueError:require(False,'FACT_PATCH_SOURCE_TIME')
        object.__setattr__(self,'fields_json',canonical(f))

    @property
    def fields(self):return strict_json(self.fields_json)
    def as_record(self):return dict(schema_version=VERSION,command_id=self.command_id,principal_id=self.principal_id,
        origin='USER_COMMAND',authority_ref=self.authority_ref,target_ref=dict(task_id=self.task_id,revision=self.expected_revision),fields=self.fields)
    @property
    def fingerprint(self):return sha256(canonical(self.as_record()).encode()).hexdigest()


def admit_fact_patch(codec,raw):
    require(isinstance(raw,bytes) and 0<len(raw)<=262144,'FACT_PATCH_SIZE_LIMIT')
    admission=codec.admit('task-fact-patch',raw);require(admission.status=='SUPPORTED_SHAPE','FACT_PATCH_SHAPE_UNSUPPORTED')
    v=admission.payload
    return FactPatch(v['command_id'],v['principal_id'],v['authority_ref'],v['target_ref']['task_id'],
        v['target_ref']['revision'],canonical(v['fields']))


@dataclass(frozen=True)
class FactPatchGrant:
    patch: FactPatch = field(repr=False)
    evidence_ref: str
    issued_at: datetime
    expires_at: datetime | None = None
    source_observed_at: datetime | None = None
    active: bool = True

    def __post_init__(self):
        require(isinstance(self.patch,FactPatch) and identity(self.evidence_ref) and type(self.active) is bool,
            'FACT_PATCH_TYPED_GRANT')
        for v in (self.issued_at,self.expires_at,self.source_observed_at):
            require(v is None or isinstance(v,datetime) and v.utcoffset() is not None,'FACT_PATCH_GRANT_TIME')
        require(self.issued_at is not None and (self.expires_at is None or self.issued_at<self.expires_at),'FACT_PATCH_GRANT_TIME')

    def as_record(self):return dict(contract='task-fact-patch',command=self.patch.as_record(),active=self.active,
        source_observed_at=self.source_observed_at.isoformat() if self.source_observed_at is not None else None)


def validate_patch_grant(patch,grant,*,now):
    require(isinstance(grant,FactPatchGrant),'UNREGISTERED_AUTHORITY')
    require(grant.patch.fingerprint==patch.fingerprint,'FACT_PATCH_EXACT_SCOPE_MISMATCH')
    require(grant.active and grant.issued_at<=now and (grant.expires_at is None or now<grant.expires_at),'INACTIVE_AUTHORITY')
    require(grant.source_observed_at is None or grant.source_observed_at<=now,'FACT_PATCH_FUTURE_OBSERVATION')


@dataclass(frozen=True)
class PreparedDue:
    due_id: str
    task_id: str
    authority_ref: str
    value: NormalizedDue = field(repr=False)

    def __post_init__(self):require(all(identity(v) for v in (self.due_id,self.task_id,self.authority_ref))
        and isinstance(self.value,NormalizedDue),'FACT_PATCH_TYPED_DUE')
    @property
    def row(self):return (self.value.input_kind,self.value.original_value,self.value.source_ref,self.value.instant,self.value.default_policy_ref)


@dataclass(frozen=True)
class PreparedFactPatch:
    record: TaskStorageRecord = field(repr=False)
    estimates: tuple[PreparedUserEstimate,...]
    dues: tuple[PreparedDue,...]


def prepare_fact_patch(codec,patch,grant,before,*,now):
    validate_patch_grant(patch,grant,now=now)
    require(isinstance(before,TaskStorageRecord) and before.task_id==patch.task_id,'UNKNOWN_TARGET')
    require(before.revision==patch.expected_revision,'STALE_STATE_VERSION')
    v=deepcopy(before.aggregate.as_record());f=patch.fields;sources={};observations=();dues=()
    v['core']['revision']=v['effort']['task_revision']=before.revision+1
    if v['effort']['prediction'] is not None:
        v['effort']['prediction']['valid']=False;v['effort']['prediction']['applicable']=False
    for name in ('title','importance','difficulty','requiredness'):
        if name in f:v['core'][name]=f[name];sources['/core/'+name]=grant.evidence_ref
    if v['core']['disposition']=='EXPIRED':
        require(v['core']['requiredness']=='EXPIRING' and 'expiration_condition_ref' not in f,'FACT_PATCH_EXPIRED_STATE_CONFLICT')
    elif 'requiredness' in f or 'expiration_condition_ref' in f:
        condition=f.get('expiration_condition_ref',v['core']['expiration']['condition_ref'] if v['core']['expiration'] else None)
        if v['core']['requiredness']=='EXPIRING':
            require(identity(condition),'FACT_PATCH_EXPIRATION_CONDITION_REQUIRED')
            v['core']['expiration']=dict(condition_ref=condition,notice_ref=None)
        else:
            require(f.get('expiration_condition_ref') is None,'FACT_PATCH_EXPIRATION_REQUIREDNESS_CONFLICT')
            v['core']['expiration']=None
        if 'expiration_condition_ref' in f or v['core']['expiration']!=before.aggregate.as_record()['core']['expiration']:
            sources['/core/expiration']=grant.evidence_ref
    if 'user_remaining_seconds' in f:
        seconds=f['user_remaining_seconds']
        require(v['core']['completion']!='COMPLETE' or seconds==0,'FACT_PATCH_COMPLETED_REMAINING_CONFLICT')
        estimate=None
        if seconds is not None:
            require(grant.source_observed_at is not None,'FACT_PATCH_OBSERVATION_TIME_REQUIRED')
            observation=PreparedUserEstimate('observation-'+sha256((patch.fingerprint+grant.evidence_ref).encode()).hexdigest(),
                patch.task_id,seconds,grant.source_observed_at,grant.evidence_ref,patch.authority_ref)
            estimate=dict(seconds=seconds,observation_id=observation.observation_id,
                observed_at=grant.source_observed_at.isoformat(),verified_at=grant.source_observed_at.isoformat())
            observations=(observation,)
        v['effort']['user_remaining']=estimate;sources['/effort/user_remaining']=grant.evidence_ref
    if 'deadline' in f:
        deadline=None
        if f['deadline'] is not None:
            due=PreparedDue('due-'+sha256((patch.fingerprint+grant.evidence_ref).encode()).hexdigest(),patch.task_id,
                patch.authority_ref,normalize_due(f['deadline'],source_ref=grant.evidence_ref))
            deadline=dict(due_ref=due.due_id,value=due.value.as_record());dues=(due,)
        v['timing']['deadline']=deadline;v['core']['metadata']['overdue']='UNKNOWN';sources['/timing/deadline']=grant.evidence_ref
    # Clearing/replacing an object makes its former child pointers invalid.
    # Their old sources remain in the immutable before-revision; the new value
    # carries the source for the explicitly changed parent, including null.
    provenance={p['field']:p['source_ref'] for p in v['provenance']
        if not any(p['field'].startswith(path+'/') for path in sources)};provenance.update(sources)
    v['provenance']=[dict(field=path,source_ref=source) for path,source in sorted(provenance.items())]
    return PreparedFactPatch(admit_storage(codec,canonical(v).encode()),observations,dues)
