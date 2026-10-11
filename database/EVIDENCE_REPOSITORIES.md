# Source, candidate and pending evidence storage

M3A-08 adds [scope-bound PostgreSQL ingestion](../src/adapters/postgres_evidence.py)
over the existing [Source/Candidate contracts](../formats/input/SOURCE_CANDIDATE_CONTRACT.md).
It stores immutable source versions, proposals, field provenance, conflicts and
pending histories. Ingestion does not create or update canonical Tasks, grant
authority, write canonical audit or advance the store epoch.

## Admission and account scope

[Evidence values](../src/application/evidence_storage.py) use the existing codec
and domain SourceRecord/Candidate types. They retain exact wire bytes/hashes,
explicit source/capture times and nulls. Unsupported shapes, non-finite values,
control fields and finer-than-microsecond instants fail explicitly. Candidate
confidence and proposed integer facts retain exact decimal/integer values;
canonical fingerprinting does not round using ambient Decimal precision.

`SourceScope(provider, scope_ref, account_ref)` is trusted bootstrap configuration,
not an external approval flag. Registration requires the migration role and an
exact already-registered account cannot be retagged. The application role has
only SELECT on source_scope. Repository reads/writes additionally require a
configured matching provider/scope/account triple. Empty scope registries cannot
ingest or read existing evidence; their pending view is empty. Account references
are opaque references, not credentials. No account or provider is selected here.

Two accounts' identical external IDs stay distinct through their scope-bound
logical source IDs. Candidate source ID/record/hash references must match the
stored source; mapped target revisions must actually exist. Unknown mappings
stay null proposals. Ingestion accepts only PENDING review state, even when a
CONFIRMED input passes the wire schema or confidence is 1.0. Full source freshness,
user/rule authorization and review resolution remain later command/collector work.

## Immutable versions, replay and conflicts

Source replay retains the first captured bytes, capture time and raw locator.
A later capture timestamp alone is another observation of the same version,
not a new semantic source version. Changed content or external revision yields
a distinct retained version. Conflicting semantic metadata under a retained
record ID is stored separately, without overwriting the first source.

Candidate identity binds source version, parser version, action and mapped
target version. Replaying equivalent facts/confidence returns the retained
current review version without adding candidates/pending items or reopening a
resolved item. Changed parse facts under the same identity create a deduplicated
conflict with the original and observed hashes/bytes. A different parser or
source version can produce a distinct proposal. Scope/identity mismatches fail
before registration rather than remapping an existing identity.

Every proposed field stores an explicit `/proposed_fields/...` source pointer
and exact source ID/record/hash. Candidate reads verify the payload, normalized
row, source binding and complete field provenance projection. Missing original
bytes for old prototype rows are reported as legacy payload unavailable; they
are not guessed or silently upgraded.

The repository serializes imports under an evidence advisory lock, while the
schema-checked transaction holds its shared migration lock. Header, wire,
projection, provenance and OPEN pending registration commit together. A failure
after pending staging rolls back the entire ingestion. Conflict observations
retain their first diagnostic wire/time and reuse stable conflict/pending IDs.

## Deletion, raw content and pending history

The existing uniqueness of source_record prevented the domain's immutable
tombstone from retaining its prior content hash. The forward migration extends
the uniqueness key with state/deletion time and links each tombstone to its
prior record. Ingestion validates that prior metadata/hash/scope is preserved.
Identical deletion is a replay; contradictory deletion metadata is a retained
conflict. Neither event cancels or completes an accepted Task. A deleted version
cannot produce a new parser proposal; its existing candidate history remains
readable. Full provider reconciliation/restoration remains M4 work, not a live
collector implemented by this repository.

Raw provider content is separate from Source wire metadata and parsed facts:

| Raw storage state | Meaning |
| --- | --- |
| RETAINED | Exact bytes were supplied and their SHA-256 matches the source |
| EXTERNAL_REFERENCE | A locator/hash is known; bytes are not stored here |
| MINIMIZED | Previously retained bytes were cleared with a reason/time |

`minimize_raw` only clears locally retained bytes. It preserves source hash,
locator, metadata, candidate fields/provenance, conflicts and review history.
The native trigger permits only RETAINED to MINIMIZED, rejects resurrection or
identity/hash changes, and preserves the row. Replaying an old raw capture
cannot refill minimized bytes. A tombstone stores no new raw-content copy.
These checks use synthetic data only; no personal content was removed.

Pending identities reference either a candidate or conflict. Immutable pending
revisions separate OPEN from RESOLVED/REJECTED/SUPERSEDED; a mutable head advances
exactly one revision. Closed states require authority, resolution time and
canonical transaction references. Ingestion creates only OPEN version 1 and
never closes or reopens existing items. `pending_items` returns only current
OPEN rows in the configured account scopes. Trusted reviewed fixtures prove
later history remains readable on replay; a live review-resolution handler is
still a later card.

## Migration and verification

[008_evidence_storage.sql](runtime-migrations/008_evidence_storage.sql) is the
ninth pinned step, schema version `0.4.0-evidence-storage`. It adds ten tables
and eighteen FKs, including permanent candidate-origin validation on the
existing candidate_revision table. Current counts are 67 domain tables/162 FKs,
plus three runtime metadata tables. The first eight SQL sources are unchanged;
[M3A-07's eight-step manifest](../reports/acceptance/M3A-07-migration-plan.json)
and all earlier acceptance checkpoints remain preserved.

```powershell
.venv\Scripts\python.exe -m unittest tests.test_evidence_storage -q
.venv\Scripts\python.exe tools/verify_evidence_repository.py
.venv\Scripts\python.exe tools/verify_migrations.py
.venv\Scripts\python.exe tools/verify_package_install.py
```

[Focused tests](../tests/test_evidence_storage.py) exercise wire/domain admission,
source version distinctions, tombstones, exact numbers, deterministic hashes,
pending-only ingestion and scope registry checks. The native verifier creates
only owned disposable databases, compares sixteen canonical Task/authority/audit
tables before/after ingestion and checks deduplication, conflicts, scope
isolation, raw minimization, FK/immutability, reviewed replay, rollback and
fresh-connection reads. It also validates the eight-to-nine-step upgrade without
changing old migration receipts.

[M3A-08 acceptance](../reports/acceptance/M3A-08.json) archives actual native
results with separate current migration and clean offline package evidence.
Provider collectors, checkpoints, reviewed mutation handlers, live accounts
and production deployment remain separate planned work. Personal intake is
untouched and no canonical Task activation is inferred from stored evidence.
