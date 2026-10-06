# WhatToDo — Accepted Decisions Register

> Canonical record of user-approved product and architecture decisions.
> Do not silently reverse these decisions. If the user changes one, mark the old decision superseded and record the new decision.

## Decision Format

Each decision contains:
- ID
- Status
- Decision
- Rationale / implications
- Documents affected

---

## D-001 — Project type

Status: Accepted

Decision:
WhatToDo is a long-lived personal task and schedule operating system, not a basic to-do list.

Implications:
- Must model tasks, time, goals, sources, progress, preferences, and history.
- Daily plan is an output of maintained state, not the sole state itself.

Affected:
- PROJECT_PLAN
- DEVELOPMENT_PLAN
- DATA_MODEL_PLAN
- PLANNER_PLAN

---

## D-002 — Top-level domains

Status: Accepted

Decision:
Initial domains are:
- Study / academics
- Exercise / sports
- Life administration
- Other

Implications:
- Academic work supports deeper course-specific modeling.
- Taxonomy may later gain subcategories without changing these initial top-level domains.

---

## D-003 — Orchestration platform

Status: Accepted

Decision:
Use n8n as the sole workflow/orchestration platform.

Dify is out of scope unless the user explicitly reverses this decision.

Implications:
- Do not add Dify deployment/configuration.
- AI model routing belongs in custom AI Router/application logic, orchestrated by n8n where appropriate.

Affected:
- PROJECT_PLAN
- DEVELOPMENT_PLAN
- INTEGRATION_PLAN
- OPERATIONS_PLAN
- AI_EXECUTION_PLAN

---

## D-004 — Dynamic state store

Status: Accepted planning direction

Decision:
Use PostgreSQL as the intended canonical dynamic operational state store.

Implications:
- Tasks, progress, deadlines, source records, sync state, plans, and work sessions belong in structured dynamic storage.
- Exact SQL schema is deferred until Phase 2.

Affected:
- DATA_MODEL_PLAN
- OPERATIONS_PLAN

---

## D-005 — Stable declarative memory

Status: Accepted

Decision:
Do not rely on ChatGPT conversation memory as canonical project/user memory.

Use explicit version-controlled configuration such as YAML/JSON for stable declarative knowledge.

Implications:
- Course profiles, preferences, routines, and rules must eventually be explicit repository-backed data/configuration.
- Dynamic state still belongs in PostgreSQL.

---

## D-006 — Calendar role

Status: Accepted

Decision:
Calendar represents time occupancy and scheduling, not canonical task truth.

Preferred automation backend is Google Calendar. Apple Calendar may remain the user's everyday client.

Implications:
- Deadlines remain task metadata even if optionally rendered as calendar events.
- Flexible planned work blocks are distinguishable from fixed events.

Affected:
- DATA_MODEL_PLAN
- INTEGRATION_PLAN
- PLANNER_PLAN

---

## D-007 — AI architecture

Status: Accepted

Decision:
AI is a replaceable execution layer, not the source of truth.

Implications:
- Model providers must be swappable.
- Deterministic logic is preferred where sufficient.
- AI output normally becomes a structured proposal/patch.
- Validation occurs before trusted state mutation.

Affected:
- AI_EXECUTION_PLAN
- DATA_MODEL_PLAN
- PLANNER_PLAN
- TESTING_PLAN

---

## D-008 — AI cost tiers

Status: Accepted

Decision:
Use three practical execution classes:
- Level 0: no AI / deterministic code
- Level 1: cheap or normal automated model
- Level 2: premium reasoning when quality is worth the cost

Implications:
- High-frequency trivial work should not consume premium tokens.
- Model choice is runtime policy, not data architecture.

---

## D-009 — ChatGPT Plus usage

Status: Accepted

Decision:
Do not treat ChatGPT Plus as an API backend and do not automate the ChatGPT web UI as a substitute for API access.

Use ChatGPT Work/Codex as human-triggered premium workers.

Implications:
- Work is suited to complex planning/reconciliation.
- Codex is suited to repository/system development.
- Manual premium AI jobs need export/import or equivalent structured handoff.

---

## D-010 — GitHub role

