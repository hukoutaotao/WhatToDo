"""Full frozen review questions: ranking never answers or removes an item.

The PostgreSQL source adapter must independently enumerate the complete owned
scope. These values validate that handoff and provide stable pagination; supplied
questions or a successful read confer no authority to change personal state.
"""
from base64 import urlsafe_b64decode, urlsafe_b64encode
from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime
from hashlib import sha256
from hmac import compare_digest, new as hmac_new
import re

from src.application.definitions import canonical, identity, strict_json
from src.application.transactions import require
from src.domain.task_aggregate import instant

QUERY_VERSION='0.1.0-review-queue-query'
PAGE_VERSION='0.1.0-review-queue-page'
SNAPSHOT_VERSION='0.1.0-review-queue-snapshot'
MAX_ITEMS=1000000
MAX_ITEM_BYTES=2097152
MAX_SNAPSHOT_BYTES=268435456
MAX_PAGE_BYTES=4194304
KINDS=frozenset(('TASK_ESTIMATE','MANUAL_CREATION','CLARIFICATION','EVIDENCE_CANDIDATE',
    'EVIDENCE_CONFLICT','GENERATION_PENDING','GENERATION_FAILED','STAGE_PENDING','SOURCE_BLOCKER'))


def digest(value):return sha256(canonical(value).encode()).hexdigest()
def is_hash(value):return isinstance(value,str) and re.fullmatch('[a-f0-9]{64}',value) is not None
def aware(value):return isinstance(value,datetime) and value.utcoffset() is not None


@dataclass(frozen=True)
class ReviewQueueQuery:
    page_size: int
    target_minutes: int
    cursor: str | None = None

    def __post_init__(self):
        require(type(self.page_size) is int and 1<=self.page_size<=100
            and type(self.target_minutes) is int and 1<=self.target_minutes<=120,'REVIEW_QUEUE_QUERY_LIMITS')
        require(self.cursor is None or isinstance(self.cursor,str) and 0<len(self.cursor)<=2048 and self.cursor.isascii(),
            'REVIEW_QUEUE_CURSOR_SHAPE')
    def as_record(self):return dict(schema_version=QUERY_VERSION,page_size=self.page_size,target_minutes=self.target_minutes,cursor=self.cursor)
    @property
    def fingerprint(self):return digest(self.as_record()|dict(cursor=None))


def admit_review_queue_query(codec,raw):
    require(isinstance(raw,bytes) and 0<len(raw)<=8192,'REVIEW_QUEUE_QUERY_SIZE')
    wire=codec.admit('review-queue-query',raw)
    require(wire.status=='SUPPORTED_SHAPE','REVIEW_QUEUE_QUERY_UNSUPPORTED')
    v=wire.payload
    return ReviewQueueQuery(v['page_size'],v['target_minutes'],v['cursor'])


@dataclass(frozen=True)
class ReviewQueueItem:
    kind: str
    source_id: str
    source_revision: int
    reason: str
    title: str | None
    priority: int
    importance: int | None
    group_ref: str
    source_refs: tuple[str,...] = ()
    task_id: str | None = None
    task_revision: int | None = None
    details_json: str = field(default='{}',repr=False)

    def __post_init__(self):
        require(self.kind in KINDS and identity(self.source_id) and type(self.source_revision) is int
            and 0<self.source_revision<=9223372036854775807,'REVIEW_QUEUE_ITEM_IDENTITY')
        require(isinstance(self.reason,str) and re.fullmatch('[A-Z][A-Z0-9_]{0,63}',self.reason)
            and type(self.priority) is int and 0<=self.priority<=9,'REVIEW_QUEUE_ITEM_PRIORITY')
        require(self.importance is None or type(self.importance) is int and 1<=self.importance<=5,'REVIEW_QUEUE_ITEM_IMPORTANCE')
        require(self.title is None or isinstance(self.title,str) and self.title.strip() and len(self.title)<=500,
            'REVIEW_QUEUE_ITEM_TITLE')
        require(identity(self.group_ref) and isinstance(self.source_refs,tuple) and len(self.source_refs)<=100
            and len(set(self.source_refs))==len(self.source_refs) and all(identity(s) for s in self.source_refs),'REVIEW_QUEUE_ITEM_SOURCES')
        require((self.task_id is None and self.task_revision is None) or identity(self.task_id)
            and type(self.task_revision) is int and 0<self.task_revision<=9223372036854775807,'REVIEW_QUEUE_ITEM_TASK_REF')
        require(isinstance(self.details_json,str) and len(self.details_json.encode())<=MAX_ITEM_BYTES
            and isinstance(strict_json(self.details_json),dict),'REVIEW_QUEUE_ITEM_DETAILS')
        object.__setattr__(self,'details_json',canonical(strict_json(self.details_json)))
        require(len(canonical(self.payload).encode())<=MAX_ITEM_BYTES,'REVIEW_QUEUE_ITEM_TOO_LARGE')

    @property
    def item_id(self):return 'review-item-'+digest([self.kind,self.source_id,self.source_revision,self.reason])
    @property
    def sort_key(self):return (self.priority,-(self.importance or 0),self.kind,self.source_id,self.source_revision,self.reason)
    @property
    def payload(self):
        needs_response=self.kind!='SOURCE_BLOCKER' and not(self.kind=='CLARIFICATION' and self.reason=='AWAITING_EXECUTION')
        return dict(item_id=self.item_id,kind=self.kind,source_ref=dict(id=self.source_id,revision=self.source_revision),
            reason=self.reason,title=self.title,priority=self.priority,importance=self.importance,group_ref=self.group_ref,
            source_refs=list(self.source_refs),task_ref=dict(task_id=self.task_id,revision=self.task_revision) if self.task_id is not None else None,
            details=strict_json(self.details_json),answer=None,requires_response=needs_response)
    @property
    def payload_hash(self):return digest(self.payload)
    @classmethod
    def from_payload(cls,value):
        require(isinstance(value,dict),'REVIEW_QUEUE_ITEM_PAYLOAD')
        require(value.get('answer') is None and type(value.get('requires_response')) is bool,'REVIEW_QUEUE_ITEM_PAYLOAD')
        try:
            ref=value['source_ref'];task=value['task_ref']
            result=cls(value['kind'],ref['id'],ref['revision'],value['reason'],value['title'],value['priority'],value['importance'],
                value['group_ref'],tuple(value['source_refs']),task['task_id'] if task is not None else None,
                task['revision'] if task is not None else None,canonical(value['details']))
        except (KeyError,TypeError,ValueError):require(False,'REVIEW_QUEUE_ITEM_PAYLOAD')
        require(result.payload==value,'REVIEW_QUEUE_ITEM_PAYLOAD')
        return result


