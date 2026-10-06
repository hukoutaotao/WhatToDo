# WhatToDo — Project Planning Document

> Planning control center: read `plan/README.md` first in a new AI session.  
> Current state: read `plan/PROGRESS.md`.  
> Accepted decisions: read `plan/DECISIONS.md`.

> Status: Planning phase  
> Intended audience: AI agents and future maintainers  
> Repository: `hukoutaotao/WhatToDo`  
> Primary purpose: Preserve the evolving architecture, design constraints, assumptions, and decisions for a long-lived personal task and schedule management system.

---

## 1. Project Vision

WhatToDo is intended to become a long-term personal planning system for a university student. Its purpose is not merely to store a to-do list, but to continuously maintain an up-to-date model of the user's obligations, goals, available time, workload, preferences, and current progress, then produce a concrete daily action plan.

The system should reduce the cognitive cost of planning. The user should not need to repeatedly reconstruct what is urgent, what is due, what still needs to be done, or how much time is available.

The desired end state is:

1. The system continuously collects relevant information from trusted sources.
2. It maintains structured long-term knowledge about courses, recurring responsibilities, exercise, life tasks, goals, and preferences.
3. It maintains dynamic state about current tasks, deadlines, progress, workload, schedule, and recent changes.
4. It reconciles stale state after periods of inactivity.
5. It plans across multiple horizons: today, the coming week, and long-term milestones.
6. It produces a daily checklist / daily brief in a consistent user-defined format.
7. It can use different AI models depending on cost and reasoning requirements.
8. It does not depend on any one LLM vendor or model for correctness.
9. It remains maintainable through GitHub, versioned configuration, database state, and modular connectors.

---

## 2. User Life Domains

All tracked work should initially be categorized into four top-level domains:

- Study / academics
- Exercise / sports
- Life administration
- Other

Academic work is the most structurally complex domain and must support per-course configuration.

Examples of course-specific task types may include:

- Pre-class preview
- Pre-lab preparation report
- Post-class note organization
- Homework
- Lab
- Programming assignment
- Reading
- Review
- Exam preparation
- Long-term project

Each course may differ in:

- Cognitive difficulty
- Workload / volume
- Typical task duration
- Preferred time of day
- Required continuity / minimum useful session length
- Recurring task structure
- Release schedule
- Deadline pattern
- Exam importance
- Dependency between subtasks

The system must represent these differences explicitly instead of treating all tasks as equivalent.

---

## 3. Core Architectural Principle

The system must distinguish among:

- Knowledge
- Dynamic state
- Raw sources
- History / learned behavior
- Calendar occupancy
- Planning logic
- AI reasoning

The central rule is:

> AI is not the database.  
> Calendar is not the task database.  
> LLM output is not trusted state until validated.

The source of truth for current operational state should be a structured database.

---

## 4. Proposed High-Level Architecture

```text
Information Sources
├── User input
├── Calendar
├── Email
├── Learning platform / Web Learning
├── Future connectors
│
▼
Collectors / Connectors
│
▼
Automation / Orchestration Layer
(n8n only)
│
▼
PostgreSQL
(Source of Truth)
│
├── Current state
├── Tasks
├── Deadlines
├── Events
├── Goals
├── Source provenance
├── Sync metadata
├── Historical execution data
│
▼
Planner Core
│
├── Deterministic constraints
├── Priority calculation
├── Capacity calculation
├── Goal decomposition
├── Scheduling logic
│
▼
AI Router / AI Job Layer
│
├── No-AI deterministic path
├── Cheap / normal model path
├── Premium human-triggered ChatGPT path
│
▼
Structured Patch / Proposal
│
▼
Validator
│
▼
Database
│
▼
Daily Plan / Weekly Plan / Alerts
```

---

## 5. Workflow Platform Decision: n8n Only

### Decision

Use **n8n as the sole workflow / orchestration platform** for WhatToDo.

Dify is explicitly out of scope and should not be introduced into the architecture unless the user later reverses this decision.

