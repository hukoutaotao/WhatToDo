"""Owned SQL review-capture probes; not complete source-enumeration acceptance."""
from dataclasses import replace
from datetime import datetime,timedelta,timezone
from hashlib import sha256
import json
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:sys.path.insert(0,str(ROOT))
from src import __version__
from src.adapters.clocks import FrozenClock
from src.adapters.migration_files import load_migration_plan,migration_body
from src.adapters.postgres_migrations import apply_migrations,schema_checked_transaction,DatabaseRoles
from src.adapters.postgres_review_queue import PostgresReviewQueueStore
from src.application.definitions import canonical
from src.application.migrations import MigrationStep
from src.application.review_queue import ReviewQueueItem,ReviewQueueQuery,ReviewQueueHeader,make_review_queue_snapshot
from src.application.transactions import TransactionError
from src.domain.authorization import CallerIdentity
from tools.postgres_harness import PostgresHarness,HarnessError,ROLES,require

NOW=datetime(2026,1,1,tzinfo=timezone.utc);CLOCK=FrozenClock(NOW)
USER=CallerIdentity('review-user','USER_COMMAND',True);KEY=b'synthetic-review-key-32-bytes-minimum'
QUERY=ReviewQueueQuery(7,1);SCOPE_HASH='a'*64


def review_plan():
    base=load_migration_plan(root=ROOT)
    source=(ROOT/'database/runtime-migrations/018_review_queue.sql').read_text(encoding='utf-8')
    step=MigrationStep('018_review_queue',sha256(source.encode()).hexdigest(),'0.14.0-review-queue',source,migration_body(source))
    require(len(base.steps)>=19 and base.steps[18]==step,'REVIEW_RUNTIME_MIGRATION_PIN_DRIFT')
    return base


