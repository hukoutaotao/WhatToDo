# Canonical creation outbox — M3B-03

This internal persistence boundary captures the first committed canonical Task
snapshot and stores delivery processing independently of Task completion.
It does not choose rules, generate counterparts or run a background worker.

## Atomic capture

[Migration 014](runtime-migrations/014_creation_outbox.sql) captures the first
payload matching the Task's original creation transaction, together with its
exact revision/hash and the receipt's principal, authority and commit time.
The event, initial READY delivery revision and delivery head are inserted in
the same transaction as the source Task. A source rollback removes all four;
a lost commit acknowledgement leaves one durable event that command replay
does not duplicate. Pending facts and raw observations create no event.
Later Task updates do not replace the pinned original snapshot. Existing
Tasks before this migration are preserved without historical backfill.

Event IDs are `creation:` plus SHA-256 over the exact UTF-8 Task ID. Exact
foreign keys retain the original source references; the digest is not authority.
Events and delivery revisions are immutable, while heads advance by one revision.
The application role cannot insert canonical events directly. A narrowly scoped
trigger owned by the migration role performs their creation with a fixed
`pg_catalog` search path and fully qualified table references.

## Scoped delivery

[Typed values](../src/application/creation_outbox.py) and the
[PostgreSQL port](../src/adapters/postgres_creation_outbox.py) require an internal
authenticated caller, worker identity and registered provider/scope/account.
Queries bind the original principal and independently registered USER source.
Another worker may see processing state but receives no active lease token.
There is no public transport accepting arbitrary worker or authority parameters.

Claim uses a bounded 1–3600 second lease and locks only the delivery head.
`FOR UPDATE OF h SKIP LOCKED` lets another consumer skip occupied queue rows;
serialization conflicts return the closed retry result `OUTBOX_STORAGE_RETRY`.
This follows PostgreSQL's [queue-oriented locking behavior](https://www.postgresql.org/docs/18/sql-select.html).
Claims after expiry increment the attempt and replace the token. Renewal keeps
the attempt/token but advances the revision, fencing the previous lease.
Settlement verifies the entire original lease and source pins. An expired or
superseded handler cannot overwrite the replacement handler's result.

Outcomes are closed four-field values: DONE/WAITING_FACTS retain an opaque result
reference, FAILED retains a closed diagnostic, and RETRY retains a diagnostic
and an aware retry time. SQL constraints also reject malformed direct writes.
An identical acknowledgement returns its original settlement even after a
later retry claim. Changed acknowledgements conflict. Terminal outcomes are
not automatically requeued; later domain-specific recovery is a separate task.
All these operations change delivery metadata only, leaving Task, audit,
command receipt and store epoch unchanged. DONE means processing was recorded,
never that the source Task was completed.

## Verification and handoff

[Native verifier](../tools/verify_creation_outbox.py) exercises actual connection
loss before commit, acknowledgement loss after a real commit, simultaneous
consumers, occupied-row skipping, renewal, delayed retry, exact-expiry recovery,
full-lease replay checks, closed terminal outcomes, SQL rejection and cleanup.
[Pure tests](../tests/test_creation_outbox.py) cover portable values and identity,
time, token, result and input-shape boundaries. The shared CI entrypoint includes
this owned PostgreSQL group; clean-wheel smoke checks import the port without
installing the optional driver and exercise its portable values.

The schema now has fifteen migration steps, `0.10.0-creation-outbox`, 76 domain
tables/183 foreign keys plus three metadata tables. Prior fourteen SQL artifacts
are unchanged. M3B-04 may consume these pinned creation references; selection,
generation authority, deterministic target creation and domain result records
remain its own acceptance boundaries. No personal profiles or live integrations
are activated here.

[Acceptance](../reports/acceptance/M3B-03.json) records 14 focused methods, 21
new native checks and the full 662-method/153-native local regression, with
separate archived CI, installation and native reports. All fourteen test
databases/seven servers and both HTTP listeners were cleaned up.
