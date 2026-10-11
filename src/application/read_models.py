"""Owned read queries, durable immutable references and signed pagination."""
from base64 import urlsafe_b64decode,urlsafe_b64encode
from dataclasses import dataclass,field
from hashlib import sha256
from hmac import compare_digest,new as hmac_new
from copy import deepcopy
from src.application.definitions import canonical,identity,strict_json
from src.application.task_resolution import user
from src.application.task_storage import TaskStorageRecord
from src.application.transactions import require
from src.domain.task_aggregate import instant
MAX_SNAPSHOT_BYTES=8388608;MAX_REFERENCES=50000;MAX_PAGE_BYTES=240000
PENDING_KINDS=frozenset(('MANUAL_CREATION','EVIDENCE_CANDIDATE','EVIDENCE_CONFLICT','CLARIFICATION'))
STATES=frozenset(('CURRENT','HISTORICAL','OPEN','RESOLVED','REJECTED','SUPERSEDED'))


@dataclass(frozen=True)
class ReadQuery:
    payload_json: str = field(repr=False)
    def __post_init__(self):
        v=self.as_record();require(isinstance(v,dict) and set(v)=={'schema_version','view','task_id','filters','pending_kind','include_closed','page_size','cursor'},'READ_QUERY_INVALID')
        require(isinstance(v['filters'],dict) and set(v['filters'])=={'completion','disposition','trust','domain','context'},'READ_QUERY_INVALID')
        require(v['pending_kind'] is None or v['pending_kind'] in PENDING_KINDS,'READ_QUERY_INVALID')
        require(v['cursor'] is None or isinstance(v['cursor'],str) and 0<len(v['cursor'])<=2048,'READ_QUERY_INVALID')
        for key,allowed in (('completion',('INCOMPLETE','COMPLETE')),('disposition',('ACTIVE','CANCELLED','EXPIRED')),('trust',('TRUSTED','STALE','CONFLICTED','UNKNOWN')),('domain',('study','exercise','life_administration','other'))):
            require(v['filters'][key] is None or v['filters'][key] in allowed,'READ_QUERY_INVALID')
        ctx=v['filters']['context'];require(ctx is None or isinstance(ctx,dict) and set(ctx)=={'kind','id'} and ctx['kind'] in ('COURSE','ACTIVITY','GOAL','EXAM') and identity(ctx['id']),'READ_QUERY_INVALID')
        require(v['schema_version']=='0.1.0-read-query' and v['view'] in ('TASKS','HISTORY','PENDING'),'READ_QUERY_INVALID')
        require(type(v['page_size']) is int and 1<=v['page_size']<=100 and type(v['include_closed']) is bool,'READ_QUERY_INVALID')
        if v['view']=='HISTORY':require(identity(v['task_id']),'READ_HISTORY_TARGET_REQUIRED')
        else:require(v['task_id'] is None,'READ_QUERY_TARGET_SCOPE')
        if v['view']!='TASKS':require(all(value is None for value in v['filters'].values()),'READ_QUERY_FILTER_SCOPE')
        if v['view']!='PENDING':require(v['pending_kind'] is None and not v['include_closed'],'READ_QUERY_PENDING_SCOPE')
        object.__setattr__(self,'payload_json',canonical(v))
    def as_record(self):return strict_json(self.payload_json)
    @property
    def fingerprint(self):
        v=self.as_record();v['cursor']=None;return sha256(canonical(v).encode()).hexdigest()
    @property
    def cursor(self):return self.as_record()['cursor']
    @property
    def view(self):return self.as_record()['view']


def admit_query(codec,raw):
    require(isinstance(raw,bytes) and 0<len(raw)<=8192,'READ_QUERY_SIZE_LIMIT')
    wire=codec.admit('read-query',raw);require(wire.status=='SUPPORTED_SHAPE','READ_QUERY_SHAPE_UNSUPPORTED')
    return ReadQuery(canonical(wire.payload))


