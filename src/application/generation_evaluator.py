"""Exact canonical-source mapping drafts; no authority, writes or rule selection."""
from dataclasses import dataclass,field
from datetime import datetime
from hashlib import sha256
import re

from src.application.creation_outbox import CreationEvent
from src.application.definitions import (CachedDefinition,DefinitionKey,canonical,
    defaults_from,identity,strict_json)
from src.application.relationship_storage import RuleStorageRecord
from src.application.task_storage import TaskStorageRecord,TaskStorageBindings,admit_storage,validate_bindings
from src.application.command_validation import PreparedUserEstimate
from src.domain.authorization import RuleScope,change
from src.domain.task_aggregate import instant


class GenerationError(RuntimeError):pass


def require(value,code):
    if not value:raise GenerationError(code)


def _definition_pin(cached):
    return dict(key=vars(cached.key),content_hash=cached.artifact.request.content_hash,
        git_commit=cached.artifact.request.commit,git_blob=cached.artifact.blob_oid)


@dataclass(frozen=True)
class GenerationSource:
    event: CreationEvent
    task: TaskStorageRecord = field(repr=False)
    source_record_ref: str
    creation_authorization_json: str | None = field(default=None,repr=False)

    def __post_init__(self):
        require(isinstance(self.event,CreationEvent) and isinstance(self.task,TaskStorageRecord)
            and identity(self.source_record_ref),'GENERATION_CANONICAL_SOURCE_REQUIRED')
        require((self.event.task_id,self.event.task_revision,self.event.content_hash)==
            (self.task.task_id,self.task.revision,self.task.content_hash),'GENERATION_SOURCE_SNAPSHOT_MISMATCH')
        acceptance=self.task.aggregate.as_record()['core']['acceptance']
        require(acceptance['state']=='ACCEPTED' and identity(acceptance['authority_ref']),
            'GENERATION_SOURCE_ACCEPTANCE_MISMATCH')
        if acceptance['authority_ref']!=self.event.authority_ref:
            require(isinstance(self.creation_authorization_json,str) and len(self.creation_authorization_json.encode())<=8388608,
                'GENERATION_SOURCE_ACCEPTANCE_MISMATCH')
            annotation=strict_json(self.creation_authorization_json);root=acceptance['authority_ref']
            command=annotation.get('command',{}) if isinstance(annotation,dict) else {}
            generated=annotation.get('generation',{}) if isinstance(annotation,dict) else {}
            command=command if isinstance(command,dict) else {}
            generated=generated if isinstance(generated,dict) else {}
            manual=(annotation.get('grant_ref')==root and command.get('principal_id')==self.event.principal_id
                and isinstance(command.get('changes'),list)
                and any(c.get('task_id')==self.event.task_id and c.get('action')=='CREATE_TASK' and c.get('expected_revision') is None
                    for c in command.get('changes',[]) if isinstance(c,dict))) if isinstance(annotation,dict) else False
            rule_created=(isinstance(generated,dict) and generated.get('state')=='CREATED'
                and generated.get('target_task_ref')==self.event.task_id
                and isinstance(generated.get('manifest'),dict)
                and generated.get('manifest',{}).get('authority_ref')==root
                and generated.get('manifest',{}).get('principal_id')==self.event.principal_id)
            require(manual or rule_created,'GENERATION_SOURCE_ACCEPTANCE_MISMATCH')


@dataclass(frozen=True)
class AcceptedGenerationRule:
    record: RuleStorageRecord
    principal_id: str
    source_record_ref: str
    accepted_at: datetime

    def __post_init__(self):
        require(isinstance(self.record,RuleStorageRecord) and identity(self.principal_id)
            and identity(self.source_record_ref) and isinstance(self.accepted_at,datetime)
            and self.accepted_at.utcoffset() is not None,'GENERATION_ACCEPTED_RULE_BINDING')


@dataclass(frozen=True)
class GenerationDraft:
    state: str
    code: str
    scope: RuleScope
    obligation_kind: str
    target_id: str
    target: TaskStorageRecord | None = field(default=None,repr=False)
    parent_after: TaskStorageRecord | None = field(default=None,repr=False)
    bindings: TaskStorageBindings = TaskStorageBindings()
    observations: tuple[PreparedUserEstimate,...] = ()
    missing_fields: tuple[str,...] = ()
    manifest_json: str = field(default='{}',repr=False)

    @property
    def ready(self):return self.state=='PROPOSED'
    @property
    def manifest(self):return strict_json(self.manifest_json)


