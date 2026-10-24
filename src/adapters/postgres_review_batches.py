"""Scoped unchanged-estimate batch confirmation entrypoint and internal writer.

Only versioned command bytes enter this boundary. Caller, grants and per-member
current evidence are independently resolved inside one owned transaction; a
reconstructed journal never authorizes a second confirmation. Verification
records an unchanged estimate and never mutates Tasks or actual work.
"""
from dataclasses import dataclass
from datetime import timedelta
from hashlib import sha256

from src.adapters.postgres_evidence import PostgresEvidenceRepository
from src.adapters.postgres_migrations import schema_checked_transaction
from src.adapters.postgres_tasks import PostgresTaskRepository
from src.adapters.postgres_transactions import PostgresTransactionCoordinator
from src.application.command_ledger import receipt_from_row, validate_audit_fingerprint, validate_caller
from src.application.definitions import canonical, identity
from src.application.evidence_storage import EvidenceError
from src.application.migrations import MigrationError
from src.application.ports import CommitReceipt, PortResult, RequestContext, TransactionPermit
from src.application.review_batches import (BatchCommitPlan, BatchTaskEvidence, ReviewBatchGrant,
    ReviewBatchJournal, admit_review_batch, prepare_batch_commit, prepare_review_batch)
from src.application.task_storage import TaskStorageError
from src.application.transactions import TransactionError, require, valid_permit
from src.domain.authorization import CallerIdentity
from src.domain.task_aggregate import instant


def register_review_batch_grant(connection,grant,plan,*,application_version):
    """Trusted setup/resolver only; the command entrypoint never registers grants."""
    require(isinstance(grant,ReviewBatchGrant),'REVIEW_BATCH_TYPED_GRANT')
    from psycopg.types.json import Jsonb
    c=grant.command
    expected=(c.principal_id,'USER_COMMAND',grant.evidence_ref,c.fingerprint,grant.as_record(),grant.issued_at,grant.expires_at)
    with schema_checked_transaction(connection,plan,application_version=application_version,read_only=False):
        row=connection.execute('''SELECT principal_id,origin,source_record_ref,resolved_scope_hash,
            resolved_scope,issued_at,expires_at FROM whattodo.authority_record WHERE authority_ref=%s''',
            (c.authority_ref,)).fetchone()
        if row is not None:
            require(row==expected,'REVIEW_BATCH_AUTHORITY_IMMUTABLE_CONFLICT');return
        connection.execute('INSERT INTO whattodo.authority_record VALUES(%s,%s,%s,%s,%s,%s,%s,%s)',
            (c.authority_ref,*expected[:4],Jsonb(expected[4]),*expected[5:]))


