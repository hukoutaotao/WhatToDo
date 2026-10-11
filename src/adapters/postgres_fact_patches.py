"""Opt-in exact user fact edits, with atomic support facts and owned replay."""
from datetime import timedelta
from hashlib import sha256

from src.adapters.postgres_evidence import PostgresEvidenceRepository
from src.adapters.postgres_migrations import schema_checked_transaction
from src.adapters.postgres_tasks import PostgresTaskRepository
from src.adapters.postgres_transactions import PostgresTransactionCoordinator
from src.application.command_ledger import validate_caller
from src.application.definitions import DefinitionKey
from src.application.fact_patches import FactPatchGrant,admit_fact_patch,prepare_fact_patch
from src.application.migrations import MigrationError
from src.application.ports import AggregateKey,CommitRequest,PortResult,RecordWrite,RequestContext,TransactionPermit
from src.application.task_storage import TaskStorageBindings,TaskStorageError,validate_bindings
from src.application.transactions import TransactionError,require


def register_fact_patch_grant(connection,grant,plan,*,application_version):
    """Trusted resolver/setup only; JSON transport cannot register authority."""
    require(isinstance(grant,FactPatchGrant),'FACT_PATCH_TYPED_GRANT')
    from psycopg.types.json import Jsonb
    p=grant.patch
    expected=(p.principal_id,'USER_COMMAND',grant.evidence_ref,p.fingerprint,grant.as_record(),grant.issued_at,grant.expires_at)
    with schema_checked_transaction(connection,plan,application_version=application_version,read_only=False):
        row=connection.execute('''SELECT principal_id,origin,source_record_ref,resolved_scope_hash,
            resolved_scope,issued_at,expires_at FROM whattodo.authority_record WHERE authority_ref=%s''',
            (p.authority_ref,)).fetchone()
        if row is not None:require(row==expected,'AUTHORITY_GRANT_IMMUTABLE_CONFLICT');return
        connection.execute('INSERT INTO whattodo.authority_record VALUES(%s,%s,%s,%s,%s,%s,%s,%s)',
            (p.authority_ref,*expected[:4],Jsonb(expected[4]),*expected[5:]))


