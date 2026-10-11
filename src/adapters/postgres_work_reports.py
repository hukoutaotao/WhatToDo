"""Authorized work reporting with independently audited actual records and Task CAS."""
from datetime import timedelta
from hashlib import sha256
from dataclasses import dataclass,field

from src.adapters.postgres_actual_work import PostgresActualWorkRepository
from src.adapters.postgres_evidence import PostgresEvidenceRepository
from src.adapters.postgres_migrations import schema_checked_transaction
from src.adapters.postgres_tasks import PostgresTaskRepository
from src.adapters.postgres_transactions import PostgresTransactionCoordinator
from src.application.command_ledger import validate_caller
from src.application.definitions import DefinitionKey
from src.application.evidence_storage import EvidenceError
from src.application.migrations import MigrationError
from src.application.ports import AggregateKey,CommitRequest,RecordWrite,RequestContext,PortResult,TransactionPermit,CommitReceipt
from src.application.task_storage import TaskStorageBindings,TaskStorageError,validate_bindings
from src.application.transactions import TransactionError,require
from src.application.work_reports import WorkReportGrant,ActualWorkStorageRecord,admit_work_report,prepare_work_report


def register_work_report_grant(connection,grant,plan,*,application_version):
    require(isinstance(grant,WorkReportGrant),'WORK_REPORT_TYPED_GRANT')
    from psycopg.types.json import Jsonb
    r=grant.report;expected=(r.principal_id,'USER_COMMAND',grant.evidence_ref,r.fingerprint,grant.as_record(),grant.issued_at,grant.expires_at)
    with schema_checked_transaction(connection,plan,application_version=application_version,read_only=False):
        row=connection.execute('SELECT principal_id,origin,source_record_ref,resolved_scope_hash,resolved_scope,issued_at,expires_at FROM whattodo.authority_record WHERE authority_ref=%s',
            (r.authority_ref,)).fetchone()
        if row is not None:require(row==expected,'AUTHORITY_GRANT_IMMUTABLE_CONFLICT');return
        connection.execute('INSERT INTO whattodo.authority_record VALUES(%s,%s,%s,%s,%s,%s,%s,%s)',(r.authority_ref,*expected[:4],Jsonb(expected[4]),*expected[5:]))


@dataclass(frozen=True)
class WorkReportOutcome:
    receipt: CommitReceipt
    record: ActualWorkStorageRecord = field(repr=False)


