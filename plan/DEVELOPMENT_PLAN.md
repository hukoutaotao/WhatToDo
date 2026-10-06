# WhatToDo — Ordered Development Plan

> Status: Planning phase  
> Audience: AI agents, Codex, maintainers  
> Authority: This file is the authoritative source for **development order and dependencies**.  
> Architecture reference: `plan/PROJECT_PLAN.md`  
> Rule: If development sequencing here conflicts with older sequencing elsewhere, this file takes precedence. Architectural principles in `PROJECT_PLAN.md` remain valid unless explicitly superseded.

---

## 1. Purpose

This plan converts the WhatToDo architecture into an executable development sequence.

The project should not be built by starting with infrastructure, scraping, or AI. The correct order is:

```text
Understand the user and define data
        ↓
Persist trusted state
        ↓
Understand available time
        ↓
Collect external changes automatically
        ↓
Plan tasks deterministically
        ↓
Add AI where useful
        ↓
Learn and recover over time
```

The project currently contains twelve core functional capabilities. They are grouped into seven ordered phases below.

---

## 2. Core Functional Capabilities

### F1 — Personal Domain Classification

Purpose:
- Represent the user's work using the top-level domains:
  - Study / academics
  - Exercise / sports
  - Life administration
  - Other

User information required:
- Confirmation of categories
- Optional subcategories
- Examples of common recurring responsibilities

Output:
- Stable domain taxonomy

Depends on:
- Nothing

---

### F2 — Course / Activity Profiles

Purpose:
- Model each course or recurring activity differently instead of treating every task as identical.

The profile may contain:
- Name
- Importance
- Typical task types
- Cognitive difficulty
- Workload
- Typical duration
- Minimum useful session length
- Fragmentability
- Preferred time of day
- Deadline patterns
- Exam relevance
- Recurrent preparation/review needs

User information required:
- Current courses and recurring activities
- Per-course description of workload and difficulty
- Typical task patterns
- Personal experience about how the work feels and how long it takes

Output:
- Version-controlled course/activity profiles

Depends on:
- F1

---

### F3 — Task Model and Lifecycle

Purpose:
- Define exactly what the system means by a Task.

Likely task fields include:
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

Lifecycle must define states such as:
- Candidate
- Confirmed
- In progress
- Completed
- Cancelled
- Overdue
- Stale / uncertain where appropriate

User information required:
- Which properties the user actually cares about when deciding what to do
- Real examples of tasks from current courses
- How the user reports partial completion, cancellation, deadline changes, etc.

Output:
- Canonical Task schema and lifecycle

Depends on:
- F1
- F2

---

### F4 — Input Contract

Purpose:
- Define how information enters WhatToDo and how all sources normalize into machine-readable records.

Human-facing inputs should remain convenient. The user should not need to manually write JSON.

Initial source classes:
1. Direct natural-language user input
2. Calendar
3. Email
4. Learning platform
5. Internally generated history / system events

For each input source define:
- Raw input form
- Required fields
- Optional fields
- Provenance
- Normalized internal object
- Confidence rules
- Deduplication strategy
- Update / correction semantics

User information required:
- 10–20 realistic examples of how the user would describe new tasks, corrections, completions, schedule changes, goals, etc.
- Which sources are authoritative in conflicts
- Which ambiguous changes may be auto-accepted and which require confirmation

Repository location:
- `formats/input/`

Output:
- Input specification
- Example payloads
- Machine schema(s), later

Depends on:
- F3

---

### F5 — Output Contract

Purpose:
- Define exactly what the system should produce for the user every day and what structured representation sits behind it.

Potential daily output sections:
- Must do today
- Should do today
- Optional / if time remains
- Fixed schedule
- Estimated duration per task
- Concrete completion target
- Deadline / urgency indicator
- Risk warnings
- Weekly / long-term progress

User information required:
- Preferred level of detail
- Whether exact time blocks should be shown
- Whether reasons for prioritization should be shown
- Whether deadlines should be visible
- Whether long-term-goal progress should be shown
- Preferred ordering and brevity

Repository location:
- `formats/output/`

Output:
- Human daily-brief template
- Structured daily-plan schema

Depends on:
- F3
- Can proceed in parallel with F4

---

## 3. Phase 1 — Define the System's Language

### Objective

Before implementing infrastructure, make the system capable of representing the user's real life correctly.

### Work to complete

1. F1 Personal Domain Classification
2. F2 Course / Activity Profiles
3. F3 Task Model and Lifecycle
4. F4 Input Contract
5. F5 Output Contract
6. Define Goal / Milestone concepts sufficiently to support later work

