"""Real PostgreSQL migration, replay, compatibility and interruption probes."""
from dataclasses import replace
from hashlib import sha256
import json
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:sys.path.insert(0,str(ROOT))
from src import __version__
from src.adapters.migration_files import load_migration_plan,migration_body
from src.adapters.postgres_migrations import DatabaseRoles,LOCK_KEY,apply_migrations,verify_schema_compatibility
from src.application.migrations import MigrationError
from tools.postgres_harness import HarnessError,PostgresHarness,ROLES,require

ROLE_CONFIG=DatabaseRoles(ROLES['migration'],ROLES['application'],ROLES['test'])


def step_source(step,source):
    return replace(step,source_sql=source,body_sql=migration_body(source),content_hash=sha256(source.encode()).hexdigest())


def error_code(action,code):
    try:action()
    except MigrationError as exc:
        require(str(exc)==code,'MIGRATION_UNEXPECTED_FAILURE_CODE')
        return exc
    raise HarnessError('MIGRATION_NEGATIVE_PROBE_ACCEPTED')


def run_native(harness,plan):
    import psycopg
    checks=[]
    database=harness.create_database(initialize_schema=False)
    with harness.target(database,'migration').connect() as conn:
        result=apply_migrations(conn,plan,roles=ROLE_CONFIG,application_version=__version__)
        require(result.applied==tuple(s.migration_id for s in plan.steps),'MIGRATION_NATIVE_ORDER')
        checks.append('all_current_steps_applied_in_order')
        tables=conn.execute("SELECT count(*) FROM pg_tables WHERE schemaname='whattodo'").fetchone()[0]
        fks=conn.execute("SELECT count(*) FROM pg_constraint c JOIN pg_namespace n ON n.oid=c.connamespace WHERE n.nspname='whattodo' AND c.contype='f'").fetchone()[0]
        require((tables,fks)==(89,230),'MIGRATION_DOMAIN_SCHEMA_COUNT')
        checks.append('extended_domain_schema_89_tables_230_foreign_keys')
        before=conn.execute('SELECT * FROM whattodo_meta.migration_history ORDER BY position').fetchall()
        require(conn.execute('SELECT count(*) FROM whattodo.schema_migration').fetchone()==(5,),'MIGRATION_LEGACY_RECEIPTS')
        checks.append('five_legacy_receipts_and_current_runtime_receipts')
        result=apply_migrations(conn,plan,roles=ROLE_CONFIG,application_version=__version__)
        require(result.applied==() and len(result.skipped)==len(plan.steps),'MIGRATION_REPLAY')
        require(conn.execute('SELECT * FROM whattodo_meta.migration_history ORDER BY position').fetchall()==before,'MIGRATION_REPLAY_CHANGED_HISTORY')
        checks.append('rerun_skips_all_steps_without_rewriting_receipts')
        changed=replace(plan,steps=plan.steps[:-1]+(step_source(plan.steps[-1],plan.steps[-1].source_sql+'-- changed source pin\n'),))
        error_code(lambda:apply_migrations(conn,changed,roles=ROLE_CONFIG,application_version=__version__),'MIGRATION_APPLIED_DRIFT')
        require(conn.execute('SELECT * FROM whattodo_meta.migration_history ORDER BY position').fetchall()==before,'MIGRATION_REJECTED_CHANGED_HISTORY')
        checks.append('changed_applied_pin_rejected_before_mutation')
        error_code(lambda:apply_migrations(conn,plan,roles=ROLE_CONFIG,application_version='9.0'),'MIGRATION_APPLICATION_INCOMPATIBLE')
        checks.append('unsupported_application_version_rejected_before_migration')
        older=replace(plan,steps=plan.steps[:-1])
        error_code(lambda:apply_migrations(conn,older,roles=ROLE_CONFIG,application_version=__version__),'MIGRATION_UNKNOWN_APPLIED_VERSION')
        checks.append('older_migration_bundle_cannot_downgrade_database')
    for role in ('application','test'):
        with harness.target(database,role).connect() as conn:
            compatible=verify_schema_compatibility(conn,plan,application_version=__version__)
            require(compatible.generation==len(plan.steps) and compatible.authority=='SCHEMA_COMPATIBILITY_ONLY','MIGRATION_STARTUP_GATE')
    checks.append('application_and_verifier_read_only_startup_pass')
    with harness.target(database).connect() as app:
        for statement,name in [
            ('UPDATE whattodo_meta.schema_state SET schema_version=\'forged\'','application_schema_state_write_denied'),
            ('DELETE FROM whattodo_meta.migration_history','application_migration_history_write_denied'),
            ('DELETE FROM whattodo_meta.migration_failure','application_migration_failure_write_denied'),
            ('DELETE FROM whattodo.schema_migration','application_legacy_receipt_write_denied')]:
            try:app.execute(statement)
            except psycopg.errors.InsufficientPrivilege:checks.append(name)
            else:raise HarnessError('MIGRATION_APPLICATION_METADATA_WRITE')
        error_code(lambda:apply_migrations(app,plan,roles=ROLE_CONFIG,application_version=__version__),'MIGRATION_OWNER_REQUIRED')
        checks.append('application_connection_cannot_execute_migrations')
    with harness.target(database,'migration').connect() as holder:
        require(holder.execute('SELECT pg_try_advisory_lock(%s)',(LOCK_KEY,)).fetchone()==(True,),'MIGRATION_LOCK_SETUP')
        try:
            with harness.target(database,'migration').connect() as contender:
                error_code(lambda:apply_migrations(contender,plan,roles=ROLE_CONFIG,application_version=__version__),'MIGRATION_BUSY')
            with harness.target(database).connect() as app:
                error_code(lambda:verify_schema_compatibility(app,plan,application_version=__version__),'MIGRATION_BUSY')
        finally:holder.execute('SELECT pg_advisory_unlock(%s)',(LOCK_KEY,))
    checks.extend(['concurrent_migration_is_busy_without_writes','startup_is_busy_during_migration'])

    failed_database=harness.create_database(initialize_schema=False)
    bad_source=plan.steps[1].source_sql.removesuffix('COMMIT;\n')+'SELECT 1/0;\nCOMMIT;\n'
    bad_plan=replace(plan,steps=(plan.steps[0],step_source(plan.steps[1],bad_source),*plan.steps[2:]))
    with harness.target(failed_database,'migration').connect() as conn:
        error=error_code(lambda:apply_migrations(conn,bad_plan,roles=ROLE_CONFIG,application_version=__version__),'MIGRATION_STEP_FAILED')
        require(error.failed_migration==plan.steps[1].migration_id and error.sqlstate=='22012' and error.applied==(plan.steps[0].migration_id,),'MIGRATION_FAILED_DETAILS')
        require(conn.execute("SELECT EXISTS(SELECT 1 FROM pg_namespace WHERE nspname='whattodo')").fetchone()==(False,),'MIGRATION_FAILED_DDL_LEAK')
        require(conn.execute('SELECT count(*) FROM whattodo_meta.migration_history').fetchone()==(1,),'MIGRATION_FAILED_RECEIPT_LEAK')
        require(conn.execute('SELECT generation,recovery_required,failed_migration_id FROM whattodo_meta.schema_state').fetchone()==(1,True,plan.steps[1].migration_id),'MIGRATION_FAILED_STATE')
        require(conn.execute('SELECT content_hash,error_code FROM whattodo_meta.migration_failure').fetchone()==(bad_plan.steps[1].content_hash,'22012'),'MIGRATION_FAILURE_RECORD')
    checks.extend(['sql_failure_rolls_back_whole_step_and_receipt','successful_prefix_survives_later_failure','failure_candidate_hash_sqlstate_and_recovery_flag_retained'])
    with harness.target(failed_database).connect() as app:
        error_code(lambda:verify_schema_compatibility(app,plan,application_version=__version__),'MIGRATION_RECOVERY_REQUIRED')
    checks.append('application_startup_blocked_after_failed_migration')
    with harness.target(failed_database,'migration').connect() as conn:
        result=apply_migrations(conn,plan,roles=ROLE_CONFIG,application_version=__version__)
        require(len(result.applied)==len(plan.steps)-1 and len(result.skipped)==1,'MIGRATION_FAILED_RETRY')
        require(conn.execute('SELECT recovery_required,failed_migration_id FROM whattodo_meta.schema_state').fetchone()==(False,None),'MIGRATION_RECOVERY_CLEAR')
        require(conn.execute('SELECT count(*) FROM whattodo_meta.migration_failure').fetchone()==(1,),'MIGRATION_FAILURE_HISTORY_LOST')
    checks.append('retry_pending_step_clears_flag_and_preserves_failure_history')
    with harness.target(failed_database).connect() as app:verify_schema_compatibility(app,plan,application_version=__version__)
    checks.append('recovered_application_startup_passes')

    bootstrap_database=harness.create_database(initialize_schema=False)
    broken_meta=step_source(plan.steps[0],plan.steps[0].source_sql.removesuffix('COMMIT;\n')+'SELECT 1/0;\nCOMMIT;\n')
    with harness.target(bootstrap_database,'migration').connect() as conn:
        error_code(lambda:apply_migrations(conn,replace(plan,steps=(broken_meta,*plan.steps[1:])),roles=ROLE_CONFIG,application_version=__version__),'MIGRATION_STEP_FAILED')
        require(conn.execute("SELECT to_regclass('whattodo_meta.schema_state')").fetchone()==(None,),'MIGRATION_BOOTSTRAP_ROLLBACK')
        require(len(apply_migrations(conn,plan,roles=ROLE_CONFIG,application_version=__version__).applied)==len(plan.steps),'MIGRATION_BOOTSTRAP_RETRY')
    checks.append('metadata_bootstrap_failure_is_empty_and_retryable')

    interrupted_database=harness.create_database(initialize_schema=False)
    class InterruptedConnection:
        def __init__(self,connection):self.connection=connection
        def __getattr__(self,name):return getattr(self.connection,name)
        def execute(self,statement,*args,**kwargs):
            result=self.connection.execute(statement,*args,**kwargs)
            if statement==plan.steps[1].body_sql:
                self.connection.close()
                raise psycopg.OperationalError('injected connection loss after DDL')
            return result
    with harness.target(interrupted_database,'migration').connect() as raw:
        error_code(lambda:apply_migrations(InterruptedConnection(raw),plan,roles=ROLE_CONFIG,application_version=__version__),'MIGRATION_FAILURE_RECORD_UNAVAILABLE')
    with harness.target(interrupted_database,'migration').connect() as conn:
        require(conn.execute("SELECT EXISTS(SELECT 1 FROM pg_namespace WHERE nspname='whattodo')").fetchone()==(False,),'MIGRATION_INTERRUPTED_DDL_LEAK')
        require(conn.execute('SELECT count(*) FROM whattodo_meta.migration_history').fetchone()==(1,),'MIGRATION_INTERRUPTED_RECEIPT_LEAK')
        require(len(apply_migrations(conn,plan,roles=ROLE_CONFIG,application_version=__version__).applied)==len(plan.steps)-1,'MIGRATION_INTERRUPTED_RETRY')
    checks.extend(['connection_loss_rolls_back_uncommitted_step','lost_failure_record_is_explicit_not_false_success','connection_loss_releases_lock_and_retries_successfully'])

    acknowledged_database=harness.create_database(initialize_schema=False)
    class LostAcknowledgementConnection:
        def __init__(self,connection):self.connection=connection;self.transactions=0
        def __getattr__(self,name):return getattr(self.connection,name)
        def transaction(self):
            self.transactions+=1
            wrapped=self.connection.transaction();ordinal=self.transactions
            class Transaction:
                def __enter__(self):return wrapped.__enter__()
                def __exit__(self,kind,value,traceback):
                    result=wrapped.__exit__(kind,value,traceback)
                    if kind is None and ordinal==2:
                        # Actual server COMMIT has succeeded. Inject a client
                        # acknowledgement failure while the connection survives.
                        raise psycopg.OperationalError('injected lost commit acknowledgement')
                    return result
            return Transaction()
    with harness.target(acknowledged_database,'migration').connect() as raw:
        error=error_code(lambda:apply_migrations(LostAcknowledgementConnection(raw),plan,roles=ROLE_CONFIG,application_version=__version__),'MIGRATION_COMMIT_OUTCOME_RECORDED')
        require(error.applied==tuple(s.migration_id for s in plan.steps[:2]),'MIGRATION_ACK_COMMITTED_PREFIX')
        require(raw.execute('SELECT generation,recovery_required FROM whattodo_meta.schema_state').fetchone()==(2,False),'MIGRATION_ACK_FALSE_FAILURE')
        require(raw.execute('SELECT count(*) FROM whattodo_meta.migration_failure').fetchone()==(0,),'MIGRATION_ACK_FALSE_FAILURE_HISTORY')
        result=apply_migrations(raw,plan,roles=ROLE_CONFIG,application_version=__version__)
        require(result.skipped==tuple(s.migration_id for s in plan.steps[:2]) and len(result.applied)==len(plan.steps)-2,'MIGRATION_ACK_REPLAYED_DDL')
    checks.extend(['lost_commit_acknowledgement_reads_atomic_success_receipt','lost_commit_acknowledgement_never_records_false_failure_or_replays_ddl'])

    unmanaged_database=harness.create_database()
    with harness.target(unmanaged_database,'migration').connect() as conn:
        error_code(lambda:apply_migrations(conn,plan,roles=ROLE_CONFIG,application_version=__version__),'MIGRATION_UNMANAGED_DATABASE')
        require(conn.execute("SELECT to_regclass('whattodo_meta.schema_state')").fetchone()==(None,),'MIGRATION_UNMANAGED_MUTATED')
    checks.append('unmanaged_preexisting_schema_is_not_adopted')
    with harness.target(database,'migration').connect() as conn:
        # Owner fixture simulates an unknown newer deployed schema. Append-only
        # history is retained; the older application cannot acquire readiness.
        next_position=len(plan.steps)+1
        next_id=f'{int(plan.steps[-1].migration_id[:3])+1:03d}_future'
        conn.execute("INSERT INTO whattodo_meta.migration_history VALUES(%s,%s,%s,'future',CURRENT_TIMESTAMP)",
            (next_position,next_id,'a'*64))
        conn.execute("UPDATE whattodo_meta.schema_state SET generation=%s,schema_version='future' WHERE singleton=TRUE",(next_position,))
    with harness.target(database).connect() as app:
        error_code(lambda:verify_schema_compatibility(app,plan,application_version=__version__),'MIGRATION_UNKNOWN_APPLIED_VERSION')
    checks.append('unknown_newer_database_blocks_older_application_startup')
    return checks,tables,fks


