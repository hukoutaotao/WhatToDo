# Source and candidate contracts — development draft 0.1.0

Scope: [M2-03.a](../../plan/tasks/M2_CONTRACTS.md#m2-03a). [Source schema](source.schema.json), [candidate schema](candidate.schema.json), [pure helpers](../../src/domain/provenance.py), [20 synthetic schema cases](../../tests/fixtures/sources/cases.json) and [focused tests](../../tests/test_provenance.py).

## Evidence identity

SourceRecord preserves source type, provider, scope, external ID/revision, exact-byte SHA-256 hash, source timestamp when known, capture timestamp and present/deleted metadata. Logical source identity includes provider/scope/external ID; the same external ID in two scopes is distinct. Record identity includes the exact content hash and external revision, so changed content remains distinguishable. Raw content is not embedded in this record or logged by these helpers.

Source deletion is an immutable tombstone with the prior content hash retained. It neither cancels an accepted Task nor removes candidate/history. Repeated identical deletion is idempotent; contradictory deletion metadata is diagnosed. Actual source storage/reconciliation and provider field mapping remain adapter/application work.

## Proposals are not accepted facts

`make_candidate` always constructs PENDING, including confidence 1.0 and explicit external submission evidence. Parsed actions can propose creation, updates, completion or cancellation; unknown target mapping stays null/pending. Proposed facts have a closed field vocabulary; principal, acceptance, authority and review control fields cannot be supplied as task facts. Deadline text here remains unresolved raw evidence rather than a guessed timestamp.

Candidate review state is separate from Task completion. The schema can retain CONFIRMED/REJECTED review history with authority/time references and a canonical Task link where applicable; the factory/ingestion helper cannot perform those reviews or mint canonical Tasks. A syntactically valid reference is not a grant of authority. The future command/reference/version layer must resolve and authorize actual writes.

Candidates store canonical JSON for proposed facts and return copies to callers, so mutating a parsed input or returned nested dictionary cannot rewrite history. Identity binds source record/hash, parser version, action and target revision. Replaying identical evidence keeps the existing candidate and its review result. Changed facts/confidence under the same source/parser identity raise a conflict; changed content, parser version or target revision produces a distinguishable proposal. Persistent uniqueness/version rules remain PostgreSQL/application work.

## Run and handoff

```powershell
python -m unittest discover -s tests -p 'test_*.py' -v
python -m tools.check_contracts --examples tests/fixtures/sources/cases.json
python -m tools.check_contracts --contract candidate path/to/candidate.json
```

Schema checks validate structure, including dates and review-reference presence; they do not prove reference existence, authority or delivery. Typed helpers validate identities/times/replay and conservative pending construction. Parsers must validate emitted proposed fields with the bundled candidate schema before application handoff. Generic provider/scope strings support another source through configuration rather than course/provider branches. No live provider/account, scraping, actual Task import or persistence is exercised by these synthetic checks.
