# WhatToDo — Current user, course and activity modeling

> Status: executable development specification; every task initially TODO. No task is implemented by this file.
> Task scope: one bounded AI execution per task or explicitly repeated instance.

[Development plan and execution rules](../DEVELOPMENT_PLAN.md) · [Live progress](../PROGRESS.md)

## Required sources

- [USER_MODEL_PLAN.md](../USER_MODEL_PLAN.md)
- [ALIGNMENT_PLAN.md](../ALIGNMENT_PLAN.md)
- [A0_USER_INTENT.md](../A0_USER_INTENT.md)

Read the source sections relevant to the chosen task, its completed prerequisite artifacts, and the shared Definition of Done before editing. Source documents control meaning; this catalog controls work decomposition. Proposed artifact paths below are logical scopes until M2-16 freezes the language-specific mapping. An adapter/schema described here does not yet exist.

## Gate: M1-09

Task order is constrained by explicit dependencies, not by credentials for unrelated live integrations. A VERIFY task runs the smallest meaningful fixture/integration set for its boundary and records actual evidence. Repeated tasks are one course/family/account/layout/playbook per execution; a template dependency means the required instance set described in the development plan.

## Tasks

### M1-01

**Collect the current-semester inventory**

- Type: `INFO`. Initial status: `TODO`.
- Prerequisites: None; begin with the accepted repository baseline.
- Deliverable / bounded file scope: profile intake record.
- Work: Ask one scoped inventory question for current courses and recurring non-course commitments; identify missing facts and authoritative user statements. Do not import remembered old-semester facts.
- Acceptance / failure and extension checks: Each named course/activity has a stable provisional ID and confirmation state; unknowns remain unknown. Accepted A0 defaults are not asked again.
- Completion evidence: artifact paths + exact targeted command/check or user-source reference + observed result + remaining limitations, recorded in PROGRESS. Do not mark done from code presence alone.

### M1-02

**Define a versioned stable profile format**

