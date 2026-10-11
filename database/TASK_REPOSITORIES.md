# Task and stage aggregate storage

M3A-07 implements lossless Task queries and an internal append operation over
the existing [aggregate contract](../formats/input/TASK_AGGREGATE_CONTRACT.md).
It preserves separate completion, disposition and trust values. Cancellation
is a new disposition revision, not physical deletion or a zero remaining
estimate. Canonical command coordination and live handlers remain later cards.

## Values, bytes and references

[Task storage values](../src/application/task_storage.py) admit supported wire
bytes through the existing codec and domain consistency checks. A stored value
retains its original bytes/hash and detached TaskAggregate; original timestamps,
offsets, JSON array ordering and unknown/zero distinctions survive roundtrip.
Admitted values alone never constitute a write permit. The append hook repeats
codec admission rather than trusting a directly constructed value.

Normalized projections use the existing task_revision, task_details_revision,
stage_revision and task_field_provenance tables. PostgreSQL normalizes instants
for comparisons; source spelling and offsets remain in the original payload.
Original total, user remaining U, stage estimates and prediction references
remain separate. Actual-work observations and relationship graphs are separate
repositories and are not duplicated inside the Task budget.

COURSE/ACTIVITY contexts require an explicitly supplied matching Profile key
with its registered version. TaskType and template-total definitions require
exact registered versions. GOAL/EXAM wire contexts contain a logical ID;
storage checks an accepted identity exists without selecting a new version or
activating its policy. Estimate, due and prediction references must match their
stored owner, scope, values and source instants. Full command/behavior/expiry
policy eligibility is handled by the later authority pipeline, not by storage.

## Forward migration

[007_task_aggregate_storage.sql](runtime-migrations/007_task_aggregate_storage.sql)
is the eighth pinned runtime step, with schema version `0.3.0-task-storage`.
It adds four append-only tables and eleven FKs, including a new FK on existing
stage revisions. That checkpoint has 57 domain tables and 144 FKs. M3A-08's
[evidence storage](EVIDENCE_REPOSITORIES.md) brings the current nine-step schema
to 67 domain tables and 162 FKs; three runtime metadata tables are counted
separately. The previous seven-step
manifest remains in [M3A-06's snapshot](../reports/acceptance/M3A-06-migration-plan.json).
The five M2 SQL sources and the two earlier runtime SQL sources are unchanged.

| Table | Stored meaning |
| --- | --- |
| task_payload_revision | Original bytes/hash, Task revision/transaction and Profile/prediction references |
| stage_identity | Permanent stage ID and parent Task ownership |
| task_stage_revision | Ordered membership of exact stage versions in a Task snapshot |
| stage_effort_revision | Exact stage estimate observation, seconds and timestamps |

Native constraints bind payload hash/header and Task revision/transaction,
stage membership/ownership and estimate references. Stage IDs cannot move to
unrelated obligations. Stages share their parent's Task budget; they are not
independent task identities.

The migration binds existing stages to their first stored parent/transaction
without rewriting stage history. Conflicting historical owners cause migration
validation to fail. It does not invent original aggregate bytes for old core
rows: queries of such historical revisions fail explicitly with
`TASK_STORAGE_LEGACY_PAYLOAD_UNAVAILABLE`. There is no real application database
to backfill at this development checkpoint.

## Repository boundary

[PostgresTaskRepository](../src/adapters/postgres_tasks.py) exposes `get` for
current or exact historical revisions and `list_current` with independent
completion/disposition/trust filters. Reads hold a schema-checked shared
migration lock and verify retained payloads against normalized projections,
ordered stage membership, provenance and referenced facts. Missing IDs return
None; inconsistent or unavailable snapshots fail explicitly. A new connection
can reconstruct current and historical records.

`_append_in_transaction` is an internal adapter hook, not an external CRUD
endpoint. It requires an already open transaction, an independently configured
active exact-write permit and an authenticated matching caller. It checks the
current store/Task revisions, pinned schema, a prepared command receipt from
the current transaction, matching authority reference and full before/after
audit. Empty permit registries deny writes. Input JSON cannot register permits.
Schema readiness and SQL role privileges do not grant user authority.

Append uses a savepoint inside the coordinator's transaction. A caught semantic
error removes partial Task/stage rows without committing or rolling back the
whole outer transaction. It does not create permits/audit, publish the store
epoch or independently commit. [M3A-09](ATOMIC_TRANSACTIONS.md) now coordinates
atomic publication; [M3A-10](COMMAND_LEDGER.md) supplies durable replay.
[M3A-11](COMMAND_VALIDATION.md) now checks schema, independently resolved
authority, current references and complete effects before publication.
[M3A-12](MANUAL_TASK_CREATION.md) now provides the manual create handler.
[M3A-13](TASK_FACT_PATCHES.md) adds explicit fact corrections, preserving exact
profile and original expiry-notice bindings. Read-only validation may resolve
typed prepared dues/estimates; append always checks their actual SQL rows within
the atomic publication transaction.
[M3A-14](TASK_LIFECYCLE.md) now supplies explicit parent completion/cancellation,
preserving actual work and existing completed-stage snapshots while completing
the remaining stages in one audited publication.
The Task verifier's explicit synthetic coordinator supplies these prerequisites
only as test fixtures; it is not a released command service.

Task heads advance by one checked revision. New stage versions advance from
their latest stored revision; unchanged stages reuse an immutable version.
A first persisted reviewed stage snapshot can already name a later version;
the repository preserves it without fabricating missing earlier history.
Removing a stage from a later snapshot retains its identity and past membership.
Physical history update/delete/truncate is rejected.

## Verification

```powershell
.venv\Scripts\python.exe -m unittest tests.test_task_storage -q
.venv\Scripts\python.exe tools/verify_task_repository.py
.venv\Scripts\python.exe tools/verify_migrations.py
.venv\Scripts\python.exe tools/verify_package_install.py
```

[Focused tests](../tests/test_task_storage.py) cover wire/domain admission,
raw hash/content agreement, exact Profile/notice versions, independent effort
facts, detached projections, stage titles/order and source offsets. Native
checks cover persistent roundtrip, old revisions, restart reads, same-parent
stage reuse, wrong-owner FKs, missing references, unknown/zero estimates,
cancelled/complete state, prepared authority/audit failures, whole-transaction
rollback and savepoint rollback when an error is caught.

The original checkpoint is archived in [M3A-07 acceptance](../reports/acceptance/M3A-07.json),
with separate migration and clean offline installation reports. All 31 native
Task checks also pass against the current nine-step schema in
[M3A-08 Task regression](../reports/acceptance/M3A-08-tasks.json). No real course,
Task, source, Calendar, user account or deployment is activated. Source/candidate
repositories are implemented in M3A-08; complete StateStore, command authority, prediction
import and lifecycle handlers remain their separate planned modules.

M3A-15 supplies the separate [actual-work repository](WORK_REPORTS.md). A work
report publishes a new Task revision and immutable WORK_REPORT together, keeping
actual increments outside the Task budget. Its handler preserves exact existing
Profile and original expiry-notice bindings across repeated report revisions.
