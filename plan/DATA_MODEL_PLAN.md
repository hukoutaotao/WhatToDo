# WhatToDo — Data Model Planning

> Conceptual model only. Exact PostgreSQL DDL is intentionally deferred until Phase 2.
> Prerequisite: Alignment Gate A0 establishes information-granularity and semantic-boundary rules before this model is frozen.

## 1. Storage Ownership

### Git-versioned declarative knowledge
Best for relatively stable, human/AI-readable knowledge:
- Course profiles
- Activity profiles
- Preferences
- Routines
- Planning rules and accepted RelationshipRule templates
- Goal templates
- Configuration

### PostgreSQL dynamic state
Best for changing operational truth:
- Tasks and concrete typed TaskRelation / GenerationOccurrence records
- Deadlines
- Status/progress
- Events
- Goals/milestones state
- Source records
- Sync state
- Plans
- Work sessions
- AI jobs
- Audit/history

### External systems
External systems remain authoritative for their own raw facts:
- Calendar provider: source event
- Email provider: source message
- Learning platform: source announcement/assignment

WhatToDo stores normalized representations plus provenance.

---

## 2. Core Conceptual Entities

### Domain
Top-level category: study, exercise, life administration, other.

### Course / ActivityProfile
Describes semantic/grouping context and stable defaults:
- name
- domain
- typical task types
- instructional/course progress axis where applicable
- duration tendencies
- timing patterns
- recurring patterns
- review/task-generation rules

Course-level planner importance is intentionally not primary; priority lives on Tasks/Goals/Exams/generated work.

### Task
Concrete actionable obligation.

Primary parent-task completion semantics:
- COMPLETE
- INCOMPLETE

Partial work does not require a third completion state; it is represented through accumulated effort, remaining effort, and optional child-stage progress.

Must eventually support:
- stable ID
- title
- domain/course relation
- task type
- source/provenance
- release time
- deadline
- estimated total effort
- estimated remaining effort
- progress
- thinking depth
- repetitive volume
- new-learning load
- minimum useful continuous session
- fragmentability
- dependencies / parent-stage relation where needed
- requiredness: REQUIRED / OPTIONAL / EXPIRING
- expiration point for EXPIRING tasks
- importance: integer 1–5
- status
- verification/confidence

### TaskType / TaskTemplate

TaskType classifies a workflow and supplies defaults. TaskTemplate describes its decomposition/generation pattern. They may share a physical representation later, but neither is a concrete accepted Task.

Templates generate or describe recurring task patterns.

A normal task type should generally map to a stable decomposition template.

Template concepts may include:
- stage/subtask structure
- default 1–5 thinking depth / repetitive volume / new-learning load
- default importance/requiredness where appropriate
- inherited difficulty dimensions
- default total-effort range
- minimum useful session
- fragmentability
- dependency/order between stages

If an unusual workflow is substantially different, prefer defining a new task type/template rather than silently altering the ordinary one.

Example:
- Pre-lab report for Electronic Circuits.

### RelationshipRule / TaskRelation / GenerationOccurrence
Accepted reusable generation/ordering rules, concrete typed links, and idempotent source-to-target execution records. See TASK_RELATIONSHIP_PLAN.md. Generation links and hard completion/start order use separate graphs; parent/stage links share effort, generated separate Tasks do not.

### ExpirationNotice
Tracks condition detection, user-facing notice delivery, state version, and subsequent EXPIRED transition. Pending delivery is evidence/process state, not completed notification or Task completion.

### Goal
Long-horizon desired outcome.

### Milestone
Intermediate checkpoint for a Goal.

### Event
Time occupancy.

Kinds:
- fixed external event
- flexible planned work block
- optional reminder representation

### CourseProgressPosition / CourseProgressRange
Semantic position on a course's instructional axis.

Derived backlog logic should be able to detect older Unit-linked Tasks that remain incomplete after teaching/task-family progress moves ahead.

Each course may define what one progress unit means (lecture, chapter, experiment, topic, etc.).

Separate:
- teaching progress on the axis;
- per-task-family completion progress along the same axis.

Examples:
- before lesson 5
- lesson 5
- after lesson 5
- lessons 1–8

Used by:
- preview/note/homework tasks
- task prerequisites
- conditional review activation
- exam coverage

### Exam
Independent fixed academic event/object, not a normal Task.

May reference:
- course
- date/time
- CourseProgressRange coverage
- later exam metadata