class PostgresReviewBatchWriter:
    """Internal publication inside an already authorized transaction."""

    def __init__(self,connection,codec,plan,*,application_version,clock):
        self.connection=connection;self.codec=codec;self.plan=plan
        self.application_version=application_version;self.clock=clock

    def _root(self,journal,at):
        row=self.connection.execute('''SELECT principal_id,origin,source_record_ref,resolved_scope_hash,
            resolved_scope,issued_at,expires_at FROM whattodo.authority_record WHERE authority_ref=%s''',
            (journal.command.authority_ref,)).fetchone()
        require(row is not None,'REVIEW_BATCH_UNREGISTERED_AUTHORITY')
        grant=ReviewBatchGrant(journal.command,journal.source_ref,row[5],journal.source_observed_at,row[6])
        require(row[:5]==(journal.command.principal_id,'USER_COMMAND',journal.source_ref,
            journal.command.fingerprint,grant.as_record()),'REVIEW_BATCH_REGISTERED_AUTHORITY_MISMATCH')
        require(row[5]<=at and (row[6] is None or at<row[6]),'REVIEW_BATCH_INACTIVE_AUTHORITY')
        source=self.connection.execute('''SELECT r.captured_at,s.source_type FROM whattodo.source_record r
            JOIN whattodo.source_identity s USING(source_id) WHERE r.record_id=%s''',(journal.source_ref,)).fetchone()
        require(source==(journal.source_observed_at,'USER') and journal.source_observed_at<=at,
            'REVIEW_BATCH_REGISTERED_SOURCE_MISMATCH')
        return grant

    def append_in_transaction(self,plan,*,caller,permit,evidence):
        from psycopg.pq import TransactionStatus
        from psycopg.types.json import Jsonb
        from psycopg import sql
        require(self.connection.info.transaction_status==TransactionStatus.INTRANS,'REVIEW_BATCH_OPEN_TRANSACTION_REQUIRED')
        require(isinstance(plan,BatchCommitPlan),'REVIEW_BATCH_TYPED_COMMIT_REQUIRED')
        request=plan.request;journal=plan.journal;now=self.clock.now()
        validate_caller(caller,principal_id=request.principal_id)
        require(caller.origin=='USER_COMMAND','REVIEW_BATCH_TRUSTED_USER_CALLER')
        valid_permit(request,caller,permit,now)
        root=self._root(journal,now)
        # Every member is re-read and re-validated against current SQL state.
        repository=PostgresTaskRepository(self.connection,self.codec,self.plan,
            application_version=self.application_version,clock=self.clock)
        current=[]
        for member in journal.command.members:
            record=repository._get_in_transaction(member.task_id)
            require(record is not None,'REVIEW_BATCH_MEMBER_HISTORY_UNAVAILABLE')
            aggregate=record.aggregate.as_record();estimate=aggregate['effort']['user_remaining']
            if estimate is None:
                current.append(BatchTaskEvidence(record,'UNTOUCHED'))
            else:
                status,last=self._work_status(member.task_id,estimate)
                prior_id,prior_batch=self._prior(member.task_id,member.observation_id)
                current.append(BatchTaskEvidence(record,status,last,prior_id,prior_batch))
        rebuilt=prepare_review_batch(journal.command,root,tuple(current),caller=caller,now=now)
        require(rebuilt.state==journal.state and rebuilt.verifications==journal.verifications,
            'REVIEW_BATCH_EXACT_COMMIT_PLAN_REQUIRED')
        require(self.connection.execute('SELECT revision FROM whattodo.store_epoch WHERE singleton=TRUE FOR UPDATE NOWAIT'
            ).fetchone()==(request.expected_store_revision,),'REVIEW_BATCH_STALE_STORE_REVISION')
        validate_audit_fingerprint(plan.receipt,principal_id=request.principal_id,
            expected_store_revision=request.expected_store_revision,source_ref=request.source_ref,
            correlation_ref=request.context.correlation_ref,changes=tuple(a.tuple for a in plan.audits))
        annotation=dict(contract='review-batch',grant_ref=journal.command.authority_ref,
            command_fingerprint=journal.command.fingerprint,command=journal.command.as_record(),
            command_wire_hash=journal.payload()['raw_command_hash'])
        scope=dict(scope_kind='EXACT_TRANSACTION',request_fingerprint=request.fingerprint,authorization=annotation)
        self.connection.execute('INSERT INTO whattodo.authority_record VALUES(%s,%s,%s,%s,%s,%s,%s,%s)',
            (permit.permit_ref,caller.principal_id,caller.origin,request.source_ref,request.fingerprint,
                Jsonb(scope),permit.issued_at,permit.expires_at))
        self.connection.execute('INSERT INTO whattodo.command_transaction VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)',
            (request.context.request_id,request.fingerprint,caller.principal_id,caller.origin,permit.permit_ref,
                request.expected_store_revision,plan.receipt.store_revision,request.audit_id,now,Jsonb(plan.receipt_body)))
        self.connection.execute('INSERT INTO whattodo.audit_entry VALUES(%s,%s,%s,%s,%s)',
            (request.audit_id,request.context.request_id,request.source_ref,request.context.correlation_ref,now))
        for a in plan.audits:
            kind,item,previous,after,old,new=a.tuple
            self.connection.execute('INSERT INTO whattodo.audit_change VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s)',
                (a.change_ref,request.audit_id,kind,item,previous,after,
                    Jsonb(old) if old is not None else None,Jsonb(new),request.context.request_id))
        for v in journal.verifications:
            # The immutable effort history records the unchanged verification;
            # it adds no numeric estimate and no actual work.
            self.connection.execute('INSERT INTO whattodo.effort_observation VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)',
                (v.verification_id,v.task_id,'UNCHANGED_VERIFICATION',None,v.verified_at,now,
                    journal.source_ref,journal.command.authority_ref,journal.record_id,request.context.request_id))
        change=next(a for a in plan.audits if a.key.kind==journal.kind)
        row=journal.sql_row(request.context.request_id,change.change_ref)
        columns=tuple(row)
        self.connection.execute(sql.SQL('INSERT INTO whattodo.review_batch_confirmation ({}) VALUES ({})').format(
            sql.SQL(',').join(map(sql.Identifier,columns)),sql.SQL(',').join(sql.Placeholder() for _ in columns)),
            tuple(Jsonb(v) if isinstance(v,dict) else v for v in row.values()))
        for v in journal.verifications:
            change=next(a for a in plan.audits if a.key.id==v.verification_id)
            vr=v.sql_row(request.context.request_id,change.change_ref)
            vcolumns=tuple(vr)
            self.connection.execute(sql.SQL('INSERT INTO whattodo.review_batch_verification ({}) VALUES ({})').format(
                sql.SQL(',').join(map(sql.Identifier,vcolumns)),sql.SQL(',').join(sql.Placeholder() for _ in vcolumns)),
                tuple(Jsonb(val) if isinstance(val,dict) else val for val in vr.values()))
        self._root(journal,self.clock.now())
        valid_permit(request,caller,permit,self.clock.now())
        updated=self.connection.execute('''UPDATE whattodo.store_epoch SET revision=%s,last_transaction_ref=%s
            WHERE singleton=TRUE AND revision=%s''',
            (plan.receipt.store_revision,request.context.request_id,request.expected_store_revision)).rowcount
        require(updated==1,'REVIEW_BATCH_STALE_STORE_REVISION')
        return plan.receipt

    def _task(self,task_id,principal,revision):
        repository=PostgresTaskRepository(self.connection,self.codec,self.plan,
            application_version=self.application_version,clock=self.clock)
        birth=self.connection.execute('''SELECT i.transaction_ref,c.principal_id FROM whattodo.task_identity i
            JOIN whattodo.command_transaction c ON c.request_id=i.transaction_ref WHERE i.task_id=%s''',
            (task_id,)).fetchone()
        require(birth is not None and birth[1]==principal,'REVIEW_BATCH_MEMBER_NOT_OWNED')
        record=repository._get_in_transaction(task_id,revision)
        require(record is not None,'REVIEW_BATCH_MEMBER_HISTORY_UNAVAILABLE')
        return record

    def _work_status(self,task_id,estimate):
        """Worked-on is factual: positive actual-work observations after the estimate."""
        observed=instant(estimate['observed_at'])
        row=self.connection.execute('''SELECT max(observed_at) FROM whattodo.effort_observation
            WHERE task_id=%s AND kind='ACTUAL_WORK' AND seconds>0''',(task_id,)).fetchone()
        last=row[0]
        if last is not None and last>observed:return 'WORKED',last
        return 'UNTOUCHED',last

    def _prior(self,task_id,observation_id):
        row=self.connection.execute('''SELECT verification_id,batch_record_id FROM whattodo.review_batch_verification
            WHERE task_id=%s AND observation_id=%s''',(task_id,observation_id)).fetchone()
        if row is None:return None,None
        return row[0],row[1]


