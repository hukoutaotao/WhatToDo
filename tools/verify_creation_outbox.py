"""Owned native canonical capture, actual disconnect/commit and lease races."""
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
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
from src.adapters.git_definitions import GitDefinitionSource
from src.adapters.migration_files import load_migration_plan
from src.adapters.postgres_authorization import register_grant
from src.adapters.postgres_creation_outbox import PostgresCreationOutbox
from src.adapters.postgres_definitions import PostgresDefinitionRepository
from src.adapters.postgres_evidence import PostgresEvidenceRepository,register_source_scope
from src.adapters.postgres_fact_patches import PostgresFactPatchHandler,register_fact_patch_grant
from src.adapters.postgres_manual_tasks import PostgresManualTaskHandler
from src.adapters.postgres_migrations import DatabaseRoles,apply_migrations,schema_checked_transaction
from src.adapters.postgres_tasks import PostgresTaskRepository
from src.adapters.prototype_codec import PrototypeJSONCodec
from src.adapters.extension_contracts import load_supported_schemas
from src.application.creation_outbox import DeliveryOutcome,OutboxError,event_id_for
from src.application.definitions import canonical
from src.application.evidence_storage import SourceScope
from src.application.fact_patches import FactPatch,FactPatchGrant
from src.application.manual_tasks import ResolvedManualIntent
from src.application.ports import RequestContext
from src.domain.authorization import AuthorityGrant,CallerIdentity,Command,change
from src.domain.provenance import capture_source
from tools.git_definition_fixture import GitDefinitionFixture
from tools.postgres_harness import PostgresHarness,HarnessError,ROLES,require
from tools.verify_transactions import TABLES

NOW=datetime(2026,1,1,tzinfo=timezone.utc);CLOCK=FrozenClock(NOW)
CALLER=CallerIdentity('principal','USER_COMMAND',True)
SCOPE=SourceScope('synthetic-outbox','scope','account')
DIMS=dict(thinking_depth=2,repetitive_volume=3,new_learning_load=2)
OUTBOX_TABLES=('canonical_creation_event','creation_delivery_revision','creation_delivery_head')


