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
- Planning rules
- Goal templates
- Configuration

### PostgreSQL dynamic state
Best for changing operational truth:
- Tasks
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
Describes stable characteristics used in planning:
- name
- domain
- importance
- typical task types
- cognitive load
- workload
- duration tendencies
- preferred session length
- fragmentability
- timing preference
- recurring patterns

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
- importance
- minimum useful continuous session
- fragmentability
- dependencies / parent-stage relation where needed
- necessity / requiredness concept
- importance concept
- status
- verification/confidence

### TaskTemplate
Reusable pattern that generates or describes recurring tasks.

A normal task type should generally map to a stable decomposition template.

Template concepts may include:
- stage/subtask structure
- inherited difficulty dimensions
- default total-effort range
- minimum useful session
- fragmentability
- dependency/order between stages

If an unusual workflow is substantially different, prefer defining a new task type/template rather than silently altering the ordinary one.

Example:
- Pre-lab report for Electronic Circuits.

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

### Routine
Recurring expected activity not necessarily a task instance.

### Constraint
Hard or soft scheduling/planning restriction.

Examples:
- class cannot move
- no high-cognitive work after a certain hour
- lab task needs at least 90 minutes

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
Structured daily/weekly plan snapshot.

### AIJob
Structured unit of AI-assisted work.

### StateChange / AuditRecord
Records meaningful changes and their actor/source.

### PendingConfirmation / UncertainCandidate
Represents information that may be useful but is not trusted enough to mutate canonical state.

Examples:
- ambiguous deadline extraction
- possible completion inferred from an external signal
- conflicting source facts
- uncertain task mapping

Must support batching into the next normal user interaction.

### EffortHistory / EstimationObservation
Historical evidence for improving future duration estimates.

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

## 3. Task Lifecycle

Initial conceptual lifecycle:

```text
CANDIDATE
   ↓ verify/accept
CONFIRMED
   ↓ start
IN_PROGRESS
   ↓ complete
COMPLETED
```

Side transitions:
- CANDIDATE → REJECTED
- CONFIRMED/IN_PROGRESS → CANCELLED
- active task past deadline → OVERDUE
- uncertain source/state → STALE or CONFLICTED metadata/state

Final exact state machine is to be defined during Phase 1 Task-model work.

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

---

## 5. Time Semantics

Store:
- exact timestamps with timezone where relevant
- date-only deadlines only when truly date-only
- source timezone if ambiguous
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

Externally inferred completion should normally create a pending confirmation rather than directly changing the Task to COMPLETED.

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
- How user-reported progress is represented
- How task decomposition is modeled: parent/child vs dependency graph
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
