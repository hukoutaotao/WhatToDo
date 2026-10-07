# WhatToDo Plan Control Center

This is the entry point for a new AI. The repository currently contains accepted requirements and a complete development plan, not a working runtime.

## 1. Read and Act

1. Read [PROGRESS](PROGRESS.md) for actual completed/active/blocked work and evidence.
2. Read [DEVELOPMENT_PLAN](DEVELOPMENT_PLAN.md) for execution rules, 195 bounded task definitions, dependencies, robustness, extension and gates.
3. Choose one ready card from its [task catalog index](DEVELOPMENT_PLAN.md#6-milestones-and-task-catalogs). Read that catalog's semantic sources and completed prerequisite artifacts.
4. On a new handoff or semantic change, read [A0 intent](A0_USER_INTENT.md) and [DECISIONS](DECISIONS.md). Do not invent current-semester facts from chat history.

Current-semester names: [confirmed inventory](intake/CURRENT_INVENTORY.md). The next ready task and blockers are maintained in PROGRESS. M0/A0 and the detailed planning deliverable are complete. M1/M1B/M2 and all runtime tasks remain incomplete. Do not reopen accepted preferences or begin persistence before their semantic gates.

## 2. Authority by Subject

| Subject | Authority |
| --- | --- |
| User's explicit current instruction | Controls requested work and stated product changes |
| Accepted semantics | A0_USER_INTENT + DECISIONS; explicit accepted refinements supersede earlier wording |
| Execution/dependencies/gates | DEVELOPMENT_PLAN + plan/tasks catalogs |
| Actual status and evidence | PROGRESS, never a source of new product policy |
| Architecture | PROJECT_PLAN within accepted semantics |
| Domain/interface meaning | Specialized specification below |
| Concrete machine schemas/output template | formats/, within DATA_MODEL and IO_CONTRACT |

A technical proposal or task ID does not authorize a new user preference. Record genuine conflicts as a blocked affected task with both interpretations in PROGRESS; resolve before changing that meaning. Technical choices consistent with accepted semantics can be made and verified at their listed tasks.

## 3. Document Map and Execution Ownership

| Specification | Purpose | Task catalogs |
| --- | --- | --- |
| [A0_USER_INTENT](A0_USER_INTENT.md), [DECISIONS](DECISIONS.md) | Complete accepted user semantics and refinements | All; decisions preserved, not duplicated into alternatives |
| [ALIGNMENT_PLAN](ALIGNMENT_PLAN.md) | Reusable semantic-vs-adapter alignment method; completed A0 gate | M1, M1B, M2 |
| [PROJECT_PLAN](PROJECT_PLAN.md) | Architecture/storage/Calendar/AI responsibilities | M2–M8 |
| [USER_MODEL_PLAN](USER_MODEL_PLAN.md), [confirmed inventory](intake/CURRENT_INVENTORY.md) | Stable modeling specification and current user-confirmed identity intake; detailed profiles remain separate | M1, M1B, M5B |
| [DATA_MODEL_PLAN](DATA_MODEL_PLAN.md) | Task/state/provenance/history/effort ownership | M2, M3A, M3B, M5B |
| [TASK_RELATIONSHIP_PLAN](TASK_RELATIONSHIP_PLAN.md) | Typed generation/order, authority, idempotency and workload | M1B, M2, M3B, M6 |
| [IO_CONTRACT_PLAN](IO_CONTRACT_PLAN.md) | Natural input, full review, batches, emergency, output | M2, M3A/B, M6 |
| [INTEGRATION_PLAN](INTEGRATION_PLAN.md) | Calendar/email/platform/n8n mappings and source boundaries | M4, M5 |
| [PLANNER_PLAN](PLANNER_PLAN.md) | Budgets, feasibility, horizons, allocation and risk | M6, M8 |
| [LEARNING_PLAN](LEARNING_PLAN.md) | Automatic numeric predictions and reviewed behavior | M8, optional M7 |
| [AI_EXECUTION_PLAN](AI_EXECUTION_PLAN.md) | Replaceable optional models and manual premium jobs | M7 |
| [OPERATIONS_PLAN](OPERATIONS_PLAN.md) | Always-on runtime, observability, backup/replay/recovery | Early M3/M4/M5/M6 foundations; M8 extension |
| [SECURITY_PRIVACY_PLAN](SECURITY_PRIVACY_PLAN.md) | Secrets, scopes, data minimization and truth protection | All state/I/O tasks; M8 security gate |
| [TESTING_PLAN](TESTING_PLAN.md) | Semantic regression and evidence vocabulary | Every task's targeted acceptance; M3/M6/M8 gates |
| [Input formats](../formats/input/README.md), [output formats](../formats/output/README.md) | Concrete schema destinations and accepted human format | M2, M6, M8 |
| [DAILY_BRIEF_TEMPLATE](../formats/output/DAILY_BRIEF_TEMPLATE.md) | Accepted concise human Daily Brief | M2-10, M6-16–19 |

## 4. Development Protocol

One task or repeated instance per AI execution. Explicit prerequisites and observed evidence determine readiness. Split oversized tasks before coding and preserve stable IDs. Development-plan Section 4 supplies the full protocol; Section 5 defines live task states and repeated instances.

Minimum foundations are early: schema/reference/authority/version validation, atomic audit, idempotent commands/events, bounded replay/retry, last-trusted-state handling, redacted correlation IDs and isolated restore. Do not defer these until AI or the final release. n8n remains the only workflow platform; reusable domain/application code and ports isolate adapters. No live AI is required for ordinary planning.

Update all affected semantic specifications, formats, task dependencies/tests and PROGRESS when a contract or behavior changes. Record exact executed checks and limitations. Planned code, fixtures, live evidence and restored operation are separate claims. Never claim user progress/completion from external evidence, model confidence or scheduled time.

## 5. Cleanup and History

The old coarse DEVELOPMENT_PLAN was replaced in place by the executable plan and catalogs. Control/status duplication was consolidated here and in PROGRESS. The completed audit working report was removed; its C01–C21 findings and closed O01–O08 boundaries are preserved in [development-plan traceability](DEVELOPMENT_PLAN.md#13-preserved-audit-findings-and-closed-boundaries) and durable semantic owners. Git history retains prior reports.

Do not create a second competing roadmap or status ledger. Retain accepted intent, decision IDs, alignment method and module specifications; they contain domain information needed by future AIs.
