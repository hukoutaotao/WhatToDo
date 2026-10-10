"""Owned Windows PostgreSQL test clusters; never attach to a supplied endpoint.

Development-only tooling, deliberately excluded from the application wheel.
No SQLite fallback, provider credential lookup or recursive filesystem cleanup.
"""
from __future__ import annotations

from dataclasses import dataclass,field
import json
import os
from pathlib import Path
import platform
import re
import secrets
import socket
import subprocess
import time
from uuid import uuid4

ROOT=Path(__file__).resolve().parents[1]
ROLES={'bootstrap':'wt_bootstrap','migration':'wt_migration','application':'wt_application','test':'wt_test_readonly'}
RUN_ID=re.compile(r'[a-f0-9]{32}\Z')


class HarnessError(RuntimeError):
    """Only stable redacted codes cross the tooling boundary."""


def require(condition,code):
    if not condition:raise HarnessError(code)


def owned_run(path,*,workspace=ROOT):
    root=(Path(workspace)/'.local-state/postgres-tests').resolve()
    require(root.is_relative_to(Path(workspace).resolve()),'PG_RUN_SCOPE')
    chosen=Path(path).resolve()
    require(chosen.parent==root and RUN_ID.fullmatch(chosen.name) is not None,'PG_RUN_SCOPE')
    return chosen


def verify_identity(conn,cluster,cluster_name):
    actual=conn.execute('SHOW data_directory').fetchone()[0]
    require(Path(actual).resolve()==Path(cluster).resolve(),'PG_SERVER_IDENTITY')
    require(conn.execute('SHOW cluster_name').fetchone()[0]==cluster_name,'PG_SERVER_IDENTITY')
    require(conn.execute('SHOW server_version').fetchone()[0]=='18.6','PG_SERVER_VERSION')


@dataclass(frozen=True)
class ConnectionTarget:
    port:int
    database:str
    role:str
    _password:str=field(repr=False)

    def connect(self):
        import psycopg
        # Explicit connection fields and options prevent libpq environment
        # defaults from redirecting the target or adding startup SQL options.
        return psycopg.connect(host='127.0.0.1',hostaddr='127.0.0.1',port=self.port,
            dbname=self.database,user=self.role,password=self._password,
            connect_timeout=5,autocommit=True,sslmode='disable',gssencmode='disable',
            application_name='WhatToDoOwnedTest',options='-c statement_timeout=15000 -c lock_timeout=5000')