def _read_source(source,name):
    value=source.task.aggregate.as_record();core=value['core']
    aliases={k:'/core/'+k for k in core}
    aliases.update(user_remaining_seconds='/effort/user_remaining/seconds',
                   expiration_condition_ref='/core/expiration/condition_ref',
                   expiration_notice_ref='/core/expiration/notice_ref')
    pointer=aliases.get(name,name)
    if not isinstance(pointer,str) or not pointer.startswith('/') or len(pointer)>4096 or pointer.count('/')>64:
        return None,None,None
    current=value
    try:
        for part in pointer[1:].split('/'):
            if re.search(r'~(?![01])',part):return None,None,None
            key=part.replace('~1','/').replace('~0','~')
            if isinstance(current,list):
                if not re.fullmatch(r'0|[1-9][0-9]*',key):return None,None,None
                current=current[int(key)]
            else:current=current[key]
    except (KeyError,TypeError,ValueError,IndexError):return None,None,None
    candidates=[p for p in value['provenance'] if pointer==p['field'] or pointer.startswith(p['field']+'/')]
    provenance=max(candidates,key=lambda p:len(p['field']))['source_ref'] if candidates else source.source_record_ref
    observed=source.event.occurred_at
    if pointer.startswith('/effort/user_remaining/') and value['effort']['user_remaining']:
        observed=instant(value['effort']['user_remaining']['observed_at'])
    return current,provenance,observed


