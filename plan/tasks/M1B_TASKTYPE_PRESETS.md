# WhatToDo — TaskType, decomposition and relationship presets

> Status: executable development specification; every task initially TODO. No task is implemented by this file.
> Task scope: one bounded AI execution per task or explicitly repeated instance.

[Development plan and execution rules](../DEVELOPMENT_PLAN.md) · [Live progress](../PROGRESS.md)

## Required sources

- [USER_MODEL_PLAN.md](../USER_MODEL_PLAN.md)
- [TASK_RELATIONSHIP_PLAN.md](../TASK_RELATIONSHIP_PLAN.md)
- [DATA_MODEL_PLAN.md](../DATA_MODEL_PLAN.md)

Read the source sections relevant to the chosen task, its completed prerequisite artifacts, and the shared Definition of Done before editing. Source documents control meaning; this catalog controls work decomposition. Proposed artifact paths below are logical scopes until M2-16 freezes the language-specific mapping. An adapter/schema described here does not yet exist.

## Gate: M1B-09

Task order is constrained by explicit dependencies, not by credentials for unrelated live integrations. A VERIFY task runs the smallest meaningful fixture/integration set for its boundary and records actual evidence. Repeated tasks are one course/family/account/layout/playbook per execution; a template dependency means the required instance set described in the development plan.

## Tasks

### M1B-01

**Collect one representative task-family workflow [repeat]**

