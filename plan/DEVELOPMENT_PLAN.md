# WhatToDo — Ordered Development Plan

> Planning control center: `plan/README.md`  
> Live project state: `plan/PROGRESS.md`  
> Active pre-development alignment specification: `plan/ALIGNMENT_PLAN.md`  
> M1 modeling specification after A0: `plan/USER_MODEL_PLAN.md`

> Status: Existing milestone roadmap; detailed execution plan not yet prepared.
> Current requested sequence: consistency audit → synchronize accepted follow-up answers (complete, including natural-day horizons) → detailed project planning → semantic modeling milestones. M1 is incomplete, not a reason to bypass the user's current planning request.
> Status: Planning phase  
> Audience: AI agents, Codex, future maintainers  
> Authority: This file is the authoritative source for **development order, prerequisites, and milestone sequencing**.  
> Architecture reference: `plan/PROJECT_PLAN.md`  
> Rule: If an older document differs on implementation order, this file takes precedence. Architectural principles in `PROJECT_PLAN.md` remain valid unless explicitly superseded.

---

## 1. Development Principle

Do not start by building infrastructure, scraping, or AI.

Build in this dependency order:

```text
Align user-AI interaction and information semantics
        ↓
Define what the system must understand
        ↓
Persist trusted state
        ↓
Understand the user's available time
        ↓
Collect external changes automatically
        ↓
Plan tasks deterministically
        ↓
Add AI selectively
        ↓
Recover and improve from real usage
```

The project has **13 core functional capabilities**, including the newly requested Task Relationship System (F13). In addition, several design artifacts such as the Task schema and input/output contracts must be defined early because later functions depend on them.

### Phase 0 — Interaction and Information-Model Alignment

Before M1 and before any implementation, complete Alignment Gate A0 defined in `ALIGNMENT_PLAN.md`.

This phase confirms:
- how the user and AI collaborate during planning and development
- the information categories and granularity expected for each major module
- how information in one module changes behavior in downstream modules
- which information is stable, dynamic, inferred, or derived
- which questions must be answered now
- which provider-specific details must wait until real integration

A0 deliberately does **not** require exact Calendar API fields, n8n node parameters, Gmail metadata mappings, learning-platform selectors, PostgreSQL tables, or planner formulas.

Provider-specific interface details are defined later through adapter contracts once the real system is connected and inspected.

No code implementation should begin before A0 is accepted.

---

## 2. The 13 Core Functional Capabilities

### F1 — Personal Domain Classification

Goal:
- Represent the user's life using the agreed top-level domains:
  - Study / academics
  - Exercise / sports
  - Life administration
  - Other

User must provide:
- Confirmation of categories
- Common recurring responsibilities
- Optional subcategories if useful

Depends on:
- Nothing

---

### F2 — Course / Activity Model

Goal:
- Model each course and recurring activity according to its real characteristics.

Possible properties:
- TaskType defaults (Task importance/requiredness; no primary Course importance score)
- Typical task types
- Thinking depth / repetitive volume / new-learning load, each 1–5
- Workload
- Typical duration
- Minimum useful session length
- Fragmentability
- Preferred time of day
- Deadline patterns
- Exam relevance

User must provide:
- Current courses
- Recurring activities such as training
- Per-course workload and difficulty
- Typical task types
- Personal experience about duration and working style

Depends on:
- F1

---

### F3 — Task Input System

Goal:
- Let new tasks, corrections, completions, cancellations, and schedule changes enter WhatToDo conveniently.

Initial input sources:
1. Direct natural-language user input
2. Calendar
3. Email
4. Learning platform
5. Internally generated system/history events

The user should not need to manually write JSON.

User must provide:
- Real examples of how they naturally describe tasks and changes
- Which sources should be treated as authoritative
- Examples requiring clarification; v1 does not auto-accept external canonical Task changes

Depends on:
- F2
- Foundational Task model

---

### F4 — Task State Database

Goal:
- Maintain the canonical answer to: "What is currently true?"

Dynamic state includes:
- Tasks
- Status
- Progress
- Deadlines
- Estimated remaining effort
- Events
- Goal progress
- Source records
- Sync metadata
- Plan history

Storage direction:
- PostgreSQL for dynamic operational state
- Git/YAML/JSON for stable declarative knowledge

User must provide:
- Mainly review and confirmation that the model matches real use
- No database expertise is required

