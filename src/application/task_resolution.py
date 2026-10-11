"""Owned reference snapshots and version-bound clarification; no grants or I/O."""
from copy import deepcopy
from dataclasses import dataclass,field
from difflib import SequenceMatcher
from hashlib import sha256
import re
import unicodedata

from src.application.definitions import canonical,identity,strict_json
from src.application.direct_creation import parse_creation_answers
from src.application.manual_tasks import ResolvedManualIntent
from src.application.task_storage import TaskStorageRecord
from src.application.transactions import require
from src.domain.authorization import CallerIdentity,Command,change
from src.domain.task_aggregate import instant


def user(caller,principal=None):
    require(isinstance(caller,CallerIdentity) and caller.authenticated and caller.origin=='USER_COMMAND'
        and (principal is None or principal==caller.principal_id),'RESOLUTION_AUTHENTICATED_OWNER_REQUIRED')


def label_key(value):return unicodedata.normalize('NFC',value).strip().casefold()


def display_label(value):
    rendered=''.join('\\u%04x'%ord(c) if unicodedata.category(c).startswith('C') else c for c in value)
    require(bool(rendered.strip()) and len(rendered)<=500,'RESOLUTION_LABEL_UNDISPLAYABLE');return rendered


@dataclass(frozen=True)
class CourseLabel:
    course_id: str
    name: str
    aliases: tuple[str,...] = ()
    version: str = '1'

    def __post_init__(self):
        require(identity(self.course_id) and identity(self.version) and isinstance(self.aliases,tuple),'RESOLUTION_COURSE_REGISTRY')
        require(all(isinstance(s,str) and bool(s.strip()) and len(s)<=500 for s in (self.name,*self.aliases)),'RESOLUTION_COURSE_REGISTRY')

    def as_record(self):return dict(course_id=self.course_id,name=self.name,aliases=list(self.aliases),version=self.version)


def course_registry_hash(courses):
    require(isinstance(courses,tuple) and all(isinstance(c,CourseLabel) for c in courses)
        and len({c.course_id for c in courses})==len(courses),'RESOLUTION_COURSE_REGISTRY')
    return sha256(canonical([c.as_record() for c in sorted(courses,key=lambda x:x.course_id)]).encode()).hexdigest()


@dataclass(frozen=True)
class ResolutionSnapshot:
    principal_id: str
    store_revision: int
    records: tuple[TaskStorageRecord,...] = field(repr=False)
    courses: tuple[CourseLabel,...] = ()

    def __post_init__(self):
        require(identity(self.principal_id) and type(self.store_revision) is int and self.store_revision>0,'RESOLUTION_SNAPSHOT')
        require(isinstance(self.records,tuple) and len(self.records)<=1000 and all(isinstance(r,TaskStorageRecord) for r in self.records)
            and len({r.task_id for r in self.records})==len(self.records),'RESOLUTION_SNAPSHOT')
        course_registry_hash(self.courses)


