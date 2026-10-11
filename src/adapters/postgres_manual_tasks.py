"""Manual create handler with durable pending facts and original creation replay."""
import json
from hashlib import sha256

from src.adapters.postgres_authorization import PostgresCommandService
from src.adapters.postgres_evidence import PostgresEvidenceRepository
from src.adapters.postgres_migrations import schema_checked_transaction
from src.adapters.postgres_tasks import PostgresTaskRepository
from src.adapters.postgres_transactions import PostgresTransactionCoordinator
from src.application.command_ledger import validate_caller
from src.application.command_validation import admit_command
from src.application.definitions import DefinitionError
from src.application.evidence_storage import EvidenceError
from src.application.manual_tasks import (ManualCreationOutcome,ResolvedManualIntent,manual_command,prepare_manual_task)
from src.application.migrations import MigrationError
from src.application.ports import AggregateKey,CommitRequest,PortResult,RecordWrite,RequestContext
from src.application.task_storage import TaskStorageError
from src.application.transactions import TransactionError,require


class PostgresManualTaskHandler:
    def __init__(self,connection,codec,plan,*,application_version,clock,definitions=None,
                 intents=(),grants=(),source_scopes=()):
        require(isinstance(intents,tuple) and all(isinstance(i,ResolvedManualIntent) for i in intents)
            and len({i.command_fingerprint for i in intents})==len(intents),'MANUAL_TRUSTED_INTENT_REGISTRY')
        self.connection=connection;self.codec=codec;self.plan=plan
        self.application_version=application_version;self.clock=clock;self.definitions=definitions
        self._intents={i.command_fingerprint:i for i in intents};self._grants=grants;self._scopes=source_scopes
        self._evidence=PostgresEvidenceRepository(connection,codec,plan,
            application_version=application_version,clock=clock,scopes=source_scopes)
        self._reader=PostgresTaskRepository(connection,codec,plan,application_version=application_version,clock=clock)

    def _source(self,ref):
        source=self._evidence.get_source(ref)
        require(source is not None and source.source.source_type=='USER','MANUAL_USER_SOURCE_REQUIRED')
        return source.source

    def _default_approvals(self,intent):
        with schema_checked_transaction(self.connection,self.plan,application_version=self.application_version):
            for use in intent.default_uses:
                row=self.connection.execute('SELECT origin,source_record_ref FROM whattodo.authority_record WHERE authority_ref=%s',
                    (use.acceptance_ref,)).fetchone()
                require(row==('USER_COMMAND',use.source_ref),'MANUAL_DEFAULT_ACCEPTANCE_REQUIRED')
        for use in intent.default_uses:self._source(use.source_ref)

    def _request(self,command,context,expected_store_revision,audit_id,record,source):
        return CommitRequest(context,command.principal_id,expected_store_revision,
            (RecordWrite(AggregateKey('TASK',record.task_id),None,record.raw_bytes.decode('utf-8')),),audit_id,source)

    def _persist_pending(self,command,intent,draft):
        # Frozen Candidate fields cannot carry unresolved domain/profile/default
        # facts. Preserve the entire interpretation in its own immutable owner.
        key='manual-pending-'+sha256(json.dumps([command.principal_id,command.command_id,intent.fingerprint]).encode()).hexdigest()
        raw=draft.proposal_json.encode('utf-8');require(len(raw)<=1048576,'MANUAL_PENDING_SIZE_LIMIT')
        expected=(command.command_id,command.principal_id,intent.source_ref,intent.fingerprint,
            command.fingerprint,command.changes[0].task_id,sha256(raw).hexdigest(),raw)
        with schema_checked_transaction(self.connection,self.plan,application_version=self.application_version,read_only=False):
            old=self.connection.execute('''SELECT command_id,principal_id,source_record_ref,intent_hash,command_hash,
                desired_task_id,proposal_hash,proposal_bytes FROM whattodo.manual_creation_pending WHERE pending_id=%s''',(key,)).fetchone()
            if old is None:
                self.connection.execute('INSERT INTO whattodo.manual_creation_pending VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)',
                    (key,*expected,self.clock.now()))
            else:require(old[:-1]+(bytes(old[-1]),)==expected,'MANUAL_PENDING_CONTENT_CONFLICT')
        return key

    def get_pending(self,pending_id,context,*,caller):
        require(isinstance(context,RequestContext),'MANUAL_REQUEST_CONTEXT_REQUIRED')
        try:
            validate_caller(caller);require(caller.origin=='USER_COMMAND','UNTRUSTED_CALLER')
            with schema_checked_transaction(self.connection,self.plan,application_version=self.application_version):
                row=self.connection.execute('SELECT principal_id,source_record_ref,proposal_hash,proposal_bytes FROM whattodo.manual_creation_pending WHERE pending_id=%s',
                    (pending_id,)).fetchone()
                if row is None:return PortResult('UNKNOWN','PENDING_NOT_OBSERVED',context.correlation_ref)
                require(row[0]==caller.principal_id,'CALLER_SCOPE_MISMATCH')
                raw=bytes(row[3]);require(sha256(raw).hexdigest()==row[2],'MANUAL_PENDING_HISTORY_INVALID')
                proposal=json.loads(raw)
                require(isinstance(proposal.get('missing_fields'),list) and proposal['missing_fields'] and
                    all(isinstance(p,str) for p in proposal['missing_fields']),'MANUAL_PENDING_HISTORY_INVALID')
            self._source(row[1])
            return PortResult('SUCCESS','PENDING_DETAILS',context.correlation_ref,
                ManualCreationOutcome('PENDING',None,None,None,pending_id,tuple(proposal['missing_fields']),raw.decode('utf-8')))
        except (TransactionError,EvidenceError) as exc:return PortResult('PERMANENT',str(exc),context.correlation_ref)
        except MigrationError:return PortResult('RETRYABLE','MANUAL_SCHEMA_UNAVAILABLE',context.correlation_ref)
        except ImportError:return PortResult('PERMANENT','TRANSACTION_DRIVER_UNAVAILABLE',context.correlation_ref)
        except Exception:return PortResult('RETRYABLE','MANUAL_STORAGE_UNAVAILABLE',context.correlation_ref)

    def _replay_request(self,command,context,expected_store_revision,audit_id):
        with schema_checked_transaction(self.connection,self.plan,application_version=self.application_version):
            row=self.connection.execute('''SELECT c.expected_store_revision,c.audit_id,e.source_record_ref,a.resolved_scope
                FROM whattodo.command_transaction c JOIN whattodo.audit_entry e USING(request_id,audit_id)
                JOIN whattodo.authority_record a ON c.authority_ref=a.authority_ref WHERE c.request_id=%s''',
                (command.command_id,)).fetchone()
            require(row is not None and row[:2]==(expected_store_revision,audit_id),'REQUEST_ID_CONTENT_CONFLICT')
            annotation=row[3].get('authorization',{})
            proofs=annotation.get('creation_provenance',[])
            require(annotation.get('command_fingerprint')==command.fingerprint and len(proofs)==1 and
                proofs[0]['task_id']==command.changes[0].task_id and proofs[0]['details'].get('kind')=='MANUAL_CREATION',
                'MANUAL_REPLAY_SCOPE_CONFLICT')
            record=self._reader._get_in_transaction(command.changes[0].task_id,1)
            require(record is not None,'MANUAL_CREATION_HISTORY_UNAVAILABLE')
        return self._request(command,context,expected_store_revision,audit_id,record,row[2])

    def create(self,raw,context,*,expected_store_revision,audit_id,caller):
        require(isinstance(context,RequestContext),'MANUAL_REQUEST_CONTEXT_REQUIRED')
        correlation=context.correlation_ref;database_error=();transport_error=()
        try:
            command=admit_command(self.codec,raw).command;manual_command(command)
            validate_caller(caller,principal_id=command.principal_id)
            require(caller.origin=='USER_COMMAND' and context.request_id==command.command_id,'UNTRUSTED_CALLER')
            from psycopg import Error as database_error,OperationalError as transport_error
            coordinator=PostgresTransactionCoordinator(self.connection,self.codec,self.plan,
                application_version=self.application_version,clock=self.clock)
            prior=coordinator.lookup_commit(context,caller=caller)
            if prior.status=='SUCCESS':
                request=self._replay_request(command,context,expected_store_revision,audit_id)
                service=PostgresCommandService(self.connection,self.codec,self.plan,
                    application_version=self.application_version,clock=self.clock)
            else:
                if prior.status!='UNKNOWN':return prior
                intent=self._intents.get(command.fingerprint)
                require(intent is not None,'UNREGISTERED_MANUAL_INTENT')
                require(intent.source_observed_at<=self.clock.now(),'MANUAL_FUTURE_SOURCE_TIME')
                source=self._source(intent.source_ref);self._default_approvals(intent)
                require(self.definitions is not None,'MANUAL_DEFINITION_READER_REQUIRED')
                draft=prepare_manual_task(self.codec,command,intent,self.definitions)
                if not draft.ready:
                    outcome=ManualCreationOutcome('PENDING',None,None,None,
                        self._persist_pending(command,intent,draft),draft.missing_fields,draft.proposal_json)
                    return PortResult('SUCCESS','PENDING_DETAILS',correlation,outcome)
                request=self._request(command,context,expected_store_revision,audit_id,draft.after,intent.source_ref)
                service=PostgresCommandService(self.connection,self.codec,self.plan,application_version=self.application_version,
                    clock=self.clock,grants=self._grants,seeds=(draft.seed,),bindings=((draft.seed.task_id,draft.bindings),),
                    source_scopes=self._scopes,creation_provenance=(draft.provenance,),prepared_estimates=draft.prepared_estimates)
            result=service.commit(raw,request,caller=caller)
            if result.status!='SUCCESS':return result
            return PortResult('SUCCESS',result.code,correlation,
                ManualCreationOutcome('CREATED',command.changes[0].task_id,result.value.request_id,result.value))
        except TransactionError as exc:
            code=str(exc);status='CONFLICT' if code in ('REQUEST_ID_CONTENT_CONFLICT','MANUAL_REPLAY_SCOPE_CONFLICT','MANUAL_PENDING_CONTENT_CONFLICT') else 'PERMANENT'
            return PortResult(status,code,correlation)
        except (DefinitionError,EvidenceError,TaskStorageError) as exc:
            code=str(exc);return PortResult('RETRYABLE' if code=='EVIDENCE_IMPORT_BUSY' else 'PERMANENT',code,correlation)
        except MigrationError as exc:
            return PortResult('RETRYABLE' if str(exc) in ('MIGRATION_BUSY','MIGRATION_METADATA_UNREADABLE') else 'PERMANENT',
                'MANUAL_SCHEMA_UNAVAILABLE',correlation)
        except ImportError:return PortResult('PERMANENT','TRANSACTION_DRIVER_UNAVAILABLE',correlation)
        except database_error as exc:
            if isinstance(exc,transport_error) or getattr(exc,'sqlstate',None) in ('55P03','40001','40P01'):
                return PortResult('RETRYABLE','MANUAL_STORAGE_UNAVAILABLE',correlation)
            return PortResult('PERMANENT','MANUAL_DATABASE_REJECTED',correlation)
        except Exception:return PortResult('PERMANENT','MANUAL_CREATION_INVALID',correlation)