Depends on:
- F2
- F3
- Task schema
- Input contract

---

### F5 — Long-Term Goal System

Goal:
- Represent long-term outcomes separately from immediate tasks.

Hierarchy:

```text
Goal
↓
Milestone
↓
Task generation rule
↓
Concrete task
↓
Work session
```

Examples:
- English exam in three months
- Midterm preparation
- Final exam preparation
- Long-running project

User must provide:
- Goal
- Target date
- Desired outcome
- Major phases if known
- Acceptable pacing and hard constraints

Depends on:
- F4

---

### F6 — Calendar / Time System

Goal:
- Let the system know when the user is occupied and when usable work time exists.

Current direction:
- Google Calendar as automation backend
- Apple Calendar may remain the user's everyday client

User must provide:
- Current class timetable
- Training schedule
- Recurring fixed commitments
- Which events are immovable
- Which blocks may move
- Calendar habits
- Relevant no-work / sleep boundaries

Depends on:
- F4

---

### F7 — External Information Collection

Goal:
- Automatically discover new or changed obligations.

Initial sources:
- Email
- Learning platform

Email should support:
- Classification
- Fact extraction
- Course mapping
- Deduplication
- Provenance

Learning-platform connector should detect:
- New assignments
- Deadline changes
- Announcements
- Exam information
- Relevant files/materials

User must provide:
- Relevant email accounts/categories
- Examples of useful vs irrelevant messages
- Learning-platform page structure and access constraints
- Which pages and information matter

Depends on:
- F3
- F4

---

### F8 — State Reconciliation / Recovery

Goal:
- Recover trustworthy state after several days of inactivity, missed events, or contradictory information.

Flow:

```text
Last trusted state
↓
Detect stale interval
↓
Re-read calendar
↓
Fetch missed email
↓
Fetch learning-platform changes
↓
Re-evaluate deadlines
↓
Detect ambiguous / overdue tasks
↓
Present all unresolved confirmations, high-impact first, and resolve the full queue where possible
↓
Restore trusted state
↓
Replan next 7–14 days
```

User must provide:
- Missing factual completion/progress/remaining-effort information during catch-up
- Explicit user confirmations under accepted A0 rules
- Task-specific cancellation/expiration clarification where needed; do not infer completion

Depends on:
- F4
- F6
- F7
- F9

---

### F9 — Planner Core

Goal:
- Decide what should be done, in what order, and how work should fit available time.

The planner should be deterministic-first.

Inputs include:
- Deadline
- Remaining effort
- Progress
- Available calendar capacity
- Fixed events
- Dependencies
- Minimum session length
- Cognitive load
- Importance
- Exam proximity
- Long-term milestone requirements

User must provide:
- Maximum desired daily load
- Preferred study periods
- Minimum focus blocks
- Exam preparation rules
- Rules for large assignments
- Desired amount of schedule buffer
- Other planning preferences

Depends on:
- F4
- F5
- F6

---

### F10 — AI Router / AI Job System

Goal:
- Decide whether a job needs no AI, a cheap model, or premium manual reasoning.

Execution levels:

- Level 0: deterministic code
- Level 1: cheap / normal API or local model
- Level 2: premium manual ChatGPT Work / Codex where appropriate

AI should normally emit structured proposals rather than directly mutating canonical state.

User must provide:
- Rough API cost tolerance
- Which tasks deserve premium reasoning
- When manual ChatGPT processing is acceptable

Depends on:
- Stable schemas
- F4
- F9

---

### F11 — Daily Output System

Goal:
- Produce the main user-facing answer: "What should I do today?"

Potential sections:
- Must do today
- Should do today
- Optional / if time remains
- Fixed events
- Estimated duration
- Concrete completion target
- Risk warnings
- Weekly / long-term progress

Already accepted:
- concise recommendation-oriented output, without exact clock blocks by default
- parent remaining effort, selected stage effort, and work style
- all 1/3/7-day risks plus worst-horizon mode
- deadlines shown within 3 days, for risky work, or on request
- exception-driven explanation and two-round overall-EMERGENCY output

User input later:
- real examples and any explicit rendering refinements beyond the accepted template

Depends on:
- Output contract
- F9

---

### F12 — Historical Learning and Self-Correction

Goal:
- Improve planning estimates using observed behavior.

