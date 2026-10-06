# WhatToDo — Task Relationship System

> Execution: [detailed development plan](DEVELOPMENT_PLAN.md) · [live progress](PROGRESS.md).
> Bounded work: [M1B_TASKTYPE_PRESETS](tasks/M1B_TASKTYPE_PRESETS.md) · [M2_CONTRACTS](tasks/M2_CONTRACTS.md) · [M3_RELATIONSHIPS_REVIEWS](tasks/M3_RELATIONSHIPS_REVIEWS.md) · [M6_PLANNER_DAILY_MVP](tasks/M6_PLANNER_DAILY_MVP.md).

> Status: accepted product direction; conceptual specification only, not implemented.
> Source: user's 2026-10-06 answer to experience question 1.
> Authority: A0_USER_INTENT.md §60 and DECISIONS D-071/D-072.
> Dependencies: USER_MODEL_PLAN, DATA_MODEL_PLAN, IO_CONTRACT_PLAN, PLANNER_PLAN, DEVELOPMENT_PLAN, TESTING_PLAN.

## 1. Purpose and Accepted Examples

The user explicitly requested a system for adding relationships between Tasks, including:

- creating Task 1 automatically creates a corresponding Task 2;
- Task 2 must be completed before Task 1 is completed.

Relationships are first-class structured rules/links, not comments that the Planner may ignore. They may be configured for a concrete pair of Tasks or as a reusable TaskType/template pattern whose instances are linked explicitly. Courses, activities, Goals, and conditional work can use the same relationship mechanism.

## 2. Distinct Relationship Semantics

| Kind | Meaning | Effect |
| --- | --- | --- |
| Generation rule | On canonical creation of Task 1, instantiate a corresponding Task 2 under the approved mapping/template. | Event-driven creation; not evidence that either Task is complete. |
| Completion order | Task 2 must finish before Task 1 finishes. | Hard constraint on planned completion order. Task 1 may start earlier unless an additional start prerequisite is specified. |
| Start prerequisite | Task 2 must finish before Task 1 starts, when explicitly configured. | Stronger existing hard-dependency concept; do not infer it from completion order alone. |
| Soft sequence | A preferred order, such as notes before homework, where the accepted course rule allows bypass. | Preference with visible exceptions under REQUIRED-feasibility pressure. |
| Parent/stage membership | A stage is part of one parent obligation. | Shared effort accounting; distinct from generating a separate obligation. |

The first two rows are the user's new minimum requirement. The remaining rows integrate already accepted dependency/decomposition semantics; the system need not expose technical type names to the user. More relationship types can be added later only with defined meaning.

Example: creating a “lab experiment” Task can generate its “preparation report” Task. A separate completion/start relation encodes what must happen first. Generation direction and execution order need not match: Task 1 → generate Task 2 can coexist with Task 2 → finish before Task 1. Treating both edges as one graph would incorrectly flag this valid combination as a cycle.

## 3. Configuration and Authority

Configure a reusable rule in natural language, then resolve and validate its trigger, source/target identity or TaskType, target template/field mappings, relationship kind, scope, and active version. The user's explicit instruction/acceptance authorizes that exact rule.

Execution of an approved automatic-generation rule does not ask for identical per-instance confirmation again. This is a bounded exception to the general review policy: authorization comes from the approved rule, not model confidence. Unknown external task-like content still becomes a candidate until accepted; relation execution starts from the source Task's canonical creation, not from raw email/page discovery.

A template's defaults alone are not blanket automation permission. Recurring/Goal/conditional generators may activate canonical Tasks automatically only where an explicit accepted generation rule covers the trigger and target mapping. Otherwise the existing candidate/review path applies. This interpretation closes O01 within the scope the user actually requested without granting unrelated authority.

Missing or conflicting essential target facts stay pending rather than being invented. Inheriting accepted TaskType defaults needs no repeated field-by-field confirmation. Rule-created Tasks retain the origin rule, source Task, template/version, field provenance, and authorization reference.

## 4. Data Responsibilities

Conceptual entities:

- RelationshipRule: stable/reusable rule definition, trigger, target template/mapping, allowed creation scope, version, active state, user acceptance provenance.
- TaskRelation: concrete typed link between resolved Task/stage IDs, with direction, hard/soft semantics, applicable trigger/ordering endpoints, rule origin, and audit/version.
- GenerationOccurrence: source occurrence → rule → target linkage, deduplication key, processing/result state, and failures/pending facts.