### User participation

High.

The user primarily provides domain knowledge:
- Courses
- Workload characteristics
- Real task examples
- Natural-language examples
- Output preferences

AI / developer responsibility:
- Normalize the information
- Design schemas
- Remove redundancy
- Identify missing fields
- Write the resulting specifications to the repository

### Completion criteria

Phase 1 is complete when:
- At least the current semester's major courses can be represented.
- A realistic task can be represented without ad hoc fields.
- Common user statements can be mapped into structured candidate changes.
- A structured daily plan can be rendered into an acceptable human daily brief.
- The input/output contracts are stable enough for a prototype.

### Do not implement yet

- Full database
- Learning-platform scraper
- Advanced planner
- AI Router
- Historical learning

---

## 4. F6 — Long-Term Goals and Milestones

Purpose:
- Represent long-horizon objectives separately from immediate tasks.

Hierarchy:

```text
Goal
↓
Milestone
↓
Task generation rule
↓
Concrete Task
↓
Work session
```

Examples:
- English exam in three months
- Midterm preparation
- Final exam preparation
- Long-running project

User information required:
- Goal
- Target date
- Desired outcome
- Major phases if known
- Acceptable pacing
- Any hard constraints

Output:
- Goal and milestone model
- Task-generation rules

Initial design occurs in Phase 1.
Full persistence and automation occur later.

---

## 5. F7 — Structured Memory and Canonical State

Purpose:
- Ensure the system does not depend on ChatGPT conversation memory.

Storage split:

### Git / YAML / JSON

Use for relatively stable declarative knowledge:
- Course profiles
- User preferences
- Routines
- Goal templates
- Planning rules
- Configuration

### PostgreSQL

Use for dynamic operational state:
- Tasks
- Task status
- Deadlines
- Progress
- Events
- Current goal progress
- Source records
- Sync metadata
- AI jobs
- Plan history
- Work sessions

User information required:
- Primarily review/approval rather than technical input
- Confirmation that the represented objects match real usage

Developer responsibility:
- Design schema from Phase 1 contracts
- Migrations
- Validation
- Provenance
- Audit history

Depends on:
- F3
- F4
- F5
- F6 basic model

---

## 6. Phase 2 — Build the Memory Foundation

### Objective

Create a persistent source of truth before adding external automation.

### Work to complete

1. Finalize core entity model:
   - Course
   - Task
   - TaskTemplate
   - Goal
   - Milestone
   - Event
   - Routine
   - Constraint
   - SourceRecord
   - WorkSession
   - Plan
2. Implement PostgreSQL schema.
3. Implement version-controlled long-term profile files.
4. Implement read/write service or repository layer.
5. Implement validation and audit logging.
6. Implement manual creation/update of tasks.

### Minimal vertical prototype

At the end of this phase, the system should already be able to:

```text
Manual user input
↓
Normalize to Task
↓
Persist in PostgreSQL
↓
Read current tasks
↓
Produce a simple daily brief
```

No automatic email or learning-platform collection is required yet.

### Completion criteria

- State survives chat sessions and machine restarts.
- Tasks can be created, edited, completed, cancelled, and queried.
- Provenance is preserved.
- Long-term configuration and dynamic state are clearly separated.
- A basic daily brief can be generated from stored state.

---

## 7. F8 — Calendar and Time Availability

Purpose:
- Let the system understand when the user is busy and when work can be scheduled.

Current direction:
- Google Calendar as automation backend
- Apple Calendar may remain the user's daily client

Calendar concepts:
- Fixed event
- Flexible planned work block
- Deadline metadata
- Optional reminder

User information required:
- Current semester timetable
- Training schedule
- Recurrent fixed events
- Existing calendar usage habits
- Which events are immutable
- Which events can be moved
- Preferred sleep / no-work boundaries if relevant

System responsibilities:
- Read calendar
- Normalize events
- Detect conflicts
- Compute available time windows
- Later write optional flexible study blocks

Depends on:
- Phase 2 state model

---

## 8. Phase 3 — Make Time Real

### Objective

Combine task state with actual available time.

### Work to complete

1. Connect Google Calendar.
2. Import recurring classes and training.
3. Normalize calendar events into internal Event objects.
4. Compute free/busy windows.
5. Support one-off changes.
6. Detect task/calendar conflicts.
7. Produce a daily brief that includes both tasks and fixed events.

### Completion criteria

