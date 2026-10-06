# WhatToDo Plan Control Center

> This directory is the canonical planning and handoff context for AI agents, Codex, and future maintainers.
> A new AI conversation should start here.

## 1. Bootstrap Instructions for a New AI

When taking over this repository:

1. Read this file completely.
2. Read `PROGRESS.md` to learn the current project state and immediate next action.
3. Read `DECISIONS.md` to learn accepted decisions that must not be silently reversed.
4. Read `ALIGNMENT_PLAN.md` to understand the required user-AI interaction model, information granularity rules, and pre-development alignment gate.
5. Read `A0_USER_INTENT.md` for the authoritative interpretation of the user's A0 answers and product-behavior requirements.
6. Read `PROJECT_PLAN.md` for architecture and system boundaries.
7. Read `DEVELOPMENT_PLAN.md` for implementation order and prerequisites.
8. Read only the specialized planning documents relevant to the current task.
9. If the task touches input/output formats, also inspect `../formats/input/` and/or `../formats/output/`.
10. Before making a material change, use the dependency/update rules in this file.
11. After completing work, update `PROGRESS.md` and any affected source-of-truth planning documents.

Do not treat prior chat history as the canonical project state when repository planning documents are available.

---

## 2. Planning File Map

### Core authority files

#### `README.md`
Role:
- Entry point and document map
- Dependency graph
- Change-propagation rules
- New-AI handoff protocol

Authority:
- Highest authority for how planning documents interact and how updates propagate.

#### `DECISIONS.md`
Role:
- Records accepted architectural/product decisions and their status.
- Prevents future agents from casually re-litigating settled choices.

Authority:
- Highest authority for accepted decisions unless the user explicitly reverses one.

#### `CONSISTENCY_AUDIT.md`
Role:
- Records the 2026-10-06 full-document audit, corrections, requirement-to-document coverage, and unresolved boundaries.
- Provides planning input; it is not a new user-policy authority.

#### `PROGRESS.md`
Role:
- Live operational status.
- Current milestone, completed work, active work, next actions, blockers, and pending user input.

Authority:
- Highest authority for "where the project is now."

#### `PROJECT_PLAN.md`
Role:
- System architecture and rationale.
- Defines major modules, boundaries, storage philosophy, reliability principles, and end-state architecture.

Authority:
- Highest authority for architecture unless superseded by a recorded decision.

#### `DEVELOPMENT_PLAN.md`
Role:
- Ordered implementation roadmap.
- Defines phases, dependencies, user inputs, completion criteria, and milestone order.

Authority:
- Highest authority for development sequence.

### Specialized planning files

#### `ALIGNMENT_PLAN.md`
- Defines the pre-development user-AI interaction model and semantic information-alignment process.
- Separates information that must be agreed before implementation from provider-specific details that should be deferred until real integration.
- Defines Alignment Gate A0.

#### `A0_USER_INTENT.md`
- Canonical interpretation of the user's A0 answers.
- Defines the intended twice-daily interaction cadence, uncertainty policy, task/decomposition expectations, difficulty dimensions, time-estimation memory, planner output philosophy, goal onboarding, completion confirmation, and product success criteria.
- Feeds USER_MODEL, DATA_MODEL, IO_CONTRACT, PLANNER, DEVELOPMENT, TESTING, and later implementation.

#### `USER_MODEL_PLAN.md`
- M1 specification for collecting courses, recurring activities, and planning-relevant preferences; it becomes active after A0 is accepted.
- Defines what may become stable declarative user/course profiles.

#### `DATA_MODEL_PLAN.md`
- Conceptual entities, ownership, state lifecycles, source-of-truth rules, Git-vs-PostgreSQL split.
- Does not freeze SQL table definitions before Phase 2.

#### `IO_CONTRACT_PLAN.md`
- Human and machine input/output strategy.
- Governs how the conceptual contracts relate to concrete specifications under `../formats/`.

#### `INTEGRATION_PLAN.md`
- n8n orchestration, Calendar, email, learning-platform connectors, provenance, synchronization, deduplication, source precedence.

#### `PLANNER_PLAN.md`
- Deterministic planner responsibilities, constraints, scheduling flow, daily/weekly horizons, goal integration, explainability.