def main():
    harness=PostgresHarness()
    report=dict(task='M3A-05',status='IN_PROGRESS',scope='NATIVE_MIGRATION_AND_STARTUP_GATE',verified_on='2026-10-10',native_checks=[])
    try:
        plan=load_migration_plan(root=ROOT)
        with harness:report['native_checks'],tables,fks=run_native(harness,plan)
        report.update(status='PASS',native_check_count=len(report['native_checks']),migration_pins=[dict(id=s.migration_id,sha256=s.content_hash) for s in plan.steps],domain_tables=tables,domain_foreign_keys=fks,runtime_metadata_tables=3,
            limitations=['Synthetic isolated PostgreSQL only','No production application startup, canonical command handler or repositories','No executed production backup/restore; recovery procedure is documented separately'])
    except Exception as exc:
        report.update(status='FAIL',failure_type=type(exc).__name__,failure_code=str(exc) if isinstance(exc,(HarnessError,MigrationError)) else 'MIGRATION_NATIVE_CHECK_FAILED')
    report['harness']=harness.safe_summary()
    target=harness.run_root/'migration-report.json'
    if harness.run_root.exists():target.write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(dict(status=report['status'],report=str(target),checks=len(report['native_checks']),server_stopped=report['harness']['server_stopped'])))
    return 0 if report['status']=='PASS' else 1


if __name__=='__main__':raise SystemExit(main())
