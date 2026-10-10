# Generic Task aggregate development contract

Scope: [M2-01.b](../../plan/tasks/M2_CONTRACTS.md#m2-01b). [Schema](task-aggregate.schema.json), [semantic value](../../src/domain/task_aggregate.py), [admission](../../src/application/task_aggregate.py), [examples](../../tests/fixtures/task_aggregate/cases.json), [tests](../../tests/test_task_aggregate.py) and [executed native report](../../reports/acceptance/M2-01b.json).

The aggregate composes three existing contracts without changing their versions or contents. [Bundle generation](../../tools/render_task_aggregate_schema.py) rewrites their local fragment pointers into the aggregate's local definitions; drift checking detects a changed source or bundle. `task-aggregate` and `0.1.0-draft` are an explicit new contract identity, not an automatic upgrade of historical Task-core or course-profile inputs.

## Snapshot fields

| Field | Meaning |
| --- | --- |
| core | Existing independent Task identity/revision, context/type, acceptance, completion/disposition, requiredness, ratings and derived metadata. |
| effort | Existing user U, derived prediction and stages. Identity/revision/completion/disposition must agree with core. A stale prediction remains in the snapshot but cannot supply B. |
| timing.created_at / completed_at | Explicit known timestamps or null. Retrospective history may lack dates. An incomplete current Task cannot claim a current completion timestamp; old completion belongs to immutable history. Complete does not invent a timestamp. |
| timing.release | Explicit source instant, original offset/text and source reference, or null. Release does not inherit a date-only deadline's 23:59 policy. Equivalent offsets are preserved. |
| timing.deadline | Stable due reference and the existing normalized-due record, or null. Date-only due uses Beijing 23:59; explicit instants retain their original meaning. |
| work.total_estimate | Original total estimate, observed time and source, or null. USER_REPORT is distinct from TEMPLATE_DEFAULT with an explicit versioned TASKTYPE/TASK_TEMPLATE definition. It is neither current U nor model B nor actual work. |
| work.minimum_session_seconds / fragmentable | Positive integer seconds and explicit boolean, each nullable when unknown. Unknown is not zero or a scheduling permission. Actual short finishing-block policy remains Planner work. |
| stage_details | Exactly the effort stages' IDs, individual revisions and concrete titles; stages still share one parent obligation. Duplicate/missing/extra members fail. |
| provenance | Source references for explicit JSON Pointer facts. Pointers must resolve to existing facts; duplicate field claims, invalid escapes, missing facts and self/version provenance fail. Source existence/authority remains separate. |

Core and effort retain their exact authored fields on roundtrip. Completed stages may retain old estimates without adding them to the parent budget. Cancelled/expired incomplete Tasks retain U/history; inactive work is excluded from selection rather than rewritten to a zero estimate. Completing a parent still requires user authority and U=0. Time spent and template estimates never mechanically update U.

Times in the composed Python value use explicit RFC3339 offsets at microsecond-or-coarser precision. Unsupported finer precision is rejected with retained source bytes, avoiding silent datetime truncation. Canonical integer fields reject alternate float encodings rather than silently changing them. Original total may be below current U. A reversed/zero release-to-due interval remains an explicit fact with `REVERSED`/`ZERO_WIDTH` window metadata; retaining facts does not prove placement feasibility or SAFE. Relationship graphs and actual-observation history remain separately owned contracts, not duplicated workload inside this aggregate.

## Admission and authority

`admit_task` first checks exact version/shape, then cross-field semantics. `CONSISTENT_FACTS` yields an immutable, detached aggregate. All outcomes retain the wire admission's original bytes/hash. This does not resolve actual source/type/due/stage references, prove a delivered expiry notice, authenticate a caller, create a transaction permit or write a Task. A regression attempts to commit admitted facts without an independently trusted permit and verifies no state/audit change.

`TaskAggregate.from_record` requires independently shape-checked input; domain semantics do not import the schema SDK or adapters. The application consumes a codec protocol. Budget/stage methods reuse the existing exact effort helpers and return derived selections; they never replace stored facts.

## Relational boundary and evidence

The [design](../../database/design/relational.json) now adds append-only `task_details_revision` and `task_field_provenance`. Detail records bind Task ID/revision/completion through a composite foreign key. Release/total/provenance source references and total-definition kind/ID/version are relationally bound. Null total/source/definition pairs and positive/unknown session constraints are explicit. A 300-character title exposed the older SQL reference-width mismatch; Task titles now use checked text matching the core's 500-character bound. Existing 29 wire schemas remain unchanged.

The current native report verifies 51 tables, 130 foreign keys, 14 foundation negative probes, six transaction/reconciliation checks and 14 additional aggregate checks. Those additional checks include 11 negative probes and rollback. The regression run passed 300 methods, including 17 aggregate methods. Twenty-two new shape cases make 258 total; the 236 historical shape cases remain separately counted.

Original native SQL remains in [M2-16.a checkpoint](../../reports/acceptance/M2-16a-baseline/migrations/002_task_effort_review.sql), matching its old 49-table/124-FK report. The [29-contract registry checkpoint](../../reports/acceptance/M2-17a-registry.json) preserves that report's original hash. These are historical evidence, not current schema validation.

No application repository, full trusted command pipeline, production migration runner, real course generation, provider or deployment is claimed. Fresh native instances use synthetic fixtures and are stopped after verification. Once a generic migration baseline is frozen/applied, future structural changes must use a new migration rather than rewrite the applied batches.

```powershell
.venv\Scripts\python.exe tools/render_task_aggregate_schema.py --check
.venv\Scripts\python.exe -m unittest tests.test_task_aggregate -q
.venv\Scripts\python.exe -m tools.check_contracts --examples tests/fixtures/task_aggregate/cases.json
.venv\Scripts\python.exe -m tools.verify_toolchain
```
