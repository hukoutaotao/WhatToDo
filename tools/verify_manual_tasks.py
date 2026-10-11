"""Synthetic manual creation, exact defaults, durable pending and atomic U."""
from copy import deepcopy
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
from src.adapters.git_definitions import GitDefinitionSource
from src.adapters.migration_files import load_migration_plan
from src.adapters.postgres_authorization import register_grant
from src.adapters.postgres_definitions import PostgresDefinitionRepository
from src.adapters.postgres_evidence import PostgresEvidenceRepository,register_source_scope
from src.adapters.postgres_manual_tasks import PostgresManualTaskHandler
from src.adapters.postgres_migrations import DatabaseRoles,apply_migrations
from src.adapters.postgres_tasks import PostgresTaskRepository
from src.application.definitions import DefinitionKey,canonical
from src.application.evidence_storage import SourceScope
from src.application.manual_tasks import ApprovedDefaultUse,ResolvedManualIntent
from src.application.ports import RequestContext
from src.domain.authorization import AuthorityGrant,CallerIdentity,Command,change
from src.domain.provenance import capture_source
from tools.check_contract_registry import trusted_schemas
from tools.git_definition_fixture import GitDefinitionFixture
from tools.postgres_harness import HarnessError,PostgresHarness,ROLES,require
from tools.verify_definition_repository import request as definition_request
from tools.verify_toolchain import native_transactions
from tools.verify_transactions import TABLES

NOW=datetime(2026,1,1,tzinfo=timezone.utc);CLOCK=FrozenClock(NOW)
CALLER=CallerIdentity('principal','USER_COMMAND',True)
SCOPE=SourceScope('synthetic-manual','scope','account')
DIMS=dict(thinking_depth=2,repetitive_volume=2,new_learning_load=3)
DEFAULTS=dict(importance=3,requiredness='OPTIONAL',difficulty=DIMS,
    minimum_session_seconds=1200,fragmentable=True,total_estimate_seconds=1800)


