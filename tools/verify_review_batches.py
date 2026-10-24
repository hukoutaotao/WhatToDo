"""Owned native batch-confirmation probes; one invalid member rejects the batch."""
from copy import deepcopy
from dataclasses import replace
from datetime import timedelta
from hashlib import sha256
import json
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:sys.path.insert(0,str(ROOT))
from src import __version__
from src.adapters.clocks import FrozenClock
from src.adapters.contract_json import ContractJSONCodec
from src.adapters.extension_contracts import load_supported_schemas
from src.adapters.memory_definitions import MemoryDefinitionRepository
from src.adapters.migration_files import load_migration_plan,migration_body
from src.adapters.postgres_authorization import register_grant
from src.adapters.postgres_evidence import PostgresEvidenceRepository
from src.adapters.postgres_fact_patches import PostgresFactPatchHandler,register_fact_patch_grant
from src.adapters.postgres_manual_tasks import PostgresManualTaskHandler
from src.adapters.postgres_migrations import apply_migrations,schema_checked_transaction,DatabaseRoles
from src.adapters.postgres_review_batches import PostgresReviewBatchHandler,register_review_batch_grant
from src.adapters.postgres_tasks import PostgresTaskRepository
from src.application.definitions import canonical
from src.application.evidence_storage import SourceScope
from src.application.fact_patches import FactPatch,FactPatchGrant
from src.application.manual_tasks import ResolvedManualIntent
from src.application.migrations import MigrationStep
from src.application.ports import RequestContext
from src.application.review_batches import BatchMember,ReviewBatchCommand,ReviewBatchGrant,ReviewBatchJournal
from src.domain.authorization import AuthorityGrant,CallerIdentity,Command,change
from src.domain.provenance import capture_source
from src.application.transactions import TransactionError
from tools.postgres_harness import PostgresHarness,HarnessError,ROLES,require
from tools import verify_lifecycle as fixtures

NOW=fixtures.NOW;CLOCK=fixtures.CLOCK;CALLER=fixtures.CALLER;SCOPE=fixtures.SCOPE


def batch_plan():
    """Require the activated exact review-batch step; never append an unpinned candidate."""
    base=load_migration_plan(root=ROOT)
    source=(ROOT/'database/runtime-migrations/019_review_batches.sql').read_text(encoding='utf-8')
    step=MigrationStep('019_review_batches',sha256(source.encode()).hexdigest(),'0.15.0-review-batches',source,migration_body(source))
    require(len(base.steps)>=20 and base.steps[19]==step,'REVIEW_BATCH_MIGRATION_PIN_DRIFT')
    return base