Given a date, the system can answer:
- What fixed events exist?
- How much usable time is available?
- Which windows can hold focused work?
- Which tasks cannot realistically fit today?

At this stage planning may still be simple and rule-based.

---

## 9. F9 — Automatic External Information Collection

Purpose:
- Automatically discover changes without requiring the user to manually enter everything.

Initial connectors:
- Email
- Learning platform

Email pipeline:

```text
Fetch
→ classify
→ extract candidate facts
→ map to known course/domain
→ deduplicate
→ validate confidence
→ create/update candidate state
```

Learning-platform pipeline:

```text
Fetch / scrape
→ detect changes
→ normalize
→ identify assignments / announcements / exam information
→ create candidate updates
```

User information required for email:
- Relevant accounts
- Which categories of mail matter
- Which senders/domains are important
- Examples of useful and irrelevant messages

User information required for learning platform:
- Relevant pages
- Where assignments appear
- Where announcements appear
- Where deadlines appear
- Whether attachments matter
- Login constraints

Depends on:
- F4 input contract
- F7 state store
- F8 may be independent for some sources

---

## 10. Phase 4 — Automate Collection with n8n

### Objective

Move from manual state maintenance to continuously refreshed state.

### Work to complete

1. Deploy or configure n8n.
2. Create scheduled sync workflows.
3. Add email ingestion.
4. Add learning-platform connector.
5. Add calendar sync workflow if not already orchestrated through n8n.
6. Add deduplication.
7. Add provenance and confidence handling.
8. Add error logging and retries.

### Completion criteria

The system can automatically discover common new tasks and changes and store them as trusted or candidate updates without losing source traceability.

### Important constraint

Do not let connectors directly contain planner logic.

Connectors produce normalized state changes; planning remains separate.

---

## 11. F10 — Planner Core

Purpose:
- Decide what should be done and when.

The first planner must be deterministic-first.

Inputs:
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

Examples of rules:
- Shorter deadline increases urgency.
- Large remaining workload forces earlier allocation.
- High-cognitive tasks prefer sufficiently long focus windows.
- Fragmentable tasks may fill short gaps.
- Long-term goals generate recurring workload before they become urgent.

User information required:
- Planning preferences
- Maximum desired daily load
- Preferred study periods
- Minimum focus blocks
- Rules for exams
- Rules for large assignments
- Tolerance for schedule density
- How much buffer to preserve

Depends on:
- Phase 2 state
- Phase 3 calendar
- Phase 1 output contract

---

## 12. F11 — Daily Plan and User-Facing Output

Purpose:
- Deliver the main product experience: a clear answer to "What should I do today?"

The structured plan should be separable from rendering.

Possible categories:
- Must do
- Should do
- Optional
- Fixed events
- Fragment tasks
- Risk warnings
- Weekly / goal progress

User information required:
- Final approval of the daily brief format
- Feedback after using real plans

Depends on:
- F5
- F10

---

## 13. Phase 5 — Build the Planning Product

### Objective

Deliver the first genuinely useful end-to-end version.

### Work to complete

1. Implement deterministic prioritization.
2. Implement capacity calculation.
3. Implement task splitting / session allocation.
4. Incorporate goals and milestones.
5. Generate structured daily plans.
6. Render user-facing daily briefs.
7. Optionally write flexible work blocks to calendar.
8. Add daily n8n trigger.

### Completion criteria

Without premium AI, the system can:
- Refresh state,
- read the calendar,
- prioritize current work,
- produce a realistic daily plan,
- explain major risk conditions.

This is the first major MVP.

---

## 14. F12 — AI Router, Validator, and Premium AI Jobs

Purpose:
- Use models selectively without making the system dependent on any one model.

Execution levels:

### Level 0
No AI.

### Level 1
Cheap / normal API or local model for:
- Classification
- Extraction
- Simple normalization
- Basic decomposition

### Level 2
Premium manual ChatGPT Work / Codex for:
- Weekly strategic replanning
- Multi-week conflict resolution
- Complex course modeling
- Architecture changes
- Difficult reconciliation

AI outputs should normally be structured proposals, not direct database mutations.

Pipeline:

```text
AI Job
↓
Executor
↓
Structured proposal
↓
Validator
↓
Accepted state change
```

User information required:
- Rough API cost tolerance
- Which operations deserve premium reasoning
- When manual ChatGPT execution is acceptable

Depends on:
- Stable schemas
- Planner
- State store

---

## 15. Phase 6 — Add AI Selectively

### Objective

