"""Owned native actual-work settlement, deduplication and two-record atomicity."""
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
from src.adapters.extension_contracts import load_supported_schemas
from src.adapters.memory_definitions import MemoryDefinitionRepository
from src.adapters.migration_files import load_migration_plan
from src.adapters.postgres_actual_work import PostgresActualWorkRepository
from src.adapters.postgres_authorization import PostgresCommandService,register_grant
from src.adapters.postgres_evidence import PostgresEvidenceRepository,register_source_scope
from src.adapters.postgres_lifecycle import PostgresLifecycleHandler
from src.adapters.postgres_manual_tasks import PostgresManualTaskHandler
from src.adapters.postgres_migrations import DatabaseRoles,apply_migrations
from src.adapters.postgres_tasks import PostgresTaskRepository
from src.adapters.postgres_transactions import PostgresTransactionCoordinator
from src.adapters.postgres_work_reports import PostgresWorkReportHandler,register_work_report_grant
from src.application.definitions import canonical
from src.application.evidence_storage import SourceScope
from src.application.manual_tasks import ResolvedManualIntent
from src.application.ports import AggregateKey,CommitRequest,RecordWrite,RequestContext,TransactionPermit
from src.application.task_storage import TaskStorageBindings,admit_storage
from src.application.work_reports import WorkReportGrant,admit_work_report
from src.domain.authorization import AuthorityGrant,CallerIdentity,Command,change
from src.domain.provenance import capture_source
from tools.postgres_harness import HarnessError,PostgresHarness,ROLES,require
from tools.verify_transactions import TABLES

NOW=datetime(2026,1,1,tzinfo=timezone.utc);CLOCK=FrozenClock(NOW)
CALLER=CallerIdentity('principal','USER_COMMAND',True);SCOPE=SourceScope('synthetic-work','scope','account')
DIMS=dict(thinking_depth=2,repetitive_volume=2,new_learning_load=3)


