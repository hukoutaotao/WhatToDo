"""Owned native PostgreSQL evidence for atomic Task/audit/version publication."""
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from dataclasses import replace
from datetime import datetime,timedelta,timezone
import json
from pathlib import Path
import sys
from threading import Barrier

ROOT=Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:sys.path.insert(0,str(ROOT))
from src import __version__
from src.adapters.clocks import FrozenClock
from src.adapters.contract_json import ContractJSONCodec
from src.adapters.migration_files import load_migration_plan
from src.adapters.postgres_migrations import DatabaseRoles,LOCK_KEY,apply_migrations
from src.adapters.postgres_tasks import PostgresTaskRepository
from src.adapters.postgres_transactions import PostgresTransactionCoordinator
from src.application.ports import AggregateKey,CommitRequest,RecordWrite,RequestContext,TransactionPermit
from src.application.task_storage import TaskStorageError
from src.domain.authorization import CallerIdentity
from tools.check_contract_registry import trusted_schemas
from tools.postgres_harness import HarnessError,PostgresHarness,ROLES,require
from tools.verify_toolchain import native_transactions

NOW=datetime(2026,1,1,tzinfo=timezone.utc)
CALLER=CallerIdentity('principal','USER_COMMAND',True)
TABLES=('store_epoch','authority_record','command_transaction','audit_entry','audit_change',
    'task_identity','task_head','task_revision','task_details_revision','task_payload_revision',
    'stage_identity','stage_revision','task_stage_revision','stage_effort_revision','task_field_provenance')


