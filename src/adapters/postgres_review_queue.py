"""Internal durable review capture store; source enumeration is a separate gate.

The complete queue service must derive a snapshot from independently authorized
database sources. This store never accepts JSON authority, resolves personal
answers or changes canonical Tasks. Only fresh process-metadata captures are
written; later pages load their immutable rows rather than current live data.
"""
from hashlib import sha256

from src.application.command_ledger import validate_caller
from src.application.definitions import canonical,identity
from src.application.review_queue import (ReviewQueueCursor,ReviewQueueHeader,ReviewQueueItem,ReviewQueueQuery,
    ReviewQueueSnapshot,make_review_queue_page_slice)
from src.application.transactions import require
from src.domain.task_aggregate import instant


class PostgresReviewQueueStore:
    def __init__(self,connection,*,clock,cursor_key):
        self.connection=connection;self.clock=clock;self.signer=ReviewQueueCursor(cursor_key)

    def append_in_transaction(self,snapshot,*,caller):
        from psycopg.pq import TransactionStatus
        from psycopg import sql
        validate_caller(caller)
        require(caller.origin=='USER_COMMAND' and isinstance(snapshot,ReviewQueueSnapshot),'REVIEW_QUEUE_TRUSTED_CAPTURE')
        require(self.connection.info.transaction_status==TransactionStatus.INTRANS,'REVIEW_QUEUE_OPEN_TRANSACTION')
        h=snapshot.header
        require(caller.principal_id==h['principal_id'],'REVIEW_QUEUE_CAPTURE_NOT_OWNED')
        require(instant(h['observed_at'])<=self.clock.now()<instant(h['expires_at']),'REVIEW_QUEUE_CAPTURE_TIME')
        require(self.connection.execute('SELECT revision,last_transaction_ref FROM whattodo.store_epoch WHERE singleton=TRUE').fetchone()
            ==(h['store_revision'],h['last_transaction_ref']),'REVIEW_QUEUE_CAPTURE_EPOCH_DRIFT')
        names=('snapshot_id','principal_id','request_id','query_hash','scope_hash','store_revision','last_transaction_ref',
            'observed_at','expires_at','item_count','entries_hash')
        row={k:(instant(h[k]) if k in ('observed_at','expires_at') else h[k]) for k in names}
        row.update(header_hash=snapshot.header_hash,header_bytes=snapshot.header_json.encode())
        self.connection.execute(sql.SQL('INSERT INTO whattodo.review_queue_snapshot ({}) VALUES ({})').format(
            sql.SQL(',').join(map(sql.Identifier,row)),sql.SQL(',').join(sql.Placeholder() for _ in row)),tuple(row.values()))
        for ordinal,item in enumerate(snapshot.items,1):
            self.connection.execute('INSERT INTO whattodo.review_queue_entry VALUES(%s,%s,%s,%s,%s)',
                (h['snapshot_id'],ordinal,item.item_id,item.payload_hash,canonical(item.payload).encode()))
        return ReviewQueueHeader(snapshot.header_json)

    def get_in_transaction(self,snapshot_id,query,*,caller,scope_hash):
        validate_caller(caller)
        require(caller.origin=='USER_COMMAND' and identity(snapshot_id) and isinstance(query,ReviewQueueQuery),
            'REVIEW_QUEUE_TRUSTED_READER')
        row=self.connection.execute('''SELECT snapshot_id,principal_id,request_id,query_hash,scope_hash,store_revision,
            last_transaction_ref,observed_at,expires_at,item_count,entries_hash,header_hash,header_bytes
            FROM whattodo.review_queue_snapshot WHERE snapshot_id=%s AND principal_id=%s''',
            (snapshot_id,caller.principal_id)).fetchone()
        require(row is not None,'REVIEW_QUEUE_SNAPSHOT_UNAVAILABLE')
        require(sha256(bytes(row[-1])).hexdigest()==row[-2],'REVIEW_QUEUE_HEADER_HASH_DRIFT')
        header=ReviewQueueHeader(bytes(row[-1]).decode('utf-8'));h=header.header
        expected=(h['snapshot_id'],h['principal_id'],h['request_id'],h['query_hash'],h['scope_hash'],h['store_revision'],
            h['last_transaction_ref'],instant(h['observed_at']),instant(h['expires_at']),h['item_count'],h['entries_hash'],header.header_hash)
        require(row[:-1]==expected,'REVIEW_QUEUE_HEADER_PROJECTION_DRIFT')
        require(h['query_hash']==query.fingerprint and h['scope_hash']==scope_hash,'REVIEW_QUEUE_SNAPSHOT_SCOPE_CONFLICT')
        require(instant(h['observed_at'])<=self.clock.now()<instant(h['expires_at']),'REVIEW_QUEUE_SNAPSHOT_EXPIRED')
        return header

    def by_request_in_transaction(self,request_id,query,*,caller,scope_hash):
        validate_caller(caller)
        require(caller.origin=='USER_COMMAND' and identity(request_id) and isinstance(query,ReviewQueueQuery),
            'REVIEW_QUEUE_REQUEST_ID')
        row=self.connection.execute('SELECT snapshot_id FROM whattodo.review_queue_snapshot WHERE request_id=%s AND principal_id=%s',
            (request_id,caller.principal_id)).fetchone()
        return self.get_in_transaction(row[0],query,caller=caller,scope_hash=scope_hash) if row is not None else None

    def page_in_transaction(self,header,query,*,index,caller,scope_hash):
        validate_caller(caller)
        require(isinstance(header,ReviewQueueHeader) and caller.origin=='USER_COMMAND'
            and header.header['principal_id']==caller.principal_id,'REVIEW_QUEUE_PAGE_NOT_OWNED')
        h=header.header
        observed=self.get_in_transaction(h['snapshot_id'],query,caller=caller,scope_hash=scope_hash)
        require(observed==header,'REVIEW_QUEUE_PAGE_HEADER_DRIFT')
        require(isinstance(query,ReviewQueueQuery) and query.fingerprint==h['query_hash']
            and type(index) is int and 0<=index<=h['item_count'],'REVIEW_QUEUE_PAGE_SCOPE')
        rows=self.connection.execute('''SELECT ordinal,item_id,payload_hash,payload_bytes FROM whattodo.review_queue_entry
            WHERE snapshot_id=%s AND ordinal>%s ORDER BY ordinal LIMIT %s''',(h['snapshot_id'],index,query.page_size)).fetchall()
        require([r[0] for r in rows]==list(range(index+1,index+1+min(query.page_size,h['item_count']-index))),
            'REVIEW_QUEUE_CAPTURE_MEMBERSHIP_DRIFT')
        items=[]
        from src.application.definitions import strict_json
        for ordinal,item_id,payload_hash,raw in rows:
            require(sha256(bytes(raw)).hexdigest()==payload_hash,'REVIEW_QUEUE_ENTRY_HASH_DRIFT')
            item=ReviewQueueItem.from_payload(strict_json(bytes(raw)))
            require(item.item_id==item_id and item.payload_hash==payload_hash,'REVIEW_QUEUE_ENTRY_PROJECTION_DRIFT')
            items.append(item)
        return make_review_queue_page_slice(header,tuple(items),query,index=index,signer=self.signer)
