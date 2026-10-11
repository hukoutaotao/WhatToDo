# Atomic Task transactions

M3A-09 adds [detached transaction preparation](../src/application/transactions.py)
and a [PostgreSQL coordinator](../src/adapters/postgres_transactions.py) over the
existing [Task repository](TASK_REPOSITORIES.md). Its original checkpoint used
the nine-step schema, `0.4.0-evidence-storage`. Current handlers use the twelve-step
runtime plan, `0.7.0-command-resolution`. [M3A-15](WORK_REPORTS.md) adds audited
actual reports; [M3A-22](COMMAND_RESOLUTION.md) adds separate clarification process
history without modifying canonical Task transaction rules.

## Authority and admitted writes

`PostgresTransactionCoordinator.commit(request, caller=..., permit_ref=...)`
accepts a typed `CommitRequest`. An authenticated non-external caller must match
its principal. The constructor's independently supplied `TransactionPermit`
registry must supply an active permit for a fresh publication, binding that principal, caller origin,
exact request fingerprint and validity interval. Request text, existing source
records, approval IDs and existing database authority headers cannot supply this
registry. Authority resolution and authenticated transport remain separate cards.

Preparation admits every Task through the frozen schema/domain codec and checks
its exact ID, next revision and explicit Profile/expiration bindings. It accepts
1–100 distinct Task/WORK_REPORT writes with at most 8 MiB of total serialized bodies, within
the existing 1 MiB per-Task limit. Unsupported aggregate kinds fail explicitly;
adding one requires a concrete admitted storage handler and complete audit/CAS
coverage. Unknown effort and dates remain unknown. Referenced definitions and
other facts must already exist. Independently authorized typed prepared
USER_REMAINING observations and normalized dues may be staged inside the same
transaction before Task append; the coordinator checks their exact target,
payload, source and root authority. It does not infer or independently authorize
these supporting facts.

WORK_REPORT admission is opt-in and requires a paired exact Task update.
Original report bytes, settlement and observation identity participate in the
permit, fingerprint, full audit, replay proof and receipt. Actual work and
explicit U are separate observations; neither is fabricated from planned time.

## One publication boundary

The coordinator owns an idle autocommit connection and starts a schema-checked,
repeatable-read transaction. It retains the shared migration lock throughout
the operation, then acquires the singleton store-epoch row with `FOR UPDATE
NOWAIT`. It compares both the expected store revision and every Task's expected
revision before staging any write. Concurrent operations either report busy,
observe a stale version or publish the one next version.

Within that same transaction it stages:

1. An immutable exact-permit authority header, or validates an identical existing
   header without modifying it.
2. The command transaction and its typed receipt, including the next store epoch.
3. The audit entry and exact complete before/after values for every Task.
4. All Task, stage, payload, provenance and head rows through M3A-07's internal
   transaction-bound append hook.
5. A final permit validity check and a conditional store-epoch advance.

The append hook independently verifies the caller/permit, current schema,
versions, references, audit values and that the prepared command row was created
in this same open transaction. Its savepoint does not commit independently.
The outer transaction commits all staged rows together. Deferred FK failures at
COMMIT and failures after audit, Task or epoch staging roll everything back.
Previous payload bytes, versions and audits remain immutable. No provider call
or notification dispatch occurs within this database transaction.

## Typed failure meaning

| Result | Meaning |
| --- | --- |
| `SUCCESS / COMMITTED` | PostgreSQL acknowledged the whole publication; receipt carries the committed epoch |
| `CONFLICT / STALE_STORE_REVISION` | Expected global version no longer matches |
| `CONFLICT / STALE_AGGREGATE_REVISION` | Expected Task version no longer matches |
| `RETRYABLE / TRANSACTION_BUSY_OR_ABORTED` | Native lock contention, serialization failure or deadlock; no publication |
| `RETRYABLE / TRANSACTION_SCHEMA_UNAVAILABLE` | Migration lock or metadata is temporarily unavailable |
| `RETRYABLE / TRANSACTION_NOT_COMMITTED` | Transport failed before entering COMMIT; no commit was requested |
| `UNKNOWN / COMMIT_ACKNOWLEDGEMENT_LOST` | Failure while completing COMMIT; durable publication may already exist |
| `PERMANENT` | Invalid caller/permit, shape/reference, schema compatibility or other non-retryable rejection |

Server-reported constraint rejection during COMMIT is a definite rejection.
Transport errors, or driver errors without a server SQLSTATE during COMMIT,
retain `UNKNOWN`. Results contain redacted codes and the caller's correlation
reference; they do not contain SQL text, credentials or source bodies. The
optional PostgreSQL driver is imported only when executing a prepared database
operation; its absence has an explicit result and does not prevent package
import or pure preparation.

The durable command row shares the atomic transaction. M3A-10 adds
[duplicate-command replay and receipt reconciliation](COMMAND_LEDGER.md),
including restart and changed-payload handling. Identical owned requests return
the original receipt before current permit/version checks; changed contents
under one ID fail explicitly. It is not yet the complete `StateStore` port.
[M3A-11](COMMAND_VALIDATION.md) now checks independently resolved authority,
current references and complete effects before issuing the exact permit.
[M3A-12](MANUAL_TASK_CREATION.md) now provides manual creation and atomic
supporting initial user-estimate observations. [M3A-13](TASK_FACT_PATCHES.md) now
adds opt-in exact fact updates and atomic normalized dues, preserving original
sources, support history and owned command replay. [M3A-14](TASK_LIFECYCLE.md)
adds explicit completion/cancellation with atomically published parent/stage
zero observations. Later actual-work/stage/review handlers remain open.
No real user data, account, Calendar or application service is activated here.

## Verification and handoff

```powershell
.venv\Scripts\python.exe -m unittest tests.test_transactions -q
.venv\Scripts\python.exe tools/verify_transactions.py
```

The native verifier uses the [owned PostgreSQL harness](../toolchain/POSTGRES_TESTS.md)
with separate application/migration roles and only synthetic sources/permits.
It performs create, patch, two-Task batch, stale-version rejection, true
simultaneous writers, lock contention, deferred-FK rollback, mid-batch rollback,
permit expiry, actual connection loss, lost COMMIT acknowledgement and fresh
connection/history reads. Failure snapshots compare fifteen state/audit tables.
All owned databases are dropped and the owned cluster stopped on completion.

Acceptance: [M3A-09 native report](../reports/acceptance/M3A-09.json) and
[clean installation](../reports/acceptance/M3A-09-package.json). Earlier Task,
evidence, migration and package checkpoints retain their original counts and
artifacts. Progress and the next ready card are in [PROGRESS](../plan/PROGRESS.md).