Review work is generated as Tasks/Goals related to the Exam.

### Routine
Recurring expected activity not necessarily a task instance.

### Constraint
Hard or soft scheduling/planning restriction.

Examples:
- class cannot move
- no high-cognitive work after a certain hour
- lab task needs at least 90 minutes
- today-only user Task lock that expires at end of day

Temporary overrides should carry an expiry/scope so one-day instructions do not silently become persistent preferences.

### SourceRecord
Immutable or append-oriented provenance for raw/normalized facts.

Potential metadata:
- source type
- source ID
- source timestamp
- ingestion timestamp
- content hash
- parser version
- linked entity IDs
- confidence

### WorkSession
Actual or planned period of working on a task.

Useful for:
- duration calibration
- schedule history
- actual-vs-estimated analysis
- cumulative actual effort
- evidence about when work started relative to release/deadline

### Plan
Structured daily/weekly/long-term plan snapshot. Record source-state version, forecast inputs, recommendations, and provisional/final status where needed. A planned session is not evidence that work occurred.

### AIJob
Structured unit of AI-assisted work.

### StateChange / AuditRecord
Records meaningful changes and their actor/source.

### PendingConfirmation / UncertainCandidate
Represents proposed facts/changes awaiting acceptance. Even high-confidence external Task discoveries and completion signals belong here: pending acceptance is an authority boundary, not merely low confidence.

Examples:
- ambiguous deadline extraction
- possible completion inferred from an external signal
- conflicting source facts
- uncertain task mapping

Must support batching into the next normal user interaction.

### EffortHistory / EstimationObservation
Historical evidence for improving future duration estimates and feeding `LEARNING_PLAN.md`.

Estimate provenance should distinguish at least:
- user-confirmed/canonical remaining-effort estimate;
- model-derived remaining-effort prediction and selected effective planning budget (D-074);
- timestamp/version of the observation.

Model disagreement may create risk information but does not overwrite the user's canonical estimate.

Should distinguish:
- estimated effort
- actual effort
- course/task type
- relevant difficulty/session characteristics
- estimation error
- release-to-first-work delay
- release-to-completion delay
- postponement observations
- available-capacity context when delay occurred

Exact physical table structure is deferred.

---

## 3. Task Acceptance and Completion Semantics

Separate **candidate acceptance** from **task completion**.

Before canonical creation:

```text
CANDIDATE
   ↓ user confirms or an accepted generation relationship authorizes its mapped instance
CANONICAL TASK
```

Candidate-side outcomes may include:
- CONFIRMED / accepted into canonical state
- REJECTED
- CONFLICTED / pending clarification

Once a canonical parent Task exists, its primary completion state is:

```text
INCOMPLETE
   ↓ final completion
COMPLETE
```

A task may have substantial work already invested and still remain INCOMPLETE.

For EXPIRING tasks, expiration may end the task's usefulness without implying successful completion.

Represent "has started" through execution/history facts such as:
- WorkSession records
- cumulative actual effort
- completed child stages/subtasks
- first-work timestamp

Do not require an IN_PROGRESS completion state for the parent task.

Other lifecycle/disposition concepts include:
- CANCELLED
- EXPIRED / no longer relevant
- OVERDUE risk metadata

Child stages/subtasks may transition from completed back to incomplete/reopened when rework is discovered.

Historical outcomes and state transitions must be retained. Normal COMPLETE/CANCELLED/EXPIRED history should not be hard-deleted; deletion/merge is mainly for erroneous records, duplicates, or explicit policy/privacy removal.

---

## 4. Trust and Provenance

Separate:
1. Raw source
2. Parsed candidate fact
3. Accepted/trusted state

Never discard source identity merely because a fact was normalized.

Potential trust ordering is context-specific:
- Explicit user correction is authoritative for personal task state.
- Calendar provider is authoritative for the raw external calendar event itself.
- Learning platform may be authoritative for what it publishes, but a newly discovered task/change still enters WhatToDo as a candidate until user review.
- Email may announce changes but can conflict with older platform data.
- Raw source evidence may update automatically; canonical task facts should remain conservative according to accepted confirmation policy.

Conflict-resolution rules belong partly in `INTEGRATION_PLAN.md`.

Canonical personal task-state mutation policy:
- raw external evidence may be ingested automatically;
- parsed candidates may be generated automatically;
- meaningful accepted Task-state changes require user confirmation by default;
- D-072 authorizes scoped relationship-generated creation; D-073 authorizes expiration only after informing the user; other exceptions still require explicit policy, and external completion always requires review.