@dataclass(frozen=True)
class ResolutionIntent:
    payload_json: str = field(repr=False)

    def __post_init__(self):
        v=self.as_record()
        require(set(v)=={'schema_version','session_id','command_id','principal_id','action','target','creation_task_id','fields','creation_facts'}
            and v['schema_version']=='0.1.0-resolution-intent' and all(identity(v[n]) for n in ('session_id','command_id','principal_id')),'RESOLUTION_INTENT_IDENTITY')
        require(v['action'] in ('CREATE_TASK','COMPLETE_TASK','CANCEL_TASK','UPDATE_TASK'),'RESOLUTION_INTENT_ACTION')
        create=v['action']=='CREATE_TASK'
        require((v['target'] is None and identity(v['creation_task_id'])) if create else
            (v['creation_task_id'] is None and isinstance(v['target'],dict) and set(v['target'])=={'mode','value','course'}),'RESOLUTION_TARGET_SHAPE')
        if not create:
            target=v['target'];require(target['mode'] in ('ID','NAME') and isinstance(target['value'],str) and bool(target['value'].strip()),'RESOLUTION_TARGET_SHAPE')
            c=target['course'];require(c is None or isinstance(c,dict) and set(c)=={'mode','value'} and c['mode'] in ('ID','NAME') and isinstance(c['value'],str) and bool(c['value'].strip()),'RESOLUTION_COURSE_SELECTOR')
        require(isinstance(v['creation_facts'],dict) and set(v['creation_facts'])<= {'domain'}
            and (create or not v['creation_facts']) and v['creation_facts'].get('domain','other') in ('study','exercise','life_administration','other'),'RESOLUTION_CREATION_FACTS')
        try:
            change(v['creation_task_id'] if create else 'unresolved',None if create else 1,'CREATE_TASK' if create else 'UPDATE_TASK',v['fields'])
        except (TypeError,ValueError):require(False,'RESOLUTION_FIELDS_INVALID')
        if create:
            require(set(v['fields'])<= {'title','importance','requiredness','difficulty','user_remaining_seconds'},'RESOLUTION_CREATION_OUTCOME_FORBIDDEN')
            require(v['fields'].get('requiredness','OPTIONAL') in ('REQUIRED','OPTIONAL'),'RESOLUTION_CREATION_EXPIRY_UNSUPPORTED')
        if v['action']=='COMPLETE_TASK':require(v['fields'].get('completion')=='COMPLETE'
            and set(v['fields'])<= {'completion','disposition','user_remaining_seconds'} and v['fields'].get('disposition','ACTIVE')=='ACTIVE'
            and v['fields'].get('user_remaining_seconds',0)==0,'RESOLUTION_COMPLETE_SCOPE')
        if v['action']=='CANCEL_TASK':require(v['fields']==dict(disposition='CANCELLED'),'RESOLUTION_CANCEL_SCOPE')
        object.__setattr__(self,'payload_json',canonical(v))

    def as_record(self):return strict_json(self.payload_json)
    @property
    def fingerprint(self):return sha256(self.payload_json.encode()).hexdigest()


def admit_intent(codec,raw):
    require(isinstance(raw,bytes) and 0<len(raw)<=8192,'RESOLUTION_INPUT_SIZE')
    v=codec.admit('resolution-intent',raw);require(v.status=='SUPPORTED_SHAPE','RESOLUTION_INTENT_SHAPE_UNSUPPORTED')
    return ResolutionIntent(canonical(v.payload))


def admit_reply(codec,raw):
    require(isinstance(raw,bytes) and 0<len(raw)<=8192,'RESOLUTION_INPUT_SIZE')
    v=codec.admit('clarification-reply',raw);require(v.status=='SUPPORTED_SHAPE','RESOLUTION_REPLY_SHAPE_UNSUPPORTED')
    d=v.payload;require(type(d['expected_revision']) is int and d['expected_revision']>0,'RESOLUTION_REPLY_REVISION');return d


def essential(fields,facts):
    return tuple(sorted('/core/'+k for k in ('title','importance','requiredness','difficulty','domain') if k not in fields|facts))


def details_question(missing):
    names={'title':'任务标题','importance':'重要性','requiredness':'是否必须完成','difficulty':'三项难度','domain':'所属领域'}
    return '还需补充：'+'、'.join(names[x.split('/')[-1]] for x in missing)


