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
application credentials. The original M3A-05 checkpoint contains 51 domain
tables and 130 foreign keys; its six-step manifest is preserved in
[the acceptance snapshot](../reports/acceptance/M3A-05-migration-plan.json).
M3A-06 adds [definition caches](DEFINITION_REPOSITORIES.md) through a seventh
forward migration, bringing the domain counts to 53 tables and 133 foreign
keys at that checkpoint. M3A-07 adds [Task/stage storage](TASK_REPOSITORIES.md)
through an eighth forward migration, bringing that checkpoint to 57
tables and 144 foreign keys. M3A-08 adds [evidence/pending storage](EVIDENCE_REPOSITORIES.md)
through the ninth migration, bringing that checkpoint to 67 tables and 162
foreign keys. M3A-12 adds a lossless [manual creation pending owner](MANUAL_TASK_CREATION.md)
through the tenth forward migration, with 68 tables/163 foreign keys at that
checkpoint. M3A-15 adds [actual report history](WORK_REPORTS.md) through the
eleventh migration, with 69 domain tables/169 foreign keys at that checkpoint.
M3A-22 adds [owned clarification history](COMMAND_RESOLUTION.md) through the
twelfth migration, with 72 domain tables/176 foreign keys at that checkpoint.
M3A-17 adds [immutable read snapshots](READ_MODELS.md) through the thirteenth
migration. That checkpoint schema is `0.8.0-read-models`, with
73 domain tables/177 foreign keys.

M3B-01 adds [typed relationship metadata](RELATIONSHIP_STORAGE.md) through
`013_relationship_storage`, preserving the thirteen-step prefix. That checkpoint
fourteen-step schema is `0.9.0-relationships`, with 73 domain tables/178 foreign
keys and three runtime metadata tables. Rule/link history remains immutable;
old rows are not silently admitted to the new typed port.
M3B-03 adds [atomic creation outbox](CREATION_OUTBOX.md) through
`014_creation_outbox`, preserving the fourteen-step prefix. That checkpoint fifteen-step
schema is `0.10.0-creation-outbox`, with 76 domain tables/183 foreign keys
and three metadata tables. Canonical events and durable delivery history are
separate from source Task state, without historical backfill.
M3B-05.a adds [immutable occurrence history](GENERATION_COMMIT_FOUNDATION.md) through
`015_generation_occurrences`, preserving the fifteen-step prefix and legacy unadmitted heads
without backfill. The current sixteen-step schema is `0.11.0-generation-occurrences`,
with 77 domain tables/193 foreign keys and three metadata tables. This foundation
does not execute generation; [M3B-05 scoped runtime](GENERATION_RUNTIME.md) now supplies actual atomic publication without another migration.
The three metadata tables are counted separately. Earlier native regression
is archived in [M3A-17 migration acceptance](../reports/acceptance/M3A-17-migrations.json).

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

Installed packages include the current manifest and all nine SQL resources.
`load_migration_plan()` resolves them under the environment's `share/whattodo`
directory; checkout tools pass their explicit repository root. The PostgreSQL
driver remains optional until an executor is actually called.

Repositories use `schema_checked_transaction` to retain the shared migration
lock throughout their read/write operation, after checking compatibility in
that transaction. This closes the gap between a separate startup check and
later repository work. The gate grants no caller or Task mutation authority.

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

This card documents restore-based recovery. [M3A-18](../toolchain/BACKUP_RESTORE.md)
now exercises a logical backup, isolated separate-database restore and actual
failed-restore rollback/retry against all thirteen prototype migrations. Production
backup, retention and cutover remain later operations tasks.
Automatic down migrations and silent data loss are not provided.

Transaction and lock behavior follows official
[Psycopg transaction documentation](https://www.psycopg.org/psycopg3/docs/basic/transactions.html)
and [PostgreSQL advisory-lock documentation](https://www.postgresql.org/docs/18/explicit-locking.html#ADVISORY-LOCKS).

M3B-06 appends [generation processing](runtime-migrations/016_generation_processing.sql), the seventeenth step at `0.12.0-generation-processing`: 82 domain tables/204 foreign keys plus three metadata tables. Persistent lineage, checkpoints and chain reservations support the [finite worker](GENERATION_PROCESSING.md); earlier SQL remains unchanged.