def verify(h,report):
    import psycopg
    plan=review_plan();base=replace(plan,steps=plan.steps[:18]);db=h.create_database(initialize_schema=False)
    roles=DatabaseRoles(ROLES['migration'],ROLES['application'],ROLES['test']);checks=report['native_checks']
    with h.target(db,'migration').connect() as owner:
        apply_migrations(owner,base,roles=roles,application_version=__version__)
        prior=owner.execute('SELECT * FROM whattodo_meta.migration_history ORDER BY position').fetchall()
        out=apply_migrations(owner,plan,roles=roles,application_version=__version__)
        require(out.applied==('018_review_queue',) and owner.execute('SELECT * FROM whattodo_meta.migration_history WHERE position<=18 ORDER BY position').fetchall()==prior,
            'REVIEW_CAPTURE_UPGRADE_PREFIX')
    checks.append('pinned_nineteenth_step_preserves_all_eighteen_prior_migration_receipts')
    with h.target(db).connect() as conn:
        def store(c=conn,clock=CLOCK):return PostgresReviewQueueStore(c,clock=clock,cursor_key=KEY)
        def boundary(c=conn,write=False):return schema_checked_transaction(c,plan,application_version=__version__,read_only=not write)
        def canonical_state():
            return tuple(conn.execute('SELECT * FROM whattodo.'+t+' ORDER BY 1,2').fetchall() for t in
                ('task_identity','task_revision','stage_revision','command_transaction','authority_record','audit_entry','audit_change','effort_observation','store_epoch'))
        def counts():return tuple(conn.execute('SELECT count(*) FROM whattodo.'+t).fetchone()[0] for t in ('review_queue_snapshot','review_queue_entry'))
        def snapshot(name,n=141,change=False):
            items=tuple(ReviewQueueItem('TASK_ESTIMATE',f'future-{i}',1,'ESTIMATE_VERIFICATION',
                'Changed title' if change else f'Future task {i}',0 if i==0 else 5,5 if i==0 else 1,f'course-{i%9}',
                (),f'future-{i}',1,canonical(dict(work_status='UNKNOWN',estimate_status='UNCERTAIN'))) for i in range(n))
            return make_review_queue_snapshot(QUERY,items,snapshot_id=name,principal_id=USER.principal_id,request_id='request-'+name,
                scope_hash=SCOPE_HASH,store_revision=1,last_transaction_ref=None,observed_at=NOW,expires_at=NOW+timedelta(hours=1),
                coverage_blockers=('SYNTHETIC_PROJECTIONS_ONLY',))
        original=canonical_state();capture=snapshot('capture')
        with boundary(write=True):header=store().append_in_transaction(capture,caller=USER)
        require(counts()==(1,141) and canonical_state()==original,'REVIEW_CAPTURE_SIDE_EFFECTS')
        checks.append('one_minute_target_persists_all_141_ranked_questions_without_canonical_task_authority_audit_or_epoch_changes')
        seen=[];index=0;cursor=None
        while True:
            with h.target(db).connect() as fresh:
                reader=store(fresh)
                with boundary(fresh):
                    actual=reader.get_in_transaction('capture',QUERY,caller=USER,scope_hash=SCOPE_HASH)
                    page=reader.page_in_transaction(actual,QUERY,index=index,caller=USER,scope_hash=SCOPE_HASH)
                require(not page['personal_reconciliation_complete'] and not page['enumeration_complete']
                    and all(i['answer'] is None for i in page['items']),'REVIEW_CAPTURE_FALSE_RECONCILIATION')
                seen.extend(i['item_id'] for i in page['items']);cursor=page['next_cursor']
                if cursor is not None:
                    sid,index=reader.signer.decode(cursor,principal_id=USER.principal_id,query_hash=QUERY.fingerprint)
                    require(sid=='capture','REVIEW_CAPTURE_CURSOR_TARGET')
            if cursor is None:break
        require(seen==[i.item_id for i in capture.items] and len(set(seen))==141,'REVIEW_CAPTURE_LOST_LOW_PRIORITY')
        checks.append('fresh_connection_and_signing_key_cursor_walk_returns_every_frozen_low_priority_question_once')
        with boundary():
            same=store().by_request_in_transaction('request-capture',QUERY,caller=USER,scope_hash=SCOPE_HASH)
            require(same==header,'REVIEW_CAPTURE_REQUEST_RESTART')
        # Even an absent request must pass the same independently trusted
        # user-origin gate before any existence lookup can run.
        class NoLookup:
            def execute(self,*args,**kwargs):raise AssertionError('REVIEW_CAPTURE_UNTRUSTED_LOOKUP_EXECUTED')
        try:
            store(NoLookup()).by_request_in_transaction('absent',QUERY,
                caller=CallerIdentity('process','EXPIRATION_PROCESS',True),scope_hash=SCOPE_HASH)
        except TransactionError as exc:require(str(exc)=='REVIEW_QUEUE_REQUEST_ID','REVIEW_CAPTURE_LOOKUP_ORIGIN_ERROR')
        else:require(False,'REVIEW_CAPTURE_UNTRUSTED_LOOKUP_ACCEPTED')
        later=snapshot('later',change=True)
        with boundary(write=True):store().append_in_transaction(later,caller=USER)
        with boundary():
            page=store().page_in_transaction(header,QUERY,index=0,caller=USER,scope_hash=SCOPE_HASH)
        require(page['items'][0]['title']!='Changed title' and page['total_items']==141,'REVIEW_CAPTURE_REWRITTEN')
        checks.append('owned_request_lookup_and_later_capture_preserve_original_rank_title_group_counts_and_questions')
        for kwargs,expected in ((dict(caller=CallerIdentity('foreign','USER_COMMAND',True),scope_hash=SCOPE_HASH),'REVIEW_QUEUE_SNAPSHOT_UNAVAILABLE'),
            (dict(caller=USER,scope_hash='b'*64),'REVIEW_QUEUE_SNAPSHOT_SCOPE_CONFLICT')):
            try:
                with boundary():store().get_in_transaction('capture',QUERY,**kwargs)
            except TransactionError as exc:require(str(exc)==expected,'REVIEW_CAPTURE_WRONG_SCOPE_ERROR')
            else:require(False,'REVIEW_CAPTURE_FOREIGN_SCOPE_ACCEPTED')
        forged=ReviewQueueHeader(canonical(header.header|dict(principal_id='foreign')))
        try:
            with boundary():store().page_in_transaction(forged,QUERY,index=0,caller=CallerIdentity('foreign','USER_COMMAND',True),scope_hash=SCOPE_HASH)
        except TransactionError as exc:require(str(exc)=='REVIEW_QUEUE_SNAPSHOT_UNAVAILABLE','REVIEW_CAPTURE_FORGED_HEADER_ERROR')
        else:require(False,'REVIEW_CAPTURE_FORGED_HEADER_ACCEPTED')
        checks.append('foreign_principal_changed_account_scope_and_forged_typed_header_cannot_read_captured_rows')

        class Proxy:
            def __init__(self,actual):self.actual=actual
            def __getattr__(self,key):return getattr(self.actual,key)
            def text(self,statement):return statement.as_string(self.actual) if hasattr(statement,'as_string') else statement
        class SkipLast(Proxy):
            def execute(self,statement,*args,**kwargs):
                if self.text(statement).startswith('INSERT INTO whattodo.review_queue_entry') and args[0][1]==5:return None
                return self.actual.execute(statement,*args,**kwargs)
        missing=snapshot('missing',5);baseline=counts()
        try:
            with boundary(write=True):store(SkipLast(conn)).append_in_transaction(missing,caller=USER)
        except psycopg.errors.CheckViolation:pass
        else:require(False,'REVIEW_CAPTURE_MISSING_QUESTION_COMMITTED')
        require(counts()==baseline and canonical_state()==original,'REVIEW_CAPTURE_MISSING_ROLLBACK')
        checks.append('deferred_sql_membership_guard_rejects_a_missing_final_question_and_rolls_back_the_entire_capture')
        class ChangeHash(Proxy):
            def execute(self,statement,*args,**kwargs):
                if self.text(statement).startswith('INSERT INTO whattodo.review_queue_entry'):
                    row=list(args[0]);row[3]='0'*64
                    return self.actual.execute(statement,tuple(row),**kwargs)
                return self.actual.execute(statement,*args,**kwargs)
        try:
            with boundary(write=True):store(ChangeHash(conn)).append_in_transaction(snapshot('hash',1),caller=USER)
        except psycopg.errors.CheckViolation:pass
        else:require(False,'REVIEW_CAPTURE_BAD_HASH_COMMITTED')
        require(counts()==baseline,'REVIEW_CAPTURE_HASH_ROLLBACK')
        checks.append('actual_sql_payload_hash_validation_rejects_bypassed_writer_tampering_without_partial_metadata')
        class CloseDuringCapture(Proxy):
            reached=False
            def execute(self,statement,*args,**kwargs):
                result=self.actual.execute(statement,*args,**kwargs)
                if self.text(statement).startswith('INSERT INTO whattodo.review_queue_entry') and args[0][1]==3:
                    self.reached=True;self.actual.close()
                return result
        retry=snapshot('retry',5)
        with h.target(db).connect() as victim:
            proxy=CloseDuringCapture(victim)
            try:
                with boundary(proxy,True):store(proxy).append_in_transaction(retry,caller=USER)
            except (psycopg.OperationalError,psycopg.InterfaceError):pass
            else:require(False,'REVIEW_CAPTURE_CONNECTION_CLOSE_NOT_OBSERVED')
            require(proxy.reached and victim.closed,'REVIEW_CAPTURE_CLOSE_PATH_NOT_REACHED')
        require(counts()==baseline,'REVIEW_CAPTURE_REAL_CLOSE_LEAKED')
        with boundary(write=True):store().append_in_transaction(retry,caller=USER)
        require(counts()==(baseline[0]+1,baseline[1]+5),'REVIEW_CAPTURE_RETRY_DUPLICATED')
        checks.append('real_connection_close_after_header_and_three_entries_rolls_back_and_original_capture_retries_once')
        for table in ('review_queue_snapshot','review_queue_entry'):
            for sql in (f'UPDATE whattodo.{table} SET snapshot_id=snapshot_id',f'DELETE FROM whattodo.{table}'):
                try:
                    with conn.transaction():conn.execute(sql)
                except psycopg.errors.CheckViolation:pass
                else:require(False,'REVIEW_CAPTURE_HISTORY_MUTABLE')
        checks.append('application_role_cannot_update_or_delete_review_capture_header_or_question_history')
        try:
            with boundary():store(clock=FrozenClock(NOW+timedelta(days=1))).get_in_transaction('capture',QUERY,caller=USER,scope_hash=SCOPE_HASH)
        except TransactionError as exc:require(str(exc)=='REVIEW_QUEUE_SNAPSHOT_EXPIRED','REVIEW_CAPTURE_EXPIRY_ERROR')
        else:require(False,'REVIEW_CAPTURE_EXPIRED_CURSOR_ACCEPTED')
        require(canonical_state()==original and conn.execute("SELECT count(*) FROM whattodo.review_queue_entry WHERE snapshot_id='capture'").fetchone()==(141,),
            'REVIEW_CAPTURE_EXPIRY_DISCARDED_QUESTIONS')
        checks.append('expired_presentation_remains_unanswered_and_cannot_delete_or_reconcile_any_personal_state')
        measured=(conn.execute("SELECT count(*) FROM pg_tables WHERE schemaname='whattodo'").fetchone()[0],
            conn.execute("SELECT count(*) FROM pg_constraint c JOIN pg_namespace n ON n.oid=c.connamespace WHERE n.nspname='whattodo' AND c.contype='f'").fetchone()[0])
        require(measured==(87,221),'REVIEW_CAPTURE_DRAFT_SCHEMA_COUNTS')
        report.update(schema_version=plan.schema_version,migration_steps=len(plan.steps),domain_tables=measured[0],domain_foreign_keys=measured[1],
            activated_steps=len(plan.steps),retained_questions=141)


