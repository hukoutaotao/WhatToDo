# WhatToDo — Learning, resilient operation and maintainable release

> Status: executable development specification; every task initially TODO. No task is implemented by this file.
> Task scope: one bounded AI execution per task or explicitly repeated instance.

[Development plan and execution rules](../DEVELOPMENT_PLAN.md) · [Live progress](../PROGRESS.md)

## Required sources

- [LEARNING_PLAN.md](../LEARNING_PLAN.md)
- [OPERATIONS_PLAN.md](../OPERATIONS_PLAN.md)
- [SECURITY_PRIVACY_PLAN.md](../SECURITY_PRIVACY_PLAN.md)
- [PLANNER_PLAN.md](../PLANNER_PLAN.md)
- [TESTING_PLAN.md](../TESTING_PLAN.md)

Read the source sections relevant to the chosen task, its completed prerequisite artifacts, and the shared Definition of Done before editing. Source documents control meaning; this catalog controls work decomposition. Proposed artifact paths below are logical scopes until M2-16 freezes the language-specific mapping. An adapter/schema described here does not yet exist.

## Gate: M8-27

Task order is constrained by explicit dependencies, not by credentials for unrelated live integrations. A VERIFY task runs the smallest meaningful fixture/integration set for its boundary and records actual evidence. Repeated tasks are one course/family/account/layout/playbook per execution; a template dependency means the required instance set described in the development plan.

## Tasks

### M8-01

**Build immutable learning observation projection**