Status: Accepted

Decision:
GitHub is the canonical source repository.

Local development and cloud runtime are complementary.

Implications:
- Final runtime must not depend on the user's personal laptop staying online.
- Plans/config/code should be version-controlled where appropriate.

---

## D-011 — Recovery after inactivity

Status: Accepted

Decision:
State reconciliation is a first-class capability.

Implications:
- Missed push/webhook events must not permanently corrupt state.
- System needs stale/conflict semantics and periodic reconciliation.
- Several days of inactivity should be recoverable without rebuilding everything manually.

---

## D-012 — Development order

Status: Accepted

Decision:
Define semantic/domain and I/O contracts before database implementation, connectors, planner, or AI infrastructure.

Implications:
- Alignment Gate A0 is the current prerequisite before user/course modeling.
- After A0, M1 user/course modeling begins.
- Starting n8n/PostgreSQL/scraping before Phase 1 completion is intentionally deferred.

Authority:
- Detailed order is in `DEVELOPMENT_PLAN.md`.


---

## D-013 — Pre-development alignment gate

Status: Accepted

Decision:
Before collecting the full domain model or starting implementation, complete an explicit interaction and information-model alignment stage (Alignment Gate A0).

The user and AI must align on:
- development interaction mode
- module meanings
- information granularity
- cross-module effects
- stable vs dynamic vs inferred information
- which questions must be answered now vs deferred

Implications:
- M1 does not begin until A0 is accepted.
- Infrastructure work must not begin before semantic alignment.
- `ALIGNMENT_PLAN.md` is authoritative for this gate.

Affected:
- README
- DEVELOPMENT_PLAN
- PROGRESS
- USER_MODEL_PLAN
- DATA_MODEL_PLAN
- IO_CONTRACT_PLAN

---

## D-014 — Semantic contracts before provider adapters

Status: Accepted

Decision:
Define WhatToDo's internal semantic needs before provider-specific interface mappings, but defer details that can only be known after real integration.

Example:
For Calendar, define concepts such as fixed/flexible event, busy interval, recurrence, ownership, and availability now; define Google Calendar field mapping, event IDs, sync tokens, webhook behavior, and provider edge cases during actual Calendar integration.

Implications:
- Do not invent API-specific fields during early planning.
- Calendar/email/learning-platform adapter contracts are later-phase deliverables.
- Discoveries during integration should update semantic plans only when they change internal meaning, not merely external field mapping.

Affected:
- ALIGNMENT_PLAN
- IO_CONTRACT_PLAN
- INTEGRATION_PLAN
- DEVELOPMENT_PLAN


---

## D-015 — Twice-daily normal interaction cadence

Status: Accepted

Decision:
Normal operation uses two short user interactions per day:
- morning: reconcile/update state and generate the daily plan;
- evening: confirm completion/non-completion, actual effort, and update state/history.

Expected interaction time is roughly 5–10 minutes each.

If interactions are missed, automated collection may continue and the next interaction performs reconciliation.

Affected:
- A0_USER_INTENT
- IO_CONTRACT_PLAN
- PLANNER_PLAN
- DATA_MODEL_PLAN
- DEVELOPMENT_PLAN

---

## D-016 — Uncertainty must wait for confirmation

Status: Accepted

Decision:
Uncertain information must not be silently committed as trusted state.

Store uncertain evidence as candidate/pending confirmation and batch it into a normal user interaction for resolution.

Affected:
- DATA_MODEL_PLAN
- IO_CONTRACT_PLAN
- INTEGRATION_PLAN
- TESTING_PLAN

---

## D-017 — Task difficulty is multi-dimensional

Status: Accepted

Decision:
At minimum, task difficulty conceptually distinguishes:
- thinking depth;
- repetitive volume;
- new-learning load.

Do not collapse these into one generic user-facing difficulty field by default.

Exact scales are deferred to detailed task/course modeling.

Affected:
- USER_MODEL_PLAN
- DATA_MODEL_PLAN
- PLANNER_PLAN

---

## D-018 — Planner recommends workload, not an exact timetable by default

Status: Accepted