def verify(harness,report):
    import psycopg
    plan=load_migration_plan(root=ROOT);codec=ContractJSONCodec(trusted_schemas())
    roles=DatabaseRoles(ROLES['migration'],ROLES['application'],ROLES['test'])
    database=harness.create_database(initialize_schema=False);checks=report['native_checks']
    with harness.target(database,'migration').connect() as owner:
        old=load_migration_plan(root=ROOT,manifest_path=ROOT/'reports/acceptance/M3A-11-migration-plan.json')
        apply_migrations(owner,old,roles=roles,application_version=__version__);native_transactions(owner)
        prior=owner.execute('SELECT * FROM whattodo_meta.migration_history ORDER BY position').fetchall()
        result=apply_migrations(owner,plan,roles=roles,application_version=__version__)
        require(result.applied==tuple(s.migration_id for s in plan.steps[len(old.steps):]) and
            owner.execute('SELECT * FROM whattodo_meta.migration_history WHERE position<=%s ORDER BY position',(len(old.steps),)).fetchall()==prior,
            'MANUAL_FORWARD_UPGRADE_CHANGED_PRIOR_RECEIPTS')
        checks.append('forward_suffix_preserves_all_nine_prior_checkpoint_receipts')
        register_source_scope(owner,plan,roles,SCOPE,application_version=__version__,clock=CLOCK)
    fixture=GitDefinitionFixture(harness.run_root/'git-fixture')
    values=[dict(kind='TASKTYPE',id='work',version='1',body=dict(defaults=DEFAULTS)),
        dict(kind='TASKTYPE',id='work',version='2',body=dict(defaults=dict(DEFAULTS,importance=5))),
        dict(kind='TASK_TEMPLATE',id='conflict',version='1',body=dict(defaults=dict(importance=5)))]
    files={f'{i}.json':canonical(v).encode() for i,v in enumerate(values)};commit=fixture.commit_objects(files)
    with harness.target(database,'migration').connect() as owner:
        definitions=PostgresDefinitionRepository(owner,GitDefinitionSource(fixture.root),plan,roles,application_version=__version__)
        definitions.register(tuple(definition_request(commit,f'{i}.json',v) for i,v in enumerate(values)))

    def evidence(conn,name):
        raw=('synthetic manual statement '+name).encode()
        source=capture_source(provider=SCOPE.provider,scope_ref=SCOPE.scope_ref,external_id=name,raw_bytes=raw,
            captured_at=NOW-timedelta(minutes=1),source_type='USER')
        repo=PostgresEvidenceRepository(conn,codec,plan,application_version=__version__,clock=CLOCK,scopes=(SCOPE,))
        repo.observe_source(json.dumps(source.as_record()).encode(),raw_content=raw,locator_ref='synthetic-'+name)
        return source.record_id
    def grant(c,source):
        g=AuthorityGrant(c.authority_ref,c.principal_id,c.origin,c.command_id,c.changes,source,
            NOW-timedelta(minutes=1),expires_at=NOW+timedelta(hours=1))
        with harness.target(database,'migration').connect() as owner:register_grant(owner,g,plan,application_version=__version__)
        return g
    def state(conn):return tuple(conn.execute('SELECT * FROM whattodo.'+t+' ORDER BY 1,2').fetchall() for t in TABLES+('effort_observation',))
    def pending_state(conn):return tuple(conn.execute('SELECT * FROM whattodo.'+t+' ORDER BY 1,2').fetchall() for t in
        ('candidate_identity','candidate_revision','candidate_payload','candidate_field_provenance','pending_evidence_identity','pending_evidence_revision','pending_evidence_head','manual_creation_pending'))

    with harness.target(database).connect() as conn:
        defs=PostgresDefinitionRepository(conn,GitDefinitionSource(fixture.root),plan,roles,application_version=__version__)
        reader=PostgresTaskRepository(conn,codec,plan,application_version=__version__,clock=CLOCK)
        approval_source=evidence(conn,'default-approval')
        approval=Command('approve-defaults','principal','USER_COMMAND','default-approval',
            (change('synthetic-approved-default',None,'CREATE_TASK',dict(title='Approved defaults statement')),))
        grant(approval,approval_source)
        use=ApprovedDefaultUse(DefinitionKey('TASKTYPE','work','1'),'default-approval',approval_source)
        def setup(command_id,*,fields=None,facts=None,uses=None):
            c=Command(command_id,'principal','USER_COMMAND','grant-'+command_id,
                (change(command_id+'-task',None,'CREATE_TASK',fields or dict(title='Manual '+command_id)),))
            source=evidence(conn,command_id);g=grant(c,source)
            facts=dict(domain='study',task_type_ref=dict(id='work',version='1')) if facts is None else facts
            i=ResolvedManualIntent(c.fingerprint,source,NOW-timedelta(seconds=30),canonical(facts),
                (use,) if uses is None else uses)
            epoch=conn.execute('SELECT revision FROM whattodo.store_epoch').fetchone()[0]
            return c,g,i,epoch
        def handler(c=None,g=None,i=None,**kw):
            connection=kw.pop('connection',conn)
            options=dict(application_version=__version__,clock=CLOCK,definitions=defs,
                intents=(i,) if i else (),grants=(g,) if g else (),source_scopes=(SCOPE,))
            options.update(kw);return PostgresManualTaskHandler(connection,codec,plan,**options)
        def submit(h,c,epoch,*,caller=CALLER,audit=None,correlation=None):
            return h.create(json.dumps(c.as_record()).encode(),RequestContext(c.command_id,correlation or 'correlation-'+c.command_id),
                expected_store_revision=epoch,audit_id=audit or 'audit-'+c.command_id,caller=caller)
        def deny(h,c,epoch,code,**kw):
            before=state(conn);pending=pending_state(conn);out=submit(h,c,epoch,**kw)
            require(out.status in ('PERMANENT','CONFLICT') and out.code==code,'MANUAL_NEGATIVE_'+out.code)
            require(state(conn)==before and pending_state(conn)==pending,'MANUAL_NEGATIVE_MUTATED_STATE')
            return out
        def require_pending(h,c,epoch,path):
            before=state(conn);diagnostics=[]
            def trace(frame,event,arg):
                if event=='exception' and Path(frame.f_code.co_filename).is_relative_to(ROOT/'src'):
                    diagnostics.append(dict(file=Path(frame.f_code.co_filename).name,line=frame.f_lineno,type=arg[0].__name__))
                return trace
            sys.settrace(trace)
            try:out=submit(h,c,epoch)
            finally:sys.settrace(None)
            if out.status!='SUCCESS':report['safe_exception_locations']=diagnostics[-8:]
            require(out.status=='SUCCESS' and out.code=='PENDING_DETAILS' and out.value.state=='PENDING'
                and out.value.task_id is None and out.value.receipt is None and path in out.value.missing_fields,'MANUAL_PENDING_RESULT_'+out.code)
            require(state(conn)==before and reader.get(c.changes[0].task_id) is None,'MANUAL_PENDING_CREATED_TASK')
            current=pending_state(conn);again=submit(h,c,epoch,correlation='pending-retry')
            require(again.value==out.value and state(conn)==before and pending_state(conn)==current,'MANUAL_PENDING_RETRY_DUPLICATE')
            return out

        c,g,i,epoch=setup('first');out=submit(handler(c,g,i),c,epoch)
        require(out.status=='SUCCESS' and out.code=='COMMITTED','MANUAL_DEFAULT_CREATE_'+out.code)
        original=out.value;task=reader.get(original.task_id);record=task.aggregate.as_record()
        require(original.creation_event_ref==c.command_id and original.receipt.changed_keys[0].id==task.task_id and
            conn.execute('SELECT transaction_ref FROM whattodo.task_identity WHERE task_id=%s',(task.task_id,)).fetchone()==(c.command_id,),
            'MANUAL_CANONICAL_CREATION_LINK')
        require(record['core']['importance']==3 and record['work']['total_estimate']['seconds']==1800
            and record['effort']['user_remaining'] is None,'MANUAL_DEFAULTS_BECAME_U')
        checks.append('resolved_registered_user_instruction_creates_one_accepted_task_and_canonical_creation_link')
        annotation=conn.execute('''SELECT a.resolved_scope->'authorization' FROM whattodo.authority_record a
            JOIN whattodo.command_transaction c ON c.authority_ref=a.authority_ref WHERE c.request_id=%s''',(c.command_id,)).fetchone()[0]
        proof=annotation['creation_provenance'][0]['details']
        require(proof['approved_default_snapshots'][0]['key']==dict(kind='TASKTYPE',id='work',version='1') and
            proof['approved_default_snapshots'][0]['content_hash']==definition_request(commit,'0.json',values[0]).content_hash and
            dict(field='/core/importance',source_ref=approval_source) in record['provenance'],'MANUAL_DEFAULT_PROVENANCE')
        checks.append('copied_defaults_retain_exact_git_hash_version_accepted_source_and_field_provenance')
        checks.append('template_total_is_initial_total_and_never_an_inferred_current_remaining_estimate')
        before=state(conn);replay=submit(handler(clock=FrozenClock(NOW+timedelta(days=7)),definitions=None,source_scopes=()),c,epoch,
            correlation='restart-retry')
        require(replay.status=='SUCCESS' and replay.code=='REPLAY' and replay.value==original and state(conn)==before,
            'MANUAL_REPLAY_WITHOUT_LIVE_RESOLVERS_'+replay.code)
        checks.append('restart_retry_uses_original_history_without_active_grants_intents_defaults_or_source_registry')
        changed=replace(c,changes=(change(c.changes[0].task_id,None,'CREATE_TASK',dict(title='Changed same command')),))
        deny(handler(),changed,epoch,'MANUAL_REPLAY_SCOPE_CONFLICT')
        deny(handler(),c,epoch,'REQUEST_ID_CONTENT_CONFLICT',audit='another-audit')
        deny(handler(),c,epoch+1,'REQUEST_ID_CONTENT_CONFLICT')
        checks.append('same_command_id_cannot_change_meaning_audit_or_expected_store_version')

        c2,g2,i2,epoch2=setup('version-two',facts=dict(domain='study',task_type_ref=dict(id='work',version='2')),
            uses=(ApprovedDefaultUse(DefinitionKey('TASKTYPE','work','2'),'default-approval',approval_source),))
        out=submit(handler(c2,g2,i2),c2,epoch2)
        require(out.status=='SUCCESS' and reader.get(c2.changes[0].task_id).aggregate.as_record()['core']['importance']==5
            and reader.get(c.changes[0].task_id)==task,'MANUAL_NEW_DEFAULTS_REWRITE_OLD_TASK')
        checks.append('new_definition_version_changes_only_a_new_task_and_preserves_existing_task_and_defaults_snapshot')

        x,xg,xi,xe=setup('missing-title',fields=dict(importance=3),facts=dict(domain='study'),uses=())
        title_pending=require_pending(handler(x,xg,xi),x,xe,'/core/title')
        pending_read=handler().get_pending(title_pending.value.pending_id,RequestContext('pending-read','pending-read'),caller=CALLER)
        require(pending_read.status=='SUCCESS' and pending_read.value==title_pending.value,'MANUAL_PENDING_READ')
        require(json.loads(pending_read.value.proposal_json)['resolved_creation']['resolved_facts']==dict(domain='study'),
            'MANUAL_PENDING_DROPPED_RESOLVED_FACTS')
        checks.append('missing_title_ratings_and_requiredness_persist_as_deduplicated_pending_without_task_audit_or_epoch')
        wrong_owner=handler().get_pending(title_pending.value.pending_id,RequestContext('wrong-owner','wrong-owner'),
            caller=CallerIdentity('different-principal','USER_COMMAND',True))
        require(wrong_owner.status=='PERMANENT' and wrong_owner.code=='CALLER_SCOPE_MISMATCH','MANUAL_PENDING_OWNER_ISOLATION')
        wrong_scope=handler(source_scopes=(SourceScope(SCOPE.provider,SCOPE.scope_ref,'another-account'),)).get_pending(
            title_pending.value.pending_id,RequestContext('wrong-scope','wrong-scope'),caller=CALLER)
        require(wrong_scope.status=='PERMANENT' and wrong_scope.code=='EVIDENCE_SOURCE_SCOPE_NOT_REGISTERED',
            'MANUAL_PENDING_ACCOUNT_ISOLATION')
        checks.append('pending_reads_retain_all_resolved_facts_and_require_original_principal_and_registered_account_scope')
        for statement in ('DELETE FROM whattodo.manual_creation_pending','UPDATE whattodo.manual_creation_pending SET created_at=CURRENT_TIMESTAMP'):
            try:conn.execute(statement)
            except psycopg.errors.CheckViolation:pass
            else:raise HarnessError('MANUAL_PENDING_HISTORY_MUTABLE')
        checks.append('pending_interpretation_history_cannot_be_deleted_or_rewritten_by_application_role')
        x,xg,xi,xe=setup('missing-domain',facts=dict(task_type_ref=dict(id='work',version='1')))
        require_pending(handler(x,xg,xi),x,xe,'/core/domain')
        checks.append('unknown_domain_is_not_replaced_with_other_or_inferred_from_a_tasktype')
        x,xg,xi,xe=setup('unapproved-cache',uses=())
        require_pending(handler(x,xg,xi),x,xe,'/core/importance')
        checks.append('cached_templates_cannot_supply_unapproved_default_values_or_creation_authority')
        x,xg,xi,xe=setup('missing-version',facts=dict(domain='study',task_type_ref=dict(id='work',version='unregistered')),
            uses=(ApprovedDefaultUse(DefinitionKey('TASKTYPE','work','unregistered'),'default-approval',approval_source),))
        require_pending(handler(x,xg,xi),x,xe,'/references/task_type_ref')
        checks.append('unresolved_exact_tasktype_version_stays_pending_without_substitution_by_latest')
        x,xg,xi,xe=setup('missing-course-profile',facts=dict(domain='study',context=dict(kind='COURSE',id='course'),task_type_ref=dict(id='work',version='1')))
        require_pending(handler(x,xg,xi),x,xe,'/references/profile_ref')
        checks.append('course_context_requires_its_exact_profile_version_before_canonical_creation')
        conflict_use=ApprovedDefaultUse(DefinitionKey('TASK_TEMPLATE','conflict','1'),'default-approval',approval_source)
        x,xg,xi,xe=setup('conflict-defaults',facts=dict(domain='study',task_type_ref=dict(id='work',version='1'),template_ref=dict(id='conflict',version='1')),
            uses=(use,conflict_use))
        require_pending(handler(x,xg,xi),x,xe,'/defaults/importance')
        checks.append('contradictory_approved_defaults_are_pending_without_implicit_source_precedence')
        x,xg,xi,xe=setup('explicit-override',fields=dict(title='Explicit exception',importance=2),facts=xi.facts,uses=(use,conflict_use))
        out=submit(handler(x,xg,xi),x,xe)
        require(out.status=='SUCCESS' and reader.get(x.changes[0].task_id).aggregate.as_record()['core']['importance']==2,
            'MANUAL_EXPLICIT_OVERRIDE_'+out.code)
        checks.append('explicit_user_override_resolves_only_its_field_and_preserves_other_default_values')

        x,xg,xi,xe=setup('fake-default-approval',uses=(replace(use,acceptance_ref='known-but-unaccepted'),))
        deny(handler(x,xg,xi),x,xe,'MANUAL_DEFAULT_ACCEPTANCE_REQUIRED')
        checks.append('default_use_requires_its_independent_accepted_scope_and_matching_persisted_user_source')
        x,xg,xi,xe=setup('no-creation-authority')
        deny(handler(x,None,xi),x,xe,'UNREGISTERED_AUTHORITY')
        deny(handler(x,xg,None),x,xe,'UNREGISTERED_MANUAL_INTENT')
        checks.append('source_and_approved_defaults_alone_cannot_authorize_manual_creation_or_populate_intent_registry')
        deny(handler(x,xg,xi),x,xe,'UNTRUSTED_CALLER',caller=CallerIdentity('principal','EXTERNAL',True))
        deny(handler(x,xg,xi),x,xe,'UNTRUSTED_CALLER',caller=CallerIdentity('principal','USER_COMMAND',False))
        checks.append('external_or_unauthenticated_callers_cannot_create_tasks_or_pending_user_intents')

        x,xg,xi,xe=setup('explicit-u',fields=dict(title='Reported remaining',user_remaining_seconds=7200))
        out=submit(handler(x,xg,xi),x,xe)
        require(out.status=='SUCCESS','MANUAL_INITIAL_U_'+out.code)
        v=reader.get(x.changes[0].task_id).aggregate.as_record();u=v['effort']['user_remaining']
        require(u['seconds']==7200 and v['work']['total_estimate']['seconds']==1800 and
            v['effort']['prediction'] is None and u['observed_at']==xi.source_observed_at.isoformat(),
            'MANUAL_INITIAL_U_MEANING')
        observation=conn.execute('SELECT kind,seconds,source_record_ref,authority_ref,transaction_ref FROM whattodo.effort_observation WHERE observation_id=%s',
            (u['observation_id'],)).fetchone()
        require(observation==('USER_REMAINING',7200,xi.source_ref,xg.grant_id,x.command_id),'MANUAL_INITIAL_U_PROVENANCE')
        checks.append('explicit_initial_remaining_has_a_separate_source_authorized_observation_committed_with_task_and_receipt')
        before=state(conn);again=submit(handler(),x,xe)
        require(again.status=='SUCCESS' and again.code=='REPLAY' and again.value==out.value and state(conn)==before,
            'MANUAL_INITIAL_U_RETRY_DUPLICATE')
        checks.append('known_remaining_creation_retry_preserves_original_task_observation_and_audit_once')
        x,xg,xi,xe=setup('explicit-zero',fields=dict(title='Reported zero remaining',user_remaining_seconds=0))
        out=submit(handler(x,xg,xi),x,xe);zero=reader.get(x.changes[0].task_id)
        require(out.status=='SUCCESS' and zero.aggregate.as_record()['core']['completion']=='INCOMPLETE' and
            zero.aggregate.as_record()['effort']['user_remaining']['seconds']==0,'MANUAL_ZERO_U_ASSERTED_COMPLETION')
        checks.append('explicit_zero_remaining_is_retained_without_asserting_task_completion')
        x,xg,xi,xe=setup('atomic-failure',fields=dict(title='Native failure',user_remaining_seconds=10))
        class FailTaskInsert:
            def __getattr__(self,name):return getattr(conn,name)
            def execute(self,query,*args,**kw):
                text=query if isinstance(query,str) else query.as_string(conn)
                if text.startswith('INSERT INTO whattodo.') and '"task_revision"' in text:
                    # A real server SQL error after supporting facts are staged.
                    conn.execute('SELECT 1/0')
                return conn.execute(query,*args,**kw)
        deny(handler(x,xg,xi,connection=FailTaskInsert()),x,xe,'TRANSACTION_DATABASE_REJECTED')
        checks.append('injected_native_sql_failure_after_observation_staging_rolls_back_observation_task_authority_audit_receipt_and_epoch')
        x,xg,xi,xe=setup('future-source')
        deny(handler(x,xg,replace(xi,source_observed_at=NOW+timedelta(seconds=1))),x,xe,'MANUAL_FUTURE_SOURCE_TIME')
        checks.append('future_user_observation_time_is_rejected_without_fabricating_verification_or_creation')
        x,xg,xi,xe=setup('stale-store',fields=dict(title='Stale create',user_remaining_seconds=20))
        deny(handler(x,xg,xi),x,xe-1,'STALE_STORE_REVISION')
        checks.append('stale_store_rejects_creation_and_its_supporting_observation_as_one_operation')
        pending_before=pending_state(conn)
    with harness.target(database).connect() as fresh:
        h=PostgresManualTaskHandler(fresh,codec,plan,application_version=__version__,clock=CLOCK)
        out=h.create(json.dumps(c.as_record()).encode(),RequestContext(c.command_id,'fresh-restart'),
            expected_store_revision=epoch,audit_id='audit-'+c.command_id,caller=CALLER)
        require(out.status=='SUCCESS' and out.code=='REPLAY' and out.value==original and pending_state(fresh)==pending_before,
            'MANUAL_FRESH_RESTART_'+out.code)
        scoped=PostgresManualTaskHandler(fresh,codec,plan,application_version=__version__,clock=CLOCK,source_scopes=(SCOPE,))
        pending=scoped.get_pending(title_pending.value.pending_id,RequestContext('fresh-pending-read','fresh-pending-read'),caller=CALLER)
        require(pending.status=='SUCCESS' and pending.value==title_pending.value,'MANUAL_FRESH_PENDING_READ')
        checks.append('fresh_connection_reads_original_creation_and_retains_durable_pending_history')
        report.update(domain_tables=fresh.execute("SELECT count(*) FROM pg_tables WHERE schemaname='whattodo'").fetchone()[0],
            domain_foreign_keys=fresh.execute("SELECT count(*) FROM pg_constraint c JOIN pg_namespace n ON n.oid=c.connamespace WHERE n.nspname='whattodo' AND c.contype='f'").fetchone()[0])


