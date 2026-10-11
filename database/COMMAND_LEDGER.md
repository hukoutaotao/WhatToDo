# Durable command replay and receipt reconciliation

M3A-10 extends the [atomic coordinator](ATOMIC_TRANSACTIONS.md) with authenticated
`lookup_commit(context, caller=...)` and exact duplicate-command replay. It uses
the existing immutable command, audit, authority and Task history; the nine-step
schema and all SQL pins remain unchanged.

That is the M3A-10 checkpoint. M3A-15 adds an explicitly selected WORK_REPORT
aggregate and checks its full report/actual observation plus paired original
Task revision during lookup. See [reported actual work](WORK_REPORTS.md) for the
separate observation-ID replay rule; the original command fingerprint still
binds both audited aggregate writes.

## Stable meaning and caller ownership

The frozen `CommitRequest.fingerprint` includes the principal, expected store
revision, concrete aggregate writes and their expected versions, audit ID and
source reference. JSON bodies are strict and canonical; writes are sorted by
key for the fingerprint. Request ID identifies the command; correlation IDs
identify attempts. Changing only the correlation or the order of the same
batch does not change its meaning. Retries retain the original request ID,
audit ID, expected versions and payload. A caller must inspect conflict results
before issuing a separately authorized correction.

Only the independently authenticated original principal and origin may look up
or replay a stored receipt. External, unauthenticated, different-principal or
different-origin callers receive no receipt. Request data, approval text and
the receipt itself do not authenticate the caller.

## Read before a new publication

After checking caller identity and bounded request size, `commit` enters the
schema-checked transaction and looks for the original command. A found receipt
is validated against its exact header and ordered distinct changed keys; the
immutable audit entry, source, timestamp and authority scope; complete before
and after values and a rebuilt original fingerprint; actual historical Task
payloads and the transaction that produced each after-version; and a store
epoch at least as new as the receipt's committed version.

If caller ownership and meaning match, it returns `SUCCESS / REPLAY` with the
original typed `CommitReceipt`. Its original changed-key order is preserved.
It does not invoke the append hook, insert observations/audit/authority, advance
versions, consult current defaults or require an active new permit. Original
permit expiry and later Task corrections do not invalidate an owned historical
read. Same ID with changed meaning returns
`CONFLICT / REQUEST_ID_CONTENT_CONFLICT`; no write is attempted.

When no command is observed, the exact active permit and all schema, reference,
Task/store version and atomic publication checks from M3A-09 still apply. An
empty or expired permit registry cannot authorize a fresh command. Failed
transactions leave no receipt or deduplication tombstone; a still-authorized
retry can commit that same ID. The command PK, global epoch lock and atomic
receipt/state publication prevent concurrent duplicates from both committing.
A racing attempt may return a retryable native lock/serialization result; its
next identical retry reads the original receipt.

## Unknown outcome is retained until observed

`lookup_commit` uses a read-only repeatable-read schema-checked transaction. A
validated owned receipt returns `SUCCESS / COMMIT_FOUND` with the caller's new
correlation reference. An absent receipt returns
`UNKNOWN / COMMIT_NOT_OBSERVED`: another transaction may still be in flight,
so absence of a visible row does not establish that nothing committed.

Unavailable reads return a retryable result; malformed or inconsistent receipt
history fails explicitly. A legacy fixture receipt outside the typed protocol
returns `COMMAND_RECEIPT_INVALID`, without inventing a result from Task heads.
After an ambiguous COMMIT acknowledgement, a fresh connection can read the
durable receipt and then replay the identical request without a second write.
Database history survives process restart; no in-memory cache is authoritative.

The current concrete coordinator supports Task writes. The ledger's receipt
and fingerprint checks use the generic port contract; future aggregate handlers
must add explicit storage/backlink checks. [M3A-11](COMMAND_VALIDATION.md) now
checks resolved authority and binds domain command meaning to the receipt.
Actual completion/effort command handlers remain M3A-14/15, and the full
StateStore/read-service surface remains later work. No live account, current
course Task, authenticated transport or deployment is activated.

## Verification and handoff

```powershell
.venv\Scripts\python.exe -m unittest tests.test_command_ledger -q
.venv\Scripts\python.exe tools/verify_command_ledger.py
.venv\Scripts\python.exe tools/verify_transactions.py
```

The native launcher runs in the [owned PostgreSQL harness](../toolchain/POSTGRES_TESTS.md),
using real separate connections for concurrent identical and changed requests,
an in-flight uncommitted writer, failed commit and lost acknowledgement. It
also verifies restart with an empty/expired permit registry, caller isolation,
later corrections, reordered batches, immutable evidence, invalid legacy
receipts and a plausible forged receipt with a wrong Task transaction backlink.
The completion scenario retains explicit zero U and preseeded synthetic actual
observations on retry; it does not implement the future actual-work handler.
State comparisons include sixteen Task/authority/audit/observation tables.

Acceptance: [command replay](../reports/acceptance/M3A-10.json),
[atomicity regression](../reports/acceptance/M3A-10-transactions.json) and
[clean offline installation](../reports/acceptance/M3A-10-package.json).
Original checkpoints remain unchanged; actual status and the next ready card
are recorded in [PROGRESS](../plan/PROGRESS.md).