- Type: `SPEC`. Initial status: `TODO`.
- Prerequisites: [M1-01](M1_USER_COURSE_MODEL.md#m1-01)
- Deliverable / bounded file scope: profiles schema proposal and one synthetic example.
- Work: Define Course/Activity identity, context, axis units, TaskType references, provenance and version; separate stable profile fields from dynamic personal progress.
- Acceptance / failure and extension checks: A course without a primary importance scalar is valid; dynamic progress cannot be committed as a stable default; adding an activity type needs no planner-specific code.
- Completion evidence: artifact paths + exact targeted command/check or user-source reference + observed result + remaining limitations, recorded in PROGRESS. Do not mark done from code presence alone.

### M1-03

**Model one representative course**

- Type: `INFO`. Initial status: `TODO`.
- Prerequisites: [M1-02](M1_USER_COURSE_MODEL.md#m1-02)
- Deliverable / bounded file scope: one reviewed Course Profile.
- Work: Collect the chosen course’s task families, three difficulty dimensions, workload/session tendencies and actual workflow. Record source statements and unresolved course-specific facts.
- Acceptance / failure and extension checks: Every planning-relevant field maps to a user statement or an explicitly accepted default; profile review covers this one course only.
- Completion evidence: artifact paths + exact targeted command/check or user-source reference + observed result + remaining limitations, recorded in PROGRESS. Do not mark done from code presence alone.

### M1-04

**Model that course’s progress axis**

- Type: `SPEC`. Initial status: `TODO`.
- Prerequisites: [M1-03](M1_USER_COURSE_MODEL.md#m1-03)
- Deliverable / bounded file scope: one axis definition and example progress records.
- Work: Define the course’s units, ranges, teaching progress and task-family progress; include a hole/backlog example and exam-coverage reference.
- Acceptance / failure and extension checks: Teaching Unit 6 with unfinished Unit 5 work remains representable; a maximum completed unit cannot erase holes; unit semantics are not assumed to mean lectures.
- Completion evidence: artifact paths + exact targeted command/check or user-source reference + observed result + remaining limitations, recorded in PROGRESS. Do not mark done from code presence alone.

### M1-05

**Refine the reusable profile schema**

- Type: `SPEC`. Initial status: `TODO`.
- Prerequisites: [M1-04](M1_USER_COURSE_MODEL.md#m1-04)
- Deliverable / bounded file scope: revised stable schema and compatibility note.
- Work: Extract reusable fields from the representative course; define optional extensions and error reporting for missing required context. Preserve the original reviewed example.
- Acceptance / failure and extension checks: The example round-trips without loss; another course can use chapters or experiments through configuration; optional extension fields cannot alter accepted core semantics.
- Completion evidence: artifact paths + exact targeted command/check or user-source reference + observed result + remaining limitations, recorded in PROGRESS. Do not mark done from code presence alone.

### M1-06

**Model one additional course [repeat per course]**

- Type: `INFO`. Initial status: `TODO`.
- Prerequisites: [M1-05](M1_USER_COURSE_MODEL.md#m1-05)
- Deliverable / bounded file scope: one reviewed profiles/course_<id> instance.
- Work: Instantiate this task once per actual course; collect that course’s facts, progress-axis definition and TaskType references. Never process the whole semester in one execution.
- Acceptance / failure and extension checks: One course’s reviewed values and pending facts are recorded separately; another course’s settings are untouched; all required instances feed M1-09.
- Completion evidence: artifact paths + exact targeted command/check or user-source reference + observed result + remaining limitations, recorded in PROGRESS. Do not mark done from code presence alone.

### M1-07

**Model one recurring activity [repeat per activity]**

- Type: `INFO`. Initial status: `TODO`.
- Prerequisites: [M1-05](M1_USER_COURSE_MODEL.md#m1-05)
- Deliverable / bounded file scope: one reviewed profiles/activity_<id> instance.
- Work: Collect one sport, life or other commitment’s recurrence, occupancy/task distinction, flexible capacity and default task characteristics.
- Acceptance / failure and extension checks: A fixed training event is not double-counted as task effort; flexible activity obligations use ordinary Tasks; new activity categories need only profile/config additions.
- Completion evidence: artifact paths + exact targeted command/check or user-source reference + observed result + remaining limitations, recorded in PROGRESS. Do not mark done from code presence alone.

### M1-08

**Record remaining capacity preferences and exceptions**

- Type: `INFO`. Initial status: `TODO`.
- Prerequisites: [M1-03](M1_USER_COURSE_MODEL.md#m1-03)
- Deliverable / bounded file scope: reviewed user planning profile.
- Work: Collect missing waking/no-work windows, fixed routines, focus limits and real exceptions to accepted defaults; retain Beijing time, natural-day windows, reserve and output defaults.
- Acceptance / failure and extension checks: Missing availability is not invented; exception scope/version is explicit; preferences can change without changing Task schemas.
- Completion evidence: artifact paths + exact targeted command/check or user-source reference + observed result + remaining limitations, recorded in PROGRESS. Do not mark done from code presence alone.

### M1-09

**Close the M1 modeling gate**

- Type: `VERIFY`. Initial status: `TODO`.
- Prerequisites: [M1-06](M1_USER_COURSE_MODEL.md#m1-06) · [M1-07](M1_USER_COURSE_MODEL.md#m1-07) · [M1-08](M1_USER_COURSE_MODEL.md#m1-08)
- Deliverable / bounded file scope: reports/acceptance/M1.md.
- Work: Check the full confirmed current inventory, all required repeated profile instances, schema/examples and unresolved-field ledger. Distinguish a usable representative example from complete semester modeling.
- Acceptance / failure and extension checks: Every current course/activity is covered or explicitly marked blocked; no M1 completion claim while required facts are missing; evidence contains no credentials or unneeded personal raw content.
- Completion evidence: artifact paths + exact targeted command/check or user-source reference + observed result + remaining limitations, recorded in PROGRESS. Do not mark done from code presence alone.