### Responsibilities of n8n

The core system needs to coordinate:

- Scheduled workflows
- Calendar synchronization
- Email ingestion
- HTTP requests
- Database reads/writes
- Webhooks
- Learning-platform scraping / polling
- Background jobs
- Trigger-based actions
- Calling internal services
- Notifications
- Invoking low-cost AI APIs when needed
- Passing standardized AI jobs to the project's AI Router

n8n is the system's orchestration layer. AI-specific logic that should remain portable across model providers belongs in the custom AI Router / application code rather than in a separate AI workflow platform.

This keeps the deployment and operational model simpler and avoids maintaining overlapping workflow systems.

---

## 6. AI Must Be a Replaceable Execution Layer

The project should contain an explicit AI abstraction / routing layer.

The system must not assume one permanent model such as GPT, Claude, Gemini, Qwen, or a local model.

Each AI job should use a standardized input/output contract.

Possible execution classes:

### Level 0 — No AI

Use deterministic code for tasks such as:

- Date arithmetic
- Deadline comparison
- Calendar conflict detection
- Database queries
- Detecting stale records
- Page diffing
- Sync logic
- Fixed scheduling constraints
- Capacity calculation

Cost target: effectively zero.

### Level 1 — Cheap / Normal AI

Use for high-volume, low-risk language tasks such as:

- Email classification
- Extracting a deadline from an announcement
- Mapping text to a known course
- Converting raw announcements into structured candidate tasks
- Summarizing recent changes
- Basic task decomposition

Possible backends:

- Low-cost API model
- OpenAI-compatible provider
- Local model

### Level 2 — Premium Reasoning AI

Use only when higher reasoning quality is valuable:

- Semester-level planning
- Multi-week workload balancing
- Replanning around several conflicting deadlines
- Creating a new course workload model
- Designing task templates
- Complex state reconciliation
- Reviewing system architecture

Premium jobs should be infrequent.

---

## 7. ChatGPT Plus / Work / Codex Integration Strategy

ChatGPT Plus should not be treated as an API credential source.

The project should not attempt to automate the ChatGPT website or simulate API calls through the subscription.

Instead, ChatGPT Work and Codex should be modeled as **human-triggered premium AI workers**.

### Work

Best suited for operating on the user's real task state, such as:

- Weekly review
- Multi-week replanning
- Complex reconciliation
- High-level study strategy
- Reviewing collected task data
- Interpreting ambiguous changes

### Codex

Best suited for changing the system itself:

- Implementing connectors
- Modifying schemas
- Writing planner logic
- Debugging
- Adding tests
- Refactoring
- Updating deployment code

### AI Job Queue

The system should be able to create pending jobs such as:

```text
job_type: WEEKLY_REPLAN
priority: HIGH
executor_class: PREMIUM_MANUAL
reason: Three major deadlines changed
context_ref: state_snapshot_2026_10_03
expected_output_schema: planning_patch_v1
```

The user can later open Work or Codex and explicitly process that job using the subscription's available model quota.

This keeps ChatGPT subscription usage separate from automated API cost.

---

## 8. Structured AI Output

LLMs should not directly mutate database state whenever avoidable.

Instead, models should emit structured proposals / patches.

Example:

```json
{
  "action": "update_priority",
  "task_id": "DM_HW4",
  "old_priority": 45,
  "new_priority": 72,
  "reason": "Deadline is within 48 hours",
  "confidence": 0.93
}
```

The system should then:

1. Validate schema.
2. Check referenced objects.
3. Check hard constraints.
4. Reject unsafe / contradictory changes.
5. Require user acceptance for canonical Task facts or policy changes unless the resolved explicit user instruction already authorizes that exact change.
6. Apply authorized changes atomically with state-version checks.
7. Log the change and source.

This design is necessary for model portability and reliability.

The numeric priority example is a derived recommendation score, not the Task's user-defined 1–5 importance. Updating a derived score must not silently change canonical importance or remaining effort.

