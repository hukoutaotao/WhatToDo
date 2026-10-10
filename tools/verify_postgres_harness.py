"""Execute isolated native PostgreSQL authentication, role and cleanup probes."""
import json
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:sys.path.insert(0,str(ROOT))
from tools.postgres_harness import ConnectionTarget,HarnessError,PostgresHarness,ROLES,require


def verify(harness):
    import psycopg
    from psycopg import sql
    checks=[]
    database=harness.create_database()
    with harness.target(database,'migration').connect() as migration:
        # Fixture DDL, not a migration runner or application repository.
        migration.execute('CREATE TABLE whattodo.role_probe (id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY, value text NOT NULL)')
        migration.execute('CREATE FUNCTION whattodo.role_probe_function() RETURNS integer LANGUAGE SQL AS $$ SELECT 1 $$')
    checks.append('migration_role_creates_owned_schema_objects')
    with harness._admin() as admin:
        require(admin.execute('SHOW listen_addresses').fetchone()[0]=='127.0.0.1','PG_LISTEN_SCOPE')
        methods={row[0] for row in admin.execute('SELECT auth_method FROM pg_hba_file_rules WHERE error IS NULL').fetchall()}
        require(methods=={'scram-sha-256'},'PG_AUTHENTICATION')
        secrets=[row[0] for row in admin.execute('SELECT rolpassword FROM pg_authid WHERE rolname = ANY(%s)',(list(ROLES.values()),)).fetchall()]
        require(len(secrets)==4 and all(value.startswith('SCRAM-SHA-256$') for value in secrets),'PG_PASSWORD_VERIFIERS')
    checks.extend(['loopback_only','scram_only_hba','scram_role_verifiers'])
    with harness.target(database).connect() as app:
        flags=app.execute('SELECT rolsuper,rolcreatedb,rolcreaterole,rolreplication,rolbypassrls FROM pg_roles WHERE rolname=current_user').fetchone()
        require(flags==(False,False,False,False,False),'PG_APPLICATION_PRIVILEGES')
        require(app.execute('SELECT count(*) FROM pg_auth_members WHERE member=(SELECT oid FROM pg_roles WHERE rolname=current_user)').fetchone()==(0,),'PG_APPLICATION_MEMBERSHIPS')
        require(app.pgconn.used_password,'PG_AUTHENTICATION')
        app.execute("INSERT INTO whattodo.role_probe(value) VALUES ('synthetic')")
        app.execute("UPDATE whattodo.role_probe SET value='changed' WHERE id=1")
        require(app.execute('SELECT value FROM whattodo.role_probe WHERE id=1').fetchone()==('changed',),'PG_APPLICATION_DML')
        checks.extend(['application_restricted_role_flags_and_no_memberships','application_password_authentication','application_table_and_sequence_dml'])
        rejected=[('CREATE TABLE whattodo.forbidden(id integer)','application_ddl_denied'),
            ('CREATE DATABASE wt_forbidden','application_database_creation_denied'),
            ('CREATE ROLE wt_forbidden','application_role_creation_denied'),
            ('SET ROLE wt_migration','application_role_escalation_denied'),
            ('TRUNCATE whattodo.role_probe','application_truncate_denied'),
            ('CREATE TEMP TABLE forbidden(id integer)','application_temp_creation_denied'),
            ('SELECT whattodo.role_probe_function()','default_function_execution_denied')]
        for statement,name in rejected:
            try:app.execute(statement)
            except psycopg.errors.InsufficientPrivilege:checks.append(name)
            else:raise HarnessError('PG_PRIVILEGE_PROBE_FAILED')
    with harness.target(database,'test').connect() as test:
        require(test.execute('SELECT value FROM whattodo.role_probe').fetchone()==('changed',),'PG_TEST_READ')
        checks.append('test_role_can_read_application_data')
        for statement,name in [('DELETE FROM whattodo.role_probe','test_role_write_denied'),('ALTER TABLE whattodo.role_probe ADD COLUMN forbidden integer','test_role_ddl_denied')]:
            try:test.execute(statement)
            except psycopg.errors.InsufficientPrivilege:checks.append(name)
            else:raise HarnessError('PG_PRIVILEGE_PROBE_FAILED')
    for database_name,name,password in [('postgres','application_maintenance_database_denied',harness._passwords['application']),(database,'wrong_password_denied','synthetic-invalid-password')]:
        try:
            with ConnectionTarget(harness.port,database_name,ROLES['application'],password).connect():pass
        except psycopg.OperationalError as exc:
            expected='42501' if database_name=='postgres' else '28P01'
            # Some libpq connect failures carry no parsed SQLSTATE; match only
            # the expected local server error, without emitting its text.
            if exc.sqlstate is None:
                text=str(exc)
                require(('permission denied for database' if database_name=='postgres' else 'password authentication failed') in text,'PG_AUTH_PROBE_FAILED')
            else:require(exc.sqlstate==expected,'PG_AUTH_PROBE_FAILED')
            checks.append(name)
        else:raise HarnessError('PG_AUTH_PROBE_FAILED')
    try:harness.drop_database('production')
    except HarnessError as exc:require(str(exc)=='PG_DATABASE_SCOPE','PG_DROP_SCOPE')
    else:raise HarnessError('PG_DROP_SCOPE')
    checks.append('unregistered_database_drop_rejected')
    second=harness.create_database()
    with harness.target(second).connect() as conn:
        require(conn.execute('SELECT count(*) FROM pg_tables WHERE schemaname=\'whattodo\'').fetchone()==(0,),'PG_DATABASE_ISOLATION')
    checks.append('second_disposable_database_is_independent')
    harness.drop_database(second)
    with harness._admin() as admin:
        require(admin.execute('SELECT count(*) FROM pg_database WHERE datname=%s',(second,)).fetchone()==(0,),'PG_DATABASE_DROP')
    checks.append('owned_database_drop_completed')
    return checks


