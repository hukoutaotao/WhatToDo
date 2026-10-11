"""Native explicit completion/cancellation, stage cascade and owned replay."""
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
from src.adapters.git_definitions import GitDefinitionSource
from src.adapters.memory_definitions import MemoryDefinitionRepository
from src.adapters.migration_files import load_migration_plan
from src.adapters.postgres_authorization import PostgresCommandService,register_grant
from src.adapters.postgres_definitions import PostgresDefinitionRepository
from src.adapters.postgres_evidence import PostgresEvidenceRepository,register_source_scope
from src.adapters.postgres_lifecycle import PostgresLifecycleHandler
from src.adapters.postgres_manual_tasks import PostgresManualTaskHandler
from src.adapters.postgres_migrations import DatabaseRoles,apply_migrations
from src.adapters.postgres_tasks import PostgresTaskRepository
from src.adapters.postgres_transactions import PostgresTransactionCoordinator
from src.application.definitions import canonical
from src.application.evidence_storage import SourceScope
from src.application.manual_tasks import ResolvedManualIntent
from src.application.ports import AggregateKey,CommitRequest,RecordWrite,RequestContext,TransactionPermit
from src.application.task_storage import TaskStorageBindings,admit_storage
from src.domain.authorization import AuthorityGrant,CallerIdentity,Command,change
from src.domain.provenance import capture_source
from tools.check_contract_registry import trusted_schemas
from tools.git_definition_fixture import GitDefinitionFixture
from tools.postgres_harness import HarnessError,PostgresHarness,ROLES,require
from tools.verify_definition_repository import request as definition_request
from tools.verify_transactions import TABLES

NOW=datetime(2026,1,1,tzinfo=timezone.utc);CLOCK=FrozenClock(NOW)
CALLER=CallerIdentity('principal','USER_COMMAND',True);SCOPE=SourceScope('synthetic-lifecycle','scope','account')
DIMS=dict(thinking_depth=2,repetitive_volume=2,new_learning_load=3)