class PostgresHarness:
    """Owns exactly one new cluster and its explicitly registered test DBs."""

    def __init__(self):
        self.run_id=uuid4().hex
        self.run_root=owned_run(ROOT/'.local-state/postgres-tests'/self.run_id)
        self.cluster=self.run_root/'cluster'
        self.cluster_name='whattodo_test_'+self.run_id
        self.binary=ROOT/'.dev-tools/postgresql-18.6/pgsql/bin'
        self.port=None
        self._passwords={role:secrets.token_urlsafe(32) for role in ROLES}
        self._databases=set()
        self._created=[]
        self._dropped=[]
        self._start_attempted=False
        self._active=False
        self._entered=False

    def _execute(self,argv,*,log=None):
        env={k:v for k,v in os.environ.items() if not k.upper().startswith('PG')}
        opts=dict(cwd=ROOT,env=env,timeout=45,text=True,encoding='utf-8',errors='replace',
                  creationflags=subprocess.CREATE_NO_WINDOW if os.name=='nt' else 0)
        try:
            if log is None:
                result=subprocess.run([str(a) for a in argv],capture_output=True,**opts)
                output=result.stdout.strip()
            else:
                with Path(log).open('w',encoding='utf-8') as stream:
                    result=subprocess.run([str(a) for a in argv],stdout=stream,stderr=subprocess.STDOUT,**opts)
                output=''
        except (OSError,subprocess.SubprocessError):raise HarnessError('PG_PROCESS_FAILED') from None
        require(result.returncode==0,'PG_PROCESS_FAILED')
        return output

    def _owned(self):
        require(owned_run(self.run_root)==self.run_root,'PG_RUN_SCOPE')
        require(self.cluster.resolve()==self.run_root/'cluster','PG_CLUSTER_SCOPE')
        try:marker=json.loads((self.run_root/'owner.json').read_text(encoding='utf-8'))
        except (OSError,ValueError):raise HarnessError('PG_OWNER_MARKER') from None
        require(marker==dict(run_id=self.run_id,scope='SYNTHETIC_TEST_ONLY',cluster_name=self.cluster_name),'PG_OWNER_MARKER')

    def _admin(self):
        self._owned()
        require(self.port is not None and self._start_attempted,'PG_NOT_STARTED')
        conn=ConnectionTarget(self.port,'postgres',ROLES['bootstrap'],self._passwords['bootstrap']).connect()
        try:verify_identity(conn,self.cluster,self.cluster_name)
        except Exception:
            conn.close();raise
        return conn

    def __enter__(self):
        require(not self._entered,'PG_SINGLE_USE')
        self._entered=True
        require(os.name=='nt' and platform.machine().lower() in ('amd64','x86_64'),'PG_PLATFORM')
        require(self.binary.resolve().is_relative_to((ROOT/'.dev-tools').resolve()),'PG_BINARY_SCOPE')
        require(self._execute([self.binary/'postgres.exe','--version'])=='postgres (PostgreSQL) 18.6','PG_BINARY_VERSION')
        self.run_root.mkdir(parents=True,exist_ok=False)
        (self.run_root/'owner.json').write_text(json.dumps(dict(run_id=self.run_id,scope='SYNTHETIC_TEST_ONLY',cluster_name=self.cluster_name)),encoding='utf-8')
        try:
            require(not self.cluster.exists(),'PG_EXISTING_CLUSTER')
            # This short-lived plaintext file is ignored and removed even if
            # initdb fails. Role creation later transmits SCRAM verifiers only.
            password_file=self.run_root/'initdb.password'
            try:
                with password_file.open('x',encoding='utf-8') as stream:stream.write(self._passwords['bootstrap']+'\n')
                os.chmod(password_file,0o600)
                self._execute([self.binary/'initdb.exe','-D',self.cluster,'-U',ROLES['bootstrap'],
                    '--auth=scram-sha-256','--pwfile',password_file,'--locale=C','--encoding=UTF8'],log=self.run_root/'initdb.log')
            finally:
                if password_file.exists():password_file.unlink()
            with (self.cluster/'postgresql.conf').open('a',encoding='utf-8') as stream:
                stream.write("\nlisten_addresses = '127.0.0.1'\npassword_encryption = 'scram-sha-256'\nlog_statement = 'none'\nlog_min_error_statement = 'panic'\nlog_error_verbosity = 'terse'\n")
                stream.write("cluster_name = '"+self.cluster_name+"'\n")
            with socket.socket() as sock:
                sock.bind(('127.0.0.1',0));self.port=sock.getsockname()[1]
            self._start_attempted=True
            self._execute([self.binary/'pg_ctl.exe','-D',self.cluster,'-l',self.run_root/'postgresql.log',
                '-w','-t','30','-o',f'-p {self.port} -c max_connections=20','start'],log=self.run_root/'start.log')
            deadline=time.monotonic()+10
            import psycopg
            while True:
                try:
                    with self._admin() as conn:
                        require(conn.execute('SELECT 1').fetchone()==(1,),'PG_NOT_READY')
                    break
                except psycopg.OperationalError:
                    if time.monotonic()>=deadline:raise HarnessError('PG_NOT_READY') from None
                    time.sleep(0.1)
            self._active=True
            self._roles()
            return self
        except BaseException:
            self.close();raise

    def _roles(self):
        from psycopg import sql
        with self._admin() as conn:
            for alias in ('migration','application','test'):
                role=ROLES[alias]
                encrypted=conn.pgconn.encrypt_password(self._passwords[alias].encode(),role.encode(),b'scram-sha-256').decode()
                conn.execute(sql.SQL('CREATE ROLE {} LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOINHERIT NOREPLICATION NOBYPASSRLS PASSWORD {}').format(sql.Identifier(role),sql.Literal(encrypted)))
            for name in ('postgres','template1'):
                conn.execute(sql.SQL('REVOKE ALL ON DATABASE {} FROM PUBLIC').format(sql.Identifier(name)))

    def create_database(self,*,initialize_schema=True):
        from psycopg import sql
        require(self._active,'PG_NOT_STARTED')
        name='wt_test_'+self.run_id+'_'+str(len(self._created)+1)
        with self._admin() as conn:
            conn.execute(sql.SQL('CREATE DATABASE {} OWNER {} TEMPLATE template0').format(sql.Identifier(name),sql.Identifier(ROLES['migration'])))
            # Register immediately: a later grant/setup failure still cleans up.
            self._databases.add(name);self._created.append(name)
            conn.execute(sql.SQL('COMMENT ON DATABASE {} IS {}').format(sql.Identifier(name),sql.Literal(self.cluster_name)))
            conn.execute(sql.SQL('REVOKE ALL ON DATABASE {} FROM PUBLIC').format(sql.Identifier(name)))
            conn.execute(sql.SQL('GRANT CONNECT ON DATABASE {} TO {}, {}').format(sql.Identifier(name),sql.Identifier(ROLES['application']),sql.Identifier(ROLES['test'])))
        if not initialize_schema:return name
        with self.target(name,'migration').connect() as conn:
            conn.execute('REVOKE ALL ON SCHEMA public FROM PUBLIC')
            conn.execute('CREATE SCHEMA whattodo')
            conn.execute(sql.SQL('GRANT USAGE ON SCHEMA whattodo TO {}, {}').format(sql.Identifier(ROLES['application']),sql.Identifier(ROLES['test'])))
            conn.execute(sql.SQL('ALTER DEFAULT PRIVILEGES IN SCHEMA whattodo GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO {}').format(sql.Identifier(ROLES['application'])))
            conn.execute(sql.SQL('ALTER DEFAULT PRIVILEGES IN SCHEMA whattodo GRANT USAGE, SELECT ON SEQUENCES TO {}').format(sql.Identifier(ROLES['application'])))
            conn.execute(sql.SQL('ALTER DEFAULT PRIVILEGES IN SCHEMA whattodo GRANT SELECT ON TABLES TO {}').format(sql.Identifier(ROLES['test'])))
            conn.execute('ALTER DEFAULT PRIVILEGES REVOKE EXECUTE ON FUNCTIONS FROM PUBLIC')
        return name

    def target(self,database,role='application'):
        require(self._active and database in self._databases,'PG_DATABASE_SCOPE')
        require(role in ('migration','application','test'),'PG_ROLE_SCOPE')
        # Identity is revalidated before handing out a connection target.
        with self._admin():pass
        return ConnectionTarget(self.port,database,ROLES[role],self._passwords[role])

    def drop_database(self,name):
        from psycopg import sql
        require(name in self._databases,'PG_DATABASE_SCOPE')
        with self._admin() as conn:
            row=conn.execute("SELECT pg_get_userbyid(datdba), shobj_description(oid,'pg_database') FROM pg_database WHERE datname=%s",(name,)).fetchone()
            if row is not None:
                require(row==(ROLES['migration'],self.cluster_name),'PG_DATABASE_OWNERSHIP')
                conn.execute(sql.SQL('DROP DATABASE {} WITH (FORCE)').format(sql.Identifier(name)))
            self._databases.remove(name);self._dropped.append(name)

    def close(self):
        if not self.run_root.exists():return
        self._owned()
        cleanup_error=None
        try:
            if self._active:
                for name in sorted(self._databases):self.drop_database(name)
        except Exception as exc:cleanup_error=exc
        finally:
            if self._start_attempted and (self.cluster/'postmaster.pid').exists():
                # No PID killing and no endpoint-supplied pg_ctl target. Validate
                # the PID file's data-dir identity before stopping this cluster.
                lines=(self.cluster/'postmaster.pid').read_text(encoding='utf-8').splitlines()
                require(len(lines)>=2 and Path(lines[1]).resolve()==self.cluster.resolve(),'PG_STOP_IDENTITY')
                self._execute([self.binary/'pg_ctl.exe','-D',self.cluster,'-w','-t','30','-m','fast','stop'],log=self.run_root/'stop.log')
            self._active=False
            require(not (self.cluster/'postmaster.pid').exists(),'PG_STOP_FAILED')
        if cleanup_error is not None:raise HarnessError('PG_DATABASE_CLEANUP_FAILED') from None

    def __exit__(self,*_):self.close()

    def safe_summary(self):
        return dict(run_id=self.run_id,scope='SYNTHETIC_TEST_ONLY',listen_address='127.0.0.1',
            authentication='SCRAM_SHA_256',roles=dict(ROLES),databases_created=len(self._created),
            databases_dropped=len(self._dropped),server_stopped=not (self.cluster/'postmaster.pid').exists(),
            initdb_password_file_retained=(self.run_root/'initdb.password').exists(),
            production_endpoint='NOT_ACCEPTED',recursive_filesystem_cleanup=False)
