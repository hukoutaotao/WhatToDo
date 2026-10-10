"""Immutable declarative cache values; registration is not Task authority."""
from dataclasses import dataclass,field
from datetime import datetime
from hashlib import sha1,sha256
import json
from pathlib import PurePosixPath
import re
from typing import Protocol

KINDS=frozenset(('COURSE_PROFILE','ACTIVITY_PROFILE','TASKTYPE','TASK_TEMPLATE','RELATIONSHIP_RULE','PREFERENCE'))
OID=re.compile(r'(?:[a-f0-9]{40}|[a-f0-9]{64})\Z')
HASH=re.compile(r'[a-f0-9]{64}\Z')


class DefinitionError(RuntimeError):pass


def need(condition,code):
    if not condition:raise DefinitionError(code)


def identity(value):return isinstance(value,str) and bool(value.strip()) and '\x00' not in value and len(value)<=200


def canonical(value):
    try:return json.dumps(value,sort_keys=True,ensure_ascii=False,separators=(',',':'),allow_nan=False)
    except (TypeError,ValueError,UnicodeError,RecursionError):raise DefinitionError('DEFINITION_JSON') from None


def strict_json(raw):
    def pairs(items):
        result={}
        for key,value in items:
            need(key not in result,'DEFINITION_DUPLICATE_JSON_KEY');result[key]=value
        return result
    def nonfinite(_):raise DefinitionError('DEFINITION_NONFINITE_JSON')
    try:return json.loads(raw.decode('utf-8') if isinstance(raw,bytes) else raw,object_pairs_hook=pairs,parse_constant=nonfinite)
    except DefinitionError:raise
    except (TypeError,ValueError,UnicodeError,RecursionError):raise DefinitionError('DEFINITION_JSON') from None


@dataclass(frozen=True,order=True)
class DefinitionKey:
    kind:str
    id:str
    version:str

    def __post_init__(self):
        need(isinstance(self.kind,str) and self.kind in KINDS and identity(self.id) and identity(self.version),'DEFINITION_KEY')

    @property
    def configuration_ref(self):return 'definition-'+sha256(canonical([self.kind,self.id,self.version]).encode()).hexdigest()


@dataclass(frozen=True)
class GitDefinitionRequest:
    commit:str
    path:str
    content_hash:str

    def __post_init__(self):
        need(isinstance(self.commit,str) and OID.fullmatch(self.commit) is not None,'DEFINITION_GIT_COMMIT')
        need(isinstance(self.content_hash,str) and HASH.fullmatch(self.content_hash) is not None,'DEFINITION_HASH')
        need(isinstance(self.path,str) and self.path and '\\' not in self.path and '\x00' not in self.path and len(self.path)<=4096,'DEFINITION_GIT_PATH')
        path=PurePosixPath(self.path)
        need(not path.is_absolute() and all(part not in ('','..','.') for part in self.path.split('/')),'DEFINITION_GIT_PATH')


def validate_defaults(values):
    need(isinstance(values,dict),'DEFINITION_DEFAULTS')
    fields={'importance','requiredness','difficulty','minimum_session_seconds','fragmentable','total_estimate_seconds','workload_unit'}
    need(set(values)<=fields,'DEFINITION_DEFAULT_FIELDS')
    if 'importance' in values:need(type(values['importance']) is int and 1<=values['importance']<=5,'DEFINITION_DEFAULT_RATING')
    if 'requiredness' in values:need(values['requiredness'] in ('REQUIRED','OPTIONAL','EXPIRING'),'DEFINITION_DEFAULT_REQUIREDNESS')
    if 'difficulty' in values:
        ratings=values['difficulty'];need(isinstance(ratings,dict) and set(ratings)=={'thinking_depth','repetitive_volume','new_learning_load'} and all(type(n) is int and 1<=n<=5 for n in ratings.values()),'DEFINITION_DEFAULT_RATING')
    for field,minimum in [('total_estimate_seconds',0),('minimum_session_seconds',1)]:
        if field in values:need(values[field] is None or type(values[field]) is int and values[field]>=minimum,'DEFINITION_DEFAULT_DURATION')
    if 'fragmentable' in values:need(values['fragmentable'] is None or type(values['fragmentable']) is bool,'DEFINITION_DEFAULT_SESSION')
    if 'workload_unit' in values:need(identity(values['workload_unit']),'DEFINITION_DEFAULT_WORKLOAD_UNIT')


