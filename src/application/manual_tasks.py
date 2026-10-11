"""Resolved manual creation and approved default snapshots; no transport auth."""
from dataclasses import dataclass,field
from datetime import datetime
from hashlib import sha256
import json

from src.application.command_validation import CreationProvenance,PreparedUserEstimate
from src.application.definitions import (DefinitionKey,canonical,defaults_from,identity,strict_json)
from src.application.ports import CommitReceipt
from src.application.task_storage import TaskStorageBindings,admit_storage
from src.application.transactions import require
from src.domain.authorization import Command


@dataclass(frozen=True)
class ApprovedDefaultUse:
    key: DefinitionKey
    acceptance_ref: str
    source_ref: str

    def __post_init__(self):
        require(isinstance(self.key,DefinitionKey) and self.key.kind in ('TASKTYPE','TASK_TEMPLATE')
            and identity(self.acceptance_ref) and identity(self.source_ref),'MANUAL_APPROVED_DEFAULT_USE')


@dataclass(frozen=True)
class ResolvedManualIntent:
    command_fingerprint: str
    source_ref: str
    source_observed_at: datetime
    facts_json: str = field(repr=False)
    default_uses: tuple[ApprovedDefaultUse,...] = ()

    def __post_init__(self):
        require(isinstance(self.command_fingerprint,str) and len(self.command_fingerprint)==64 and
            all(c in '0123456789abcdef' for c in self.command_fingerprint) and identity(self.source_ref)
            and isinstance(self.source_observed_at,datetime) and self.source_observed_at.utcoffset() is not None,
            'MANUAL_RESOLVED_INTENT')
        require(isinstance(self.facts_json,str) and len(self.facts_json.encode('utf-8'))<=1048576,
            'MANUAL_RESOLVED_FACTS')
        v=self.facts
        require(isinstance(v,dict) and set(v)<= {'domain','context','task_type_ref','profile_ref','template_ref',
            'minimum_session_seconds','fragmentable','total_estimate_seconds'},'MANUAL_RESOLVED_FACTS')
        require(isinstance(self.default_uses,tuple) and all(isinstance(u,ApprovedDefaultUse) for u in self.default_uses)
            and len({u.key for u in self.default_uses})==len(self.default_uses),'MANUAL_APPROVED_DEFAULT_USE')

    @property
    def facts(self):return strict_json(self.facts_json)

    @property
    def fingerprint(self):
        return sha256(canonical(dict(command=self.command_fingerprint,source=self.source_ref,
            observed_at=self.source_observed_at.isoformat(),facts=self.facts,
            defaults=[dict(key=vars(u.key),acceptance=u.acceptance_ref,source=u.source_ref)
                for u in sorted(self.default_uses,key=lambda u:u.key)])).encode()).hexdigest()


@dataclass(frozen=True)
class ManualDraft:
    seed: object = field(repr=False)
    after: object = field(repr=False)
    bindings: TaskStorageBindings
    provenance: CreationProvenance | None = field(repr=False)
    prepared_estimates: tuple[PreparedUserEstimate,...]
    missing_fields: tuple[str,...]
    proposal_json: str = field(repr=False)

    @property
    def ready(self):return not self.missing_fields
    @property
    def proposal(self):return strict_json(self.proposal_json)


@dataclass(frozen=True)
class ManualCreationOutcome:
    state: str
    task_id: str | None
    creation_event_ref: str | None
    receipt: CommitReceipt | None = field(repr=False)
    pending_id: str | None = None
    missing_fields: tuple[str,...] = ()
    proposal_json: str | None = field(default=None,repr=False)


def manual_command(command):
    require(isinstance(command,Command) and command.origin=='USER_COMMAND' and len(command.changes)==1
        and command.changes[0].action=='CREATE_TASK' and command.batch_ref is None,'MANUAL_ONE_USER_CREATION_REQUIRED')
    fields=command.changes[0].fields
    require(fields.get('completion','INCOMPLETE')=='INCOMPLETE' and fields.get('disposition','ACTIVE')=='ACTIVE'
        and fields.get('expiration_notice_ref') is None,'MANUAL_CREATION_CANNOT_ASSERT_OUTCOME')