def verify(harness,report):
    import psycopg
    plan=load_migration_plan(root=ROOT);old=replace(plan,steps=plan.steps[:14])
    roles=DatabaseRoles(ROLES['migration'],ROLES['application'],ROLES['test'])
    codec=PrototypeJSONCodec(load_supported_schemas(root=ROOT));checks=report['native_checks']
    db=harness.create_database(initialize_schema=False)
    fixture=GitDefinitionFixture(harness.run_root/'git-fixture');git=GitDefinitionSource(fixture.root)
    with harness.target(db,'migration').connect() as owner:
        apply_migrations(owner,old,roles=roles,application_version=__version__)
        register_source_scope(owner,old,roles,SCOPE,application_version=__version__,clock=CLOCK)
    with harness.target(db).connect() as conn:
        def source(name,raw,active_plan=plan,kind='USER'):
            value=capture_source(provider=SCOPE.provider,scope_ref=SCOPE.scope_ref,external_id=name,
                                 raw_bytes=raw,captured_at=NOW,source_type=kind)
            PostgresEvidenceRepository(conn,codec,active_plan,application_version=__version__,clock=CLOCK,scopes=(SCOPE,)).observe_source(
                canonical(value.as_record()).encode(),raw_content=raw,locator_ref='synthetic-'+name)
            return value.record_id

        def prepare(name,active_plan=plan,partial=False):
            fields=dict(title='Synthetic '+name,importance=3,requiredness='REQUIRED',difficulty=DIMS,user_remaining_seconds=600)
            if partial:fields=dict(title='Synthetic incomplete creation')
            c=Command('create-'+name,'principal','USER_COMMAND','root-'+name,(change(name,None,'CREATE_TASK',fields),))
            raw=canonical(c.as_record()).encode();ref=source(c.command_id,raw,active_plan)
            grant=AuthorityGrant(c.authority_ref,c.principal_id,c.origin,c.command_id,c.changes,ref,NOW-timedelta(minutes=1),expires_at=NOW+timedelta(hours=1))
            with harness.target(db,'migration').connect() as owner:register_grant(owner,grant,active_plan,application_version=__version__)
            intent=ResolvedManualIntent(c.fingerprint,ref,NOW,canonical({} if partial else dict(domain='study',total_estimate_seconds=1800)))
            return c,raw,grant,intent,conn.execute('SELECT revision FROM whattodo.store_epoch').fetchone()[0],active_plan

        def create(packet,connection=None):
            c,raw,g,intent,epoch,active_plan=packet;connection=connection or conn
            definitions=PostgresDefinitionRepository(connection,git,active_plan,roles,application_version=__version__)
            return PostgresManualTaskHandler(connection,codec,active_plan,application_version=__version__,clock=CLOCK,
                definitions=definitions,grants=(g,),source_scopes=(SCOPE,),intents=(intent,)).create(raw,
                RequestContext(c.command_id,'outbox-correlation'),expected_store_revision=epoch,audit_id='audit-'+c.command_id,caller=CALLER)

        historical=prepare('historical',old);require(create(historical).code=='COMMITTED','OUTBOX_HISTORICAL_CREATE')
        with harness.target(db,'migration').connect() as owner:
            prefix=owner.execute('SELECT * FROM whattodo_meta.migration_history ORDER BY position').fetchall()
            result=apply_migrations(owner,plan,roles=roles,application_version=__version__)
            require(result.applied==('014_creation_outbox','015_generation_occurrences','016_generation_processing','017_stage_commands','018_review_queue') and owner.execute('SELECT * FROM whattodo_meta.migration_history WHERE position<=14 ORDER BY position').fetchall()==prefix,'OUTBOX_UPGRADE_PREFIX')
        require(conn.execute('SELECT count(*) FROM whattodo.canonical_creation_event').fetchone()==(0,),'OUTBOX_RETROACTIVE_BACKFILL')
        checks.append('fourteen_step_upgrade_preserves_prior_task_and_receipts_without_historical_backfill')
        source('external',b'Synthetic external discovery',kind='EMAIL')
        require(conn.execute('SELECT count(*) FROM whattodo.canonical_creation_event').fetchone()==(0,),'OUTBOX_RAW_TRIGGER')
        checks.append('raw_external_observation_creates_no_canonical_creation_event')

        def counts():return tuple(conn.execute('SELECT count(*) FROM whattodo.'+t).fetchone()[0] for t in TABLES+OUTBOX_TABLES)
        class Disconnect:
            def __init__(self,real):self.real=real;self.fired=False;self.saw_task_event=False
            def __getattr__(self,key):return getattr(self.real,key)
            def execute(self,query,*args,**kw):
                result=self.real.execute(query,*args,**kw)
                if isinstance(query,str) and query.startswith('UPDATE whattodo.store_epoch'):
                    self.saw_task_event=self.real.execute("SELECT EXISTS(SELECT 1 FROM whattodo.canonical_creation_event WHERE task_id='disconnected')").fetchone()[0]
                    self.fired=True;self.real.close();raise psycopg.OperationalError('synthetic disconnect')
                return result

        packet=prepare('disconnected');before=counts()
        with harness.target(db).connect() as separate:
            proxy=Disconnect(separate)
            try:create(packet,proxy)
            except psycopg.Error:pass
            require(proxy.fired and proxy.saw_task_event,'OUTBOX_DISCONNECT_NOT_STAGED')
        require(counts()==before,'OUTBOX_PRECOMMIT_LEAK')
        checks.append('actual_connection_close_after_task_event_staging_rolls_back_task_event_delivery_receipt_audit_and_epoch')

        class LostAck:
            def __init__(self,real):self.real=real;self.fired=False;self.lost=False;self.depth=0
            def __getattr__(self,key):return getattr(self.real,key)
            def execute(self,query,*args,**kw):
                result=self.real.execute(query,*args,**kw)
                if isinstance(query,str) and query.startswith('INSERT INTO whattodo.command_transaction'):self.fired=True
                return result
            @contextmanager
            def transaction(self):
                self.depth+=1
                try:
                    with self.real.transaction():yield
                    if self.depth==1 and self.fired and not self.lost:
                        self.lost=True;raise psycopg.OperationalError('synthetic lost acknowledgement')
                finally:self.depth-=1

        packet=prepare('committed')
        with harness.target(db).connect() as separate:
            proxy=LostAck(separate);out=create(packet,proxy)
            require(proxy.lost and out.status=='UNKNOWN','OUTBOX_ACK_NOT_LOST')

        def port(connection=conn,worker='worker',at=NOW,caller=CALLER,scopes=(SCOPE,)):
            return PostgresCreationOutbox(connection,plan,application_version=__version__,clock=FrozenClock(at),
                caller=caller,worker_id=worker,source_scopes=scopes)

        eid=event_id_for('committed');ready=port().get(eid)
        require(ready is not None and ready.state=='READY' and ready.attempt==0,'OUTBOX_LOST_EVENT')
        reader=PostgresTaskRepository(conn,codec,plan,application_version=__version__,clock=CLOCK)
        require(ready.event.content_hash==reader.get('committed',1).content_hash and ready.event.creation_transaction_ref==packet[0].command_id,'OUTBOX_SOURCE_PIN')
        checks.append('lost_ack_after_real_commit_leaves_durable_ready_event_with_exact_initial_payload_and_original_creation_transaction')
        replay=create(packet);require(replay.code=='REPLAY','OUTBOX_CREATION_REPLAY')
        require(conn.execute('SELECT count(*) FROM whattodo.canonical_creation_event WHERE event_id=%s',(eid,)).fetchone()==(1,),'OUTBOX_DUPLICATE_EVENT')
        checks.append('original_command_retry_preserves_one_event_and_initial_delivery_revision')
        partial=prepare('partial',partial=True);require(create(partial).code=='PENDING_DETAILS','OUTBOX_PARTIAL_CREATE')
        require(port().get(event_id_for('partial')) is None,'OUTBOX_PENDING_TRIGGER')
        checks.append('pending_manual_facts_do_not_publish_a_task_or_creation_event')
        patch=FactPatch('patch-source','principal','root-patch-source','committed',1,canonical(dict(importance=4)))
        raw=canonical(patch.as_record()).encode();ref=source('patch-source',raw)
        grant=FactPatchGrant(patch,ref,NOW,NOW+timedelta(hours=1),NOW)
        with harness.target(db,'migration').connect() as owner:register_fact_patch_grant(owner,grant,plan,application_version=__version__)
        out=PostgresFactPatchHandler(conn,codec,plan,application_version=__version__,clock=CLOCK,grants=(grant,),source_scopes=(SCOPE,)).patch(raw,
            RequestContext(patch.command_id,'outbox-correlation'),expected_store_revision=conn.execute('SELECT revision FROM whattodo.store_epoch').fetchone()[0],audit_id='audit-patch-source',caller=CALLER)
        require(out.code=='COMMITTED' and port().get(eid).event==ready.event and conn.execute('SELECT count(*) FROM whattodo.canonical_creation_event').fetchone()==(1,),'OUTBOX_UPDATE_DUPLICATE')
        checks.append('subsequent_fact_update_keeps_first_creation_snapshot_without_new_events')

        with harness.target(db).connect() as locker:
            with schema_checked_transaction(locker,plan,application_version=__version__,read_only=False):
                locker.execute('SELECT event_id FROM whattodo.creation_delivery_head WHERE event_id=%s FOR UPDATE',(eid,))
                require(port(worker='skipped').claim(lease_seconds=10) is None,'OUTBOX_SKIP_LOCKED')
        checks.append('locked_delivery_is_skipped_without_waiting_or_claiming_it')
        barrier=Barrier(2)
        def contender(worker):
            with harness.target(db).connect() as separate:
                queue=port(separate,worker=worker);barrier.wait(timeout=15)
                try:return queue.claim(lease_seconds=10)
                except OutboxError as exc:
                    require(str(exc)=='OUTBOX_STORAGE_RETRY','OUTBOX_RACE_ERROR');return None
        with ThreadPoolExecutor(max_workers=2) as pool:leases=list(pool.map(contender,('worker-a','worker-b')))
        require(sum(l is not None for l in leases)==1,'OUTBOX_DOUBLE_CLAIM');lease=next(l for l in leases if l is not None)
        worker=lease.worker_id;require(port(worker=worker).get(eid).lease==lease,'OUTBOX_RESTART_LEASE')
        checks.append('simultaneous_workers_obtain_exactly_one_fenced_lease_and_restart_reads_that_lease')
        require(port(worker='other-worker').get(eid).lease is None and port(worker='other-worker').claim() is None,'OUTBOX_FOREIGN_WORKER_TOKEN')
        checks.append('other_worker_cannot_read_lease_token_or_claim_unexpired_delivery')

        def reject(action,code):
            try:action()
            except OutboxError as exc:require(str(exc)==code,'OUTBOX_UNEXPECTED_CODE')
            else:require(False,'OUTBOX_NEGATIVE_ACCEPTED')

        state_before=tuple(conn.execute('SELECT count(*) FROM whattodo.'+t).fetchone()[0] for t in TABLES)
        renewed=port(worker=worker,at=NOW+timedelta(seconds=1)).renew(lease,lease_seconds=20)
        require(renewed.attempt==lease.attempt and renewed.token==lease.token and renewed.revision==lease.revision+1,'OUTBOX_RENEW_IDENTITY')
        reject(lambda:port(worker=worker,at=NOW+timedelta(seconds=2)).settle(lease,DeliveryOutcome('DONE','stale-result')),'OUTBOX_STALE_LEASE')
        checks.append('renewal_retains_attempt_and_token_but_fences_previous_delivery_revision')
        retry=DeliveryOutcome('RETRY',code='TEMPORARY_UNAVAILABLE',retry_at=NOW+timedelta(seconds=5))
        settled=port(worker=worker,at=NOW+timedelta(seconds=2)).settle(renewed,retry)
        require(settled.state=='READY' and settled.outcome==retry and port(at=NOW+timedelta(seconds=4)).claim() is None,'OUTBOX_RETRY_DELAY')
        replayed=port(worker=worker,at=NOW+timedelta(seconds=3)).settle(renewed,retry)
        require(replayed==settled,'OUTBOX_SETTLEMENT_REPLAY')
        for forged in (replace(renewed,attempt=renewed.attempt+1),
                       replace(renewed,event=replace(renewed.event,content_hash='a'*64)),
                       replace(renewed,expires_at=renewed.expires_at+timedelta(seconds=1))):
            reject(lambda:port(worker=worker).settle(forged,retry),'OUTBOX_STALE_LEASE')
        checks.append('settlement_replay_verifies_original_source_snapshot_attempt_and_full_lease')
        reject(lambda:port(worker=worker).settle(renewed,DeliveryOutcome('FAILED',code='DIFFERENT_RESULT')),'OUTBOX_REPLAY_CONFLICT')
        checks.append('retry_time_and_original_settlement_survive_replay_and_conflicting_result_is_rejected')
        next_lease=port(worker='recovering',at=NOW+timedelta(seconds=5)).claim(lease_seconds=10)
        require(next_lease.attempt==2 and next_lease.token!=renewed.token,'OUTBOX_RETRY_CLAIM')
        require(port(worker=worker,at=NOW+timedelta(seconds=6)).settle(renewed,retry)==settled and port(worker='recovering').get(eid).lease==next_lease,'OUTBOX_OLD_RETRY_OVERWROTE_NEW_CLAIM')
        checks.append('original_retry_ack_replays_after_new_claim_without_overwriting_it')
        require(port(worker='replacement',at=NOW+timedelta(seconds=14)).claim() is None,'OUTBOX_PREMATURE_RECOVERY')
        recovered=port(worker='replacement',at=NOW+timedelta(seconds=15)).claim(lease_seconds=10)
        require(recovered is not None and recovered.attempt==3 and recovered.token!=next_lease.token,'OUTBOX_EXPIRED_LOSS')
        reject(lambda:port(worker='recovering',at=NOW+timedelta(seconds=16)).settle(next_lease,DeliveryOutcome('DONE','late-worker')),'OUTBOX_STALE_LEASE')
        checks.append('expired_worker_lease_recovers_at_exact_expiry_and_late_previous_worker_cannot_settle')
        done=DeliveryOutcome('DONE','synthetic-generation-processing-result')
        final=port(worker='replacement',at=NOW+timedelta(seconds=16)).settle(recovered,done)
        require(final.state=='DONE' and port(worker='replacement',at=NOW+timedelta(seconds=30)).settle(recovered,done)==final
                and port(at=NOW+timedelta(seconds=30)).claim() is None,'OUTBOX_FINAL_REPLAY')
        checks.append('terminal_result_is_durable_and_original_ack_replays_after_expiry_without_requeue')
        require(tuple(conn.execute('SELECT count(*) FROM whattodo.'+t).fetchone()[0] for t in TABLES)==state_before
                and reader.get('committed').aggregate.as_record()['core']['completion']=='INCOMPLETE','OUTBOX_METADATA_TASK_MUTATION')
        checks.append('delivery_claim_renew_retry_and_done_do_not_mutate_task_audit_receipt_or_store_epoch')
        require(port(caller=CallerIdentity('foreign','USER_COMMAND',True)).get(eid) is None and
                port(scopes=(SourceScope(SCOPE.provider,SCOPE.scope_ref,'wrong-account'),)).get(eid) is None,'OUTBOX_SOURCE_LEAK')
        checks.append('foreign_principal_and_wrong_registered_account_scope_cannot_read_event_or_delivery')
        with harness.target(db).connect() as app:
            try:
                with app.transaction():app.execute('INSERT INTO whattodo.canonical_creation_event SELECT * FROM whattodo.canonical_creation_event LIMIT 1')
            except psycopg.Error as exc:require(exc.sqlstate=='42501','OUTBOX_EVENT_PRIVILEGE')
            else:require(False,'OUTBOX_DIRECT_EVENT_INSERT')
        checks.append('application_role_cannot_insert_events_manually_but_legitimate_task_trigger_can')
        with harness.target(db,'migration').connect() as owner:
            for table in ('canonical_creation_event','creation_delivery_revision'):
                try:
                    with owner.transaction():owner.execute('DELETE FROM whattodo.'+table)
                except psycopg.Error as exc:require(exc.sqlstate=='23514','OUTBOX_HISTORY_SQLSTATE')
                else:require(False,'OUTBOX_HISTORY_MUTATED')
        checks.append('canonical_event_and_delivery_history_are_append_only')
        from psycopg.types.json import Jsonb
        for kind in ('WAITING_FACTS','FAILED'):
            packet=prepare('terminal-'+kind);require(create(packet).code=='COMMITTED','OUTBOX_TERMINAL_CREATE')
            queue=port(worker='terminal-worker',at=NOW+timedelta(seconds=40));lease=queue.claim()
            require(lease.event.task_id=='terminal-'+kind,'OUTBOX_TERMINAL_CLAIM')
            try:
                with conn.transaction():
                    conn.execute('''INSERT INTO whattodo.creation_delivery_revision
                        (event_id,revision,state,attempt,changed_at,available_at,settled_worker_id,settled_token,settled_revision,outcome)
                        VALUES(%s,%s,'DONE',%s,%s,%s,%s,%s,%s,%s)''',
                        (lease.event.event_id,lease.revision+1,lease.attempt,NOW+timedelta(seconds=41),NOW,
                         lease.worker_id,lease.token,lease.revision,Jsonb(dict(kind='DONE',result_ref=None,code=None,retry_at=None))))
            except psycopg.Error as exc:require(exc.sqlstate=='23514','OUTBOX_BAD_RESULT_SQLSTATE')
            else:require(False,'OUTBOX_MALFORMED_RESULT_ADMITTED')
            outcome=DeliveryOutcome(kind,'waiting-facts-result') if kind=='WAITING_FACTS' else DeliveryOutcome(kind,code='UNSUPPORTED_MAPPING')
            terminal=queue.settle(lease,outcome)
            require(terminal.state==kind and queue.settle(lease,outcome)==terminal and queue.claim() is None,'OUTBOX_TERMINAL_STATE')
        checks.append('waiting_facts_and_failed_results_are_durable_and_malformed_direct_sql_result_is_rejected')
        report.update(schema_version=plan.schema_version,migration_steps=len(plan.steps),
            domain_tables=conn.execute("SELECT count(*) FROM pg_tables WHERE schemaname='whattodo'").fetchone()[0],
            domain_foreign_keys=conn.execute("SELECT count(*) FROM pg_constraint c JOIN pg_namespace n ON n.oid=c.connamespace WHERE n.nspname='whattodo' AND c.contype='f'").fetchone()[0])
        require((report['domain_tables'],report['domain_foreign_keys'])==(87,221),'OUTBOX_SCHEMA_COUNTS')


def main():
    h=PostgresHarness();r=dict(task='M3B-03',status='IN_PROGRESS',scope='SYNTHETIC_ATOMIC_CAPTURE_AND_SCOPED_LEASES',native_checks=[])
    try:
        with h:verify(h,r)
        r.update(status='PASS',native_check_count=len(r['native_checks']),limitations=['No live worker, rule selection or counterpart generation','Outcome settlement records delivery processing only; domain mutations require their own authority/transaction','Historical creations are not backfilled'])
    except Exception as exc:r.update(status='FAIL',failure_type=type(exc).__name__,failure_code=str(exc) if isinstance(exc,(HarnessError,OutboxError)) else 'OUTBOX_NATIVE_FAILED',failure_sqlstate=getattr(exc,'sqlstate',None))
    r['harness']=h.safe_summary();p=h.run_root/'creation-outbox-report.json'
    if h.run_root.exists():p.write_text(json.dumps(r,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(dict(status=r['status'],report=str(p),checks=len(r['native_checks']),server_stopped=r['harness']['server_stopped'])))
    return 0 if r['status']=='PASS' else 1


if __name__=='__main__':raise SystemExit(main())
