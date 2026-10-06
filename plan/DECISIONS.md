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
