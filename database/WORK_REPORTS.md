# Reported actual work

M3A-15 implements the [work-report preparation](../src/application/work_reports.py),
[authorized handler](../src/adapters/postgres_work_reports.py) and
[immutable actual repository](../src/adapters/postgres_actual_work.py).
The eleventh [migration](runtime-migrations/010_actual_work_reports.sql) adds one
report table and six foreign keys. The runtime schema is
`0.6.0-work-reports`: 69 domain tables/169 foreign keys plus three metadata tables.
The original ten-step [checkpoint](../reports/acceptance/M3A-14-migration-plan.json),
30 base schemas and 91 baseline pins remain unchanged.

## Explicit admission and authority

The extension registry supplies `work-report` (`0.1.0-work-report`) and
`actual-work-record` (`0.1.0-actual-work-record`). Consumers explicitly select
`load_supported_schemas`; default loading retains the base 30 schemas. Together
with fact patches there are three opt-in extensions, not a change to the frozen
base command or Task aggregate. Unknown versions/fields retain bytes and fail.

`PostgresWorkReportHandler.report(raw, context, expected_store_revision=...,
audit_id=..., caller=...)` requires an authenticated USER_COMMAND caller matching
the command principal. A fresh report needs an independently supplied typed
`WorkReportGrant`, its identical immutable SQL root authority, retained USER
source payload and independently registered provider/account scope. The grant
binds the entire report and expected Task revision; source text or submitted
approval fields cannot populate this registry. Caller/account/grant inputs in
the current acceptance are trusted synthetic fixtures; live transport is later.

Input includes command/principal/authority IDs, an independent observation ID,
exact Task ID/revision, `mode`, integral nonnegative `seconds`, nullable stage ID,
and nullable explicitly reported session bounds. The optional
`user_remaining_seconds` distinguishes omission, unknown (`null`) and known zero.
A stage must be permanently owned by the Task. Reporting it does not change
stage completion or stage U; the actual increment is counted once at Task level.

## Settlement and independent remaining work

INCREMENT adds the stated seconds. CUMULATIVE states the **Task-wide total**;
the persisted actual increment is `reported total - previously recorded total`.
Both the original report and the settlement are retained. Previously recorded
total sums only ACTUAL_WORK increment rows, including legacy rows, never planned
blocks, USER_REMAINING or unchanged-verification observations. Equal cumulative
totals produce a real zero increment. Lower totals are explicit conflicts;
negative corrections and counter resets need a future separately authorized
operation. Settlement follows publication order, not a guessed session order.
Seconds use the existing unbounded integral numeric domain, not bigint.

Spent time never subtracts U, marks completion, restores a cancelled/expired
Task, or creates work/session/completion timestamps. Session bounds remain null
unless explicitly supplied; one known bound leaves the other unknown. Original
offset/microsecond spelling remains in the payload. Bounds must be ordered when
both exist and cannot be later than the source capture instant. Capture time
identifies when the user supplied the report, not the work session itself.

An explicit new U creates a source/root-bound USER_REMAINING observation; null
clears the current known value while preserving history. Zero U does not imply
completion. Reporting historical work on a COMPLETE Task keeps completion and
zero U; an explicit positive/unknown U cannot silently reopen it. Actual reports
can be retained on CANCELLED/EXPIRED Tasks without altering their lifecycle,
expiry notice or prior session facts. Prediction validity is invalidated after
the new Task revision; no learning weight/model update is implemented here.

## One atomic publication and two identities

Fresh publication contains two exact RecordWrites: TASK at its expected prior
revision and immutable WORK_REPORT at observation ID/version 1. The permit,
request fingerprint, full before/after audits and receipt changed keys bind
**both** payloads. Under the existing shared migration lock and singleton epoch
CAS, the coordinator stages U, the next Task revision, settled ACTUAL_WORK row,
full report, both audits, authority, receipt and next epoch in one transaction.
SQL/protocol failures before commit roll everything back. Lost commit
acknowledgement remains UNKNOWN until the owned original receipt is observed.

The SQL report checks payload hash/identity/settlement and references its exact
Task revision, actual increment, source, authority, transaction and stage owner.
Reads re-admit original bytes and compare the complete SQL projection and actual
observation. History rejects UPDATE/DELETE/TRUNCATE; application TRUNCATE is
also denied by role permissions. Replay validates both full audits, the rebuilt
fingerprint, original Task version, report/observation backlink and caller scope.

The original command ID replays its original receipt using original epoch/audit
and payload, even after newer edits or expired grants. Different transaction
content under that command ID conflicts. Observation identity separately
deduplicates a retry with a new transport command ID: the same principal and
same report facts return OBSERVATION_REPLAY with the original receipt/report,
without a new command row, Task version or U verification. Transport command ID,
authority ID and target revision may differ on this read-only retry; reported
Task, mode, seconds, stage, bounds and U presence/value must match. Different
facts conflict. Another principal receives no owned receipt. Legacy observation
IDs lacking full report metadata are explicitly unavailable, never overwritten.

## Verification and handoff

Run focused methods with `.venv/Scripts/python.exe -m unittest
tests.test_work_reports -q`, and native checks with
`.venv/Scripts/python.exe tools/verify_work_reports.py`. Native verification uses
only a project-owned loopback SCRAM PostgreSQL instance and drops its databases
and stops the server on success or failure. The clean package checker also
verifies settlement, explicit U, two-record preparation and the missing optional
driver result outside the source checkout.

[Live progress](../plan/PROGRESS.md) records executed acceptance and regressions;
[M3A-15 report](../reports/acceptance/M3A-15.json) retains the actual result.
Transport, direct natural-language intent, stage editing/reopening, negative
corrections, learning/calibration and the full runtime remain later cards.