Decision:
Daily planning should estimate usable free time and recommend a realistic workload, including which work belongs in large uninterrupted blocks versus fragmented time.

The normal user-facing plan should not assign exact clock times to every task.

Affected:
- PLANNER_PLAN
- IO_CONTRACT_PLAN

---

## D-019 — Historical actual effort informs future estimates

Status: Accepted

Decision:
Record actual task effort where available and use historical completion data to improve future estimates for similar tasks, course/task types, and user estimation bias.

Affected:
- DATA_MODEL_PLAN
- PLANNER_PLAN
- DEVELOPMENT_PLAN

---

## D-020 — Completion evidence is advisory until confirmed

Status: Accepted

Decision:
The evening user review is the primary completion confirmation mechanism.

External signals may suggest that a task is completed, but if the user has not confirmed it the system should ask for confirmation rather than silently mark completion.

Affected:
- DATA_MODEL_PLAN
- INTEGRATION_PLAN
- IO_CONTRACT_PLAN
- TESTING_PLAN

---

## D-021 — Dedicated per-course/task-type decomposition presets

Status: Accepted

Decision:
Task decomposition depth is not universal. A dedicated modeling milestone must define decomposition presets per course/task class, including stage structure, difficulty dimensions, effort/session characteristics, and extensibility.

Affected:
- DEVELOPMENT_PLAN
- USER_MODEL_PLAN
- DATA_MODEL_PLAN
- PLANNER_PLAN

---

## D-022 — Dedicated long-term-goal onboarding

Status: Accepted

Decision:
Creating a long-term goal triggers a dedicated setup interaction defining target, total workload, recurring/daily work, milestones/phases, progress measurement, and task-generation rules.

Only after setup should goal work be automatically integrated into daily planning.

Affected:
- DEVELOPMENT_PLAN
- DATA_MODEL_PLAN
- IO_CONTRACT_PLAN
- PLANNER_PLAN

---

## D-023 — Exception-driven explanation style

Status: Accepted

Decision:
Routine user-facing plans should remain concise. Expanded explanation is primarily for abnormal, risky, uncertain, surprising, or major-replanning situations, or when the user explicitly asks why.

Affected:
- IO_CONTRACT_PLAN
- PLANNER_PLAN


---

## D-024 — Morning and evening interaction shape

Status: Accepted

Decision:
Morning interaction order is:
1. reconcile newly collected information;
2. present confirmation items;
3. ask a guided question about today's special circumstances;
4. apply user corrections/special requirements;
5. estimate usable free time;
6. generate the daily plan.

Evening review should present all routine questions in one consolidated prompt and only ask follow-up questions when the response is incomplete or ambiguous.

Affected:
- A0_USER_INTENT
- IO_CONTRACT_PLAN
- TESTING_PLAN

---

## D-025 — Primary task completion is binary

Status: Accepted

Decision:
At the parent Task level, a task is COMPLETE or INCOMPLETE.

Partial work does not create a third canonical completion state. Instead, incomplete tasks retain:
- cumulative actual time invested;
- latest estimated remaining effort.

If the user reports incomplete work without remaining-effort information, the system should request it.

Affected:
- DATA_MODEL_PLAN
- IO_CONTRACT_PLAN
- PLANNER_PLAN

---

## D-026 — Parent task owns deadline; task type owns default decomposition

Status: Accepted

Decision:
The parent Task represents the external obligation and owns the overall deadline.

Detailed execution uses stages/subtasks.

Each normal task type should have a stable decomposition template. If a substantially different workflow is needed, prefer adding a new task type/template rather than mutating the normal template ad hoc.

Affected:
- USER_MODEL_PLAN
- DATA_MODEL_PLAN
- DEVELOPMENT_PLAN
- PLANNER_PLAN

---

## D-027 — Procrastination is primarily learned behavior

Status: Accepted

Decision:
Do not require the user to pre-score psychological resistance for every task.

Estimate procrastination/resistance mainly from historical behavior, while distinguishing delay caused by insufficient capacity from delay despite available opportunity.

Affected:
- DATA_MODEL_PLAN
- PLANNER_PLAN
- DEVELOPMENT_PLAN

---

## D-028 — Normal daily buffer target

