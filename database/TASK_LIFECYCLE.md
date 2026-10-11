# User-confirmed completion and cancellation — M3A-14

[Progress](../plan/PROGRESS.md) · [Pure preparation](../src/application/task_lifecycle.py) · [PostgreSQL handler](../src/adapters/postgres_lifecycle.py) · [Command validation](COMMAND_VALIDATION.md) · [Atomic publication](ATOMIC_TRANSACTIONS.md)

The complete and cancel endpoints accept one existing Task through the frozen `command 0.1.0-draft` contract. Each requires an independently authenticated USER_COMMAND caller, an exact registered root grant and immutable USER source evidence within an independently registered account scope. Admission, a submission record or a grant ID supplied in JSON cannot supply that authority. Natural-language interpretation and pending external confirmations remain separate cards.

## Endpoint effects

`PostgresLifecycleHandler.complete` requires `completion: COMPLETE`. It also accepts an explicit zero `user_remaining_seconds`, and explicit `disposition: ACTIVE` when the user's instruction restores cancelled/expired work. Other fact edits and stage operations are rejected by this endpoint. An inactive Task cannot be implicitly restored just because completion is reported; the resolved command must explicitly authorize ACTIVE.

Completion makes parent U a known zero USER_REMAINING observation and completes still-incomplete owned stages with their own known-zero observations and next stage versions. All of these effects publish together. Already-complete stages retain their previous versions, historical U and sources; their past estimates are not replaced with current zeros. Completing an already-complete parent through a new confirmation preserves its zero observation, completed-stage versions and actual-work history. Explicitly reconfirming U=0 can record a new user estimate. An identical command retry always returns the original receipt and adds no observations or revisions.

`PostgresLifecycleHandler.cancel` requires exactly `disposition: CANCELLED`. It preserves completion, current remaining estimates, stage progress, total estimates, actual work and dates. A cancelled incomplete Task remains INCOMPLETE; cancellation supplies neither completed effort nor a new zero estimate. Cancelling work that was already confirmed complete retains the independent COMPLETE fact. Repeated cancellation records the new explicit statement in audit/provenance without inventing effort.

Explicit cancellation or reactivation of an EXPIRED Task clears its current notice backlink to satisfy the active/cancelled state invariant, retaining its condition. The original expired revision, notice identity and notice version remain immutable history. This is a policy effect of the explicit disposition change, not a notification send or fabricated delivery. Current course/activity profile versions remain exactly those of the original Task.

## Honest timing and source provenance

The immutable USER source's capture timestamp identifies when this confirmation was captured. New zero observations use that timestamp and reject a future capture. It is never assigned to `timing.completed_at`, a session start/end or actual-work report. A known actual completion timestamp remains unchanged; unknown work times remain unknown. Reporting actual duration/times belongs to M3A-15.

Per-field provenance names the confirming user source for parent completion/disposition, duplicated effort dimensions and changed stage completion/U. Replaced object descendants keep their old source/value in the before-revision; current parent provenance describes the replacement. The complete-effect validator permits only these declared or required policy effects and still rejects unrelated aggregate or source changes. Revision-bound predictions remain in history with valid/applicable false for the new Task version.

## Publication, history and replay

The handler builds the after-image itself within a schema-checked read frame. The existing command service revalidates the exact grant, current references, expected versions and whole aggregate before minting the private short-lived permit. Prepared parent/stage zero observations are inserted by the coordinator in the same transaction as Task/stage revisions, full before/after audit, receipt and store epoch. CAS and permit checks cover changes after preparation. Failure after parent/first-stage staging rolls back every zero and stage version.

Owned replay reconstructs the original after-revision and durable annotation instead of applying the command to the current head. Thus an old completion retry cannot undo a newer cancellation. Replay works after restart, grant expiry and resolver/account registry removal; changed principal, semantics, original expected epoch or audit identity conflict. History is preserved rather than hard-deleted. Lost-acknowledgement behavior remains the coordinator's explicit UNKNOWN/reconciliation contract.

## Verification and downstream scope

Run `.\.venv\Scripts\python.exe -m unittest tests.test_task_lifecycle -q` and the isolated native `tools\verify_lifecycle.py`. [Native acceptance](../reports/acceptance/M3A-14.json) covers completion/cancellation, source/submission/account isolation, exact profile history, zero provenance, repeated confirmations/replays, simultaneous complete/cancel, expired-history preservation and SQL failures after both zero and stage staging. Unit checks also exercise already-complete stage historical estimates and prediction invalidation. [Installed-wheel acceptance](../reports/acceptance/M3A-14-package.json) executes both pure endpoints and both explicit missing-driver paths.

The 30 base schemas, one opt-in fact-patch extension, 91 generic-baseline artifacts and ten-step SQL plan remain unchanged. All fixtures use synthetic callers, sources, grants, stage/expiry history and prior actual work. Live transport, stage editing/reopening and the full StateStore/runtime remain incomplete. Next card: M3A-15 reported work observations, including cumulative/new actual effort with no fabricated session times.