def verify(h,report):
    import psycopg
    plan=batch_plan();initial=len(h._created)
    setup=dict(native_checks=[])
    fixtures.verify(h,setup,migration_plan=replace(plan,steps=plan.steps[:19]))
    require(len(h._created)==initial+1,'REVIEW_BATCH_FIXTURE_DATABASE_COUNT')
    database=h._created[-1]
    roles=DatabaseRoles(ROLES['migration'],ROLES['application'],ROLES['test'])
    codec=ContractJSONCodec(load_supported_schemas(root=ROOT));checks=report['native_checks']
    report['fixture_native_check_count']=len(setup['native_checks'])
    with h.target(database,'migration').connect() as owner:
        prefix=owner.execute('SELECT * FROM whattodo_meta.migration_history ORDER BY position').fetchall()
        old_payloads=owner.execute('SELECT task_id,task_revision,raw_bytes FROM whattodo.task_payload_revision ORDER BY 1,2').fetchall()
        applied=apply_migrations(owner,plan,roles=roles,application_version=__version__)
        require(applied.applied==('019_review_batches',) and owner.execute(
            'SELECT * FROM whattodo_meta.migration_history WHERE position<=19 ORDER BY position').fetchall()==prefix
            and owner.execute('SELECT task_id,task_revision,raw_bytes FROM whattodo.task_payload_revision ORDER BY 1,2').fetchall()==old_payloads,
            'REVIEW_BATCH_UPGRADE_REWROTE_HISTORY')
    checks.append('pinned_twentieth_step_preserves_all_nineteen_prior_migration_and_task_payload_history')
    with h.target(database).connect() as conn:
        reader=PostgresTaskRepository(conn,codec,plan,application_version=__version__,clock=CLOCK)
        def epoch():return conn.execute('SELECT revision FROM whattodo.store_epoch').fetchone()[0]
        def evidence(name,kind='USER',captured=None):
            raw=('synthetic batch statement '+name).encode()
            source=capture_source(provider=SCOPE.provider,scope_ref=SCOPE.scope_ref,external_id=name,
                raw_bytes=raw,captured_at=captured or NOW-timedelta(minutes=1),source_type=kind)
            PostgresEvidenceRepository(conn,codec,plan,application_version=__version__,clock=CLOCK,scopes=(SCOPE,)).observe_source(
                canonical(source.as_record()).encode(),raw_content=raw,locator_ref='synthetic-'+name)
            return source
        def create(name,*,seconds=600):
            fields=dict(title='Batch task '+name,importance=3,requiredness='REQUIRED',
                difficulty=dict(thinking_depth=2,repetitive_volume=2,new_learning_load=3),user_remaining_seconds=seconds)
            c=Command('create-'+name,'principal','USER_COMMAND','create-grant-'+name,(change(name,None,'CREATE_TASK',fields),))
            source=evidence('create-'+name)
            g=AuthorityGrant(c.authority_ref,c.principal_id,c.origin,c.command_id,c.changes,source.record_id,
                NOW-timedelta(minutes=2),expires_at=NOW+timedelta(hours=1))
            with h.target(database,'migration').connect() as owner:
                register_grant(owner,g,plan,application_version=__version__)
            intent=ResolvedManualIntent(c.fingerprint,source.record_id,NOW-timedelta(minutes=1),
                canonical(dict(domain='study',total_estimate_seconds=1800)))
            out=PostgresManualTaskHandler(conn,codec,plan,application_version=__version__,clock=CLOCK,
                definitions=MemoryDefinitionRepository(CLOCK),grants=(g,),source_scopes=(SCOPE,),intents=(intent,)).create(
                canonical(c.as_record()).encode(),RequestContext(c.command_id,'correlation'),expected_store_revision=epoch(),
                audit_id='audit-'+c.command_id,caller=CALLER)
            require(out.code=='COMMITTED','REVIEW_BATCH_CREATE_'+out.code)
            return reader.get(name),source.record_id
        def batch_command(name,member_tuple,*,confirmed=True,no_work=None,principal='principal'):
            return ReviewBatchCommand(name,principal,'batch-grant-'+name,'review-1',3,'statement-'+name,
                'batch-'+name,confirmed,member_tuple,no_work)
        def grant_for(command):
            source=evidence('batch-'+command.command_id)
            return ReviewBatchGrant(command,source.record_id,NOW-timedelta(minutes=2),
                NOW-timedelta(minutes=1),NOW+timedelta(hours=1))
        def handler(grants):
            return PostgresReviewBatchHandler(conn,codec,plan,application_version=__version__,clock=CLOCK,grants=grants)
        def submit(command,*,g=None,grants=None,caller=CALLER):
            g=g or grant_for(command)
            with h.target(database,'migration').connect() as owner:
                register_review_batch_grant(owner,g,plan,application_version=__version__)
            return handler((g,) if grants is None else grants).confirm(canonical(command.as_record()).encode(),
                RequestContext(command.command_id,'native-batch'),expected_store_revision=epoch(),
                audit_id='audit-'+command.command_id,caller=caller)
        def members(*records):
            return tuple(BatchMember(r.task_id,r.revision,r.aggregate.as_record()['effort']['user_remaining']['observation_id'],
                r.aggregate.as_record()['effort']['user_remaining']['seconds']) for r in records)
        def state():
            return tuple(conn.execute('SELECT * FROM whattodo.'+t+' ORDER BY 1,2').fetchall() for t in
                ('task_identity','task_revision','task_payload_revision','command_transaction','authority_record',
                 'audit_entry','audit_change','effort_observation','store_epoch','review_batch_confirmation','review_batch_verification'))
        def deny(command,code,*,caller=CALLER):
            g=grant_for(command)
            with h.target(database,'migration').connect() as owner:
                register_review_batch_grant(owner,g,plan,application_version=__version__)
            before=state();out=handler((g,)).confirm(canonical(command.as_record()).encode(),
                RequestContext(command.command_id,'native-batch'),expected_store_revision=epoch(),
                audit_id='audit-'+command.command_id,caller=caller)
            require(out.status in ('CONFLICT','PERMANENT','RETRYABLE') and out.code==code,'REVIEW_BATCH_NEGATIVE_'+out.code)
            require(state()==before,'REVIEW_BATCH_NEGATIVE_MUTATED');return out

        first,first_source=create('batch-first');second,second_source=create('batch-second')
        worked,worked_source=create('batch-worked')
        base_epoch=epoch();first_before=deepcopy(first.aggregate.as_record())
        second_before=deepcopy(second.aggregate.as_record())
        command=batch_command('confirm-one',members(first,second))
        first_grant=grant_for(command)
        with h.target(database,'migration').connect() as owner:
            register_review_batch_grant(owner,first_grant,plan,application_version=__version__)
        out=handler((first_grant,)).confirm(canonical(command.as_record()).encode(),
            RequestContext(command.command_id,'native-batch'),expected_store_revision=base_epoch,
            audit_id='audit-'+command.command_id,caller=CALLER)
        require(out.status=='SUCCESS' and out.code=='REVIEW_BATCH_CONFIRMED','REVIEW_BATCH_CONFIRM_'+out.code)
        value=out.value
        require(epoch()==base_epoch+1 and value.receipt.store_revision==base_epoch+1,'REVIEW_BATCH_EPOCH')
        current=reader.get('batch-first');later=reader.get('batch-second')
        require(current.revision==first.revision==1 and current.aggregate.as_record()==first_before
            and later.aggregate.as_record()==second_before,'REVIEW_BATCH_TASK_MUTATED')
        estimate=current.aggregate.as_record()['effort']['user_remaining']
        require(estimate['verified_at']==first_before['effort']['user_remaining']['verified_at'],
            'REVIEW_BATCH_U_VERIFIED_TIME_CHANGED')
        verification=conn.execute('SELECT task_id,task_revision,observation_id,seconds,observed_at,verified_at FROM whattodo.review_batch_verification'
            ' WHERE batch_record_id=%s ORDER BY task_id',(value.journal.record_id,)).fetchall()
        from src.domain.task_aggregate import instant as _instant
        require(verification==[(m.task_id,m.expected_revision,m.observation_id,m.seconds,
            _instant(estimate['observed_at']),value.journal.source_observed_at) for m in sorted(command.members,key=lambda m:m.task_id)],
            'REVIEW_BATCH_VERIFICATION_ROWS')
        unchanged=conn.execute("SELECT kind,seconds,observed_at,batch_ref FROM whattodo.effort_observation WHERE kind='UNCHANGED_VERIFICATION'"
            ' AND batch_ref=%s ORDER BY observation_id',(value.journal.record_id,)).fetchall()
        require(len(unchanged)==2 and all(row[1] is None and row[2]==value.journal.source_observed_at for row in unchanged),
            'REVIEW_BATCH_UNCHANGED_OBSERVATIONS')
        checks.append('confirmed_batch_verifies_each_untouched_estimate_with_separate_time_without_task_or_u_mutation')

        # Worked-on after the estimate is excluded, rejecting the whole batch.
        with h.target(database,'migration').connect() as owner:
            owner.execute('INSERT INTO whattodo.effort_observation VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)',
                ('worked-after','batch-worked','ACTUAL_WORK',300,NOW-timedelta(seconds=30),NOW,
                    worked_source,'create-grant-batch-worked',None,'create-batch-worked'))
        deny(batch_command('confirm-worked',members(worked)),'REVIEW_BATCH_MEMBER_WORKED_ON')
        checks.append('task_worked_on_after_the_estimate_is_excluded_and_rejects_the_whole_batch')

        # Silence confirms none: an unconfirmed batch records no verification.
        quiet=batch_command('confirm-silent',members(second),confirmed=None)
        out=submit(quiet)
        require(out.status=='SUCCESS' and out.code=='REVIEW_BATCH_NOT_CONFIRMED' and out.value.state=='NOT_CONFIRMED',
            'REVIEW_BATCH_SILENT_'+out.code)
        require(conn.execute('SELECT count(*) FROM whattodo.review_batch_verification WHERE batch_record_id=%s',
            (out.value.journal.record_id,)).fetchone()==(0,),'REVIEW_BATCH_SILENT_VERIFIED')
        checks.append('silence_confirms_none_and_an_unconfirmed_batch_records_no_member_verification')

        # Stale member version conflicts instead of silently approving.
        patch=FactPatch('bump-worked','principal','bump-grant','batch-worked',worked.revision,canonical(dict(importance=5)))
        bump_source=evidence('bump-worked')
        patch_grant=FactPatchGrant(patch,bump_source.record_id,NOW-timedelta(minutes=2),NOW+timedelta(hours=1),NOW)
        with h.target(database,'migration').connect() as owner:
            register_fact_patch_grant(owner,patch_grant,plan,application_version=__version__)
        out=PostgresFactPatchHandler(conn,codec,plan,application_version=__version__,clock=CLOCK,grants=(patch_grant,),
            source_scopes=(SCOPE,)).patch(canonical(patch.as_record()).encode(),RequestContext('bump-worked','correlation'),
            expected_store_revision=epoch(),audit_id='audit-bump',caller=CALLER)
        require(out.code=='COMMITTED','REVIEW_BATCH_BUMP_'+out.code)
        deny(batch_command('confirm-stale',members(worked)),'REVIEW_BATCH_STALE_MEMBER')
        checks.append('stale_member_version_conflicts_instead_of_silently_approving_changed_values')

        # A changed estimate identity or seconds is excluded.
        head=reader.get('batch-worked')
        deny(batch_command('confirm-changed',(BatchMember(head.task_id,head.revision,'observation-other',600),)),
            'REVIEW_BATCH_CHANGED_ESTIMATE')
        deny(batch_command('confirm-missing',(BatchMember(head.task_id,head.revision,
            head.aggregate.as_record()['effort']['user_remaining']['observation_id'],9999),)),
            'REVIEW_BATCH_CHANGED_ESTIMATE')
        checks.append('changed_estimate_identity_or_seconds_is_excluded_from_confirmation')

        # Overlapping confirmed batches are rejected at the boundary and by SQL.
        deny(batch_command('confirm-overlap',members(first)),'REVIEW_BATCH_OVERLAPPING_VERIFICATION')
        row=conn.execute('''SELECT verification_id,batch_record_id,task_id,task_revision,observation_id,seconds,observed_at,verified_at,
            no_work_statement,transaction_ref,audit_change_ref,runtime_payload FROM whattodo.review_batch_verification LIMIT 1''').fetchone()
        from psycopg import sql
        from psycopg.types.json import Jsonb
        forged=dict(row[11]);forged['verification_id']='verification-'+'d'*64
        try:
            with conn.transaction():
                conn.execute(sql.SQL('INSERT INTO whattodo.review_batch_verification ({}) VALUES ({})').format(
                    sql.SQL(',').join(map(sql.Identifier,('verification_id','batch_record_id','aggregate_kind','revision','task_id','task_revision','estimate_kind',
                        'observation_id','seconds','observed_at','verified_at','no_work_statement','transaction_ref','audit_change_ref','runtime_payload'))),
                    sql.SQL(',').join(sql.Placeholder() for _ in range(15))),
                    ('verification-'+'d'*64,row[1],'REVIEW_VERIFICATION',1,row[2],row[3],'USER_REMAINING',row[4],row[5],row[6],row[7],row[8],row[9],row[10],Jsonb(forged)))
        except psycopg.errors.UniqueViolation:pass
        else:require(False,'REVIEW_BATCH_OVERLAP_NOT_ENFORCED')
        checks.append('overlapping_confirmed_batches_are_rejected_by_handler_and_sql_unique_constraint')

        # Original command replay returns the original receipt without duplicates.
        before=state();replay=handler((first_grant,)).confirm(canonical(command.as_record()).encode(),
            RequestContext(command.command_id,'native-batch'),expected_store_revision=base_epoch,
            audit_id='audit-'+command.command_id,caller=CALLER)
        require(replay.status=='SUCCESS' and replay.code=='REVIEW_BATCH_REPLAYED' and replay.value.receipt==value.receipt
            and replay.value.journal==value.journal and state()==before,'REVIEW_BATCH_REPLAY_'+replay.code)
        checks.append('original_command_replay_returns_original_receipt_and_journal_without_duplicate_effects')

        # Foreign principals, foreign callers and unregistered grants are denied.
        deny(batch_command('confirm-foreign',members(first),principal='intruder'),'REVIEW_BATCH_MEMBER_NOT_OWNED',
            caller=CallerIdentity('intruder','USER_COMMAND',True))
        deny(batch_command('confirm-external',members(first)),'UNTRUSTED_CALLER',
            caller=CallerIdentity('principal','EXTERNAL',True))
        unregistered=batch_command('confirm-unregistered',members(first))
        before=state();out=handler(()).confirm(canonical(unregistered.as_record()).encode(),
            RequestContext(unregistered.command_id,'native-batch'),expected_store_revision=epoch(),
            audit_id='audit-'+unregistered.command_id,caller=CALLER)
        require(out.code=='REVIEW_BATCH_INDEPENDENT_GRANT_REQUIRED' and state()==before,'REVIEW_BATCH_UNREGISTERED_'+out.code)
        checks.append('foreign_principal_and_unregistered_grant_cannot_confirm_any_member')

        # Stored history is immutable.
        for table in ('review_batch_confirmation','review_batch_verification'):
            for verb in ('UPDATE whattodo.'+table+' SET revision=revision','DELETE FROM whattodo.'+table):
                try:
                    with conn.transaction():conn.execute(verb)
                except psycopg.errors.CheckViolation:pass
                else:require(False,'REVIEW_BATCH_HISTORY_NOT_IMMUTABLE')
        checks.append('application_role_cannot_update_or_delete_batch_or_verification_history')

        tables_count=conn.execute("SELECT count(*) FROM pg_tables WHERE schemaname='whattodo'").fetchone()[0]
        fk_count=conn.execute("SELECT count(*) FROM pg_constraint c JOIN pg_namespace n ON n.oid=c.connamespace"
            " WHERE n.nspname='whattodo' AND c.contype='f'").fetchone()[0]
        report.update(schema_version=plan.schema_version,migration_steps=len(plan.steps),domain_tables=tables_count,
            domain_foreign_keys=fk_count,activated_steps=len(load_migration_plan(root=ROOT).steps))
        require(len(plan.steps)==20,'REVIEW_BATCH_STEP_COUNT')
    with h.target(database).connect() as fresh:
        stored=fresh.execute('SELECT runtime_payload FROM whattodo.review_batch_confirmation WHERE command_id=%s',('confirm-one',)).fetchone()[0]
        require(ReviewBatchJournal.from_payload(stored)==value.journal,'REVIEW_BATCH_FRESH_JOURNAL')
    checks.append('fresh_connection_reconstructs_the_original_journal_and_verification_payload')