def verify(harness,report):
    import psycopg
    plan=load_migration_plan(root=ROOT);codec=ContractJSONCodec(trusted_schemas());checks=report['native_checks']
    database=harness.create_database(initialize_schema=False);roles=DatabaseRoles(ROLES['migration'],ROLES['application'],ROLES['test'])
    with harness.target(database,'migration').connect() as owner:
        apply_migrations(owner,plan,roles=roles,application_version=__version__)
        register_source_scope(owner,plan,roles,SCOPE,application_version=__version__,clock=CLOCK)
    fixture=GitDefinitionFixture(harness.run_root/'git-fixture')
    profile=dict(kind='COURSE_PROFILE',id='synthetic-course',version='1',body=dict(record_mode='SYNTHETIC'))
    commit=fixture.commit_objects({'profile.json':canonical(profile).encode()})
    with harness.target(database,'migration').connect() as owner:
        PostgresDefinitionRepository(owner,GitDefinitionSource(fixture.root),plan,roles,application_version=__version__).register(
            (definition_request(commit,'profile.json',profile),))
    with harness.target(database).connect() as conn:
        reader=PostgresTaskRepository(conn,codec,plan,application_version=__version__,clock=CLOCK)
        def epoch():return conn.execute('SELECT revision FROM whattodo.store_epoch').fetchone()[0]
        def state():return tuple(conn.execute('SELECT * FROM whattodo.'+t+' ORDER BY 1,2').fetchall() for t in TABLES+
            ('effort_observation','normalized_due','manual_creation_pending'))
        def actuals():return conn.execute("SELECT * FROM whattodo.effort_observation WHERE kind='ACTUAL_WORK' ORDER BY observation_id").fetchall()
        def evidence(name,kind='USER',captured=None):
            raw=('synthetic confirmation '+name).encode()
            source=capture_source(provider=SCOPE.provider,scope_ref=SCOPE.scope_ref,external_id=name,raw_bytes=raw,
                captured_at=captured or NOW-timedelta(minutes=1),source_type=kind)
            PostgresEvidenceRepository(conn,codec,plan,application_version=__version__,clock=CLOCK,scopes=(SCOPE,)).observe_source(
                canonical(source.as_record()).encode(),raw_content=raw,locator_ref='synthetic-'+name)
            return source.record_id
        def grant(c,source,*,active=True,registered=True):
            g=AuthorityGrant(c.authority_ref,c.principal_id,c.origin,c.command_id,c.changes,source,
                NOW-timedelta(minutes=2),expires_at=NOW+timedelta(hours=1),active=active)
            if registered:
                with harness.target(database,'migration').connect() as owner:register_grant(owner,g,plan,application_version=__version__)
            return g
        def create(name,*,requiredness='REQUIRED',course=False):
            fields=dict(title='Synthetic '+name,importance=3,requiredness=requiredness,difficulty=DIMS,user_remaining_seconds=600)
            if requiredness=='EXPIRING':fields['expiration_condition_ref']='class-start'
            c=Command('create-'+name,'principal','USER_COMMAND','create-grant-'+name,(change(name,None,'CREATE_TASK',fields),))
            source=evidence('create-'+name);g=grant(c,source)
            facts=dict(domain='study',total_estimate_seconds=1800)
            if course:facts.update(context=dict(kind='COURSE',id='synthetic-course'),profile_ref=dict(kind='COURSE_PROFILE',id='synthetic-course',version='1'))
            intent=ResolvedManualIntent(c.fingerprint,source,NOW-timedelta(minutes=1),canonical(facts))
            definitions=PostgresDefinitionRepository(conn,GitDefinitionSource(fixture.root),plan,roles,application_version=__version__) if course else MemoryDefinitionRepository(CLOCK)
            out=PostgresManualTaskHandler(conn,codec,plan,application_version=__version__,clock=CLOCK,definitions=definitions,
                grants=(g,),source_scopes=(SCOPE,),intents=(intent,)).create(canonical(c.as_record()).encode(),
                RequestContext(c.command_id,'correlation'),expected_store_revision=epoch(),audit_id='audit-'+c.command_id,caller=CALLER)
            require(out.code=='COMMITTED','LIFECYCLE_CREATE_'+out.code)
            # Existing reported actual work is a synthetic history fixture,
            # independent of completion/cancellation, never inferred by them.
            with harness.target(database,'migration').connect() as owner:
                owner.execute('INSERT INTO whattodo.effort_observation VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)',
                    ('actual-'+name,name,'ACTUAL_WORK',900,NOW-timedelta(minutes=1),NOW,source,g.grant_id,None,c.command_id))
            return reader.get(name)
        def create_staged(name):
            source=evidence('create-'+name);c=Command('create-'+name,'principal','USER_COMMAND','create-grant-'+name,
                (change(name,None,'CREATE_TASK',dict(title='Staged task')),));g=grant(c,source)
            seed=deepcopy(original.aggregate.as_record());seed['core'].update(task_id=name,context=None,title='Staged task',acceptance=dict(state='ACCEPTED',authority_ref=g.grant_id))
            seed['effort'].update(task_id=name,user_remaining=None,stages=[dict(stage_id=name+'-stage-'+str(i),completion='INCOMPLETE',weight=None,user_remaining=None) for i in range(2)])
            seed['stage_details']=[dict(stage_id=name+'-stage-'+str(i),revision=1,title='Stage '+str(i)) for i in range(2)];seed['provenance']=[]
            request=CommitRequest(RequestContext(c.command_id,'correlation'),c.principal_id,epoch(),
                (RecordWrite(AggregateKey('TASK',name),None,canonical(seed)),),'audit-'+c.command_id,source)
            require(PostgresCommandService(conn,codec,plan,application_version=__version__,clock=CLOCK,grants=(g,),source_scopes=(SCOPE,),
                seeds=(admit_storage(codec,canonical(seed).encode()),)).commit(canonical(c.as_record()).encode(),request,caller=CALLER).code=='COMMITTED',
                'LIFECYCLE_STAGE_SETUP')
            return reader.get(name)
        def setup(name,operation='COMPLETE',task='task',*,fields=None,revision=None,kind='USER',active=True,registered=True,captured=None):
            c=Command(name,'principal','USER_COMMAND','grant-'+name,(change(task,revision or reader.get(task).revision,'UPDATE_TASK',
                fields or (dict(completion='COMPLETE') if operation=='COMPLETE' else dict(disposition='CANCELLED'))),))
            source=evidence(name,kind,captured);return c,grant(c,source,active=active,registered=registered),epoch()
        def handler(g=None,**kw):
            options=dict(application_version=__version__,clock=CLOCK,grants=(g,) if g else (),source_scopes=(SCOPE,));options.update(kw)
            return PostgresLifecycleHandler(options.pop('connection',conn),codec,plan,**options)
        def submit(h,c,e,operation='COMPLETE',*,caller=CALLER,audit=None,context=None,raw=None):
            fn=h.complete if operation=='COMPLETE' else h.cancel
            return fn(raw or canonical(c.as_record()).encode(),context or RequestContext(c.command_id,'correlation-'+c.command_id),
                expected_store_revision=e,audit_id=audit or 'audit-'+c.command_id,caller=caller)
        def deny(h,c,e,code,operation='COMPLETE',**kw):
            before=state();out=submit(h,c,e,operation,**kw)
            require(out.status in ('CONFLICT','PERMANENT','RETRYABLE') and out.code==code,'LIFECYCLE_NEGATIVE_'+out.code)
            require(state()==before,'LIFECYCLE_NEGATIVE_MUTATED');return out

        original=create('task',course=True);actual_history=actuals();c,g,e=setup('complete')
        out=submit(handler(g),c,e);require(out.code=='COMMITTED','LIFECYCLE_COMPLETE_'+out.code);receipt=out.value
        current=reader.get('task');v=current.aggregate.as_record();u=v['effort']['user_remaining']
        require(current.revision==2 and epoch()==e+1 and v['core']['completion']=='COMPLETE' and u['seconds']==0,'LIFECYCLE_COMPLETE_FACTS')
        checks.append('confirmed_complete_commits_one_task_revision_zero_u_audit_receipt_and_epoch')
        require(v['work']==original.aggregate.as_record()['work'] and actuals()==actual_history and v['core']['disposition']=='ACTIVE','LIFECYCLE_WORK_INVENTED')
        checks.append('completion_does_not_infer_actual_effort_change_total_estimate_or_rewrite_disposition')
        require(v['timing']==original.aggregate.as_record()['timing'] and v['timing']['completed_at'] is None,'LIFECYCLE_FAKE_COMPLETED_AT')
        checks.append('source_capture_time_is_remaining_confirmation_time_and_not_an_invented_work_finish_time')
        require(conn.execute('SELECT source_record_ref,authority_ref,transaction_ref,observed_at,kind FROM whattodo.effort_observation WHERE observation_id=%s',
            (u['observation_id'],)).fetchone()==(g.evidence_ref,g.grant_id,c.command_id,NOW-timedelta(minutes=1),'USER_REMAINING'),'LIFECYCLE_ZERO_PROVENANCE')
        checks.append('zero_remaining_observation_is_bound_to_user_confirmation_source_root_authority_and_transaction')
        require(reader.get('task',1)==original,'LIFECYCLE_LOST_ORIGINAL')
        require(conn.execute('SELECT profile_ref FROM whattodo.task_payload_revision WHERE task_id=%s ORDER BY task_revision',('task',)).fetchall()[0:2]
            ==[(original_profile:=conn.execute('SELECT profile_ref FROM whattodo.task_payload_revision WHERE task_id=%s AND task_revision=1',('task',)).fetchone()[0],),(original_profile,)],
            'LIFECYCLE_PROFILE_DRIFT')
        checks.append('completed_task_preserves_original_revision_context_and_exact_course_profile')
        before=state();replay=submit(handler(clock=FrozenClock(NOW+timedelta(days=7)),source_scopes=()),c,e)
        require(replay.code=='REPLAY' and replay.value==receipt and state()==before,'LIFECYCLE_REPLAY_'+replay.code)
        checks.append('completion_retry_uses_original_history_without_live_grants_accounts_or_unexpired_permits')
        deny(handler(),replace(c,changes=(change('task',1,'UPDATE_TASK',dict(completion='COMPLETE',user_remaining_seconds=0)),)),e,'LIFECYCLE_REPLAY_SCOPE_CONFLICT')
        deny(handler(),c,e+1,'REQUEST_ID_CONTENT_CONFLICT');deny(handler(),c,e,'REQUEST_ID_CONTENT_CONFLICT',audit='different-audit')
        deny(handler(),c,e,'UNTRUSTED_CALLER',caller=CallerIdentity('intruder','USER_COMMAND',True))
        checks.append('replay_refuses_changed_meaning_principal_original_epoch_and_audit_identity')
        c2,g2,e2=setup('complete-again');observations=conn.execute('SELECT count(*) FROM whattodo.effort_observation').fetchone()
        require(submit(handler(g2),c2,e2).code=='COMMITTED' and conn.execute('SELECT count(*) FROM whattodo.effort_observation').fetchone()==observations
            and reader.get('task').aggregate.as_record()['effort']['user_remaining']==u and actuals()==actual_history,'LIFECYCLE_REPEATED_COMPLETE')
        checks.append('new_confirmation_of_already_complete_work_keeps_zero_observation_stage_and_actual_work_history')
        x,xg,xe=setup('cancel-completed','CANCEL');before_complete=reader.get('task').aggregate.as_record()
        cancellation=submit(handler(xg),x,xe,'CANCEL');require(cancellation.code=='COMMITTED','LIFECYCLE_CANCEL_COMPLETE')
        v=reader.get('task').aggregate.as_record()
        require(v['core']['disposition']=='CANCELLED' and v['core']['completion']=='COMPLETE' and v['effort']['user_remaining']==u
            and actuals()==actual_history,'LIFECYCLE_CANCELLED_COMPLETION_DRIFT')
        checks.append('cancellation_preserves_an_already_confirmed_completion_as_an_independent_dimension')
        before=state();late=submit(handler(),c,e)
        require(late.value==receipt and late.code=='REPLAY' and state()==before and reader.get('task').aggregate.as_record()['core']['disposition']=='CANCELLED',
            'LIFECYCLE_OLD_REPLAY_CHANGED_CURRENT')
        checks.append('old_completion_replay_after_cancellation_does_not_restore_a_newer_cancelled_head')
        x,xg,xe=setup('restore-required');deny(handler(xg),x,xe,'LIFECYCLE_REACTIVATION_REQUIRED')
        x,xg,xe=setup('restore-explicit',fields=dict(completion='COMPLETE',disposition='ACTIVE'))
        require(submit(handler(xg),x,xe).code=='COMMITTED' and reader.get('task').aggregate.as_record()['core']['disposition']=='ACTIVE','LIFECYCLE_EXPLICIT_RESTORE')
        checks.append('completion_of_cancelled_work_requires_an_explicit_scoped_restore_instruction')

        cancelled=create('cancel-task');old=cancelled.aggregate.as_record();a,ag,ae=setup('cancel','CANCEL','cancel-task')
        observation_count=conn.execute('SELECT count(*) FROM whattodo.effort_observation').fetchone();actual_history=actuals()
        cancel_out=submit(handler(ag),a,ae,'CANCEL');require(cancel_out.code=='COMMITTED','LIFECYCLE_CANCEL_'+cancel_out.code)
        v=reader.get('cancel-task').aggregate.as_record()
        require(v['core']['completion']=='INCOMPLETE' and v['core']['disposition']=='CANCELLED' and
            v['effort']['user_remaining']==old['effort']['user_remaining'] and conn.execute('SELECT count(*) FROM whattodo.effort_observation').fetchone()==observation_count
            and actuals()==actual_history,'LIFECYCLE_CANCEL_REWROTE_EFFORT')
        checks.append('cancelling_incomplete_work_retains_positive_remaining_and_actual_work_without_marking_complete')
        a2,ag2,ae2=setup('cancel-again','CANCEL','cancel-task');require(submit(handler(ag2),a2,ae2,'CANCEL').code=='COMMITTED'
            and conn.execute('SELECT count(*) FROM whattodo.effort_observation').fetchone()==observation_count,'LIFECYCLE_REPEAT_CANCEL')
        before=state();again=submit(handler(source_scopes=(),clock=FrozenClock(NOW+timedelta(days=7))),a,ae,'CANCEL')
        require(again.code=='REPLAY' and again.value==cancel_out.value and state()==before,'LIFECYCLE_CANCEL_REPLAY')
        checks.append('cancellation_repeat_and_owned_replay_create_no_effort_or_duplicate_observations')

        # A synthetic exact-command seed exercises native stage storage before
        # stage creation/reopening has a public handler in its later task card.
        create_staged('staged')
        z,zg,ze=setup('staged-complete',task='staged');old_stage=reader.get('staged');out=submit(handler(zg),z,ze)
        require(out.code=='COMMITTED','LIFECYCLE_STAGE_COMPLETE_'+out.code);v=reader.get('staged').aggregate.as_record()
        require(all(s['completion']=='COMPLETE' and s['user_remaining']['seconds']==0 for s in v['effort']['stages']) and
            all(d['revision']==2 for d in v['stage_details']) and reader.get('staged',1)==old_stage,'LIFECYCLE_STAGE_CASCADE')
        checks.append('parent_completion_atomically_completes_owned_stages_and_records_parent_and_each_stage_zero')
        require(conn.execute('SELECT count(*) FROM whattodo.effort_observation WHERE transaction_ref=%s',('staged-complete',)).fetchone()==(3,)
            and all(dict(field=f'/effort/stages/{i}/completion',source_ref=zg.evidence_ref) in v['provenance'] for i in range(2)),
            'LIFECYCLE_STAGE_PROVENANCE')
        checks.append('stage_completion_and_zero_remaining_have_explicit_user_source_provenance_without_inferred_work')
        z2,zg2,ze2=setup('staged-repeat',task='staged');stage_history=conn.execute('SELECT * FROM whattodo.stage_revision ORDER BY stage_id,revision').fetchall()
        require(submit(handler(zg2),z2,ze2).code=='COMMITTED' and conn.execute('SELECT * FROM whattodo.stage_revision ORDER BY stage_id,revision').fetchall()==stage_history,
            'LIFECYCLE_REPEAT_STAGE_VERSIONS')
        checks.append('repeated_parent_completion_reuses_completed_stage_versions_and_observations')
        create_staged('stage-rollback');sx,sg,se=setup('rollback-stages',task='stage-rollback')
        class FailSecondStage:
            def __getattr__(self,name):return getattr(conn,name)
            def execute(self,query,*args,**kw):
                text=query if isinstance(query,str) else query.as_string(conn)
                if text.startswith('INSERT INTO whattodo.') and '"stage_revision"' in text and args[0][0]=='stage-rollback-stage-1':
                    require(conn.execute('SELECT count(*) FROM whattodo.stage_revision WHERE stage_id=%s AND revision=2',('stage-rollback-stage-0',)).fetchone()==(1,)
                        and conn.execute('SELECT count(*) FROM whattodo.effort_observation WHERE transaction_ref=%s',('rollback-stages',)).fetchone()==(3,),
                        'LIFECYCLE_FAILURE_BEFORE_STAGE_STAGING');conn.execute('SELECT 1/0')
                return conn.execute(query,*args,**kw)
        deny(handler(sg,connection=FailSecondStage()),sx,se,'TRANSACTION_DATABASE_REJECTED')
        require(reader.get('stage-rollback').revision==1,'LIFECYCLE_PARTIAL_COMPLETION')
        checks.append('sql_failure_after_parent_and_first_stage_staging_rolls_back_all_stage_versions_and_three_zero_observations')
        require(submit(handler(sg),sx,se).code=='COMMITTED','LIFECYCLE_STAGE_RETRY')
        checks.append('staged_completion_retry_after_partial_staging_failure_publishes_one_complete_parent_and_each_stage')

        create('negative');negatives=[('stale',dict(revision=1,task='task'),'STALE_STATE_VERSION'),
            ('missing-target',dict(task='missing',revision=1),'UNKNOWN_TARGET'),('unregistered',dict(registered=False),'AUTHORITY_REGISTERED_SCOPE_MISMATCH'),
            ('inactive',dict(active=False),'INACTIVE_AUTHORITY'),('submitted',dict(kind='LEARNING_PLATFORM'),'LIFECYCLE_USER_CONFIRMATION_REQUIRED'),
            ('future-source',dict(captured=NOW+timedelta(seconds=1)),'LIFECYCLE_CONFIRMATION_TIME_REQUIRED')]
        for name,options,code in negatives:
            options.setdefault('task','negative');x,xg,xe=setup(name,**options);deny(handler(xg),x,xe,code);checks.append('refuses_'+name.replace('-','_')+'_without_any_publication')
        x,xg,xe=setup('scope-required',task='negative')
        deny(handler(),x,xe,'UNREGISTERED_AUTHORITY');deny(handler(xg),x,xe-1,'STALE_STORE_REVISION')
        deny(handler(xg,source_scopes=()),x,xe,'EVIDENCE_SOURCE_SCOPE_NOT_AUTHORIZED')
        deny(handler(xg,source_scopes=(replace(SCOPE,account_ref='other-account'),)),x,xe,'EVIDENCE_SOURCE_SCOPE_NOT_REGISTERED')
        deny(handler(xg),x,xe,'UNTRUSTED_CALLER',caller=CallerIdentity('principal','EXTERNAL',True))
        checks.append('complete_requires_exact_root_authority_authenticated_user_registered_account_and_current_store_epoch')
        mixed=replace(x,changes=(change('negative',1,'UPDATE_TASK',dict(completion='COMPLETE',title='Smuggled title')),))
        deny(handler(xg),mixed,xe,'LIFECYCLE_COMPLETION_SCOPE_REQUIRED');deny(handler(xg),x,xe,'LIFECYCLE_CANCELLATION_SCOPE_REQUIRED','CANCEL')
        checks.append('closed_endpoint_scope_cannot_smuggle_unrelated_facts_or_switch_completion_into_cancellation')
        mixed=replace(x,changes=(change('negative',1,'UPDATE_TASK',dict(completion='COMPLETE',user_remaining_seconds=0)),))
        deny(handler(xg),mixed,xe,'EXACT_CHANGE_SCOPE_MISMATCH');checks.append('changing_even_equivalent_declared_zero_requires_matching_independent_grant')

        x,xg,xe=setup('rollback',task='negative')
        class FailTaskInsert:
            def __getattr__(self,name):return getattr(conn,name)
            def execute(self,query,*args,**kw):
                text=query if isinstance(query,str) else query.as_string(conn)
                if text.startswith('INSERT INTO whattodo.') and '"task_revision"' in text:
                    require(conn.execute('SELECT count(*) FROM whattodo.effort_observation WHERE transaction_ref=%s',('rollback',)).fetchone()==(1,),
                        'LIFECYCLE_FAILURE_BEFORE_ZERO_STAGING');conn.execute('SELECT 1/0')
                return conn.execute(query,*args,**kw)
        deny(handler(xg,connection=FailTaskInsert()),x,xe,'TRANSACTION_DATABASE_REJECTED')
        checks.append('sql_failure_after_zero_staging_rolls_back_observation_task_authority_audit_receipt_and_epoch')
        require(submit(handler(xg),x,xe).code=='COMMITTED','LIFECYCLE_RETRY_AFTER_FAILURE');checks.append('same_request_retry_after_rollback_commits_once')

        create('race');ra,rga,rea=setup('race-complete',task='race');rb,rgb,reb=setup('race-cancel','CANCEL','race');require(rea==reb,'LIFECYCLE_RACE_EPOCH')
        barrier=Barrier(2)
        def race(c,g,e,operation):
            with harness.target(database).connect() as fresh:
                local=handler(g,connection=fresh);barrier.wait(timeout=30);return submit(local,c,e,operation)
        with ThreadPoolExecutor(max_workers=2) as pool:
            futures=[pool.submit(race,ra,rga,rea,'COMPLETE'),pool.submit(race,rb,rgb,reb,'CANCEL')];results=[f.result(timeout=60) for f in futures]
        require(sum(r.code=='COMMITTED' for r in results)==1 and all(r.status in ('SUCCESS','CONFLICT','RETRYABLE') for r in results)
            and reader.get('race').revision==2 and epoch()==rea+1,'LIFECYCLE_RACE')
        checks.append('simultaneous_complete_and_cancel_publish_one_version_and_reject_stale_or_busy_competitor')

        # The original expiry/notice is synthetic fixture history; neither
        # handler sends a notification or claims a real delivery occurred.
        preview=create('expired',requiredness='EXPIRING');source=evidence('expiry-fixture')
        with harness.target(database,'migration').connect() as owner:
            owner.execute('INSERT INTO whattodo.expiration_notice VALUES(%s,%s,%s,%s,%s,%s,%s)',
                ('notice-expired','expired',1,'class-start',source,NOW,'create-expired'))
        v=preview.aggregate.as_record();v['core']['revision']=v['effort']['task_revision']=2
        v['core']['disposition']=v['effort']['disposition']='EXPIRED';v['core']['expiration']['notice_ref']='notice-expired'
        req=CommitRequest(RequestContext('expiry-fixture','correlation'),CALLER.principal_id,epoch(),
            (RecordWrite(AggregateKey('TASK','expired'),1,canonical(v)),),'audit-expiry-fixture',source)
        permit=TransactionPermit('permit-expiry-fixture',CALLER.principal_id,CALLER.origin,req.fingerprint,NOW,NOW+timedelta(minutes=5))
        require(PostgresTransactionCoordinator(conn,codec,plan,application_version=__version__,clock=CLOCK,permits=(permit,),
            bindings=(('expired',TaskStorageBindings(notice_task_revision=1)),)).commit(req,caller=CALLER,permit_ref=permit.permit_ref).code=='COMMITTED','LIFECYCLE_EXPIRY_SETUP')
        x,xg,xe=setup('expired-cancel','CANCEL','expired');require(submit(handler(xg),x,xe,'CANCEL').code=='COMMITTED','LIFECYCLE_EXPIRED_CANCEL')
        require(reader.get('expired',2).aggregate.as_record()['core']['expiration']['notice_ref']=='notice-expired' and
            conn.execute('SELECT notice_task_revision,expiration_notice_ref FROM whattodo.task_revision WHERE task_id=%s AND revision=3',('expired',)).fetchone()==(None,None),
            'LIFECYCLE_EXPIRED_NOTICE_HISTORY')
        checks.append('explicit_expired_cancellation_clears_current_notice_binding_and_preserves_original_notice_history')
        x,xg,xe=setup('expired-restore',task='expired',fields=dict(completion='COMPLETE',disposition='ACTIVE'))
        require(submit(handler(xg),x,xe).code=='COMMITTED' and reader.get('expired').aggregate.as_record()['core']['completion']=='COMPLETE','LIFECYCLE_EXPIRED_RESTORE')
        checks.append('explicit_reactivation_and_completion_preserve_expiry_history_instead_of_implicitly_restoring')
        for table in ('task_revision','task_details_revision','stage_revision','effort_observation'):
            try:
                with conn.transaction():conn.execute('DELETE FROM whattodo.'+table)
            except psycopg.errors.CheckViolation:pass
            else:require(False,'LIFECYCLE_HISTORY_DELETED')
        checks.append('completion_cancellation_stage_and_actual_work_history_cannot_be_hard_deleted')

    with harness.target(database).connect() as fresh:
        before=fresh.execute('SELECT revision FROM whattodo.store_epoch').fetchone()
        restarted=PostgresLifecycleHandler(fresh,codec,plan,application_version=__version__,clock=FrozenClock(NOW+timedelta(days=30)))
        out=submit(restarted,c,e);require(out.code=='REPLAY' and out.value==receipt and fresh.execute('SELECT revision FROM whattodo.store_epoch').fetchone()==before,'LIFECYCLE_RESTART')
        checks.append('fresh_connection_replays_original_completion_without_any_live_grants_or_source_registry')
        report.update(migration_steps=len(plan.steps),schema_version=plan.schema_version,
            domain_tables=fresh.execute("SELECT count(*) FROM pg_tables WHERE schemaname='whattodo'").fetchone()[0],
            domain_foreign_keys=fresh.execute("SELECT count(*) FROM pg_constraint c JOIN pg_namespace n ON n.oid=c.connamespace WHERE n.nspname='whattodo' AND c.contype='f'").fetchone()[0])


def main():
    harness=PostgresHarness();report=dict(task='M3A-14',status='IN_PROGRESS',scope='SYNTHETIC_USER_CONFIRMED_LIFECYCLE',
        verified_on='2026-10-10',native_checks=[])
    try:
        with harness:verify(harness,report)
        report.update(status='PASS',native_check_count=len(report['native_checks']),limitations=[
            'Source capture times identify user confirmations, never actual work start/end/completion times',
            'Independent user caller/account/grant and staged/expiry/actual-work fixture history are synthetic',
            'Actual-work reports, stage editing/reopening, live transport and deployed runtime remain later cards'])
    except Exception as exc:
        report.update(status='FAIL',failure_type=type(exc).__name__,failure_code=str(exc) if isinstance(exc,HarnessError) else 'LIFECYCLE_NATIVE_CHECK_FAILED',
            failure_sqlstate=getattr(exc,'sqlstate',None))
    report['harness']=harness.safe_summary();target=harness.run_root/'lifecycle-report.json'
    if harness.run_root.exists():target.write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(dict(status=report['status'],report=str(target),checks=len(report['native_checks']),server_stopped=report['harness']['server_stopped'])))
    return 0 if report['status']=='PASS' else 1


if __name__=='__main__':raise SystemExit(main())