Status: Accepted

Decision:
Under normal conditions, preserve approximately 40–60 minutes of unallocated/rest capacity per day.

This is a soft target, not a hard limit. It may shrink during exam sprints or other explicitly high-intensity periods when deadline/goal safety requires more work.

Affected:
- PLANNER_PLAN
- TESTING_PLAN

---

## D-029 — All new canonical tasks require user review

Status: Accepted

Decision:
External systems and detectors may create candidate tasks, but newly discovered task-like content must be reviewed by the user before becoming canonical Task state.

This applies even when the source appears clear.

Affected:
- IO_CONTRACT_PLAN
- DATA_MODEL_PLAN
- INTEGRATION_PLAN
- TESTING_PLAN

---

## D-030 — Urgent notifications may bypass the normal twice-daily cadence

Status: Accepted

Decision:
The system may proactively notify the user outside morning/evening interactions when projected remaining required effort is close to or exceeds remaining usable capacity before a deadline.

Exact channels and thresholds are deferred.

Affected:
- PLANNER_PLAN
- INTEGRATION_PLAN
- OPERATIONS_PLAN
- IO_CONTRACT_PLAN

---

## D-031 — Multi-horizon capacity forecasting

Status: Accepted

Decision:
Planner risk analysis should compare expected required work against usable free time over at least:
- 1 day;
- 3 days;
- 7 days.

This comparison should influence early work advancement, risk warnings, and emergency behavior.

Affected:
- PLANNER_PLAN
- DATA_MODEL_PLAN
- TESTING_PLAN

---

## D-032 — Time and long-horizon feasibility are primary optimization criteria

Status: Accepted

Decision:
Planner load is measured primarily by estimated work time and suitability for available blocks, not by task count.

The optimization target is long-term feasibility and deadline safety, not maximizing daily checklist completion percentage.

Affected:
- PLANNER_PLAN
- TESTING_PLAN


---

## D-033 — Canonical personal task-state mutations require user confirmation by default

Status: Accepted

Decision:
Automated systems may ingest raw evidence and create candidates, but meaningful mutations to canonical personal task state should not be committed without user confirmation.

This includes, by default:
- creating a task;
- changing a task's interpreted deadline;
- changing completion state;
- changing user progress/remaining-effort facts;
- other consequential task-state corrections.

Raw external source records may update automatically because they record what the source said, not the user's accepted operational truth.

A future exception may only be introduced through an explicit user-approved policy.

Affected:
- A0_USER_INTENT
- DATA_MODEL_PLAN
- IO_CONTRACT_PLAN
- INTEGRATION_PLAN
- TESTING_PLAN


---

## D-034 — Task is the fundamental planning unit

Status: Accepted

Decision:
Task is the fundamental operational/planning unit.

Course, study/exercise/life domains, and similar layers are contextual classifications for understanding, grouping, defaults, and generation.

Planning-relevant difficulty, effort, importance, requiredness, and completion are primarily Task properties or TaskType defaults.

Affected:
- USER_MODEL_PLAN
- DATA_MODEL_PLAN
- PLANNER_PLAN
- DEVELOPMENT_PLAN

---

## D-035 — Course importance is not a primary planning variable

Status: Accepted

Decision:
Do not use Course importance as a primary Planner input.

Importance and requiredness should be expressed on Tasks, Goals, Exams, or generated work.

Affected:
- USER_MODEL_PLAN
- DATA_MODEL_PLAN
- PLANNER_PLAN

---

## D-036 — Importance and requiredness are separate

Status: Accepted

Decision:
Task importance and whether the task must ultimately be completed are separate dimensions.

A deadline does not imply requiredness.

Examples include optional exercises that expire after class.

Affected:
- DATA_MODEL_PLAN
- PLANNER_PLAN
- USER_MODEL_PLAN

---

## D-037 — Three-dimensional difficulty uses 1–5 task-level scales

Status: Accepted

Decision:
Thinking depth, repetitive volume, and new-learning load each use a 1–5 scale.

TaskType templates define defaults; concrete Tasks inherit and may override them.

