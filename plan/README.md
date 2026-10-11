# WhatToDo Plan Control Center

This is the entry point for a new AI. The repository contains accepted requirements, a complete development plan and sixteen runnable offline development slices, including Plan/forecast, AI-result, application ports [semantic scenarios](../tests/fixtures/semantic/README.md) and [guided review](../formats/input/GUIDED_REVIEW_PROTOTYPE.md); a [checked relational/migration draft](../database/README.md) and [native toolchain spike](../toolchain/ADR-001.md) are also available. The complete application runtime is not yet implemented. Use the [input contract index](../formats/input/README.md), [output contract index](../formats/output/README.md) and live progress ledger for interfaces and executed checks.

## 1. Read and Act

1. Read [PROGRESS](PROGRESS.md) for actual completed/active/blocked work and evidence.
2. Read [DEVELOPMENT_PLAN](DEVELOPMENT_PLAN.md) for execution rules, 195 bounded task definitions, dependencies, robustness, extension and gates.
3. Choose one ready card from its [task catalog index](DEVELOPMENT_PLAN.md#6-milestones-and-task-catalogs). Read that catalog's semantic sources and completed prerequisite artifacts.
4. On a new handoff or semantic change, read [A0 intent](A0_USER_INTENT.md) and [DECISIONS](DECISIONS.md). Do not invent current-semester facts from chat history.

Current-semester names: [confirmed inventory](intake/CURRENT_INVENTORY.md). The next ready task and blockers are maintained in PROGRESS. M0/A0 and the detailed planning deliverable are complete. M1/M1B remain incomplete; the generic M2 development baseline passes, while real activation/runtime gates remain open. [D-080](DECISIONS.md#d-080--develop-the-system-before-completing-personal-intake) explicitly prioritizes system development and defers remaining personal intake; generic offline development may use accepted semantics and synthetic examples. Do not mark deferred facts complete, invent availability or activate unresolved real profiles. Keep the required schema/authority/audit gates for persistence.

M3A-01 through M3A-03 add the [private package foundation](../toolchain/PACKAGE.md),
injected UTC/date primitives and version-pinned configuration loading. Their
focused evidence and installation checkpoints are in PROGRESS. M3A-04 adds an
[isolated PostgreSQL harness with separated roles](../toolchain/POSTGRES_TESTS.md),
verified with native authentication and success/failure cleanup probes.
M3A-05 now supplies [ordered migrations and schema compatibility](../database/RUNTIME_MIGRATIONS.md)
with native rollback/retry/interruption evidence. The next ready scope is
M3B-07 truthful stage rework, after verified M3B-06 bounded cascade and recovery processing; other normalization classes and later runtime dependencies remain open. M3A-06 supplies
[Git-backed immutable definitions](../database/DEFINITION_REPOSITORIES.md),
exact-version reference checks and default snapshots; native verification proves
new default versions preserve existing Task history. M3A-07 now provides
[Task/stage storage](../database/TASK_REPOSITORIES.md) with lossless history,
permanent stage ownership and an internal transaction-bound append operation.
M3A-08 provides [source/candidate and pending-confirmation storage](../database/EVIDENCE_REPOSITORIES.md),
including immutable scoped evidence, conflicts, tombstones and raw-content
minimization. Ingestion preserves canonical Task/authority/audit state and
reviewed replay; native acceptance covers 34 checks. M3A-09 adds
[atomic Task/audit publication](../database/ATOMIC_TRANSACTIONS.md) with exact
independent permits, native version conflicts, whole-batch rollback and explicit
unknown commit outcomes. Its 22 native checks and 377 full methods pass.
M3A-10 adds [durable command replay and receipt reconciliation](../database/COMMAND_LEDGER.md),
including caller ownership, expired-permit replay, changed-payload conflicts and
restart/concurrent/unknown-ack verification. Its 21 native replay checks,
22 atomicity regression checks and 385 full methods pass at that checkpoint.
M3A-11 now supplies [strict schema and resolved-authority validation](../database/COMMAND_VALIDATION.md),
including independent root grants/current references, complete effect scope and
atomic command annotations. Eleven focused methods, 25 native authority checks,
396 full methods and clean installation across 43 modules pass at that checkpoint.
M3A-12 now supplies [manual Task creation](../database/MANUAL_TASK_CREATION.md),
including exact accepted-default provenance, lossless pending facts, one canonical
creation identity and atomic initial U. Ten focused methods, 26 native creation
checks, 406 full methods and clean installation across 45 modules pass at that checkpoint. Current
seventeen-step migrations have 82 domain tables/204 FKs; current migration, authority,
storage, ledger and atomicity regressions pass. M3A-13 adds [explicit Task fact
updates](../database/TASK_FACT_PATCHES.md), preserving source time/history and
original-request replay with atomic due/U support. Fifteen focused methods,
32 native checks and 421 full methods pass at that checkpoint; clean installation covers 48 modules
and a separately selected extension while keeping the 30 base schemas unchanged.
M3A-14 adds [user-confirmed completion/cancellation](../database/TASK_LIFECYCLE.md),
with atomic parent/stage zero U, retained actual work and honest work timestamps.
Fourteen focused methods, 34 native checks and 435 full methods pass at that checkpoint; clean
installation covers 50 modules and both endpoints without optional-driver
imports. M3A-15 adds [actual-work reporting](../database/WORK_REPORTS.md), with
increment/cumulative settlement, independent U, lossless optional sessions and
observation-ID deduplication. Eighteen focused methods, 39 native checks and 453
full methods pass; current regression evidence and 53-module/33-schema clean
installation are recorded in PROGRESS. The base 30 contracts and 91 pins remain
unchanged. M3A-21@CREATE_TASK adds [direct-user creation input](../formats/input/DIRECT_USER_CREATION.md),
with clear Chinese phrases/text answers, exact statement/source ownership and the
existing manual service handoff. Twenty-one focused methods, 16 native handoff
checks, 474 full methods and six scripted/stdin demos pass; clean installation
covers 54 modules. Other command classes remain separate repeat instances.
[M3A-22 resolution](../database/COMMAND_RESOLUTION.md) now joins owned Task/course
snapshots, versioned replies and same-command authorized handoff. Twenty-two
focused methods, 23 native checks and 496 full methods pass; clean installation
covers 56 modules/36 selected schemas at that checkpoint.
[M3A-16 transport](../formats/input/PROTOTYPE_COMMAND_TRANSPORT.md) now exposes
existing handlers through an authenticated loopback HTTP API. Twenty-nine focused
methods, 23 native HTTP checks and 525 full methods pass; current clean installation
covers 60 modules/38 selected schemas at that checkpoint.
[M3A-17 read models](../database/READ_MODELS.md) now return owned Tasks, retained
outcomes, pending summaries and exact semantic audit history with restart-safe
signed pagination. Thirty-one focused methods, 20 native checks and 556 full methods
pass; current installation covers 62 modules/40 schemas and 63 matching files.
[M3A-18 backup/restore](../toolchain/BACKUP_RESTORE.md) now verifies all 76 tables,
catalogs, audits and command receipts in a separate database. Sixteen native
checks, 33 focused methods and 589 full methods pass, including corruption and
actual late restore rollback/retry. [M3A-20 isolated CI](../toolchain/CI.md) now
rehearses the complete entrypoint in a fresh Windows checkout: 602 methods,
113 native checks, twelve dropped test databases and three deliberate failure
gates pass. Hosted Actions has not been run.
[M3A-19 acceptance](../reports/acceptance/M3A.md) now closes the bounded generic
persistence gate with fifteen requirement mappings, a fresh 602-method/113-native
run, exact installed-source checks and separate restore. M3B-01 typed storage, M3B-02 graph validation, M3B-03 outbox and M3B-04 generation evaluation are DONE; M3B-05.a/b and parent M3B-05 scoped atomic generation are DONE. [M3B-06 bounded processing](../database/GENERATION_PROCESSING.md) is DONE with 715 methods/197 native checks; M3B-07 stage rework follows; [runtime handoff](../database/GENERATION_RUNTIME.md) records evidence and remaining work.
Personal intake remains deferred.

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

[Typed relationship storage](../database/RELATIONSHIP_STORAGE.md) now preserves accepted rule/link versions and exact provenance. Current regression passes 685 methods and 153 native checks; personal intake remains deferred.

[Bounded relationship graph validation](../database/RELATIONSHIP_GRAPH_VALIDATION.md) now verifies separately typed graphs, precise diagnostics and explicit generation resource limits. Current installation contains 68 modules/69 matching files; automatic generation and personal activation remain future work.

[Canonical creation outbox](../database/CREATION_OUTBOX.md) now preserves the first source snapshot atomically and supports scoped delivery leases, retry/restart recovery and fenced result replay. Delivery state remains separate from Task completion. Rule evaluation is available; atomic target generation remains next.

[Exact-version generation evaluation](../database/GENERATION_EVALUATOR.md) now constructs a validated independent Task or shared-parent stage, or explicit pending facts, with original source/default/template provenance. Atomic counterpart persistence and deduplication remain next.
