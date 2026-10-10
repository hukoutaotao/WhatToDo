"""Explicit file layers and environment-secret references; no adapter activation."""
from copy import deepcopy
from collections.abc import Mapping
from hashlib import sha256
import json
import os
from pathlib import Path
import re

from src.adapters.contract_json import strict_json
from src.application.configuration import AdapterConfig,DefinitionSnapshot,RuntimeConfig,SecretRef

ADAPTERS=frozenset(('state_store','calendar_source','evidence_source','notification_sink','predictor','solver','renderer'))
KINDS=frozenset(('COURSE_PROFILE','ACTIVITY_PROFILE','TASKTYPE','TASK_TEMPLATE','RELATIONSHIP_RULE','PREFERENCE'))
ENV_NAME=re.compile(r'[A-Z][A-Z0-9_]{0,127}\Z')
HASH=re.compile(r'[a-f0-9]{64}\Z')


class ConfigurationError(ValueError):pass


def _need(condition,code):
    if not condition:raise ConfigurationError(code)


def _identity(value):return isinstance(value,str) and bool(value.strip()) and len(value)<=200


def _merge(base,override):
    result=deepcopy(base)
    for key,value in override.items():
        if isinstance(value,dict) and isinstance(result.get(key),dict):result[key]=_merge(result[key],value)
        else:result[key]=deepcopy(value)
    return result


def _read(path,code):
    try:
        with Path(path).open('rb') as stream:raw=stream.read(1048577)
        if len(raw)>1048576:raise ConfigurationError('CONFIG_INPUT_TOO_LARGE')
        return strict_json(raw)
    except ConfigurationError:raise
    except (OSError,UnicodeError,ValueError,RecursionError):raise ConfigurationError(code) from None


def _canonical(value):
    try:return json.dumps(value,sort_keys=True,ensure_ascii=False,separators=(',',':'),allow_nan=False)
    except (ValueError,TypeError,RecursionError):raise ConfigurationError('CONFIG_DEFINITION_ENCODING') from None


def load_runtime_config(base_path,*,override_path=None,definition_root=None,env=None):
    base=_read(base_path,'CONFIG_BASE_UNREADABLE')
    _need(isinstance(base,dict),'CONFIG_OBJECT_REQUIRED')
    if override_path is not None:
        override=_read(override_path,'CONFIG_OVERRIDE_UNREADABLE')
        _need(isinstance(override,dict),'CONFIG_OVERRIDE_OBJECT_REQUIRED')
        try:base=_merge(base,override)
        except RecursionError:raise ConfigurationError('CONFIG_LAYER_DEPTH') from None
    _need(set(base)=={'schema_version','planning_timezone','definitions','adapters'},'CONFIG_FIELDS')
    _need(base['schema_version']=='0.1.0-config','CONFIG_VERSION')
    _need(base['planning_timezone']=='Asia/Shanghai','CONFIG_PLANNING_TIMEZONE')
    _need(isinstance(base['adapters'],dict) and set(base['adapters'])==ADAPTERS,'CONFIG_ADAPTER_OWNERSHIP')
    environment=os.environ if env is None else env
    _need(isinstance(environment,Mapping),'CONFIG_ENVIRONMENT_MAPPING')
    adapters=[]
    for name,item in sorted(base['adapters'].items()):
        _need(isinstance(item,dict) and set(item)=={'mode','secret_env'},'CONFIG_ADAPTER_FIELDS')
        _need(item['mode'] in ('DISABLED','FAKE','LIVE'),'CONFIG_ADAPTER_MODE')
        if name=='state_store':_need(item['mode']!='DISABLED','CONFIG_CORE_STATE_STORE_REQUIRED')
        key=item['secret_env']
        _need(key is None or isinstance(key,str) and ENV_NAME.fullmatch(key) is not None,'CONFIG_SECRET_REFERENCE')
        if item['mode']=='LIVE' and name=='state_store':
            _need(key is not None,'CONFIG_ENABLED_SECRET_REFERENCE_REQUIRED')
        if item['mode']=='LIVE' and key is not None:
            secret=environment.get(key)
            _need(isinstance(secret,str) and bool(secret.strip()),'CONFIG_ENABLED_SECRET_UNAVAILABLE')
        adapters.append(AdapterConfig(name,item['mode'],SecretRef(key) if key is not None else None))
    refs=base['definitions'];_need(isinstance(refs,list),'CONFIG_DEFINITION_REFERENCES')
    try:root=Path(definition_root).resolve() if definition_root is not None else Path(base_path).resolve().parent
    except (OSError,ValueError,TypeError):raise ConfigurationError('CONFIG_DEFINITION_PATH_SCOPE') from None
    snapshots=[];identities=set();active_ids=set()
    for ref in refs:
        _need(isinstance(ref,dict) and set(ref)=={'kind','id','version','path','content_hash'},'CONFIG_DEFINITION_FIELDS')
        _need(isinstance(ref['kind'],str) and ref['kind'] in KINDS and _identity(ref['id']) and _identity(ref['version']),'CONFIG_DEFINITION_IDENTITY')
        _need(isinstance(ref['path'],str) and isinstance(ref['content_hash'],str) and HASH.fullmatch(ref['content_hash']) is not None,'CONFIG_DEFINITION_REFERENCE')
        identity=(ref['kind'],ref['id'],ref['version']);active=(ref['kind'],ref['id'])
        _need(identity not in identities and active not in active_ids,'CONFIG_DUPLICATE_ACTIVE_DEFINITION')
        identities.add(identity);active_ids.add(active)
        try:target=(root/ref['path']).resolve()
        except (OSError,ValueError):raise ConfigurationError('CONFIG_DEFINITION_PATH_SCOPE') from None
        _need(target.is_relative_to(root),'CONFIG_DEFINITION_PATH_SCOPE')
        body=_read(target,'CONFIG_DEFINITION_UNREADABLE')
        _need(isinstance(body,dict) and set(body)=={'kind','id','version','body'} and isinstance(body['body'],dict),'CONFIG_DEFINITION_ENVELOPE')
        try:actual=sha256(_canonical(body).encode('utf-8')).hexdigest()
        except UnicodeError:raise ConfigurationError('CONFIG_DEFINITION_ENCODING') from None
        _need(actual==ref['content_hash'],'CONFIG_DEFINITION_HASH')
        _need((body['kind'],body['id'],body['version'])==identity,'CONFIG_DEFINITION_VERSION')
        snapshots.append(DefinitionSnapshot(*identity,actual,_canonical(body['body'])))
    return RuntimeConfig(base['schema_version'],base['planning_timezone'],tuple(snapshots),tuple(adapters))