Examples:
- Estimated vs actual duration
- Planned vs completed work
- Course-specific underestimation
- Time-of-day completion patterns
- Repeated postponements

User must provide:
- Actual completion status
- Actual duration where practical
- Corrections when inferred history is wrong

Depends on:
- Stable task types
- F4
- F9
- Real usage history

---

### F13 — Task Relationship System

Goal:
- define generation and completion/start-order relationships between Tasks
- automatically create a mapped counterpart under a preapproved generation rule
- enforce hard temporal relations and distinguish soft sequence/stage membership
- prevent duplicate/uncontrolled generation and contradictory order

User supplies representative relationship patterns and any missing meaning/target defaults; no coding or technical graph notation is required. The accepted minimum examples are Task 1 creation → Task 2 generation, and Task 2 completion before Task 1 completion. Generic authority is D-071/D-072; no need to reconfirm the feature itself.

Depends on F2/F3 semantic contracts and F4 persistence; feeds F5 goal generation and F9 Planner. M1B/M2 define relationships; M3 implements minimal persistence/generation; M6 enforces ordering. Detailed specification: TASK_RELATIONSHIP_PLAN.md.

---

## 3. Foundational Design Artifacts

These are not separate end-user functions, but they must be completed early.

### A. Task Model and Lifecycle

Define what one Task contains.

Likely fields:
- Identity
- Domain / course
- Type
- Title
- Source
- Release time
- Deadline
- Estimated total time
- Estimated remaining time
- Progress
- Cognitive load
- Importance
- Minimum session length
- Whether it can be split
- Dependencies
- Status
- Confidence / verification metadata

Keep distinct conceptual dimensions (exact encoding in M2):
- Candidate acceptance: pending / confirmed / rejected / conflicted
- Canonical parent completion: INCOMPLETE / COMPLETE
- Lifecycle/disposition: active / CANCELLED / EXPIRED
- Derived risk/trust: OVERDUE, STALE / UNKNOWN / CONFLICTED
- Partial work: actual invested effort, user-confirmed remaining effort, child-stage status

Do not introduce IN_PROGRESS as a third parent completion state or automatically mark overdue work expired.

### B. Input Contract

Repository location:
- `formats/input/`

Define for each source:
- Raw form
- Required fields
- Optional fields
- Provenance
- Normalized object
- Confidence
- Deduplication
- Correction/update semantics

### C. Output Contract

Repository location:
- `formats/output/`

Define:
- Structured daily-plan representation
- Human-readable daily brief
- Required vs optional sections
- Rendering rules

These three artifacts should be stable before database and connector implementation.

---

## 4. Phase 1 — Define What the System Understands

### Build

1. F1 Personal Domain Classification
2. F2 Course / Activity Model
3. Task Model and Lifecycle
4. F3 manual natural-language task input design
5. Input Contract
6. Output Contract
7. Initial Goal / Milestone concepts and generic onboarding contract (A0 minimum fields, approval boundary, Task generation semantics)
8. F13 typed Task relationships, automatic-generation rule authority, and concrete mappings before persistence

### User participation

High.

The user provides:
- Courses
- Recurring activities
- Workload characteristics
- Real task examples
- Natural-language input examples
- Desired daily-output style

### Completion criteria

Phase 1 is complete when:
- Current courses can be represented.
- Real current tasks fit the Task model without ad hoc fields.
- Common user statements map into structured candidate changes.
- A structured daily plan can be rendered into an acceptable daily brief.

### Do not build yet

- Full PostgreSQL implementation
- Learning-platform scraper
- Advanced planner
- AI Router

---

## 5. Phase 2 — Build Persistent Memory and State

### Build

1. F4 Task State Database
2. PostgreSQL schema
3. Git/YAML/JSON long-term profiles
4. Manual task create/update/complete/cancel flows
5. Provenance
6. Audit history, confirmed-write authority, state version checks, pending-confirmation persistence, effort history, and staleness/minimal reconciliation
7. Initial F5 Goal persistence (configuration only; full goal generation is later)
8. F13 minimal relationship persistence, separate graph validation, and approved canonical-creation → mapped counterpart generation with idempotent audit
9. Expiration notice-before-record workflow/process state and unchanged-estimate batch-confirmation provenance

### Minimal vertical prototype

