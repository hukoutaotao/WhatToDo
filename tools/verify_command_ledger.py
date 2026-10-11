"""Native concurrent/restarted replay and unknown-commit reconciliation."""
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from dataclasses import asdict,replace
from datetime import datetime,timedelta,timezone
import json
from pathlib import Path
import sys
from threading import Barrier,Event

ROOT=Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:sys.path.insert(0,str(ROOT))
from src import __version__
from src.adapters.clocks import FrozenClock
from src.adapters.contract_json import ContractJSONCodec
from src.adapters.migration_files import load_migration_plan
from src.adapters.postgres_migrations import DatabaseRoles,apply_migrations
from src.adapters.postgres_tasks import PostgresTaskRepository
from src.adapters.postgres_transactions import PostgresTransactionCoordinator
from src.application.ports import AggregateKey,CommitRequest,RecordWrite,RequestContext,TransactionPermit
from src.domain.authorization import CallerIdentity
from tools.check_contract_registry import trusted_schemas
from tools.postgres_harness import HarnessError,PostgresHarness,ROLES,require
from tools.verify_toolchain import native_transactions
from tools.verify_transactions import TABLES

NOW=datetime(2026,1,1,tzinfo=timezone.utc)
CALLER=CallerIdentity('principal','USER_COMMAND',True)