def main():
    h=PostgresHarness();report=dict(task='M3B-09',status='IN_PROGRESS',
        scope='SYNTHETIC_SCOPED_UNCHANGED_ESTIMATE_BATCH_CONFIRMATION',native_checks=[])
    try:
        with h:verify(h,report)
        report.update(status='PASS',native_check_count=len(report['native_checks']),limitations=[
            'The prerequisite lifecycle fixture checks are reported separately and not counted as new batch checks',
            'Verification preserves estimates and never mutates Tasks, U or actual work',
            'Evening review coordination and answer submission remain separate cards',
            'No personal profile activation, live provider, n8n or deployment is claimed'])
    except Exception as exc:
        report.update(status='FAIL',failure_type=type(exc).__name__,failure_code=str(exc) if isinstance(exc,HarnessError) else 'REVIEW_BATCH_NATIVE_FAILED',
            failure_sqlstate=getattr(exc,'sqlstate',None),failed_migration=getattr(exc,'failed_migration',None))
    report['harness']=h.safe_summary();path=h.run_root/'review-batches-report.json'
    if h.run_root.exists():path.write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(dict(status=report['status'],report=str(path),checks=len(report['native_checks']),
        server_stopped=report['harness']['server_stopped'])))
    return 0 if report['status']=='PASS' else 1


if __name__=='__main__':raise SystemExit(main())