class CursorSigner:
    def __init__(self,key):
        require(isinstance(key,bytes) and 32<=len(key)<=128,'READ_CURSOR_KEY_REQUIRED');self._key=key
    def encode(self,snapshot_id,index,principal_id,query_hash):
        require(identity(snapshot_id) and identity(principal_id) and type(index) is int and index>0,'READ_CURSOR_INVALID')
        raw=canonical(dict(s=snapshot_id,i=index,p=principal_id,q=query_hash)).encode()
        return urlsafe_b64encode(raw).rstrip(b'=').decode()+'.'+urlsafe_b64encode(hmac_new(self._key,raw,'sha256').digest()).rstrip(b'=').decode()
    def decode(self,token,*,principal_id,query_hash):
        try:
            require(isinstance(token,str) and 0<len(token)<=2048 and token.isascii(),'READ_CURSOR_INVALID')
            payload,signature=token.split('.');require(all(part and all(c in 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789_-' for c in part) for part in (payload,signature)),'READ_CURSOR_INVALID');raw=urlsafe_b64decode(payload+'='*((-len(payload))%4));actual=urlsafe_b64decode(signature+'='*((-len(signature))%4))
            require(urlsafe_b64encode(raw).rstrip(b'=').decode()==payload and urlsafe_b64encode(actual).rstrip(b'=').decode()==signature,'READ_CURSOR_INVALID')
            require(compare_digest(actual,hmac_new(self._key,raw,'sha256').digest()),'READ_CURSOR_INVALID');v=strict_json(raw)
            require(set(v)=={'s','i','p','q'} and identity(v['s']) and type(v['i']) is int and 0<v['i']<=MAX_REFERENCES,'READ_CURSOR_INVALID')
            require((v['p'],v['q'])==(principal_id,query_hash),'READ_CURSOR_SCOPE_CONFLICT');return v['s'],v['i']
        except Exception as exc:
            if str(exc)=='READ_CURSOR_SCOPE_CONFLICT':raise
            require(False,'READ_CURSOR_INVALID')


@dataclass(frozen=True)
class ReadSnapshot:
    raw_bytes: bytes = field(repr=False)
    payload_json: str = field(repr=False)
    def __post_init__(self):
        require(isinstance(self.raw_bytes,bytes) and 0<len(self.raw_bytes)<=MAX_SNAPSHOT_BYTES,'READ_SNAPSHOT_SIZE_LIMIT')
        v=self.as_record();require(strict_json(self.raw_bytes)==v,'READ_SNAPSHOT_BYTES_DRIFT')
        require(set(v)=={'snapshot_id','principal_id','query','query_hash','scope_hash','store_revision','last_transaction_ref','observed_at','expires_at','references','source_scope_state'},'READ_SNAPSHOT_SHAPE')
        require(v['source_scope_state'] in ('CONFIGURED','UNCONFIGURED','NOT_APPLICABLE'),'READ_SNAPSHOT_SCOPE_STATE')
        require(identity(v['snapshot_id']) and identity(v['principal_id']) and type(v['store_revision']) is int and v['store_revision']>0,'READ_SNAPSHOT_IDENTITY')
        require((v['last_transaction_ref'] is None) if v['store_revision']==1 else identity(v['last_transaction_ref']),'READ_SNAPSHOT_EPOCH')
        q=ReadQuery(canonical(v['query']));require(q.cursor is None and q.fingerprint==v['query_hash'],'READ_SNAPSHOT_QUERY_DRIFT')
        require(all(isinstance(v[k],str) and len(v[k])==64 and all(c in '0123456789abcdef' for c in v[k]) for k in ('query_hash','scope_hash')),'READ_SNAPSHOT_HASH')
        require(instant(v['expires_at'])>instant(v['observed_at']),'READ_SNAPSHOT_TIME')
        refs=v['references'];require(isinstance(refs,list) and len(refs)<=MAX_REFERENCES,'READ_SNAPSHOT_REFERENCES_TOO_BROAD')
        for r in refs:
            require(isinstance(r,dict) and set(r)=={'kind','id','revision','state','actual_seconds','transaction_ref','store_revision','pending_id','pending_revision'} and identity(r['id']) and type(r['revision']) is int and r['revision']>0
                and r['state'] in STATES and type(r['actual_seconds']) is int and r['actual_seconds']>=0,'READ_SNAPSHOT_REFERENCE')
            require(r['kind'] in ({'TASK'} if q.view=='TASKS' else {'HISTORY'} if q.view=='HISTORY' else PENDING_KINDS),'READ_SNAPSHOT_REFERENCE_KIND')
            require(r['transaction_ref'] is None or identity(r['transaction_ref']),'READ_SNAPSHOT_REFERENCE')
            require(r['store_revision'] is None or type(r['store_revision']) is int and 1<r['store_revision']<=v['store_revision'],'READ_SNAPSHOT_REFERENCE')
            require((r['pending_id'] is None and r['pending_revision'] is None) if r['kind'] not in ('EVIDENCE_CANDIDATE','EVIDENCE_CONFLICT') else identity(r['pending_id']) and type(r['pending_revision']) is int and r['pending_revision']>0,'READ_SNAPSHOT_REFERENCE')
            require((r['transaction_ref'] is None)==(r['store_revision'] is None),'READ_SNAPSHOT_REFERENCE')
            if r['kind'] in ('TASK','HISTORY'):require(r['transaction_ref'] is not None and r['state']==('CURRENT' if q.view=='TASKS' else 'HISTORICAL'),'READ_SNAPSHOT_REFERENCE')
            else:require(r['actual_seconds']==0 and r['state'] in ('OPEN','RESOLVED','REJECTED','SUPERSEDED'),'READ_SNAPSHOT_REFERENCE')
        keys=[(r['kind'],r['id'],r['revision']) for r in refs];require(keys==sorted(set(keys)),'READ_SNAPSHOT_REFERENCE_ORDER')
    def as_record(self):return strict_json(self.payload_json)
    @property
    def fingerprint(self):return sha256(self.raw_bytes).hexdigest()


def make_snapshot(query,*,snapshot_id,principal_id,scope_hash,store_revision,last_transaction_ref,observed_at,expires_at,references,source_scope_state):
    q=query.as_record();q['cursor']=None
    v=dict(snapshot_id=snapshot_id,principal_id=principal_id,query=q,query_hash=query.fingerprint,scope_hash=scope_hash,store_revision=store_revision,last_transaction_ref=last_transaction_ref,
        observed_at=observed_at.isoformat(),expires_at=expires_at.isoformat(),source_scope_state=source_scope_state,references=sorted(deepcopy(references),key=lambda r:(r['kind'],r['id'],r['revision'])))
    raw=canonical(v).encode();return ReadSnapshot(raw,canonical(v))


def task_view(record,actual_seconds):
    require(isinstance(record,TaskStorageRecord) and type(actual_seconds) is int and actual_seconds>=0,'READ_TASK_PROJECTION')
    v=record.aggregate.as_record();c=v['core'];u=v['effort']['user_remaining'];total=v['work']['total_estimate']
    result={k:c[k] for k in ('task_id','revision','title','domain','context','task_type_ref','completion','disposition','requiredness','importance','difficulty')}
    result.update(trust=c['metadata']['trust'],user_remaining={k:u.get(k) for k in ('seconds','observation_id','observed_at','verified_at')} if u is not None else None,
        actual_seconds=actual_seconds,total_estimate_seconds=total['seconds'] if total is not None else None,timing=deepcopy(v['timing']),
        field_sources=[dict(field=p['field'],source_ref=p['source_ref']) for p in v['provenance']])
    return result


def semantic_changes(before,after):
    skip={'task_id','revision','field_sources'}
    return sorted('/'+k for k in after if k not in skip and (before is None or before.get(k)!=after[k]))


@dataclass(frozen=True)
class ReadPage:
    payload_json: str = field(repr=False)
    def as_record(self):return strict_json(self.payload_json)


def make_page(codec,snapshot,items,*,start_index,signer,caller):
    v=snapshot.as_record();user(caller,v['principal_id']);end=start_index+len(items);more=end<len(v['references'])
    require(type(start_index) is int and 0<=start_index<=len(v['references']) and len(items)<=v['query']['page_size'] and (bool(items) or not more),'READ_PAGE_POSITION')
    require(end<=len(v['references']),'READ_PAGE_POSITION')
    for item,ref in zip(items,v['references'][start_index:end]):
        require(all(item.get(k)==ref[k] for k in ('kind','id','revision','state')),'READ_PAGE_REFERENCE_DRIFT')
        if item['kind'] in ('TASK','HISTORY'):
            task=item['data'] if item['kind']=='TASK' else item['data']['task']
            require((task['task_id'],task['revision'],task['actual_seconds'])==(ref['id'],ref['revision'],ref['actual_seconds']),'READ_PAGE_TASK_DRIFT')
    page=dict(schema_version='0.1.0-read-page',view=v['query']['view'],snapshot_id=v['snapshot_id'],store_revision=v['store_revision'],observed_at=v['observed_at'],expires_at=v['expires_at'],
        query_hash=v['query_hash'],source_scope_state=v['source_scope_state'],items=items,has_more=more,next_cursor=signer.encode(v['snapshot_id'],end,v['principal_id'],v['query_hash']) if more else None)
    raw=canonical(page).encode();require(len(raw)<=262144,'READ_PAGE_SIZE_LIMIT')
    require(codec.admit('read-page',raw).status=='SUPPORTED_SHAPE','READ_PAGE_SHAPE_UNSUPPORTED');return ReadPage(canonical(page))
