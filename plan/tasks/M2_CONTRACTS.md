# WhatToDo — Concrete semantic contracts and implementation choices

> Status: executable development specification; every task initially TODO. No task is implemented by this file.
> Task scope: one bounded AI execution per task or explicitly repeated instance.

[Development plan and execution rules](../DEVELOPMENT_PLAN.md) · [Live progress](../PROGRESS.md)

## Required sources

- [DATA_MODEL_PLAN.md](../DATA_MODEL_PLAN.md)
- [IO_CONTRACT_PLAN.md](../IO_CONTRACT_PLAN.md)
- [TASK_RELATIONSHIP_PLAN.md](../TASK_RELATIONSHIP_PLAN.md)
- [PLANNER_PLAN.md](../PLANNER_PLAN.md)
- [SECURITY_PRIVACY_PLAN.md](../SECURITY_PRIVACY_PLAN.md)

Read the source sections relevant to the chosen task, its completed prerequisite artifacts, and the shared Definition of Done before editing. Source documents control meaning; this catalog controls work decomposition. Proposed artifact paths below are logical scopes until M2-16 freezes the language-specific mapping. An adapter/schema described here does not yet exist.

## Gate: M2-18

Task order is constrained by explicit dependencies, not by credentials for unrelated live integrations. A VERIFY task runs the smallest meaningful fixture/integration set for its boundary and records actual evidence. Repeated tasks are one course/family/account/layout/playbook per execution; a template dependency means the required instance set described in the development plan.

## Tasks

### M2-01

**Freeze core Task dimensions**

