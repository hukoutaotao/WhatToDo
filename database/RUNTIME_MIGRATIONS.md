# Runtime migration execution and startup compatibility

M3A-05 adds a trusted migration plan, executor and read-only compatibility gate.
It preserves all five pinned [M2 SQL drafts](migrations/001_foundation.sql).
The [new metadata migration](runtime-migrations/000_runtime_metadata.sql) and
[ordered manifest](migration-plan.json) are separate runtime artifacts.

The manifest pins each migration ID, source path, UTF-8 SHA-256 and resulting
schema version. Source text normalizes CRLF to LF before hashing, including
comments and the original transaction envelope. The loader confines resources
to its chosen root, rejects hash/order/identity drift and retains detached frozen
values. These are integrity/version checks on trusted reviewed artifacts, not
permission to execute SQL from a Course profile, external content or user input.

The loader derives a transaction body while preserving quoted strings and
dollar-quoted functions. It removes only the outer BEGIN/COMMIT envelope and
comments, rejects additional top-level transaction commands and requires statement
terminators. Quoted backslash escapes are outside this lexical subset; use doubled
quotes. This guard is not a general SQL parser or an authorization sandbox.

`apply_migrations` requires an idle autocommit connection belonging to the
non-superuser database-owning migration role. A database-wide advisory lock
serializes runners; a busy runner fails explicitly rather than executing twice.
The runner verifies applied records against the exact known prefix before any
DDL. It refuses unknown future IDs, altered applied hashes, state/history mismatch
or an unmanaged existing schema. An old spike database is not silently adopted.

Each step's DDL, grants, runtime receipt, legacy receipt where applicable and
schema-head update commit in one PostgreSQL transaction. Successful earlier steps
stay committed when a later step fails. Reruns skip exact matching receipts and
never rewrite their timestamps. New definitions/defaults are not activated by
migration success, and schema compatibility is not Task mutation authority.

`whattodo_meta` contains three tables:

| Table | Meaning |
| --- | --- |
| migration_history | Append-only ordered ID/hash/version receipts |
| schema_state | Current generation/version and recovery-required flag |
| migration_failure | Append-only failed candidate hash, SQLSTATE and timestamp |

Application and verifier roles can read metadata but cannot insert, update,
delete or truncate it. The legacy `whattodo.schema_migration` receipt table is
also read-only for these roles. Schema-owning credentials remain separate from
application credentials. The 51 domain tables and 130 foreign keys are unchanged;
the three metadata tables are counted separately.

`verify_schema_compatibility` uses a read-only repeatable-read transaction and
a shared advisory lock. It requires the supported application version, complete
exact migration chain, matching legacy receipts and no pending recovery. Startup
during migration is explicitly busy. Future repository/service startup must call
this gate before admitting writes; it does not authenticate a user or authorize
a command and is not a substitute for transaction-time authority/CAS checks.

For isolated development, reproduce the checks with:

```powershell
.venv\Scripts\python.exe -m unittest tests.test_migrations -q
.venv\Scripts\python.exe tools/verify_migrations.py
```

The native launcher uses [M3A-04's owned harness](../toolchain/POSTGRES_TESTS.md),
creates empty databases with `initialize_schema=False`, exercises real PostgreSQL
and stops its cluster. Windows sandbox pg_ctl token restrictions may require the
approved local execution boundary. The [native report](../reports/acceptance/M3A-05.json)
records actual results. No production endpoint or SQLite substitute is accepted
by the launcher.

Installed packages include the manifest and all six SQL resources.
`load_migration_plan()` resolves them under the environment's `share/whattodo`
directory; checkout tools pass their explicit repository root. The PostgreSQL
driver remains optional until an executor is actually called.

## Forward changes and recovery

An applied migration is immutable. Fix or extend it with a new ordered migration
ID and explicit schema version, update the reviewed manifest and application
compatibility, then rehearse it against an isolated restored database. Do not edit
an applied receipt/hash to force a green startup. A changed *unapplied* failed
candidate can be reviewed and retried; its original failed hash remains in history.

On an SQL error, the failed step's DDL/receipt/head update roll back. Once metadata
exists, a separate transaction records its failure and marks recovery required.
Application readiness remains blocked until the reviewed pending step succeeds.
The runner returns only an error code, failed ID, SQLSTATE and committed IDs;
it does not expose SQL text, source paths or driver diagnostics. A bootstrap
metadata failure leaves an empty database and is retryable from the start.

If the connection is lost, PostgreSQL rolls back its active transaction and
releases the session lock. The runner explicitly reports that its failure record
could not be stored. Reconnect with migration credentials, inspect the durable
prefix and rerun the reviewed plan; incomplete schema remains unready. Loss after
commit is reconciled from the atomic receipt rather than blindly replaying DDL.
When the connection survives an acknowledgement error, the executor reports
`MIGRATION_COMMIT_OUTCOME_RECORDED` with the committed IDs; it neither adds a
false failure record nor marks the committed step as requiring recovery. A new
call skips that receipt and continues the pending suffix.

For a non-reversible committed change, recovery uses a pre-migration backup:

1. Stop admitting application writes and retain migration/incident evidence.
2. Identify the exact backup and matching application/manifest revision; keep the
   affected database untouched while determining the intended recovery point.
3. Restore into a separate isolated database, never overwrite a live database as
   a first diagnostic step. Verify receipt/hash/head consistency and targeted
   semantic/data checks with the matching application version.
4. If needed, rehearse a reviewed forward fix there. Establish the restored data's
   recovery point and reconcile later confirmed changes from retained evidence;
   do not infer lost completions or estimates.
5. Validate the recovery and perform a separately authorized deployment/cutover,
   preserving the affected database and backup under the applicable retention rule.

This card documents restore-based recovery; it does not certify an executed
production backup, restore or cutover. Those remain the operations/restore tasks.
Automatic down migrations and silent data loss are not provided.

Transaction and lock behavior follows official
[Psycopg transaction documentation](https://www.psycopg.org/psycopg3/docs/basic/transactions.html)
and [PostgreSQL advisory-lock documentation](https://www.postgresql.org/docs/18/explicit-locking.html#ADVISORY-LOCKS).
