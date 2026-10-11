# Bounded relationship graph validation

M3B-02 provides [the portable validation service](../src/application/relationship_validation.py)
over [M3B-01 stored rule/link values](RELATIONSHIP_STORAGE.md). It performs no
database I/O, clock reads, authority registration, mutation or target creation.
The frozen M2 helper/contract baseline and fourteen SQL steps are unchanged.

The caller supplies an immutable `GraphSnapshot` with explicitly selected
rule/link versions and independently resolved `EndpointFact` records. Each stage
fact names its permanent parent Task. Duplicate stable rule/link IDs, including
multiple selected versions, are rejected rather than picking the highest version.
An old instance's origin rule version need not be the currently selected rule:
editing generation does not rewrite that instance's accepted execution order.

Generation edges use exact source/target TaskType **ID and version**. Only active
rules participate. Hard order uses separate Task/stage START and FINISH events:
completion order is prerequisite FINISH to dependent FINISH; a start prerequisite
is prerequisite FINISH to dependent START. Every endpoint has its intrinsic
START-to-FINISH edge. Thus lab-to-preparation generation and
preparation-finish-before-lab coexist. No rule/type node enters the event graph.

Soft sequence remains a preference. Membership checks endpoint/parent identity,
multiple parents and duplicate memberships without introducing a hard order.
Tasks and stages retain distinct identities even if their text IDs match. Missing
endpoints/owners are diagnostics and never cause an endpoint or Task to be inferred.
Confirmed actual execution times remain untouched; this service validates graph
structure, not whether recorded events obeyed an order.

The service uses iterative strongly connected components and reports all rule or
link IDs internal to each genuinely cyclic component. Incoming/outgoing unrelated
branches are excluded. Generation recursion and hard order contradictions have
different diagnostic codes; neither graph is treated as the other. Conditional
recursive generation is not declared safe without a termination contract; the
supported finite scope is acyclic generation chains.

`GraphLimits` defaults and their meanings:

| Limit | Default | Meaning |
| --- | ---: | --- |
| max_rules | 2048 | Total selected rule records, including inactive ones |
| max_relations | 4096 | Total selected concrete links |
| max_endpoints | 4096 | Total resolved endpoint facts |
| max_payload_bytes | 8388608 | Combined canonical record/endpoint payload bytes |
| max_traversal_work | 250000 | Explicit record, node and edge visit units |
| max_generation_depth | 32 | Maximum generated edge count along a chain |
| max_generated_instances | 10000 | Maximum new Task/stage instances per initial source occurrence |

Limits must be positive integers; booleans and values above the service ceilings
are rejected. Count/byte failures stop before constructing graph adjacency and
return an incomplete result. Traversal stops at its exact allowed work count.
These are logical operation/resource limits, not wall-clock guarantees.

Generation work counts instances, not study time or effort budgets. Parallel
rules produce their own targets. Two paths converging on the same target type
still have different source occurrences and therefore distinct targets. Dynamic
programming computes this work without materializing a cascade; counts saturate
at the configured limit plus one. Saturated values are explicitly lower bounds.
A generated stage counts as creation work while continuing to share its parent
effort budget. Depth violations retain a precise longest-path rule witness.

The immutable result is VALID, INVALID or LIMIT_EXCEEDED, with deterministic
diagnostics, traversal count, generation metrics, metric exactness and traversal
completion flags. The input hash includes selected record hashes, endpoint
ownership and limits; shuffled input ordering has the same result. VALID certifies
only the supplied structural snapshot. It neither grants authorization nor proves
current state, canonical trigger evidence or an entire feasible schedule. The
enclosing transaction/worker must still resolve authority, select current rule
versions and revalidate state before committing generation or relationship edits.

Validation evidence:

```powershell
.venv/Scripts/python.exe -m unittest discover -s tests -p test_relationship_validation.py -v
.venv/Scripts/python.exe tools/run_ci.py
```

[Thirty-one focused methods](../tests/test_relationship_validation.py) include
120 independent transitive-closure graph cases, 30 explicit cascade enumeration
cases, a 1200-edge finite chain, reverse directions, mixed hard cycles, soft and
membership semantics, version/ownership identity, all limit families and
permutation-stable diagnostics. Clean installation additionally executes reverse,
true-cycle and traversal-limit cases without the optional PostgreSQL driver.
CI includes this module in the full suite and retains the existing persistence
regressions. All examples are synthetic. Canonical-event outbox and automatic
generation remain separate M3B-03 and later cards.
