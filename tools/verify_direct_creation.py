"""Native source-to-direct-input-to-existing-manual-service handoff checks."""
from dataclasses import replace
from datetime import datetime,timedelta,timezone
import json
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:sys.path.insert(0,str(ROOT))
from src import __version__
from src.adapters.clocks import FrozenClock
from src.adapters.contract_json import ContractJSONCodec
from src.adapters.memory_definitions import MemoryDefinitionRepository
from src.adapters.migration_files import load_migration_plan
from src.adapters.postgres_authorization import register_grant
from src.adapters.postgres_evidence import PostgresEvidenceRepository,register_source_scope
from src.adapters.postgres_manual_tasks import PostgresManualTaskHandler
from src.adapters.postgres_migrations import DatabaseRoles,apply_migrations
from src.adapters.postgres_tasks import PostgresTaskRepository
from src.application.definitions import canonical
from src.application.direct_creation import DirectCreationNormalizer,UserInputBinding,guided_message
from src.application.evidence_storage import SourceScope
from src.application.ports import RequestContext
from src.application.transactions import TransactionError
from src.domain.authorization import AuthorityGrant,CallerIdentity
from src.domain.provenance import capture_source
from tools.check_contract_registry import trusted_schemas
from tools.postgres_harness import HarnessError,PostgresHarness,ROLES,require
from tools.verify_transactions import TABLES

NOW=datetime(2026,1,1,tzinfo=timezone.utc);CLOCK=FrozenClock(NOW);CALLER=CallerIdentity('principal','USER_COMMAND',True)
SCOPE=SourceScope('synthetic-direct-user','scope','account')


