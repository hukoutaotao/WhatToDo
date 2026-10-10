# Offline cross-contract admission and evolution

Evidence scope: `M2-17.a`, synthetic development baseline, **not a real activation release**. Its [29-contract checkpoint](../../reports/acceptance/M2-17a-registry.json) retains the originally verified schema hashes. The [current registry](../contract-registry.json) now additionally registers the [Task aggregate](TASK_AGGREGATE_CONTRACT.md), resolving 30 schemas, consumer files and [relational owners](../../database/design/ownership.json). [Live progress](../../plan/PROGRESS.md) controls task status.

## Admission

[ContractJSONCodec](../../src/adapters/contract_json.py) admits immutable UTF-8 bytes against an independently supplied, detached snapshot of checked-in schemas. Supported inputs have exactly `0.1.0-draft`. Unknown contracts, missing/unsupported versions, malformed/duplicate-key/nonfinite JSON and invalid shapes are rejected with reason. Inputs larger than 262144 bytes are rejected before parsing. All outcomes retain exact source bytes and SHA-256, including rejected historical input; this in-memory retention does not implement persistent source storage.

There is no legacy converter. Existing course-profile snapshots are not covered by these 29 wire contracts and cannot be promoted to current Task data by this codec. Optional fields obey each schema's policy; strict unknown fields are rejected rather than discarded. Payload access returns a fresh parsed object. Error diagnostics expose paths/constraints, without instance values. Offline schemas resolve local fragment references only.

`SUPPORTED_SHAPE` means version and shape support. Domain references, canonical creation, independently authenticated callers, grants and transaction permits still need their own checks. Admission has no boolean truth value and does not mutate state. The external-command regression demonstrates that supported command JSON is denied canonical authority.

## Evolution and downstream evidence

[Evolution assessment](../../src/application/contract_versions.py) is a conservative structural check, not a general schema inclusion prover. It requires explicit consumer identities. Identical validation structure may retain compatibility after prose changes. Property names and literal `const`/`enum`/`default` data are preserved even when their names resemble annotation keywords. Default changes require review.

For a bounded, satisfiable object language (strict additional properties, primitive property types, no references or cross-field constraints), adding an optional field accepts prior input but produces input strict old consumers reject. Requiring an existing optional field rejects some old input. Both require a version bump and invalidate named consumer evidence. A reference-free identity change also invalidates consumers. Reference changes, changed dialects, conditions, constrained/unsatisfiable additions and other complex changes return `REVIEW_REQUIRED` with unknown compatibility directions. The checks deliberately avoid proving these cases from appearance alone.

An assessment names affected consumers; it does not update a schema, registry, database or migration automatically. Registry drift fails the next admission setup until explicitly reviewed. Supported wire versions are separate from the database migration IDs and human-intake revision numbers.

## Composed evidence

[Five independent expectations](../../tests/fixtures/contracts/cross_scenarios.json) are executed by [scenario helpers](../../tests/contract_scenarios.py) and [runner](../../tools/check_cross_contracts.py):

| Workflow | Checked behavior |
| --- | --- |
| Morning | Model B may be below user U; three horizons are not added; an ADVANCE lock does not imply completion; stored U is retained. |
| Evening | Explicit remaining replaces U; actual increment is separate; unchanged verification retains original observation; candidate rejection remains explicit. |
| Generation/order | Accepted fixture rule generates one separate obligation; graph/order scopes stay separate; replay adds no second audit entry or duplicated effort. |
| Expiration | Delivered notice and current evidence precede authorization; expiration retains incomplete status and U; Task/effort revisions and states agree. |
| Goal | Measured progress above target does not complete a Task or change its effort; no configured generation rules means candidate-only generation. |

The five workflows validate 31 wire records. Fixture grants, solver evidence, callers and transaction permits are independently seeded; this does not implement an authority-to-commit service or actual solver. StateStore/notification paths use fakes. No real user Task, provider, calendar, application PostgreSQL adapter or deployment is involved. Existing native PostgreSQL spike evidence remains separate.

```powershell
.venv\Scripts\python.exe tools/check_contract_registry.py
.venv\Scripts\python.exe tools/check_cross_contracts.py
.venv\Scripts\python.exe -m unittest tests.test_contract_versions -q
```

[Focused regressions](../../tests/test_contract_versions.py) include the existing 236 positive/negative shape expectations, exact version rejection, byte retention, authority separation, drift, conservative evolution, independent scenario expectations and Task/effort scope mismatch. Rechecking 236 existing cases does not add new shape cases to that count. The five workflows are additional to the older 11 semantic scenarios; neither collection constitutes full release acceptance.