```text
Manual user input
↓
Normalize/resolve proposed Task or explicit user instruction
↓
User acceptance when not already authorized + validation
↓
Persist canonical state + audit
↓
Read current tasks
↓
Produce a simple daily brief
```

### User participation

Low to medium.

The user mainly reviews whether the stored concepts match real use.

### Completion criteria

- State survives chat sessions and restarts.
- Tasks can be created, edited, completed, and queried.
- Stable knowledge and dynamic state are separated.
- A basic daily brief can be produced from stored state.

---

## 6. Phase 3 — Add Real Time Availability

### Build

1. F6 Calendar / Time System
2. Google Calendar integration
3. Import recurring classes and training
4. Normalize calendar events
5. Free/busy calculation
6. One-off changes
7. Calendar conflict detection

### User must provide

- Timetable
- Training schedule
- Fixed commitments
- Event flexibility rules
- Calendar preferences

### Completion criteria

For any day, the system can determine:
- Fixed events
- Usable time windows
- Focus-capable windows
- Whether proposed work can realistically fit

---

## 7. Phase 4 — Automate Information Collection with n8n

### Build

1. Deploy/configure n8n
2. F7 External Information Collection
3. Email ingestion workflow
4. Learning-platform connector
5. Calendar sync workflow as needed
6. Deduplication
7. Confidence handling
8. Retry/error logging

### User must provide

For email:
- Relevant accounts/categories
- Important senders/types
- Examples of useful and irrelevant mail

For learning platform:
- Relevant pages
- Assignment locations
- Announcement locations
- Deadline locations
- Attachment requirements
- Login/access constraints

### Completion criteria

Common new obligations and changes can be discovered automatically and stored as evidence/candidates with source traceability. Canonical Task changes still require user review; high confidence does not bypass it.

### Constraint

Connectors must not own planner logic. They normalize information; planning remains separate.

---

## 8. Phase 5 — Build the Planning MVP

### Build

1. F5 Long-Term Goal System
2. F9 Planner Core
3. Priority calculation
4. Capacity calculation
5. Task/session splitting
6. Goal-generated recurring work
7. F11 Daily Output System
8. Daily n8n trigger
9. Optional calendar writing for flexible work blocks (only after ownership/write scope is agreed)
10. Morning/evening review, missed-interaction reconciliation, proactive risk alerts, and two-round overall-EMERGENCY planning using the safety foundations already built

### User must provide

- Planning preferences
- Daily load preference
- Buffer preference
- Focus-block preference
- Exam review timing
- Rules for large assignments
- Final daily-output preferences

### Completion criteria

Without premium AI, the system can:
- Refresh current state
- read available time
- prioritize current work
- generate a realistic daily plan
- identify major risks

This is the first major usable MVP.

---

## 9. Phase 6 — Add AI Selectively

### Build

1. F10 AI Router / AI Job System
2. No-AI / cheap-AI / premium-manual routing
3. One low-cost automated model path
4. Structured AI output schemas
5. Extend the existing confirmed-write validator with AI schemas/provider results; validation never substitutes for user authorization
6. Manual premium-job workflow for ChatGPT Work
7. Cost/token logging for automated APIs

### User must provide

- Cost tolerance
- Premium vs cheap decision preferences
- Which operations may wait for manual ChatGPT execution

### Completion criteria

- Swapping model providers does not redesign the system.
- AI failures cannot corrupt trusted state.
- Daily planning still works when all AI providers are unavailable.

---

## 10. Phase 7 — Make the System Resilient and Self-Correcting

### Build

1. Extend F8 to comprehensive multi-source inactivity recovery and weekly/long-term review
2. Extend existing TRUSTED / STALE / UNKNOWN / CONFLICTED handling; these safety foundations already exist in earlier prototypes
3. Periodic full synchronization
4. Weekly review
5. F12 Historical Learning and Self-Correction
6. Estimated-vs-actual calibration
7. Backlog detection
8. Planning-parameter adjustment from history

### User must provide

Mostly real-world usage feedback:
- What was actually completed
- How long work actually took
- Whether generated plans felt realistic
- Corrections when system inferences were wrong

### Completion criteria

The system can be ignored for several days, recover trustworthy state, and produce a useful new plan without rebuilding everything manually.

---

## 11. Ordered Milestones

### M0 — Planning repository prepared — COMPLETE

Already available:
- planning control center
- architecture and ordered development plan
- input/output planning directories
- n8n-only orchestration decision