@dataclass(frozen=True)
class DefinitionArtifact:
    request:GitDefinitionRequest
    blob_oid:str
    raw_bytes:bytes=field(repr=False)

    def __post_init__(self):
        need(isinstance(self.request,GitDefinitionRequest) and isinstance(self.blob_oid,str) and OID.fullmatch(self.blob_oid) is not None,'DEFINITION_GIT_BLOB')
        need(type(self.raw_bytes) is bytes and len(self.raw_bytes)<=1048576,'DEFINITION_SIZE')
        git_payload=b'blob '+str(len(self.raw_bytes)).encode()+b'\0'+self.raw_bytes
        expected=(sha1 if len(self.blob_oid)==40 else sha256)(git_payload).hexdigest()
        need(expected==self.blob_oid,'DEFINITION_GIT_BLOB')
        record=strict_json(self.raw_bytes)
        need(isinstance(record,dict) and set(record)=={'kind','id','version','body'} and isinstance(record['body'],dict),'DEFINITION_ENVELOPE')
        DefinitionKey(record['kind'],record['id'],record['version'])
        try:digest=sha256(canonical(record).encode('utf-8')).hexdigest()
        except UnicodeError:raise DefinitionError('DEFINITION_JSON') from None
        need(digest==self.request.content_hash,'DEFINITION_HASH')
        references=record['body'].get('references',[])
        need(isinstance(references,list) and len(references)<=1000,'DEFINITION_REFERENCES')
        keys=[]
        for ref in references:
            need(isinstance(ref,dict) and set(ref)=={'kind','id','version'},'DEFINITION_REFERENCES')
            keys.append(DefinitionKey(**ref))
        need(len(set(keys))==len(keys),'DEFINITION_DUPLICATE_REFERENCE')
        if record['kind'] in ('TASKTYPE','TASK_TEMPLATE') and 'defaults' in record['body']:validate_defaults(record['body']['defaults'])

    @property
    def envelope(self):return strict_json(self.raw_bytes)
    @property
    def key(self):
        record=self.envelope;return DefinitionKey(record['kind'],record['id'],record['version'])
    @property
    def references(self):return tuple(DefinitionKey(**ref) for ref in self.envelope['body'].get('references',[]))
    @property
    def raw_hash(self):return sha256(self.raw_bytes).hexdigest()


@dataclass(frozen=True)
class CachedDefinition:
    artifact:DefinitionArtifact
    registered_at:datetime

    def __post_init__(self):need(isinstance(self.registered_at,datetime) and self.registered_at.utcoffset() is not None,'DEFINITION_REGISTRATION_TIME')
    @property
    def key(self):return self.artifact.key
    @property
    def body(self):return self.artifact.envelope['body']


@dataclass(frozen=True)
class DefaultSnapshot:
    source:DefinitionKey
    source_hash:str
    _values_json:str=field(repr=False)
    meaning:str='INITIAL_DEFAULTS_NOT_CANONICAL_REMAINING_OR_GENERATION_AUTHORITY'
    @property
    def values(self):return strict_json(self._values_json)


class DefinitionRepository(Protocol):
    def get(self,key:DefinitionKey)->CachedDefinition|None: ...


def defaults_from(record):
    need(isinstance(record,CachedDefinition) and record.key.kind in ('TASKTYPE','TASK_TEMPLATE'),'DEFINITION_DEFAULT_KIND')
    values=record.body.get('defaults');validate_defaults(values)
    return DefaultSnapshot(record.key,record.artifact.request.content_hash,canonical(values))


def resolve_task_definitions(repository,core,*,profile_key=None):
    """Resolve exact supplied versions; never choose latest or generate Tasks."""
    keys=[]
    if core['task_type_ref'] is not None:keys.append(DefinitionKey('TASKTYPE',**core['task_type_ref']))
    context=core['context']
    if context is not None and context['kind'] in ('COURSE','ACTIVITY'):
        expected_kind='COURSE_PROFILE' if context['kind']=='COURSE' else 'ACTIVITY_PROFILE'
        need(isinstance(profile_key,DefinitionKey) and (profile_key.kind,profile_key.id)==(expected_kind,context['id']),'DEFINITION_PROFILE_VERSION_REQUIRED')
        keys.append(profile_key)
    elif profile_key is not None:raise DefinitionError('DEFINITION_PROFILE_CONTEXT_MISMATCH')
    result=[];seen=set();pending=list(keys)
    while pending:
        key=pending.pop(0)
        if key in seen:continue
        seen.add(key);record=repository.get(key)
        need(record is not None,'DEFINITION_UNRESOLVED_REFERENCE')
        result.append(record);pending.extend(record.artifact.references)
    return tuple(result)
