# Command schema, resolved authority and exact Task effects

M3A-11 connects the frozen command contract and domain authorizer to current
PostgreSQL references and the [atomic coordinator](ATOMIC_TRANSACTIONS.md).
It is an application service for independently resolved instructions, before
the manual creation and base-command correction handlers. The opt-in
[M3A-13 fact handler](TASK_FACT_PATCHES.md) resolves its independent exact typed
grant and shares the same atomic coordinator; the frozen base command does not
silently accept its deadline fields. Neither handler parses user prose or
activate a live channel. External text and AI results remain proposals.

## Independent authority and strict admission

`admit_command` accepts at most 1 MiB of strict command JSON, rejects duplicate
keys, unsupported versions and approval flags, and constructs immutable domain
values. Caller authentication is independently supplied. The command cannot
populate the trusted grant, creation-seed, account-scope or condition registries.

`register_grant` is a trusted resolver/setup hook for an immutable, source-backed
`AuthorityGrant`; it is not a JSON transport operation. Registration preserves
the exact normalized command, principal/origin, source, validity and resolved
scope. The service requires both the independently supplied grant and the
identical persisted scope. The referenced user statement must belong to an
independently registered provider/scope/account. A known database authority ID,
an external source, a confidence score or a serialized approval assertion cannot
replace these checks. Explicit resolved instructions need no second approval.

## Current references and complete effect matching

The schema-checked, read-only repeatable-read frame loads current Tasks, the
store epoch, exact immutable definition/profile references and supporting effort
facts. The pure validator checks exact targets/versions, declared fields,
principal/origin and rule/batch scope. It compares the complete proposed
aggregate with the expected effect; undeclared context, timing, workload,
metadata, stage membership and acceptance changes cannot ride along with an
authorized title correction. Changed field provenance must name the actual
statement. Updates preserve the original exact profile version.

Creation requires an independently supplied, admitted seed with accepted source
authority, unknown remaining effort and timing, incomplete stages and no
completed/expired outcome. Seeds and versioned defaults alone confer no
authority. The implemented creation handler assembles these seeds from resolved facts.
New known user estimates require exact stored USER_REMAINING observation
ownership, source, authority, value and observation time. Completing a parent
requires zero U and the policy's zero-U completion effects on its incomplete
stages; unrelated stage facts and historical actual work remain unchanged.
M3A-12 additionally supplies typed resolved initial user estimates that the
coordinator atomically stages before Task append. [M3A-14](TASK_LIFECYCLE.md) now
adds completion/cancellation handlers and atomic parent/stage zero observations.
The whole-effect validator checks the required stage source pointers and
clearing current expiry-notice bindings on explicit cancellation/reactivation.
Actual-work reporting remains M3A-15; unreported work timestamps stay unknown.

A relationship-rule creation additionally requires its exact active accepted
SQL rule and cached Git version/template, matching source/target TaskTypes,
and the source Task's actual canonical creation transaction. A raw source event
cannot impersonate that transaction. Rule activation and mapped generation
remain separate cards. Expiry additionally requires an independently confirmed
condition, the exact current-version notice and an actual persisted DELIVERED
dispatch result. Delivery alone cannot establish condition truth; a claimed
delivery alone cannot substitute for a result. The expiry effect preserves
completion and U. Synthetic verification inserts test delivery rows and sends
no message.

## Publication and replay

Only a fully checked effect receives an exact full-request transaction permit,
valid for at most five minutes and bounded by grant expiry. The readonly frame
ends before publication. The coordinator rechecks the global epoch and every
Task version under its write transaction, closing the gap against a concurrent
change. It commits Task history, authority annotation, full audit, durable
receipt and epoch together. The annotation binds the normalized domain command,
original wire hash and root grant reference to that exact publication.

Owned historical replay checks both domain command meaning and the original
concrete request/audit fingerprint. Empty registries and expired grants do not
force a second approval of an already committed command. A different command
cannot borrow a receipt by presenting the same writes. Caller isolation and
unknown commit outcomes retain the [ledger's rules](COMMAND_LEDGER.md).

Unavailable read-only references return a retryable result without claiming a
commit. Invalid schema, references or effects fail with stable redacted codes.
No raw statement, provider payload or SQL diagnostic is returned in the result.

## Verification and remaining scope

```powershell
.venv\Scripts\python.exe -m unittest tests.test_command_validation -q
.venv\Scripts\python.exe tools/verify_authorization_pipeline.py
.venv\Scripts\python.exe tools/verify_command_ledger.py
.venv\Scripts\python.exe tools/verify_transactions.py
.venv\Scripts\python.exe tools/verify_package_install.py
```

Eleven focused methods, 25 native authorization checks, 21 native ledger checks,
22 native atomicity checks and 396 full regression methods pass. Clean offline
installation verifies strict admission, complete effect scope and the explicit
optional-driver result across 43 modules. Native tests include a reference-read
disconnect and a real second connection committing after authorization but
before publication. Denied effects compare sixteen state/audit/observation
tables. All owned databases are dropped and test clusters stopped.

At the M3A-11 checkpoint, the nine-step schema and 91-artifact generic baseline
remained unchanged. [M3A-12](MANUAL_TASK_CREATION.md) adds one forward pending
draft owner and binds exact default provenance to creation. The
frozen command fields do not express deadline or standalone stage editing;
those handlers require explicit contract evolution rather than hidden fields.
Manual intent resolution, observation staging, complete StateStore/read surfaces,
real authentication/accounts/profiles and runtime activation remain unfinished
tasks. M3A-12 manual Task creation is now implemented; current next scope is in
[PROGRESS](../plan/PROGRESS.md). Executed checkpoint
evidence is in [M3A-11](../reports/acceptance/M3A-11.json) and
[live progress](../plan/PROGRESS.md).