class PostgresFactPatchHandler:
    def __init__(self,connection,codec,plan,*,application_version,clock,grants=(),source_scopes=()):
        require(isinstance(grants,tuple) and all(isinstance(g,FactPatchGrant) for g in grants)
            and len({g.patch.authority_ref for g in grants})==len(grants),'FACT_PATCH_TRUSTED_GRANT_REGISTRY')
        self.connection=connection;self.codec=codec;self.plan=plan;self.application_version=application_version;self.clock=clock
        self._grants={g.patch.authority_ref:g for g in grants};self._scopes=source_scopes
        self._evidence=PostgresEvidenceRepository(connection,codec,plan,application_version=application_version,
            clock=clock,scopes=source_scopes)
        self._reader=PostgresTaskRepository(connection,codec,plan,application_version=application_version,clock=clock)

    def _request(self,patch,context,epoch,audit,record,source):
        return CommitRequest(context,patch.principal_id,epoch,
            (RecordWrite(AggregateKey('TASK',patch.task_id),patch.expected_revision,record.raw_bytes.decode()),),audit,source)

    def _binding(self,record):
        row=self.connection.execute('''SELECT p.profile_ref,t.notice_task_revision FROM whattodo.task_payload_revision p
            JOIN whattodo.task_revision t ON t.task_id=p.task_id AND t.revision=p.task_revision
            WHERE p.task_id=%s AND p.task_revision=%s''',(record.task_id,record.revision)).fetchone()
        require(row is not None,'FACT_PATCH_HISTORY_UNAVAILABLE')
        profile=None
        if row[0] is not None:
            key=self.connection.execute('SELECT kind,id,version FROM whattodo.definition_cache WHERE configuration_ref=%s',
                (row[0],)).fetchone()
            require(key is not None,'FACT_PATCH_HISTORY_UNAVAILABLE');profile=DefinitionKey(*key)
        # The delivered notice refers to the original expiry revision, not the
        # most recent fact edit. Repeated edits must keep that exact backlink.
        return TaskStorageBindings(profile,row[1])

    def patch(self,raw,context,*,expected_store_revision,audit_id,caller):
        require(isinstance(context,RequestContext),'TYPED_REQUEST_CONTEXT_REQUIRED')
        correlation=context.correlation_ref;database_error=();transport_error=()
        try:
            patch=admit_fact_patch(self.codec,raw)
            validate_caller(caller,principal_id=patch.principal_id)
            require(caller.origin=='USER_COMMAND' and context.request_id==patch.command_id,'UNTRUSTED_CALLER')
            from psycopg import Error as database_error,OperationalError as transport_error
            coordinator=PostgresTransactionCoordinator(self.connection,self.codec,self.plan,
                application_version=self.application_version,clock=self.clock)
            prior=coordinator.lookup_commit(context,caller=caller)
            if prior.status=='SUCCESS':
                with schema_checked_transaction(self.connection,self.plan,application_version=self.application_version):
                    row=self.connection.execute('''SELECT a.resolved_scope,e.source_record_ref FROM whattodo.command_transaction c
                        JOIN whattodo.authority_record a ON a.authority_ref=c.authority_ref
                        JOIN whattodo.audit_entry e ON e.audit_id=c.audit_id WHERE c.request_id=%s''',
                        (context.request_id,)).fetchone()
                    annotation=row[0].get('authorization') if row else None
                    require(annotation is not None and annotation.get('contract')=='task-fact-patch'
                        and annotation.get('command_fingerprint')==patch.fingerprint,'FACT_PATCH_REPLAY_SCOPE_CONFLICT')
                    record=self._reader._get_in_transaction(patch.task_id,patch.expected_revision+1)
                    require(record is not None,'FACT_PATCH_HISTORY_UNAVAILABLE')
                    request=self._request(patch,context,expected_store_revision,audit_id,record,row[1])
                return coordinator.commit(request,caller=caller,permit_ref='REPLAY_ONLY')
            if prior.status!='UNKNOWN':return prior
            grant=self._grants.get(patch.authority_ref);require(grant is not None,'UNREGISTERED_AUTHORITY')
            source=self._evidence.get_source(grant.evidence_ref)
            require(source is not None and source.source.source_type=='USER','FACT_PATCH_USER_SOURCE_REQUIRED')
            with schema_checked_transaction(self.connection,self.plan,application_version=self.application_version):
                require(self.connection.execute('SELECT revision FROM whattodo.store_epoch WHERE singleton=TRUE').fetchone()
                    ==(expected_store_revision,),'STALE_STORE_REVISION')
                expected=(patch.principal_id,'USER_COMMAND',grant.evidence_ref,grant.patch.fingerprint,
                    grant.as_record(),grant.issued_at,grant.expires_at)
                require(self.connection.execute('''SELECT principal_id,origin,source_record_ref,resolved_scope_hash,
                    resolved_scope,issued_at,expires_at FROM whattodo.authority_record WHERE authority_ref=%s''',
                    (patch.authority_ref,)).fetchone()==expected,'AUTHORITY_REGISTERED_SCOPE_MISMATCH')
                scope=self.connection.execute('''SELECT s.provider,s.scope_ref,a.account_ref FROM whattodo.source_record r
                    JOIN whattodo.source_identity s USING(source_id) JOIN whattodo.source_scope a USING(provider,scope_ref)
                    WHERE r.record_id=%s''',(grant.evidence_ref,)).fetchone()
                require(any((s.provider,s.scope_ref,s.account_ref)==scope for s in self._scopes),'AUTHORITY_SOURCE_SCOPE_REQUIRED')
                before=self._reader._get_in_transaction(patch.task_id)
                prepared=prepare_fact_patch(self.codec,patch,grant,before,now=self.clock.now())
                binding=self._binding(before);validate_bindings(prepared.record,binding)
                self._reader._check_references(prepared.record,binding,
                    resolved_estimates=tuple(o.row for o in prepared.estimates),
                    resolved_dues=tuple((d.due_id,*d.row) for d in prepared.dues))
                request=self._request(patch,context,expected_store_revision,audit_id,prepared.record,grant.evidence_ref)
                now=self.clock.now();expiry=min(now+timedelta(minutes=5),grant.expires_at) if grant.expires_at else now+timedelta(minutes=5)
                permit=TransactionPermit('permit-'+sha256((patch.fingerprint+request.fingerprint).encode()).hexdigest(),
                    caller.principal_id,caller.origin,request.fingerprint,now,expiry)
                annotation=dict(contract='task-fact-patch',command_fingerprint=patch.fingerprint,
                    command=patch.as_record(),command_wire_hash=sha256(raw).hexdigest(),grant_ref=patch.authority_ref)
            return PostgresTransactionCoordinator(self.connection,self.codec,self.plan,
                application_version=self.application_version,clock=self.clock,permits=(permit,),
                bindings=((patch.task_id,binding),),authorization_context=annotation,
                prepared_estimates=prepared.estimates,prepared_dues=prepared.dues).commit(
                    request,caller=caller,permit_ref=permit.permit_ref)
        except TransactionError as exc:
            code=str(exc);status='CONFLICT' if code in ('STALE_STORE_REVISION','STALE_STATE_VERSION',
                'FACT_PATCH_REPLAY_SCOPE_CONFLICT') else 'PERMANENT'
            return PortResult(status,code,correlation)
        except TaskStorageError as exc:return PortResult('PERMANENT',str(exc),correlation)
        except MigrationError as exc:
            return PortResult('RETRYABLE','TRANSACTION_SCHEMA_UNAVAILABLE',correlation) if str(exc) in (
                'MIGRATION_BUSY','MIGRATION_METADATA_UNREADABLE') else PortResult('PERMANENT','TRANSACTION_SCHEMA_INCOMPATIBLE',correlation)
        except ImportError:return PortResult('PERMANENT','TRANSACTION_DRIVER_UNAVAILABLE',correlation)
        except database_error as exc:
            if isinstance(exc,transport_error) or getattr(exc,'sqlstate',None) in ('55P03','40001','40P01'):
                return PortResult('RETRYABLE','FACT_PATCH_REFERENCES_UNAVAILABLE',correlation)
            return PortResult('PERMANENT','FACT_PATCH_REFERENCE_DATABASE_REJECTED',correlation)
        except Exception:return PortResult('PERMANENT','FACT_PATCH_VALIDATION_FAILED',correlation)