def item_manifest(items):
    """SQL uses the same unambiguous ASCII ordinal/hash manifest."""
    return ''.join(f'{n}:{item.item_id}:{item.payload_hash}\n' for n,item in enumerate(items,1)).encode('ascii')


@dataclass(frozen=True)
class ReviewQueueSnapshot:
    header_json: str = field(repr=False)
    items: tuple[ReviewQueueItem,...] = field(repr=False)

    def __post_init__(self):
        header=ReviewQueueHeader(self.header_json);h=header.header
        require(isinstance(self.items,tuple) and len(self.items)<=MAX_ITEMS and all(isinstance(i,ReviewQueueItem) for i in self.items)
            and len({i.item_id for i in self.items})==len(self.items),'REVIEW_QUEUE_SNAPSHOT_ITEMS')
        require(list(self.items)==sorted(self.items,key=lambda i:i.sort_key),'REVIEW_QUEUE_SNAPSHOT_ORDER')
        require(h['item_count']==len(self.items)
            and h['entries_hash']==sha256(item_manifest(self.items)).hexdigest(),'REVIEW_QUEUE_SNAPSHOT_MEMBERSHIP')
        groups=[dict(group_ref=k,item_count=v) for k,v in sorted(Counter(i.group_ref for i in self.items).items())]
        require(h['groups']==groups,'REVIEW_QUEUE_SNAPSHOT_GROUPS')
        require(sum(len(canonical(i.payload).encode()) for i in self.items)+len(self.header_json.encode())<=MAX_SNAPSHOT_BYTES,
            'REVIEW_QUEUE_SNAPSHOT_TOO_LARGE')
        # Admit the whole capture or reject it explicitly. A large group index
        # must never strand a question that fitted the per-item byte limit.
        envelope=_page_envelope(h,header.header_hash,h['query']['target_minutes'],h['item_count'],100,'x'*2048)
        largest=max((len(canonical(i.payload).encode()) for i in self.items),default=0)
        require(len(canonical(envelope).encode())+largest<=MAX_PAGE_BYTES,'REVIEW_QUEUE_PAGE_METADATA_TOO_LARGE')
        object.__setattr__(self,'header_json',header.header_json)
    @property
    def header(self):return strict_json(self.header_json)
    @property
    def header_hash(self):return sha256(self.header_json.encode()).hexdigest()


