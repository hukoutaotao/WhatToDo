# Bounded generation processing

M3B-06 adds a finite PostgreSQL outbox consumer over the independently authorized
[generation handler](GENERATION_RUNTIME.md). It processes canonical creation
events under configured principal/account scopes and exact accepted rule versions.
It introduces no new workflow engine, per-instance approval or live scheduler.

## Entry points and ownership

`PostgresGenerationWorker` takes the application connection, codec, current
migration plan, injected Clock, independently configured `GenerationPolicy`,
worker identity, definition repository and `ProcessingLimits`.

- `run_batch()` claims at most `max_events` events and executes at most
  `max_rules_per_lease` rules per claim. Its result records processed event count,
  checkpoint states and whether a claim found the queue idle. Reaching the batch
  cap does not prove that the queue is empty.
- `wake(event_id)` acts only on an owned `WAITING_FACTS` or `FAILED` delivery whose
  independently evaluated inputs changed. An unchanged input returns no claim.
  A new claim has a new fencing token and retains prior delivery history.
- Callers configure exact rule keys; neither a latest-version lookup nor a
  serialized approval flag supplies authority. A completed delivery is not
  retroactively reopened merely because a rule version changed.

Default processing limits are 32 events, 16 rules per lease, five attempts,
300-second leases and 30-second retry delays. Values are positive bounded integers.
Application connections require the optional PostgreSQL driver; its absence is
the explicit `TRANSACTION_DRIVER_UNAVAILABLE` error.

## Durable progress and chain limits

[The seventeenth migration](runtime-migrations/016_generation_processing.sql)
adds immutable lineage, checkpoint and reservation histories with advancing
heads. Current schema `0.12.0-generation-processing` has 82 domain tables,
204 foreign keys and three runtime metadata tables. Earlier SQL artifacts are
unchanged. The additive delivery guard allows a new claim from a terminal
waiting/failed delivery; application code requires the changed-input check.

A checkpoint pins evaluated input hashes, selected rule versions, the next cursor,
committed rule results and attempts. Only complete results can settle `DONE`;
pending facts remain `WAITING_FACTS`. A partial rule batch returns to `READY`
with a retry time and preserves its cursor. Batch continuation does not consume
the transient-failure allowance. Actual progress resets that allowance.

Each event retains its canonical root, causal parent and depth. Reservation
transactions serialize on the root row. The instance budget includes actual
counterparts created before worker processing and outstanding reservations;
committed counterparts are counted once. A changed accepted role cannot reset
the budget. An actual descendant cannot restart its depth at zero. Recursive
selected graphs and exceeded instance/depth limits produce visible failures.

## Fencing and recovery

Every metadata mutation verifies the current scoped delivery lease. The generator
checks the same lease inside its canonical transaction, verifies the matching
reservation before a new counterpart and fences again before commit. Losing a
lease therefore prevents further canonical writes. Lease renewal occurs between
independent rule transactions and retains the ownership token.

Generation, checkpoint recording and delivery settlement are separate durable
steps. A crash after generation replays the immutable occurrence and receipt;
a crash before checkpoint commit rolls back metadata. Once its lease expires,
another worker can resume. Unknown commit acknowledgement is reconciled through
the generation handler's committed-receipt lookup before recording a result.
Connection loss leaves recoverable delivery state and raises a closed retry error;
it cannot fabricate completion. Retryable lock/serialization failures use backoff,
then stop at the configured attempt limit. Unchanged terminal failures remain
visible until a later scoped recovery changes accepted inputs or policy.

Source cancellation/reactivation retains the canonical creation identity and
counterpart history. It cannot silently cancel or recreate a counterpart.

## Verification and remaining work

Run `.venv/Scripts/python.exe tools/verify_generation_worker.py` for isolated
native PostgreSQL verification and `tools/run_ci.py` for the full pinned baseline.
The native worker fixture also executes the seventeen underlying generation
runtime checks; prerequisite checks are reported separately from worker checks.
Six checkpoint/limit methods, 53 combined generation methods and 715 full methods pass. The worker adds sixteen native checks; full CI passes 30 phases/197 native checks across ten groups, with all seventeen databases dropped and all ten servers stopped. Clean installation verifies 73 modules/74 exact source hashes/40 schemas. Acceptance artifacts are archived in [M3B-06](../reports/acceptance/M3B-06.json).

Only explicit finite worker calls are implemented. Live activation, deployment,
provider/calendar/n8n/model integrations and personal intake remain deferred.
Next development is [stage rework](../plan/tasks/M3_RELATIONSHIPS_REVIEWS.md#m3b-07).
