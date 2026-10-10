"""Atomic ordered PostgreSQL migrations and read-only startup compatibility.

Caller supplies a trusted migration-owned connection, not arbitrary user SQL.
Canonical Task authority and repositories are separate application layers.
"""
from dataclasses import dataclass
from contextlib import contextmanager

from src.adapters.migration_files import migration_body
from src.application.migrations import (MigrationError,MigrationRecord,MigrationResult,
    SchemaCompatibility,SchemaState,check_history,need)

LOCK_KEY=519013571


@dataclass(frozen=True)
class DatabaseRoles:
    migration:str
    application:str
    verifier:str|None=None

    def __post_init__(self):
        names=(self.migration,self.application)+((self.verifier,) if self.verifier is not None else ())
        need(all(isinstance(name,str) and name.strip() and '\x00' not in name and len(name.encode('utf-8'))<=63 for name in names),'MIGRATION_ROLE_CONFIG')
        need(len(set(names))==len(names),'MIGRATION_ROLE_CONFIG')


def _idle(conn):
    from psycopg.pq import TransactionStatus
    need(conn.autocommit and conn.info.transaction_status==TransactionStatus.IDLE,'MIGRATION_IDLE_CONNECTION_REQUIRED')


def _snapshot(conn):
    if not conn.execute("SELECT to_regclass('whattodo_meta.schema_state') IS NOT NULL").fetchone()[0]:return None
    rows=conn.execute('SELECT generation,schema_version,recovery_required,failed_migration_id FROM whattodo_meta.schema_state WHERE singleton=TRUE').fetchall()
    need(len(rows)==1,'MIGRATION_STATE_DRIFT')
    records=tuple(MigrationRecord(*row) for row in conn.execute('SELECT position,migration_id,content_hash,schema_version FROM whattodo_meta.migration_history ORDER BY position').fetchall())
    return records,SchemaState(*rows[0])


def _legacy_receipts(conn,plan,records):
    expected=tuple((step.migration_id,step.content_hash,step.legacy_design_version) for step in plan.steps[:len(records)] if step.legacy_design_version is not None)
    if not expected:return
    actual=tuple(conn.execute('SELECT migration_id,content_hash,design_version FROM whattodo.schema_migration ORDER BY migration_id').fetchall())
    need(actual==expected,'MIGRATION_LEGACY_RECEIPT_DRIFT')


def _owner(conn,roles):
    row=conn.execute('SELECT current_user, pg_get_userbyid(datdba) FROM pg_database WHERE datname=current_database()').fetchone()
    need(row==(roles.migration,roles.migration),'MIGRATION_OWNER_REQUIRED')
    flags=conn.execute('SELECT rolsuper,rolcreatedb,rolcreaterole,rolreplication,rolbypassrls FROM pg_roles WHERE rolname=current_user').fetchone()
    need(flags==(False,False,False,False,False),'MIGRATION_OWNER_PRIVILEGES')


def _fresh_database(conn):
    namespaces=conn.execute("SELECT nspname FROM pg_namespace WHERE nspname NOT LIKE 'pg_%' AND nspname NOT IN ('information_schema','public')").fetchall()
    need(not namespaces,'MIGRATION_UNMANAGED_DATABASE')
    objects=conn.execute("SELECT (EXISTS(SELECT 1 FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace WHERE n.nspname='public') OR EXISTS(SELECT 1 FROM pg_proc p JOIN pg_namespace n ON n.oid=p.pronamespace WHERE n.nspname='public') OR EXISTS(SELECT 1 FROM pg_type t JOIN pg_namespace n ON n.oid=t.typnamespace WHERE n.nspname='public'))").fetchone()[0]
    need(not objects,'MIGRATION_UNMANAGED_DATABASE')


def _grants(conn,roles):
    from psycopg import sql
    readers=[roles.application]+([roles.verifier] if roles.verifier is not None else [])
    for reader in readers:
        role=sql.Identifier(reader)
        conn.execute(sql.SQL('GRANT USAGE ON SCHEMA whattodo_meta TO {}').format(role))
        conn.execute(sql.SQL('REVOKE ALL ON ALL TABLES IN SCHEMA whattodo_meta FROM {}').format(role))
        conn.execute(sql.SQL('REVOKE ALL ON ALL SEQUENCES IN SCHEMA whattodo_meta FROM {}').format(role))
        conn.execute(sql.SQL('GRANT SELECT ON ALL TABLES IN SCHEMA whattodo_meta TO {}').format(role))
    if not conn.execute("SELECT EXISTS(SELECT 1 FROM pg_namespace WHERE nspname='whattodo')").fetchone()[0]:return
    tables=tuple(row[0] for row in conn.execute("SELECT tablename FROM pg_tables WHERE schemaname='whattodo' ORDER BY tablename").fetchall())
    for reader in readers:
        role=sql.Identifier(reader)
        conn.execute(sql.SQL('GRANT USAGE ON SCHEMA whattodo TO {}').format(role))
        conn.execute(sql.SQL('REVOKE ALL ON ALL TABLES IN SCHEMA whattodo FROM {}').format(role))
        for table in tables:
            protected={'schema_migration','configuration_revision','definition_cache','definition_reference'}
            privileges=sql.SQL('SELECT,INSERT,UPDATE,DELETE') if reader==roles.application and table not in protected else sql.SQL('SELECT')
            conn.execute(sql.SQL('GRANT {} ON TABLE whattodo.{} TO {}').format(privileges,sql.Identifier(table),role))


