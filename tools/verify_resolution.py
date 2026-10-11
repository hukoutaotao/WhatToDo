"""Native owned reference resolution, durable clarification and existing handler handoff."""
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime,timedelta,timezone
from hashlib import sha256
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
from src.adapters.memory_definitions import MemoryDefinitionRepository
from src.adapters.migration_files import load_migration_plan
from src.adapters.postgres_authorization import register_grant
from src.adapters.postgres_definitions import PostgresDefinitionRepository
from src.adapters.postgres_evidence import PostgresEvidenceRepository,register_source_scope
from src.adapters.postgres_lifecycle import PostgresLifecycleHandler
from src.adapters.postgres_manual_tasks import PostgresManualTaskHandler
from src.adapters.postgres_migrations import DatabaseRoles,apply_migrations
from src.adapters.postgres_resolution import PostgresResolutionService
from src.adapters.postgres_tasks import PostgresTaskRepository
from src.application.definitions import canonical
from src.application.direct_creation import DirectCreationNormalizer,UserInputBinding,guided_message
from src.application.evidence_storage import SourceScope
from src.application.manual_tasks import ResolvedManualIntent
from src.application.ports import RequestContext
from src.application.task_resolution import CourseLabel
from src.domain.authorization import AuthorityGrant,CallerIdentity,Command,change
from src.domain.provenance import capture_source
from tools.git_definition_fixture import GitDefinitionFixture
from tools.postgres_harness import HarnessError,PostgresHarness,ROLES,require
from tools.verify_definition_repository import request as definition_request
from tools.verify_transactions import TABLES
NOW=datetime(2026,1,1,tzinfo=timezone.utc);CLOCK=FrozenClock(NOW)
CALLER=CallerIdentity('principal','USER_COMMAND',True);OTHER=CallerIdentity('other','USER_COMMAND',True)
SCOPE=SourceScope('synthetic-resolution','scope','account');BINDINGS=(UserInputBinding('principal',SCOPE),UserInputBinding('other',SCOPE))
COURSES=(CourseLabel('synthetic-course','Physics',('phys',)),)
DIMS=dict(thinking_depth=2,repetitive_volume=2,new_learning_load=3)