def verify(harness,report):
    import psycopg
    plan=load_migration_plan(root=ROOT);codec=ContractJSONCodec(load_supported_schemas(root=ROOT));checks=report['native_checks']
    database=harness.create_database(initialize_schema=False);roles=DatabaseRoles(ROLES['migration'],ROLES['application'],ROLES['test'])
    with harness.target(database,'migration').connect() as owner:
        old=load_migration_plan(root=ROOT,manifest_path=ROOT/'reports/acceptance/M3A-14-migration-plan.json')
        apply_migrations(owner,old,roles=roles,application_version=__version__)
        prior=owner.execute('SELECT * FROM whattodo_meta.migration_history ORDER BY position').fetchall()
        upgraded=apply_migrations(owner,plan,roles=roles,application_version=__version__)
        require(upgraded.applied==tuple(step.migration_id for step in plan.steps[len(old.steps):]) and owner.execute('SELECT * FROM whattodo_meta.migration_history WHERE position<=10 ORDER BY position').fetchall()==prior,
            'WORK_FORWARD_UPGRADE')
        register_source_scope(owner,plan,roles,SCOPE,application_version=__version__,clock=CLOCK)
    checks.append('forward_migrations_preserve_exact_ten_step_history_without_backfilling_unknown_sessions')
    with harness.target(database).connect() as conn:
        reader=PostgresTaskRepository(conn,codec,plan,application_version=__version__,clock=CLOCK)
        work=PostgresActualWorkRepository(conn,codec,plan,application_version=__version__,clock=CLOCK)
        def epoch():return conn.execute('SELECT revision FROM whattodo.store_epoch').fetchone()[0]
        def state():return tuple(conn.execute('SELECT * FROM whattodo.'+t+' ORDER BY 1,2').fetchall() for t in TABLES+
            ('effort_observation','actual_work_report','normalized_due','manual_creation_pending'))
        def evidence(name,kind='USER',captured=None):
            raw=('synthetic work statement '+name).encode()
            source=capture_source(provider=SCOPE.provider,scope_ref=SCOPE.scope_ref,external_id=name,raw_bytes=raw,
                captured_at=captured or NOW-timedelta(minutes=1),source_type=kind)
            PostgresEvidenceRepository(conn,codec,plan,application_version=__version__,clock=CLOCK,scopes=(SCOPE,)).observe_source(
                canonical(source.as_record()).encode(),raw_content=raw,locator_ref='synthetic-'+name)
            return source.record_id
        def base_grant(c,source):
            g=AuthorityGrant(c.authority_ref,c.principal_id,c.origin,c.command_id,c.changes,source,NOW-timedelta(minutes=2),expires_at=NOW+timedelta(hours=1))
            with harness.target(database,'migration').connect() as owner:register_grant(owner,g,plan,application_version=__version__)
            return g
        def create(name,*,requiredness='REQUIRED'):
            fields=dict(title='Synthetic '+name,importance=3,requiredness=requiredness,difficulty=DIMS,user_remaining_seconds=600)
            if requiredness=='EXPIRING':fields['expiration_condition_ref']='class-start'
            c=Command('create-'+name,'principal','USER_COMMAND','create-grant-'+name,(change(name,None,'CREATE_TASK',fields),))
            source=evidence('create-'+name);g=base_grant(c,source)
            intent=ResolvedManualIntent(c.fingerprint,source,NOW-timedelta(minutes=1),canonical(dict(domain='study',total_estimate_seconds=1800)))
            result=PostgresManualTaskHandler(conn,codec,plan,application_version=__version__,clock=CLOCK,definitions=MemoryDefinitionRepository(CLOCK),
                grants=(g,),source_scopes=(SCOPE,),intents=(intent,)).create(canonical(c.as_record()).encode(),RequestContext(c.command_id,'correlation'),
                expected_store_revision=epoch(),audit_id='audit-'+c.command_id,caller=CALLER)
            require(result.code=='COMMITTED','WORK_CREATE_'+result.code);return reader.get(name)
        def setup(name,*,task='task',source_kind='USER',registered=True,active=True,captured=None,**fields):
            v=dict(schema_version='0.1.0-work-report',command_id=name,principal_id='principal',origin='USER_COMMAND',authority_ref='grant-'+name,
                observation_id='observation-'+name,target_ref=dict(task_id=task,revision=reader.get(task).revision),mode='INCREMENT',seconds=300,
                stage_id=None,session_started_at=None,session_ended_at=None);v.update(fields)
            r=admit_work_report(codec,canonical(v).encode());source=evidence(name,source_kind,captured)
            g=WorkReportGrant(r,source,NOW-timedelta(minutes=2),NOW+timedelta(hours=1),active)
            if registered:
                with harness.target(database,'migration').connect() as owner:register_work_report_grant(owner,g,plan,application_version=__version__)
            return r,g,epoch()
        def handler(g=None,**kw):
            options=dict(application_version=__version__,clock=CLOCK,grants=(g,) if g else (),source_scopes=(SCOPE,));options.update(kw)
            return PostgresWorkReportHandler(options.pop('connection',conn),codec,plan,**options)
        def submit(h,r,e,*,caller=CALLER,audit=None,raw=None):
            return h.report(raw or r.payload_json.encode(),RequestContext(r.command_id,'correlation-'+r.command_id),
                expected_store_revision=e,audit_id=audit or 'audit-'+r.command_id,caller=caller)
        def deny(h,r,e,code,**kw):
            before=state();out=submit(h,r,e,**kw)
            require(out.status in ('CONFLICT','PERMANENT','RETRYABLE') and out.code==code,'WORK_NEGATIVE_'+out.code)
            require(state()==before,'WORK_NEGATIVE_MUTATED');return out
        def confirm(name,operation,task):
            fields=dict(completion='COMPLETE') if operation=='COMPLETE' else dict(disposition='CANCELLED')
            c=Command(name,'principal','USER_COMMAND','grant-'+name,(change(task,reader.get(task).revision,'UPDATE_TASK',fields),))
            g=base_grant(c,evidence(name));h=PostgresLifecycleHandler(conn,codec,plan,application_version=__version__,clock=CLOCK,grants=(g,),source_scopes=(SCOPE,))
            fn=h.complete if operation=='COMPLETE' else h.cancel
            out=fn(canonical(c.as_record()).encode(),RequestContext(c.command_id,'correlation'),expected_store_revision=epoch(),audit_id='audit-'+name,caller=CALLER)
            require(out.code=='COMMITTED','WORK_CONFIRM_'+out.code)

        original=create('task');r,g,e=setup('first');out=submit(handler(g),r,e)
        require(out.code=='COMMITTED','WORK_FIRST_'+out.code);receipt=out.value.receipt;first=out.value.record
        require(work.get(r.observation_id)==first and work.total('task')==300 and reader.get('task').revision==2,'WORK_INCREMENT_ROUNDTRIP')
        old=original.aggregate.as_record();new=reader.get('task').aggregate.as_record()
        require(new['effort']['user_remaining']==old['effort']['user_remaining'] and new['timing']==old['timing'] and new['work']==old['work']
            and new['core']['completion']=='INCOMPLETE','WORK_SPENT_CHANGED_U')
        checks.append('reported_increment_roundtrips_without_subtracting_u_completing_task_or_fabricating_session_bounds')
        require(conn.execute('SELECT aggregate_kind,aggregate_id FROM whattodo.audit_change WHERE request_id=%s ORDER BY aggregate_kind',(r.command_id,)).fetchall()==
            [('TASK','task'),('WORK_REPORT',r.observation_id)] and len(receipt.changed_keys)==2,'WORK_TWO_AUDITS')
        require(PostgresTransactionCoordinator(conn,codec,plan,application_version=__version__,clock=CLOCK).lookup_commit(RequestContext(r.command_id,'fresh'),caller=CALLER).value==receipt,
            'WORK_LEDGER_TWO_AGGREGATES');checks.append('receipt_fingerprint_and_two_full_audits_bind_task_and_original_work_report')
        same_before=state();replay=submit(handler(),r,e)
        require(replay.code=='REPLAY' and replay.value.receipt==receipt and state()==same_before,'WORK_SAME_COMMAND_REPLAY')
        checks.append('same_command_retry_with_empty_grants_replays_owned_original_receipt_without_double_counting')

        c,cg,ce=setup('cumulative',mode='CUMULATIVE',seconds=900);co=submit(handler(cg),c,ce)
        require(co.code=='COMMITTED' and co.value.record.as_record()['increment_seconds']==600 and work.total('task')==900,'WORK_CUMULATIVE')
        checks.append('cumulative_total_settles_only_difference_from_prior_actual_increments_and_keeps_original_report')
        c,cg,ce=setup('equal-cumulative',mode='CUMULATIVE',seconds=900);co=submit(handler(cg),c,ce)
        require(co.code=='COMMITTED' and co.value.record.as_record()['increment_seconds']==0 and work.total('task')==900,'WORK_EQUAL_TOTAL')
        checks.append('equal_cumulative_total_records_zero_increment_without_duplicate_effort')
        c,cg,ce=setup('below-cumulative',mode='CUMULATIVE',seconds=899)
        deny(handler(cg),c,ce,'WORK_REPORT_CUMULATIVE_BELOW_RECORDED_TOTAL');checks.append('lower_cumulative_report_is_explicit_conflict_without_negative_work_or_counter_reset')

        alias=r.as_record();alias['command_id']='alias-first';alias['authority_ref']='no-alias-grant';alias['target_ref']['revision']=999
        alias=admit_work_report(codec,canonical(alias).encode());before=state();again=submit(handler(),alias,epoch(),audit='different-audit')
        require(again.code=='OBSERVATION_REPLAY' and again.value.receipt==receipt and again.value.record==first and state()==before,'WORK_OBSERVATION_REPLAY')
        checks.append('observation_identity_deduplicates_changed_transport_id_revision_and_audit_without_new_u_verification_or_command_row')
        changed=alias.as_record();changed['seconds']=301;deny(handler(),admit_work_report(codec,canonical(changed).encode()),epoch(),'WORK_REPORT_OBSERVATION_ID_CONFLICT')
        checks.append('same_observation_identity_with_changed_fact_is_conflict_and_leaves_current_head_untouched')
        changed=alias.as_record();changed['principal_id']='other'
        deny(handler(),admit_work_report(codec,canonical(changed).encode()),epoch(),'CALLER_SCOPE_MISMATCH',caller=CallerIdentity('other','USER_COMMAND',True))
        checks.append('observation_retry_is_owned_and_cannot_disclose_another_principals_receipt')
        require(submit(handler(clock=FrozenClock(NOW+timedelta(days=30)),source_scopes=()),r,e).code=='REPLAY' and reader.get('task').revision==4,'WORK_HISTORICAL_REPLAY')
        checks.append('expired_grants_and_missing_live_account_registry_do_not_prevent_owned_historical_replay')
        deny(handler(),r,e,audit='wrong-audit',code='REQUEST_ID_CONTENT_CONFLICT')
        checks.append('same_command_id_with_changed_audit_or_transaction_content_is_not_silently_rebound')

        c,cg,ce=setup('explicit-u',user_remaining_seconds=0);co=submit(handler(cg),c,ce)
        require(co.code=='COMMITTED' and reader.get('task').aggregate.as_record()['effort']['user_remaining']['seconds']==0
            and reader.get('task').aggregate.as_record()['core']['completion']=='INCOMPLETE','WORK_EXPLICIT_U')
        checks.append('explicit_zero_u_and_actual_increment_publish_together_without_asserting_completion')
        before=state();require(submit(handler(),c,ce).code=='REPLAY' and state()==before,'WORK_U_REPLAY')
        checks.append('retry_of_report_with_u_creates_no_second_remaining_observation_or_verification')
        c,cg,ce=setup('unknown-u',user_remaining_seconds=None);require(submit(handler(cg),c,ce).code=='COMMITTED'
            and reader.get('task').aggregate.as_record()['effort']['user_remaining'] is None,'WORK_NULL_U')
        checks.append('explicit_unknown_u_retains_old_known_estimate_in_history_without_inventing_zero')
        start='2025-12-31T20:00:00.123456-03:00';c,cg,ce=setup('session',seconds=42,session_started_at=start)
        co=submit(handler(cg),c,ce);require(co.code=='COMMITTED' and co.value.record.report.as_record()['session_started_at']==start
            and co.value.record.report.as_record()['session_ended_at'] is None,'WORK_PARTIAL_SESSION')
        checks.append('explicit_session_offset_microseconds_are_lossless_and_unreported_end_stays_unknown')
        c,cg,ce=setup('future-session',session_ended_at=NOW.isoformat());deny(handler(cg),c,ce,'WORK_REPORT_FUTURE_SESSION')
        checks.append('future_or_planned_session_time_cannot_become_actual_work')
        planned=c.as_record();planned['planned_block_ref']='synthetic-block'
        deny(handler(cg),c,ce,'WORK_REPORT_SHAPE_UNSUPPORTED',raw=canonical(planned).encode())
        checks.append('planned_block_reference_and_other_unknown_fields_fail_closed_before_writes')

        for name,options,expected in (
            ('missing-registry',dict(registered=False),'AUTHORITY_REGISTERED_SCOPE_MISMATCH'),
            ('inactive',dict(active=False),'INACTIVE_AUTHORITY'),
            ('calendar',dict(source_kind='CALENDAR'),'WORK_REPORT_USER_SOURCE_REQUIRED'),
            ('future-source',dict(captured=NOW+timedelta(seconds=1)),'WORK_REPORT_SOURCE_TIME_REQUIRED')):
            c,cg,ce=setup(name,**options);deny(handler(cg),c,ce,expected)
        checks.append('unregistered_inactive_external_and_future_source_authority_never_publish_actual_work')
        c,cg,ce=setup('no-grant');deny(handler(),c,ce,'UNREGISTERED_AUTHORITY')
        deny(handler(cg,source_scopes=()),c,ce,'EVIDENCE_SOURCE_SCOPE_NOT_AUTHORIZED')
        deny(handler(cg,source_scopes=(replace(SCOPE,account_ref='wrong'),)),c,ce,'EVIDENCE_SOURCE_SCOPE_NOT_REGISTERED')
        checks.append('source_capture_and_raw_payload_do_not_replace_independent_exact_grant_and_account_scope')
        for caller in (CallerIdentity('principal','USER_COMMAND',False),CallerIdentity('other','USER_COMMAND',True),CallerIdentity('principal','EXTERNAL',True)):
            deny(handler(cg),c,ce,'UNTRUSTED_CALLER',caller=caller)
        checks.append('unauthenticated_external_and_wrong_principal_transport_is_rejected')
        c,cg,ce=setup('stale-task',target_ref=dict(task_id='task',revision=1));deny(handler(cg),c,ce,'STALE_STATE_VERSION')
        c,cg,ce=setup('stale-store');deny(handler(cg),c,ce-1,'STALE_STORE_REVISION')
        checks.append('stale_task_and_store_versions_cannot_mutate_observations_or_audits')

        legacy=create('legacy');source=evidence('legacy-actual')
        with harness.target(database,'migration').connect() as owner:
            owner.execute('INSERT INTO whattodo.effort_observation VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)',
                ('legacy-observation','legacy','ACTUAL_WORK',500,NOW-timedelta(minutes=1),NOW,source,'create-grant-legacy',None,'create-legacy'))
        c,cg,ce=setup('legacy-cumulative',task='legacy',mode='CUMULATIVE',seconds=800);co=submit(handler(cg),c,ce)
        require(co.code=='COMMITTED' and co.value.record.as_record()['increment_seconds']==300 and work.total('legacy')==800,'WORK_LEGACY_TOTAL')
        checks.append('existing_actual_increment_rows_contribute_once_to_cumulative_settlement')
        c,cg,ce=setup('legacy-identity',task='legacy',observation_id='legacy-observation')
        deny(handler(cg),c,ce,'WORK_REPORT_LEGACY_OBSERVATION_ID_UNAVAILABLE')
        checks.append('legacy_observation_without_full_report_metadata_is_not_guessed_or_overwritten')
        create('huge');c,cg,ce=setup('huge',task='huge',seconds=2**80);co=submit(handler(cg),c,ce)
        require(co.code=='COMMITTED' and work.total('huge')==2**80,'WORK_BIG_SECONDS')
        checks.append('actual_seconds_larger_than_bigint_roundtrip_through_numeric_domain_and_full_audit')

        create('completed');confirm('complete-task','COMPLETE','completed');c,cg,ce=setup('historic-completed',task='completed')
        require(submit(handler(cg),c,ce).code=='COMMITTED' and reader.get('completed').aggregate.as_record()['effort']['user_remaining']['seconds']==0
            and reader.get('completed').aggregate.as_record()['core']['completion']=='COMPLETE','WORK_COMPLETED_HISTORY')
        c,cg,ce=setup('completed-positive-u',task='completed',user_remaining_seconds=1);deny(handler(cg),c,ce,'WORK_REPORT_COMPLETED_U_CONFLICT')
        checks.append('historical_work_on_completed_task_preserves_zero_u_and_cannot_reopen_implicitly')
        create('cancelled');confirm('cancel-task','CANCEL','cancelled');c,cg,ce=setup('historic-cancelled',task='cancelled')
        require(submit(handler(cg),c,ce).code=='COMMITTED' and reader.get('cancelled').aggregate.as_record()['core']['disposition']=='CANCELLED'
            and reader.get('cancelled').aggregate.as_record()['effort']['user_remaining']['seconds']==600,'WORK_CANCELLED_HISTORY')
        checks.append('cancelled_task_can_retain_reported_work_without_restoration_or_u_subtraction')

        create('expired',requiredness='EXPIRING');source=evidence('expiry-fixture')
        with harness.target(database,'migration').connect() as owner:
            owner.execute('INSERT INTO whattodo.expiration_notice VALUES(%s,%s,%s,%s,%s,%s,%s)',('notice-expired','expired',1,'class-start',source,NOW,'create-expired'))
        v=reader.get('expired').aggregate.as_record();v['core']['revision']=v['effort']['task_revision']=2
        v['core']['disposition']=v['effort']['disposition']='EXPIRED';v['core']['expiration']['notice_ref']='notice-expired'
        req=CommitRequest(RequestContext('expiry-fixture','correlation'),CALLER.principal_id,epoch(),(RecordWrite(AggregateKey('TASK','expired'),1,canonical(v)),),'audit-expiry-fixture',source)
        permit=TransactionPermit('permit-expiry-fixture',CALLER.principal_id,CALLER.origin,req.fingerprint,NOW,NOW+timedelta(minutes=5))
        require(PostgresTransactionCoordinator(conn,codec,plan,application_version=__version__,clock=CLOCK,permits=(permit,),bindings=(('expired',TaskStorageBindings(notice_task_revision=1)),)).commit(
            req,caller=CALLER,permit_ref=permit.permit_ref).code=='COMMITTED','WORK_EXPIRY_FIXTURE')
        for n in range(2):
            c,cg,ce=setup('expired-work-'+str(n),task='expired');require(submit(handler(cg),c,ce).code=='COMMITTED','WORK_EXPIRED_APPEND')
        require(reader.get('expired').aggregate.as_record()['core']['disposition']=='EXPIRED' and conn.execute(
            "SELECT notice_task_revision FROM whattodo.task_revision WHERE task_id='expired' AND revision=4").fetchone()==(1,),'WORK_EXPIRY_BINDING')
        checks.append('successive_expired_task_reports_preserve_original_notice_revision_and_positive_u')
        c,cg,ce=setup('foreign-stage',task='task',stage_id='nonexistent-stage');deny(handler(cg),c,ce,'WORK_REPORT_STAGE_OWNER_REQUIRED')
        checks.append('unregistered_or_foreign_stage_cannot_be_attached_to_reported_task')

        class Fault:
            def __init__(self,real,trigger):self.real=real;self.trigger=trigger;self.fired=False
            def __getattr__(self,name):return getattr(self.real,name)
            def execute(self,sql,*args,**kw):
                result=self.real.execute(sql,*args,**kw)
                rendered=sql if isinstance(sql,str) else sql.as_string(self.real)
                if not self.fired and self.trigger(rendered,args):
                    self.fired=True;raise psycopg.OperationalError('synthetic interruption')
                return result
        for suffix,trigger in (
            ('task',lambda sql,args:isinstance(sql,str) and sql.startswith('INSERT INTO') and 'task_payload_revision' in sql),
            ('actual',lambda sql,args:isinstance(sql,str) and sql.startswith('INSERT INTO whattodo.effort_observation') and args and args[0][2]=='ACTUAL_WORK'),
            ('report',lambda sql,args:isinstance(sql,str) and sql.startswith('INSERT INTO whattodo.actual_work_report'))):
            c,cg,ce=setup('fault-'+suffix,user_remaining_seconds=1200);proxy=Fault(conn,trigger)
            deny(handler(cg,connection=proxy),c,ce,'TRANSACTION_NOT_COMMITTED');require(proxy.fired,'WORK_FAULT_NOT_FIRED')
            checks.append('failure_after_'+suffix+'_insert_rolls_back_task_u_actual_report_audits_receipt_and_epoch')
            require(submit(handler(cg),c,ce).code=='COMMITTED','WORK_FAILURE_RETRY')
        checks.append('same_request_retry_after_each_partial_failure_commits_exactly_once')

        class LostAck:
            def __init__(self,real):self.real=real;self.staged=False
            def __getattr__(self,name):return getattr(self.real,name)
            def execute(self,sql,*args,**kw):
                result=self.real.execute(sql,*args,**kw)
                if isinstance(sql,str) and sql.startswith('INSERT INTO whattodo.actual_work_report'):self.staged=True
                return result
            def transaction(self):
                wrapped=self.real.transaction();proxy=self
                class Transaction:
                    def __enter__(self):return wrapped.__enter__()
                    def __exit__(self,kind,error,traceback):
                        value=wrapped.__exit__(kind,error,traceback)
                        if kind is None and proxy.staged:proxy.staged=False;raise psycopg.OperationalError('synthetic lost ack')
                        return value
                return Transaction()
        c,cg,ce=setup('lost-ack');before_total=work.total('task');out=submit(handler(cg,connection=LostAck(conn)),c,ce)
        require(out.status=='UNKNOWN' and out.code=='COMMIT_ACKNOWLEDGEMENT_LOST' and work.total('task')==before_total+300,'WORK_ACK_CLASSIFICATION')
        before=state();require(submit(handler(),c,ce).code=='REPLAY' and state()==before,'WORK_ACK_REPLAY')
        checks.append('lost_commit_ack_is_unknown_and_owned_retry_recovers_two_record_receipt_without_double_work')

        create('race');a,ag,ae=setup('race-a',task='race');b,bg,be=setup('race-b',task='race',mode='CUMULATIVE',seconds=600)
        barrier=Barrier(2)
        def race(r,g,e):
            with harness.target(database).connect() as fresh:
                h=handler(g,connection=fresh);barrier.wait(timeout=30);return submit(h,r,e)
        with ThreadPoolExecutor(max_workers=2) as pool:
            futures=[pool.submit(race,a,ag,ae),pool.submit(race,b,bg,be)];results=[f.result(timeout=60) for f in futures]
        require(sum(r.code=='COMMITTED' for r in results)==1 and all(r.status in ('SUCCESS','CONFLICT','RETRYABLE') for r in results)
            and reader.get('race').revision==2 and work.total('race') in (300,600) and epoch()==ae+1,'WORK_CONCURRENT_CAS')
        checks.append('simultaneous_reports_publish_one_epoch_and_exact_total_without_lost_update')
        create('same-race');c,cg,ce=setup('race-same',task='same-race');barrier=Barrier(2)
        with ThreadPoolExecutor(max_workers=2) as pool:
            futures=[pool.submit(race,c,cg,ce) for _ in range(2)];results=[f.result(timeout=60) for f in futures]
        require(sum(r.code=='COMMITTED' for r in results)==1 and work.total('same-race')==300 and reader.get('same-race').revision==2,'WORK_CONCURRENT_DUPLICATE')
        require(submit(handler(),c,ce).code=='REPLAY','WORK_CONCURRENT_RECOVERY')
        checks.append('simultaneous_identical_observation_is_counted_once_and_retry_reconciles_original_receipt')
        for table in ('actual_work_report','effort_observation'):
            for verb in ('UPDATE','DELETE','TRUNCATE'):
                sql='UPDATE whattodo.'+table+' SET observation_id=observation_id' if verb=='UPDATE' else verb+' '+('FROM ' if verb=='DELETE' else '')+'whattodo.'+table
                try:
                    with conn.transaction():conn.execute(sql)
                except (psycopg.errors.CheckViolation,psycopg.errors.InsufficientPrivilege):pass
                else:require(False,'WORK_HISTORY_MUTABLE')
        checks.append('application_cannot_update_delete_or_truncate_actual_report_and_increment_history')
        with harness.target(database,'migration').connect() as owner:
            for table in ('actual_work_report','effort_observation'):
                try:
                    with owner.transaction():owner.execute('TRUNCATE whattodo.'+table+' CASCADE')
                except psycopg.errors.CheckViolation:pass
                else:require(False,'WORK_OWNER_HISTORY_MUTABLE')
        checks.append('schema_owner_truncate_is_also_blocked_by_append_only_history_guard')
    with harness.target(database).connect() as fresh:
        restarted=PostgresWorkReportHandler(fresh,codec,plan,application_version=__version__,clock=FrozenClock(NOW+timedelta(days=30)))
        result=restarted.report(r.payload_json.encode(),RequestContext(r.command_id,'restart'),expected_store_revision=e,audit_id='audit-'+r.command_id,caller=CALLER)
        require(result.code=='REPLAY' and result.value.receipt==receipt,'WORK_RESTART_REPLAY')
        checks.append('fresh_connection_restart_validates_full_historical_report_and_original_task_version')
        report.update(migration_steps=len(plan.steps),schema_version=plan.schema_version,
            domain_tables=fresh.execute("SELECT count(*) FROM pg_tables WHERE schemaname='whattodo'").fetchone()[0],
            domain_foreign_keys=fresh.execute("SELECT count(*) FROM pg_constraint c JOIN pg_namespace n ON n.oid=c.connamespace WHERE n.nspname='whattodo' AND c.contype='f'").fetchone()[0])
        require((report['domain_tables'],report['domain_foreign_keys'])==(89,230),'WORK_SCHEMA_COUNT')


def main():
    harness=PostgresHarness();report=dict(task='M3A-15',status='IN_PROGRESS',scope='SYNTHETIC_USER_REPORTED_ACTUAL_WORK',verified_on='2026-10-10',native_checks=[])
    try:
        with harness:verify(harness,report)
        report.update(status='PASS',native_check_count=len(report['native_checks']),limitations=[
            'Independent caller/account/grant and expiry fixture inputs are synthetic; no live transport or collectors',
            'Cumulative settlement is Task-wide in publication order; negative corrections and counter resets require a future explicit operation',
            'No unreported session bounds, stage U/status changes or completion timestamp are inferred'])
    except Exception as exc:
        report.update(status='FAIL',failure_type=type(exc).__name__,failure_code=str(exc) if isinstance(exc,HarnessError) else 'WORK_NATIVE_CHECK_FAILED',failure_sqlstate=getattr(exc,'sqlstate',None))
    report['harness']=harness.safe_summary();target=harness.run_root/'work-report.json'
    if harness.run_root.exists():target.write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(dict(status=report['status'],report=str(target),checks=len(report['native_checks']),server_stopped=report['harness']['server_stopped'])))
    return 0 if report['status']=='PASS' else 1


if __name__=='__main__':raise SystemExit(main())