- Type: `DEV`. Initial status: `TODO`.
- Prerequisites: [M6-26](M6_PLANNER_DAILY_MVP.md#m6-26) · [M3A-15](M3_STATE_FOUNDATION.md#m3a-15)
- Deliverable / bounded file scope: training/analysis observation read model.
- Work: Join historical Task context, actual work, user U, model B and plan snapshots without rewriting old observations; distinguish canceled/expired/reworked outcomes.
- Acceptance / failure and extension checks: Abandoned invested effort is not full completion duration; unmeasured setup estimates are not measured training samples; unreported time-of-day is unknown; late model versions cannot rewrite earlier prediction errors.
- Completion evidence: artifact paths + exact targeted command/check or user-source reference + observed result + remaining limitations, recorded in PROGRESS. Do not mark done from code presence alone.

### M8-02

**Implement baseline remaining-effort predictor**

- Type: `DEV`. Initial status: `TODO`.
- Prerequisites: [M8-01](M8_LEARNING_RELEASE_OPERATIONS.md#m8-01)
- Deliverable / bounded file scope: versioned numeric predictor.
- Work: Use a simple robust interpretable baseline for one TaskType family with finite sample/validity requirements and explicit cold-start fallback.
- Acceptance / failure and extension checks: Predictions concern unfinished effort, not raw total duration; small/outlier samples do not create fake certainty; unknown work quantity is not assumed comparable; no user U/template default is overwritten.
- Completion evidence: artifact paths + exact targeted command/check or user-source reference + observed result + remaining limitations, recorded in PROGRESS. Do not mark done from code presence alone.

### M8-03

**Implement automatic numeric calibration/versioning**

- Type: `DEV`. Initial status: `TODO`.
- Prerequisites: [M8-02](M8_LEARNING_RELEASE_OPERATIONS.md#m8-02)
- Deliverable / bounded file scope: model training/version activation service.
- Work: Fit from eligible observations, store model metadata and support deterministic activation/rollback; expose through Predictor port.
- Acceptance / failure and extension checks: Numeric model update needs no behavioral-rule approval; sufficient applicable measurements can substantially reduce or remove an unmeasured setup estimate's influence under LEARNING_PLAN §15 without rewriting history/U/defaults; reusing a rough estimate in plans does not create additional measured samples; rollback restores the earlier prediction source; restart does not duplicate training runs.
- Completion evidence: artifact paths + exact targeted command/check or user-source reference + observed result + remaining limitations, recorded in PROGRESS. Do not mark done from code presence alone.

### M8-04

**Implement prediction diagnostics and comparison**

- Type: `DEV`. Initial status: `TODO`.
- Prerequisites: [M8-03](M8_LEARNING_RELEASE_OPERATIONS.md#m8-03)
- Deliverable / bounded file scope: prediction error/uncertainty report.
- Work: Compare contemporaneous predictions with eligible observed outcomes; report applicability/uncertainty and user-model disagreement concisely.
- Acceptance / failure and extension checks: No future-data leakage into past error; non-completion outcomes are labeled; diagnostics never silently choose max(U,B).
- Completion evidence: artifact paths + exact targeted command/check or user-source reference + observed result + remaining limitations, recorded in PROGRESS. Do not mark done from code presence alone.

### M8-05

**Implement one behavioral-pattern candidate detector**

- Type: `DEV`. Initial status: `TODO`.
- Prerequisites: [M8-01](M8_LEARNING_RELEASE_OPERATIONS.md#m8-01) · [M6-20](M6_PLANNER_DAILY_MVP.md#m6-20)
- Deliverable / bounded file scope: one explainable pattern detector.
- Work: Detect one scoped candidate pattern using release-to-first-work, competing workload and optional reasons; avoid diagnosing delay alone as procrastination.
- Acceptance / failure and extension checks: Weak/confounded data yields no confident rule; candidate contains evidence/scope; detector cannot modify planning behavior directly.
- Completion evidence: artifact paths + exact targeted command/check or user-source reference + observed result + remaining limitations, recorded in PROGRESS. Do not mark done from code presence alone.

### M8-06

**Implement weekly learned-rule review**

- Type: `DEV`. Initial status: `TODO`.
- Prerequisites: [M8-05](M8_LEARNING_RELEASE_OPERATIONS.md#m8-05) · [M3B-08](M3_RELATIONSHIPS_REVIEWS.md#m3b-08)
- Deliverable / bounded file scope: weekly candidate review coordinator.
- Work: Present candidate behavioral rules with concise evidence, recommended response and explicit acceptance/rejection/revocation through versioned authorization.
- Acceptance / failure and extension checks: Silence is not adoption; explicit existing preferences win; rejected suggestions remain historical and do not influence allocation.
- Completion evidence: artifact paths + exact targeted command/check or user-source reference + observed result + remaining limitations, recorded in PROGRESS. Do not mark done from code presence alone.

### M8-07

**Apply and revoke accepted behavioral rules**

- Type: `DEV`. Initial status: `TODO`.
- Prerequisites: [M8-06](M8_LEARNING_RELEASE_OPERATIONS.md#m8-06) · [M6-15](M6_PLANNER_DAILY_MVP.md#m6-15)
- Deliverable / bounded file scope: versioned planning-rule registry.
- Work: Load only user-accepted scoped behavioral policies into Planner through existing interfaces; support revocation and preserve past plan rule versions.
- Acceptance / failure and extension checks: Unknown rule type cannot run code or modify core invariants; revocation affects future plans without rewriting history; provider-free Planner still works.
- Completion evidence: artifact paths + exact targeted command/check or user-source reference + observed result + remaining limitations, recorded in PROGRESS. Do not mark done from code presence alone.

### M8-08

**Implement weekly forward-risk preview**

- Type: `DEV`. Initial status: `TODO`.
- Prerequisites: [M8-04](M8_LEARNING_RELEASE_OPERATIONS.md#m8-04) · [M5B-08](M5B_GOALS_GENERATION.md#m5b-08) · [M6-06](M6_PLANNER_DAILY_MVP.md#m6-06)
- Deliverable / bounded file scope: Weekly Plan contract/renderer.
- Work: Reuse workload/availability projection for bottlenecks, required early work, course backlog and Goal pacing; preserve separate weekly presentation.
- Acceptance / failure and extension checks: Weekly is not merely concatenated daily lists; far-future necessary work remains visible; no second Task store or duplicate Goal workload exists.
- Completion evidence: artifact paths + exact targeted command/check or user-source reference + observed result + remaining limitations, recorded in PROGRESS. Do not mark done from code presence alone.

### M8-09

**Implement long-term planning preview**

- Type: `DEV`. Initial status: `TODO`.
- Prerequisites: [M8-08](M8_LEARNING_RELEASE_OPERATIONS.md#m8-08)
- Deliverable / bounded file scope: Long-Term Plan contract/renderer.
- Work: Expose finite longer-horizon risks, phases and data coverage without inventing exact future availability; reuse Solver/Predictor/domain contracts.
- Acceptance / failure and extension checks: Uncertain future coverage is labeled; output cannot promise infeasible deadlines safe; long-term projections do not rewrite canonical dates.
- Completion evidence: artifact paths + exact targeted command/check or user-source reference + observed result + remaining limitations, recorded in PROGRESS. Do not mark done from code presence alone.

### M8-10

**Implement inactivity catch-up reconciliation**

- Type: `DEV`. Initial status: `TODO`.
- Prerequisites: [M8-09](M8_LEARNING_RELEASE_OPERATIONS.md#m8-09) · [M3B-14](M3_RELATIONSHIPS_REVIEWS.md#m3b-14) · [M5-15](M5_INGESTION_N8N.md#m5-15)
- Deliverable / bounded file scope: catch-up review/replan coordinator.
- Work: On return after missed interactions, summarize evidence changes, stale state, full pending queue and unfinished obligations; use normal reviewed commands then recalculate.
- Acceptance / failure and extension checks: Old daily recommendations are not mechanically rolled forward; unknown personal progress remains pending; existing learned/explicit rules are respected.
- Completion evidence: artifact paths + exact targeted command/check or user-source reference + observed result + remaining limitations, recorded in PROGRESS. Do not mark done from code presence alone.

### M8-11

**Run learning/recovery regression fixtures**

- Type: `VERIFY`. Initial status: `TODO`.
- Prerequisites: [M8-10](M8_LEARNING_RELEASE_OPERATIONS.md#m8-10) · [M8-07](M8_LEARNING_RELEASE_OPERATIONS.md#m8-07)
- Deliverable / bounded file scope: learning and catch-up replay report.
- Work: Check cold start, outliers, canceled/expired/rework history, numerical rollback, rejected behavioral rules and multi-day inactivity return.
- Acceptance / failure and extension checks: Numeric/behavioral authority distinction holds; no fabricated sessions or missed-task completion; historical plan snapshots stay immutable.
- Completion evidence: artifact paths + exact targeted command/check or user-source reference + observed result + remaining limitations, recorded in PROGRESS. Do not mark done from code presence alone.

### M8-12

**Add structured logs and correlation conventions**

- Type: `DEV`. Initial status: `TODO`.
- Prerequisites: [M6-26](M6_PLANNER_DAILY_MVP.md#m6-26) · [M5-20](M5_INGESTION_N8N.md#m5-20)
- Deliverable / bounded file scope: logging/redaction and health contracts.
- Work: Standardize command/event/source/plan/rule correlation IDs, typed error categories and bounded redacted records; early modules already carry these IDs.
- Acceptance / failure and extension checks: Raw bodies, cookies, tokens and secret URLs are filtered; logs diagnose failed graph/dispatch/replay without exposing private data; common format spans adapters.
- Completion evidence: artifact paths + exact targeted command/check or user-source reference + observed result + remaining limitations, recorded in PROGRESS. Do not mark done from code presence alone.

### M8-13

**Add runtime health and freshness metrics**

- Type: `DEV`. Initial status: `TODO`.
- Prerequisites: [M8-12](M8_LEARNING_RELEASE_OPERATIONS.md#m8-12)
- Deliverable / bounded file scope: health/readiness/metrics endpoints.
- Work: Expose DB readiness, outbox lag, source freshness, pending review, notification unknown/failure, missed plan and model fallback counts.
- Acceptance / failure and extension checks: Transport success is not semantic reconciliation; process alive is not DB/source readiness; alerts identify a practical operator action.
- Completion evidence: artifact paths + exact targeted command/check or user-source reference + observed result + remaining limitations, recorded in PROGRESS. Do not mark done from code presence alone.

### M8-14

**Package service and pinned n8n/runtime configs**

- Type: `OPS`. Initial status: `TODO`.
- Prerequisites: [M6-27](M6_PLANNER_DAILY_MVP.md#m6-27) · [M8-13](M8_LEARNING_RELEASE_OPERATIONS.md#m8-13)
- Deliverable / bounded file scope: deployment manifests and safe workflow exports.
- Work: Package application/DB/n8n topology and persistent volumes with health checks, secret references and explicit environment separation; reuse approved runtime ADR.
- Acceptance / failure and extension checks: A clean staging environment starts reproducibly; no production credentials are committed; user laptop shutdown does not stop always-on service.
- Completion evidence: artifact paths + exact targeted command/check or user-source reference + observed result + remaining limitations, recorded in PROGRESS. Do not mark done from code presence alone.

### M8-15

**Implement production backup scheduling and verification**

- Type: `OPS`. Initial status: `TODO`.
- Prerequisites: [M8-14](M8_LEARNING_RELEASE_OPERATIONS.md#m8-14) · [M3A-18](M3_STATE_FOUNDATION.md#m3a-18)
- Deliverable / bounded file scope: backup automation and integrity/age monitoring.
- Work: Back up DB, non-secret config/workflow versions and securely documented secret recovery references; use selected retention/RPO settings.
- Acceptance / failure and extension checks: Missing/old/corrupted backups alert visibly; task/audit/occurrence consistency is included; a backup file alone is not claimed successful recovery.
- Completion evidence: artifact paths + exact targeted command/check or user-source reference + observed result + remaining limitations, recorded in PROGRESS. Do not mark done from code presence alone.

### M8-16

**Run full restore into isolated staging**

- Type: `VERIFY`. Initial status: `TODO`.
- Prerequisites: [M8-15](M8_LEARNING_RELEASE_OPERATIONS.md#m8-15)
- Deliverable / bounded file scope: reports/acceptance/restore.md.
- Work: Restore a production-shaped synthetic backup plus compatible service/workflow versions into new staging, then replay pending events/commands/notices safely.
- Acceptance / failure and extension checks: State, audit, dedup and checkpoints survive; unknown notification outcomes do not cause blind resend; measured restore time/data loss are recorded against chosen targets.
- Completion evidence: artifact paths + exact targeted command/check or user-source reference + observed result + remaining limitations, recorded in PROGRESS. Do not mark done from code presence alone.

### M8-17

**Define upgrade and rollback procedure**

- Type: `OPS`. Initial status: `TODO`.
- Prerequisites: [M8-16](M8_LEARNING_RELEASE_OPERATIONS.md#m8-16)
- Deliverable / bounded file scope: upgrade/rollback runbook and rehearsal.
- Work: Use backward-compatible expand/migrate/contract DB/schema changes and pinned workflow/provider versions; rehearse one compatible upgrade and app rollback.
- Acceptance / failure and extension checks: Rollback cannot require data-destructive down migrations; unsupported version combinations are blocked; snapshot/config/model versions permit diagnosis.
- Completion evidence: artifact paths + exact targeted command/check or user-source reference + observed result + remaining limitations, recorded in PROGRESS. Do not mark done from code presence alone.

### M8-18

**Implement source retention and explicit privacy removal**

- Type: `DEV`. Initial status: `TODO`.
- Prerequisites: [M8-12](M8_LEARNING_RELEASE_OPERATIONS.md#m8-12) · [M3A-17](M3_STATE_FOUNDATION.md#m3a-17)
- Deliverable / bounded file scope: retention/privacy handlers.
- Work: Minimize raw content by configured policy while retaining semantic outcomes/audit; implement explicit authorized removal/duplicate merge with reference handling.
- Acceptance / failure and extension checks: Normal COMPLETE/CANCELLED/EXPIRED history is not garbage-collected; raw removal does not cancel Tasks; privacy removal leaves no dangling target references or leaked retained payload.
- Completion evidence: artifact paths + exact targeted command/check or user-source reference + observed result + remaining limitations, recorded in PROGRESS. Do not mark done from code presence alone.

### M8-19

**Run access, injection and secret-leak checks**

- Type: `VERIFY`. Initial status: `TODO`.
- Prerequisites: [M8-18](M8_LEARNING_RELEASE_OPERATIONS.md#m8-18) · [M8-14](M8_LEARNING_RELEASE_OPERATIONS.md#m8-14)
- Deliverable / bounded file scope: security acceptance report.
- Work: Exercise scopes/auth, command replay, malicious evidence/AI text, log redaction, workflow exports and secret scanning on release artifacts. If optional AI is enabled for the release, additionally require M7-14 evidence; disabled AI is an explicit scope decision, not a false completed task.
- Acceptance / failure and extension checks: No external source/model gains write authority; public transport cannot bypass handlers; disabled AI still passes core checks; real secret values are never test fixtures.
- Completion evidence: artifact paths + exact targeted command/check or user-source reference + observed result + remaining limitations, recorded in PROGRESS. Do not mark done from code presence alone.

### M8-20

**Benchmark realistic bounded workloads**

- Type: `VERIFY`. Initial status: `TODO`.
- Prerequisites: [M8-13](M8_LEARNING_RELEASE_OPERATIONS.md#m8-13) · [M6-25](M6_PLANNER_DAILY_MVP.md#m6-25)
- Deliverable / bounded file scope: performance/scale benchmark report.
- Work: Use synthetic per-semester Tasks, recurrence, source volume and interval counts; measure snapshot/query/solver/outbox memory/time and identify limits.
- Acceptance / failure and extension checks: Results state hardware/data size/timeouts; scale failure degrades visibly rather than corrupting truth or labeling unknown feasible; budgets are recorded, not invented SLAs.
- Completion evidence: artifact paths + exact targeted command/check or user-source reference + observed result + remaining limitations, recorded in PROGRESS. Do not mark done from code presence alone.

### M8-21

**Optimize one measured bottleneck [repeat if justified]**

- Type: `DEV`. Initial status: `TODO`.
- Prerequisites: [M8-20](M8_LEARNING_RELEASE_OPERATIONS.md#m8-20)
- Deliverable / bounded file scope: one indexed query/algorithm optimization.
- Work: Change only the measured bottleneck with query/algorithm evidence, preserving frozen contracts and bounded resource use. Split distinct bottlenecks into separate instances.
- Acceptance / failure and extension checks: Before/after benchmark improves the target; semantic/oracle fixtures still pass; no premature microservice/cache dependency is introduced without evidenced need.
- Completion evidence: artifact paths + exact targeted command/check or user-source reference + observed result + remaining limitations, recorded in PROGRESS. Do not mark done from code presence alone.

### M8-22

**Run extension conformance probes**

- Type: `VERIFY`. Initial status: `TODO`.
- Prerequisites: [M8-21](M8_LEARNING_RELEASE_OPERATIONS.md#m8-21) · [M8-19](M8_LEARNING_RELEASE_OPERATIONS.md#m8-19)
- Deliverable / bounded file scope: extension probe report.
- Work: Add a synthetic new TaskType/profile, second fake evidence provider, alternate fake model and renderer using registries/ports; remove probes cleanly after verification.
- Acceptance / failure and extension checks: Each extension requires only its adapter/config/schema migration and focused tests; no course-name branch, core-data rewrite or second workflow platform is needed.
- Completion evidence: artifact paths + exact targeted command/check or user-source reference + observed result + remaining limitations, recorded in PROGRESS. Do not mark done from code presence alone.

### M8-23

**Write one failure recovery playbook per scenario [repeat]**

- Type: `OPS`. Initial status: `TODO`.
- Prerequisites: [M8-17](M8_LEARNING_RELEASE_OPERATIONS.md#m8-17) · [M8-22](M8_LEARNING_RELEASE_OPERATIONS.md#m8-22)
- Deliverable / bounded file scope: one operator playbook.
- Work: For one DB outage, stale Calendar, credential revocation, poison source, stuck lease, solver unknown or notification-unknown scenario, document diagnosis, bounded recovery and replay verification.
- Acceptance / failure and extension checks: Another AI can execute the playbook from recorded state without guessing or deleting history; rollback boundaries and uncertain external outcomes are explicit.
- Completion evidence: artifact paths + exact targeted command/check or user-source reference + observed result + remaining limitations, recorded in PROGRESS. Do not mark done from code presence alone.

### M8-24

**Run restart and dependency-outage drills**

- Type: `VERIFY`. Initial status: `TODO`.
- Prerequisites: [M8-23](M8_LEARNING_RELEASE_OPERATIONS.md#m8-23)
- Deliverable / bounded file scope: resilience drill report.
- Work: Stop/restart application, DB, n8n and optional providers separately in staging; test worker contention and recovery with bounded fault cases.
- Acceptance / failure and extension checks: No duplicate canonical side effects or checkpoint loss; stale/unavailable output is honest; planned service recovers within measured chosen limits without laptop dependency.
- Completion evidence: artifact paths + exact targeted command/check or user-source reference + observed result + remaining limitations, recorded in PROGRESS. Do not mark done from code presence alone.

### M8-25

**Prepare user and AI maintenance handoff**

- Type: `OPS`. Initial status: `TODO`.
- Prerequisites: [M8-24](M8_LEARNING_RELEASE_OPERATIONS.md#m8-24) · [M8-11](M8_LEARNING_RELEASE_OPERATIONS.md#m8-11)
- Deliverable / bounded file scope: maintenance guide and task/runbook links.
- Work: Explain normal morning/evening use, corrections, rule changes, provider addition, backup/restore, upgrades and task-status/evidence maintenance; keep technical detail out of routine product output.
- Acceptance / failure and extension checks: A new AI can locate semantic authority, module interfaces, targeted commands and recovery evidence; user guide does not require manually authoring JSON.
- Completion evidence: artifact paths + exact targeted command/check or user-source reference + observed result + remaining limitations, recorded in PROGRESS. Do not mark done from code presence alone.

### M8-26

**Run a bounded live operating pilot**

- Type: `VERIFY`. Initial status: `TODO`.
- Prerequisites: [M6-29](M6_PLANNER_DAILY_MVP.md#m6-29) · [M8-25](M8_LEARNING_RELEASE_OPERATIONS.md#m8-25)
- Deliverable / bounded file scope: reports/acceptance/pilot.md.
- Work: Run the agreed finite pilot with real reviewed data and enabled sources, recording lost/doubled actions, stale plans, response usability and measured cost/failure recovery.
- Acceptance / failure and extension checks: Synthetic checks are not counted as live evidence; zero unreviewed completion/progress writes; issues map to small follow-up tasks rather than whole-system rewrites.
- Completion evidence: artifact paths + exact targeted command/check or user-source reference + observed result + remaining limitations, recorded in PROGRESS. Do not mark done from code presence alone.

### M8-27

**Close maintainable release gate**

- Type: `VERIFY`. Initial status: `TODO`.
- Prerequisites: [M8-26](M8_LEARNING_RELEASE_OPERATIONS.md#m8-26)
- Deliverable / bounded file scope: reports/acceptance/release.md.
- Work: Require semantic/fault/security/restore/extension evidence, explicit enabled-provider readiness, documented operating limits and accurate progress; optional AI may remain disabled with M7 status declared.
- Acceptance / failure and extension checks: No hidden BLOCKED_USER dependency in enabled production scope; restore and upgrades have rehearsals; every accepted capability has test/evidence coverage and an owner contract.
- Completion evidence: artifact paths + exact targeted command/check or user-source reference + observed result + remaining limitations, recorded in PROGRESS. Do not mark done from code presence alone.
