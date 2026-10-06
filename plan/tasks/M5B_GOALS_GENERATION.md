# WhatToDo — Goal, Exam and recurring work activation

> Status: executable development specification; every task initially TODO. No task is implemented by this file.
> Task scope: one bounded AI execution per task or explicitly repeated instance.

[Development plan and execution rules](../DEVELOPMENT_PLAN.md) · [Live progress](../PROGRESS.md)

## Required sources

- [USER_MODEL_PLAN.md](../USER_MODEL_PLAN.md)
- [IO_CONTRACT_PLAN.md](../IO_CONTRACT_PLAN.md)
- [TASK_RELATIONSHIP_PLAN.md](../TASK_RELATIONSHIP_PLAN.md)
- [PLANNER_PLAN.md](../PLANNER_PLAN.md)

Read the source sections relevant to the chosen task, its completed prerequisite artifacts, and the shared Definition of Done before editing. Source documents control meaning; this catalog controls work decomposition. Proposed artifact paths below are logical scopes until M2-16 freezes the language-specific mapping. An adapter/schema described here does not yet exist.

## Gate: M5B-11

Task order is constrained by explicit dependencies, not by credentials for unrelated live integrations. A VERIFY task runs the smallest meaningful fixture/integration set for its boundary and records actual evidence. Repeated tasks are one course/family/account/layout/playbook per execution; a template dependency means the required instance set described in the development plan.

## Tasks

### M5B-01

**Onboard one actual Goal [repeat per Goal]**