---

## 5. Time Semantics

Store:
- exact timestamps with timezone where relevant
- date-only deadlines only when truly date-only
- source timezone if supplied/ambiguous; retain original evidence
- planning timezone Asia/Shanghai; date-only cutoff local 23:59, retaining default-policy provenance
- created/released/due/completed times separately

Avoid:
- storing human strings such as "tomorrow night" as canonical time
- silently dropping timezone
- confusing deadline with scheduled work block

---

## 6. Progress and Effort

Keep distinct:
- estimated total effort
- estimated remaining effort
- cumulative actual effort
- minimum useful continuous session
- fragmentability
- optional subtask/stage progress

A percentage is not required as the user's primary progress input.

Reason:
A task can be 50% conceptually complete without having exactly half of estimated time remaining.

Historical calibration should use actual work sessions rather than only self-reported percentages when possible.

User evening review is the primary routine point for confirming actual completion and actual effort.

For every future-relevant INCOMPLETE Task, evening review needs a new user estimate or an explicit unchanged-estimate confirmation. Untouched Tasks with existing unchanged estimates may be confirmed in one scoped batch (D-077). If neither is supplied, continue requesting it.

Externally inferred completion must create a pending confirmation rather than directly changing the Task to COMPLETE in v1.

When model and user remaining-effort estimates disagree:
- user estimate remains canonical;
- model estimate remains derived and, when applicable/valid, supplies the effective allocation/risk budget (D-074);
- disagreement may produce an estimation-risk signal.

---

## 7. Goal/Task Separation

Do not model a 3-month exam-preparation goal as one giant task.

Use:
```text
Goal → Milestone → generation rule → Task → WorkSession
```

This allows long-term work to enter the daily planner before urgency becomes extreme.

---

## 8. Calendar Separation

Task deadline:
- property of Task.

Calendar event:
- property of Event.

Scheduled study block:
- an Event/WorkSession linked to a Task.

These can reference each other but must not collapse into one object.

---

## 9. Alignment Rule

For each entity/field, be able to state:
- why it exists
- where it comes from
- whether it is stable/dynamic/derived
- which downstream modules consume it
- what behavior it changes
- whether its exact representation can be deferred

Do not add provider-specific fields to the conceptual model merely because an external API exposes them.

## 10. Open Questions to Resolve in Phase 1

- Exact Task fields required vs optional
- Exact status/state machine
- Exact encoding of effort/stage-based progress (binary parent completion and user-canonical remaining effort are already accepted)
- Exact representation of accepted parent/stage structure and hard/soft dependency edges; both semantics are required
- Whether Course and generic Activity share one profile type
- How recurring tasks are instantiated
- Which preferences are global vs course-specific
- Confidence semantics
- Exact conflict state representation

When resolved, propagate changes to:
- IO_CONTRACT_PLAN
- INTEGRATION_PLAN
- PLANNER_PLAN
- formats/
- TESTING_PLAN

---

## 11. Cross-Entity Invariants to Carry into M2

- Keep separate dimensions: candidate acceptance, INCOMPLETE/COMPLETE, lifecycle/disposition (active/cancelled/expired), and derived overdue/stale/conflicted metadata. Their exact encoding is open; a single undifferentiated status enum is insufficient. An overdue REQUIRED Task is not automatically complete, optional, expired, or deleted.
- User-confirmed remaining effort, template/default initial estimates, internal numeric predictions, and selected daily stage/session estimates are different quantities with provenance/version. Completing a Task sets its remaining effort to zero after authorized validation; time spent alone never proves completion or mechanically determines remaining effort.
- Parent and child stages describe the same obligation. Forecasts must count its work once; daily selected stage effort is part of parent effort, not an extra workload. Parent-versus-stage accounting is resolved in Section 12: one effective parent planning budget (model-first under D-074) supplies stage allocations; the canonical user estimate remains separate and is not extra workload.
- A child-stage completion does not independently confirm the final parent obligation. Reopening a stage preserves history and requires the accepted personal-state authorization path; apply the consistent parent effect under Section 12 when the user explicitly confirms genuine rework of that same obligation.
- TaskType defaults may be copied automatically into a proposed/authorized Task; automatic inheritance does not authorize canonical creation. New template versions must not silently rewrite existing accepted Tasks.
- Accepted Goal configuration is distinct from generated Tasks/Goal progress. Canonical instances may be activated by an explicitly accepted generation relationship under D-072; otherwise candidate review remains. Generators must be idempotent.
- Expiration condition is distinct from deadline. D-073 permits recording EXPIRED after first informing the user, without an extra acknowledgement; uncertain condition or failed notice delivery remains pending. Preserve evidence/history.
- Course teaching/task-family progress values are dynamic; axis/unit definitions are stable. A maximum completed unit must not hide holes in older units when reporting backlog.
- WorkSession actual observations and planned allocations remain separate, even if implemented in one table. Optional time-of-day data must not be fabricated when only total effort was reported.
- Effective-state/version checks and audit records are required for confirmed writes, including batch writes. Reject stale proposals rather than overwriting intervening user updates.