@dataclass(frozen=True)
class ReviewQueueHeader:
    """Owned persisted header; membership is checked by capture and SQL guards."""
    header_json: str = field(repr=False)
    def __post_init__(self):
        require(isinstance(self.header_json,str) and len(self.header_json.encode())<=8388608,'REVIEW_QUEUE_SNAPSHOT_HEADER')
        h=strict_json(self.header_json)
        require(isinstance(h,dict) and set(h)=={'schema_version','snapshot_id','principal_id','request_id','query','query_hash','scope_hash',
            'store_revision','last_transaction_ref','observed_at','expires_at','item_count','entries_hash','groups','coverage_blockers'},
            'REVIEW_QUEUE_SNAPSHOT_HEADER')
        require(h['schema_version']==SNAPSHOT_VERSION and all(identity(h[k]) for k in ('snapshot_id','principal_id','request_id')),
            'REVIEW_QUEUE_SNAPSHOT_IDENTITY')
        q=h['query']
        require(isinstance(q,dict),'REVIEW_QUEUE_SNAPSHOT_QUERY')
        try:query=ReviewQueueQuery(q['page_size'],q['target_minutes'],q['cursor'])
        except (KeyError,TypeError):require(False,'REVIEW_QUEUE_SNAPSHOT_QUERY')
        require(query.cursor is None and query.as_record()==q and h['query_hash']==query.fingerprint
            and is_hash(h['scope_hash']),'REVIEW_QUEUE_SNAPSHOT_QUERY')
        require(type(h['store_revision']) is int and 0<h['store_revision']<=9223372036854775807
            and ((h['store_revision']==1 and h['last_transaction_ref'] is None)
                or h['store_revision']>1 and identity(h['last_transaction_ref'])),'REVIEW_QUEUE_SNAPSHOT_EPOCH')
        try:start=instant(h['observed_at']);end=instant(h['expires_at'])
        except (TypeError,ValueError,OverflowError):require(False,'REVIEW_QUEUE_SNAPSHOT_TIME')
        require(start<end,'REVIEW_QUEUE_SNAPSHOT_TIME')
        require(type(h['item_count']) is int and 0<=h['item_count']<=MAX_ITEMS and is_hash(h['entries_hash']),
            'REVIEW_QUEUE_SNAPSHOT_MEMBERSHIP')
        require(isinstance(h['groups'],list) and len(h['groups'])<=MAX_ITEMS,'REVIEW_QUEUE_SNAPSHOT_GROUPS')
        keys=[];total=0
        for g in h['groups']:
            require(isinstance(g,dict) and set(g)=={'group_ref','item_count'} and identity(g['group_ref'])
                and type(g['item_count']) is int and 0<g['item_count']<=MAX_ITEMS,'REVIEW_QUEUE_SNAPSHOT_GROUPS')
            keys.append(g['group_ref']);total+=g['item_count']
        require(keys==sorted(set(keys)) and total==h['item_count'],'REVIEW_QUEUE_SNAPSHOT_GROUPS')
        require(isinstance(h['coverage_blockers'],list) and h['coverage_blockers']==sorted(set(h['coverage_blockers']))
            and all(isinstance(c,str) and re.fullmatch('[A-Z][A-Z0-9_]{0,63}',c) for c in h['coverage_blockers']),
            'REVIEW_QUEUE_SNAPSHOT_COVERAGE')
        object.__setattr__(self,'header_json',canonical(h))
    @property
    def header(self):return strict_json(self.header_json)
    @property
    def header_hash(self):return sha256(self.header_json.encode()).hexdigest()


def make_review_queue_snapshot(query,items,*,snapshot_id,principal_id,request_id,scope_hash,store_revision,last_transaction_ref,
                               observed_at,expires_at,coverage_blockers=()):
    require(isinstance(query,ReviewQueueQuery) and aware(observed_at) and aware(expires_at),'REVIEW_QUEUE_SNAPSHOT_INPUT')
    require(isinstance(items,tuple) and all(isinstance(i,ReviewQueueItem) for i in items),'REVIEW_QUEUE_SNAPSHOT_ITEMS')
    ordered=tuple(sorted(items,key=lambda i:i.sort_key))
    h=dict(schema_version=SNAPSHOT_VERSION,snapshot_id=snapshot_id,principal_id=principal_id,request_id=request_id,
        query=query.as_record()|dict(cursor=None),query_hash=query.fingerprint,scope_hash=scope_hash,store_revision=store_revision,
        last_transaction_ref=last_transaction_ref,observed_at=observed_at.isoformat(),expires_at=expires_at.isoformat(),
        item_count=len(ordered),entries_hash=sha256(item_manifest(ordered)).hexdigest(),
        groups=[dict(group_ref=k,item_count=v) for k,v in sorted(Counter(i.group_ref for i in ordered).items())],
        coverage_blockers=sorted(set(coverage_blockers)))
    return ReviewQueueSnapshot(canonical(h),ordered)


