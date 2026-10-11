"""User-confirmed lifecycle handlers over the existing exact-command service."""
from src.adapters.postgres_authorization import PostgresCommandService
from src.adapters.postgres_evidence import PostgresEvidenceRepository
from src.adapters.postgres_migrations import schema_checked_transaction
from src.adapters.postgres_tasks import PostgresTaskRepository
from src.adapters.postgres_transactions import PostgresTransactionCoordinator
from src.application.command_ledger import validate_caller
from src.application.evidence_storage import EvidenceError
from src.application.migrations import MigrationError
from src.application.ports import AggregateKey,CommitRequest,RecordWrite,RequestContext,PortResult
from src.application.task_lifecycle import admit_lifecycle_command,prepare_lifecycle_task
from src.application.task_storage import TaskStorageError
from src.application.transactions import TransactionError,require
from src.domain.authorization import AuthorityGrant


class PostgresLifecycleHandler:
    def __init__(self,connection,codec,plan,*,application_version,clock,grants=(),source_scopes=()):
        require(isinstance(grants,tuple) and all(isinstance(g,AuthorityGrant) for g in grants)
            and len({g.grant_id for g in grants})==len(grants),'LIFECYCLE_TRUSTED_GRANT_REGISTRY')
        self.connection=connection;self.codec=codec;self.plan=plan;self.application_version=application_version;self.clock=clock
        self._grants={g.grant_id:g for g in grants};self._scopes=source_scopes
        self._reader=PostgresTaskRepository(connection,codec,plan,application_version=application_version,clock=clock)
        self._evidence=PostgresEvidenceRepository(connection,codec,plan,application_version=application_version,clock=clock,scopes=source_scopes)

    def complete(self,raw,context,*,expected_store_revision,audit_id,caller):
        return self._execute(raw,context,operation='COMPLETE',expected_store_revision=expected_store_revision,audit_id=audit_id,caller=caller)

    def cancel(self,raw,context,*,expected_store_revision,audit_id,caller):
        return self._execute(raw,context,operation='CANCEL',expected_store_revision=expected_store_revision,audit_id=audit_id,caller=caller)

    def _request(self,command,context,epoch,audit,record,source):
        return CommitRequest(context,command.principal_id,epoch,
            (RecordWrite(AggregateKey('TASK',record.task_id),command.changes[0].expected_revision,record.raw_bytes.decode()),),audit,source)

    def _execute(self,raw,context,*,operation,expected_store_revision,audit_id,caller):
        require(isinstance(context,RequestContext),'TYPED_REQUEST_CONTEXT_REQUIRED')
        correlation=context.correlation_ref;database_error=();transport_error=()
        try:
            admitted=admit_lifecycle_command(self.codec,raw,operation);command=admitted.command;c=command.changes[0]
            validate_caller(caller,principal_id=command.principal_id)
            require(caller.origin=='USER_COMMAND' and context.request_id==command.command_id,'UNTRUSTED_CALLER')
            from psycopg import Error as database_error,OperationalError as transport_error
            coordinator=PostgresTransactionCoordinator(self.connection,self.codec,self.plan,application_version=self.application_version,clock=self.clock)
            prior=coordinator.lookup_commit(context,caller=caller)
            if prior.status=='SUCCESS':
                with schema_checked_transaction(self.connection,self.plan,application_version=self.application_version):
                    row=self.connection.execute('''SELECT a.resolved_scope,e.source_record_ref FROM whattodo.command_transaction t
                        JOIN whattodo.authority_record a ON a.authority_ref=t.authority_ref JOIN whattodo.audit_entry e ON e.audit_id=t.audit_id
                        WHERE t.request_id=%s''',(context.request_id,)).fetchone()
                    annotation=row[0].get('authorization') if row else None
                    require(annotation is not None and annotation.get('command_fingerprint')==command.fingerprint,'LIFECYCLE_REPLAY_SCOPE_CONFLICT')
                    record=self._reader._get_in_transaction(c.task_id,c.expected_revision+1)
                    require(record is not None,'LIFECYCLE_HISTORY_UNAVAILABLE')
                    request=self._request(command,context,expected_store_revision,audit_id,record,row[1])
                return coordinator.commit(request,caller=caller,permit_ref='REPLAY_ONLY')
            if prior.status!='UNKNOWN':return prior
            grant=self._grants.get(command.authority_ref);require(grant is not None,'UNREGISTERED_AUTHORITY')
            source=self._evidence.get_source(grant.evidence_ref)
            require(source is not None and source.source.source_type=='USER','LIFECYCLE_USER_CONFIRMATION_REQUIRED')
            require(source.source.captured_at<=self.clock.now(),'LIFECYCLE_CONFIRMATION_TIME_REQUIRED')
            service=PostgresCommandService(self.connection,self.codec,self.plan,application_version=self.application_version,
                clock=self.clock,grants=(grant,),source_scopes=self._scopes)
            with schema_checked_transaction(self.connection,self.plan,application_version=self.application_version):
                require(self.connection.execute('SELECT revision FROM whattodo.store_epoch WHERE singleton=TRUE').fetchone()
                    ==(expected_store_revision,),'STALE_STORE_REVISION')
                service._grant(grant)
                before=self._reader._get_in_transaction(c.task_id)
                prepared=prepare_lifecycle_task(self.codec,admitted,grant,before,operation=operation,caller=caller,
                    source_observed_at=source.source.captured_at,now=self.clock.now())
                request=self._request(command,context,expected_store_revision,audit_id,prepared.record,grant.evidence_ref)
            return PostgresCommandService(self.connection,self.codec,self.plan,application_version=self.application_version,
                clock=self.clock,grants=(grant,),source_scopes=self._scopes,prepared_estimates=prepared.estimates).commit(raw,request,caller=caller)
        except TransactionError as exc:
            code=str(exc);status='CONFLICT' if code in ('STALE_STORE_REVISION','STALE_STATE_VERSION','LIFECYCLE_REPLAY_SCOPE_CONFLICT',
                'LIFECYCLE_REACTIVATION_REQUIRED') else 'PERMANENT'
            return PortResult(status,code,correlation)
        except (TaskStorageError,EvidenceError) as exc:return PortResult('PERMANENT',str(exc),correlation)
        except MigrationError as exc:
            return PortResult('RETRYABLE','TRANSACTION_SCHEMA_UNAVAILABLE',correlation) if str(exc) in (
                'MIGRATION_BUSY','MIGRATION_METADATA_UNREADABLE') else PortResult('PERMANENT','TRANSACTION_SCHEMA_INCOMPATIBLE',correlation)
        except ImportError:return PortResult('PERMANENT','TRANSACTION_DRIVER_UNAVAILABLE',correlation)
        except database_error as exc:
            if isinstance(exc,transport_error) or getattr(exc,'sqlstate',None) in ('55P03','40001','40P01'):
                return PortResult('RETRYABLE','LIFECYCLE_REFERENCES_UNAVAILABLE',correlation)
            return PortResult('PERMANENT','LIFECYCLE_REFERENCE_DATABASE_REJECTED',correlation)
        except Exception:return PortResult('PERMANENT','LIFECYCLE_VALIDATION_FAILED',correlation)