def verify(harness,report):
    plan=load_migration_plan(root=ROOT);codec=ContractJSONCodec(trusted_schemas());checks=report['native_checks']
    database=harness.create_database(initialize_schema=False);roles=DatabaseRoles(ROLES['migration'],ROLES['application'],ROLES['test'])
    with harness.target(database,'migration').connect() as owner:
        apply_migrations(owner,plan,roles=roles,application_version=__version__)
        register_source_scope(owner,plan,roles,SCOPE,application_version=__version__,clock=CLOCK)
    normalizer=DirectCreationNormalizer(codec,clock=CLOCK,bindings=(UserInputBinding(CALLER.principal_id,SCOPE),))
    with harness.target(database).connect() as conn:
        evidence=PostgresEvidenceRepository(conn,codec,plan,application_version=__version__,clock=CLOCK,scopes=(SCOPE,))
        reader=PostgresTaskRepository(conn,codec,plan,application_version=__version__,clock=CLOCK)
        def state():return tuple(conn.execute('SELECT * FROM whattodo.'+table+' ORDER BY 1,2').fetchall() for table in TABLES+('effort_observation',))
        def epoch():return conn.execute('SELECT revision FROM whattodo.store_epoch').fetchone()[0]
        def proposal(name,raw,*,guided=False):
            source=capture_source(provider=SCOPE.provider,scope_ref=SCOPE.scope_ref,external_id=name,raw_bytes=raw,captured_at=NOW-timedelta(minutes=1),source_type='USER')
            evidence.observe_source(canonical(source.as_record()).encode(),raw_content=raw,locator_ref='synthetic-'+name)
            before=state();p=(normalizer.guided if guided else normalizer.natural)(raw,source,caller=CALLER)
            require(state()==before,'DIRECT_NORMALIZER_MUTATED');return p
        def fixture_grant(handoff):
            c=handoff.command;g=AuthorityGrant(c.authority_ref,c.principal_id,c.origin,c.command_id,c.changes,handoff.intent.source_ref,
                NOW-timedelta(minutes=2),expires_at=NOW+timedelta(hours=1))
            with harness.target(database,'migration').connect() as owner:register_grant(owner,g,plan,application_version=__version__)
            return g
        def handler(h,g=None,**kwargs):
            options=dict(application_version=__version__,clock=CLOCK,definitions=MemoryDefinitionRepository(CLOCK),grants=(g,) if g else (),
                source_scopes=(SCOPE,),intents=(h.intent,));options.update(kwargs)
            return PostgresManualTaskHandler(conn,codec,plan,**options)
        def submit(service,h,e):return service.create(canonical(h.command.as_record()).encode(),RequestContext(h.command.command_id,'synthetic-correlation'),
            expected_store_revision=e,audit_id='audit-'+h.command.command_id,caller=CALLER)

        raw='新增任务：阅读论文，必须完成，重要性4，难度3/2/3，剩余约40分钟，领域学习'.encode()
        p=proposal('natural-full',raw);h=normalizer.manual_handoff(p,command_id='natural-full',task_id='task-natural',authority_ref='root-natural',caller=CALLER)
        require(p.ready_for_creation and conn.execute('SELECT count(*) FROM whattodo.authority_record').fetchone()==(0,),'DIRECT_NORMALIZER_CREATED_GRANT')
        checks.append('normalizer_preserves_exact_user_statement_and_frozen_pending_shape_without_sql_or_grant_side_effects')
        require(evidence.get_raw(p.source.record_id).raw_bytes==raw and h.statement_bytes==raw,'DIRECT_RAW_RETENTION')
        checks.append('immutable_source_storage_retains_exact_original_chinese_bytes_before_and_after_normalization')
        before=state();denied=submit(handler(h),h,epoch());require(denied.code=='UNREGISTERED_AUTHORITY' and state()==before,'DIRECT_PARSE_IS_NOT_GRANT_'+denied.code)
        checks.append('fully_parsed_input_and_manual_intent_cannot_create_task_without_independent_root_grant')
        g=fixture_grant(h);e=epoch();out=submit(handler(h,g),h,e);require(out.code=='COMMITTED','DIRECT_NATIVE_CREATE_'+out.code)
        task=reader.get('task-natural');v=task.aggregate.as_record()
        require(v['core']['title']=='阅读论文' and v['core']['importance']==4 and v['core']['requiredness']=='REQUIRED' and v['core']['domain']=='study'
            and v['effort']['user_remaining']['seconds']==2400,'DIRECT_NATIVE_VALUES')
        checks.append('clear_natural_input_runs_existing_manual_schema_authority_and_atomic_creation_path_without_extra_confirmation')
        require(v['core']['completion']=='INCOMPLETE' and v['timing']['created_at'] is None and v['work']['total_estimate'] is None,'DIRECT_INVENTED_FACTS')
        require(conn.execute("SELECT count(*) FROM whattodo.effort_observation WHERE kind='ACTUAL_WORK'").fetchone()==(0,),'DIRECT_INVENTED_ACTUAL')
        checks.append('remaining_estimate_does_not_become_original_total_actual_work_or_invented_completion_session_time')
        creation_source={x['source_ref'] for x in v['provenance']};require(creation_source=={p.source.record_id},'DIRECT_PROVENANCE')
        observation=conn.execute('SELECT source_record_ref,authority_ref,transaction_ref FROM whattodo.effort_observation WHERE observation_id=%s',
            (v['effort']['user_remaining']['observation_id'],)).fetchone()
        require(observation==(p.source.record_id,g.grant_id,h.command.command_id),'DIRECT_U_BINDING')
        checks.append('normalized_fields_and_u_keep_original_user_source_root_and_committed_command_provenance')
        require(conn.execute('SELECT count(*) FROM whattodo.candidate_identity').fetchone()==(0,),'DIRECT_CLEAR_INPUT_QUEUED')
        checks.append('clear_direct_command_does_not_leave_a_duplicate_candidate_for_later_reconfirmation')
        before=state();again=submit(handler(h,clock=FrozenClock(NOW+timedelta(days=30)),grants=(),source_scopes=(),intents=()),h,e)
        require(again.code=='REPLAY' and again.value.receipt==out.value.receipt and state()==before,'DIRECT_NATIVE_REPLAY')
        checks.append('normalized_command_replays_original_owned_receipt_without_live_parser_grants_intents_or_accounts')

        partial=proposal('partial','新增任务：读论文'.encode())
        ph=normalizer.manual_handoff(partial,command_id='partial',task_id='task-partial',authority_ref='root-partial',caller=CALLER);pg=fixture_grant(ph)
        before=state();pending=submit(handler(ph,pg),ph,epoch())
        require(pending.code=='PENDING_DETAILS' and reader.get('task-partial') is None and state()==before
            and set(pending.value.missing_fields)==set(partial.missing_fields),'DIRECT_PENDING_FACTS')
        checks.append('missing_essential_facts_stay_durable_manual_pending_details_without_fabricated_task_or_defaults')
        require(conn.execute('SELECT count(*) FROM whattodo.manual_creation_pending').fetchone()==(1,),'DIRECT_PENDING_COUNT')
        before=state();repeat=submit(handler(ph,pg),ph,epoch());require(repeat.value==pending.value and state()==before
            and conn.execute('SELECT count(*) FROM whattodo.manual_creation_pending').fetchone()==(1,),'DIRECT_PENDING_REPLAY')
        checks.append('partial_creation_retries_keep_one_pending_record_and_no_canonical_receipt')

        ambiguous=proposal('ambiguous','新增任务：读论文，重要性3，重要性4，剩余20~30分钟'.encode())
        before=state()
        try:normalizer.manual_handoff(ambiguous,command_id='ambiguous',task_id='never-created',authority_ref='never-granted',caller=CALLER)
        except TransactionError as exc:require(str(exc)=='DIRECT_CLARIFICATION_REQUIRED','DIRECT_AMBIGUOUS_ERROR')
        else:require(False,'DIRECT_AMBIGUOUS_HANDOFF')
        require(state()==before and reader.get('never-created') is None,'DIRECT_AMBIGUOUS_MUTATED')
        checks.append('conflicting_ratings_and_duration_ranges_cannot_cross_manual_handoff')
        evidence.observe_candidate(ambiguous.candidate_json.encode());stored,_=evidence.get_candidate(ambiguous.candidate['candidate_id'])
        require(stored.candidate.review_state=='PENDING' and stored.candidate.authority_ref is None,'DIRECT_UNCERTAIN_QUEUE')
        require(evidence.observe_candidate(ambiguous.candidate_json.encode()).outcome=='REPLAY','DIRECT_UNCERTAIN_REPLAY')
        checks.append('uncertain_input_can_use_existing_immutable_candidate_queue_without_approval_or_duplicate_task')

        for name,answers,unknown in (
            ('guided-known',dict(title='整理材料',importance='3',requiredness='可选',difficulty='2/2/2',remaining='0分钟',domain='生活'),False),
            ('guided-unknown',dict(title='整理材料',importance='3',requiredness='可选',difficulty='2/2/2',remaining='不知道',domain='生活'),True)):
            p2=proposal(name,guided_message(answers),guided=True);h2=normalizer.manual_handoff(p2,command_id=name,task_id='task-'+name,authority_ref='root-'+name,caller=CALLER)
            g2=fixture_grant(h2);require(submit(handler(h2,g2),h2,epoch()).code=='COMMITTED','DIRECT_GUIDED_CREATE')
            u=reader.get('task-'+name).aggregate.as_record()['effort']['user_remaining']
            require((u is None) if unknown else (u['seconds']==0),'DIRECT_GUIDED_U')
        checks.append('textual_guided_creation_distinguishes_explicit_unknown_remaining_and_known_zero')
        require(reader.get('task-guided-known').aggregate.as_record()['core']['title']==reader.get('task-guided-unknown').aggregate.as_record()['core']['title']
            and reader.get('task-guided-known').task_id!=reader.get('task-guided-unknown').task_id,'DIRECT_LABEL_IDS')
        checks.append('same_human_title_can_create_distinct_stable_ids_without_provider_or_title_identity_collision')
        before=state()
        for caller in (CallerIdentity('principal','EXTERNAL',True),CallerIdentity('principal','USER_COMMAND',False),CallerIdentity('other','USER_COMMAND',True)):
            try:normalizer.natural(raw,p.source,caller=caller)
            except TransactionError:pass
            else:require(False,'DIRECT_UNTRUSTED_CALLER')
        require(state()==before,'DIRECT_UNTRUSTED_MUTATED');checks.append('external_unauthenticated_and_wrong_account_principal_input_never_reaches_canonical_service')
        before=state()
        try:normalizer.manual_handoff(replace(p,facts_json='{"domain":"other"}'),command_id='forged',task_id='forged',authority_ref='forged',caller=CALLER)
        except TransactionError as exc:require(str(exc)=='DIRECT_PROPOSAL_DRIFT','DIRECT_FORGED_ERROR')
        else:require(False,'DIRECT_FORGED_HANDOFF')
        require(state()==before,'DIRECT_FORGED_MUTATED');checks.append('handoff_reparses_original_bytes_and_rejects_replaced_resolved_facts')
        report.update(migration_steps=len(plan.steps),schema_version=plan.schema_version,
            domain_tables=conn.execute("SELECT count(*) FROM pg_tables WHERE schemaname='whattodo'").fetchone()[0],
            domain_foreign_keys=conn.execute("SELECT count(*) FROM pg_constraint c JOIN pg_namespace n ON n.oid=c.connamespace WHERE n.nspname='whattodo' AND c.contype='f'").fetchone()[0])