Open cross-file edges are tracked in CONSISTENCY_AUDIT.md; exact SQL tables remain deferred until Phase 2.

---

## 12. O03 Resolved — Parent/Stage Accounting

Resolution type: internal engineering rule under existing A0 semantics; no new user field or repeated review is introduced. The user authorized resolution of non-experience implementation questions on 2026-10-06.

1. A parent obligation retains its user-confirmed remaining effort U separately from its effective planning budget B. Under D-074, B is the valid model remaining-effort prediction when available, otherwise U with fallback provenance. Stages/sessions consume B for forecast accounting; never add U+B or parent+stage budgets. Preserve original estimates/provenance separately.
2. Stage planning budgets are derived. Allocate the effective parent planning budget B across unfinished stages using accepted template proportions or stage prediction weights. If valid weights sum to W, a provisional stage allocation is B*w_i/W. Exact allocation heuristics may change without changing canonical estimates. With no reliable weights, plan against the parent budget and report stage-estimate uncertainty rather than fabricate user-supplied detail.
3. Preserve separately user-provided stage estimates if available. A contradictory accepted stage estimate is not silently scaled away or used to overwrite the parent. Surface one reconciliation question, with both interpretations, only when the contradiction affects actionable planning. Otherwise B controls allocation/forecast accounting; canonical U and any separately confirmed stage values retain their provenance, with material disagreement surfaced concisely.
4. Reporting time spent never mechanically reduces canonical remaining effort. Evening review supplies an updated user estimate or authorized unchanged-estimate batch; then recompute any applicable remaining-effort prediction, select B under D-074, and regenerate derived stage allocations. Existing history retains the earlier budget and predictions.
5. If the user explicitly says an existing obligation's completed stage genuinely needs rework, the resolved command authorizes reopening that stage and keeping/reopening its parent as INCOMPLETE in the same audited transaction. This is a consistent effect of the user's command, not external evidence or automatic inference. Obtain a user-confirmed remaining estimate when needed. Distinguish correcting an erroneous old completion record from a new independent follow-up obligation; ambiguous intent stays pending.
6. Child stages alone do not prove final parent completion. Final COMPLETE remains user-confirmed, with remaining effort zero. Keep stage/parent rework history and do not re-ask the same resolved instruction.

This uses the existing normal brief (parent remaining effort + today's stage estimate) and the existing rework/confirmation rules. Physical storage, rounding precision, and optimization-library choice remain later engineering details.

---

## 13. Follow-Up Data Invariants

Record rule-authorized creation separately from direct confirmation; preserve field/default provenance and rule version. Validate generation and temporal-order graphs separately. Concrete generation creates a separate Task unless explicitly specified as a stage; never share a parent budget by accident.

For expiration retain detected condition, notice delivery evidence/time, actual state-change time, and previous effort/completion history. Inform-before-record does not require marking the user as having read the message. Expiration is a disposition change; it must not set completion to COMPLETE or turn last user remaining effort into zero as if work succeeded.

An unchanged-estimate batch records membership and per-Task verification provenance. Keep the original estimate's observation time; record the review confirmation time separately. Unreported work/session details remain unknown.

Time-normalized fields use Asia/Shanghai for user-day semantics and explicit default 23:59 for date-only deadlines. Exact provider timestamps retain their timezone and may be converted for display without changing the instant. D-078 fixes the horizon mode to natural days including today, with 1/3/7-day cutoffs today / today+2 / today+6 at 23:59. A versioned forecast snapshot retains calculation instant, Asia/Shanghai anchor date, covered date range, and cutoff for each window. Remaining usable capacity starts at the snapshot, not midnight in the past. Preserve absolute source deadlines and distinguish forecast-window bounds from Task deadlines and override expiry.