@dataclass(frozen=True)
class ReviewBatchOutcome:
    journal: ReviewBatchJournal
    receipt: CommitReceipt
    def __post_init__(self):
        require(isinstance(self.journal,ReviewBatchJournal) and isinstance(self.receipt,CommitReceipt)
            and self.receipt.request_id==self.journal.command.command_id
            and any(k.kind==self.journal.kind and k.id==self.journal.record_id for k in self.receipt.changed_keys),
            'REVIEW_BATCH_TYPED_OUTCOME')
    @property
    def state(self):return self.journal.state


class PostgresReviewBatchHandler:
    def __init__(self,connection,codec,plan,*,application_version,clock,grants=()):
        require(isinstance(grants,tuple) and all(isinstance(g,ReviewBatchGrant) for g in grants)
            and len({g.command.authority_ref for g in grants})==len(grants),'REVIEW_BATCH_TRUSTED_GRANT_REGISTRY')
        self.connection=connection;self.codec=codec;self.plan=plan
        self.application_version=application_version;self.clock=clock
        self.grants={g.command.authority_ref:g for g in grants}
        self.reader=PostgresTaskRepository(connection,codec,plan,application_version=application_version,clock=clock)
        self.evidence=PostgresEvidenceRepository(connection,codec,plan,application_version=application_version,
            clock=clock,scopes=())
        self.writer=PostgresReviewBatchWriter(connection,codec,plan,application_version=application_version,clock=clock)

    def _owned_task(self,task_id,principal,revision=None):
        birth=self.connection.execute('''SELECT i.transaction_ref,c.principal_id FROM whattodo.task_identity i
            JOIN whattodo.command_transaction c ON c.request_id=i.transaction_ref WHERE i.task_id=%s''',
            (task_id,)).fetchone()
        require(birth is not None and birth[1]==principal,'REVIEW_BATCH_MEMBER_NOT_OWNED')
        record=self.reader._get_in_transaction(task_id,revision)
        require(record is not None,'REVIEW_BATCH_MEMBER_HISTORY_UNAVAILABLE')
        return record

    def _work_status(self,task_id,estimate):
        return self.writer._work_status(task_id,estimate)

    def _prior(self,task_id,observation_id):
        return self.writer._prior(task_id,observation_id)

    def _replay(self,command,caller,*,epoch=None,audit_id=None):
        row=self.connection.execute('''SELECT j.record_id,c.request_hash,c.principal_id,c.origin,c.authority_ref,
            c.expected_store_revision,c.committed_store_revision,c.audit_id,c.committed_at,c.receipt,e.source_record_ref,e.correlation_ref,e.committed_at
            FROM whattodo.review_batch_confirmation j JOIN whattodo.command_transaction c ON c.request_id=j.transaction_ref
            JOIN whattodo.audit_entry e ON(e.request_id,e.audit_id)=(c.request_id,c.audit_id) WHERE j.command_id=%s''',
            (command.command_id,)).fetchone()
        if row is None:
            require(self.connection.execute('SELECT 1 FROM whattodo.command_transaction WHERE request_id=%s',
                (command.command_id,)).fetchone() is None,'REVIEW_BATCH_REPLAY_SCOPE_CONFLICT')
            return None
        journal=ReviewBatchJournal.from_payload(self.connection.execute(
            'SELECT runtime_payload FROM whattodo.review_batch_confirmation WHERE record_id=%s',(row[0],)).fetchone()[0])
        require(journal.command.fingerprint==command.fingerprint and row[2:4]==(caller.principal_id,'USER_COMMAND')
            and (epoch is None or epoch==row[5]) and (audit_id is None or audit_id==row[7]),'REVIEW_BATCH_REPLAY_SCOPE_CONFLICT')
        require(row[10]==journal.source_ref and row[12]==row[8],'REVIEW_BATCH_REPLAY_RECEIPT_DRIFT')
        grant=self.writer._root(journal,row[8])
        changes=tuple(self.connection.execute('''SELECT aggregate_kind,aggregate_id,before_revision,after_revision,before_value,after_value
            FROM whattodo.audit_change WHERE request_id=%s AND audit_id=%s ORDER BY aggregate_kind,aggregate_id''',(command.command_id,row[7])).fetchall())
        verifications=self.connection.execute('''SELECT runtime_payload FROM whattodo.review_batch_verification
            WHERE transaction_ref=%s ORDER BY verification_id''',(command.command_id,)).fetchall()
        require([v[0] for v in verifications]==[v.as_record() for v in sorted(journal.verifications,key=lambda v:v.verification_id)],
            'REVIEW_BATCH_REPLAY_VERIFICATION_DRIFT')
        receipt=receipt_from_row(row[9],request_id=command.command_id,request_hash=row[1],store_revision=row[6],audit_id=row[7])
        validate_audit_fingerprint(receipt,principal_id=command.principal_id,expected_store_revision=row[5],
            source_ref=journal.source_ref,correlation_ref=row[11],changes=changes)
        require(self.connection.execute('SELECT revision FROM whattodo.store_epoch WHERE singleton=TRUE').fetchone()[0]>=receipt.store_revision,
            'REVIEW_BATCH_REPLAY_EPOCH_DRIFT')
        return ReviewBatchOutcome(journal,receipt)

    def _run(self,raw,context,caller,*,epoch=None,audit_id=None,lookup=False):
        require(isinstance(context,RequestContext),'TYPED_REQUEST_CONTEXT_REQUIRED')
        correlation=context.correlation_ref;phase='ADMISSION';database_error=();transport_error=();interface_error=()
        try:
            command=admit_review_batch(self.codec,raw);validate_caller(caller,principal_id=command.principal_id)
            require(caller.origin=='USER_COMMAND' and context.request_id==command.command_id,'REVIEW_BATCH_TRUSTED_USER_CALLER')
            from psycopg import Error as database_error,OperationalError as transport_error,InterfaceError as interface_error
            require(any(s.migration_id=='019_review_batches' for s in self.plan.steps),'REVIEW_BATCH_SCHEMA_NOT_ENABLED')
            with schema_checked_transaction(self.connection,self.plan,application_version=self.application_version,read_only=lookup):
                prior=self._replay(command,caller,epoch=epoch,audit_id=audit_id)
                if prior is not None:return PortResult('SUCCESS','REVIEW_BATCH_REPLAYED',correlation,prior)
                if lookup:return PortResult('UNKNOWN','REVIEW_BATCH_NOT_OBSERVED',correlation)
                grant=self.grants.get(command.authority_ref)
                require(grant is not None and grant.command.fingerprint==command.fingerprint,'REVIEW_BATCH_INDEPENDENT_GRANT_REQUIRED')
                evidence=[]
                for member in command.members:
                    record=self._owned_task(member.task_id,caller.principal_id)
                    aggregate=record.aggregate.as_record();estimate=aggregate['effort']['user_remaining']
                    status,last=self._work_status(member.task_id,estimate)
                    prior_id,prior_batch=self._prior(member.task_id,member.observation_id)
                    evidence.append(BatchTaskEvidence(record,status,last,prior_id,prior_batch))
                plan=prepare_batch_commit(self.codec,raw,grant,tuple(evidence),caller=caller,now=self.clock.now(),
                    context=context,expected_store_revision=epoch,audit_id=audit_id)
                require(self.writer._root(plan.journal,self.clock.now())==grant,'REVIEW_BATCH_REGISTERED_AUTHORITY_MISMATCH')
                now=self.clock.now();expires=min(now+timedelta(minutes=1),grant.expires_at) if grant.expires_at else now+timedelta(minutes=1)
                permit=TransactionPermit('review-permit-'+sha256((command.fingerprint+plan.request.fingerprint).encode()).hexdigest(),
                    command.principal_id,'USER_COMMAND',plan.request.fingerprint,now,expires)
                phase='STAGING'
                self.writer.append_in_transaction(plan,caller=caller,permit=permit,evidence=tuple(evidence))
                phase='COMMITTING'
            return PortResult('SUCCESS','REVIEW_BATCH_'+plan.journal.state,correlation,ReviewBatchOutcome(plan.journal,plan.receipt))
        except MigrationError as exc:
            retry=str(exc) in ('MIGRATION_BUSY','MIGRATION_METADATA_UNREADABLE')
            return PortResult('RETRYABLE' if retry else 'PERMANENT','REVIEW_BATCH_SCHEMA_UNAVAILABLE' if retry else 'REVIEW_BATCH_SCHEMA_INCOMPATIBLE',correlation)
        except ImportError:return PortResult('PERMANENT','TRANSACTION_DRIVER_UNAVAILABLE',correlation)
        except TransactionError as exc:
            code=str(exc);status='CONFLICT' if code in ('REVIEW_BATCH_STALE_STORE_REVISION','REVIEW_BATCH_STALE_MEMBER',
                'REVIEW_BATCH_OVERLAPPING_VERIFICATION','REVIEW_BATCH_CHANGED_ESTIMATE','REVIEW_BATCH_MISSING_ESTIMATE',
                'REVIEW_BATCH_MEMBER_WORKED_ON','REVIEW_BATCH_MEMBER_INELIGIBLE','REVIEW_BATCH_WORK_STATUS_UNCONFIRMED',
                'REVIEW_BATCH_REPLAY_SCOPE_CONFLICT','REVIEW_BATCH_COMMAND_ID_CONFLICT') else 'PERMANENT'
            return PortResult(status,code,correlation)
        except (TaskStorageError,EvidenceError) as exc:return PortResult('PERMANENT',str(exc),correlation)
        except database_error as exc:
            from psycopg import InterfaceError as _interface
            if isinstance(exc,(transport_error,_interface)):
                return PortResult('UNKNOWN' if phase=='COMMITTING' else 'RETRYABLE','REVIEW_BATCH_ACKNOWLEDGEMENT_LOST' if phase=='COMMITTING'
                    else 'REVIEW_BATCH_REFERENCES_UNAVAILABLE',correlation)
            if getattr(exc,'sqlstate',None) in ('55P03','40001','40P01'):
                return PortResult('RETRYABLE','REVIEW_BATCH_REFERENCES_UNAVAILABLE',correlation)
            return PortResult('PERMANENT','REVIEW_BATCH_REFERENCE_DATABASE_REJECTED',correlation)
        except Exception:return PortResult('PERMANENT','REVIEW_BATCH_VALIDATION_FAILED',correlation)

    def confirm(self,raw,context,*,expected_store_revision,audit_id,caller):
        return self._run(raw,context,caller,epoch=expected_store_revision,audit_id=audit_id)

    def lookup(self,raw,context,caller):
        return self._run(raw,context,caller,lookup=True)