class ReviewQueueCursor:
    def __init__(self,key):
        require(isinstance(key,bytes) and 32<=len(key)<=128,'REVIEW_QUEUE_CURSOR_KEY')
        self._key=key
    def encode(self,snapshot_id,index,principal_id,query_hash):
        require(identity(snapshot_id) and identity(principal_id) and is_hash(query_hash)
            and type(index) is int and 0<index<=MAX_ITEMS,'REVIEW_QUEUE_CURSOR_INVALID')
        raw=canonical(dict(s=snapshot_id,i=index,p=principal_id,q=query_hash)).encode()
        encode=lambda v:urlsafe_b64encode(v).rstrip(b'=').decode('ascii')
        return encode(raw)+'.'+encode(hmac_new(self._key,raw,'sha256').digest())
    def decode(self,token,*,principal_id,query_hash):
        try:
            require(isinstance(token,str) and 0<len(token)<=2048 and token.isascii(),'REVIEW_QUEUE_CURSOR_INVALID')
            parts=token.split('.');require(len(parts)==2 and all(re.fullmatch('[A-Za-z0-9_-]+',p) for p in parts),'REVIEW_QUEUE_CURSOR_INVALID')
            raw,sig=(urlsafe_b64decode(p+'='*((-len(p))%4)) for p in parts)
            require(all(urlsafe_b64encode(v).rstrip(b'=').decode()==p for v,p in zip((raw,sig),parts))
                and compare_digest(sig,hmac_new(self._key,raw,'sha256').digest()),'REVIEW_QUEUE_CURSOR_INVALID')
            v=strict_json(raw)
            require(isinstance(v,dict) and set(v)=={'s','i','p','q'} and identity(v['s'])
                and type(v['i']) is int and 0<v['i']<=MAX_ITEMS,'REVIEW_QUEUE_CURSOR_INVALID')
            require((v['p'],v['q'])==(principal_id,query_hash),'REVIEW_QUEUE_CURSOR_SCOPE_CONFLICT')
            return v['s'],v['i']
        except Exception as exc:
            if str(exc)=='REVIEW_QUEUE_CURSOR_SCOPE_CONFLICT':raise
            require(False,'REVIEW_QUEUE_CURSOR_INVALID')


def make_review_queue_page(snapshot,query,*,index,signer):
    require(isinstance(snapshot,ReviewQueueSnapshot) and isinstance(query,ReviewQueueQuery) and isinstance(signer,ReviewQueueCursor),
        'REVIEW_QUEUE_PAGE_INPUT')
    return make_review_queue_page_slice(ReviewQueueHeader(snapshot.header_json),snapshot.items[index:index+query.page_size],
        query,index=index,signer=signer)


def _page_envelope(h,header_hash,target_minutes,index,count,cursor):
    return dict(schema_version=PAGE_VERSION,snapshot_id=h['snapshot_id'],snapshot_hash=header_hash,
        observed_at=h['observed_at'],expires_at=h['expires_at'],store_revision=h['store_revision'],target_minutes=target_minutes,
        total_items=h['item_count'],start_index=index,returned_count=count,items=[],groups=h['groups'],
        next_cursor=cursor,enumeration_complete=not h['coverage_blockers'],coverage_blockers=h['coverage_blockers'],
        personal_reconciliation_complete=False)


def make_review_queue_page_slice(header,items,query,*,index,signer):
    """Page only captured rows, without reloading or re-evaluating the full queue."""
    require(isinstance(header,ReviewQueueHeader) and isinstance(query,ReviewQueueQuery) and isinstance(signer,ReviewQueueCursor),
        'REVIEW_QUEUE_PAGE_INPUT')
    h=header.header
    require(query.fingerprint==h['query_hash'] and type(index) is int and 0<=index<=h['item_count'],'REVIEW_QUEUE_PAGE_SCOPE')
    require(isinstance(items,tuple) and len(items)==min(query.page_size,h['item_count']-index)
        and all(isinstance(item,ReviewQueueItem) for item in items),'REVIEW_QUEUE_PAGE_MEMBERSHIP')
    selected=[];size=0;result=None
    for item in items:
        body=item.payload;added=len(canonical(body).encode())
        next_index=index+len(selected)+1
        cursor=signer.encode(h['snapshot_id'],next_index,h['principal_id'],query.fingerprint) if next_index<h['item_count'] else None
        candidate=_page_envelope(h,header.header_hash,query.target_minutes,index,len(selected)+1,cursor)
        # The empty list is already in the envelope; charge item bytes plus
        # exactly one comma between adjacent items, including all metadata.
        total=len(canonical(candidate).encode())+size+added+len(selected)
        if selected and total>MAX_PAGE_BYTES:break
        require(total<=MAX_PAGE_BYTES,'REVIEW_QUEUE_PAGE_METADATA_TOO_LARGE')
        selected.append(body);size+=added
        result=candidate
    if result is None:
        result=_page_envelope(h,header.header_hash,query.target_minutes,index,0,None)
        require(len(canonical(result).encode())<=MAX_PAGE_BYTES,'REVIEW_QUEUE_PAGE_METADATA_TOO_LARGE')
    result['items']=selected
    return result