def verify(harness,report):
    import psycopg
    plan=load_migration_plan(root=ROOT);codec=ContractJSONCodec(load_supported_schemas(root=ROOT));checks=report['native_checks']
    database=harness.create_database(initialize_schema=False);roles=DatabaseRoles(ROLES['migration'],ROLES['application'],ROLES['test'])
    with harness.target(database,'migration').connect() as owner:
        old=load_migration_plan(root=ROOT,manifest_path=ROOT/'reports/acceptance/M3A-21-migration-plan.json')
        apply_migrations(owner,old,roles=roles,application_version=__version__)
        prior=owner.execute('SELECT * FROM whattodo_meta.migration_history ORDER BY position').fetchall()
        upgraded=apply_migrations(owner,plan,roles=roles,application_version=__version__)
        require(upgraded.applied==tuple(step.migration_id for step in plan.steps[len(old.steps):]) and owner.execute('SELECT * FROM whattodo_meta.migration_history WHERE position<=11 ORDER BY position').fetchall()==prior,'RESOLUTION_FORWARD_UPGRADE')
        register_source_scope(owner,plan,roles,SCOPE,application_version=__version__,clock=CLOCK)
    checks.append('forward_migrations_preserve_exact_eleven_step_history_without_task_backfills')
    fixture=GitDefinitionFixture(harness.run_root/'git-fixture')
    profile=dict(kind='COURSE_PROFILE',id='synthetic-course',version='1',body=dict(record_mode='SYNTHETIC'))
    commit=fixture.commit_objects({'profile.json':canonical(profile).encode()})
    with harness.target(database,'migration').connect() as owner:
        PostgresDefinitionRepository(owner,GitDefinitionSource(fixture.root),plan,roles,application_version=__version__).register((definition_request(commit,'profile.json',profile),))
    with harness.target(database).connect() as conn:
        evidence=PostgresEvidenceRepository(conn,codec,plan,application_version=__version__,clock=CLOCK,scopes=(SCOPE,))
        reader=PostgresTaskRepository(conn,codec,plan,application_version=__version__,clock=CLOCK)
        def ctx(name):return RequestContext(name,'synthetic-correlation')
        def epoch():return conn.execute('SELECT revision FROM whattodo.store_epoch').fetchone()[0]
        def state():return tuple(conn.execute('SELECT * FROM whattodo.'+t+' ORDER BY 1,2').fetchall() for t in TABLES+('effort_observation','normalized_due'))
        def process_state():return tuple(conn.execute('SELECT * FROM whattodo.'+t+' ORDER BY 1,2').fetchall() for t in ('command_resolution_revision','command_resolution_head','command_resolution_reply'))
        def source(name,raw,kind='USER',captured=NOW):
            s=capture_source(provider=SCOPE.provider,scope_ref=SCOPE.scope_ref,external_id=name,raw_bytes=raw,captured_at=captured,source_type=kind)
            evidence.observe_source(canonical(s.as_record()).encode(),raw_content=raw,locator_ref='synthetic-'+name);return s
        def grant(command,ref):
            g=AuthorityGrant(command.authority_ref,command.principal_id,command.origin,command.command_id,command.changes,ref,NOW-timedelta(minutes=2),expires_at=NOW+timedelta(hours=1))
            with harness.target(database,'migration').connect() as owner:register_grant(owner,g,plan,application_version=__version__)
            return g
        def create(name,title,course=False,caller=CALLER):
            c=Command('seed-'+name,caller.principal_id,'USER_COMMAND','seed-root-'+name,(change(name,None,'CREATE_TASK',dict(title=title,importance=3,requiredness='REQUIRED',difficulty=DIMS,user_remaining_seconds=600)),))
            s=source(c.command_id,canonical(c.as_record()).encode());g=grant(c,s.record_id);facts=dict(domain='study')
            if course:facts.update(context=dict(kind='COURSE',id='synthetic-course'),profile_ref=dict(kind='COURSE_PROFILE',id='synthetic-course',version='1'))
            intent=ResolvedManualIntent(c.fingerprint,s.record_id,NOW,canonical(facts))
            defs=PostgresDefinitionRepository(conn,GitDefinitionSource(fixture.root),plan,roles,application_version=__version__) if course else MemoryDefinitionRepository(CLOCK)
            result=PostgresManualTaskHandler(conn,codec,plan,application_version=__version__,clock=CLOCK,definitions=defs,grants=(g,),source_scopes=(SCOPE,),intents=(intent,)).create(canonical(c.as_record()).encode(),ctx(c.command_id),expected_store_revision=epoch(),audit_id='audit-'+c.command_id,caller=caller)
            require(result.code=='COMMITTED','RESOLUTION_SETUP_'+result.code)
        def service(connection=conn,bindings=BINDINGS,courses=COURSES):return PostgresResolutionService(connection,codec,plan,application_version=__version__,clock=CLOCK,input_bindings=bindings,course_bindings=(('principal',courses),))
        svc=service()
        def begin(name,value='Homework',mode='NAME',course=None,kind='USER',action='COMPLETE_TASK',fields=None):
            v=dict(schema_version='0.1.0-resolution-intent',session_id='session-'+name,command_id=name,principal_id='principal',action=action,target=dict(mode=mode,value=value,course=course),creation_task_id=None,fields=fields or dict(completion='COMPLETE'),creation_facts={})
            raw=canonical(v).encode();s=source(name,raw,kind);return svc.begin(raw,s.record_id,ctx(name),caller=CALLER),raw,s
        def reply_input(frame,name,selection=None,answers=None):
            raw=canonical(dict(schema_version='0.1.0-clarification-reply',reply_id=name,session_id=frame.session_id,expected_revision=frame.revision,scope_hash=frame.fingerprint,selection=selection,answers=answers or {})).encode()
            return raw,source(name,raw)
        def answer(frame,name,selection=None,answers=None):
            raw,s=reply_input(frame,name,selection,answers);return svc.reply(raw,s.record_id,ctx(name),caller=CALLER),raw,s
        def handoff(frame,root):return svc.handoff(frame.session_id,frame.revision,frame.fingerprint,root,ctx(frame.as_record()['command_id']),caller=CALLER)
        def complete(frame,root):
            h=handoff(frame,root);require(h.code=='HANDOFF_READY','RESOLUTION_HANDOFF_'+h.code)
            c=h.value.command;g=grant(c,frame.as_record()['last_source_ref'])
            out=PostgresLifecycleHandler(conn,codec,plan,application_version=__version__,clock=CLOCK,grants=(g,),source_scopes=(SCOPE,)).complete(canonical(c.as_record()).encode(),ctx(c.command_id),expected_store_revision=h.value.expected_store_revision,audit_id='audit-'+c.command_id,caller=CALLER)
            require(out.code=='COMMITTED','RESOLUTION_LIFECYCLE_'+out.code);return h
        create('a','Homework',True);create('b','Homework');create('unique','Reading');create('hidden','Homework',caller=OTHER)
        before=state();out,raw,s=begin('ambiguous');f=out.value
        require(out.code=='NEEDS_CLARIFICATION' and [x['id'] for x in f.as_record()['choices']]==['a','b'] and state()==before,'RESOLUTION_OWNED_CHOICES')
        checks.append('duplicate_titles_list_only_owned_stable_ids_and_preserve_canonical_task_audit_epoch')
        untouched,_,_=begin('explicit','unique','ID');named,_,_=begin('unique-name','Reading')
        require(untouched.code==named.code=='RESOLVED' and not named.value.as_record()['question'] and state()==before,'RESOLUTION_REDUNDANT_APPROVAL')
        checks.append('exact_id_and_unique_exact_human_name_resolve_without_identical_extra_approval')
        wrong,_,_=begin('id-is-not-label','Reading','ID');near,_,_=begin('similar','Readin')
        require(wrong.code==near.code=='NEEDS_CLARIFICATION' and wrong.value.as_record()['choices']==[] and len(near.value.as_record()['choices'])==1,'RESOLUTION_LABEL_ID_DISTINCTION')
        checks.append('explicit_id_never_falls_back_to_title_and_single_fuzzy_candidate_still_requires_selection')
        course,_,_=begin('course','Homework',course=dict(mode='NAME',value='phys'))
        require(course.code=='RESOLVED' and course.value.as_record()['selected_task_ref']['task_id']=='a','RESOLUTION_COURSE_ALIAS')
        checks.append('independently_bound_course_alias_restricts_matching_to_exact_course_context')
        vague,_,_=answer(f,'vague',selection='\u786e\u8ba4')
        require(vague.code=='NEEDS_CLARIFICATION' and vague.value.revision==2 and state()==before,'RESOLUTION_VAGUE_CONFIRMATION')
        resolved,reply_raw,reply_source=answer(vague.value,'choose-second',selection='2');rf=resolved.value
        require(resolved.code=='RESOLVED' and rf.as_record()['selected_task_ref']==dict(task_id='b',revision=1) and rf.as_record()['command_id']=='ambiguous','RESOLUTION_SCOPED_CHOICE')
        checks.append('ambiguous_confirmation_stays_pending_and_numbered_reply_resolves_original_list_under_same_command_id')
        h=handoff(rf,'complete-root');require(h.code=='HANDOFF_READY' and h.value.source_refs==(s.record_id,reply_source.record_id),'RESOLUTION_SOURCE_CHAIN')
        c=h.value.command;denied=PostgresLifecycleHandler(conn,codec,plan,application_version=__version__,clock=CLOCK,grants=(),source_scopes=(SCOPE,)).complete(canonical(c.as_record()).encode(),ctx(c.command_id),expected_store_revision=epoch(),audit_id='denied',caller=CALLER)
        require(denied.code=='UNREGISTERED_AUTHORITY' and state()==before,'RESOLUTION_MINTED_GRANT')
        checks.append('resolved_reference_cannot_mint_grants_or_publish_without_independent_authorized_handler')
        complete(rf,'complete-root')
        require(reader.get('b').aggregate.as_record()['core']['completion']=='COMPLETE' and reader.get('a').revision==1 and conn.execute("SELECT count(*) FROM whattodo.effort_observation WHERE kind='ACTUAL_WORK'").fetchone()==(0,),'RESOLUTION_WRONG_TASK')
        checks.append('scoped_reply_hands_same_command_to_existing_completion_path_mutating_only_selected_task_without_inferred_work')
        after=state();restarted=service(bindings=(),courses=())
        replay=restarted.reply(reply_raw,reply_source.record_id,ctx('choose-second'),caller=CALLER)
        require(replay.code=='CLARIFICATION_REPLAY' and replay.value==rf and state()==after,'RESOLUTION_RESTART_REPLY')
        replayh=restarted.handoff(rf.session_id,rf.revision,rf.fingerprint,'complete-root',ctx('ambiguous'),caller=CALLER)
        require(replayh.code=='HANDOFF_REPLAY' and replayh.value.command==h.value.command,'RESOLUTION_RESTART_HANDOFF_'+replayh.code)
        require(restarted.begin(raw,s.record_id,ctx('ambiguous'),caller=CALLER).value==rf,'RESOLUTION_BEGIN_REPLAY')
        checks.append('restart_owned_replays_return_original_frame_and_command_after_task_change_without_live_bindings')
        changed=bytearray(reply_raw);changed[-2]=32
        require(svc.reply(bytes(changed),reply_source.record_id,ctx('choose-second'),caller=CALLER).status!='SUCCESS' and state()==after,'RESOLUTION_CHANGED_REPLY')
        for caller in (OTHER,CallerIdentity('principal','EXTERNAL',True),CallerIdentity('principal','USER_COMMAND',False)):
            require(svc.get(rf.session_id,ctx('read'),caller=caller).status=='PERMANENT','RESOLUTION_OWNER_READ')
            require(svc.reply(reply_raw,reply_source.record_id,ctx('choose-second'),caller=caller).status=='PERMANENT','RESOLUTION_OWNER_REPLY')
        external,_,_=begin('external',kind='EMAIL');require(external.code=='RESOLUTION_USER_SOURCE_REQUIRED' and state()==after,'RESOLUTION_EXTERNAL_SOURCE')
        checks.append('foreign_principal_external_source_unauthenticated_caller_and_changed_reply_bytes_cannot_resume_or_read_owned_command')
        stale,_,_=begin('stale');old_frame=stale.value;complete(untouched.value,'unique-root')
        # Change a listed Task, then prove old scoped choices cannot execute.
        complete(course.value,'course-root')
        old_reply,old_source=reply_input(old_frame,'stale-reply',selection='1');before_process=process_state();after=state()
        require(svc.reply(old_reply,old_source.record_id,ctx('stale-reply'),caller=CALLER).code=='RESOLUTION_TASK_SNAPSHOT_CHANGED' and process_state()==before_process and state()==after,'RESOLUTION_STALE_TASK')
        refreshed=svc.refresh(old_frame.session_id,old_frame.revision,old_frame.fingerprint,ctx('refresh'),caller=CALLER)
        require(refreshed.value.revision==2 and svc.reply(old_reply,old_source.record_id,ctx('stale-reply'),caller=CALLER).code=='RESOLUTION_STALE_SESSION','RESOLUTION_REFRESH_SCOPE')
        answered,_,_=answer(refreshed.value,'refreshed-choice',selection='a');require(answered.code=='RESOLVED' and answered.value.as_record()['selected_task_ref']['revision']==2,'RESOLUTION_REFRESH_VERSION')
        checks.append('changed_task_rejects_old_frame_atomically_and_explicit_refresh_requires_new_question_revision')
        raw_create=guided_message(dict(title='New task'));cs=source('creation-input',raw_create)
        proposal=DirectCreationNormalizer(codec,clock=CLOCK,bindings=BINDINGS).guided(raw_create,cs,caller=CALLER)
        initial=DirectCreationNormalizer(codec,clock=CLOCK,bindings=BINDINGS).manual_handoff(proposal,command_id='create-followup',task_id='created-through-followup',authority_ref='creation-pending-root',caller=CALLER)
        initial_grant=grant(initial.command,cs.record_id)
        pending=PostgresManualTaskHandler(conn,codec,plan,application_version=__version__,clock=CLOCK,definitions=MemoryDefinitionRepository(CLOCK),grants=(initial_grant,),source_scopes=(SCOPE,),intents=(initial.intent,)).create(canonical(initial.command.as_record()).encode(),ctx('create-followup'),expected_store_revision=epoch(),audit_id='unused-pending-audit',caller=CALLER)
        require(pending.code=='PENDING_DETAILS' and reader.get('created-through-followup') is None,'RESOLUTION_INITIAL_PENDING')
        pending_history=conn.execute('SELECT * FROM whattodo.manual_creation_pending').fetchall()
        partial=svc.begin_creation(proposal,ctx('create-followup'),session_id='create-session',desired_task_id='created-through-followup',caller=CALLER)
        cf=partial.value;before=state()
        forbidden,_,_=answer(cf,'creation-overwrite',answers=dict(title='Changed title'))
        require(forbidden.code=='RESOLUTION_ANSWER_FIELD_SCOPE' and svc.get(cf.session_id,ctx('read'),caller=CALLER).value==cf and state()==before,'RESOLUTION_KNOWN_FIELD_OVERWRITE')
        checks.append('reply_cannot_overwrite_already_known_creation_fields_or_expand_original_effect_scope')
        partial2,_,_=answer(cf,'creation-details',answers=dict(importance='bad',requiredness='\u5fc5\u987b\u5b8c\u6210',difficulty='3/2/3',domain='\u5b66\u4e60'))
        require(partial2.code=='NEEDS_CLARIFICATION' and partial2.value.as_record()['missing_fields']==['/core/importance'] and state()==before,'RESOLUTION_PARTIAL_ANSWERS')
        ready,_,final_source=answer(partial2.value,'creation-rating',answers=dict(importance='4'));cf=ready.value
        ch=handoff(cf,'creation-final-root');require(ch.code=='HANDOFF_READY' and ch.value.command.command_id=='create-followup','RESOLUTION_CREATION_COMMAND')
        c=ch.value.command;g=grant(c,final_source.record_id)
        created=PostgresManualTaskHandler(conn,codec,plan,application_version=__version__,clock=CLOCK,definitions=MemoryDefinitionRepository(CLOCK),grants=(g,),source_scopes=(SCOPE,),intents=(ch.value.manual_intent,)).create(canonical(c.as_record()).encode(),ctx(c.command_id),expected_store_revision=ch.value.expected_store_revision,audit_id='audit-create-followup',caller=CALLER)
        require(created.code=='COMMITTED','RESOLUTION_CREATION_'+created.code)
        v=reader.get('created-through-followup').aggregate.as_record()
        require(v['core']['importance']==4 and v['core']['title']=='New task' and v['effort']['user_remaining'] is None and v['work']['total_estimate'] is None,'RESOLUTION_CREATION_DEFAULTS')
        require(conn.execute('SELECT * FROM whattodo.manual_creation_pending').fetchall()==pending_history,'RESOLUTION_PENDING_REWRITTEN')
        checks.append('creation_followup_retains_valid_answers_only_reasks_missing_field_and_creates_same_command_without_invented_u_or_total')
        checks.append('completion_of_same_creation_command_preserves_original_manual_pending_history_without_duplicate_task')
        scoped,_,_=begin('course-registry-change');sf=scoped.value
        changed_service=service(courses=(CourseLabel('synthetic-course','New Physics',('phys',),'2'),))
        scoped_raw,scoped_source=reply_input(sf,'registry-reply',selection='1');before=state();before_process=process_state()
        require(changed_service.reply(scoped_raw,scoped_source.record_id,ctx('registry-reply'),caller=CALLER).code=='RESOLUTION_COURSE_REGISTRY_CHANGED' and process_state()==before_process,'RESOLUTION_REGISTRY_CHANGE')
        refreshed=changed_service.refresh(sf.session_id,sf.revision,sf.fingerprint,ctx('refresh'),caller=CALLER)
        require(refreshed.value.revision==2 and changed_service.reply(scoped_raw,scoped_source.record_id,ctx('registry-reply'),caller=CALLER).code=='RESOLUTION_STALE_SESSION' and state()==before,'RESOLUTION_REGISTRY_REFRESH')
        checks.append('course_label_registry_change_requires_new_versioned_question_without_reusing_old_answer')
        unbound=service(bindings=())
        own,own_raw,own_source=begin('account-required')
        new_raw=own_raw.replace(b'account-required',b'account-required-new')
        new_source=source('account-required-new',new_raw)
        require(unbound.begin(new_raw,new_source.record_id,ctx('account-required-new'),caller=CALLER).code=='RESOLUTION_INPUT_ACCOUNT_REQUIRED','RESOLUTION_ACCOUNT_SCOPE')
        require(svc.begin(new_raw,own_source.record_id,ctx('account-required-new'),caller=CALLER).code=='RESOLUTION_EXACT_SOURCE_REQUIRED','RESOLUTION_EXACT_BYTES')
        checks.append('fresh_input_requires_independent_actor_account_binding_and_exact_retained_source_bytes')
        old_raw,old_source=reply_input(own.value,'old-source-time',selection='1')
        captured=source('captured-before-question',old_raw,captured=NOW-timedelta(seconds=1));before_process=process_state()
        require(svc.reply(old_raw,captured.record_id,ctx('old-source-time'),caller=CALLER).code=='RESOLUTION_REPLY_TIME_REQUIRED' and process_state()==before_process,'RESOLUTION_OLD_SOURCE_TIME')
        cross=canonical(dict(schema_version='0.1.0-clarification-reply',reply_id='cross-scope',session_id=own.value.session_id,expected_revision=own.value.revision,scope_hash=sf.fingerprint,selection='1',answers={})).encode()
        cross_source=source('cross-scope',cross)
        require(svc.reply(cross,cross_source.record_id,ctx('cross-scope'),caller=CALLER).code=='RESOLUTION_REPLY_SCOPE_CONFLICT' and process_state()==before_process,'RESOLUTION_CROSS_SCOPE')
        checks.append('reply_captured_before_question_or_bound_to_another_frame_hash_cannot_advance_history')
        kept_ids=[x['id'] for x in own.value.as_record()['choices']]
        create('new-duplicate','Homework');picked,_,_=answer(own.value,'original-list-choice',selection='2')
        require(picked.code=='RESOLVED' and picked.value.as_record()['selected_task_ref']['task_id']==kept_ids[1],'RESOLUTION_WIDENED_LIST')
        checks.append('unrelated_new_task_does_not_reorder_or_widen_original_listed_choice_scope')
        q,_,_=begin('atomic-reply');qf=q.value;atomic_raw,atomic_source=reply_input(qf,'atomic-reply-answer',selection='1')
        class Fault:
            def __init__(self,connection,lost=False):self.connection=connection;self.lost=lost;self.armed=False
            def __getattr__(self,n):return getattr(self.connection,n)
            def execute(self,query,*a,**kw):
                result=self.connection.execute(query,*a,**kw)
                if 'INSERT INTO whattodo.command_resolution_reply' in query:
                    self.armed=True
                    if not self.lost:raise psycopg.OperationalError('synthetic before commit')
                return result
            def transaction(self):
                wrapped=self.connection.transaction();proxy=self
                class T:
                    def __enter__(self):return wrapped.__enter__()
                    def __exit__(self,k,e,t):
                        result=wrapped.__exit__(k,e,t)
                        if k is None and proxy.lost and proxy.armed:
                            proxy.armed=False;raise psycopg.OperationalError('synthetic lost acknowledgement')
                        return result
                return T()
        before_process=process_state();before=state();fault=service(Fault(conn))
        require(fault.reply(atomic_raw,atomic_source.record_id,ctx('atomic-reply-answer'),caller=CALLER).status=='RETRYABLE' and process_state()==before_process and state()==before,'RESOLUTION_ROLLBACK')
        checks.append('failure_after_frame_head_and_reply_insert_rolls_back_all_process_records_and_preserves_canonical_state')
        lost=service(Fault(conn,lost=True));unknown=lost.reply(atomic_raw,atomic_source.record_id,ctx('atomic-reply-answer'),caller=CALLER)
        require(unknown.status=='UNKNOWN' and svc.reply(atomic_raw,atomic_source.record_id,ctx('atomic-reply-answer'),caller=CALLER).code=='CLARIFICATION_REPLAY' and state()==before,'RESOLUTION_LOST_ACK_'+unknown.code)
        checks.append('lost_commit_acknowledgement_remains_unknown_and_owned_reply_lookup_recovers_one_durable_result')
        race,_,_=begin('race');r1,s1=reply_input(race.value,'race-one',selection='1');r2,s2=reply_input(race.value,'race-two',selection='2');barrier=Barrier(2)
        def racer(raw,ref,name):
            with harness.target(database).connect() as other:
                barrier.wait(timeout=10);return service(other).reply(raw,ref,ctx(name),caller=CALLER)
        before=state()
        with ThreadPoolExecutor(max_workers=2) as pool:
            futures=[pool.submit(racer,r1,s1.record_id,'race-one'),pool.submit(racer,r2,s2.record_id,'race-two')];results=[f.result(timeout=20) for f in futures]
        require(sum(r.status=='SUCCESS' for r in results)==1 and svc.get(race.value.session_id,ctx('read'),caller=CALLER).value.revision==2 and state()==before,'RESOLUTION_CONCURRENT_REPLY')
        checks.append('concurrent_answers_to_one_question_have_one_version_winner_without_canonical_task_writes')
        for table in ('command_resolution_revision','command_resolution_reply'):
            for query in ('DELETE FROM whattodo.'+table,'UPDATE whattodo.'+table+' SET principal_id=principal_id'):
                try:
                    with conn.transaction():conn.execute(query)
                except psycopg.Error as exc:require(exc.sqlstate=='23514','RESOLUTION_IMMUTABLE_SQLSTATE')
                else:require(False,'RESOLUTION_HISTORY_MUTATION')
        checks.append('resolution_and_reply_history_are_append_only_with_owned_head_compare_and_swap')
        report.update(migration_steps=len(plan.steps),schema_version=plan.schema_version,domain_tables=conn.execute("SELECT count(*) FROM pg_tables WHERE schemaname='whattodo'").fetchone()[0],domain_foreign_keys=conn.execute("SELECT count(*) FROM pg_constraint c JOIN pg_namespace n ON n.oid=c.connamespace WHERE n.nspname='whattodo' AND c.contype='f'").fetchone()[0])
        require((report['domain_tables'],report['domain_foreign_keys'])==(82,204),'RESOLUTION_SCHEMA_COUNTS')
        checks.append('native_schema_has_82_domain_tables_204_foreign_keys_and_three_runtime_metadata_tables')


def main():
    harness=PostgresHarness();report=dict(task='M3A-22',status='IN_PROGRESS',scope='SYNTHETIC_OWNED_REFERENCE_AND_CLARIFICATION_HANDOFF',verified_on='2026-10-10',native_checks=[])
    try:
        with harness:verify(harness,report)
        report.update(status='PASS',native_check_count=len(report['native_checks']),limitations=['Independent synthetic caller/account/course labels and grants; no live channel or personal activation','Mutation/lifecycle intents are already normalized structured input; other freeform command classes remain separate M3A-21 instances','No relative date parser or durable caller authentication deployment is supplied by resolution'])
    except Exception as exc:report.update(status='FAIL',failure_type=type(exc).__name__,failure_code=str(exc) if isinstance(exc,HarnessError) else 'RESOLUTION_NATIVE_FAILED',failure_sqlstate=getattr(exc,'sqlstate',None))
    report['harness']=harness.safe_summary();target=harness.run_root/'resolution-report.json'
    if harness.run_root.exists():target.write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(dict(status=report['status'],report=str(target),checks=len(report['native_checks']),server_stopped=report['harness']['server_stopped'])))
    return 0 if report['status']=='PASS' else 1

if __name__=='__main__':raise SystemExit(main())