- Type: `SPEC`. Initial status: `TODO`.
- Prerequisites: [M1B-09](M1B_TASKTYPE_PRESETS.md#m1b-09)
- Deliverable / bounded file scope: formats/input/task.schema and examples.
- Work: Define versioned Task identity, acceptance, binary completion, disposition, trust/overdue metadata, importance and three difficulty dimensions. Give valid/invalid examples.
- Acceptance / failure and extension checks: No single status enum conflates acceptance, progress and expiry; REQUIRED/OPTIONAL/EXPIRING remain exactly the accepted requiredness vocabulary.
- Completion evidence: artifact paths + exact targeted command/check or user-source reference + observed result + remaining limitations, recorded in PROGRESS. Do not mark done from code presence alone.

### M2-02

**Freeze effort, stages and work observations**

- Type: `SPEC`. Initial status: `TODO`.
- Prerequisites: [M2-01](M2_CONTRACTS.md#m2-01)
- Deliverable / bounded file scope: effort/stage/session schemas.
- Work: Define canonical user U, model remaining-work prediction, effective B, weights, actual effort and observation/verification times; encode parent/stage accounting and truthful rework.
- Acceptance / failure and extension checks: U=4 and B=6 yields 6, not 10 forecast hours; stages partition B; actual time does not mechanically decrement U or imply completion.
- Completion evidence: artifact paths + exact targeted command/check or user-source reference + observed result + remaining limitations, recorded in PROGRESS. Do not mark done from code presence alone.

### M2-03

**Freeze source and candidate contracts**

- Type: `SPEC`. Initial status: `TODO`.
- Prerequisites: [M2-01](M2_CONTRACTS.md#m2-01)
- Deliverable / bounded file scope: source/candidate schemas.
- Work: Define provenance, source hashes/IDs, parser versions, conflicts, confidence and pending acceptance; preserve raw evidence versus canonical facts.
- Acceptance / failure and extension checks: A high-confidence submission produces a completion candidate, not COMPLETE; a source deletion does not cancel its accepted Task.
- Completion evidence: artifact paths + exact targeted command/check or user-source reference + observed result + remaining limitations, recorded in PROGRESS. Do not mark done from code presence alone.

### M2-04

**Freeze command and authorization envelope**

- Type: `SPEC`. Initial status: `TODO`.
- Prerequisites: [M2-01](M2_CONTRACTS.md#m2-01) · [M2-03](M2_CONTRACTS.md#m2-03)
- Deliverable / bounded file scope: formats/input/command.schema and authority matrix.
- Work: Define command ID, principal/origin, resolved targets, expected version, exact authorized fields, batch membership and approval/rule reference.
- Acceptance / failure and extension checks: An explicit user command needs no duplicate approval; inferred extra updates stay pending; external content cannot mint a principal or authorization reference.
- Completion evidence: artifact paths + exact targeted command/check or user-source reference + observed result + remaining limitations, recorded in PROGRESS. Do not mark done from code presence alone.

### M2-05

**Freeze review and unchanged-estimate batch contracts**

- Type: `SPEC`. Initial status: `TODO`.
- Prerequisites: [M2-02](M2_CONTRACTS.md#m2-02) · [M2-04](M2_CONTRACTS.md#m2-04)
- Deliverable / bounded file scope: review/questionnaire/batch schemas.
- Work: Define full pending-queue presentation, worked-on individual updates, untouched unchanged batches, per-Task verification and partial-review status.
- Acceptance / failure and extension checks: Silence and missing initial estimates do not confirm anything; a partial answer never becomes a completed normal review; original estimate observation time is retained.
- Completion evidence: artifact paths + exact targeted command/check or user-source reference + observed result + remaining limitations, recorded in PROGRESS. Do not mark done from code presence alone.

### M2-06

**Freeze typed relationship objects**

- Type: `SPEC`. Initial status: `TODO`.
- Prerequisites: [M2-01](M2_CONTRACTS.md#m2-01) · [M2-04](M2_CONTRACTS.md#m2-04)
- Deliverable / bounded file scope: rule/relation/occurrence schemas.
- Work: Define generation, completion/start order, soft sequence and membership separately; stable rule identity, version, field mapping and occurrence key.
- Acceptance / failure and extension checks: The generation/order reverse pair is not a false cycle; genuine recursive generation and hard-order contradiction are diagnosable; changing rule version does not duplicate old targets.
- Completion evidence: artifact paths + exact targeted command/check or user-source reference + observed result + remaining limitations, recorded in PROGRESS. Do not mark done from code presence alone.

### M2-07

**Freeze expiration and notification process contracts**

- Type: `SPEC`. Initial status: `TODO`.
- Prerequisites: [M2-04](M2_CONTRACTS.md#m2-04)
- Deliverable / bounded file scope: expiration-notice and dispatch-result schemas.
- Work: Define detected condition, pending notice, confirmed/failed/unknown delivery, post-notice version revalidation and retained transition history. Select no delivery provider yet.
- Acceptance / failure and extension checks: Unsent queue entries are not “informed”; no new acknowledgement is required; ambiguous delivery or stale state does not authorize EXPIRED.
- Completion evidence: artifact paths + exact targeted command/check or user-source reference + observed result + remaining limitations, recorded in PROGRESS. Do not mark done from code presence alone.

### M2-08

**Freeze events, occupancy and time contracts**

- Type: `SPEC`. Initial status: `TODO`.
- Prerequisites: [M2-01](M2_CONTRACTS.md#m2-01)
- Deliverable / bounded file scope: event/availability schemas and date fixtures.
- Work: Define source event ownership, exact instant versus date-only, Asia/Shanghai 23:59 defaults, recurrence concepts and finite availability windows. Include stable preference constraints versus dynamic scoped today-only locks with complete/advance meaning and next-midnight expiry.
- Acceptance / failure and extension checks: Explicit source times survive normalization; today-lock expiry is next midnight; natural-day bounds include today and elapsed capacity is excluded.
- Completion evidence: artifact paths + exact targeted command/check or user-source reference + observed result + remaining limitations, recorded in PROGRESS. Do not mark done from code presence alone.

### M2-09

**Freeze generic Goal and Exam contracts**

- Type: `SPEC`. Initial status: `TODO`.
- Prerequisites: [M2-01](M2_CONTRACTS.md#m2-01) · [M2-06](M2_CONTRACTS.md#m2-06)
- Deliverable / bounded file scope: goal/milestone/exam/onboarding schemas.
- Work: Define target, workload/measure, target date, cadence, phases and progress; Exam is an independent fixed event; generated work uses ordinary Tasks and accepted rule scope.
- Acceptance / failure and extension checks: Goal configuration is not itself Task completion; milestones do not create a parallel workload total; missing generation mappings remain pending.
- Completion evidence: artifact paths + exact targeted command/check or user-source reference + observed result + remaining limitations, recorded in PROGRESS. Do not mark done from code presence alone.

### M2-10

**Freeze Plan and forecast output contracts**

- Type: `SPEC`. Initial status: `TODO`.
- Prerequisites: [M2-02](M2_CONTRACTS.md#m2-02) · [M2-06](M2_CONTRACTS.md#m2-06) · [M2-08](M2_CONTRACTS.md#m2-08)
- Deliverable / bounded file scope: formats/output/plan.schema and fixtures.
- Work: Define snapshot/version, B/source, C/R/S, natural-day bounds, data-quality state, solver outcome, plan role versus requiredness and provisional/final emergency flags.
- Acceptance / failure and extension checks: Unknown/stale input is distinct from SAFE/DANGER/EMERGENCY; overlapping forecasts are not summed; display does not count repeated fragment references twice.
- Completion evidence: artifact paths + exact targeted command/check or user-source reference + observed result + remaining limitations, recorded in PROGRESS. Do not mark done from code presence alone.

### M2-11

**Freeze AI-job and learning-result contracts**

- Type: `SPEC`. Initial status: `TODO`.
- Prerequisites: [M2-02](M2_CONTRACTS.md#m2-02) · [M2-04](M2_CONTRACTS.md#m2-04)
- Deliverable / bounded file scope: AIJob/prediction/behavior-rule schemas.
- Work: Define manual export/import, validation state, model metadata and versioned numeric predictions versus candidate reviewed behavioral policy.
- Acceptance / failure and extension checks: Predictions cannot overwrite canonical U or preferences; a valid schema/model confidence alone cannot grant write authority.
- Completion evidence: artifact paths + exact targeted command/check or user-source reference + observed result + remaining limitations, recorded in PROGRESS. Do not mark done from code presence alone.

### M2-12

**Define ports and module ownership**

- Type: `SPEC`. Initial status: `TODO`.
- Prerequisites: [M2-03](M2_CONTRACTS.md#m2-03) · [M2-07](M2_CONTRACTS.md#m2-07) · [M2-08](M2_CONTRACTS.md#m2-08) · [M2-10](M2_CONTRACTS.md#m2-10)
- Deliverable / bounded file scope: application ports and error taxonomy.
- Work: Specify StateStore, Clock, CalendarSource, EvidenceSource, NotificationSink, Predictor, Solver and Renderer requests/results; typed retryable/permanent/conflict/unknown outcomes.
- Acceptance / failure and extension checks: Fake adapters can satisfy the same contracts as live providers; domain code has no provider SDK, credential or n8n-node dependencies; new adapters do not change Task semantics.
- Completion evidence: artifact paths + exact targeted command/check or user-source reference + observed result + remaining limitations, recorded in PROGRESS. Do not mark done from code presence alone.

### M2-13

**Build semantic fixture catalog**

- Type: `SPEC`. Initial status: `TODO`.
- Prerequisites: [M2-05](M2_CONTRACTS.md#m2-05) · [M2-09](M2_CONTRACTS.md#m2-09) · [M2-10](M2_CONTRACTS.md#m2-10) · [M2-11](M2_CONTRACTS.md#m2-11)
- Deliverable / bounded file scope: tests/fixtures/semantic and requirement map.
- Work: Create synthetic positive/negative fixtures for each accepted boundary and core workflow; preserve a decision-to-fixture mapping independent of implementation.
- Acceptance / failure and extension checks: Contains U<B/U>B, hard window infeasibility, notice failure, batch scope, reverse relationship graphs and natural-day rollover; fixtures contain no current private user data.
- Completion evidence: artifact paths + exact targeted command/check or user-source reference + observed result + remaining limitations, recorded in PROGRESS. Do not mark done from code presence alone.

### M2-14

**Design PostgreSQL ownership and constraints**

- Type: `SPEC`. Initial status: `TODO`.
- Prerequisites: [M2-12](M2_CONTRACTS.md#m2-12) · [M2-13](M2_CONTRACTS.md#m2-13)
- Deliverable / bounded file scope: schema design and migration sequence.
- Work: Map frozen contracts to separate aggregate tables/logs, foreign keys, uniqueness/version constraints, outbox/checkpoints and semantic history retention; stage migrations into small batches.
- Acceptance / failure and extension checks: Exactly one occurrence per source/rule/role is enforceable in PostgreSQL; audit and state share transactions; no JSON-only design evades referential/version checks.
- Completion evidence: artifact paths + exact targeted command/check or user-source reference + observed result + remaining limitations, recorded in PROGRESS. Do not mark done from code presence alone.

### M2-15

**Choose prototype delivery and access contract**

- Type: `SPEC`. Initial status: `TODO`.
- Prerequisites: [M2-04](M2_CONTRACTS.md#m2-04) · [M2-07](M2_CONTRACTS.md#m2-07) · [M2-12](M2_CONTRACTS.md#m2-12)
- Deliverable / bounded file scope: prototype transport/channel/access ADR.
- Work: Resolve one prototype review/brief/notification surface and authenticated caller path using user needs; choose service auth/scopes without selecting unrelated email providers.
- Acceptance / failure and extension checks: Human normal input is natural language/guided responses, not hand-written JSON; test channel exists; real channel choice is a scoped user checkpoint; no unauthenticated mutation endpoint.
- Completion evidence: artifact paths + exact targeted command/check or user-source reference + observed result + remaining limitations, recorded in PROGRESS. Do not mark done from code presence alone.

### M2-16

**Select one implementation toolchain**

- Type: `SPIKE`. Initial status: `TODO`.
- Prerequisites: [M2-12](M2_CONTRACTS.md#m2-12) · [M2-14](M2_CONTRACTS.md#m2-14)
- Deliverable / bounded file scope: technical ADR and reproducible toolchain manifest.
- Work: Bound the comparison to Python versus TypeScript unless a blocker is evidenced; test date arithmetic, schema validation, PostgreSQL transactions and a fake port. Pin supported versions and map logical paths to real files.
- Acceptance / failure and extension checks: A clean machine runs one command for targeted checks; language/versions are explicit engineering choices, not invented user preferences; SDK-specific code remains behind adapters.
- Completion evidence: artifact paths + exact targeted command/check or user-source reference + observed result + remaining limitations, recorded in PROGRESS. Do not mark done from code presence alone.

### M2-17

**Check all contracts together**

- Type: `VERIFY`. Initial status: `TODO`.
- Prerequisites: [M2-15](M2_CONTRACTS.md#m2-15) · [M2-16](M2_CONTRACTS.md#m2-16)
- Deliverable / bounded file scope: contract consistency and evolution report.
- Work: Walk one morning/evening scenario, one generation+order case, one expiration case and one generic Goal through schemas/ports; define additive versus breaking version behavior.
- Acceptance / failure and extension checks: No field carries incompatible meanings across contracts; old-version input is either explicitly adapted or rejected with reason; no silent accepted-data loss.
- Completion evidence: artifact paths + exact targeted command/check or user-source reference + observed result + remaining limitations, recorded in PROGRESS. Do not mark done from code presence alone.

### M2-18

**Close the M2 contract gate**

- Type: `VERIFY`. Initial status: `TODO`.
- Prerequisites: [M2-17](M2_CONTRACTS.md#m2-17)
- Deliverable / bounded file scope: reports/acceptance/M2.md.
- Work: Freeze core schema versions, output baseline, selected toolchain/path mapping and critical assumptions. Required unresolved semantics block affected coding; provider credentials do not block fake adapters.
- Acceptance / failure and extension checks: M1/M1B facts and M2 contracts are demonstrably usable before M3; planned artifacts are not claimed implemented; every later code task has stable input/output ownership.
- Completion evidence: artifact paths + exact targeted command/check or user-source reference + observed result + remaining limitations, recorded in PROGRESS. Do not mark done from code presence alone.