#### `TASK_RELATIONSHIP_PLAN.md`
- Accepted Task relationship subsystem: creation-trigger generation, hard completion/start order, soft sequencing, graph validation, authorization, idempotency, and stage-vs-counterpart effort accounting.
- Feeds DATA_MODEL, IO_CONTRACT, USER_MODEL, INTEGRATION, PLANNER, DEVELOPMENT, AI/OPERATIONS/SECURITY, TESTING, and formats.

#### `LEARNING_PLAN.md`
- Historical effort calibration and behavioral pattern discovery.
- Defines weekly analysis, candidate learned rules, user confirmation, and how accepted patterns feed Planner.

#### `AI_EXECUTION_PLAN.md`
- AI Router, model tiers, ChatGPT Work/Codex roles, structured proposals, validation boundary, cost policy.

#### `OPERATIONS_PLAN.md`
- Deployment topology, configuration, secrets, backups, observability, failure recovery, environments.

#### `SECURITY_PRIVACY_PLAN.md`
- Personal-data boundaries, credential handling, least privilege, retention, logging restrictions, external model data exposure.

#### `TESTING_PLAN.md`
- Quality gates, fixtures, connector testing, schema validation, planner regression tests, phase-level acceptance tests.

---

## 3. Authority and Conflict Resolution

Use authority by subject, not a rule that an architecture/status file may override accepted user intent.

1. Latest explicit user instruction controls the requested work and any stated product changes.
2. `A0_USER_INTENT.md` preserves accepted product semantics; `DECISIONS.md` indexes accepted decisions and later refinements. These two must agree. Later explicit accepted refinements supersede earlier wording; numbering or a file's timestamp alone does not authorize a new policy.
3. `PROGRESS.md` controls actual work status and the immediate next action, not product policy.
4. `DEVELOPMENT_PLAN.md` controls provisional milestone order/prerequisites, not accepted semantics. The detailed execution plan is still to be prepared after this audit.
5. `PROJECT_PLAN.md` controls architecture within accepted decisions; specialized documents define their domain details.
6. `../formats/` implements the semantic I/O requirements. Its current Daily Brief is a conceptual template; no machine schema is implemented.
7. Earlier issues/comments/chat may supply provenance but cannot silently replace repository truth.

If intent/register conflict without an identifiable accepted refinement, retain both evidence and record the unresolved boundary in `CONSISTENCY_AUDIT.md`. Do not guess a user decision. Technical choices consistent with accepted semantics may be proposed and later tested without pretending they were already user-approved.

---

## 4. Dependency Graph

```text
User intent / corrections
          ↓
   A0_USER_INTENT.md
          ↓
     DECISIONS.md
          ↓
    ALIGNMENT_PLAN.md
      ┌────┴───────────────┐
      ↓                    ↓
PROJECT_PLAN.md      USER_MODEL_PLAN.md
      ↓                    ↓
DEVELOPMENT_PLAN.md   DATA_MODEL_PLAN.md
      │                    ↓
      │              IO_CONTRACT_PLAN.md
      │               ┌────┴─────────────┐
      │               ↓                  ↓
      │        ../formats/input/   ../formats/output/
      │
      ├────────→ INTEGRATION_PLAN.md
      ├────────→ PLANNER_PLAN.md
      ├────────→ LEARNING_PLAN.md
      └────────→ AI_EXECUTION_PLAN.md
                       │
         ┌─────────────┼──────────────┐
         ↓             ↓              ↓
   OPERATIONS_PLAN  SECURITY_      TESTING_PLAN.md
                    PRIVACY_PLAN.md
         \_____________|_____________/
                       ↓
                 implementation
                       ↓
                  PROGRESS.md
```

Interpretation:
- `ALIGNMENT_PLAN.md` is the semantic gate before implementation: it defines how the user and AI align on meaning, granularity, sources, downstream effects, and deferred provider details.
- Architecture determines module boundaries.
- Development order determines when modules may be implemented.
- User/course, data, and I/O semantics must stabilize before persistence and connectors.
- Provider-specific adapter details are defined only when real integrations are examined.
- Integrations feed normalized state; they do not own planning logic.
- Planner depends on stable state and time availability. Candidate review, audit history, staleness, and minimal recovery begin with persistence/ingestion; Phase 7 extends them rather than introducing safety for the first time.
- AI augments planning/ingestion but must not become canonical state.
- Operations, security, and testing apply across implementation phases.
- Progress reflects actual repository state, not intended future state.