def verify(harness,report):
    import psycopg
    codec=ContractJSONCodec(trusted_schemas());plan=load_migration_plan(root=ROOT)
    clock=FrozenClock(NOW);checks=report['native_checks']
    example=json.loads((ROOT/'tests/fixtures/task_aggregate/cases.json').read_text(encoding='utf-8'))['cases'][0]['payload']
    database=harness.create_database(initialize_schema=False)
    with harness.target(database,'migration').connect() as conn:
        apply_migrations(conn,plan,roles=DatabaseRoles(ROLES['migration'],ROLES['application'],ROLES['test']),application_version=__version__)
        native_transactions(conn)

    def value(task_id,revision=1,title='Synthetic task'):
        v=deepcopy(example);v['core']['task_id']=v['effort']['task_id']=task_id
        v['core']['revision']=v['effort']['task_revision']=revision
        v['core']['title']=title;v['core']['acceptance']['authority_ref']='authority'
        v['effort']['user_remaining']=None
        return v

    def request(conn,request_id,values,*,epoch=None,expected=None,source='record'):
        if epoch is None:epoch=conn.execute('SELECT revision FROM whattodo.store_epoch').fetchone()[0]
        return CommitRequest(RequestContext(request_id,'correlation-'+request_id),'principal',epoch,
            tuple(RecordWrite(AggregateKey('TASK',v['core']['task_id']),
                expected if expected is not None else (v['core']['revision']-1 or None),json.dumps(v)) for v in values),
            'audit-'+request_id,source)

    def permit(r):
        return TransactionPermit('permit-'+r.context.request_id,'principal','USER_COMMAND',
            r.fingerprint,NOW-timedelta(minutes=1),NOW+timedelta(hours=1))

    def coordinator(conn,r,*,p=None,permits=None,use_clock=clock):
        return PostgresTransactionCoordinator(conn,codec,plan,application_version=__version__,
            clock=use_clock,permits=(p or permit(r),) if permits is None else permits)

    def state(conn):
        return tuple(conn.execute('SELECT * FROM whattodo.'+t+' ORDER BY 1,2').fetchall() for t in TABLES)

    def no_change(conn,r,*,expected_status,expected_code=None,owner=None,caller=CALLER):
        before=state(conn);out=(owner or coordinator(conn,r)).commit(r,caller=caller,permit_ref=permit(r).permit_ref)
        require(out.status==expected_status and (expected_code is None or out.code==expected_code),'TRANSACTION_NEGATIVE_RESULT')
        require(state(conn)==before,'TRANSACTION_NEGATIVE_LEAKED_ROWS')
        return out

    class ExecuteProxy:
        def __init__(self,conn,trigger,*,disconnect=False):
            self.connection=conn;self.trigger=trigger;self.disconnect=disconnect;self.fired=False
        def __getattr__(self,name):return getattr(self.connection,name)
        def execute(self,query,*args,**kwargs):
            result=self.connection.execute(query,*args,**kwargs)
            if not self.fired and self.trigger(query):
                self.fired=True
                if self.disconnect:self.connection.close()
                raise psycopg.OperationalError('synthetic transport interruption')
            return result

    class LostAck:
        def __init__(self,conn,error_type=psycopg.OperationalError):
            self.connection=conn;self.ordinal=0;self.error_type=error_type
        def __getattr__(self,name):return getattr(self.connection,name)
        def transaction(self):
            self.ordinal+=1;outer=self.ordinal==1;wrapped=self.connection.transaction();error_type=self.error_type
            class Transaction:
                def __enter__(self):return wrapped.__enter__()
                def __exit__(self,kind,error,traceback):
                    result=wrapped.__exit__(kind,error,traceback)
                    if kind is None and outer:raise error_type('synthetic lost commit acknowledgement')
                    return result
            return Transaction()

    with harness.target(database).connect() as conn:
        reader=PostgresTaskRepository(conn,codec,plan,application_version=__version__,clock=clock)
        r=request(conn,'create',[value('task')]);p=permit(r)
        out=coordinator(conn,r).commit(r,caller=CALLER,permit_ref=p.permit_ref)
        require(out.status=='SUCCESS' and out.code=='COMMITTED' and out.value.store_revision==3,'TRANSACTION_CREATE')
        first=reader.get('task')
        require(first.aggregate.as_record()==json.loads(r.writes[0].body_json),'TRANSACTION_CREATE_ROUNDTRIP')
        row=conn.execute('''SELECT c.request_hash,c.receipt,a.source_record_ref,a.correlation_ref,
            x.before_revision,x.after_revision,x.before_value,x.after_value
            FROM whattodo.command_transaction c JOIN whattodo.audit_entry a USING(request_id,audit_id)
            JOIN whattodo.audit_change x USING(request_id,audit_id) WHERE c.request_id=%s''',(r.context.request_id,)).fetchone()
        require(row==(r.fingerprint,coordinator_receipt(out.value),'record','correlation-create',None,1,None,first.aggregate.as_record()),'TRANSACTION_CREATE_AUDIT')
        require(conn.execute('SELECT revision,last_transaction_ref FROM whattodo.store_epoch').fetchone()==(3,'create'),'TRANSACTION_CREATE_EPOCH')
        checks.append('create_publishes_task_authority_full_audit_receipt_and_epoch_together')
        r=request(conn,'patch',[value('task',2,'Corrected title')])
        out=coordinator(conn,r).commit(r,caller=CALLER,permit_ref=permit(r).permit_ref)
        require(out.status=='SUCCESS' and reader.get('task',1)==first and reader.get('task').revision==2,'TRANSACTION_PATCH_HISTORY')
        audit=conn.execute('SELECT before_revision,after_revision,before_value,after_value FROM whattodo.audit_change WHERE request_id=%s',('patch',)).fetchone()
        require(audit==(1,2,first.aggregate.as_record(),reader.get('task').aggregate.as_record()),'TRANSACTION_PATCH_AUDIT')
        checks.append('patch_retains_exact_before_after_values_and_old_aggregate_history')
        r=request(conn,'batch',[value('batch-a'),value('batch-b')]);out=coordinator(conn,r).commit(r,caller=CALLER,permit_ref=permit(r).permit_ref)
        require(out.status=='SUCCESS' and len(out.value.changed_keys)==2 and reader.get('batch-a') and reader.get('batch-b'),'TRANSACTION_BATCH')
        require(conn.execute('SELECT count(*) FROM whattodo.audit_change WHERE request_id=%s',('batch',)).fetchone()==(2,),'TRANSACTION_BATCH_AUDIT')
        checks.append('two_aggregate_batch_has_one_epoch_receipt_and_two_full_audited_changes')
        r=request(conn,'stale-store',[value('task',3)],epoch=2)
        no_change(conn,r,expected_status='CONFLICT',expected_code='STALE_STORE_REVISION')
        checks.append('stale_store_revision_is_conflict_with_no_authority_audit_or_task_mutation')
        r=request(conn,'stale-task',[value('task',2)])
        no_change(conn,r,expected_status='CONFLICT',expected_code='STALE_AGGREGATE_REVISION')
        checks.append('stale_aggregate_revision_is_distinct_conflict_with_no_mutation')
        r=request(conn,'missing-permit',[value('denied')])
        no_change(conn,r,owner=coordinator(conn,r,permits=()),expected_status='PERMANENT',expected_code='EXACT_ACTIVE_PERMIT_REQUIRED')
        checks.append('missing_independent_permit_cannot_create_canonical_state')
        for caller in (CallerIdentity('principal','USER_COMMAND',False),CallerIdentity('other','USER_COMMAND',True),CallerIdentity('principal','EXTERNAL',True)):
            no_change(conn,r,caller=caller,expected_status='PERMANENT',expected_code='UNTRUSTED_CALLER')
        checks.append('unauthenticated_wrong_principal_and_external_callers_leave_no_rows')
        no_change(conn,r,owner=coordinator(conn,r,p=replace(permit(r),expires_at=NOW)),expected_status='PERMANENT',expected_code='EXACT_ACTIVE_PERMIT_REQUIRED')
        no_change(conn,r,owner=coordinator(conn,r,p=replace(permit(r),request_fingerprint='f'*64)),expected_status='PERMANENT',expected_code='EXACT_ACTIVE_PERMIT_REQUIRED')
        checks.append('expired_and_different_exact_write_permits_are_rejected')

        for suffix,trigger in (
                ('audit',lambda q:isinstance(q,str) and q.startswith('INSERT INTO whattodo.audit_change')),
                ('epoch',lambda q:isinstance(q,str) and q.startswith('UPDATE whattodo.store_epoch'))):
            r=request(conn,'fault-'+suffix,[value('fault-'+suffix)])
            proxy=ExecuteProxy(conn,trigger)
            no_change(conn,r,owner=coordinator(proxy,r),expected_status='RETRYABLE',expected_code='TRANSACTION_NOT_COMMITTED')
            require(proxy.fired,'TRANSACTION_FAULT_NOT_INJECTED')
            checks.append('transport_failure_after_'+suffix+'_staging_rolls_back_all_task_audit_authority_receipt_and_epoch_rows')

        class FailAfterAppend:
            def __init__(self,real):self.real=real;self.fired=False
            def __getattr__(self,name):return getattr(self.real,name)
            def _append_in_transaction(self,*args,**kwargs):
                self.real._append_in_transaction(*args,**kwargs);self.fired=True
                raise TaskStorageError('SYNTHETIC_AFTER_FIRST_AGGREGATE')
        r=request(conn,'fault-batch',[value('fault-first'),value('fault-second')]);owner=coordinator(conn,r)
        fault=FailAfterAppend(owner._repository);owner._repository=fault
        no_change(conn,r,owner=owner,expected_status='PERMANENT',expected_code='SYNTHETIC_AFTER_FIRST_AGGREGATE')
        require(fault.fired,'TRANSACTION_BATCH_FAULT_NOT_INJECTED')
        checks.append('failure_after_first_batch_aggregate_rolls_back_entire_batch_and_audit')
        r=request(conn,'missing-source',[value('bad-source')],source='unregistered-source')
        no_change(conn,r,expected_status='PERMANENT',expected_code='TRANSACTION_DATABASE_REJECTED')
        checks.append('deferred_source_fk_failure_at_commit_rolls_back_state_and_full_audit')

        class ExpiringClock:
            def __init__(self):self.calls=0
            def now(self):
                self.calls+=1;return NOW if self.calls<=3 else NOW+timedelta(hours=2)
        r=request(conn,'expiry-during-staging',[value('late-permit')]);c=ExpiringClock()
        no_change(conn,r,owner=coordinator(conn,r,use_clock=c),expected_status='PERMANENT',expected_code='EXACT_ACTIVE_PERMIT_REQUIRED')
        require(c.calls>=4,'TRANSACTION_FINAL_EXPIRY_NOT_CHECKED')
        checks.append('permit_expiring_while_staging_cannot_publish_prepared_state')
        # Hold the native epoch lock with another real connection.
        with harness.target(database).connect() as other:
            with other.transaction():
                other.execute('SELECT revision FROM whattodo.store_epoch FOR UPDATE')
                r=request(conn,'busy',[value('busy-task')])
                no_change(conn,r,expected_status='RETRYABLE',expected_code='TRANSACTION_BUSY_OR_ABORTED')
        checks.append('native_epoch_lock_contention_is_retryable_and_does_not_publish_rows')
        with harness.target(database,'migration').connect() as other:
            with other.transaction():
                other.execute('SELECT pg_advisory_xact_lock(%s)',(LOCK_KEY,))
                r=request(conn,'schema-busy',[value('schema-busy-task')])
                no_change(conn,r,expected_status='RETRYABLE',expected_code='TRANSACTION_SCHEMA_UNAVAILABLE')
        checks.append('migration_lock_contention_is_retryable_before_any_command_staging')

        before=state(conn)
        with harness.target(database).connect() as failing:
            r=request(conn,'disconnect',[value('disconnect-task')])
            proxy=ExecuteProxy(failing,lambda q:isinstance(q,str) and q.startswith('UPDATE whattodo.store_epoch'),disconnect=True)
            out=coordinator(proxy,r).commit(r,caller=CALLER,permit_ref=permit(r).permit_ref)
            require(out.status=='RETRYABLE' and out.code=='TRANSACTION_NOT_COMMITTED' and proxy.fired,'TRANSACTION_DISCONNECT_STATUS')
        require(state(conn)==before,'TRANSACTION_DISCONNECT_COMMITTED_ROWS')
        checks.append('actual_precommit_connection_loss_is_retryable_and_server_rolls_back_all_rows')
        r=request(conn,'lost-ack',[value('ack-task')]);out=coordinator(LostAck(conn),r).commit(r,caller=CALLER,permit_ref=permit(r).permit_ref)
        require(out.status=='UNKNOWN' and out.code=='COMMIT_ACKNOWLEDGEMENT_LOST' and reader.get('ack-task') is not None,'TRANSACTION_ACK_AMBIGUITY')
        require(conn.execute('SELECT count(*) FROM whattodo.audit_change WHERE request_id=%s',('lost-ack',)).fetchone()==(1,),'TRANSACTION_ACK_LOST_AUDIT')
        checks.append('lost_commit_acknowledgement_is_unknown_while_durable_task_audit_and_receipt_survive')
        r=request(conn,'interface-ack',[value('interface-ack-task')])
        out=coordinator(LostAck(conn,psycopg.InterfaceError),r).commit(r,caller=CALLER,permit_ref=permit(r).permit_ref)
        require(out.status=='UNKNOWN' and out.code=='COMMIT_ACKNOWLEDGEMENT_LOST' and reader.get('interface-ack-task') is not None,'TRANSACTION_INTERFACE_ACK_AMBIGUITY')
        checks.append('driver_interface_error_without_server_sqlstate_at_commit_retains_unknown_outcome')

        base=reader.get('task').revision
        contenders=[request(conn,'writer-'+str(i),[value('task',base+1,'Writer '+str(i))]) for i in range(2)]
        barrier=Barrier(2)
        def writer(r):
            with harness.target(database).connect() as separate:
                owner=coordinator(separate,r);barrier.wait(timeout=20)
                return owner.commit(r,caller=CALLER,permit_ref=permit(r).permit_ref)
        with ThreadPoolExecutor(max_workers=2) as pool:
            outcomes=list(pool.map(writer,contenders))
        require(sum(o.status=='SUCCESS' for o in outcomes)==1 and all(o.status in ('SUCCESS','RETRYABLE','CONFLICT') for o in outcomes),'TRANSACTION_TWO_WRITERS_OVERWROTE')
        loser=next(r for r,o in zip(contenders,outcomes) if o.status!='SUCCESS')
        no_change(conn,loser,expected_status='CONFLICT',expected_code='STALE_STORE_REVISION')
        require(reader.get('task').revision==base+1 and conn.execute("SELECT count(*) FROM whattodo.command_transaction WHERE request_id IN ('writer-0','writer-1')").fetchone()==(1,),'TRANSACTION_TWO_WRITER_DUPLICATE_HISTORY')
        checks.append('two_real_simultaneous_writers_cannot_both_overwrite_one_version')
        checks.append('losing_writer_retry_returns_stale_conflict_instead_of_repeating_state_or_audit')
        # Existing authority headers never act as an independent permit or get overwritten.
        r=request(conn,'authority-collision',[value('collision-task')]);p=replace(permit(r),permit_ref='authority')
        no_change(conn,r,owner=coordinator(conn,r,p=p),expected_status='PERMANENT',expected_code='EXACT_ACTIVE_PERMIT_REQUIRED')
        before=state(conn);out=coordinator(conn,r,p=p).commit(r,caller=CALLER,permit_ref='authority')
        require(out.status=='PERMANENT' and out.code=='TRANSACTION_AUTHORITY_REFERENCE_DRIFT' and state(conn)==before,'TRANSACTION_AUTHORITY_OVERWRITE')
        checks.append('existing_authority_scope_mismatch_cannot_be_retagged_or_used_as_approval')
        expected=reader.get('task')
    with harness.target(database).connect() as fresh:
        reader=PostgresTaskRepository(fresh,codec,plan,application_version=__version__,clock=clock)
        require(reader.get('task')==expected and reader.get('task',1)==first,'TRANSACTION_RESTART_HISTORY')
        require(fresh.execute('SELECT receipt FROM whattodo.command_transaction WHERE request_id=%s',('lost-ack',)).fetchone() is not None,'TRANSACTION_RESTART_RECEIPT')
        checks.append('fresh_connection_preserves_committed_current_old_task_and_unknown_ack_receipt')
        report.update(domain_tables=fresh.execute("SELECT count(*) FROM pg_tables WHERE schemaname='whattodo'").fetchone()[0],
            domain_foreign_keys=fresh.execute("SELECT count(*) FROM pg_constraint c JOIN pg_namespace n ON n.oid=c.connamespace WHERE n.nspname='whattodo' AND c.contype='f'").fetchone()[0])