### A0 — Interaction and information-model alignment — COMPLETE

Historically obtained from user (do not re-request as a new gate):
- confirmation/correction of the intended user-AI development interaction
- discussion of expected semantic granularity for modules
- confirmation that semantic contracts may be fixed before provider-specific adapter contracts
- examples/questions needed to expose mismatched interpretations

Deliverables:
- accepted interaction model
- module information-alignment method
- documented cross-module effects
- explicit deferred integration-specific questions

Completion authority:
- `plan/ALIGNMENT_PLAN.md`

### M1 — User and course model — NEXT INCOMPLETE SEMANTIC MILESTONE

This milestone is intentionally information-rich. Detailed per-course modeling is expected to be one of the largest user-input activities in the project.

Important modeling principle:
- Course is primarily context/classification.
- Task is the fundamental planning unit.
- Course-level importance is not a primary planner variable; task-level importance/requiredness drives planning.
- Each course should define an instructional progress axis for attaching tasks and exam coverage.

Need from user:
- All current courses
- Recurring exercise/training
- Recurring life/other obligations
- Per-course characteristics

Deliverables:
- Domain taxonomy
- Course/activity profiles
- Planning-relevant course semantics

### M1B — Course / task-type decomposition presets

Purpose:
- define task granularity separately for each course/task class instead of forcing one universal decomposition rule.

Need from user:
- representative tasks from each course/task class
- preferred decomposition depth
- meaningful stages/subtasks
- thinking-depth, repetitive-volume, and new-learning-load characteristics
- total-time tendencies
- minimum useful continuous session
- fragmentability
- recurring stage/dependency patterns

Deliverables:
- per-course/task-type decomposition presets and representative generation/order relationship patterns
- extensible task-type taxonomy
- one stable default template per normal task type
- rules for when a workflow should become a new task type/template
- rules for when to split and when not to split
- multi-dimensional difficulty representation
- effort/session defaults that task instances may inherit

### M2 — Task and I/O contracts

Need from user:
- Real task examples
- Natural-language task/change examples
- Desired daily output
- partial-progress/update examples
- uncertainty/confirmation examples
- examples of externally detected possible completion

Deliverables:
- Task schema
- Task lifecycle
- Input specification
- Output specification
- concrete Daily Brief contract based on `formats/output/DAILY_BRIEF_TEMPLATE.md`
- generic Goal onboarding/approval/generation contract before Goal persistence; M5B later validates real Goal examples
- typed Task relationship/generation-rule contracts and bounded instance authorization
- model-first effective planning budget vs canonical user estimate, expiration notice-before-record, Beijing-time cutoff, aggregate-gap and batch-review contracts
- accepted natural-day window contract (D-078), snapshot time, local-date/cutoff bounds, remaining-only capacity, and unchanged daily reserve before exact risk-window implementation

### M3 — Persistent-state prototype

Deliverables:
- PostgreSQL
- Long-term config
- Manual task CRUD
- Basic daily brief

### M4 — Calendar-aware prototype

Need from user:
- Timetable
- Training
- Calendar preferences

Deliverables:
- Calendar integration
- Free/busy calculation
- Calendar-aware daily brief

### M5 — Automated collection

Need from user:
- Email rules
- Learning-platform details

Deliverables:
- n8n workflows
- Email connector
- Learning-platform connector
- Provenance and deduplication

### M5B — Long-term goal onboarding refinement and activation

Purpose:
- refine/test the generic M2 onboarding contract using real Goal examples and make runtime generation ready for M6. M5B does not postpone basic Goal semantics until after database design.

Need from user:
- example long-term goals
- overall target/outcome
- total workload or measurable target
- desired daily/recurring work
- target date
- milestone/phase preferences
- progress measurement

Deliverables:
- goal onboarding interaction contract
- goal/milestone/task-generation semantics
- configured Goal/recurring/conditional work uses accepted generation relationships for mapped canonical instances; outside their scope use candidate review (D-072)
- generated Tasks must enter Planner through the same Task interface as other work

### M6 — Planning MVP

Need from user:
- Scheduling preferences

Deliverables:
- Planner with hard completion/start-order relations and model-first remaining-effort budgets
- Daily plan
- 1/3/7-day capacity-vs-required-work forecasts
- emergency/risk mode
- daily scheduled generation