def verify(harness,report):
    import psycopg
    from psycopg.types.json import Jsonb
    plan=load_migration_plan(root=ROOT);codec=ContractJSONCodec(trusted_schemas());clock=FrozenClock(NOW)
    checks=report['native_checks'];database=harness.create_database(initialize_schema=False)
    example=json.loads((ROOT/'tests/fixtures/task_aggregate/cases.json').read_text(encoding='utf-8'))['cases'][0]['payload']
    with harness.target(database,'migration').connect() as owner:
        apply_migrations(owner,plan,roles=DatabaseRoles(ROLES['migration'],ROLES['application'],ROLES['test']),application_version=__version__)
        native_transactions(owner)

    def value(task_id,rev=1,title='Synthetic task'):
        v=deepcopy(example);v['core']['task_id']=v['effort']['task_id']=task_id
        v['core']['revision']=v['effort']['task_revision']=rev;v['core']['title']=title
        v['core']['acceptance']['authority_ref']='authority';v['effort']['user_remaining']=None
        return v
    def request(conn,request_id,values):
        epoch=conn.execute('SELECT revision FROM whattodo.store_epoch').fetchone()[0]
        return CommitRequest(RequestContext(request_id,'first-'+request_id),'principal',epoch,
            tuple(RecordWrite(AggregateKey('TASK',v['core']['task_id']),v['core']['revision']-1 or None,json.dumps(v)) for v in values),
            'audit-'+request_id,'record')
    def permit(r):
        return TransactionPermit('permit-'+r.context.request_id,'principal','USER_COMMAND',r.fingerprint,
            NOW-timedelta(minutes=1),NOW+timedelta(hours=1))
    def coordinator(conn,r=None,*,permits=None,use_clock=clock):
        return PostgresTransactionCoordinator(conn,codec,plan,application_version=__version__,clock=use_clock,
            permits=((permit(r),) if r is not None else ()) if permits is None else permits)
    def state(conn):
        return tuple(conn.execute('SELECT * FROM whattodo.'+t+' ORDER BY 1,2').fetchall() for t in TABLES+('effort_observation',))
    def commit(owner,r):return owner.commit(r,caller=CALLER,permit_ref=permit(r).permit_ref)
    def lookup(owner,r,caller=CALLER):
        return owner.lookup_commit(RequestContext(r.context.request_id,'new-lookup'),caller=caller)
    def replay_unchanged(conn,r,receipt,*,owner=None):
        before=state(conn);out=commit(owner or coordinator(conn),r)
        require(out.status=='SUCCESS' and out.code=='REPLAY' and out.value==receipt,'COMMAND_REPLAY_RESULT')
        require(state(conn)==before,'COMMAND_REPLAY_MUTATED_STATE')
        return out

    class NoAppend:
        def __init__(self,real):self.real=real
        def __getattr__(self,name):return getattr(self.real,name)
        def _append_in_transaction(self,*args,**kwargs):raise HarnessError('COMMAND_REPLAY_CALLED_APPEND')
    class LostAck:
        def __init__(self,conn):self.connection=conn;self.count=0
        def __getattr__(self,name):return getattr(self.connection,name)
        def transaction(self):
            self.count+=1;outer=self.count==1;wrapped=self.connection.transaction()
            class Tx:
                def __enter__(self):return wrapped.__enter__()
                def __exit__(self,kind,error,traceback):
                    result=wrapped.__exit__(kind,error,traceback)
                    if kind is None and outer:raise psycopg.OperationalError('synthetic lost acknowledgement')
                    return result
            return Tx()
    class FailedEpoch:
        def __init__(self,conn):self.connection=conn;self.fired=False
        def __getattr__(self,name):return getattr(self.connection,name)
        def execute(self,query,*args,**kw):
            out=self.connection.execute(query,*args,**kw)
            if isinstance(query,str) and query.startswith('UPDATE whattodo.store_epoch') and not self.fired:
                self.fired=True;raise psycopg.OperationalError('synthetic precommit failure')
            return out

    with harness.target(database).connect() as conn:
        r=request(conn,'create',[value('task')]);owner=coordinator(conn,r);out=commit(owner,r)
        require(out.status=='SUCCESS','COMMAND_INITIAL_COMMIT');original=out.value
        reader=PostgresTaskRepository(conn,codec,plan,application_version=__version__,clock=clock)
        replay_unchanged(conn,r,original)
        checks.append('identical_duplicate_returns_original_receipt_without_permit_or_new_mutation')
        out=lookup(coordinator(conn),r)
        require(out.status=='SUCCESS' and out.code=='COMMIT_FOUND' and out.value==original and out.correlation_ref=='new-lookup','COMMAND_LOOKUP')
        checks.append('authenticated_readonly_lookup_returns_typed_original_receipt_and_new_correlation')
        late=FrozenClock(NOW+timedelta(days=7));owner=coordinator(conn,r,use_clock=late)
        owner._repository=NoAppend(owner._repository)
        replay_unchanged(conn,r,original,owner=owner)
        require(lookup(owner,r).value==original,'COMMAND_EXPIRED_LOOKUP')
        checks.append('expired_original_permit_does_not_prevent_owned_readonly_replay')
        attempt=replace(r,context=RequestContext(r.context.request_id,'another-attempt'))
        replay_unchanged(conn,attempt,original)
        checks.append('transport_attempt_correlation_changes_do_not_change_command_meaning')
        for changed in (replace(r,audit_id='different-audit'),replace(r,source_ref='different-source'),
                replace(r,expected_store_revision=r.expected_store_revision+1),
                replace(r,writes=(replace(r.writes[0],body_json=json.dumps(value('task',title='different'))),))):
            before=state(conn);out=commit(coordinator(conn),changed)
            require(out.status=='CONFLICT' and out.code=='REQUEST_ID_CONTENT_CONFLICT' and state(conn)==before,'COMMAND_CHANGED_PAYLOAD')
        checks.append('same_id_with_changed_body_source_audit_or_expected_version_is_content_conflict')
        before=state(conn)
        for caller in (CallerIdentity('principal','USER_COMMAND',False),CallerIdentity('principal','EXTERNAL',True),
                CallerIdentity('other','USER_COMMAND',True),CallerIdentity('principal','RELATIONSHIP_RULE',True)):
            result=lookup(coordinator(conn),r,caller)
            require(result.status=='PERMANENT' and result.value is None,'COMMAND_CALLER_LOOKUP_LEAK')
            result=coordinator(conn).commit(r,caller=caller,permit_ref='claimed-approval')
            require(result.status=='PERMANENT' and result.value is None,'COMMAND_CALLER_REPLAY_LEAK')
        require(state(conn)==before,'COMMAND_DENIED_LOOKUP_CHANGED_STATE')
        checks.append('untrusted_wrong_principal_or_origin_cannot_read_or_replay_receipts')
        missing=RequestContext('not-observed','missing-correlation')
        out=coordinator(conn).lookup_commit(missing,caller=CALLER)
        require(out.status=='UNKNOWN' and out.code=='COMMIT_NOT_OBSERVED','COMMAND_MISSING_NOT_UNKNOWN')
        checks.append('missing_receipt_remains_unknown_instead_of_proving_absence_of_commit')
        patch=request(conn,'patch',[value('task',2,'Later correction')]);require(commit(coordinator(conn,patch),patch).status=='SUCCESS','COMMAND_LATER_PATCH')
        replay_unchanged(conn,r,original)
        require(reader.get('task').revision==2,'COMMAND_OLD_REPLAY_OVERWROTE_NEW_TASK')
        checks.append('replaying_old_command_after_later_edits_keeps_current_and_historical_task_versions')
        batch=request(conn,'batch',[value('batch-z'),value('batch-a')]);batch_out=commit(coordinator(conn,batch),batch)
        require(batch_out.status=='SUCCESS','COMMAND_BATCH_COMMIT')
        reordered=replace(batch,writes=tuple(reversed(batch.writes)),context=RequestContext('batch','reordered-attempt'))
        replay_unchanged(conn,reordered,batch_out.value)
        require(tuple(k.id for k in batch_out.value.changed_keys)==('batch-z','batch-a'),'COMMAND_ORIGINAL_RECEIPT_ORDER')
        checks.append('reordered_same_batch_replays_original_changed_key_order_without_writes')
        # Missing registry may replay old commands, but never admit a new command.
        fresh=request(conn,'fresh-without-permit',[value('unauthorized')]);before=state(conn)
        out=commit(coordinator(conn),fresh)
        require(out.status=='PERMANENT' and out.code=='EXACT_ACTIVE_PERMIT_REQUIRED' and state(conn)==before,'COMMAND_NEW_PERMIT_BYPASS')
        checks.append('receipt_replay_exception_never_authorizes_a_fresh_command_without_exact_permit')

        timed=request(conn,'lost-ack',[value('timed-task')]);out=commit(coordinator(LostAck(conn),timed),timed)
        require(out.status=='UNKNOWN','COMMAND_ACK_NOT_UNKNOWN')
        found=lookup(coordinator(conn),timed)
        require(found.status=='SUCCESS','COMMAND_ACK_NOT_RECONCILED')
        replay_unchanged(conn,timed,found.value)
        checks.append('lost_acknowledgement_reconciles_durable_receipt_and_timeout_retry_mutates_once')
        failed=request(conn,'precommit-failure',[value('failed-task')]);before=state(conn);proxy=FailedEpoch(conn)
        out=commit(coordinator(proxy,failed),failed)
        require(out.status=='RETRYABLE' and proxy.fired and state(conn)==before,'COMMAND_FAILED_TRANSACTION_RETAINED_LEDGER')
        require(lookup(coordinator(conn),failed).status=='UNKNOWN','COMMAND_ABORTED_HAS_SUCCESS_RECEIPT')
        recovered=commit(coordinator(conn,failed),failed)
        require(recovered.status=='SUCCESS','COMMAND_FAILED_TRANSACTION_CANNOT_RETRY')
        replay_unchanged(conn,failed,recovered.value)
        checks.append('rolled_back_command_leaves_no_dedup_tombstone_and_same_id_can_commit_then_replay')

        concurrent=request(conn,'concurrent',[value('concurrent-task')]);barrier=Barrier(2)
        def run(r):
            with harness.target(database).connect() as independent:
                owner=coordinator(independent,r);barrier.wait(timeout=20);return commit(owner,r)
        with ThreadPoolExecutor(max_workers=2) as pool:outcomes=list(pool.map(run,(concurrent,concurrent)))
        require(sum(o.status=='SUCCESS' and o.code=='COMMITTED' for o in outcomes)==1 and
            all(o.status in ('SUCCESS','RETRYABLE','CONFLICT') for o in outcomes),'COMMAND_CONCURRENT_DOUBLE_COMMIT')
        found=lookup(coordinator(conn),concurrent);require(found.status=='SUCCESS','COMMAND_CONCURRENT_NOT_FOUND')
        for out in outcomes:
            if out.status=='SUCCESS':require(out.value==found.value,'COMMAND_CONCURRENT_RECEIPT_CHANGED')
        replay_unchanged(conn,concurrent,found.value)
        require(conn.execute("SELECT count(*) FROM whattodo.command_transaction WHERE request_id='concurrent'").fetchone()==(1,) and
            conn.execute("SELECT count(*) FROM whattodo.audit_change WHERE request_id='concurrent'").fetchone()==(1,),'COMMAND_CONCURRENT_DUPLICATE_HISTORY')
        checks.append('real_concurrent_identical_requests_publish_once_and_retry_replays_same_durable_receipt')
        a=request(conn,'concurrent-conflict',[value('conflict-task',title='A')])
        b=replace(a,writes=(replace(a.writes[0],body_json=json.dumps(value('conflict-task',title='B'))),))
        barrier=Barrier(2)
        with ThreadPoolExecutor(max_workers=2) as pool:outcomes=list(pool.map(run,(a,b)))
        require(sum(o.status=='SUCCESS' for o in outcomes)==1,'COMMAND_CONCURRENT_CHANGED_DOUBLE_COMMIT')
        winner=next(r for r,o in zip((a,b),outcomes) if o.status=='SUCCESS');loser=b if winner is a else a
        before=state(conn);out=commit(coordinator(conn),loser)
        require(out.status=='CONFLICT' and out.code=='REQUEST_ID_CONTENT_CONFLICT' and state(conn)==before,'COMMAND_CONCURRENT_CHANGED_NOT_CONFLICT')
        checks.append('concurrent_same_id_with_changed_payload_has_one_winner_and_durable_content_conflict')

        # An in-flight uncommitted row is not visible to another receipt read.
        staged=Event();release=Event()
        class PausedEpoch:
            def __init__(self,real):self.connection=real
            def __getattr__(self,name):return getattr(self.connection,name)
            def execute(self,q,*args,**kwargs):
                out=self.connection.execute(q,*args,**kwargs)
                if isinstance(q,str) and q.startswith('UPDATE whattodo.store_epoch'):
                    staged.set();require(release.wait(20),'COMMAND_INFLIGHT_RELEASE_TIMEOUT')
                return out
        inflight=request(conn,'inflight',[value('inflight-task')])
        def pending_writer():
            with harness.target(database).connect() as real:return commit(coordinator(PausedEpoch(real),inflight),inflight)
        with ThreadPoolExecutor(max_workers=1) as pool:
            future=pool.submit(pending_writer)
            try:
                require(staged.wait(20),'COMMAND_INFLIGHT_NOT_STAGED')
                require(lookup(coordinator(conn),inflight).status=='UNKNOWN','COMMAND_INFLIGHT_FALSE_ABSENCE')
            finally:release.set()
            require(future.result(timeout=20).status=='SUCCESS','COMMAND_INFLIGHT_COMMIT')
        require(lookup(coordinator(conn),inflight).status=='SUCCESS','COMMAND_INFLIGHT_AFTER_COMMIT')
        checks.append('uncommitted_inflight_receipt_is_unknown_and_becomes_observable_after_commit')

        # Exercise completion replay against explicit retained observation fixtures.
        completion_create=request(conn,'completion-create',[value('completion-task')])
        require(commit(coordinator(conn,completion_create),completion_create).status=='SUCCESS','COMMAND_COMPLETION_CREATE')
        with harness.target(database,'migration').connect() as trusted:
            with trusted.transaction():
                for oid,kind,seconds in (('zero-u','USER_REMAINING',0),('retained-actual','ACTUAL_WORK',1800)):
                    trusted.execute('INSERT INTO whattodo.effort_observation VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)',
                        (oid,'completion-task',kind,seconds,NOW,NOW,'record','authority',None,'completion-create'))
        completed=value('completion-task',2)
        completed['core']['completion']=completed['effort']['completion']='COMPLETE'
        completed['effort']['user_remaining']=dict(seconds=0,observation_id='zero-u',observed_at=NOW.isoformat(),verified_at=NOW.isoformat())
        complete_request=request(conn,'completion',[completed]);out=commit(coordinator(LostAck(conn),complete_request),complete_request)
        require(out.status=='UNKNOWN','COMMAND_COMPLETION_ACK')
        found=lookup(coordinator(conn),complete_request);require(found.status=='SUCCESS','COMMAND_COMPLETION_LOOKUP')
        replay_unchanged(conn,complete_request,found.value)
        require(reader.get('completion-task').aggregate.as_record()['effort']['user_remaining']['seconds']==0 and
            conn.execute("SELECT count(*),sum(seconds) FROM whattodo.effort_observation WHERE task_id='completion-task' AND kind='ACTUAL_WORK'").fetchone()==(1,1800),
            'COMMAND_COMPLETION_RETRY_REPEATED_WORK')
        checks.append('completion_timeout_retry_preserves_zero_u_and_retained_actual_observations_without_new_audit')
        for table in ('command_transaction','audit_entry','audit_change'):
            before=state(conn)
            try:conn.execute('DELETE FROM whattodo.'+table+" WHERE request_id='create'")
            except psycopg.Error as exc:require(exc.sqlstate=='23514','COMMAND_HISTORY_MUTATION_SQLSTATE')
            else:raise HarnessError('COMMAND_HISTORY_MUTATION_ACCEPTED')
            require(state(conn)==before,'COMMAND_HISTORY_MUTATION_CHANGED_ROWS')
        checks.append('native_command_and_audit_history_guards_prevent_deleting_replay_evidence')
        out=coordinator(conn).lookup_commit(RequestContext('committed','legacy-read'),caller=CALLER)
        require(out.status=='PERMANENT' and out.code=='COMMAND_RECEIPT_INVALID','COMMAND_LEGACY_RECEIPT_FABRICATED')
        checks.append('legacy_non_protocol_receipt_is_explicitly_invalid_not_fabricated')

        # Trusted fixture: a plausible new receipt references another command's
        # old Task snapshot. Body/hash agreement alone must not admit it.
        forgery=request(conn,'forged-ledger',[value('task')]);p=permit(forgery)
        from src.application.transactions import prepare_transaction
        prepared=prepare_transaction(codec,forgery,caller=CALLER,permit=p,at=NOW)
        with harness.target(database,'migration').connect() as trusted:
            with trusted.transaction():
                trusted.execute('INSERT INTO whattodo.authority_record VALUES(%s,%s,%s,%s,%s,%s,%s,%s)',
                    (p.permit_ref,'principal','USER_COMMAND','record',forgery.fingerprint,Jsonb(dict(synthetic=True)),p.issued_at,p.expires_at))
                trusted.execute('INSERT INTO whattodo.command_transaction VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)',
                    ('forged-ledger',forgery.fingerprint,'principal','USER_COMMAND',p.permit_ref,forgery.expected_store_revision,prepared.receipt.store_revision,forgery.audit_id,NOW,Jsonb(prepared.receipt_body)))
                trusted.execute('INSERT INTO whattodo.audit_entry VALUES(%s,%s,%s,%s,%s)',
                    (forgery.audit_id,'forged-ledger','record',forgery.context.correlation_ref,NOW))
                trusted.execute('INSERT INTO whattodo.audit_change VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s)',
                    (prepared.writes[0].change_ref,forgery.audit_id,'TASK','task',None,1,None,Jsonb(value('task')),'forged-ledger'))
                trusted.execute('UPDATE whattodo.store_epoch SET revision=%s,last_transaction_ref=%s',
                    (prepared.receipt.store_revision,'forged-ledger'))
        before=state(conn);out=lookup(coordinator(conn),forgery)
        require(out.status=='PERMANENT' and out.code=='COMMAND_RECEIPT_INVALID' and state(conn)==before,'COMMAND_FORGED_BACKLINK_ACCEPTED')
        checks.append('receipt_with_correct_body_hash_but_wrong_task_transaction_backlink_is_rejected')
        original_task=reader.get('task')

    with harness.target(database).connect() as fresh:
        fresh_owner=coordinator(fresh,use_clock=FrozenClock(NOW+timedelta(days=30)))
        found=lookup(fresh_owner,r);require(found.status=='SUCCESS' and found.value==original,'COMMAND_RESTART_LOOKUP')
        replay_unchanged(fresh,r,original,owner=fresh_owner)
        require(PostgresTaskRepository(fresh,codec,plan,application_version=__version__,clock=clock).get('task')==original_task,'COMMAND_RESTART_OVERWRITE')
        checks.append('fresh_connection_and_empty_permit_registry_replay_old_receipt_after_later_updates')
        before=state(fresh)
        with harness.target(database).connect() as failing:
            failing.close();out=lookup(coordinator(failing),r)
            require(out.status=='RETRYABLE' and out.value is None,'COMMAND_FAILED_LOOKUP_FALSE_SUCCESS')
        require(state(fresh)==before,'COMMAND_FAILED_LOOKUP_MUTATED_STATE')
        checks.append('unavailable_receipt_connection_is_retryable_without_claiming_commit_absence')
        report.update(domain_tables=fresh.execute("SELECT count(*) FROM pg_tables WHERE schemaname='whattodo'").fetchone()[0],
            domain_foreign_keys=fresh.execute("SELECT count(*) FROM pg_constraint c JOIN pg_namespace n ON n.oid=c.connamespace WHERE n.nspname='whattodo' AND c.contype='f'").fetchone()[0])


def main():
    harness=PostgresHarness();report=dict(task='M3A-10',status='IN_PROGRESS',scope='SYNTHETIC_DURABLE_COMMAND_REPLAY',verified_on='2026-10-10',native_checks=[])
    try:
        with harness:verify(harness,report)
        report.update(status='PASS',native_check_count=len(report['native_checks']),limitations=[
            'Independent exact permits and observation facts are trusted synthetic fixtures; no live authority resolver',
            'Task transactions and completion facts exercised; actual effort-addition handler remains M3A-15',
            'No real course/source account/authenticated transport or deployment activation'])
    except Exception as exc:
        report.update(status='FAIL',failure_type=type(exc).__name__,failure_code=str(exc) if isinstance(exc,HarnessError) else 'COMMAND_LEDGER_NATIVE_CHECK_FAILED',failure_sqlstate=getattr(exc,'sqlstate',None))
    report['harness']=harness.safe_summary();target=harness.run_root/'command-ledger-report.json'
    if harness.run_root.exists():target.write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(dict(status=report['status'],report=str(target),checks=len(report['native_checks']),server_stopped=report['harness']['server_stopped'])))
    return 0 if report['status']=='PASS' else 1


if __name__=='__main__':raise SystemExit(main())
