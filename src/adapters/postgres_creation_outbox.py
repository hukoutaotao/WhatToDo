"""Scoped internal delivery port; canonical event writes are trigger-owned."""
from datetime import timedelta
from uuid import uuid4

from src.adapters.postgres_migrations import schema_checked_transaction
from src.application.creation_outbox import (CreationEvent,DeliveryLease,DeliveryOutcome,
    DeliverySnapshot,OutboxError,require,instant,lease_duration)
from src.application.definitions import identity
from src.application.evidence_storage import SourceScope
from src.domain.authorization import CallerIdentity

EVENT_COLUMNS='e.event_id,e.task_id,e.task_revision,e.content_hash,e.creation_transaction_ref,e.principal_id,e.authority_ref,e.occurred_at'
STATE_COLUMNS='v.revision,v.state,v.attempt,v.changed_at,v.available_at,v.worker_id,v.lease_token,v.lease_until,v.settled_worker_id,v.settled_token,v.settled_revision,v.outcome'
JOINS=''' FROM whattodo.canonical_creation_event e
 JOIN whattodo.creation_delivery_head h USING(event_id)
 JOIN whattodo.creation_delivery_revision v ON (v.event_id,v.revision)=(h.event_id,h.revision)
 JOIN whattodo.authority_record a ON a.authority_ref=e.authority_ref
 JOIN whattodo.source_record r ON r.record_id=a.source_record_ref
 JOIN whattodo.source_identity s USING(source_id)
 JOIN whattodo.source_scope p USING(provider,scope_ref) '''