### M7 — AI-enhanced planning

Need from user:
- Cost policy
- Premium-vs-cheap policy

Deliverables:
- AI Router
- Validator
- Manual ChatGPT premium-job path

### M8 — Long-term resilient system

Need from user:
- Usage feedback
- confirmation/rejection of candidate learned behavioral rules

Deliverables:
- Reconciliation
- Weekly review
- Historical calibration
- Behavior/estimation analyzer
- Candidate learned-rule review
- Self-correction through automatic internal numeric calibration and user-approved behavioral rules; neither silently overwrites canonical user estimates

---

## 12. Current Project Position and Next Action

Current position:

```text
M0 complete
↓
A0 interaction + information-model alignment COMPLETE
↓
Post-audit detailed project planning requested
↓
M1 user/course modeling NEXT / INCOMPLETE
```

A0 is closed. Do not reopen broad alignment questioning unless M1 or later work exposes a genuine semantic contradiction.

Do **not** begin PostgreSQL implementation, n8n workflow construction, scraping, calendar API mapping, or planner coding yet.

The six experience answers are now synchronized, including the new Task Relationship System. O03/O06 are resolved internal specifications. D-078 now also resolves natural-day horizons including today. Prepare the detailed project plan before course/activity collection; do not re-ask accepted choices. Use CONSISTENCY_AUDIT.md as planning input; do not mark semantic milestones complete or begin infrastructure.

Subsequent semantic sequence:

1. Collect and confirm the user's current courses and recurring non-course commitments.
2. Choose one representative course and build its Course Profile and Course Progress Axis.
3. Refine the reusable course-profile structure using that real example.
4. Apply the structure to all remaining courses/activities.
5. Complete M1 acceptance criteria.
6. Complete M1B per-course/task-type decomposition presets.
7. Proceed to M2 Task and I/O contracts before persistence.

Provider-specific Calendar/Gmail/learning-platform details remain deferred until their integration phases.

---

## 13. Cross-Phase Safeguards and Remaining Planning Work

This file remains an ordered roadmap, not the detailed implementation plan requested next. The next planning session should map milestones to concrete deliverables, module interfaces, dependencies, user-input checkpoints, acceptance criteria, and rollout steps without pretending missing profiles/schemas are already complete.

Safety is incremental: Phase 2 owns minimal confirmation/audit/versioning/staleness/history; Phase 4 owns safe connector replay/checkpoints; Phase 5 owns usable recovery and normal/emergency review. Phase 7 adds comprehensive recovery, weekly/long-term review, and historical learning. Full AI Router work in Phase 6 must not be a prerequisite for earlier basic validation or deterministic ingestion/planning.

Known A0 policies are defaults, not new questions: no primary Course importance, no generic TaskType lead time, binary parent completion, three requiredness values, one-hour reserve, worst-horizon risk, advisory external completion, user-canonical remaining effort, and automatic numeric learning vs reviewed behavioral rules. Collect concrete course/TaskType values and explicit exceptions at their milestones.

Before activating a behavior touched by an unresolved item in CONSISTENCY_AUDIT.md, resolve its semantics at the listed milestone. Conservative evidence/candidate storage permits useful preparatory work; it is not permission to invent missing personal facts.

---

## 14. Follow-Up Implementation Prerequisites

Build the newly accepted relationship system as a domain capability across M1B/M2/M3/M6, not as a speculative later add-on. M3's minimal persistent-state prototype must handle approved creation cascades/deduplication; M6 must consume distinct completion/start-order constraints and counted counterpart workloads. n8n orchestration remains the sole workflow platform.

The user approved notice-before-record expiration without another confirmation click. Persist delivery attempts/state/version and do not claim a notice succeeded when delivery failed. Keep hard completion evidence review unchanged. The user chose model prediction for planning, not overwriting personal effort facts; parent/stage allocation uses one operative model-first budget.

Asia/Shanghai and date-only 23:59 are fixed. The SAFE discretionary remainder rule is aggregate <=40 minutes. Untouched unchanged estimates are explicitly confirmed in a scoped batch. These are accepted contracts, not new questions or implemented capabilities. D-078 also fixes natural-day risk windows including today, ending today / today+2 / today+6 at Beijing-time 23:59. All original experience choices are resolved; concrete schemas/libraries/provider adapters remain normal later engineering work.
