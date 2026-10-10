# Isolated PostgreSQL development and integration tests

M3A-04 provides `tools.postgres_harness.PostgresHarness` and a native acceptance
launcher. They reuse the pinned Windows x64 PostgreSQL 18.6 binaries and Psycopg
3.3.6 from [ADR-001](ADR-001.md). Existing toolchain bootstrap remains unchanged.
There is no SQLite substitute, external DSN, supplied production endpoint or
connection to an existing application database.

From the project root, run:

```powershell
.venv\Scripts\python.exe -m unittest tests.test_postgres_harness -q
.venv\Scripts\python.exe tools/verify_postgres_harness.py
```

The first command runs scope/error unit checks without starting a database. The
second starts actual PostgreSQL, tests authentication, role permissions, separate
databases and cleanup on success/failure, then stops each owned server. A native
Windows sandbox may prevent pg_ctl from creating its restricted process token;
run the same reviewed launcher through the approved local execution boundary.
Never bypass PostgreSQL's token checks or redirect tests to a production server.

Each context creates a new UUID directory under `.local-state/postgres-tests`,
refuses an existing cluster and listens only on 127.0.0.1 on a selected local
port. pg_ctl waits for startup, then SQL readiness checks validate data-directory
identity, a per-run cluster-name nonce and server version before administration.
A racing or unrelated server cannot pass this identity/authentication boundary.

| Connection role | Test-cluster permissions |
| --- | --- |
| Bootstrap controller | Initializes roles and disposable databases; isolated cluster administrator, never handed to the application |
| Migration | Owns its disposable database and schema; no superuser, database creation, role creation, replication or RLS bypass |
| Application | CONNECT and schema USAGE; SELECT/INSERT/UPDATE/DELETE on migration-created tables and sequence USAGE/SELECT |
| Test verifier | CONNECT, schema USAGE and SELECT on migration-created tables |

Application and verifier roles have no memberships, DDL, TRUNCATE or temporary
table rights and cannot connect to the maintenance databases. PUBLIC does not
receive access to owned databases or default execution rights on migration-created
functions. Defaults apply to objects created by the migration role; migrations
must preserve that ownership. This role separation supports future repositories,
not end-user authentication or authorization for canonical Task mutations.

Passwords are random per run and retained only in memory. initdb receives its
bootstrap password through a short-lived ignored file removed in `finally`.
Other roles receive client-generated SCRAM verifiers. Passwords are not placed
in command arguments, tracked config, reports or logs. PostgreSQL authenticates
with SCRAM; binary catalogs retain verifiers in ignored local state. This local
harness runs under the developer's Windows account; it does not establish an
OS isolation boundary against other processes using that same account.

Integrations use the scoped API, for example:

```python
from tools.postgres_harness import PostgresHarness

with PostgresHarness() as database:
    name = database.create_database()
    with database.target(name, "migration").connect() as connection:
        connection.execute("CREATE TABLE whattodo.example(id bigint PRIMARY KEY)")
    with database.target(name, "application").connect() as connection:
        connection.execute("INSERT INTO whattodo.example VALUES (1)")
```

Only registered generated database names can be dropped. The controller
revalidates cluster identity and each database's owner/nonce comment before
dropping it. Remaining sessions for that owned database are terminated by DROP
WITH FORCE. Context exit, including an exception, drops owned test databases
and stops only the validated owned data directory. Reports/logs/cluster files
remain ignored for diagnosis; no automatic recursive filesystem deletion,
PID-based process killing or Windows service registration occurs.

Native evidence is in [M3A-04](../reports/acceptance/M3A-04.json). It exercises
fixture objects rather than the Task schema. The ordered migration runner,
application repositories, transaction authority and production backup/restore
remain separate cards. The M2 spike and its historical reports are preserved.

Role/authentication behavior follows official
[CREATE ROLE](https://www.postgresql.org/docs/18/sql-createrole.html),
[default privileges](https://www.postgresql.org/docs/18/sql-alterdefaultprivileges.html),
[initdb](https://www.postgresql.org/docs/18/app-initdb.html) and
[Psycopg password verifier](https://www.psycopg.org/psycopg3/docs/api/pq.html#psycopg.pq.PGconn.encrypt_password)
documentation; acceptance counts describe actual local observations.