---

## 5. Mandatory Change-Propagation Rules

### If the interaction model, information granularity, or semantic-vs-adapter boundary changes
Update:
1. `A0_USER_INTENT.md` when the change comes from user intent/preferences
2. `ALIGNMENT_PLAN.md`
3. `DECISIONS.md` for accepted policy changes
4. `DEVELOPMENT_PLAN.md` if the alignment gate/order changes
5. `USER_MODEL_PLAN.md`, `DATA_MODEL_PLAN.md`, or `IO_CONTRACT_PLAN.md` as affected
6. Any downstream specialized plan whose inputs/behavior change
7. `PROGRESS.md`

### If a product/architecture decision changes
Update:
1. `DECISIONS.md`
2. `PROJECT_PLAN.md`
3. `DEVELOPMENT_PLAN.md` if sequencing changes
4. Any affected specialized plans
5. `PROGRESS.md` if current/next work changes

### If development order changes
Update:
1. `DEVELOPMENT_PLAN.md`
2. `PROJECT_PLAN.md` only if its high-level order becomes inconsistent
3. `PROGRESS.md`
4. `README.md` only if document dependencies/authority change

### If the user/course profile model changes
Update:
1. `USER_MODEL_PLAN.md`
2. `DATA_MODEL_PLAN.md`
3. `PLANNER_PLAN.md`
4. `IO_CONTRACT_PLAN.md` if profile fields are exposed through input/output
5. `TESTING_PLAN.md` conceptual acceptance scenarios now; executable fixtures once implementation exists
6. `PROGRESS.md`

### If an entity or state model changes
Update:
1. `DATA_MODEL_PLAN.md`
2. `IO_CONTRACT_PLAN.md` when inputs/outputs expose it
3. `PLANNER_PLAN.md` if planner consumes it
4. `INTEGRATION_PLAN.md` if connectors produce it
5. `../formats/` concrete specs after those specs exist
6. `TESTING_PLAN.md`
7. `PROGRESS.md`

### If an input/output contract changes
Update:
1. `IO_CONTRACT_PLAN.md`
2. Corresponding `../formats/input/` or `../formats/output/` files
3. `DATA_MODEL_PLAN.md` if semantics change
4. `INTEGRATION_PLAN.md` for affected sources
5. `PLANNER_PLAN.md` for affected planner output
6. `TESTING_PLAN.md`
7. `PROGRESS.md`

### If a connector changes
Update:
1. `INTEGRATION_PLAN.md`
2. `SECURITY_PRIVACY_PLAN.md` if permissions/data exposure change
3. `OPERATIONS_PLAN.md` if deployment/configuration changes
4. `TESTING_PLAN.md`
5. `PROGRESS.md`

### If historical learning / estimation behavior changes
Update:
1. `LEARNING_PLAN.md`
2. `DATA_MODEL_PLAN.md`
3. `PLANNER_PLAN.md` if accepted learned outputs affect planning
4. `USER_MODEL_PLAN.md` if task/course defaults change
5. `TESTING_PLAN.md`
6. `PROGRESS.md`

### If AI usage changes
Update:
1. `AI_EXECUTION_PLAN.md`
2. `DECISIONS.md` for material policy changes
3. `SECURITY_PRIVACY_PLAN.md` if data sent to models changes
4. `OPERATIONS_PLAN.md` if new credentials/services are required
5. `TESTING_PLAN.md`
6. `PROGRESS.md`

### After any implementation work
Always inspect/update:
- `PROGRESS.md`
- The plan file governing the changed component
- Tests/acceptance criteria if behavior changed

---

## 6. Planning vs Implemented Truth

Planning documents may describe future intent.

Use these conventions:

- **Accepted**: user-approved direction.
- **Planned**: intended but not implemented.
- **In progress**: work has begun in the named scope (planning, modeling, or implementation); specify the scope so planning activity is not mistaken for implemented code.
- **Implemented**: code/config exists.
- **Verified**: tested in the intended environment.
- **Deferred**: intentionally postponed.
- **Superseded**: kept only for historical context; no longer authoritative.

Never label a planned capability as implemented simply because it is described here.

`PROGRESS.md` must distinguish these states explicitly.

---

## 7. Relationship to the Rest of the Repository

`plan/`:
- Why, what, sequencing, constraints, dependencies, and current status.

`formats/`:
- Concrete input/output specifications and examples once defined.
- Conceptual rules originate in `IO_CONTRACT_PLAN.md`; concrete schemas live in `formats/`.

Future implementation directories:
- Must follow plans but become the truth for what code actually exists.
- When implementation exposes a planning mismatch, update the plans instead of leaving them stale.

---

## 8. Current Architectural Invariants

Unless explicitly changed by the user:

- n8n is the only workflow/orchestration platform; Dify is out of scope.
- PostgreSQL is the intended canonical dynamic state store.
- Git-versioned YAML/JSON/config is intended for stable declarative knowledge.
- Calendar represents time occupancy, not canonical task truth.
- Google Calendar is the preferred automation backend; Apple Calendar may remain the user-facing client.
- AI is replaceable and must not be the database.
- ChatGPT Plus is not treated as an API backend.
- Premium ChatGPT Work/Codex usage is human-triggered.
- AI output should normally be a structured proposal validated before state mutation.
- GitHub is the canonical source repository.
- Final runtime should not depend on the user's personal computer being powered on.
- Alignment Gate A0 is complete.
- A0 is complete; M1 is the next incomplete semantic milestone. The six follow-up answers are synchronized, including Task relationships and model-first planning. Natural-day risk windows including today are also accepted under D-078; all original boundaries are resolved. Detailed planning and M1/M1B/M2 prerequisites follow. No infrastructure implementation has begun.
- Broad A0 questioning should not be reopened unless later work reveals a genuine semantic contradiction.
- Internal semantic contracts should be agreed before provider-specific adapter contracts; API/node-specific details are deferred until the real integration stage.

For rationale, read `DECISIONS.md` and `PROJECT_PLAN.md`.

---

## 9. Maintenance Checklist for Any AI Agent

Before editing:
- [ ] Read `PROGRESS.md`.
- [ ] Read relevant accepted decisions.
- [ ] Identify authoritative plan file(s).
- [ ] Identify downstream dependent documents from Section 5.

After editing:
- [ ] Remove contradictions introduced by the change.
- [ ] Update dependent planning documents.
- [ ] Update concrete format specs if already implemented.
- [ ] Update tests/acceptance plan if behavior changed.
- [ ] Update `PROGRESS.md`.
- [ ] Do not claim verification that was not actually performed.

---

## 10. Follow-Up Authority and Relationship Propagation

Read A0_USER_INTENT §60 and DECISIONS D-071–D-077 for the latest accepted answers. TASK_RELATIONSHIP_PLAN.md is the relationship domain specification; it introduces no extra workflow platform or independent Task world. Relationship generation is authorized by an accepted rule; ordinary external discovery/completion still needs review. Notify-before-record expiration, model-first planning without user-estimate overwrite, Asia/Shanghai + date-only 23:59, aggregate <=40-minute SAFE remainder, and bulk unchanged-estimate confirmation supersede earlier unresolved wording.

If relationship semantics/rules change, inspect/update TASK_RELATIONSHIP_PLAN, USER_MODEL, DATA_MODEL, IO_CONTRACT, INTEGRATION, PLANNER, DEVELOPMENT, AI_EXECUTION, OPERATIONS, SECURITY_PRIVACY, TESTING, formats, accepted intent/decision records as appropriate, and PROGRESS. Configuration/schema representation may remain later engineering work; accepted meaning must not be lost.

All original O01–O08 boundaries are resolved. D-078 closes O05 with natural-day windows including today, ending today / today+2 / today+6 at Beijing-time 23:59. Read A0_USER_INTENT §61 and PLANNER_PLAN §23 for the boundary contract. Do not reopen already answered preferences; detailed project planning is next.