@dataclass(frozen=True)
class ResolutionFrame:
    raw_bytes: bytes = field(repr=False)
    payload_json: str = field(repr=False)

    def __post_init__(self):
        v=self.as_record();require(strict_json(self.raw_bytes.decode())==v,'RESOLUTION_FRAME_BYTES_DRIFT')
        intent=ResolutionIntent(canonical(v['intent'])).as_record()
        require((v['session_id'],v['command_id'],v['principal_id'])==(intent['session_id'],intent['command_id'],intent['principal_id']),'RESOLUTION_FRAME_IDENTITY')
        require(type(v['revision']) is int and v['revision']>0 and v['previous_revision']==(v['revision']-1 or None),'RESOLUTION_FRAME_REVISION')
        require(v['state'] in ('NEEDS_COURSE','NEEDS_TASK','NEEDS_DETAILS','RESOLVED'),'RESOLUTION_FRAME_STATE')
        require(all(v['fields'].get(k)==value for k,value in intent['fields'].items()) and
            all(v['creation_facts'].get(k)==value for k,value in intent['creation_facts'].items()),'RESOLUTION_ORIGINAL_FACTS_DRIFT')
        require(intent['action']=='CREATE_TASK' or (v['fields']==intent['fields'] and v['creation_facts']=={}),'RESOLUTION_EFFECT_SCOPE_DRIFT')
        choices=v['choices'];require(len({(x['kind'],x['id']) for x in choices})==len(choices),'RESOLUTION_DUPLICATE_CHOICES')
        require(all(identity(v[n]) for n in ('query_source_ref','last_source_ref')) and type(v['store_revision']) is int and v['store_revision']>0,'RESOLUTION_FRAME_SOURCE')
        instant(v['created_at']);instant(v['last_source_observed_at'])
        if intent['action']=='CREATE_TASK':
            require(set(v['fields'])<= {'title','importance','requiredness','difficulty','user_remaining_seconds'}
                and v['fields'].get('requiredness','OPTIONAL') in ('REQUIRED','OPTIONAL'),'RESOLUTION_CREATION_OUTCOME_FORBIDDEN')
            require(v['selected_task_ref'] is None and tuple(v['missing_fields'])==essential(v['fields'],v['creation_facts'])
                and v['state']==('NEEDS_DETAILS' if v['missing_fields'] else 'RESOLVED'),'RESOLUTION_CREATION_STATE')
            try:change(intent['creation_task_id'],None,'CREATE_TASK',v['fields'])
            except (ValueError,TypeError):require(False,'RESOLUTION_FIELDS_INVALID')
        else:require(not v['missing_fields'] and (v['state']=='RESOLVED')==(v['selected_task_ref'] is not None),'RESOLUTION_SELECTED_STATE')
        if v['state'] in ('NEEDS_COURSE','NEEDS_TASK'):
            expected='COURSE' if v['state']=='NEEDS_COURSE' else 'TASK'
            require(all(x['kind']==expected for x in choices),'RESOLUTION_CHOICE_KIND')

    def as_record(self):return strict_json(self.payload_json)
    @property
    def fingerprint(self):return sha256(self.raw_bytes).hexdigest()
    @property
    def session_id(self):return self.as_record()['session_id']
    @property
    def revision(self):return self.as_record()['revision']


def admit_frame(codec,raw):
    require(isinstance(raw,bytes) and 0<len(raw)<=1048576,'RESOLUTION_FRAME_SIZE')
    v=codec.admit('resolution-session',raw);require(v.status=='SUPPORTED_SHAPE','RESOLUTION_FRAME_SHAPE_UNSUPPORTED')
    return ResolutionFrame(raw,canonical(v.payload))


def _task_choice(record):
    core=record.aggregate.as_record()['core'];context=core['context']
    return dict(kind='TASK',id=record.task_id,revision=record.revision,label=display_label(core['title']),
        course_id=context['id'] if context and context['kind']=='COURSE' else None,completion=core['completion'],disposition=core['disposition'])


def _matches(snapshot,target,course_id):
    records=[r for r in snapshot.records if course_id is None or _task_choice(r)['course_id']==course_id]
    if target['mode']=='ID':return [r for r in records if r.task_id==target['value']],[]
    key=label_key(target['value']);exact=[r for r in records if label_key(r.aggregate.as_record()['core']['title'])==key]
    similar=[r for r in records if key in label_key(r.aggregate.as_record()['core']['title'])
        or SequenceMatcher(None,key,label_key(r.aggregate.as_record()['core']['title'])).ratio()>=0.6]
    return exact,similar