Affected:
- USER_MODEL_PLAN
- DATA_MODEL_PLAN
- PLANNER_PLAN

---

## D-038 — Course Progress Axis

Status: Accepted

Decision:
Each academic course should support an instructional progress axis.

Tasks and exams may attach to semantic positions/ranges such as:
- before lesson N;
- during lesson N;
- after lesson N;
- lessons A–B.

The axis supports prerequisites, review generation, backlog tracking, and exam coverage.

Affected:
- USER_MODEL_PLAN
- DATA_MODEL_PLAN
- PLANNER_PLAN
- DEVELOPMENT_PLAN

---

## D-039 — Exam is an independent event/object

Status: Accepted

Decision:
An exam is not a normal Task.

It is an independent course-linked event/object with coverage on the Course Progress Axis. Exam preparation is generated as Tasks/Goals.

Affected:
- DATA_MODEL_PLAN
- USER_MODEL_PLAN
- PLANNER_PLAN

---

## D-040 — Three risk states

Status: Accepted

Decision:
Use SAFE, DANGER, and EMERGENCY as the high-level feasibility/risk vocabulary.

Exact thresholds are deferred.

Affected:
- PLANNER_PLAN
- IO_CONTRACT_PLAN
- TESTING_PLAN

---

## D-041 — Weekly learned-pattern review with user confirmation

Status: Accepted

Decision:
Historical behavior/estimation analysis may run automatically on a weekly cadence and may also be invoked manually.

Material learned rules that change Planner behavior should be presented to the user for confirmation before becoming accepted.

Planner consumes accepted learned rules; pattern discovery belongs to a separate learning/analyzer module.

Affected:
- LEARNING_PLAN
- DATA_MODEL_PLAN
- PLANNER_PLAN
- DEVELOPMENT_PLAN

---

## D-042 — Explicit user rule wins over unconfirmed learned behavior

Status: Accepted

Decision:
When historical behavior appears to conflict with an explicit user rule/preference, present the evidence and recommend a change, but do not silently override the user rule.

Affected:
- LEARNING_PLAN
- PLANNER_PLAN


---

## D-043 — Task importance uses a 1–5 scale

Status: Accepted

Decision:
Task importance is an integer from 1 to 5.

Importance is separate from requiredness and influences ordering/protection/sacrifice decisions.

Affected:
- DATA_MODEL_PLAN
- PLANNER_PLAN
- USER_MODEL_PLAN

---

## D-044 — Requiredness has REQUIRED / OPTIONAL / EXPIRING

Status: Accepted

Decision:
Use:
- REQUIRED
- OPTIONAL
- EXPIRING

EXPIRING must carry an expiration point/condition. Deadline and expiration are distinct.

Affected:
- DATA_MODEL_PLAN
- USER_MODEL_PLAN
- PLANNER_PLAN

---

## D-045 — No generic lead-time field; use safe-capacity advancement

Status: Accepted

Decision:
Do not rely on a generic "start this task N days early" property.

After protecting required work, if the plan remains SAFE and usable capacity remains, advance future REQUIRED work to build slack.

Affected:
- PLANNER_PLAN
- DATA_MODEL_PLAN

---

## D-046 — TaskType defaults inherit automatically

Status: Accepted

Decision:
TaskType configuration stores default planning properties such as three-dimensional difficulty.

Concrete Tasks inherit defaults without per-task reconfirmation; exceptional tasks may override them.

Affected:
- USER_MODEL_PLAN
- DATA_MODEL_PLAN

---

## D-047 — Course progress units are course-defined

Status: Accepted

Decision:
A Course Progress Axis uses course-defined units such as lecture, chapter, experiment, topic, or another suitable unit.

Track both teaching progress and task-family progress along the axis.

Affected:
- USER_MODEL_PLAN
- DATA_MODEL_PLAN

---

## D-048 — Default academic dependency templates

Status: Accepted

Decision:
Course/task templates may predefine dependency flows such as:
preview → class → note organization → homework/exercise.

Concrete tasks inherit the template unless explicitly overridden.

Affected:
- USER_MODEL_PLAN
- DATA_MODEL_PLAN

---

## D-049 — Initial conditional review triggers

Status: Accepted

