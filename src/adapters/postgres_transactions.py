"""Atomic audited Task publication and durable authenticated command replay.

Only independently injected exact permits authorize a transaction. No network
calls occur inside it; concrete aggregate storage remains in postgres_tasks.
"""
from src.adapters.postgres_migrations import schema_checked_transaction
from src.adapters.postgres_tasks import PostgresTaskRepository
from src.adapters.postgres_actual_work import PostgresActualWorkRepository
from src.application.migrations import MigrationError
from src.application.command_ledger import (receipt_from_row,validate_audit_fingerprint,validate_caller)
from src.application.command_validation import PreparedUserEstimate
from src.application.fact_patches import PreparedDue
from src.domain.task_aggregate import instant
from src.application.ports import CommitRequest, PortResult, RequestContext, TransactionPermit
from src.application.task_storage import TaskStorageError,TaskStorageRecord
from src.application.transactions import (TransactionError, prepare_transaction,
    require, valid_permit)


class PostgresTransactionCoordinator:
    def __init__(self, connection, codec, plan, *, application_version, clock,
                 permits=(), bindings=(), authorization_context=None,prepared_estimates=(),prepared_dues=()):
        require(isinstance(permits, tuple) and all(isinstance(p, TransactionPermit)
            for p in permits) and len({p.permit_ref for p in permits})==len(permits),
            'TRANSACTION_TRUSTED_PERMIT_REGISTRY')
        self.connection=connection
        self.codec=codec
        self.plan=plan
        self.application_version=application_version
        self.clock=clock
        self._permits={p.permit_ref:p for p in permits}
        self._bindings=bindings
        require(isinstance(prepared_estimates,tuple) and
            all(isinstance(o,PreparedUserEstimate) for o in prepared_estimates) and
            len({o.observation_id for o in prepared_estimates})==len(prepared_estimates),
            'TRANSACTION_TRUSTED_PREPARED_ESTIMATES')
        self._prepared_estimates=prepared_estimates
        require(isinstance(prepared_dues,tuple) and all(isinstance(d,PreparedDue) for d in prepared_dues)
            and len({d.due_id for d in prepared_dues})==len(prepared_dues),'TRANSACTION_TRUSTED_PREPARED_DUES')
        self._prepared_dues=prepared_dues
        # Trusted application annotation, never an input approval envelope.
        import json
        require(authorization_context is None or isinstance(authorization_context,dict),
            'TRANSACTION_AUTHORIZATION_CONTEXT')
        self._authorization_json=json.dumps(authorization_context,sort_keys=True,allow_nan=False)
        self._repository=PostgresTaskRepository(connection,codec,plan,
            application_version=application_version,clock=clock,permits=permits)
        self._work_repository=PostgresActualWorkRepository(connection,codec,plan,
            application_version=application_version,clock=clock,permits=permits)

    def commit(self, request, *, caller, permit_ref):
        require(isinstance(request, CommitRequest),'TYPED_TRANSACTION_REQUIRED')
        correlation=request.context.correlation_ref
        phase='PREPARING'
        database_error=()
        transport_error=()
        try:
            validate_caller(caller,principal_id=request.principal_id)
            require(1<=len(request.writes)<=100 and
                sum(len(w.body_json.encode('utf-8')) for w in request.writes)<=8388608,
                'TRANSACTION_SIZE_LIMIT')
            from psycopg import Error as database_error, OperationalError as transport_error
            from psycopg.types.json import Jsonb
            if self.connection.closed:
                return PortResult('RETRYABLE','TRANSACTION_NOT_COMMITTED',correlation)
            with schema_checked_transaction(self.connection,self.plan,
                    application_version=self.application_version,read_only=False):
                phase='READING'
                prior=self._lookup_in_transaction(request.context.request_id,caller)
                if prior is not None:
                    require(prior.request_fingerprint==request.fingerprint,'REQUEST_ID_CONTENT_CONFLICT')
                    return PortResult('SUCCESS','REPLAY',correlation,prior)
                permit=self._permits.get(permit_ref)
                prepared=prepare_transaction(self.codec,request,caller=caller,
                    permit=permit,at=self.clock.now(),bindings=self._bindings)
                phase='STAGING'
                # NOWAIT gives an explicit retryable busy result. Once locked,
                # both the store epoch and all Task versions are stable for CAS.
                epoch=self.connection.execute('SELECT revision FROM whattodo.store_epoch WHERE singleton=TRUE FOR UPDATE NOWAIT').fetchone()
                require(epoch==(request.expected_store_revision,),'STALE_STORE_REVISION')
                require(self.connection.execute('SELECT 1 FROM whattodo.audit_entry WHERE audit_id=%s',
                    (request.audit_id,)).fetchone() is None,'AUDIT_ID_ALREADY_USED')
                previous=[]
                for write in request.writes:
                    old=(self._repository._get_in_transaction(write.key.id) if write.key.kind=='TASK' else
                        self._work_repository._get_in_transaction(write.key.id))
                    require((old.revision if old else None)==write.expected_revision,
                        'STALE_AGGREGATE_REVISION')
                    previous.append(old)
                now=self.clock.now()
                valid_permit(request,caller,permit,now)
                authority=self.connection.execute('''SELECT principal_id,origin,source_record_ref,
                    resolved_scope_hash,issued_at,expires_at FROM whattodo.authority_record
                    WHERE authority_ref=%s''',(permit_ref,)).fetchone()
                expected=(caller.principal_id,caller.origin,request.source_ref,
                    request.fingerprint,permit.issued_at,permit.expires_at)
                import json
                scope=dict(scope_kind='EXACT_TRANSACTION',request_fingerprint=request.fingerprint)
                annotation=json.loads(self._authorization_json)
                if annotation is not None:scope['authorization']=annotation
                if authority is None:
                    self.connection.execute('INSERT INTO whattodo.authority_record VALUES(%s,%s,%s,%s,%s,%s,%s,%s)',
                        (permit_ref,*expected[:4],Jsonb(scope),*expected[4:]))
                else:
                    require(authority==expected,'TRANSACTION_AUTHORITY_REFERENCE_DRIFT')
                    if annotation is not None:
                        require(self.connection.execute('SELECT resolved_scope FROM whattodo.authority_record WHERE authority_ref=%s',
                            (permit_ref,)).fetchone()==(scope,),'TRANSACTION_AUTHORITY_REFERENCE_DRIFT')
                self.connection.execute('INSERT INTO whattodo.command_transaction VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)',
                    (request.context.request_id,request.fingerprint,caller.principal_id,
                    caller.origin,permit_ref,request.expected_store_revision,
                    prepared.receipt.store_revision,request.audit_id,now,Jsonb(prepared.receipt_body)))
                self.connection.execute('INSERT INTO whattodo.audit_entry VALUES(%s,%s,%s,%s,%s)',
                    (request.audit_id,request.context.request_id,request.source_ref,correlation,now))
                for observation in self._prepared_estimates:
                    target=next((w.record for w in prepared.writes if isinstance(w.record,TaskStorageRecord) and w.record.task_id==observation.task_id),None)
                    require(target is not None and caller.origin=='USER_COMMAND' and observation.source_ref==request.source_ref
                        and observation.observed_at<=now,'TRANSACTION_OBSERVATION_SCOPE_MISMATCH')
                    value=target.aggregate.as_record()['effort']
                    estimates=[value['user_remaining']]+[s['user_remaining'] for s in value['stages']]
                    require(any(u is not None and u['observation_id']==observation.observation_id and
                        u['seconds']==observation.seconds and instant(u['observed_at'])==observation.observed_at
                        and observation.observed_at<=instant(u['verified_at'])<=now for u in estimates),
                        'TRANSACTION_OBSERVATION_SCOPE_MISMATCH')
                    root=self.connection.execute('SELECT principal_id,origin,source_record_ref FROM whattodo.authority_record WHERE authority_ref=%s',
                        (observation.authority_ref,)).fetchone()
                    require(root==(caller.principal_id,'USER_COMMAND',request.source_ref),
                        'TRANSACTION_OBSERVATION_SCOPE_MISMATCH')
                    prior=self.connection.execute('''SELECT observation_id,task_id,kind,seconds,
                        observed_at,source_record_ref,authority_ref FROM whattodo.effort_observation WHERE observation_id=%s''',
                        (observation.observation_id,)).fetchone()
                    if prior is None:
                        self.connection.execute('INSERT INTO whattodo.effort_observation VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)',
                            (*observation.row[:5],now,*observation.row[5:],None,request.context.request_id))
                    else:require(prior==observation.row,'TRANSACTION_OBSERVATION_SCOPE_MISMATCH')
                for due in self._prepared_dues:
                    target=next((w.record for w in prepared.writes if isinstance(w.record,TaskStorageRecord) and w.record.task_id==due.task_id),None)
                    require(target is not None and caller.origin=='USER_COMMAND' and due.value.source_ref==request.source_ref,
                        'TRANSACTION_DUE_SCOPE_MISMATCH')
                    deadline=target.aggregate.as_record()['timing']['deadline']
                    require(deadline is not None and deadline['due_ref']==due.due_id and deadline['value']==due.value.as_record(),
                        'TRANSACTION_DUE_SCOPE_MISMATCH')
                    require(self.connection.execute('SELECT principal_id,origin,source_record_ref FROM whattodo.authority_record WHERE authority_ref=%s',
                        (due.authority_ref,)).fetchone()==(caller.principal_id,'USER_COMMAND',request.source_ref),
                        'TRANSACTION_DUE_SCOPE_MISMATCH')
                    prior=self.connection.execute('SELECT input_kind,original_value,source_record_ref,due_at,default_policy_ref FROM whattodo.normalized_due WHERE due_id=%s',
                        (due.due_id,)).fetchone()
                    if prior is None:
                        from datetime import date
                        date_only=due.value.input_kind=='DATE_ONLY'
                        self.connection.execute('INSERT INTO whattodo.normalized_due VALUES(%s,%s,%s,%s,%s,%s,%s,%s)',
                            (due.due_id,*due.row[:4],date.fromisoformat(due.value.original_value) if date_only else None,
                            due.value.default_policy_ref,'Asia/Shanghai' if date_only else None))
                    else:require(prior==due.row,'TRANSACTION_DUE_SCOPE_MISMATCH')
                for write,old in zip(prepared.writes,previous):
                    is_task=isinstance(write.record,TaskStorageRecord)
                    item_id=write.record.task_id if is_task else write.record.observation_id
                    old_value=old.aggregate.as_record() if old is not None and is_task else old.as_record() if old else None
                    new_value=write.record.aggregate.as_record() if is_task else write.record.as_record()
                    self.connection.execute('INSERT INTO whattodo.audit_change VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s)',
                        (write.change_ref,request.audit_id,'TASK' if is_task else 'WORK_REPORT',item_id,
                        old.revision if old else None,write.record.revision,
                        Jsonb(old_value) if old_value is not None else None,
                        Jsonb(new_value),request.context.request_id))
                    if is_task:
                        self._repository._append_in_transaction(write.record,write.bindings,
                            request=request,caller=caller,permit_ref=permit_ref,audit_change_ref=write.change_ref)
                    else:
                        self._work_repository._append_in_transaction(write.record,request=request,caller=caller,
                            permit_ref=permit_ref,audit_change_ref=write.change_ref)
                # The final permit check also covers expiry while staging a batch.
                valid_permit(request,caller,permit,self.clock.now())
                updated=self.connection.execute('UPDATE whattodo.store_epoch SET revision=%s,last_transaction_ref=%s WHERE singleton=TRUE AND revision=%s',
                    (prepared.receipt.store_revision,request.context.request_id,
                    request.expected_store_revision)).rowcount
                require(updated==1,'STALE_STORE_REVISION')
                phase='COMMITTING'
            return PortResult('SUCCESS','COMMITTED',correlation,prepared.receipt)
        except TransactionError as exc:
            code=str(exc)
            status='CONFLICT' if code in ('STALE_STORE_REVISION','STALE_AGGREGATE_REVISION',
                'REQUEST_ID_ALREADY_USED','REQUEST_ID_CONTENT_CONFLICT','AUDIT_ID_ALREADY_USED') else 'PERMANENT'
            return PortResult(status,code,correlation)
        except TaskStorageError as exc:
            code=str(exc)
            status='CONFLICT' if code.startswith('TASK_STORAGE_STALE_') else 'PERMANENT'
            return PortResult(status,code,correlation)
        except MigrationError as exc:
            if str(exc) in ('MIGRATION_BUSY','MIGRATION_METADATA_UNREADABLE'):
                return PortResult('RETRYABLE','TRANSACTION_SCHEMA_UNAVAILABLE',correlation)
            return PortResult('PERMANENT','TRANSACTION_SCHEMA_INCOMPATIBLE',correlation)
        except ImportError:
            return PortResult('PERMANENT','TRANSACTION_DRIVER_UNAVAILABLE',correlation)
        except Exception as exc:
            # Only local psycopg errors are classified. Never expose SQL text,
            # DSNs, source content or arbitrary exception messages.
            if isinstance(exc,database_error):
                state=exc.sqlstate
                if state in ('40001','40P01','55P03'):
                    return PortResult('RETRYABLE','TRANSACTION_BUSY_OR_ABORTED',correlation)
                if isinstance(exc,transport_error) or (state and state.startswith('08')) or (phase=='COMMITTING' and state is None):
                    return PortResult('UNKNOWN' if phase=='COMMITTING' else 'RETRYABLE',
                        'COMMIT_ACKNOWLEDGEMENT_LOST' if phase=='COMMITTING' else 'TRANSACTION_NOT_COMMITTED',correlation)
                if state=='23505':
                    return PortResult('CONFLICT','TRANSACTION_IDENTITY_CONFLICT',correlation)
                return PortResult('PERMANENT','TRANSACTION_DATABASE_REJECTED',correlation)
            return PortResult('PERMANENT','TRANSACTION_INTERNAL_FAILURE',correlation)

    def _lookup_in_transaction(self,request_id,caller):
        row=self.connection.execute('''SELECT request_hash,principal_id,origin,authority_ref,
            expected_store_revision,committed_store_revision,audit_id,committed_at,receipt
            FROM whattodo.command_transaction WHERE request_id=%s''',(request_id,)).fetchone()
        if row is None:return None
        request_hash,principal,origin,authority_ref,expected,committed,audit_id,at,body=row
        require((principal,origin)==(caller.principal_id,caller.origin),'CALLER_SCOPE_MISMATCH')
        receipt=receipt_from_row(body,request_id=request_id,request_hash=request_hash,
            store_revision=committed,audit_id=audit_id)
        audit=self.connection.execute('''SELECT source_record_ref,correlation_ref,committed_at
            FROM whattodo.audit_entry WHERE request_id=%s AND audit_id=%s''',
            (request_id,audit_id)).fetchone()
        require(audit is not None and audit[2]==at,'COMMAND_RECEIPT_INVALID')
        source,correlation,_=audit
        authority=self.connection.execute('''SELECT principal_id,origin,source_record_ref,
            resolved_scope_hash,issued_at,expires_at FROM whattodo.authority_record
            WHERE authority_ref=%s''',(authority_ref,)).fetchone()
        require(authority is not None and authority[:4]==(principal,origin,source,request_hash)
            and authority[4]<=at and (authority[5] is None or at<authority[5]),'COMMAND_RECEIPT_INVALID')
        changes=tuple(self.connection.execute('''SELECT aggregate_kind,aggregate_id,
            before_revision,after_revision,before_value,after_value FROM whattodo.audit_change
            WHERE request_id=%s AND audit_id=%s ORDER BY aggregate_kind,aggregate_id''',
            (request_id,audit_id)).fetchall())
        validate_audit_fingerprint(receipt,principal_id=principal,expected_store_revision=expected,
            source_ref=source,correlation_ref=correlation,changes=changes)
        for kind,item_id,before,after,old,new in changes:
            if kind=='WORK_REPORT':
                actual=self._work_repository._get_in_transaction(item_id)
                require(before is None and after==1 and actual is not None and actual.as_record()==new
                    and actual.report.command_id==request_id,'COMMAND_RECEIPT_INVALID')
                report=actual.report
                require(report.principal_id==principal and actual.as_record()['source_ref']==source and
                    any(k=='TASK' and i==report.task_id and b==report.expected_revision and a==report.expected_revision+1
                        for k,i,b,a,_,_ in changes),'COMMAND_RECEIPT_INVALID')
                continue
            require(kind=='TASK','COMMAND_RECEIPT_UNSUPPORTED_AGGREGATE')
            require(self.connection.execute('''SELECT transaction_ref FROM whattodo.task_revision
                WHERE task_id=%s AND revision=%s''',(item_id,after)).fetchone()==(request_id,),
                'COMMAND_RECEIPT_INVALID')
            actual=self._repository._get_in_transaction(item_id,after)
            require(actual is not None and actual.aggregate.as_record()==new,'COMMAND_RECEIPT_INVALID')
            if before is not None:
                actual=self._repository._get_in_transaction(item_id,before)
                require(actual is not None and actual.aggregate.as_record()==old,'COMMAND_RECEIPT_INVALID')
        epoch=self.connection.execute('SELECT revision FROM whattodo.store_epoch WHERE singleton=TRUE').fetchone()
        require(epoch is not None and epoch[0]>=committed,'COMMAND_RECEIPT_INVALID')
        return receipt

    def lookup_commit(self,context,*,caller):
        require(isinstance(context,RequestContext),'TYPED_REQUEST_CONTEXT_REQUIRED')
        correlation=context.correlation_ref
        database_error=()
        transport_error=()
        try:
            validate_caller(caller)
            from psycopg import Error as database_error, OperationalError as transport_error
            if self.connection.closed:
                return PortResult('RETRYABLE','COMMIT_LOOKUP_UNAVAILABLE',correlation)
            with schema_checked_transaction(self.connection,self.plan,
                    application_version=self.application_version,read_only=True):
                receipt=self._lookup_in_transaction(context.request_id,caller)
            return PortResult('UNKNOWN','COMMIT_NOT_OBSERVED',correlation) if receipt is None else \
                PortResult('SUCCESS','COMMIT_FOUND',correlation,receipt)
        except TransactionError as exc:
            return PortResult('PERMANENT',str(exc),correlation)
        except TaskStorageError:
            return PortResult('PERMANENT','COMMAND_RECEIPT_INVALID',correlation)
        except MigrationError as exc:
            return PortResult('RETRYABLE','TRANSACTION_SCHEMA_UNAVAILABLE',correlation) if str(exc) in \
                ('MIGRATION_BUSY','MIGRATION_METADATA_UNREADABLE') else \
                PortResult('PERMANENT','TRANSACTION_SCHEMA_INCOMPATIBLE',correlation)
        except ImportError:
            return PortResult('PERMANENT','TRANSACTION_DRIVER_UNAVAILABLE',correlation)
        except (ValueError,TypeError):
            return PortResult('PERMANENT','COMMAND_RECEIPT_INVALID',correlation)
        except Exception as exc:
            # An unavailable read cannot establish absence of a commit.
            if isinstance(exc,database_error) and not isinstance(exc,transport_error) and \
                    exc.sqlstate not in ('40001','40P01','55P03') and \
                    not (exc.sqlstate and exc.sqlstate.startswith('08')):
                return PortResult('PERMANENT','COMMIT_LOOKUP_REJECTED',correlation)
            return PortResult('RETRYABLE','COMMIT_LOOKUP_UNAVAILABLE',correlation)