def coordinator_receipt(receipt):
    from dataclasses import asdict
    # PostgreSQL JSON arrays correspond to tuple-valued dataclass fields.
    return json.loads(json.dumps(asdict(receipt)))


def main():
    harness=PostgresHarness();report=dict(task='M3A-09',status='IN_PROGRESS',scope='SYNTHETIC_ATOMIC_TASK_TRANSACTIONS',verified_on='2026-10-10',native_checks=[])
    try:
        with harness:verify(harness,report)
        report.update(status='PASS',native_check_count=len(report['native_checks']),
            limitations=['Independent permits supplied by trusted synthetic setup; full authority resolution remains M3A-11',
                'Task aggregate writes only; future aggregate kinds must add explicit audited storage handlers',
                'Atomicity regression scope; current command replay/reconciliation acceptance uses the separate M3A-10 launcher',
                'No real course, source account, command transport or deployment activation'])
    except Exception as exc:
        report.update(status='FAIL',failure_type=type(exc).__name__,failure_code=str(exc) if isinstance(exc,HarnessError) else 'TRANSACTION_NATIVE_CHECK_FAILED')
    report['harness']=harness.safe_summary();target=harness.run_root/'transaction-report.json'
    if harness.run_root.exists():target.write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(dict(status=report['status'],report=str(target),checks=len(report['native_checks']),server_stopped=report['harness']['server_stopped'])))
    return 0 if report['status']=='PASS' else 1


if __name__=='__main__':raise SystemExit(main())