---

## 9. Memory and State Architecture

The project needs several distinct forms of memory.

### 9.1 Long-Term Declarative Knowledge

Examples:

- Course characteristics
- Typical task types
- User preferences
- Sports routines
- Personal planning rules
- Study preferences
- Long-term goal configuration

Recommended storage:

```text
memory/
├── courses/
│   ├── signals.yaml
│   ├── dsa.yaml
│   └── circuits.yaml
├── sports/
├── goals/
├── routines/
└── preferences.yaml
```

These files should be:

- Human-readable
- Version-controlled in Git
- Easy for AI to read
- Explicit rather than inferred from chat history

### 9.2 Dynamic Operational State

Examples:

- Task status
- Deadline
- Progress
- Estimated remaining duration
- Priority
- Last verified time
- Current schedule
- Pending AI jobs
- Current milestone progress

Recommended storage: PostgreSQL.

### 9.3 Raw Source Records

Every extracted fact should retain provenance where practical.

Examples:

- Email message
- Calendar event
- Learning-platform announcement
- User statement
- Scraped assignment page

Important metadata may include:

```text
source_type
source_id
source_timestamp
ingested_at
content_hash
parser_version
confidence
linked_entities
```

The system should preserve the distinction between:

- Original source
- Parsed candidate fact
- Verified state

### 9.4 Historical Execution Data

Track enough history for the system to learn from actual behavior.

Examples:

- Estimated vs actual task duration
- Planned vs completed work
- Time-of-day completion rate
- Repeated postponements
- Course-specific estimation bias
- Task-type estimation bias

This history can later improve planning.

---

## 10. Calendar Strategy

The calendar represents **time occupancy**, not the canonical list of tasks.

Recommended long-term backend: Google Calendar.

The user may continue using the Apple Calendar application as a front end by adding the Google Calendar account.

Reasons for preferring Google Calendar as the automation backend:

- Better API integration
- Read/write access
- Event synchronization
- Easier automation ecosystem
- Change notification support
- Better compatibility with n8n and ChatGPT connectors

The system should distinguish:

- Fixed events: class, training, appointment
- Flexible blocks: planned study sessions
- Deadlines: task metadata, not necessarily calendar events
- Reminders: optional notification layer

Calendar changes must be synchronized back into system state.

---

## 11. Data Collection Sources

### User Input

User input is authoritative when explicitly stated.

The interface should allow natural-language corrections such as:

- "This lab is cancelled."
- "I finished HW3."
- "Move training to Friday."
- "This assignment will take about four hours."

The system should translate these statements into structured updates.

### Email

Potential pipeline:

```text
Email
→ ingest
→ classify
→ extract candidate facts
→ map to course / domain
→ deduplicate
→ preserve candidate / recommend interpretation
→ user confirmation
→ validate authorized change
→ update canonical Task state
```

### Learning Platform / Web Learning

Likely requires a custom connector or scraper.

The connector should be isolated from the planner.

It should expose normalized changes such as:

- New assignment
- Changed deadline
- New announcement
- New exam information
- New file / material

The planner should not know how the site is scraped.

### Calendar

Read both:

- Fixed recurring schedule
- One-off changes

Track changes rather than relying only on full repeated reads.

---

## 12. Reconciliation / Recovery After Inactivity

This is a first-class system feature.

If the system has not been actively maintained for several days, old state must not be assumed correct.

The system should perform state reconciliation.

Proposed flow:

```text
Last trusted state
↓
Detect stale interval
↓
Re-read current calendar
↓
Fetch new email
↓
Fetch learning-platform changes
↓
Re-evaluate deadlines
↓
Detect overdue / ambiguous tasks
↓
Compare against historical task state
↓
Present all pending confirmations, high-impact first; resolve the full queue where possible
↓
Rebuild trusted current state
↓
Replan next 7–14 days
```

Suggested state confidence labels:

- TRUSTED
- STALE
- UNKNOWN
- CONFLICTED