def _record_failure(conn,step,error):
    snapshot=_snapshot(conn)
    if snapshot is None:return False
    records,_=snapshot
    committed=[row for row in records if row.migration_id==step.migration_id]
    if committed:
        need(len(committed)==1 and committed[0].content_hash==step.content_hash and committed[0].schema_version==step.schema_version,'MIGRATION_APPLIED_DRIFT')
        return True
    code=error.sqlstate or 'XX000'
    with conn.transaction():
        conn.execute('INSERT INTO whattodo_meta.migration_failure(migration_id,content_hash,error_code,failed_at) VALUES(%s,%s,%s,CURRENT_TIMESTAMP)',(step.migration_id,step.content_hash,code))
        conn.execute('UPDATE whattodo_meta.schema_state SET recovery_required=TRUE,failed_migration_id=%s WHERE singleton=TRUE',(step.migration_id,))
    return False


def apply_migrations(conn,plan,*,roles,application_version):
    import psycopg
    need(application_version in plan.application_versions,'MIGRATION_APPLICATION_INCOMPATIBLE')
    # Re-derive executable bodies before acquiring a database lock. A forged
    # in-memory body cannot bypass the pinned source or transaction boundary.
    for step in plan.steps:need(step.body_sql==migration_body(step.source_sql),'MIGRATION_BODY_DRIFT')
    _idle(conn);_owner(conn,roles)
    locked=conn.execute('SELECT pg_try_advisory_lock(%s)',(LOCK_KEY,)).fetchone()[0]
    need(locked,'MIGRATION_BUSY')
    applied=[];skipped=[]
    try:
        snapshot=_snapshot(conn)
        if snapshot is None:
            _fresh_database(conn);records=();state=SchemaState(0,'UNINITIALIZED',False,None)
        else:records,state=snapshot
        count=check_history(plan,records,state,application_version=application_version)
        _legacy_receipts(conn,plan,records)
        skipped=[row.migration_id for row in records]
        for index,step in enumerate(plan.steps[count:],start=count+1):
            try:
                with conn.transaction():
                    conn.execute('SET LOCAL search_path=pg_catalog')
                    conn.execute(step.body_sql,prepare=False)
                    _grants(conn,roles)
                    if step.legacy_design_version is not None:
                        conn.execute('INSERT INTO whattodo.schema_migration VALUES(%s,%s,%s,CURRENT_TIMESTAMP)',(step.migration_id,step.content_hash,step.legacy_design_version))
                    conn.execute('INSERT INTO whattodo_meta.migration_history VALUES(%s,%s,%s,%s,CURRENT_TIMESTAMP)',(index,step.migration_id,step.content_hash,step.schema_version))
                    conn.execute('UPDATE whattodo_meta.schema_state SET generation=%s,schema_version=%s,recovery_required=FALSE,failed_migration_id=NULL WHERE singleton=TRUE',(index,step.schema_version))
            except psycopg.Error as exc:
                # SQL text/driver diagnostics are never returned. Successful
                # prefixes stay committed; this failed step and receipt vanish.
                try:already_committed=_record_failure(conn,step,exc)
                except psycopg.Error:
                    raise MigrationError('MIGRATION_FAILURE_RECORD_UNAVAILABLE',failed_migration=step.migration_id,sqlstate=exc.sqlstate,applied=applied) from None
                if already_committed:
                    raise MigrationError('MIGRATION_COMMIT_OUTCOME_RECORDED',failed_migration=step.migration_id,sqlstate=exc.sqlstate,applied=(*applied,step.migration_id)) from None
                raise MigrationError('MIGRATION_STEP_FAILED',failed_migration=step.migration_id,sqlstate=exc.sqlstate,applied=applied) from None
            applied.append(step.migration_id)
        records,state=_snapshot(conn)
        check_history(plan,records,state,application_version=application_version,complete=True)
        _legacy_receipts(conn,plan,records)
        return MigrationResult(tuple(applied),tuple(skipped),state.schema_version)
    except psycopg.Error:raise MigrationError('MIGRATION_METADATA_UNREADABLE') from None
    finally:
        if not conn.closed:conn.execute('SELECT pg_advisory_unlock(%s)',(LOCK_KEY,))


@contextmanager
def schema_checked_transaction(conn,plan,*,application_version,read_only=True):
    """Hold schema readiness/shared migration lock throughout scoped DB work."""
    import psycopg
    need(application_version in plan.application_versions,'MIGRATION_APPLICATION_INCOMPATIBLE')
    _idle(conn)
    with conn.transaction():
        try:
            conn.execute('SET TRANSACTION ISOLATION LEVEL REPEATABLE READ, '+('READ ONLY' if read_only else 'READ WRITE'))
            need(conn.execute('SELECT pg_try_advisory_xact_lock_shared(%s)',(LOCK_KEY,)).fetchone()[0],'MIGRATION_BUSY')
            snapshot=_snapshot(conn)
            need(snapshot is not None,'MIGRATION_SCHEMA_UNINITIALIZED')
            records,state=snapshot
            check_history(plan,records,state,application_version=application_version,complete=True)
            _legacy_receipts(conn,plan,records)
        except psycopg.Error:raise MigrationError('MIGRATION_METADATA_UNREADABLE') from None
        yield SchemaCompatibility(state.schema_version,state.generation,application_version)


def verify_schema_compatibility(conn,plan,*,application_version):
    """Read-only startup gate; grants no canonical Task mutation authority."""
    with schema_checked_transaction(conn,plan,application_version=application_version) as compatibility:return compatibility