- Type: `INFO`. Initial status: `TODO`.
- Prerequisites: [M1-09](M1_USER_COURSE_MODEL.md#m1-09)
- Deliverable / bounded file scope: one course/task-family intake record.
- Work: For one TaskType, collect concrete stages, useful session sizes, fragmentability, importance/requiredness defaults and dependencies; split further if the course has multiple unrelated families.
- Acceptance / failure and extension checks: One example can be executed conceptually without vague “work on course” instructions; no generic start-N-days-early field is added.
- Completion evidence: artifact paths + exact targeted command/check or user-source reference + observed result + remaining limitations, recorded in PROGRESS. Do not mark done from code presence alone.

### M1B-02

**Define TaskType and template identity/version rules**

- Type: `SPEC`. Initial status: `TODO`.
- Prerequisites: [M1B-01](M1B_TASKTYPE_PRESETS.md#m1b-01)
- Deliverable / bounded file scope: TaskType/template semantic contract.
- Work: Define stable IDs, defaults, override provenance and immutable historical versions; choose how a new workflow becomes a distinct type versus a variant.
- Acceptance / failure and extension checks: Changing defaults does not rewrite old accepted Tasks; a new type is registered through data/schema rather than hard-coded course branches.
- Completion evidence: artifact paths + exact targeted command/check or user-source reference + observed result + remaining limitations, recorded in PROGRESS. Do not mark done from code presence alone.

### M1B-03

**Define one decomposition preset [repeat]**

- Type: `SPEC`. Initial status: `TODO`.
- Prerequisites: [M1B-02](M1B_TASKTYPE_PRESETS.md#m1b-02)
- Deliverable / bounded file scope: one reviewed stage template.
- Work: Write one family’s concrete stage objectives, stage order, weights and minimum useful sessions; identify indivisible work and parent deadline ownership.
- Acceptance / failure and extension checks: Stages share one parent obligation; generated separate obligations are explicitly distinct; stage weights never become invented user estimates.
- Completion evidence: artifact paths + exact targeted command/check or user-source reference + observed result + remaining limitations, recorded in PROGRESS. Do not mark done from code presence alone.

### M1B-04

**Resolve one automatic-generation relationship [repeat]**

- Type: `INFO`. Initial status: `TODO`.
- Prerequisites: [M1B-03](M1B_TASKTYPE_PRESETS.md#m1b-03)
- Deliverable / bounded file scope: one accepted RelationshipRule mapping.
- Work: Resolve trigger, source/target type, mapped facts/defaults, separate-task versus stage meaning and bounded authorization. Creation of Task 1 is not completion of Task 1.
- Acceptance / failure and extension checks: The target’s essential facts are available or pending; approving a template alone is not blanket creation permission; cancellation/reopen propagation is not silently assumed.
- Completion evidence: artifact paths + exact targeted command/check or user-source reference + observed result + remaining limitations, recorded in PROGRESS. Do not mark done from code presence alone.

### M1B-05

**Define hard order and soft sequence examples**

- Type: `SPEC`. Initial status: `TODO`.
- Prerequisites: [M1B-03](M1B_TASKTYPE_PRESETS.md#m1b-03)
- Deliverable / bounded file scope: typed order fixtures.
- Work: Define finish-before-finish, explicit finish-before-start and bypassable soft sequence for the representative families; include a generation direction opposite to execution order.
- Acceptance / failure and extension checks: Task 1 generates Task 2 while Task 2 finishes first is valid; finish-before-finish alone does not block Task 1’s start.
- Completion evidence: artifact paths + exact targeted command/check or user-source reference + observed result + remaining limitations, recorded in PROGRESS. Do not mark done from code presence alone.

### M1B-06

**Define initial conditional review patterns**

- Type: `SPEC`. Initial status: `TODO`.
- Prerequisites: [M1B-04](M1B_TASKTYPE_PRESETS.md#m1b-04) · [M1B-05](M1B_TASKTYPE_PRESETS.md#m1b-05)
- Deliverable / bounded file scope: review/catch-up trigger presets.
- Work: Specify the accepted three missed post-class-note trigger and exam-preparation phase trigger with IDs, scope and candidate/authorized-generation treatment.
- Acceptance / failure and extension checks: Older-unit backlog is visible; repeated detections do not produce new duplicate obligations; conditions without accepted generation scope remain candidates.
- Completion evidence: artifact paths + exact targeted command/check or user-source reference + observed result + remaining limitations, recorded in PROGRESS. Do not mark done from code presence alone.

### M1B-07

**Complete one remaining preset [repeat]**

- Type: `SPEC`. Initial status: `TODO`.
- Prerequisites: [M1B-03](M1B_TASKTYPE_PRESETS.md#m1b-03) · [M1B-04](M1B_TASKTYPE_PRESETS.md#m1b-04) · [M1B-05](M1B_TASKTYPE_PRESETS.md#m1b-05)
- Deliverable / bounded file scope: one additional reviewed TaskType preset.
- Work: Apply the reusable format to one remaining task family; capture exceptions and relationship defaults without cloning course-specific code.
- Acceptance / failure and extension checks: Each normal type has one stable default decomposition or an explicit no-split choice; custom variants preserve inherited-field provenance.
- Completion evidence: artifact paths + exact targeted command/check or user-source reference + observed result + remaining limitations, recorded in PROGRESS. Do not mark done from code presence alone.

### M1B-08

**Check preset compatibility and accounting**

- Type: `VERIFY`. Initial status: `TODO`.
- Prerequisites: [M1B-06](M1B_TASKTYPE_PRESETS.md#m1b-06) · [M1B-07](M1B_TASKTYPE_PRESETS.md#m1b-07)
- Deliverable / bounded file scope: preset fixture report.
- Work: Validate all required repeated instances with split/no-split, override, separate counterpart, soft bypass and rework examples. Reconcile only material contradictions.
- Acceptance / failure and extension checks: Each obligation’s work is counted once; missing facts stay pending; no stage completion alone proves the parent complete.
- Completion evidence: artifact paths + exact targeted command/check or user-source reference + observed result + remaining limitations, recorded in PROGRESS. Do not mark done from code presence alone.

### M1B-09

**Close the M1B preset gate**

- Type: `VERIFY`. Initial status: `TODO`.
- Prerequisites: [M1B-08](M1B_TASKTYPE_PRESETS.md#m1b-08)
- Deliverable / bounded file scope: reports/acceptance/M1B.md.
- Work: Confirm preset coverage, type-extension rules, typed relationships and user-authorized mapping scope. List schema decisions to carry into M2.
- Acceptance / failure and extension checks: No real preset is activated without its required review; all acceptance examples are linked to accepted sources rather than AI assumptions. D-080 permits independent generic contract/offline code development with synthetic presets while personal intake is deferred; this exception does not complete M1B or authorize real counterpart generation.
- Completion evidence: artifact paths + exact targeted command/check or user-source reference + observed result + remaining limitations, recorded in PROGRESS. Do not mark done from code presence alone.
