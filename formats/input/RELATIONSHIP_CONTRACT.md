# Typed relationships — development draft 0.1.0

Scope: [M2-06.a](../../plan/tasks/M2_CONTRACTS.md#m2-06a). Development schemas: [rules](relationship-rule.schema.json), [concrete relations](task-relation.schema.json) and [occurrences](generation-occurrence.schema.json). Implementation: [pure helpers](../../src/domain/relationships.py); evidence: [synthetic cases](../../tests/fixtures/relationships/cases.json), [tests](../../tests/test_relationships.py).

## Separate meanings and graphs

Generation rules describe canonical source creation, accepted mapping provenance, source/target types, versioned target template, target role and SEPARATE_TASK versus STAGE meaning. Concrete links separately describe completion order, start prerequisites, soft sequence or Task-to-stage membership. Typed endpoint identity distinguishes a Task from a stage even when their text IDs match. A stage may have one parent; links never create a second effort budget.

`check_relationships` checks active generation type graphs and hard execution event graphs separately. Completion order connects prerequisite FINISH to dependent FINISH. Start prerequisite connects prerequisite FINISH to dependent START; intrinsic START-to-FINISH edges catch contradictions across the two kinds. Soft preferences do not become hard constraints. Canonical creation A-to-B and hard order B-before-A coexist without a false cycle. Diagnostics retain every offending rule/link in a cyclic component. Unresolved concrete endpoints and multiple stage parents are explicit issues.

The static generation check supports acyclic finite type chains; recursive type rules are diagnosed conservatively. Conditional recursion, bounded recursive scopes, nested stage decomposition and Planner penalties are outside this draft. Iterative traversal handles long finite chains without relying on Python recursion depth.

## Mapping, occurrence identity and authority

Each immutable field binding explicitly uses SOURCE, a version-bound DEFAULT or LITERAL. Only listed fields are copied; absent essential facts remain PENDING. Resolved mapping values must satisfy typed creation-field checks and cannot infer COMPLETE or CANCELLED. Template/ref/version/role/type scope and independent canonical creation evidence must match. No source deletion, cancellation, reopening or reported completion triggers generation here.

`resolve_generation` returns a proposal, pending facts, a replay result or a scope diagnostic. Accepted-provenance strings are metadata, not authority. An independently resolved rule grant and trusted caller still have to pass [authorization](COMMAND_AUTHORITY_CONTRACT.md). Full Task identity/context/type/default validation and per-field provenance persistence remain integration work.

Occurrence keys reuse `RuleScope.generation_key`: stable rule ID, source Task ID, target role and occurrence identity; rule version stays audit metadata. A recorded CREATED occurrence wins across retries and rule edits, retaining its original target and version. Changing its obligation kind reports conflict. Pending facts can be resolved again without creating a Task in memory. PostgreSQL uniqueness, replay transactions, event/outbox handling and retroactive rule-edit authority remain future responsibilities.

## Ordering evidence and handoff

`check_execution_order` compares timezone-aware recorded or proposed times. A prerequisite can finish exactly at a dependent start/finish boundary. Completion order permits an earlier dependent start; start prerequisite does not. Missing prerequisite completion evidence and real out-of-order completion return issues without rewriting or rejecting actual facts. This checker reports relationships, rather than certifying an entire feasible schedule.

```powershell
python -m unittest discover -s tests -p 'test_relationships.py' -v
python -m tools.check_contracts --examples tests/fixtures/relationships/cases.json
```

All examples are synthetic. No personal generation rules, persistent targets, real calendar schedule or live notification are created by these checks.