class PostgresWorkReportHandler:
    def __init__(self,connection,codec,plan,*,application_version,clock,grants=(),source_scopes=()):
        require(isinstance(grants,tuple) and all(isinstance(g,WorkReportGrant) for g in grants)
            and len({g.report.authority_ref for g in grants})==len(grants),'WORK_REPORT_TRUSTED_GRANT_REGISTRY')
        self.connection=connection;self.codec=codec;self.plan=plan;self.application_version=application_version;self.clock=clock
        self._grants={g.report.authority_ref:g for g in grants};self._scopes=source_scopes
        self._reader=PostgresTaskRepository(connection,codec,plan,application_version=application_version,clock=clock)
        self._work=PostgresActualWorkRepository(connection,codec,plan,application_version=application_version,clock=clock)
        self._evidence=PostgresEvidenceRepository(connection,codec,plan,application_version=application_version,clock=clock,scopes=source_scopes)

    def _binding(self,record):
        row=self.connection.execute('''SELECT p.profile_ref,t.notice_task_revision FROM whattodo.task_payload_revision p
            JOIN whattodo.task_revision t ON t.task_id=p.task_id AND t.revision=p.task_revision WHERE p.task_id=%s AND p.task_revision=%s''',
            (record.task_id,record.revision)).fetchone();require(row is not None,'WORK_REPORT_HISTORY_UNAVAILABLE')
        profile=None
        if row[0] is not None:
            key=self.connection.execute('SELECT kind,id,version FROM whattodo.definition_cache WHERE configuration_ref=%s',(row[0],)).fetchone()
            require(key is not None,'WORK_REPORT_HISTORY_UNAVAILABLE');profile=DefinitionKey(*key)
        return TaskStorageBindings(profile,row[1])

    def _request(self,report,context,epoch,audit,task,work):
        return CommitRequest(context,report.principal_id,epoch,
            (RecordWrite(AggregateKey('TASK',report.task_id),report.expected_revision,task.raw_bytes.decode()),
            RecordWrite(AggregateKey('WORK_REPORT',report.observation_id),None,work.raw_bytes.decode())),audit,work.as_record()['source_ref'])

    def _replay_record(self,report,context,epoch,audit):
        with schema_checked_transaction(self.connection,self.plan,application_version=self.application_version):
            work=self._work._get_in_transaction(report.observation_id)
            require(work is not None and work.report.fingerprint==report.fingerprint,'WORK_REPORT_REPLAY_SCOPE_CONFLICT')
            task=self._reader._get_in_transaction(report.task_id,report.expected_revision+1)
            require(task is not None,'WORK_REPORT_HISTORY_UNAVAILABLE')
            return work,self._request(report,context,epoch,audit,task,work)

    def report(self,raw,context,*,expected_store_revision,audit_id,caller):
        require(isinstance(context,RequestContext),'TYPED_REQUEST_CONTEXT_REQUIRED')
        correlation=context.correlation_ref;database_error=();transport_error=()
        try:
            report=admit_work_report(self.codec,raw);validate_caller(caller,principal_id=report.principal_id)
            require(caller.origin=='USER_COMMAND' and context.request_id==report.command_id,'UNTRUSTED_CALLER')
            from psycopg import Error as database_error,OperationalError as transport_error
            coordinator=PostgresTransactionCoordinator(self.connection,self.codec,self.plan,application_version=self.application_version,clock=self.clock)
            prior=coordinator.lookup_commit(context,caller=caller)
            if prior.status=='SUCCESS':
                work,request=self._replay_record(report,context,expected_store_revision,audit_id)
                result=coordinator.commit(request,caller=caller,permit_ref='REPLAY_ONLY')
                return PortResult('SUCCESS',result.code,correlation,WorkReportOutcome(result.value,work)) if result.status=='SUCCESS' else result
            if prior.status!='UNKNOWN':return prior
            # Independent observation identity also deduplicates transport IDs.
            # Owned read-only replay returns the original command receipt and
            # never re-verifies U or publishes a new command/Task revision.
            with schema_checked_transaction(self.connection,self.plan,application_version=self.application_version):
                old=self._work._get_in_transaction(report.observation_id)
                if old is not None:
                    require(old.report.principal_id==caller.principal_id,'CALLER_SCOPE_MISMATCH')
                    require(old.report.fact_fingerprint==report.fact_fingerprint,'WORK_REPORT_OBSERVATION_ID_CONFLICT')
                    receipt=coordinator._lookup_in_transaction(old.report.command_id,caller)
                    require(receipt is not None,'WORK_REPORT_HISTORY_UNAVAILABLE')
                    return PortResult('SUCCESS','OBSERVATION_REPLAY',correlation,WorkReportOutcome(receipt,old))
                require(self.connection.execute('SELECT 1 FROM whattodo.effort_observation WHERE observation_id=%s',(report.observation_id,)).fetchone() is None,
                    'WORK_REPORT_LEGACY_OBSERVATION_ID_UNAVAILABLE')
            grant=self._grants.get(report.authority_ref);require(grant is not None,'UNREGISTERED_AUTHORITY')
            source=self._evidence.get_source(grant.evidence_ref)
            require(source is not None and source.source.source_type=='USER','WORK_REPORT_USER_SOURCE_REQUIRED')
            with schema_checked_transaction(self.connection,self.plan,application_version=self.application_version):
                require(self.connection.execute('SELECT revision FROM whattodo.store_epoch WHERE singleton=TRUE').fetchone()==(expected_store_revision,),'STALE_STORE_REVISION')
                require(self.connection.execute('SELECT principal_id,origin,source_record_ref,resolved_scope_hash,resolved_scope,issued_at,expires_at FROM whattodo.authority_record WHERE authority_ref=%s',
                    (report.authority_ref,)).fetchone()==(report.principal_id,'USER_COMMAND',grant.evidence_ref,grant.report.fingerprint,grant.as_record(),grant.issued_at,grant.expires_at),
                    'AUTHORITY_REGISTERED_SCOPE_MISMATCH')
                before=self._reader._get_in_transaction(report.task_id)
                if report.as_record()['stage_id'] is not None:
                    require(self.connection.execute('SELECT task_id FROM whattodo.stage_identity WHERE stage_id=%s',(report.as_record()['stage_id'],)).fetchone()==(report.task_id,),
                        'WORK_REPORT_STAGE_OWNER_REQUIRED')
                prepared=prepare_work_report(self.codec,report,grant,before,caller=caller,previous_total_seconds=self._work._total_in_transaction(report.task_id),
                    source_observed_at=source.source.captured_at,now=self.clock.now())
                binding=self._binding(before);validate_bindings(prepared.task,binding)
                self._reader._check_references(prepared.task,binding,resolved_estimates=tuple(o.row for o in prepared.estimates))
                request=self._request(report,context,expected_store_revision,audit_id,prepared.task,prepared.work)
                now=self.clock.now();end=min(now+timedelta(minutes=5),grant.expires_at) if grant.expires_at else now+timedelta(minutes=5)
                permit=TransactionPermit('permit-'+sha256((report.fingerprint+request.fingerprint).encode()).hexdigest(),caller.principal_id,caller.origin,request.fingerprint,now,end)
                annotation=dict(contract='work-report',command_fingerprint=report.fingerprint,command_wire_hash=sha256(raw).hexdigest(),grant_ref=report.authority_ref,command=report.as_record())
            result=PostgresTransactionCoordinator(self.connection,self.codec,self.plan,application_version=self.application_version,clock=self.clock,
                permits=(permit,),bindings=((report.task_id,binding),),authorization_context=annotation,prepared_estimates=prepared.estimates).commit(request,caller=caller,permit_ref=permit.permit_ref)
            return PortResult('SUCCESS',result.code,correlation,WorkReportOutcome(result.value,prepared.work)) if result.status=='SUCCESS' else result
        except TransactionError as exc:
            code=str(exc);status='CONFLICT' if code in ('STALE_STORE_REVISION','STALE_STATE_VERSION','WORK_REPORT_REPLAY_SCOPE_CONFLICT',
                'WORK_REPORT_OBSERVATION_ID_CONFLICT','WORK_REPORT_CUMULATIVE_BELOW_RECORDED_TOTAL') else 'PERMANENT'
            return PortResult(status,code,correlation)
        except (TaskStorageError,EvidenceError) as exc:return PortResult('PERMANENT',str(exc),correlation)
        except MigrationError as exc:
            return PortResult('RETRYABLE','TRANSACTION_SCHEMA_UNAVAILABLE',correlation) if str(exc) in (
                'MIGRATION_BUSY','MIGRATION_METADATA_UNREADABLE') else PortResult('PERMANENT','TRANSACTION_SCHEMA_INCOMPATIBLE',correlation)
        except ImportError:return PortResult('PERMANENT','TRANSACTION_DRIVER_UNAVAILABLE',correlation)
        except database_error as exc:
            if isinstance(exc,transport_error) or getattr(exc,'sqlstate',None) in ('55P03','40001','40P01'):
                return PortResult('RETRYABLE','WORK_REPORT_REFERENCES_UNAVAILABLE',correlation)
            return PortResult('PERMANENT','WORK_REPORT_REFERENCE_DATABASE_REJECTED',correlation)
        except Exception:return PortResult('PERMANENT','WORK_REPORT_VALIDATION_FAILED',correlation)