def main():
    h=PostgresHarness();report=dict(task='M3B-08',status='IN_PROGRESS',scope='INTERNAL_REVIEW_CAPTURE_STORAGE_ONLY_NOT_COMPLETE_SOURCE_QUERY',native_checks=[])
    try:
        with h:verify(h,report)
        report.update(status='PASS',native_check_count=len(report['native_checks']),limitations=[
            'Questions are independently supplied synthetic projections; complete admitted-source enumeration and actual Task eligibility are not certified',
            'Pinned nineteenth migration is tested as an upgrade from the actual eighteen-step predecessor',
            'Public source query, initial-request recovery and unified acceptance require their own gates, not this component probe',
            'No canonical personal state, user answer or reconciliation completion is written'])
    except Exception as exc:
        report.update(status='FAIL',failure_type=type(exc).__name__,failure_code=str(exc) if isinstance(exc,HarnessError) else 'REVIEW_CAPTURE_NATIVE_FAILED',
            failure_sqlstate=getattr(exc,'sqlstate',None),failed_migration=getattr(exc,'failed_migration',None))
    report['harness']=h.safe_summary();path=h.run_root/'review-queue-storage-report.json'
    if h.run_root.exists():path.write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(dict(status=report['status'],report=str(path),checks=len(report['native_checks']),server_stopped=report['harness']['server_stopped'])))
    return 0 if report['status']=='PASS' else 1
if __name__=='__main__':raise SystemExit(main())