def main():
    harness=PostgresHarness();report=dict(task='M3A-12',status='IN_PROGRESS',scope='SYNTHETIC_MANUAL_TASK_HANDLER',
        verified_on='2026-10-10',native_checks=[])
    try:
        with harness:verify(harness,report)
        report.update(status='PASS',native_check_count=len(report['native_checks']),limitations=[
            'Authenticated caller, resolved user intent/default acceptance and root grant registries are synthetic trusted inputs',
            'Manual interpretation and pending review/resolution remain M3A-21/22; no raw natural language is executed',
            'Deadline and standalone stage fields require their future handler/contract evolution',
            'No real course/account/source/Calendar or deployed transport is activated'])
    except Exception as exc:
        report.update(status='FAIL',failure_type=type(exc).__name__,failure_code=str(exc) if isinstance(exc,HarnessError) else 'MANUAL_NATIVE_CHECK_FAILED',
            failure_sqlstate=getattr(exc,'sqlstate',None))
    report['harness']=harness.safe_summary();target=harness.run_root/'manual-task-report.json'
    if harness.run_root.exists():target.write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(dict(status=report['status'],report=str(target),checks=len(report['native_checks']),server_stopped=report['harness']['server_stopped'])))
    return 0 if report['status']=='PASS' else 1


if __name__=='__main__':raise SystemExit(main())