Stable rule/template configuration may live in versioned declarative memory. Concrete links/occurrences and runtime state belong in PostgreSQL. No SQL schema or directory format is frozen here. Relation changes are versioned and do not silently rewrite accepted historical Tasks.

A generated Task 2 is a separate obligation unless explicitly configured as a stage of Task 1. Separate obligations have separate remaining effort and are counted once each; stages share their parent's planning budget. Always distinguish this during rule setup.

## 5. Execution and Reliability

1. Persist the source Task's authorized canonical creation and an event/outbox record.
2. Resolve the active accepted relationship rules for that source occurrence.
3. Validate scope, target facts, graph constraints, rule version, and deduplication.
4. Create/link the target Task and record provenance/audit under the rule's authorization, or persist a pending item if essential facts are unresolved.
5. Feed all resulting accepted Tasks/relations into Planner and replan when material.

Use an occurrence key based on source Task ID + stable rule ID + target role/occurrence identity. Replaying the same creation event or changing a rule version must not accidentally create duplicate counterpart Tasks. Version is recorded for audit; applying a newly edited rule retroactively needs explicit scope, not automatic recreation of old instances.

Check creation cascades and hard ordering separately. Disallow uncontrolled recursive generation and contradictory hard-order cycles; report the precise offending rule/link. Approved finite chains may run automatically. A creation cascade plus reverse execution order is not automatically a cycle across the distinct graphs.

Deleting/cancelling/reopening a source Task does not automatically delete/cancel/recreate its target without an explicit propagation rule. A completed source is not proof that its counterpart is complete. Relation rules never bypass the external-completion confirmation boundary.

## 6. Planner and Actual-Fact Handling

Planner consumes concrete typed relations and eligible generated Tasks. Protect required prerequisite/ordered work needed to make a REQUIRED obligation feasible; account for each obligation/stage correctly. Do not bypass an explicit hard relation because a Task is important or today-locked; show the conflict if impossible.

For completion order, constrain target finish before source finish; for a start prerequisite, constrain prerequisite finish before dependent start. Preserve the distinction. A Task can already exist while blocked/unready; do not hide it or misclassify it as nonexistent.

If the user reports that real work finished out of order, record the truthful confirmed completion and flag the violated relationship. Do not reject reality, fabricate earlier completion times, or pretend the prerequisite was completed. The constraint governs future recommendations and violation reporting, not authority to falsify history.

## 7. User Interaction and Output

Accept commands such as “When creating this kind of Task, create its preparation Task too” and “Task B must finish before Task A.” Ask only for unresolved meanings/IDs or essential field mappings. Present a short interpretation when useful.

Normal Daily Brief stays concise. Show relationship details only when they explain why work is recommended, is blocked, or is at risk. Rule-generated items can carry a short origin label; do not create a redundant confirmation queue for fully authorized rule execution.

## 8. Development and Acceptance

- M1/M1B collect representative course/TaskType relationship patterns alongside decomposition.
- M2 defines typed relationship commands/objects, authorization, generation mappings, deduplication, and hard/soft semantics before persistence.
- M3 implements minimal relationship persistence/validation and approved canonical-creation → counterpart generation within the persistent-state prototype.
- M5B integrates real Goal/recurring/conditional generation through the same bounded mechanism.
- M6 Planner enforces ordering and includes relationship-generated workload in feasibility/brief output.
- Later n8n workflows orchestrate portable application/domain logic; no second workflow platform is introduced.

Planned acceptance examples: Task 1 creation produces exactly one Task 2 across retries; unaccepted external evidence triggers no canonical cascade; generated counterparts use approved field/default mappings; missing essential facts remain pending; generation/ordering direction differ without false cycle detection; true recursion/ordering conflicts are reported; completion-before-start and completion-before-completion behave differently; stage vs separate Task effort is not double-counted; confirmed real violations are recorded honestly; cancellation does not silently propagate.

No relationship code, database, workflow, or runtime behavior is implemented by this document update.

---

## Detailed Execution Mapping

Typed contracts M2-06; persistence/validation/generation M3B-01–07; Planner order M6-09; retries/reverse graphs/violations are acceptance cases.
