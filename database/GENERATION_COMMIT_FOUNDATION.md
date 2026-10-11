# Composite generation foundation — M3B-05.a

This child prepares the data and SQL boundary required by M3B-05. At this foundation checkpoint the parent remained IN_PROGRESS.
[M3B-05.b scoped runtime](GENERATION_RUNTIME.md) now executes and verifies actual
generation; the parent is DONE. This preparer still confers no mutation authority.

## Composite preparation

[The portable preparer](../src/application/generation_commit.py) re-evaluates
one pinned canonical source and selected accepted rule rather than trusting an
arbitrary supplied target draft. It derives stable occurrence/target/link IDs
from the source creation event, stable rule ID and role. Rule version remains
audit metadata, and a CREATED occurrence replays its original target without
reconstruction. A pending/failed occurrence can advance under a newly accepted
version, retaining its original source identity and prior immutable payload.

Each plan has one ordinary exact-fingerprint `CommitRequest`, a detached receipt
and a matching audit change for every Task, concrete relation and occurrence
effect. IDs/fingerprints change with actual revision/epoch/provenance, while
correlation remains attempt metadata. Preparation produces a permit reference,
never a `TransactionPermit`, authority record, SQL write or worker action.

Missing facts produce an occurrence-only PENDING plan. A closed-parent conflict
can produce an occurrence-only FAILED plan. A separate target produces its
admitted Task aggregate; a stage updates its supplied current parent and shares
that obligation's budget. Supporting estimate observations cite the intended
derived transaction authority, while their original evidence remains in the
mapping manifest. The [scoped handler](GENERATION_RUNTIME.md) resolves that authority independently.

Generation links source and target through the occurrence itself. It does not
invent execution order. An optional accepted template `relation` object has
exactly `kind` and `direction`: COMPLETION_ORDER, START_PREREQUISITE or
SOFT_SEQUENCE with SOURCE_TO_TARGET/TARGET_TO_SOURCE for separate Tasks.
The explicit STAGE obligation entails SOURCE_TO_TARGET STAGE_MEMBERSHIP.
Reverse prerequisite order therefore remains independent of creation direction.
Malformed/extra/incompatible relation specs fail before any effect is written.
This extends the internal template consumer; frozen base wire contracts remain
unchanged.

## Original and derived source authorization

The actual manual creation path retains the original user grant in Task
acceptance, and an exact derivative permit in the creation receipt/event.
[GenerationSource](../src/application/generation_evaluator.py) now retains the
immutable creation authorization annotation when those references differ.
It checks the annotated original grant, principal and explicit creation target,
or a rule-created target's generation annotation. Snapshot ID/revision/byte hash
still must match the event. These are trusted repository bindings, not a public
input authority envelope. M3B-05.b must fetch the actual referenced authority
row and independently verify its source/account/grant chain before committing.

## Additive occurrence storage

[Migration 015](runtime-migrations/015_generation_occurrences.sql) adds immutable
`generation_occurrence_revision` rows and typed metadata to the existing head.
The head's existing business-key uniqueness excludes rule version. Exact foreign
keys bind the original event/Task revision/creation transaction, accepted rule
version/role, target identity/stage, optional relation and exact audited receipt.
Typed JSON must equal the corresponding normalized columns and missing-facts
list; the deferred head/history guard requires the whole head snapshot to match
its immutable revision.

A generated nullable history key gives typed heads a real history FK while
leaving legacy unadmitted heads intact, without invented history or authority.
History writes advance from the current head by one revision and preserve
source/role/obligation identity. Typed CREATED heads are terminal. Pending and
failed heads may advance under a new exact accepted version. Legacy rows cannot
be silently converted to the typed runtime. UPDATE/DELETE/TRUNCATE of history
are rejected, and application TRUNCATE privilege remains absent.

The schema is `0.11.0-generation-occurrences`, sixteen steps, 77 domain tables,
193 foreign keys and three metadata tables. The prior fifteen SQL files are
unchanged. This migration does not run generation or backfill old Tasks.

## Scoped verification and next work

[Sixteen focused methods](../tests/test_generation_commit.py) cover stable
identities, source/rule/version scope, pending and failure effects, separate and
stage changes, explicit reverse order, exact receipt/audit reconstruction,
observation lineage and replay. Existing evaluator methods remain regressions.
Installed-package smoke executes composite preparation and receipt reconstruction
without the optional database driver.

[The native verifier](../tools/verify_generation_foundation.py) constructs a
source through the actual manual creation handler, with real original/derivative
authority records. It then probes eleven schema boundaries, including migration
preservation, exact source revision, missing/mismatched history, metadata rollback,
target FK, pending-to-created version history, terminal state and immutability.
Its metadata-only SQL fixtures refer to separately user-created synthetic targets;
they are deliberately not proof of an automatic generation transaction.

M3B-05.b now implements application-role scoped lookup, current active rule/root
authority and graph checks, re-evaluation, independent exact permits, original
receipt replay and atomic target/stage/link/occurrence/provenance/audit/epoch
publication. Actual concurrent generation, precommit disconnect and lost-commit
acknowledgement recovery now pass in [the runtime acceptance](../reports/acceptance/M3B-05b.json).
Parent M3B-05 is DONE; delivery/cascade orchestration remains M3B-06.
No live worker or personal activation is provided by this child.