def main():
    harness=PostgresHarness();report=dict(task='M3A-21@CREATE_TASK',status='IN_PROGRESS',scope='SYNTHETIC_DIRECT_USER_CREATION_HANDOFF',verified_on='2026-10-10',native_checks=[])
    try:
        with harness:verify(harness,report)
        report.update(status='PASS',native_check_count=len(report['native_checks']),limitations=[
            'Caller/account bindings and exact creation root grants are independent synthetic fixtures; no live transport selected',
            'Only bounded Chinese creation phrases and textual guided creation are supported; other command classes remain separate instances',
            'Relative dates, reference resolution, expiry conditions, defaults and clarification resumption remain separate cards'])
    except Exception as exc:report.update(status='FAIL',failure_type=type(exc).__name__,failure_code=str(exc) if isinstance(exc,HarnessError) else 'DIRECT_CREATION_NATIVE_FAILED',failure_sqlstate=getattr(exc,'sqlstate',None))
    report['harness']=harness.safe_summary();target=harness.run_root/'direct-creation-report.json'
    if harness.run_root.exists():target.write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(dict(status=report['status'],report=str(target),checks=len(report['native_checks']),server_stopped=report['harness']['server_stopped'])))
    return 0 if report['status']=='PASS' else 1


if __name__=='__main__':raise SystemExit(main())