def _resolve_target(v,snapshot):
    target=v['intent']['target'];course=target['course']
    if course is not None and v['course_id'] is None:
        if course['mode']=='ID':
            known={c.course_id for c in snapshot.courses}|{_task_choice(r)['course_id'] for r in snapshot.records}
            require(course['value'] in known,'RESOLUTION_COURSE_NOT_AVAILABLE');v['course_id']=course['value']
        else:
            matches=[c for c in snapshot.courses if label_key(course['value']) in {label_key(s) for s in (c.name,*c.aliases)}]
            if len(matches)!=1:
                v.update(state='NEEDS_COURSE',selected_task_ref=None,choices=[dict(kind='COURSE',id=c.course_id,revision=None,
                    label=display_label(c.name),course_id=c.course_id,completion=None,disposition=None) for c in sorted(matches,key=lambda c:c.course_id)],
                    question='你指的是哪门课？请选择列出的课程；没有匹配时请提供准确名称。');return
            v['course_id']=matches[0].course_id
    exact,similar=_matches(snapshot,target,v['course_id'])
    if len(exact)==1:
        selected=exact[0];v.update(state='RESOLVED',choices=[],selected_task_ref=dict(task_id=selected.task_id,revision=selected.revision),question='');return
    options=exact or similar
    v.update(state='NEEDS_TASK',selected_task_ref=None,choices=[_task_choice(r) for r in sorted(options,key=lambda r:r.task_id)],
        question='有多个同名任务，你指的是哪一项？' if exact else '没有完全匹配的任务。你指的是下面哪一项？没有合适项时请提供准确名称或任务 ID。')


def _make(codec,v):return admit_frame(codec,canonical(v).encode())


def begin_resolution(codec,intent,snapshot,*,source_ref,source_observed_at,at,caller):
    user(caller,snapshot.principal_id);i=intent.as_record();user(caller,i['principal_id'])
    require(source_observed_at<=at,'RESOLUTION_FUTURE_SOURCE')
    v=dict(schema_version='0.1.0-resolution-session',session_id=i['session_id'],revision=1,previous_revision=None,command_id=i['command_id'],principal_id=i['principal_id'],
        intent=i,query_source_ref=source_ref,last_source_ref=source_ref,last_source_observed_at=source_observed_at.isoformat(),created_at=at.isoformat(),state='RESOLVED',
        store_revision=snapshot.store_revision,course_id=None,course_registry_hash=course_registry_hash(snapshot.courses),choices=[],selected_task_ref=None,
        fields=deepcopy(i['fields']),creation_facts=deepcopy(i['creation_facts']),missing_fields=[],question='')
    if i['action']=='CREATE_TASK':
        require(i['creation_task_id'] not in {r.task_id for r in snapshot.records},'RESOLUTION_CREATE_TARGET_ALREADY_EXISTS')
        v['missing_fields']=list(essential(v['fields'],v['creation_facts']))
        if v['missing_fields']:v.update(state='NEEDS_DETAILS',question=details_question(v['missing_fields']))
    else:_resolve_target(v,snapshot)
    return _make(codec,v)


def _selection(value,choices):
    if value is None:return None
    value=value.strip();direct=[x for x in choices if x['id']==value]
    if len(direct)==1:return direct[0]
    if value in ('是','好的','确认','就是这个') and len(choices)==1:return choices[0]
    match=re.fullmatch(r'(?:第)?([1-9][0-9]{0,3}|[一二三四五六七八九十])(?:个|项)?',value)
    if not match:return None
    number=int(match[1]) if match[1].isascii() else '一二三四五六七八九十'.index(match[1])+1
    return choices[number-1] if 1<=number<=len(choices) else None


def current_scope(frame,snapshot):
    v=frame.as_record();require(snapshot.principal_id==v['principal_id'],'RESOLUTION_AUTHENTICATED_OWNER_REQUIRED')
    require(v['course_registry_hash']==course_registry_hash(snapshot.courses),'RESOLUTION_COURSE_REGISTRY_CHANGED')
    by_id={r.task_id:r for r in snapshot.records}
    for choice in v['choices']:
        if choice['kind']=='TASK':require(choice['id'] in by_id and _task_choice(by_id[choice['id']])==choice,'RESOLUTION_TASK_SNAPSHOT_CHANGED')
    if v['selected_task_ref'] is not None:
        target=v['selected_task_ref'];require(target['task_id'] in by_id and by_id[target['task_id']].revision==target['revision'],'RESOLUTION_TASK_SNAPSHOT_CHANGED')
        require(v['course_id'] is None or _task_choice(by_id[target['task_id']])['course_id']==v['course_id'],'RESOLUTION_TASK_SNAPSHOT_CHANGED')
    if v['intent']['action']=='CREATE_TASK':require(v['intent']['creation_task_id'] not in by_id,'RESOLUTION_CREATE_TARGET_ALREADY_EXISTS')