Improve quality without turning AI into a hidden dependency.

### Work to complete

1. Define AI Job schema.
2. Implement AI Router.
3. Connect one low-cost model path.
4. Add structured output validation.
5. Add manual premium-job export/import path for ChatGPT Work.
6. Use Codex for system development rather than normal life planning.
7. Add token/cost logs where automated APIs are used.

### Completion criteria

- Swapping a model does not require redesigning the database.
- AI failure does not corrupt canonical state.
- Basic daily planning still works when all AI services are unavailable.

---

## 16. F13 — State Reconciliation / Recovery

Although the project has twelve main user-facing capability groups, recovery is treated as a cross-cutting operational feature and must be implemented explicitly.

Purpose:
- Recover after several days of inactivity or missed updates.

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
Detect ambiguous or overdue tasks
↓
Ask user only for unresolved high-impact facts
↓
Restore trusted state
↓
Replan next 7–14 days
```

User information required:
- Which unknowns may be inferred
- Which changes require confirmation
- How aggressively the system may mark tasks completed/obsolete

Depends on:
- All relevant connectors
- State confidence metadata
- Planner

---

## 17. F14 — History and Self-Correction

This is another cross-cutting later-stage capability rather than a separate initial product requirement.

Purpose:
- Improve estimates based on observed behavior.

Examples:
- Estimated vs actual duration
- Planned vs completed sessions
- Course-specific underestimation
- Time-of-day completion patterns
- Repeated postponements

User information required:
- Actual completion status
- Actual duration when available
- Corrections when inferred history is wrong

Depends on:
- WorkSession history
- Stable task types
- Planner

---

## 18. Phase 7 — Reliability and Long-Term Learning

### Objective

Make the system resilient and increasingly personalized.

### Work to complete

1. Implement reconciliation after inactivity.
2. Add stale / trusted / unknown / conflicted state.
3. Add periodic full synchronization in addition to event-driven updates.
4. Implement weekly review.
5. Record estimated vs actual work.
6. Calibrate duration estimates.
7. Detect chronic backlog and unrealistic plans.
8. Improve planner parameters from history.

### Completion criteria

The system can be ignored for several days, recover, and generate a trustworthy new plan without requiring a full manual rebuild.

---

## 19. Ordered Milestones

### M0 — Planning repository prepared

Already complete:
- Architecture plan exists.
- `formats/input/` exists.
- `formats/output/` exists.
- n8n-only workflow decision is recorded.

### M1 — User model complete

Need:
- Current courses
- Recurring exercise
- Life/other recurring obligations
- Per-course task characteristics

Deliverables:
- Domain taxonomy
- Course/activity profiles

### M2 — Task and I/O contracts complete

Need:
- Real task examples
- Natural-language input examples
- Desired daily output examples

Deliverables:
- Task schema
- Task lifecycle
- Input specification
- Output specification

### M3 — Persistent-state prototype

Deliverables:
- PostgreSQL
- Long-term config files
- Manual CRUD
- Basic daily brief

### M4 — Calendar-aware prototype

Need:
- Timetable
- Training
- Calendar preferences

Deliverables:
- Calendar integration
- Free/busy calculation
- Calendar-aware daily brief

### M5 — Automated collection

Need:
- Email rules
- Learning-platform access / page structure

Deliverables:
- n8n workflows
- Email connector
- Learning-platform connector
- Deduplication and provenance

### M6 — Planning MVP

Need:
- Personal scheduling rules
- Daily-load preferences

Deliverables:
- Deterministic Planner
- Daily plan
- Scheduled daily generation

### M7 — AI-enhanced planner

Need:
- Cost policy
- Premium-vs-cheap task policy

Deliverables:
- AI Router
- Validator
- Manual ChatGPT premium-job workflow

### M8 — Resilient long-term system

Need:
- Real-world usage feedback

Deliverables:
- Reconciliation
- Weekly review
- Historical calibration
- Self-correction

---

## 20. Current Next Action

The project is currently at **M0 → M1**.

Do not begin PostgreSQL, n8n workflow construction, scraping, or planner coding yet.

The next work session should collect and model the user's current semester courses and recurring activities.

Recommended immediate sequence:

1. List all current courses and recurring non-course commitments.
2. Model one representative course in detail.
3. Use that course to refine the course-profile schema.
4. Apply the schema to the remaining courses.
5. Collect several real tasks and use them to design the Task model.
6. Then finalize the input and output formats.

This is the shortest path to a stable foundation and minimizes later rework.