Suggested timestamps:

- last_synced_at
- last_verified_at
- source_updated_at

The project should prefer "eventual correctness" over assuming that webhook delivery is perfect.

Use both:

- Event-driven updates where possible
- Periodic reconciliation

---

## 13. Goal, Milestone, and Task Separation

Long-term goals must not be represented as one large task.

Model hierarchy:

```text
Goal
↓
Milestones
↓
Task generator / recurring plan
↓
Concrete tasks
↓
Scheduled sessions
```

Example:

```text
Goal: English exam in 3 months

Milestones:
- Vocabulary target
- Reading practice target
- Mock exam phase
- Final review phase

Concrete generated tasks:
- Learn 70 words today
- Complete 3 reading passages this week
- Complete one mock exam
```

Goal state and task state must remain separate.

---

## 14. Planner Responsibilities

The planner is deterministic-first and must produce a usable Daily Brief without AI. AI may propose interpretations/decomposition or strategic advice through validation and the accepted confirmation boundary; it is not a required serial step in every planning pass.

### Deterministic planning inputs

- Deadline
- Estimated remaining time
- Current progress
- Available calendar capacity
- Fixed events
- Task dependencies
- Minimum session length
- Task importance (1–5) and REQUIRED / OPTIONAL / EXPIRING; Course is context/defaults
- Exam proximity
- Overdue state
- Long-term milestone requirements

### Optional LLM assistance

- Interpret ambiguous input into candidates for confirmation.
- Propose task decomposition and strategic adjustments.
- Explain exceptional risks concisely.

Difficulty (three 1–5 dimensions), importance, fragmentability, and session defaults are already structured Task/TaskType inputs. AI must not silently infer and overwrite them. Calendar arithmetic, capacity checks, and hard constraints remain deterministic.

### Output should distinguish

- Must do today
- Should do today
- Optional / if time remains
- Fixed events
- Short fragment tasks
- Risk warnings
- Progress against weekly / long-term goals

---

## 15. Daily Workflow

Target daily pipeline:

```text
Collect
↓
Reconcile
↓
Update current state
↓
Generate recurring / goal-driven tasks
↓
Compute urgency and constraints
↓
Compute available capacity
↓
Plan / prioritize
↓
Run AI jobs if needed
↓
Validate proposed changes
↓
Generate Daily Brief
↓
Optionally write flexible study blocks to calendar
```

The accepted conceptual Daily Brief is in `formats/output/DAILY_BRIEF_TEMPLATE.md`; M2 defines the machine schema and refines wording while preserving A0 semantics.

---

## 16. Weekly / Strategic Workflow

A weekly workflow should exist separately from the daily workflow.

Possible responsibilities:

- Review upcoming 2–4 weeks
- Identify exams and large assignments
- Adjust milestone pacing
- Update workload estimates
- Detect persistent backlog
- Compare planned vs actual time
- Create high-level schedule changes
- Create premium AI jobs when necessary

Weekly review is a strong candidate for ChatGPT Work / premium manual execution.

---

## 17. Deployment Philosophy

Target topology:

```text
GitHub repository
├── Source code
├── Versioned configuration
├── Planning docs
└── Long-term declarative memory

Local development environment
├── VS Code
├── Codex
└── Tests

Always-on server / cloud host
├── n8n
├── PostgreSQL
├── planner service
├── connectors
└── scheduled jobs

ChatGPT
├── Design / review
├── Work for premium planning tasks
└── Codex for repository development
```

The final operational system should not depend on the user's laptop being powered on.

GitHub should be the canonical code repository.

---

## 18. Proposed Core Modules

This is a planning-stage module boundary, not final code structure.

### Collector

Responsibilities:

- Receive data from external sources
- Normalize basic metadata
- Preserve provenance

### Reconciler

Responsibilities:

- Detect stale or conflicting state
- Compare source changes
- Restore trusted current state

### State Store

Responsibilities:

- Canonical operational database
- Versioned state changes
- Relationships among entities

### Planner Core

Responsibilities:

- Priority
- Capacity
- Hard constraints
- Scheduling
- Goal progression

### AI Router

Responsibilities:

- Classify AI job requirements
- Route to no-AI / cheap AI / premium manual AI
- Standardize inputs and outputs

### Validator

Responsibilities:

- Validate AI patches
- Enforce hard rules
- Reject malformed or unsafe changes

### Daily Brief Generator

Responsibilities:

- Convert current plan to user-facing daily output
- Use stable formatting

### Historical Learning / Behavior Analyzer

Responsibilities:

- Analyze estimated vs actual effort
- Detect recurring duration bias
- Detect repeated postponement patterns
- Evaluate time-of-day/task-type performance patterns
- Produce candidate learned parameters/rules
- Submit material behavioral rule changes for user confirmation before Planner adoption

This module is distinct from Planner. Planner consumes accepted learned parameters; it does not silently invent and apply behavioral rules.

### Connectors

Initial candidates:

- Calendar
- Gmail / email
- Learning platform
- Manual input

---

## 19. Reliability Principles

1. Do not rely on chat memory as canonical project memory.
2. Do not let AI-generated facts silently overwrite trusted facts.
3. Preserve provenance.
4. Prefer idempotent workflows.
5. All external connectors must be replaceable.
6. All AI providers must be replaceable.
7. Keep collector logic separate from planner logic.
8. Keep task state separate from calendar representation.
9. Keep long-term goals separate from current tasks.
10. Support stale-state recovery from the beginning.
11. Prefer structured output contracts over free-form LLM responses.
12. Store enough audit data to explain why a plan changed.

---

## 20. Cost-Control Principles

The project must explicitly optimize model usage.

Desired order of preference:

1. Deterministic code
2. Cheap / local / low-cost model
3. Medium model
4. Premium manual ChatGPT reasoning

Do not spend premium tokens on:

- Date calculations
- Simple classification where a cheap model performs well
- Repetitive extraction
- Fixed business rules

Premium reasoning should be reserved for decisions where quality materially affects planning.

---

## 21. Initial Technology Direction

Current planning preference:

- Repository: GitHub
- Development: local clone + VS Code + Codex
- Automation: self-hosted n8n
- Database: PostgreSQL
- Calendar backend: Google Calendar
- Calendar UI: Apple Calendar may remain the user's daily interface
- Email: account/provider selection remains deferred until the user confirms relevant accounts; Gmail is a possible adapter, not a selected mandatory backend
- Learning platform: custom connector / scraper
- Planner: custom service, likely Python or TypeScript; not yet finalized
- AI integration: custom AI Router
- Premium reasoning: user-triggered ChatGPT Work / Codex
- Runtime: always-on cloud/VPS/containerized environment

These are current planning decisions, not immutable implementation commitments.

---

## 22. Explicitly Deferred Decisions

Do not prematurely lock down the following:

- Exact PostgreSQL schema
- Exact programming language for the planner
- Exact cloud/VPS provider
- Exact cheap model provider
- Exact notification channel
- Exact machine Daily Plan schema and rendering details (the human semantic template is already accepted)
- Exact scraping method for the learning platform
- Exact priority formula
- Exact scheduling algorithm
- Exact level of automatic calendar writing
- Exact authentication architecture
- Exact provider API field mappings, IDs, sync tokens, webhook/watch behavior, and connector-specific edge cases until the relevant real integration is examined

These should be decided after module boundaries and data contracts are clearer.

---

## 23. Development Order

The authoritative implementation order is maintained in:

`plan/DEVELOPMENT_PLAN.md`

This architecture document defines **what the system is and why it is designed this way**.  
The development plan defines **what to build first, what depends on what, what information the user must provide, and when each capability is considered complete**.

When the two documents appear to differ on implementation order, `DEVELOPMENT_PLAN.md` takes precedence for sequencing. Architectural constraints in this document still apply unless explicitly superseded.