def resume_resolution(codec,frame,reply,snapshot,*,source_ref,source_observed_at,at,caller):
    v=frame.as_record();user(caller,v['principal_id']);current_scope(frame,snapshot)
    require((reply['session_id'],reply['expected_revision'],reply['scope_hash'])==(frame.session_id,frame.revision,frame.fingerprint),'RESOLUTION_REPLY_SCOPE_CONFLICT')
    require(v['state']!='RESOLVED','RESOLUTION_ALREADY_RESOLVED')
    require(instant(v['created_at'])<=source_observed_at<=at,'RESOLUTION_REPLY_TIME_REQUIRED')
    v.update(revision=frame.revision+1,previous_revision=frame.revision,last_source_ref=source_ref,last_source_observed_at=source_observed_at.isoformat(),created_at=at.isoformat(),
        store_revision=snapshot.store_revision)
    if v['state']=='NEEDS_DETAILS':
        require(reply['selection'] is None and set(reply['answers'])<= {x.split('/')[-1] for x in v['missing_fields']},'RESOLUTION_ANSWER_FIELD_SCOPE')
        fields,facts,_,issues=parse_creation_answers(reply['answers'])
        issues=tuple(x for x in issues if not (x.field=='title' and 'title' not in reply['answers']))
        if 'remaining_seconds' in fields:fields['user_remaining_seconds']=fields.pop('remaining_seconds')
        v['fields'].update(fields);v['creation_facts'].update(facts)
        v['missing_fields']=list(essential(v['fields'],v['creation_facts']))
        v.update(state='NEEDS_DETAILS' if v['missing_fields'] else 'RESOLVED',question='；'.join(x.question for x in issues)
            if issues else (details_question(v['missing_fields']) if v['missing_fields'] else ''))
    else:
        require(not reply['answers'],'RESOLUTION_ANSWER_FIELD_SCOPE')
        choice=_selection(reply['selection'],v['choices'])
        if choice is None:v['question']='请明确选择本次列出的哪一项；多个候选时仅说“确认”不能确定对象。'
        elif v['state']=='NEEDS_COURSE':v['course_id']=choice['id'];_resolve_target(v,snapshot)
        else:v.update(state='RESOLVED',choices=[],selected_task_ref=dict(task_id=choice['id'],revision=choice['revision']),question='')
    return _make(codec,v)


def refresh_resolution(codec,frame,snapshot,*,at,caller):
    v=frame.as_record();user(caller,v['principal_id'])
    require(v['state']!='RESOLVED','RESOLUTION_ALREADY_RESOLVED')
    v.update(revision=frame.revision+1,previous_revision=frame.revision,created_at=at.isoformat(),store_revision=snapshot.store_revision,
        course_registry_hash=course_registry_hash(snapshot.courses),selected_task_ref=None)
    if v['intent']['action']!='CREATE_TASK':v['course_id']=None;_resolve_target(v,snapshot)
    return _make(codec,v)


@dataclass(frozen=True)
class ResolutionHandoff:
    command: Command = field(repr=False)
    session_id: str
    session_revision: int
    scope_hash: str
    expected_store_revision: int
    source_refs: tuple[str,...]
    manual_intent: ResolvedManualIntent | None = field(default=None,repr=False)


def resolution_handoff(frame,*,authority_ref,caller):
    v=frame.as_record();user(caller,v['principal_id']);require(v['state']=='RESOLVED','RESOLUTION_CLARIFICATION_REQUIRED')
    require(identity(authority_ref),'RESOLUTION_AUTHORITY_ID_REQUIRED')
    create=v['intent']['action']=='CREATE_TASK';target=v['selected_task_ref'];target_id=v['intent']['creation_task_id'] if create else target['task_id']
    command=Command(v['command_id'],v['principal_id'],'USER_COMMAND',authority_ref,(change(target_id,None if create else target['revision'],
        'CREATE_TASK' if create else 'UPDATE_TASK',v['fields']),))
    manual=ResolvedManualIntent(command.fingerprint,v['last_source_ref'],instant(v['last_source_observed_at']),canonical(v['creation_facts'])) if create else None
    return ResolutionHandoff(command,v['session_id'],v['revision'],frame.fingerprint,v['store_revision'],tuple(dict.fromkeys((v['query_source_ref'],v['last_source_ref']))),manual)
