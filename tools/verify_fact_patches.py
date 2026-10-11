"""Isolated native fact-patch authority, CAS, supporting facts and replay."""
from copy import deepcopy
from concurrent.futures import ThreadPoolExecutor
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
from src.adapters.git_definitions import GitDefinitionSource
from src.adapters.postgres_definitions import PostgresDefinitionRepository
from src.adapters.migration_files import load_migration_plan
from src.adapters.memory_definitions import MemoryDefinitionRepository
from src.adapters.postgres_authorization import register_grant
from src.adapters.postgres_evidence import PostgresEvidenceRepository,register_source_scope
from src.adapters.postgres_fact_patches import PostgresFactPatchHandler,register_fact_patch_grant
from src.adapters.postgres_manual_tasks import PostgresManualTaskHandler
from src.adapters.postgres_migrations import DatabaseRoles,apply_migrations
from src.adapters.postgres_tasks import PostgresTaskRepository
from src.adapters.postgres_transactions import PostgresTransactionCoordinator
from src.application.definitions import canonical
from src.application.evidence_storage import SourceScope
from src.application.fact_patches import FactPatch,FactPatchGrant
from src.application.manual_tasks import ResolvedManualIntent
from src.application.ports import AggregateKey,CommitRequest,RecordWrite,RequestContext,TransactionPermit
from src.application.task_storage import TaskStorageBindings
from src.domain.authorization import AuthorityGrant,CallerIdentity,Command,change
from src.domain.provenance import capture_source
from tools.postgres_harness import HarnessError,PostgresHarness,ROLES,require
from tools.verify_transactions import TABLES
from tools.git_definition_fixture import GitDefinitionFixture
from tools.verify_definition_repository import request as definition_request

NOW=datetime(2026,1,1,tzinfo=timezone.utc);CLOCK=FrozenClock(NOW)
CALLER=CallerIdentity('principal','USER_COMMAND',True);SCOPE=SourceScope('synthetic-fact-patch','scope','account')
DIMS=dict(thinking_depth=2,repetitive_volume=2,new_learning_load=3)