The high-level order is:

0. Align the user-AI interaction model, module meanings, information granularity, cross-module effects, and semantic-vs-adapter boundaries.
1. Define the user's domain model, task model, input contract, and output contract.
2. Build structured memory and canonical state storage.
3. Integrate calendar/time availability and define provider-specific adapter details against the real service.
4. Add automatic external information collection.
5. Build deterministic planning and daily-plan generation.
6. Add AI routing, validation, and premium/manual AI execution.
7. Add recovery, weekly planning, and historical self-correction.

Do not begin later phases merely because their technologies are available. A phase should start only when the data contracts and prerequisites it depends on are stable enough to test end-to-end.

---

## 24. Current Key Decisions Summary

The following decisions are currently considered accepted unless the user later changes them:

- The project is a personal task/schedule operating system, not a basic to-do app.
- n8n is the sole workflow / orchestration platform; Dify is not part of the planned architecture.
- PostgreSQL is the canonical dynamic state store.
- Long-term declarative knowledge should be version-controlled, likely YAML/JSON.
- Calendar represents time occupancy, not task truth.
- Google Calendar is preferred as the automation backend; Apple Calendar may remain the user's client.
- The system requires a first-class reconciliation mechanism after inactivity.
- AI must be replaceable through an AI Router / AI Job abstraction.
- High-frequency easy jobs should use no AI or cheap models.
- High-value complex reasoning can be performed manually through ChatGPT Work / Codex to use ChatGPT Plus capacity.
- ChatGPT Plus is not treated as an API backend.
- AI outputs should normally be structured proposals, validated before modifying canonical state.
- GitHub is the canonical code repository.
- Local development and cloud runtime are complementary, not alternatives.
- The system should eventually run independently of the user's personal computer.
- Alignment Gate A0 must establish shared user-AI understanding before M1 domain collection and before implementation.
- Internal semantic contracts should be aligned before provider-specific adapter mappings; API/node-specific details are deferred until real integration.

---

## 25. Change Policy for This Document

This file is intended to evolve during planning.

When the user reviews a human-readable summary and requests changes:

1. Update the architectural decision in this document.
2. Remove or mark superseded assumptions.
3. Preserve useful rationale when a decision changes.
4. Keep the Current Key Decisions Summary consistent.
5. Avoid allowing stale contradictory decisions to remain silently in different sections.
6. Record major architectural reversals explicitly.

`plan/README.md` is the entry point and authority map. This file is the architecture view; specialized design documents already exist and must be updated together.

---

## 26. Reconciled Runtime Boundaries

The diagram in Section 4 is a module inventory, not a mandatory serial call chain. Canonical personal Task mutations follow evidence/input → candidate/authorized user instruction → review when needed → validator → atomic state/audit update. A clear direct user command can itself provide confirmation; do not ask the same decision twice. Schema validity or high model confidence alone cannot authorize a write.

Planner reads accepted Tasks, accepted rules, derived numeric predictions, and a current availability snapshot. It emits recommendations/plan snapshots without changing completion facts. All three planner horizons share one Task model. Learner is optional: internal numeric model updates may be automatic; behavioral rules require review; canonical user estimates remain separate.

In overall EMERGENCY, show a visibly provisional normal baseline, collect the user's sacrifices/additional capacity, then recompute and return the final plan. Optional removal alone cannot mathematically erase a REQUIRED-work deficit; preserve the residual deficit if it remains.

Goal/recurring/conditional generators emit proposed instances under approved templates. Per-instance canonical activation authority is still open; until settled, the conservative review path applies. Source Calendar updates may refresh occupancy automatically within configured scope without becoming Task progress/completion.

Minimum confirmation, provenance, audit, versioning, staleness, and recovery safeguards belong to persistence/ingestion and the first MVP. Advanced catch-up/weekly learning in Phase 7 extends those foundations. See `CONSISTENCY_AUDIT.md` for unresolved edges and planning inputs.
