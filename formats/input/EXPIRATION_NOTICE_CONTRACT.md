# Expiration notices — development draft 0.1.0

Scope: [M2-07.a](../../plan/tasks/M2_CONTRACTS.md#m2-07a). [Notice schema](expiration-notice.schema.json), [dispatch result schema](dispatch-result.schema.json), [pure lifecycle](../../src/domain/expiration.py), [synthetic fixtures](../../tests/fixtures/expiration/cases.json) and [tests](../../tests/test_expiration.py).

## Detection and delivery

A trusted condition evaluator supplies explicit condition identity, evidence reference, true/false/unknown and observation time. `detect_expiration` only prepares a notice for EXPIRING/INCOMPLETE/ACTIVE tasks whose matching condition is confirmed. REQUIRED overdue work, OPTIONAL work, completed/inactive tasks and uncertain/future conditions do not become EXPIRED. No source deletion or deadline guess is used as a condition evaluator.

Notice identity binds task ID, revision and condition reference. Repeated detection retains that identity; the application must load the existing process before dispatch rather than reinitialize it, so retries preserve previous attempts. Detection does not send anything or mutate canonical state.

`begin_dispatch` registers an immutable PENDING attempt with correlation reference. PENDING, FAILED and UNKNOWN cannot prove the user was informed. Trusted dispatch results bind the registered notice/attempt/start time and retain evidence, correlation, outcome and explicit delivery time. DELIVERED means a provider adapter has established user-facing delivery under its contract; a queued log, API acceptance or high confidence cannot supply that guarantee by itself. Neither actual delivery nor its provider is implemented here.

Confirmed failure permits a later retry. In-flight or UNKNOWN delivery blocks automatic resend. A trusted receipt/query can explicitly reconcile the original UNKNOWN attempt as DELIVERED or FAILED; the history retains both the ambiguity and its resolution. Request/result replay is idempotent, conflicting final results are rejected and a delivered notice needs no additional read acknowledgement. Actual provider idempotency/reconciliation behavior remains an adapter decision.

## Post-delivery revalidation

`revalidate_expiration` checks a current matching task revision/condition, unchanged EXPIRING/INCOMPLETE/ACTIVE state, confirmed delivery and a new confirmed condition observation at or after delivery. Completion, cancellation, requiredness, revision or condition races prevent readiness. Future evidence cannot authorize a transition.

Readiness returns compatible `NoticeEvidence` for the independent [authorizer](COMMAND_AUTHORITY_CONTRACT.md); it is not an EXPIRED write. The application still needs the registered policy grant and an audited transaction that revalidates the latest state. Completion and canonical U are never rewritten by these helpers. Failed/unknown attempts, retained snapshots and dispatch history must be persisted by the later outbox/state implementation.

## Execution and remaining handoff

```powershell
python -m unittest discover -s tests -p 'test_expiration.py' -v
python -m tools.check_contracts --examples tests/fixtures/expiration/cases.json
```

Schemas check shape, not truth of delivery or cross-record authority. Pure functions check lifecycle/time/scope using independently trusted records. No message rendering, real notification target, credentials, provider SDK, actual expiry-condition evaluation, database/outbox or personal-task transition is enabled. All examples are synthetic.