def verify(harness,report):
    import psycopg
    plan=load_migration_plan(root=ROOT);codec=ContractJSONCodec(load_supported_schemas(root=ROOT))
    roles=DatabaseRoles(ROLES['migration'],ROLES['application'],ROLES['test']);database=harness.create_database(initialize_schema=False)
    checks=report['native_checks']
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
        def evidence(name,kind='USER'):
            raw=('synthetic source '+name).encode()
            s=capture_source(provider=SCOPE.provider,scope_ref=SCOPE.scope_ref,external_id=name,raw_bytes=raw,
                captured_at=NOW-timedelta(minutes=1),source_type=kind)
            out=PostgresEvidenceRepository(conn,codec,plan,application_version=__version__,clock=CLOCK,scopes=(SCOPE,)).observe_source(
                canonical(s.as_record()).encode(),raw_content=raw,locator_ref='synthetic-'+name)
            return s.record_id
        def create(name,requiredness='OPTIONAL',condition=None,*,facts=None,definitions=None):
            fields=dict(title='Synthetic '+name,importance=3,difficulty=DIMS,requiredness=requiredness)
            if condition:fields['expiration_condition_ref']=condition
            c=Command('create-'+name,'principal','USER_COMMAND','create-grant-'+name,(change(name,None,'CREATE_TASK',fields),))
            source=evidence('create-'+name);g=AuthorityGrant(c.authority_ref,'principal','USER_COMMAND',c.command_id,c.changes,
                source,NOW-timedelta(minutes=1),expires_at=NOW+timedelta(hours=1))
            with harness.target(database,'migration').connect() as owner:register_grant(owner,g,plan,application_version=__version__)
            intent=ResolvedManualIntent(c.fingerprint,source,NOW-timedelta(seconds=30),canonical(facts or dict(domain='other')))
            out=PostgresManualTaskHandler(conn,codec,plan,application_version=__version__,clock=CLOCK,
                definitions=definitions or MemoryDefinitionRepository(CLOCK),intents=(intent,),grants=(g,),source_scopes=(SCOPE,)).create(canonical(c.as_record()).encode(),
                RequestContext(c.command_id,'correlation-'+c.command_id),expected_store_revision=epoch(),audit_id='audit-'+c.command_id,caller=CALLER)
            require(out.status=='SUCCESS' and out.code=='COMMITTED','FACT_SETUP_'+out.code)
            return reader.get(name)
        def setup(name,fields,task='task',revision=None,*,observed=NOW,kind='USER',active=True,registered=True):
            p=FactPatch(name,'principal','grant-'+name,task,revision or reader.get(task).revision,canonical(fields))
            g=FactPatchGrant(p,evidence(name,kind),NOW-timedelta(minutes=1),NOW+timedelta(hours=1),observed,active)
            if registered:
                with harness.target(database,'migration').connect() as owner:register_fact_patch_grant(owner,g,plan,application_version=__version__)
            return p,g,epoch()
        def handler(g=None,**kw):
            options=dict(application_version=__version__,clock=CLOCK,grants=(g,) if g else (),source_scopes=(SCOPE,));options.update(kw)
            return PostgresFactPatchHandler(options.pop('connection',conn),codec,plan,**options)
        def submit(h,p,e,*,caller=CALLER,audit=None,raw=None,context=None):
            return h.patch(raw or canonical(p.as_record()).encode(),context or RequestContext(p.command_id,'correlation-'+p.command_id),
                expected_store_revision=e,audit_id=audit or 'audit-'+p.command_id,caller=caller)
        def deny(h,p,e,code,**kw):
            before=state();out=submit(h,p,e,**kw)
            require(out.status in ('PERMANENT','CONFLICT','RETRYABLE') and out.code==code,'FACT_NEGATIVE_'+out.code)
            require(state()==before,'FACT_NEGATIVE_MUTATION');return out
        original=create('task');checks.append('fact_handler_updates_an_existing_source_authorized_task')
        p,g,e=setup('explicit',dict(title='Changed title',importance=5,difficulty=dict(thinking_depth=3,repetitive_volume=4,new_learning_load=3),
            deadline='2026-10-13T13:30:00.123456+08:00',user_remaining_seconds=2400,requiredness='REQUIRED'))
        before=state();out=submit(handler(g),p,e)
        require(out.status=='SUCCESS' and out.code=='COMMITTED','FACT_COMMIT_'+out.code);receipt=out.value
        task=reader.get('task');value=task.aggregate.as_record();deadline=value['timing']['deadline']
        require(task.revision==2 and epoch()==e+1 and reader.get('task',1)==original,'FACT_HISTORY')
        checks.append('single_patch_atomically_advances_task_and_store_once_with_full_before_after_audit')
        require(value['work']==original.aggregate.as_record()['work'] and value['stage_details']==[] and
            value['core']['completion']=='INCOMPLETE' and value['core']['disposition']=='ACTIVE','FACT_UNREQUESTED_EFFECT')
        checks.append('unrelated_work_stages_completion_disposition_and_original_revision_are_preserved')
        due=conn.execute('SELECT input_kind,original_value,due_at,original_date,default_policy_ref,default_timezone FROM whattodo.normalized_due WHERE due_id=%s',
            (deadline['due_ref'],)).fetchone()
        require(due==('EXPLICIT_INSTANT',p.fields['deadline'],datetime.fromisoformat(p.fields['deadline']),None,None,None),'FACT_EXPLICIT_TIME')
        checks.append('explicit_offset_microsecond_deadline_is_preserved_without_date_only_default')
        u=value['effort']['user_remaining'];observation=conn.execute('SELECT kind,seconds,observed_at,source_record_ref,authority_ref,transaction_ref FROM whattodo.effort_observation WHERE observation_id=%s',
            (u['observation_id'],)).fetchone()
        require(observation==('USER_REMAINING',2400,NOW,g.evidence_ref,p.authority_ref,p.command_id),'FACT_U_SOURCE')
        checks.append('remaining_observation_and_immutable_due_commit_with_task_under_exact_source_grant')
        require(all(dict(field=field,source_ref=g.evidence_ref) in value['provenance'] for field in
            ('/core/title','/core/importance','/core/difficulty','/core/requiredness','/timing/deadline','/effort/user_remaining')),'FACT_PROVENANCE')
        checks.append('each_explicit_fact_retains_its_independent_user_evidence_source')
        before=state();replay=submit(handler(clock=FrozenClock(NOW+timedelta(days=7)),source_scopes=()),p,e)
        require(replay.code=='REPLAY' and replay.value==receipt and state()==before,'FACT_REPLAY_'+replay.code)
        checks.append('replay_returns_original_receipt_without_active_grants_source_registry_or_current_time')
        deny(handler(),replace(p,fields_json=canonical(dict(importance=1))),e,'FACT_PATCH_REPLAY_SCOPE_CONFLICT')
        deny(handler(),p,e+1,'REQUEST_ID_CONTENT_CONFLICT');deny(handler(),p,e,'REQUEST_ID_CONTENT_CONFLICT',audit='different-audit')
        deny(handler(),p,e,'UNTRUSTED_CALLER',caller=CallerIdentity('intruder','USER_COMMAND',True))
        checks.append('replay_cannot_change_user_identity_semantics_original_epoch_or_audit')

        p2,g2,e2=setup('date-only',dict(deadline='2026-10-20'));out=submit(handler(g2),p2,e2)
        require(out.code=='COMMITTED','FACT_DATE_'+out.code);v=reader.get('task').aggregate.as_record()
        require(v['timing']['deadline']['value']['instant']=='2026-10-20T23:59:00+08:00','FACT_DATE_DEFAULT')
        checks.append('date_only_deadline_uses_explicit_beijing_2359_policy_and_retains_original_date')
        before=state();again=submit(handler(),p,e)
        require(again.code=='REPLAY' and again.value==receipt and state()==before and reader.get('task').revision==3,'FACT_OLD_REPLAY')
        checks.append('old_patch_replay_after_newer_edits_neither_reverts_head_nor_duplicates_supporting_facts')
        x,xg,xe=setup('clear',dict(deadline=None,user_remaining_seconds=None));old_due_count=conn.execute('SELECT count(*) FROM whattodo.normalized_due').fetchone()[0]
        require(submit(handler(xg),x,xe).code=='COMMITTED','FACT_CLEAR')
        v=reader.get('task').aggregate.as_record()
        require(v['timing']['deadline'] is None and v['effort']['user_remaining'] is None and
            conn.execute('SELECT count(*) FROM whattodo.normalized_due').fetchone()[0]==old_due_count,'FACT_CLEAR_HISTORY')
        checks.append('explicit_clear_sets_current_unknown_without_deleting_previous_deadlines_or_estimates')
        x,xg,xe=setup('zero',dict(user_remaining_seconds=0));require(submit(handler(xg),x,xe).code=='COMMITTED','FACT_ZERO')
        require(reader.get('task').aggregate.as_record()['core']['completion']=='INCOMPLETE','FACT_ZERO_COMPLETED')
        checks.append('zero_remaining_is_a_known_user_observation_and_never_implicit_completion')

        negatives=[('stale',dict(importance=1),dict(revision=1),'STALE_STATE_VERSION'),
            ('unknown-target',dict(importance=2),dict(task='missing',revision=1),'UNKNOWN_TARGET'),
            ('unregistered',dict(importance=2),dict(registered=False),'AUTHORITY_REGISTERED_SCOPE_MISMATCH'),
            ('inactive',dict(importance=2),dict(active=False),'INACTIVE_AUTHORITY'),
            ('future',dict(user_remaining_seconds=5),dict(observed=NOW+timedelta(seconds=1)),'FACT_PATCH_FUTURE_OBSERVATION'),
            ('missing-time',dict(user_remaining_seconds=5),dict(observed=None),'FACT_PATCH_OBSERVATION_TIME_REQUIRED'),
            ('external-evidence',dict(importance=2),dict(kind='CALENDAR'),'FACT_PATCH_USER_SOURCE_REQUIRED'),
            ('expiring-missing',dict(requiredness='EXPIRING'),{},'FACT_PATCH_EXPIRATION_CONDITION_REQUIRED')]
        for name,fields,options,code in negatives:
            x,xg,xe=setup(name,fields,**options);deny(handler(xg),x,xe,code);checks.append('rejects_'+name.replace('-','_')+'_without_any_canonical_mutation')
        x,xg,xe=setup('fresh-scope',dict(importance=2))
        deny(handler(),x,xe,'UNREGISTERED_AUTHORITY')
        deny(handler(xg),replace(x,fields_json=canonical(dict(importance=1))),xe,'FACT_PATCH_EXACT_SCOPE_MISMATCH')
        deny(handler(xg),x,xe-1,'STALE_STORE_REVISION')
        deny(handler(xg),x,xe,'UNTRUSTED_CALLER',caller=CallerIdentity('principal','EXTERNAL',True))
        deny(handler(xg),x,xe,'UNTRUSTED_CALLER',context=RequestContext('another-command','correlation'))
        checks.append('fresh_patch_requires_independent_exact_grant_authenticated_user_and_current_global_epoch')
        deny(handler(replace(xg,evidence_ref=g.evidence_ref)),x,xe,'AUTHORITY_REGISTERED_SCOPE_MISMATCH')
        checks.append('persisted_root_scope_cannot_be_substituted_with_a_different_user_source')
        deny(handler(xg,source_scopes=()),x,xe,'FACT_PATCH_VALIDATION_FAILED')
        deny(handler(xg,source_scopes=(replace(SCOPE,account_ref='other-account'),)),x,xe,'FACT_PATCH_VALIDATION_FAILED')
        checks.append('user_source_type_and_root_grant_do_not_bypass_independent_registered_account_scope')
        v=x.as_record();v['fields']['completion']='COMPLETE';deny(handler(xg),x,xe,'FACT_PATCH_SHAPE_UNSUPPORTED',raw=canonical(v).encode())
        v=x.as_record();v['schema_version']='future';deny(handler(xg),x,xe,'FACT_PATCH_SHAPE_UNSUPPORTED',raw=canonical(v).encode())
        checks.append('wire_version_and_field_allowlist_refuse_lifecycle_or_hidden_effects')

        x,xg,xe=setup('atomic-failure',dict(deadline='2026-10-20T13:00:00Z',user_remaining_seconds=600))
        class FailTaskInsert:
            def __getattr__(self,name):return getattr(conn,name)
            def execute(self,query,*args,**kw):
                text=query if isinstance(query,str) else query.as_string(conn)
                if text.startswith('INSERT INTO whattodo.') and '"task_revision"' in text:
                    require(conn.execute('SELECT count(*) FROM whattodo.normalized_due WHERE due_id LIKE %s',('due-%',)).fetchone()[0]==old_due_count+1,
                        'FACT_FAILURE_BEFORE_DUE_STAGED')
                    conn.execute('SELECT 1/0')
                return conn.execute(query,*args,**kw)
        deny(handler(xg,connection=FailTaskInsert()),x,xe,'TRANSACTION_DATABASE_REJECTED')
        checks.append('real_sql_failure_after_due_and_u_staging_rolls_back_task_support_facts_authority_audit_receipt_and_epoch')
        require(submit(handler(xg),x,xe).code=='COMMITTED','FACT_RETRY_FAILED_PATCH')
        checks.append('rollback_retry_with_same_request_commits_once_and_does_not_leave_partial_identity')
        due_ref=reader.get('task').aggregate.as_record()['timing']['deadline']['due_ref'];u_ref=reader.get('task').aggregate.as_record()['effort']['user_remaining']['observation_id']
        for table,column,key in (('normalized_due','due_id',due_ref),('effort_observation','observation_id',u_ref)):
            try:
                with conn.transaction():conn.execute('DELETE FROM whattodo.'+table+' WHERE '+column+'=%s',(key,))
            except psycopg.errors.CheckViolation:pass
            else:require(False,'FACT_SUPPORT_HISTORY_MUTABLE')
        checks.append('deadline_and_remaining_support_history_cannot_be_deleted_or_rewritten')

        definitions=PostgresDefinitionRepository(conn,GitDefinitionSource(fixture.root),plan,roles,application_version=__version__)
        course=create('course-task',facts=dict(domain='study',context=dict(kind='COURSE',id='synthetic-course'),
            profile_ref=dict(kind='COURSE_PROFILE',id='synthetic-course',version='1')),definitions=definitions)
        prior_profile=conn.execute('SELECT profile_ref FROM whattodo.task_payload_revision WHERE task_id=%s AND task_revision=1',('course-task',)).fetchone()
        x,xg,xe=setup('course-edit',dict(importance=5),task='course-task');require(submit(handler(xg),x,xe).code=='COMMITTED','FACT_COURSE_EDIT')
        require(conn.execute('SELECT profile_ref FROM whattodo.task_payload_revision WHERE task_id=%s AND task_revision=2',('course-task',)).fetchone()==prior_profile
            and reader.get('course-task').aggregate.as_record()['core']['context']==course.aggregate.as_record()['core']['context'],'FACT_PROFILE_REBOUND')
        checks.append('course_patch_preserves_exact_git_profile_version_and_course_context')

        create('race-task');a,ag,ae=setup('race-a',dict(importance=2),task='race-task')
        b,bg,be=setup('race-b',dict(importance=5),task='race-task');require(ae==be,'FACT_RACE_EPOCH')
        barrier=Barrier(2)
        def race(patch,grant,expected):
            with harness.target(database).connect() as competing:
                local=handler(grant,connection=competing);barrier.wait(timeout=30)
                return submit(local,patch,expected)
        with ThreadPoolExecutor(max_workers=2) as pool:
            futures=[pool.submit(race,a,ag,ae),pool.submit(race,b,bg,be)]
            results=[f.result(timeout=60) for f in futures]
        require(sum(r.code=='COMMITTED' for r in results)==1 and all(r.status in ('SUCCESS','CONFLICT','RETRYABLE') for r in results)
            and reader.get('race-task').revision==2 and epoch()==ae+1,'FACT_RACE_PUBLICATION')
        checks.append('simultaneous_fact_writers_publish_one_correction_and_refuse_stale_or_busy_competitor')

        # Synthetic setup exercises preserved notice binding; it is not a live
        # lifecycle transition endpoint or an assertion of delivered transport.
        expired=create('expired','EXPIRING','class-start');source=evidence('expiry-setup')
        with harness.target(database,'migration').connect() as owner:
            owner.execute('INSERT INTO whattodo.expiration_notice VALUES(%s,%s,%s,%s,%s,%s,%s)',
                ('expiry-notice','expired',1,'class-start',source,NOW,'create-expired'))
        v=expired.aggregate.as_record();v['core']['revision']=v['effort']['task_revision']=2
        v['core']['disposition']=v['effort']['disposition']='EXPIRED';v['core']['expiration']['notice_ref']='expiry-notice'
        req=CommitRequest(RequestContext('expire-fixture','correlation'),CALLER.principal_id,epoch(),
            (RecordWrite(AggregateKey('TASK','expired'),1,canonical(v)),),'audit-expire-fixture',source)
        permit=TransactionPermit('expiry-fixture-permit',CALLER.principal_id,CALLER.origin,req.fingerprint,NOW,NOW+timedelta(minutes=5))
        require(PostgresTransactionCoordinator(conn,codec,plan,application_version=__version__,clock=CLOCK,permits=(permit,),
            bindings=(('expired',TaskStorageBindings(notice_task_revision=1)),)).commit(req,caller=CALLER,permit_ref=permit.permit_ref).code=='COMMITTED','FACT_EXPIRED_FIXTURE')
        for idx in range(2):
            x,xg,xe=setup('expired-fact-'+str(idx),dict(importance=idx+2),task='expired')
            require(submit(handler(xg),x,xe).code=='COMMITTED','FACT_EXPIRED_EDIT')
        require(conn.execute('SELECT notice_task_revision,expiration_notice_ref FROM whattodo.task_revision WHERE task_id=%s AND revision=4',
            ('expired',)).fetchone()==(1,'expiry-notice'),'FACT_EXPIRED_NOTICE_DRIFT')
        checks.append('repeated_expired_task_fact_edits_preserve_original_delivered_notice_revision_and_disposition')
        x,xg,xe=setup('expired-conflict',dict(requiredness='REQUIRED'),task='expired')
        deny(handler(xg),x,xe,'FACT_PATCH_EXPIRED_STATE_CONFLICT');checks.append('expired_task_cannot_be_reactivated_by_requiredness_patch')

    with harness.target(database).connect() as fresh:
        before=fresh.execute('SELECT revision FROM whattodo.store_epoch').fetchone()
        restarted=PostgresFactPatchHandler(fresh,codec,plan,application_version=__version__,clock=FrozenClock(NOW+timedelta(days=30)))
        again=submit(restarted,p,e)
        require(again.code=='REPLAY' and again.value==receipt and fresh.execute('SELECT revision FROM whattodo.store_epoch').fetchone()==before,'FACT_RESTART')
        checks.append('fresh_connection_reconstructs_original_patch_without_stale_head_body_or_registry')
        report.update(migration_steps=len(plan.steps),schema_version=plan.schema_version,
            domain_tables=fresh.execute("SELECT count(*) FROM pg_tables WHERE schemaname='whattodo'").fetchone()[0],
            domain_foreign_keys=fresh.execute("SELECT count(*) FROM pg_constraint c JOIN pg_namespace n ON n.oid=c.connamespace WHERE n.nspname='whattodo' AND c.contype='f'").fetchone()[0])


def main():
    harness=PostgresHarness();report=dict(task='M3A-13',status='IN_PROGRESS',scope='SYNTHETIC_EXACT_FACT_PATCH_HANDLER',
        verified_on='2026-10-10',native_checks=[])
    try:
        with harness:verify(harness,report)
        report.update(status='PASS',native_check_count=len(report['native_checks']),limitations=[
            'Opt-in task-fact-patch contract; base command consumer does not silently accept extensions',
            'Caller, source scope and independently registered exact grant are synthetic trusted inputs',
            'Natural-language interpretation, lifecycle/work/stage handlers and deployment remain later tasks'])
    except Exception as exc:
        report.update(status='FAIL',failure_type=type(exc).__name__,failure_code=str(exc) if isinstance(exc,HarnessError) else 'FACT_NATIVE_CHECK_FAILED',
            failure_sqlstate=getattr(exc,'sqlstate',None))
    report['harness']=harness.safe_summary();target=harness.run_root/'fact-patch-report.json'
    if harness.run_root.exists():target.write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(dict(status=report['status'],report=str(target),checks=len(report['native_checks']),server_stopped=report['harness']['server_stopped'])))
    return 0 if report['status']=='PASS' else 1


if __name__=='__main__':raise SystemExit(main())
