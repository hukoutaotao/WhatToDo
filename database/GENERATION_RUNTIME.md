# Scoped atomic counterpart generation — M3B-05

[The application-role handler](../src/adapters/postgres_generation.py) now
executes [composite generation preparation](GENERATION_COMMIT_FOUNDATION.md).
It is an internal application service, with no live worker or public HTTP route.
M3B-05.a and M3B-05.b together complete the parent card; leasing and bounded
cascade orchestration are implemented by [M3B-06 processing](GENERATION_PROCESSING.md).

## Independent scope and current inputs

[GenerationPolicy](../src/application/generation_runtime.py) is independently
configured with one principal, its registered provider/scope/account bindings,
a complete selected rule-version registry and graph limits. One exact version
per stable rule ID is allowed. The future worker must supply the complete
registry for its configuration; a request cannot choose another version or
replace that registry. Do not infer a latest version from immutable history.

`generate(event_id, rule_id, correlation_ref=..., caller=...)` accepts only
identities and an independently authenticated RELATIONSHIP_RULE caller. It
accepts no draft, approval flag, command authority or serialized permit.
Foreign principal/origin/account, missing canonical events, fake definition
repositories and unselected rules fail before effects are published.

The handler reads the exact original event and Task bytes, source evidence,
creation receipt and its authority annotation in one checked SQL snapshot.
Manual source acceptance is checked against its original command/grant;
rule-created sources retain their original generation receipt and accepted root.
Historical grants are checked at their actual commit time. Current execution
checks the selected root's active accepted-rule payload/hash, principal, source
account and validity, including a final check before transaction commit.

Definitions come from the validated immutable PostgreSQL/Git cache on that
same connection. Construction is repeated under the current snapshot rather
than accepting an external proposal. The manifest retains both the original
creation snapshot and the current source revision/hash used for concrete links
or a parent-stage update. A delayed operation maps original creation facts,
even when the current source has since changed. Historical receipt rebuilding
uses the pinned current-at-commit revision rather than today's Task head.

The graph check uses the configured selected rules, current owned concrete
relations and typed endpoint/stage ownership, plus the proposed effects. The
existing bounded service checks generation and hard order separately. A reverse
hard-order link does not reverse generation; no undeclared execution order is
introduced. Invalid, ambiguous, unadmitted legacy or oversized graphs stop before
publication. Graph validation itself does not grant authority.

## Atomic publication and stable replay

The handler obtains the schema readiness lock and NOWAIT store-epoch row lock
inside a repeatable-read transaction. All normal writers use that epoch boundary.
A concurrent snapshot/lock conflict is retryable; a fresh retry sees either the
original occurrence or the current parent revision. There is no external I/O
inside the transaction.

After independent resolution, the handler derives a short-lived exact permit
for the whole recomputed request. It writes that derivative authority, receipt,
full before/after audit, supporting estimate observations, admitted Task or
current parent-stage update, optional explicit relation, immutable occurrence
revision/head and epoch together. The existing internal Task append hook still
checks exact scope, transaction identity, CAS, audit, wire admission and actual
references. A newly created independent Task receives its own canonical event
and READY delivery record through the existing outbox trigger.

Missing facts publish only an occurrence PENDING result. A closed current stage
parent publishes only a FAILED result. Identical pending/failure retries return
the prior receipt without another revision. A newly accepted version can resolve
pending facts under the same stable occurrence/target key, retaining old history.
No per-instance confirmation queue is added for authorized generation.

CREATED is terminal. The handler verifies and returns the original target and
receipt before reconstructing a new target, including after a rule version edit
or an inactive new version. Source cancellation/reactivation leaves an existing
independent target unchanged. Stages retain one parent budget and exact membership;
two concurrent stage rules retry against the current parent and preserve both.

`lookup(...)` is read-only. It verifies actual authority/source/account, receipt
fields, exact audit fingerprint, immutable occurrence snapshots and actual
Task/relation effects. For CREATED results it reconstructs the original request
from historical source/current-parent snapshots and exact original definitions.
Source receipt ancestry is bounded by the configured generation-depth limit.
Historical receipts retain their original rule versions and grants.

A connection failure before commit rolls back all effects. A transport/interface
error while receiving the commit acknowledgement is UNKNOWN, not absence. A
fresh lookup/retry reconstructs the durable original receipt and does not create
another counterpart. The historical M3B-05 checkpoint has sixteen steps,
`0.11.0-generation-occurrences`, 77 domain tables/193 foreign keys and three
metadata tables. Its sixteen SQL artifacts remain unchanged;
[M3B-06](GENERATION_PROCESSING.md) adds the current seventeenth step with
82 domain tables/204 foreign keys.

## Evidence and remaining work

[Eight focused boundary methods](../tests/test_generation_runtime.py) cover
independent policy/version/account registration, caller guards, refusal of draft
or fake repository input, explicit optional-driver absence and honest outcomes.
The 39 preparer/evaluator methods remain regressions; occurrence parsing now also
rejects boolean revision values and pins the current-at-commit source snapshot.
Installed policy/handler smoke runs without the optional database driver.

[Seventeen native checks](../tools/verify_generation_runtime.py) use actual
manual creation, independent accepted rule records/Git definitions, real
application connections and full SQL effects. They verify independent target
budget/provenance, pending resolution/history, reverse hard order, graph cycles,
cross-principal/account denial, inactive/expired authority, concurrent target and
parent-stage writes, actual user cancellation/reactivation and delayed mapping.
Actual client connection close after staged Task/link/observation/history writes
tests rollback for independent, reverse-link and stage paths. Successful commit
with an injected lost operational/interface acknowledgement tests fresh
reconciliation for all three paths. These are automatic generation transactions,
not the metadata-only fixtures of M3B-05.a.

Current acceptance is [M3B-05](../reports/acceptance/M3B-05.json) and its
[runtime child](../reports/acceptance/M3B-05b.json), with archived CI/package/native
checks and exact code/resource pins. [M3B-06](GENERATION_PROCESSING.md) integrates delivery leases,
finite cascade batches, checkpoints, visible bounded failures and restart
recovery. No live worker, personal profile activation, Calendar/provider/model
integration, hosted Actions or deployment is claimed here.