- Type: `INFO`. Initial status: `TODO`.
- Prerequisites: [M2-18](M2_CONTRACTS.md#m2-18)
- Deliverable / bounded file scope: one reviewed Goal intake/profile.
- Work: Collect target/outcome, workload/measure, target date, cadence, milestones/phases and progress; resolve unknowns using the generic contract.
- Acceptance / failure and extension checks: A Goal cannot be fully activated with invented target/workload; accepted configuration and generated Task activation are distinct; no broad A0 re-questioning.
- Completion evidence: artifact paths + exact targeted command/check or user-source reference + observed result + remaining limitations, recorded in PROGRESS. Do not mark done from code presence alone.

### M5B-02

**Persist Goal, Milestone and Exam records**

- Type: `DEV`. Initial status: `TODO`.
- Prerequisites: [M3B-16](M3_RELATIONSHIPS_REVIEWS.md#m3b-16) · [M2-09](M2_CONTRACTS.md#m2-09)
- Deliverable / bounded file scope: Goal/Milestone/Exam repositories and migration.
- Work: Implement generic accepted configurations, dynamic progress and independent Exam events; link course-axis coverage without additional workload totals.
- Acceptance / failure and extension checks: Deleting external exam evidence does not cancel accepted preparation Tasks; persistence retains prior versions; goal effort is not added on top of its Tasks.
- Completion evidence: artifact paths + exact targeted command/check or user-source reference + observed result + remaining limitations, recorded in PROGRESS. Do not mark done from code presence alone.

### M5B-03

**Implement one Goal onboarding command flow**

- Type: `DEV`. Initial status: `TODO`.
- Prerequisites: [M5B-02](M5B_GOALS_GENERATION.md#m5b-02) · [M5B-01](M5B_GOALS_GENERATION.md#m5b-01)
- Deliverable / bounded file scope: Goal review/create/update coordinator.
- Work: Guide one Goal through target resolution and existing authorization/review handlers; produce accepted rule mappings or pending facts.
- Acceptance / failure and extension checks: Natural user descriptions map to structured state; partial answers stay pending; one explicit reviewed statement does not require redundant approval.
- Completion evidence: artifact paths + exact targeted command/check or user-source reference + observed result + remaining limitations, recorded in PROGRESS. Do not mark done from code presence alone.

### M5B-04

**Implement finite occurrence generation windows**

- Type: `DEV`. Initial status: `TODO`.
- Prerequisites: [M5B-02](M5B_GOALS_GENERATION.md#m5b-02) · [M3B-05](M3_RELATIONSHIPS_REVIEWS.md#m3b-05)
- Deliverable / bounded file scope: recurrence/occurrence window service.
- Work: Define bounded date ranges and stable recurrence occurrence identity for accepted recurring/Goal rules; persist horizon/cursor and missed-occurrence policy.
- Acceptance / failure and extension checks: Restart/timezone rollover does not generate duplicates; unbounded/infinite expansion is prevented; past missed work is not mechanically cloned into today.
- Completion evidence: artifact paths + exact targeted command/check or user-source reference + observed result + remaining limitations, recorded in PROGRESS. Do not mark done from code presence alone.

### M5B-05

**Implement one Goal-to-Task generator [repeat per pattern]**

- Type: `DEV`. Initial status: `TODO`.
- Prerequisites: [M5B-03](M5B_GOALS_GENERATION.md#m5b-03) · [M5B-04](M5B_GOALS_GENERATION.md#m5b-04)
- Deliverable / bounded file scope: one mapped Goal generator.
- Work: Create ordinary Tasks under exact accepted generation rules, otherwise candidates; distribute cadence/phase work with explicit fields and provenance.
- Acceptance / failure and extension checks: No special scheduling privilege comes from Goal origin; missing essential target values stay pending; old rule versions do not retroactively rewrite tasks.
- Completion evidence: artifact paths + exact targeted command/check or user-source reference + observed result + remaining limitations, recorded in PROGRESS. Do not mark done from code presence alone.

### M5B-06

**Implement Exam preparation phase generation**

- Type: `DEV`. Initial status: `TODO`.
- Prerequisites: [M5B-04](M5B_GOALS_GENERATION.md#m5b-04) · [M1B-06](M1B_TASKTYPE_PRESETS.md#m1b-06)
- Deliverable / bounded file scope: Exam preparation rule evaluator.
- Work: Use the independent Exam date/coverage and accepted preparation phase mapping to generate/review work via the same occurrence service.
- Acceptance / failure and extension checks: Exam event is occupancy/context, not duplicate Task workload; changed exam information becomes the appropriate reviewed update; repeated phase detection is idempotent.
- Completion evidence: artifact paths + exact targeted command/check or user-source reference + observed result + remaining limitations, recorded in PROGRESS. Do not mark done from code presence alone.

### M5B-07

**Implement missed-notes conditional review generation**

- Type: `DEV`. Initial status: `TODO`.
- Prerequisites: [M5B-04](M5B_GOALS_GENERATION.md#m5b-04) · [M1B-06](M1B_TASKTYPE_PRESETS.md#m1b-06)
- Deliverable / bounded file scope: conditional review evaluator.
- Work: Detect three consecutive missed post-class-note occurrences using real course units/accepted outcomes; route accepted mappings versus candidates correctly.
- Acceptance / failure and extension checks: Unknown progress is not classified as three misses; replay yields one logical catch-up occurrence; detection cannot fabricate Task completion.
- Completion evidence: artifact paths + exact targeted command/check or user-source reference + observed result + remaining limitations, recorded in PROGRESS. Do not mark done from code presence alone.

### M5B-08

**Implement backlog and milestone read models**

- Type: `DEV`. Initial status: `TODO`.
- Prerequisites: [M5B-05](M5B_GOALS_GENERATION.md#m5b-05) · [M5B-06](M5B_GOALS_GENERATION.md#m5b-06) · [M5B-07](M5B_GOALS_GENERATION.md#m5b-07)
- Deliverable / bounded file scope: Goal pacing/course backlog queries.
- Work: Summarize older-unit holes, Goal pacing, generated-work provenance and milestone progress from canonical state.
- Acceptance / failure and extension checks: Unit 5 holes remain visible after teaching reaches Unit 6; aggregate progress does not count parent/stages/generated copies twice; estimates retain source.
- Completion evidence: artifact paths + exact targeted command/check or user-source reference + observed result + remaining limitations, recorded in PROGRESS. Do not mark done from code presence alone.

### M5B-09

**Expose generated work to Planner snapshots**

- Type: `DEV`. Initial status: `TODO`.
- Prerequisites: [M5B-08](M5B_GOALS_GENERATION.md#m5b-08) · [M3A-17](M3_STATE_FOUNDATION.md#m3a-17)
- Deliverable / bounded file scope: ordinary Task snapshot projection.
- Work: Use one shared Task/relationship interface for course, Goal, recurring and conditional work; provide finite generation coverage/uncertainty metadata.
- Acceptance / failure and extension checks: Planner requires no separate Goal workload store; ungenerated coverage gaps cannot be hidden as complete future workload; origins add explanations without special priority.
- Completion evidence: artifact paths + exact targeted command/check or user-source reference + observed result + remaining limitations, recorded in PROGRESS. Do not mark done from code presence alone.

### M5B-10

**Run Goal/Exam generation and restart fixtures**

- Type: `VERIFY`. Initial status: `TODO`.
- Prerequisites: [M5B-09](M5B_GOALS_GENERATION.md#m5b-09)
- Deliverable / bounded file scope: goal/conditional generation fixtures.
- Work: Exercise one Goal, phase change, missed-note trigger, generation replay, canceled source and unknown mapping across process restarts.
- Acceptance / failure and extension checks: No duplicate obligation or unapproved propagation; finite window and history survive updates; same Planner interface handles all origins.
- Completion evidence: artifact paths + exact targeted command/check or user-source reference + observed result + remaining limitations, recorded in PROGRESS. Do not mark done from code presence alone.

### M5B-11

**Close Goal activation contract gate**

- Type: `VERIFY`. Initial status: `TODO`.
- Prerequisites: [M5B-10](M5B_GOALS_GENERATION.md#m5b-10)
- Deliverable / bounded file scope: reports/acceptance/M5B.md.
- Work: Verify generic configuration/generation/pacing contracts and record each real Goal’s onboarding readiness separately.
- Acceptance / failure and extension checks: M6 fixtures need no invented real Goal; production activation of a specific Goal requires its reviewed M5B-01 instance and accepted mappings.
- Completion evidence: artifact paths + exact targeted command/check or user-source reference + observed result + remaining limitations, recorded in PROGRESS. Do not mark done from code presence alone.