Decision:
Initial review/catch-up activation includes:
- three consecutive incomplete post-class note-organization tasks;
- entry into an exam-preparation/sprint phase.

Additional course-specific triggers may be configured later.

Affected:
- USER_MODEL_PLAN
- DATA_MODEL_PLAN
- PLANNER_PLAN

---

## D-050 — Worst-horizon risk aggregation

Status: Accepted

Decision:
Report 1-day, 3-day, and 7-day risk separately.

Overall mode equals the most severe horizon:
EMERGENCY > DANGER > SAFE.

Any DANGER horizon places the overall plan in DANGER unless another horizon is EMERGENCY.

Affected:
- PLANNER_PLAN
- IO_CONTRACT_PLAN
- TESTING_PLAN

---

## D-051 — Normal confirmation sessions clear the whole queue

Status: Accepted

Decision:
Morning/evening reviews should attempt to resolve all pending confirmation items in that interaction.

Items may be ordered by impact for readability, but lower-impact confirmations should not normally be left for later.

Affected:
- IO_CONTRACT_PLAN
- TESTING_PLAN

---

## D-052 — Confirmation prompts may include recommended answers

Status: Accepted

Decision:
Where responsible, present a recommended interpretation/template so the user can confirm or modify it rather than manually reconstructing the record.

Affected:
- IO_CONTRACT_PLAN
- formats/output

---

## D-053 — Daily Brief baseline structure

Status: Accepted

Decision:
Daily Brief includes usable free time, 1/3/7-day risk, overall mode, required work, future work to advance, concrete stages/subtasks, estimated effort, block/fragment guidance, and concise abnormal notes.

Show deadlines by default when within 3 days, risky, or requested.

Concrete template:
- formats/output/DAILY_BRIEF_TEMPLATE.md

Affected:
- IO_CONTRACT_PLAN
- PLANNER_PLAN
- TESTING_PLAN

---

## D-054 — Numeric prediction models may learn automatically

Status: Accepted

Decision:
Internal numeric effort-estimation models may update automatically from historical data if they remain testable, inspectable when needed, and correctable.

Behavioral/planning rules still require user confirmation before adoption.

Affected:
- LEARNING_PLAN
- DATA_MODEL_PLAN
- PLANNER_PLAN

---

## D-055 — Two-day missed-interaction reminder

Status: Accepted

Decision:
After two consecutive days without a normal user interaction, proactively remind the user to perform state reconciliation/update.

Urgent deadline-feasibility alerts remain separate and may trigger earlier.

Affected:
- OPERATIONS_PLAN
- IO_CONTRACT_PLAN

---

## D-056 — Long-term goal onboarding minimum fields

Status: Accepted

Decision:
Long-term goal onboarding includes:
- goal definition;
- target/end date;
- total workload/measurable quantity;
- desired outcome/quality;
- phases/milestones where useful;
- preferred recurring/daily allocation;
- required vs adjustable components.

The system proposes decomposition; the user reviews it before activation.

Affected:
- DEVELOPMENT_PLAN
- DATA_MODEL_PLAN
- PLANNER_PLAN
- IO_CONTRACT_PLAN

---

## D-057 — Goal-generated tasks are ordinary Planner tasks

Status: Accepted

Decision:
After approved generation, Tasks originating from long-term goals enter Planner on equal footing with other Tasks. Source does not give special scheduling privilege.

Affected:
- DATA_MODEL_PLAN
- PLANNER_PLAN

---

## D-058 — Automatic analysis vs reviewed truth/policy boundary

Status: Accepted

Decision:
Automatic:
- raw evidence ingestion;
- candidate generation;
- risk/capacity calculation;
- numeric effort prediction and internal model learning;
- historical pattern calculation;
- daily plan proposals;
- recommended confirmation templates.

User review required:
- canonical Task facts;
- completion/progress/remaining-effort facts;
- explicit preferences;
- behavioral/planning rules;
- consequential long-term planning activation.

Affected:
- A0_USER_INTENT
- DATA_MODEL_PLAN
- IO_CONTRACT_PLAN
- LEARNING_PLAN
- PLANNER_PLAN