def main():
    harness=PostgresHarness()
    report=dict(task='M3A-04',status='IN_PROGRESS',verified_on='2026-10-10',native_checks=[],scope='ISOLATED_NATIVE_DEVELOPMENT_HARNESS')
    try:
        with harness:report['native_checks']=verify(harness)
        summary=harness.safe_summary()
        require(summary['server_stopped'] and summary['databases_created']==summary['databases_dropped'] and not summary['initdb_password_file_retained'],'PG_CLEANUP_ACCEPTANCE')
        # No cleartext credential may remain in the owned logs, metadata or
        # redacted report. Binary PG catalogs intentionally retain verifiers.
        for file in harness.run_root.glob('*.log'):
            content=file.read_text(encoding='utf-8',errors='replace')
            require(all(secret not in content for secret in harness._passwords.values()),'PG_LOG_SECRET_LEAK')
        failure_harness=PostgresHarness()
        class InjectedFailure(Exception):pass
        app=None
        try:
            try:
                with failure_harness:
                    failed_db=failure_harness.create_database()
                    app=failure_harness.target(failed_db).connect()
                    app.execute('SELECT 1')
                    raise InjectedFailure()
            except InjectedFailure:pass
            failed_summary=failure_harness.safe_summary()
            require(failed_summary['server_stopped'] and failed_summary['databases_created']==failed_summary['databases_dropped']==1,'PG_FAILURE_CLEANUP')
            import psycopg
            try:app.execute('SELECT 1')
            except psycopg.OperationalError:pass
            else:raise HarnessError('PG_FAILURE_SESSION_NOT_TERMINATED')
            report['native_checks'].extend(['exception_path_owned_database_dropped','exception_path_server_stopped','owned_database_drop_terminates_remaining_test_session'])
            report['failure_teardown']=failed_summary
        finally:
            if app is not None:app.close()
        report.update(status='PASS',postgresql_version='18.6',native_check_count=len(report['native_checks']),harness=summary,
            limitations=['Local Windows x64 synthetic fixture only','No production credentials, deployment or endpoint attachment','Fixture DML is not a trusted canonical write handler','Migration runner and repositories remain later tasks','Ignored data/logs are retained; no recursive filesystem deletion'])
    except Exception as exc:
        report.update(status='FAIL',failure_type=type(exc).__name__,failure_code=str(exc) if isinstance(exc,HarnessError) else 'PG_NATIVE_CHECK_FAILED',harness=harness.safe_summary())
    target=harness.run_root/'report.json'
    if harness.run_root.exists():target.write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(dict(status=report['status'],report=str(target),native_checks=len(report['native_checks']),server_stopped=harness.safe_summary()['server_stopped'])))
    return 0 if report['status']=='PASS' else 1


if __name__=='__main__':raise SystemExit(main())