def prepare_manual_task(codec,command,intent,definitions):
    """An independently registered intent chooses facts and accepted defaults.

    Missing schema-essential facts stay a proposal. Cache presence is neither
    default acceptance nor creation authority. Contradictory defaults have no
    precedence; an explicit value can resolve the affected field only.
    """
    manual_command(command)
    require(isinstance(intent,ResolvedManualIntent) and intent.command_fingerprint==command.fingerprint,
        'MANUAL_INTENT_SCOPE_MISMATCH')
    facts=intent.facts;fields=command.changes[0].fields;task_id=command.changes[0].task_id
    keys={}
    for name,kind in [('task_type_ref','TASKTYPE'),('template_ref','TASK_TEMPLATE')]:
        ref=facts.get(name)
        if ref is not None:keys[name]=DefinitionKey(kind,**ref)
    require(all(u.key in keys.values() for u in intent.default_uses),'MANUAL_UNRELATED_DEFAULT_SOURCE')
    missing=set();snapshots=[];choices={};sources={};origins={}
    for name,key in keys.items():
        if definitions.get(key) is None:missing.add('/references/'+name)
    for use in sorted(intent.default_uses,key=lambda u:u.key):
        record=definitions.get(use.key)
        if record is None:continue
        snapshot=defaults_from(record)
        snapshots.append(dict(key=vars(use.key),content_hash=snapshot.source_hash,
            acceptance_ref=use.acceptance_ref,source_ref=use.source_ref,values=snapshot.values))
        for name,value in snapshot.values.items():
            choices.setdefault(name,[]).append(value)
            sources.setdefault(name,use.source_ref);origins.setdefault(name,use.key)
    values={};conflicts=set()
    for name,items in choices.items():
        if all(value==items[0] for value in items):values[name]=items[0]
        else:conflicts.add(name)
    for name in ('importance','requiredness','difficulty'):
        if name in fields:values[name]=fields[name];sources[name]=intent.source_ref;conflicts.discard(name)
    for name in ('minimum_session_seconds','fragmentable','total_estimate_seconds'):
        if name in facts:
            values[name]=facts[name];sources[name]=intent.source_ref;origins.pop(name,None);conflicts.discard(name)
    missing.update('/defaults/'+name for name in conflicts)
    for name,value in [('title',fields.get('title')),('domain',facts.get('domain')),
            ('importance',values.get('importance')),('requiredness',values.get('requiredness')),
            ('difficulty',values.get('difficulty'))]:
        if value is None:missing.add('/core/'+name)
    if values.get('requiredness')=='EXPIRING' and not fields.get('expiration_condition_ref'):
        missing.add('/core/expiration/condition_ref')
    context=facts.get('context');profile=None
    if context is not None and context.get('kind') in ('COURSE','ACTIVITY'):
        ref=facts.get('profile_ref')
        if ref is None:missing.add('/references/profile_ref')
        else:
            profile=DefinitionKey(**ref)
            require((profile.kind,profile.id)==('COURSE_PROFILE' if context['kind']=='COURSE' else 'ACTIVITY_PROFILE',context['id']),
                'MANUAL_PROFILE_CONTEXT_MISMATCH')
            if definitions.get(profile) is None:missing.add('/references/profile_ref')
    else:require(facts.get('profile_ref') is None,'MANUAL_PROFILE_CONTEXT_MISMATCH')
    manifest=dict(kind='MANUAL_CREATION',intent_fingerprint=intent.fingerprint,
        command_fingerprint=command.fingerprint,source_ref=intent.source_ref,
        source_observed_at=intent.source_observed_at.isoformat(),resolved_facts=facts,
        approved_default_snapshots=snapshots,field_sources=sources)
    proposal=dict(command=command.as_record(),resolved_creation=manifest,missing_fields=sorted(missing))
    binding=TaskStorageBindings(profile)
    if missing:return ManualDraft(None,None,binding,None,(),tuple(sorted(missing)),canonical(proposal))
    expiration=dict(condition_ref=fields['expiration_condition_ref'],notice_ref=None) if values['requiredness']=='EXPIRING' else None
    require(expiration is not None or fields.get('expiration_condition_ref') is None,'MANUAL_EXPIRATION_REQUIRES_EXPIRING')
    core=dict(schema_version='0.1.0-draft',task_id=task_id,revision=1,title=fields['title'],domain=facts['domain'],
        context=context,task_type_ref=facts.get('task_type_ref'),acceptance=dict(state='ACCEPTED',authority_ref=command.authority_ref),
        completion='INCOMPLETE',disposition='ACTIVE',requiredness=values['requiredness'],importance=values['importance'],
        difficulty=values['difficulty'],expiration=expiration,metadata=dict(trust='UNKNOWN',overdue='UNKNOWN'))
    total=None;seconds=values.get('total_estimate_seconds')
    if seconds is not None:
        key=origins.get('total_estimate_seconds')
        total=dict(seconds=seconds,source_ref=sources['total_estimate_seconds'],observed_at=intent.source_observed_at.isoformat(),
            basis='TEMPLATE_DEFAULT' if key else 'USER_REPORT',definition_ref=vars(key) if key else None)
    value=dict(schema_version='0.1.0-draft',core=core,
        effort=dict(schema_version='0.1.0-draft',task_id=task_id,task_revision=1,completion='INCOMPLETE',disposition='ACTIVE',
            user_remaining=None,prediction=None,stages=[]),timing=dict(created_at=None,release=None,deadline=None,completed_at=None),
        work=dict(total_estimate=total,minimum_session_seconds=values.get('minimum_session_seconds'),fragmentable=values.get('fragmentable')),
        stage_details=[],provenance=[])
    provenance={'/core/title':intent.source_ref,'/core/domain':intent.source_ref}
    for name in ('importance','requiredness','difficulty'):provenance['/core/'+name]=sources[name]
    for name in ('minimum_session_seconds','fragmentable'):
        if name in values:provenance['/work/'+name]=sources[name]
    if total:provenance['/work/total_estimate']=sources['total_estimate_seconds']
    for name in ('context','task_type_ref'):
        if name in facts:provenance['/core/'+name]=intent.source_ref
    if expiration:provenance['/core/expiration']=intent.source_ref
    value['provenance']=[dict(field=p,source_ref=source) for p,source in sorted(provenance.items())]
    seed=admit_storage(codec,canonical(value).encode());observations=()
    if fields.get('user_remaining_seconds') is not None:
        observation_id='observation-'+sha256((command.fingerprint+intent.fingerprint).encode()).hexdigest()
        observation=PreparedUserEstimate(observation_id,task_id,fields['user_remaining_seconds'],
            intent.source_observed_at,intent.source_ref,command.authority_ref)
        value['effort']['user_remaining']=dict(seconds=observation.seconds,observation_id=observation_id,
            observed_at=observation.observed_at.isoformat(),verified_at=observation.observed_at.isoformat())
        value['provenance'].append(dict(field='/effort/user_remaining',source_ref=intent.source_ref));observations=(observation,)
    after=admit_storage(codec,canonical(value).encode())
    proof=CreationProvenance(task_id,seed.content_hash,canonical(manifest))
    return ManualDraft(seed,after,binding,proof,observations,(),canonical(proposal))
