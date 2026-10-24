"""Authenticated full-queue query, durable initial-request replay and paging."""
from datetime import timedelta
from hashlib import sha256
from uuid import uuid4

from src.adapters.postgres_migrations import schema_checked_transaction
from src.adapters.postgres_review_queue import PostgresReviewQueueStore
from src.adapters.postgres_review_sources import PostgresReviewSources
from src.application.evidence_storage import EvidenceError
from src.application.definitions import canonical
from src.application.migrations import MigrationError
from src.application.ports import PortResult,RequestContext
from src.application.review_queue import admit_review_queue_query,make_review_queue_snapshot
from src.application.task_resolution import user
from src.application.task_storage import TaskStorageError
from src.application.transactions import TransactionError,require


class PostgresReviewQueueService:
    def __init__(self,connection,codec,plan,*,application_version,clock,cursor_key,source_scopes=(),definitions=None,
                 snapshot_lifetime=timedelta(hours=24)):
        require(isinstance(snapshot_lifetime,timedelta) and timedelta(seconds=1)<=snapshot_lifetime<=timedelta(days=7),
            'REVIEW_QUEUE_SNAPSHOT_LIFETIME')
        self.connection=connection;self.codec=codec;self.plan=plan;self.application_version=application_version
        self.clock=clock;self.lifetime=snapshot_lifetime
        self.store=PostgresReviewQueueStore(connection,clock=clock,cursor_key=cursor_key)
        self.sources=PostgresReviewSources(connection,codec,plan,application_version=application_version,clock=clock,
            source_scopes=source_scopes,cursor_key=cursor_key,definitions=definitions)

    def _transaction(self,write=False):
        return schema_checked_transaction(self.connection,self.plan,application_version=self.application_version,read_only=not write)

    def _page(self,header,query,index,caller,scope):
        page=self.store.page_in_transaction(header,query,index=index,caller=caller,scope_hash=scope)
        wire=self.codec.admit('review-queue-page',canonical(page).encode())
        require(wire.status=='SUPPORTED_SHAPE','REVIEW_QUEUE_PAGE_SHAPE_UNSUPPORTED')
        return page

    def query(self,raw,context,*,caller):
        require(isinstance(context,RequestContext),'REVIEW_QUEUE_CONTEXT_REQUIRED')
        attempted_capture=False
        try:
            user(caller);query=admit_review_queue_query(self.codec,raw)
            from psycopg import Error,OperationalError
            scope=self.sources.scope_hash
            if query.cursor is not None:
                key,index=self.store.signer.decode(query.cursor,principal_id=caller.principal_id,query_hash=query.fingerprint)
                with self._transaction():
                    self.sources.validate_scope()
                    header=self.store.get_in_transaction(key,query,caller=caller,scope_hash=scope)
                    page=self._page(header,query,index,caller,scope)
            else:
                with self._transaction(True):
                    self.sources.validate_scope()
                    # Request ownership is independent of command or canonical
                    # store mutation. Concurrent captures never create two
                    # different membership sets for one original request.
                    lock=int.from_bytes(sha256((caller.principal_id+'\0'+context.request_id).encode()).digest()[:8],'big',signed=True)
                    require(self.connection.execute('SELECT pg_try_advisory_xact_lock(%s)',(lock,)).fetchone()[0],
                        'REVIEW_QUEUE_CAPTURE_BUSY')
                    header=self.store.by_request_in_transaction(context.request_id,query,caller=caller,scope_hash=scope)
                    if header is None:
                        items,blockers=self.sources.collect_in_transaction(caller)
                        epoch=self.connection.execute('SELECT revision,last_transaction_ref FROM whattodo.store_epoch WHERE singleton=TRUE').fetchone()
                        require(epoch is not None,'REVIEW_QUEUE_EPOCH_UNAVAILABLE');now=self.clock.now()
                        snapshot=make_review_queue_snapshot(query,items,snapshot_id='review-'+uuid4().hex,principal_id=caller.principal_id,
                            request_id=context.request_id,scope_hash=scope,store_revision=epoch[0],last_transaction_ref=epoch[1],
                            observed_at=now,expires_at=now+self.lifetime,coverage_blockers=blockers)
                        attempted_capture=True
                        header=self.store.append_in_transaction(snapshot,caller=caller)
                    page=self._page(header,query,0,caller,scope)
            return PortResult('SUCCESS','REVIEW_QUEUE_PAGE',context.correlation_ref,page)
        except (TransactionError,TaskStorageError,EvidenceError) as exc:
            code=str(exc)
            status='RETRYABLE' if code=='REVIEW_QUEUE_CAPTURE_BUSY' else ('CONFLICT' if code in
                ('REVIEW_QUEUE_SNAPSHOT_SCOPE_CONFLICT','REVIEW_QUEUE_SNAPSHOT_EXPIRED','REVIEW_QUEUE_CURSOR_SCOPE_CONFLICT') else 'PERMANENT')
            return PortResult(status,code,context.correlation_ref)
        except MigrationError as exc:
            return PortResult('RETRYABLE' if str(exc) in ('MIGRATION_BUSY','MIGRATION_METADATA_UNREADABLE') else 'PERMANENT',
                'REVIEW_QUEUE_SCHEMA_UNAVAILABLE',context.correlation_ref)
        except ImportError:return PortResult('PERMANENT','TRANSACTION_DRIVER_UNAVAILABLE',context.correlation_ref)
        except Exception as exc:
            import importlib.util
            if importlib.util.find_spec('psycopg') is not None:
                from psycopg import Error,OperationalError,InterfaceError
                if isinstance(exc,Error):
                    uncertain=attempted_capture and isinstance(exc,(OperationalError,InterfaceError))
                    status='UNKNOWN' if uncertain else ('RETRYABLE' if isinstance(exc,(OperationalError,InterfaceError))
                        or getattr(exc,'sqlstate',None) in ('23505','40001','40P01','55P03') else 'PERMANENT')
                    return PortResult(status,'REVIEW_QUEUE_CAPTURE_UNKNOWN' if uncertain else 'REVIEW_QUEUE_DATABASE_UNAVAILABLE',context.correlation_ref)
            return PortResult('PERMANENT','REVIEW_QUEUE_INTEGRITY_FAILED',context.correlation_ref)