class PostgresCreationOutbox:
    def __init__(self,connection,plan,*,application_version,clock,caller,worker_id,source_scopes):
        require(isinstance(caller,CallerIdentity) and caller.authenticated and caller.origin in ('USER_COMMAND','RELATIONSHIP_RULE')
                and identity(worker_id),'OUTBOX_TRUSTED_WORKER')
        require(isinstance(source_scopes,tuple) and 0<len(source_scopes)<=100 and
                all(isinstance(s,SourceScope) for s in source_scopes),'OUTBOX_SOURCE_REGISTRY')
        self.connection=connection;self.plan=plan;self.application_version=application_version
        self.clock=clock;self.caller=caller;self.worker_id=worker_id;self.scopes=source_scopes
        self.scope_sql="e.principal_id=%s AND s.source_type='USER' AND (s.provider,s.scope_ref,p.account_ref) IN ("+','.join('(%s,%s,%s)' for _ in source_scopes)+')'
        self.scope_args=(caller.principal_id,)+tuple(v for s in source_scopes for v in (s.provider,s.scope_ref,s.account_ref))

    def _select(self,where='',args=(),lock=''):
        return self.connection.execute('SELECT '+EVENT_COLUMNS+','+STATE_COLUMNS+JOINS+' WHERE '+self.scope_sql+where+lock,
                                       self.scope_args+args).fetchone()

    def _snapshot(self,row):
        event=CreationEvent(*row[:8]);v=row[8:]
        lease=DeliveryLease(event,v[0],v[2],v[5],v[6],v[3],v[7]) if v[1]=='CLAIMED' and v[5]==self.worker_id else None
        outcome=DeliveryOutcome.from_payload(v[11]) if v[11] is not None else None
        return DeliverySnapshot(event,v[0],v[2],v[1],v[3],v[4],lease,outcome)

    def get(self,event_id):
        require(identity(event_id),'OUTBOX_EVENT_ID')
        with schema_checked_transaction(self.connection,self.plan,application_version=self.application_version):
            row=self._select(' AND e.event_id=%s',(event_id,))
            return self._snapshot(row) if row else None

    def _append(self,row,*,state,now,attempt,worker=None,token=None,until=None,outcome=None,settled=None):
        from psycopg.types.json import Jsonb
        v=row[8:];revision=v[0]+1;event_id=row[0]
        available=outcome.retry_at if outcome and outcome.kind=='RETRY' else v[4]
        self.connection.execute('''INSERT INTO whattodo.creation_delivery_revision
          (event_id,revision,state,attempt,changed_at,available_at,worker_id,lease_token,lease_until,
           settled_worker_id,settled_token,settled_revision,outcome) VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)''',
          (event_id,revision,state,attempt,now,available,worker,token,until,
           settled.worker_id if settled else None,settled.token if settled else None,
           settled.revision if settled else None,Jsonb(outcome.payload) if outcome else None))
        require(self.connection.execute('UPDATE whattodo.creation_delivery_head SET revision=%s WHERE event_id=%s AND revision=%s',
            (revision,event_id,v[0])).rowcount==1,'OUTBOX_STALE_DELIVERY')
        return self._snapshot(self._select(' AND e.event_id=%s',(event_id,)))

    def claim(self,*,lease_seconds=300):
        duration=lease_duration(lease_seconds);now=instant(self.clock.now())
        from psycopg import Error
        try:
            with schema_checked_transaction(self.connection,self.plan,application_version=self.application_version,read_only=False):
                row=self._select(" AND ((v.state='READY' AND v.available_at<=%s) OR (v.state='CLAIMED' AND v.lease_until<=%s))",
                    (now,now),' ORDER BY e.occurred_at,e.event_id LIMIT 1 FOR UPDATE OF h SKIP LOCKED')
                if row is None:return None
                require(now>=row[11],'OUTBOX_CLOCK_REGRESSION')
                result=self._append(row,state='CLAIMED',now=now,attempt=row[10]+1,worker=self.worker_id,
                                    token=uuid4().hex,until=now+timedelta(seconds=duration))
                return result.lease
        except Error as exc:raise OutboxError('OUTBOX_STORAGE_RETRY' if exc.sqlstate=='40001' else 'OUTBOX_STORAGE_FAILED') from None

    def _owned(self,lease):
        require(isinstance(lease,DeliveryLease) and lease.worker_id==self.worker_id
                and lease.event.principal_id==self.caller.principal_id,'OUTBOX_LEASE_OWNER')
        row=self._select(' AND e.event_id=%s',(lease.event.event_id,),' FOR UPDATE OF h')
        require(row is not None,'OUTBOX_EVENT_NOT_OWNED')
        require(CreationEvent(*row[:8])==lease.event,'OUTBOX_STALE_LEASE')
        return row

    def _live(self,row,lease,now):
        current=self._snapshot(row).lease
        require(current==lease and current is not None and now<current.expires_at,'OUTBOX_STALE_LEASE')
        require(now>=current.changed_at,'OUTBOX_CLOCK_REGRESSION')

    def renew(self,lease,*,lease_seconds=300):
        duration=lease_duration(lease_seconds);now=instant(self.clock.now())
        from psycopg import Error
        try:
            with schema_checked_transaction(self.connection,self.plan,application_version=self.application_version,read_only=False):
                row=self._owned(lease);self._live(row,lease,now);until=now+timedelta(seconds=duration)
                require(until>lease.expires_at,'OUTBOX_RENEWAL_SHRINK')
                return self._append(row,state='CLAIMED',now=now,attempt=lease.attempt,worker=self.worker_id,token=lease.token,until=until).lease
        except Error as exc:raise OutboxError('OUTBOX_STORAGE_RETRY' if exc.sqlstate=='40001' else 'OUTBOX_STORAGE_FAILED') from None

    def settle(self,lease,outcome):
        require(isinstance(outcome,DeliveryOutcome),'OUTBOX_TYPED_OUTCOME')
        now=instant(self.clock.now())
        from psycopg import Error
        try:
            with schema_checked_transaction(self.connection,self.plan,application_version=self.application_version,read_only=False):
                row=self._owned(lease)
                original=self.connection.execute('SELECT '+STATE_COLUMNS.replace('v.','')+' FROM whattodo.creation_delivery_revision WHERE event_id=%s AND revision=%s',
                    (lease.event.event_id,lease.revision)).fetchone()
                require(original is not None and self._snapshot(row[:8]+original).lease==lease,'OUTBOX_STALE_LEASE')
                prior=self.connection.execute('''SELECT revision,outcome FROM whattodo.creation_delivery_revision
                  WHERE event_id=%s AND settled_token=%s AND settled_revision=%s AND settled_worker_id=%s''',
                  (lease.event.event_id,lease.token,lease.revision,self.worker_id)).fetchall()
                if prior:
                    require(len(prior)==1 and prior[0][1]==outcome.payload,'OUTBOX_REPLAY_CONFLICT')
                    # Return original settlement even if a later attempt reclaimed a retry.
                    saved=self.connection.execute('SELECT '+STATE_COLUMNS.replace('v.','')+' FROM whattodo.creation_delivery_revision WHERE event_id=%s AND revision=%s',
                        (lease.event.event_id,prior[0][0])).fetchone()
                    return self._snapshot(row[:8]+saved)
                self._live(row,lease,now)
                require(outcome.retry_at is None or outcome.retry_at>=now,'OUTBOX_RETRY_TIME')
                return self._append(row,state='READY' if outcome.kind=='RETRY' else outcome.kind,now=now,
                                    attempt=lease.attempt,outcome=outcome,settled=lease)
        except Error as exc:raise OutboxError('OUTBOX_STORAGE_RETRY' if exc.sqlstate=='40001' else 'OUTBOX_STORAGE_FAILED') from None