def evaluate_generation(codec,source,use,definitions,*,target_id,parent=None,parent_bindings=None):
    """Consume trusted repository values; return portable proposals only.

    Definitions are exact cached snapshots. The caller selects the accepted rule
    and its independently registered principal/source; this is not a public API.
    All resulting references still require independent commit-time authority.
    """
    require(isinstance(source,GenerationSource) and isinstance(use,AcceptedGenerationRule),
            'GENERATION_CANONICAL_SOURCE_REQUIRED')
    record=use.record;rule=record.rule;event=source.event
    require(identity(target_id) and (rule.obligation_kind=='STAGE' or target_id!=source.task.task_id),'GENERATION_TARGET_IDENTITY')
    scope=RuleScope(rule.rule_id,rule.version,event.task_id,event.event_id,event.event_id,rule.target_role)
    manifest=dict(kind='RULE_GENERATION',rule=vars(record.key),rule_hash=record.content_hash,
        authority_ref=rule.acceptance_ref,principal_id=use.principal_id,rule_source_ref=use.source_record_ref,
        rule_accepted_at=use.accepted_at.isoformat(),source_event=vars(event)|{'occurred_at':event.occurred_at.isoformat()},
        source_record_ref=source.source_record_ref,generation_key=scope.generation_key,
        obligation_kind=rule.obligation_kind,target_id=target_id,defaults=[],field_sources={})
    def result(state,code,missing=(),**kw):
        return GenerationDraft(state,code,scope,rule.obligation_kind,target_id,
            missing_fields=tuple(sorted(set(missing))),manifest_json=canonical(manifest),**kw)
    if not rule.active:return result('NOT_ELIGIBLE','GENERATION_RULE_INACTIVE')
    require(event.principal_id==use.principal_id,'GENERATION_PRINCIPAL_MISMATCH')
    source_core=source.task.aggregate.as_record()['core']
    if source_core['task_type_ref']!={'id':record.source_type.id,'version':record.source_type.version}:
        return result('NOT_ELIGIBLE','GENERATION_SOURCE_TYPE_MISMATCH')
    resolved={};missing=[]
    for key in (record.key,record.source_type,record.target_type,record.template):
        cached=definitions.get(key)
        if cached is None:missing.append('/references/'+key.kind+'/'+key.id+'/'+key.version)
        else:
            require(isinstance(cached,CachedDefinition) and cached.key==key,'GENERATION_DEFINITION_BINDING')
            resolved[key]=cached
    if missing:return result('PENDING','GENERATION_DEFINITION_MISSING',missing)
    require(resolved[record.key].body==record.payload,'GENERATION_RULE_PAYLOAD_MISMATCH')
    manifest['definition_snapshots']=[_definition_pin(cached) for cached in resolved.values()]
    template=resolved[record.template].body
    require(set(template)<= {'references','defaults','creation_facts','source_facts','relation'},'GENERATION_TEMPLATE_FIELDS')
    facts=template.get('creation_facts',{})
    copied=template.get('source_facts',{})
    fact_names={'domain','context','profile_ref','stage_weight'}
    require(isinstance(facts,dict) and isinstance(copied,dict) and set(facts)<=fact_names
        and set(copied)<=fact_names and not set(facts)&set(copied),'GENERATION_TEMPLATE_FACTS')
    facts=dict(facts);fact_sources={k:use.source_record_ref for k in facts}
    for name,pointer in copied.items():
        require(isinstance(pointer,str) and pointer.startswith('/'),'GENERATION_SOURCE_POINTER')
        v,ref,_=_read_source(source,pointer)
        if ref is None:missing.append('/facts/'+name)
        else:facts[name]=v;fact_sources[name]=ref
    choices={};origins={};conflicts=set()
    for key in (record.target_type,record.template):
        cached=resolved[key]
        if 'defaults' not in cached.body:continue
        snapshot=defaults_from(cached)
        manifest['defaults'].append(dict(key=vars(key),content_hash=snapshot.source_hash,values=snapshot.values))
        for name,v in snapshot.values.items():
            if name in choices and choices[name]!=v:conflicts.add(name)
            else:choices[name]=v;origins[name]=key
    values={k:choices[k] for k in ('importance','requiredness','difficulty') if k in choices and k not in conflicts}
    field_sources={k:use.source_record_ref for k in values};times={}
    for binding in rule.mappings:
        if binding.kind=='LITERAL':v=strict_json(binding.literal_json);ref=use.source_record_ref;at=use.accepted_at
        elif binding.kind=='SOURCE':v,ref,at=_read_source(source,binding.source_field)
        else:
            if binding.source_field in conflicts:missing.append('/defaults/'+binding.source_field);continue
            v=choices.get(binding.source_field);ref=use.source_record_ref;at=use.accepted_at
        if v is not None:
            values[binding.target_field]=v;field_sources[binding.target_field]=ref;times[binding.target_field]=at
    missing.extend('/mapping/'+name for name in rule.essential_fields if values.get(name) is None)
    if values.get('completion') not in (None,'INCOMPLETE') or values.get('disposition') not in (None,'ACTIVE') or values.get('expiration_notice_ref') is not None:
        return result('PENDING','GENERATION_CANNOT_INFER_OUTCOME',('/mapping/outcome',))
    try:change(target_id,None,'CREATE_TASK',values)
    except (TypeError,ValueError):return result('PENDING','GENERATION_INVALID_MAPPING',('/mapping',))
    for name in conflicts:
        if name not in values:missing.append('/defaults/'+name)
    manifest['field_sources']=dict(field_sources)
    manifest['mapped_fields']=values
    manifest['facts']=facts;manifest['fact_sources']=fact_sources
    if rule.obligation_kind=='STAGE':
        unsupported=set(values)-{'title','completion','disposition','user_remaining_seconds'}
        # TaskType ratings are parent-level defaults, not independent stage facts.
        unsupported-=set(choices)-{b.target_field for b in rule.mappings}
        if unsupported:return result('PENDING','GENERATION_STAGE_TASK_FIELDS',('/mapping/'+k for k in unsupported))
        if parent is None:return result('PENDING','GENERATION_CURRENT_PARENT_REQUIRED',('/references/current_parent',))
        require(isinstance(parent,TaskStorageRecord) and parent.task_id==event.task_id
            and parent.revision>=event.task_revision,'GENERATION_PARENT_SCOPE')
        value=parent.aggregate.as_record()
        if value['core']['completion']!='INCOMPLETE' or value['core']['disposition']!='ACTIVE':
            return result('CONFLICT','GENERATION_PARENT_CLOSED')
        if any(x['stage_id']==target_id for x in value['stage_details']):return result('CONFLICT','GENERATION_STAGE_ALREADY_PRESENT')
        parent_context=value['core']['context']
        if parent_bindings is None:
            if parent_context is not None and parent_context.get('kind') in ('COURSE','ACTIVITY'):
                return result('PENDING','GENERATION_CURRENT_PARENT_BINDINGS_REQUIRED',('/references/parent_profile',))
            parent_bindings=TaskStorageBindings()
        validate_bindings(parent,parent_bindings)
        if parent_bindings.profile_key is not None:
            profile_snapshot=definitions.get(parent_bindings.profile_key)
            if profile_snapshot is None:missing.append('/references/parent_profile')
            else:
                require(isinstance(profile_snapshot,CachedDefinition) and profile_snapshot.key==parent_bindings.profile_key,'GENERATION_DEFINITION_BINDING')
                manifest['definition_snapshots'].append(_definition_pin(profile_snapshot))
        if facts.get('profile_ref') is not None and facts['profile_ref']!=(vars(parent_bindings.profile_key) if parent_bindings.profile_key else None):
            missing.append('/facts/profile_ref')
        for name in ('domain','context'):
            if name in facts and facts[name]!=value['core'][name]:missing.append('/facts/'+name)
        if missing:return result('PENDING','GENERATION_ESSENTIAL_FACTS_MISSING',missing)
        value['core']['revision']+=1;value['effort']['task_revision']+=1
        estimate=None;observations=()
        if values.get('user_remaining_seconds') is not None:
            observation=PreparedUserEstimate('stage-observation-'+sha256(scope.generation_key.encode()).hexdigest(),parent.task_id,
                values['user_remaining_seconds'],times['user_remaining_seconds'],field_sources['user_remaining_seconds'],rule.acceptance_ref)
            estimate=dict(seconds=observation.seconds,observation_id=observation.observation_id,
                observed_at=observation.observed_at.isoformat(),verified_at=observation.observed_at.isoformat())
            observations=(observation,)
        value['effort']['stages'].append(dict(stage_id=target_id,completion='INCOMPLETE',weight=facts.get('stage_weight'),user_remaining=estimate))
        value['stage_details'].append(dict(stage_id=target_id,revision=1,title=values['title']))
        index=len(value['stage_details'])-1
        value['provenance'].append(dict(field='/stage_details/'+str(index)+'/title',source_ref=field_sources['title']))
        value['provenance'].append(dict(field='/effort/stages/'+str(index),source_ref=use.source_record_ref))
        if estimate:value['provenance'].append(dict(field='/effort/stages/'+str(index)+'/user_remaining',source_ref=field_sources['user_remaining_seconds']))
        if 'stage_weight' in facts:value['provenance'].append(dict(field='/effort/stages/'+str(index)+'/weight',source_ref=fact_sources['stage_weight']))
        try:after=admit_storage(codec,canonical(value).encode())
        except (ValueError,RuntimeError):return result('PENDING','GENERATION_INVALID_TARGET',('/target/stage',))
        manifest['parent_revision']=parent.revision;manifest['parent_hash']=parent.content_hash
        return result('PROPOSED','GENERATION_VALIDATED_NOT_AUTHORIZED',parent_after=after,observations=observations,bindings=parent_bindings)
    for name in ('title','importance','requiredness','difficulty'):
        if values.get(name) is None:missing.append('/core/'+name)
    if facts.get('domain') is None:missing.append('/core/domain')
    if 'stage_weight' in facts:return result('PENDING','GENERATION_SEPARATE_STAGE_WEIGHT',('/facts/stage_weight',))
    profile=None;context=facts.get('context')
    if context is not None and isinstance(context,dict) and context.get('kind') in ('COURSE','ACTIVITY'):
        ref=facts.get('profile_ref')
        if ref is None:missing.append('/references/profile_ref')
        else:
            try:profile=DefinitionKey(**ref)
            except (TypeError,ValueError,RuntimeError):return result('PENDING','GENERATION_INVALID_PROFILE',('/references/profile_ref',))
            if (profile.kind,profile.id)!=('COURSE_PROFILE' if context['kind']=='COURSE' else 'ACTIVITY_PROFILE',context['id']):
                return result('PENDING','GENERATION_INVALID_PROFILE',('/references/profile_ref',))
            profile_snapshot=definitions.get(profile)
            if profile_snapshot is None:missing.append('/references/profile_ref')
            else:
                require(isinstance(profile_snapshot,CachedDefinition) and profile_snapshot.key==profile,'GENERATION_DEFINITION_BINDING')
                manifest['definition_snapshots'].append(_definition_pin(profile_snapshot))
    elif facts.get('profile_ref') is not None:return result('PENDING','GENERATION_INVALID_PROFILE',('/references/profile_ref',))
    if values.get('requiredness')=='EXPIRING' and not values.get('expiration_condition_ref'):missing.append('/core/expiration/condition_ref')
    if values.get('requiredness')!='EXPIRING' and values.get('expiration_condition_ref') is not None:
        return result('PENDING','GENERATION_INVALID_EXPIRATION',('/core/expiration',))
    if missing:return result('PENDING','GENERATION_ESSENTIAL_FACTS_MISSING',missing)
    core=dict(schema_version='0.1.0-draft',task_id=target_id,revision=1,title=values['title'],domain=facts['domain'],context=context,
        task_type_ref=dict(id=record.target_type.id,version=record.target_type.version),acceptance=dict(state='ACCEPTED',authority_ref=rule.acceptance_ref),
        completion='INCOMPLETE',disposition='ACTIVE',requiredness=values['requiredness'],importance=values['importance'],difficulty=values['difficulty'],
        expiration=dict(condition_ref=values['expiration_condition_ref'],notice_ref=None) if values['requiredness']=='EXPIRING' else None,
        metadata=dict(trust='UNKNOWN',overdue='UNKNOWN'))
    total=None
    if choices.get('total_estimate_seconds') is not None:
        total=dict(seconds=choices['total_estimate_seconds'],source_ref=use.source_record_ref,observed_at=use.accepted_at.isoformat(),
            basis='TEMPLATE_DEFAULT',definition_ref=vars(origins['total_estimate_seconds']))
    value=dict(schema_version='0.1.0-draft',core=core,effort=dict(schema_version='0.1.0-draft',task_id=target_id,task_revision=1,
        completion='INCOMPLETE',disposition='ACTIVE',user_remaining=None,prediction=None,stages=[]),
        timing=dict(created_at=None,release=None,deadline=None,completed_at=None),
        work=dict(total_estimate=total,minimum_session_seconds=choices.get('minimum_session_seconds'),fragmentable=choices.get('fragmentable')),
        stage_details=[],provenance=[])
    paths={'/core/'+k:ref for k,ref in field_sources.items() if k in ('title','importance','requiredness','difficulty','completion','disposition')}
    paths['/core/domain']=fact_sources['domain'];paths['/core/task_type_ref']=use.source_record_ref
    if context is not None:paths['/core/context']=fact_sources['context']
    if core['expiration']:paths['/core/expiration']=field_sources['expiration_condition_ref']
    for name in ('total_estimate','minimum_session_seconds','fragmentable'):
        if value['work'][name] is not None:paths['/work/'+name]=use.source_record_ref
    observations=()
    if values.get('user_remaining_seconds') is not None:
        observation=PreparedUserEstimate('observation-'+sha256(scope.generation_key.encode()).hexdigest(),target_id,values['user_remaining_seconds'],
            times['user_remaining_seconds'],field_sources['user_remaining_seconds'],rule.acceptance_ref)
        value['effort']['user_remaining']=dict(seconds=observation.seconds,observation_id=observation.observation_id,
            observed_at=observation.observed_at.isoformat(),verified_at=observation.observed_at.isoformat())
        observations=(observation,);paths['/effort/user_remaining']=observation.source_ref
    value['provenance']=[dict(field=k,source_ref=v) for k,v in sorted(paths.items())]
    try:target=admit_storage(codec,canonical(value).encode())
    except (ValueError,RuntimeError):return result('PENDING','GENERATION_INVALID_TARGET',('/target',))
    return result('PROPOSED','GENERATION_VALIDATED_NOT_AUTHORIZED',target=target,
        bindings=TaskStorageBindings(profile),observations=observations)
