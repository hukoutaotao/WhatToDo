# WhatToDo — Detailed Development Plan

> Updated: 2026-10-06. Authority: execution order, task decomposition, engineering acceptance and dependency gates.
> Product meaning remains controlled by [accepted intent](A0_USER_INTENT.md) and [decisions](DECISIONS.md).
> Status: planning deliverable complete; implementation and M1/M1B/M2 deliverables are not complete. See [live progress](PROGRESS.md).
> This replaces the former coarse roadmap at this path. The completed audit working file is retired; its important invariants and finding/boundary IDs are preserved in Sections 2 and 13.

## 1. Scope and Reading Order

The goal is a maintainable personal task/schedule system that reduces the user's daily planning effort: trusted Tasks across courses, sport, life and other; explicit task relationships; available-capacity reasoning; concise daily recommendations; morning/evening review; recovery; weekly/long-term views; optional AI and historical learning. It is not sufficient to build a Task CRUD app or an LLM prompt that produces an attractive list without verified state and feasibility.

The plan contains **195 bounded task definitions in 11 catalogs**. Real courses, TaskTypes, accounts, layouts, Goals and recovery scenarios instantiate explicitly repeated definitions; this count is not a promise that all real instances are known or that the whole system takes a fixed number of equal-duration sessions. No fictional deadline or completion estimate is assigned to the project.

An AI should read:

1. [Plan control center](README.md) and [progress](PROGRESS.md).
2. This file, especially Sections 2–6 and 8–11.
3. One selected task card and the source documents linked at its catalog's beginning.
4. Completed prerequisite artifacts, actual implementation interfaces, recent diff and relevant targeted evidence.

Read all accepted intent when taking over the project or changing semantics. A task card is an execution boundary, not permission to ignore requirements in its module specification. Execute one task or one explicitly repeated instance per development session; do not turn a milestone into a single large coding request.

## 2. Frozen Product Invariants

| Boundary | Required behavior | Authority / primary implementation tasks |
| --- | --- | --- |
| Shared planning unit | Course, Activity, Goal, Exam and recurrence provide context; all executable workload is ordinary Tasks. No second Goal workload total. | D-034/039/057; M2-09, M5B-09 |
| Platforms/storage | n8n is the only workflow platform; PostgreSQL stores dynamic state; versioned declarative profiles/config remain in Git. Calendar describes occupancy. | D-003–006; M3A, M4, M5 |
| Task axes | Acceptance, binary INCOMPLETE/COMPLETE, disposition and derived trust/risk are distinct. Importance and three difficulty dimensions are 1–5; requiredness is REQUIRED/OPTIONAL/EXPIRING. Course importance is not a primary scalar. | D-025/035–037/043–044; M2-01 |
| Authority | External discovery/completion is evidence/candidate, even if highly confident. A resolved explicit user command authorizes its exact update; inferred extras do not. | D-029/033/058/064; M2-04, M3A-11 |
| Generation | An accepted generation relationship authorizes mapped counterparts without identical per-instance confirmation. Missing essential facts stay pending; template defaults alone are not blanket authority. | D-071/072; M2-06, M3B-04–06 |
| Typed relations | Creation direction, finish-before-finish, explicit finish-before-start, soft sequence and parent membership are distinct. Do not combine generation/order graphs into a false cycle. | D-061/071; M1B-05, M3B-02, M6-09 |
| Truth/history | Record actual confirmed out-of-order completion truthfully with violation. Preserve completed/cancelled/expired/reopened history; source removal is not Task cancellation. | D-069/071; M3A-14, M3B-07, M8-18 |
| Expiration | Under an accepted expiry condition, inform first, then revalidate and record EXPIRED. No extra acknowledgement; failed/unknown dispatch is not informed. Overdue REQUIRED is not automatically expired. | D-073; M3B-11–13 |
| Effort | User U remains canonical. Applicable valid model remaining-work B drives planning, even if smaller than U; unavailable model falls back to U with provenance. No max(U,B), U+B, or total-duration-as-remaining shortcut. | D-066/074; M2-02, M6-02, M8-02 |
| Parent/stage accounting | Stages partition one B; separate generated obligations have separate B. Actual elapsed work never mechanically reduces U or confirms completion. Parent completion remains authorized; rework retains history. | A0 §58/60; DATA_MODEL §12; M6-03, M3B-07 |
| Capacity/risk | Check hard deadline/window/dependency/minimum-session feasibility, not just hour totals. SAFE: C−R≥S; DANGER: 0≤C−R<S; EMERGENCY: C−R<0 or proven required placement deficit. Solver/data unknown is a diagnostic, not a false proof. | D-059; PLANNER §21; M6-07–12 |
| Calendar windows | Asia/Shanghai. Date-only deadline 23:59; preserve explicit instants. Forecasts include today and end today/today+2/today+6 at 23:59. Count only remaining usable capacity; reserve defaults remain 1/3/7 hours. | D-075/078; M4-10, M6-11 |
| Daily discretion | Protect required feasibility/reserve, then mainly importance. Future REQUIRED extras do not always outrank higher-importance OPTIONAL/EXPIRING. In SAFE, aggregate whole-day discretionary remainder ≤40 minutes stays free; no per-window ban. | D-060/076; M6-13–14 |
| Emergency | Any horizon EMERGENCY triggers provisional baseline → user choices → all-horizon recalculation. Optional removal alone cannot fix REQUIRED R; list removal is not canonical cancellation. | D-050; A0 §38; M6-18–19 |
| Human review | Morning refresh/full queue/special circumstance/plan; evening consolidated questionnaire, individual worked-on updates and explicit untouched unchanged-estimate batches. Missing facts remain pending. Silence is not confirmation. | D-024/051/065/077; M3B-08–10, M6-21–22 |
| Output | Concise actionable parent/stage recommendations, operative estimate and useful work-style labels; no exact clock times by default. Show all risks/worst mode and material exceptions; repeated references add no effort. | D-018/053; DAILY_BRIEF_TEMPLATE; M6-16–17 |
| Course/Goals | Course-specific units distinguish teaching and task-family progress; holes remain backlog. Initial catch-up triggers are three missed notes and exam-preparation phase. Goal onboarding precedes real activation. | D-038/047–049/056; M1-04, M5B |
| AI/learning | Core planning/validation works without live AI. Numeric models may calibrate automatically; behavioral policy requires review; explicit preferences win. Premium jobs are user-triggered export/import, not unattended ChatGPT web automation. | D-007–009/041/054; M7, M8-01–07 |
| Inactivity/runtime | Two consecutive Beijing days without normal interaction trigger reconciliation reminder. Final runtime remains active without the user's laptop. Minimum safeguards begin with persistence/ingestion, not late polishing. | D-011/055; M3B-14, M6-23, M8-14 |

All original O01–O08 audit boundaries are resolved. Remaining current-semester facts, provider/account scope, notification surface, costs and credentials are scoped input checkpoints in task cards, not reasons to reopen A0.

## 3. Architecture for Robustness and Extension

Use a small modular application with explicit ports/adapters and one PostgreSQL authority. This is an engineering direction to validate in M2, not a new user-selected programming language, hosting vendor or model provider. Avoid splitting into distributed services or adding queues/caches before measured need.

| Layer / logical artifact scope | Owns | Must not own |
| --- | --- | --- |
| `src/domain/` | Values, Task/relationship/effort semantics, pure policy checks | Provider SDKs, credentials, n8n nodes, arbitrary network calls |
| `src/application/` | Authorized commands, transactions, review/generation/expiry coordination, snapshots | Model confidence as authority; provider-specific field mappings |
| `src/ports/` | StateStore, Clock, EvidenceSource, CalendarSource, NotificationSink, Predictor, Solver, Renderer contracts | Hard-coded course/provider names |
| `src/adapters/db/` and `migrations/` | PostgreSQL constraints, transactional repositories, versioning, outbox/checkpoints | Bypassing command authority or replacing semantic validation |
| `src/adapters/calendar/`, `sources/`, `notifications/`, `ai/` | Provider mapping, scoped I/O, typed transport failures | Canonical personal-state decisions from raw evidence |
| `src/planner/` | Deterministic budgets, placement, horizons, allocation and diagnostics | Completion mutation, hidden policy learning, provider dependency |
| `src/learning/` | Numeric models and candidate behavioral patterns | Unreviewed behavioral policy activation or rewriting historical estimates |
| `src/renderers/` | Human formatting from versioned machine output | Recomputing workload totals or changing core Plan semantics |
| `profiles/`, `config/` | Versioned stable definitions and accepted default references | Secrets, live personal progress, automatic truth from templates alone |
| `formats/`, `tests/fixtures/` | Versioned machine schemas; synthetic semantic/provider fixtures | Credentials or copied private raw content |
| `workflows/` | Sanitized n8n exports, schedules, error/retry routing | Duplicated domain logic or a second orchestration platform |
| `scripts/`, `reports/acceptance/` | Reproducible checks, safe migration/restore/replay and redacted evidence | Claims unsupported by actual execution |

These paths are proposed logical scopes. **M2-16** chooses one language/toolchain and maps them to real filenames; later tasks edit that mapping rather than inventing parallel structures. Define public interfaces before their consumers. Critical state mutations follow schema → reference → authority → state-version checks → one transaction with audit. Canonical creation and durable outbox share that transaction. Network dispatch occurs outside DB transactions; unknown external effects are persisted and reconciled rather than blindly retried.

The PostgreSQL outbox/leases are domain reliability mechanisms. They do not introduce another workflow platform; n8n still orchestrates schedules and external integrations. Code and schemas are versioned and testable outside n8n, so changing a provider or workflow version does not rewrite planning semantics.

## 4. Rules for a Single AI Task

Every task card provides a stable ID, type, prerequisites, bounded deliverable, work and concrete acceptance/failure/extension conditions. The shared rules below are part of every card.

1. **Check readiness.** Read PROGRESS, the card, relevant semantic sources and completed prerequisite interfaces. Runtime implementation waits for M1/M1B/M2 gates; M2-16 permits only its bounded disposable toolchain-validation spike. Do not assume a credential, profile, API field, schema or artifact exists because this plan names it.
2. **Keep one outcome.** Usually one handler, migration group, rule, adapter slice, fixture set or operating drill; ordinarily one module and its focused tests, roughly 3–7 changed implementation files. This is a scope guideline, not a quota that excuses missing essential tests. Do not combine independent task IDs into a large rewrite.
3. **Resolve engineering details within authority.** Routine implementation choices consistent with accepted contracts do not need repeated product questions. Missing personal facts or semantic conflicts affect only the relevant task; document the precise blocker and continue independent ready work when appropriate.
4. **Split before expanding.** If a card turns out to span several providers, workflows or algorithm changes, add stable child IDs (`M6-10.a`, `.b`) with deliverables, dependencies and acceptance before coding; preserve the parent ID as a gate. Update the catalogs/coverage/progress. Do not hide multi-session work under DONE.
5. **Implement through contracts.** No direct connector/AI DB mutations; no production-only n8n logic; use injected Clock/fake ports and versioned schemas. Add extension/config hooks only where needed by a defined extension, avoiding speculative frameworks.
6. **Verify the important boundary.** Run the smallest meaningful positive/negative set for that change. For state/I/O reliability, include relevant duplicate, stale-version, restart, partial-failure or unknown-result cases. For INFO/SPEC, capture authoritative facts and contract/example consistency rather than writing meaningless unit tests.
7. **Review and record.** Inspect diff, confirm secrets are absent and source semantics still agree. Record artifact paths, exact commands or user-source evidence, observed results and limitations in PROGRESS. Update affected specs/formats if behavior or interfaces changed.
8. **Finish concretely.** One reviewable change with targeted evidence, accurate task status and follow-up blockers. No “implemented” claim from a file name, TODO stub, fake live test or unexecuted command. A failing required check keeps the task incomplete.

Suggested execution prompt:

```text
Implement task <ID> or instance <ID@scope> from its catalog.
Read plan/README.md, PROGRESS.md, the card, semantic sources and prerequisites.
Preserve accepted authority and invariants. Limit changes to the bounded outcome.
If scope exceeds one session, define dependent child tasks before implementation.
Run targeted positive/negative/failure checks, update docs and progress with evidence.
Report changed artifacts, observed checks, remaining risks and the next ready task.
```

This planning turn does not deploy a service, run a production workflow, send a notification or buy infrastructure. Actual external operations occur within the authorized scope of their future task execution.

## 5. Task States, Repeated Instances and Dependencies

Task definitions state initial `TODO`; **PROGRESS is the live ledger**, so stale initial catalog text never overrides completion evidence. Use `TODO`, `IN_PROGRESS`, `BLOCKED_USER`, `BLOCKED_DEPENDENCY`, `DONE`, or `NOT_ENABLED`. `NOT_ENABLED` is an explicit release-scope setting for optional functionality, never equivalent to implemented/tested DONE.

- `DONE`: required artifact and targeted acceptance evidence exist; no unresolved essential blocker. INFO needs confirmed statements; SPEC needs versioned usable contracts/examples; DEV needs runnable behavior; VERIFY/OPS needs executed observations.
- `BLOCKED_USER`: named missing current fact, account/scope, channel/budget preference or access. Ask only that relevant checkpoint; do not ask the user to inspect long AI-facing documents.
- `BLOCKED_DEPENDENCY`: prerequisite evidence/interface absent, failed or incompatible.
- Repeated task definitions instantiate IDs such as `M1-06@course=<stable-id>`, `M5-07@provider=<id>`, `M5-09@account=<id>` or `M8-23@scenario=<id>`. Exactly one scope per execution. Enumerate real instances from the confirmed inventory, not old chat. A template dependency means all instances required by the consuming scope; an explicitly empty inventory is recorded, not silently inferred.
- Prototype/offline and live gates are separate. Synthetic fixtures permit independent development when live credentials are missing; they cannot certify production connectivity, delivery or occupancy.
- M7 is optional. M8-19 additionally requires M7-14 evidence **only if AI is enabled in that release**. Disabled optional AI leaves its tasks NOT_ENABLED/TODO with rationale and does not block the deterministic release. Similar source instances apply only to confirmed enabled scope; core semantic/port tests are never waived.
- Invalidate affected downstream evidence after a breaking schema/interface/semantic change; do not merely leave old DONE markers. Explicit dependency IDs control order even when numbering differs (M3A-20 CI feeds M3A-19).

Do not require an entire milestone's live credentials to develop independent tasks whose explicit prerequisites are already passed. Keep intended milestone order and meaningful gate checks; do not bypass semantic gates for convenience.

## 6. Milestones and Task Catalogs

| Milestone/catalog | Tasks | Main prerequisites | Gate/output |
| --- | ---: | --- | --- |
| M0, A0 | Completed before this plan | Accepted repository/intent | Existing semantic authority; not reopened |
| [M1 — User/course/activity model](tasks/M1_USER_COURSE_MODEL.md) | 9 | Confirm current inventory | M1-09: reviewed profiles/axes/preferences |
| [M1B — TaskType presets](tasks/M1B_TASKTYPE_PRESETS.md) | 9 | M1-09 | M1B-09: split/no-split/default/relationship presets |
| [M2 — Contracts and toolchain](tasks/M2_CONTRACTS.md) | 18 | M1B-09 | M2-18: concrete versioned semantics, ports, fixtures, toolchain |
| [M3A — State foundation](tasks/M3_STATE_FOUNDATION.md) | 22 | M2-18 | M3A-19, including M3A-20 CI: PostgreSQL authorized/replayable prototype |
| [M3B — Relations/reviews/expiry](tasks/M3_RELATIONSHIPS_REVIEWS.md) | 18 | M3A-19 | M3B-16: complete persistent state/relationship/review prototype |
| [M4 — Calendar/capacity](tasks/M4_CALENDAR_CAPACITY.md) | 16 | M3B-16 | M4-16 fixture contract; M4-15 actual live Calendar evidence |
| [M5 — Sources/n8n](tasks/M5_INGESTION_N8N.md) | 21 | M3B-16; actual source scopes | M5-20 offline replay; M5-21 enabled live-source readiness |
| [M5B — Goals/Exam/cadence](tasks/M5B_GOALS_GENERATION.md) | 11 | M2/M3 relationship contracts; real Goal intake for real activation | M5B-11 ordinary Task generation/pacing; no second workload model |
| [M6 — Deterministic daily MVP](tasks/M6_PLANNER_DAILY_MVP.md) | 29 | M4-16, M5-20, M5B-11 | M6-26 offline normal/emergency; M6-29 live reviewed deterministic MVP |
| [M7 — Optional AI](tasks/M7_OPTIONAL_AI.md) | 15 | Stable M6 core and confirmed cost/scope | M7-15 optional validated providers/manual premium jobs |
| [M8 — Learning/operations/release](tasks/M8_LEARNING_RELEASE_OPERATIONS.md) | 27 | Passed core; explicit enabled-provider scope | M8-27 maintainable release with restore, drills and extension evidence |
| **Total** | **195** | Additional repeated instances are explicit | No runtime capability is complete merely because listed |

Primary next task after this planning deliverable: **M1-01**, current-semester inventory. M1 is still incomplete; this plan does not collect or guess the user's courses/activities.

Practical release slices:

- **Persistent-state slice:** M3A/M3B. Manual reviewed Tasks, relationship generation, history, batches, notices and safe replay. A read preview is not yet a feasibility-verified Daily Brief.
- **Offline deterministic slice:** M6-26 with proven ports and synthetic source/capacity fixtures. All core semantics work without AI; live access remains accurately unverified.
- **Live daily MVP:** M6-29 with actual enabled sources/delivery, reviewed facts, minimal restore/auth/freshness and shadow journey evidence.
- **Maintainable release:** M8-27 with learning/weekly/long-term behavior, operating/recovery evidence and measured limits. Optional AI is independently gated by enabled scope.

## 7. Decisions and User-Information Checkpoints

| Checkpoint | Owns the unresolved detail | Can proceed independently |
| --- | --- | --- |
| M1-01/03/06/07/08 | Actual courses, activity commitments, unit definitions, missing availability/preferences | Synthetic semantic planning; no invented current facts |
| M1B repeated instances | Real family workflows, defaults, relationship mappings/authorization | Reusable contract design from reviewed examples |
| M2-15 | Natural prototype review/delivery surface, caller/access boundary | Core schema and fake NotificationSink |
| M2-16 | One language, pinned dependencies, file map, local/CI commands | Engineering choice; accepted product semantics stay fixed |
| M4-01/02/15 | Actual calendar IDs/scope/auth and provider mapping | Fake Calendar, interval/time/capacity code |
| M5-05/06 and M5-10/11 | Actual email providers/accounts/platform layouts/access | Common ingest/parser/replay engine |
| M5B-01 | Actual Goal target/workload/cadence/phases | Generic Goal/Exam persistence and synthetic generators |
| M6-08 | Solver approach and bounded unknown/proof policy | Exact small oracle and frozen Solver interface |
| M6-27 | Always-on runtime, delivery channel, measured resource/cost/backup targets | Offline core; no hosting purchase without concrete need |
| M7-01/02 | Optional model provider, allowed jobs and cost caps | Deterministic MVP; manual/fake contracts |
| M8-15/17/20/26 | Measured restore/performance/retention limits and real pilot feedback | Synthetic benchmarks and rehearsed safe operating mechanisms |

Check current primary provider/library docs when implementing a real mapping/toolchain choice. Do not freeze external API fields from this conceptual plan. Record technical ADRs with alternatives, tradeoffs, measured evidence and replacement boundary; update DECISIONS only if accepted product policy or architecture meaning changes. Routine engineering choices do not masquerade as user preferences.

## 8. Reliability Is an Early Acceptance Requirement

| Risk / invariant | Required design and failure behavior | Earliest task / strong verification |
| --- | --- | --- |
| R01 Unauthorized truth mutation | Validate exact user/rule authority; candidates remain separate | M2-04, M3A-11 / M3A-19, M8-19 |
| R02 Lost or partial state/audit | Same DB transaction; rollback every related mutation | M3A-09 / M3A-19 |
| R03 Concurrent/stale edits | Expected-version conflicts, typed retry semantics | M3A-09–10 / M3B-15 |
| R04 Duplicate command/event | Durable command/occurrence uniqueness, request fingerprint | M3A-10, M3B-03–06 / M3B-15 |
| R05 Worker crash/poison event | Persisted outbox, leases, bounded batches/retries/quarantine | M3B-03/06, M5-16 / M8-24 |
| R06 Unknown external side effect | Store confirmed/failed/unknown delivery; no exactly-once promise for arbitrary providers | M2-07, M3B-12–13 / M3B-15, M8-16 |
| R07 Broken source/checkpoint | Ack only durable batches, cursor reset/full resync, preserve trusted state | M4-06, M5-08/16 / M4-14, M5-17 |
| R08 Stale/partial capacity | Explicit quality state, last trusted/manual-authorized fallback; no invented free time | M4-11 / M6-25–26 |
| R09 False feasibility | Deadline/window/session/order proof checks; bounded solver unknown; oracle | M6-07–12 / M6-25 |
| R10 False progress/effort | Separate U/B/actual/planned, batch membership and truthful outcomes | M2-02/05, M3A-15 / M3B-15, M8-11 |
| R11 Wrong local date/reserve | Injected Clock, natural-day cutoffs, remaining-only capacity, one reserve subtraction | M3A-02, M4-10 / M6-25 |
| R12 Model/provider outage | Deterministic core, capped calls, validated/fallback predictions | M6-02, M7-06 / M7-14 |
| R13 Restore/upgrade failure | Isolated restore early, version compatibility, later full rehearsal | M3A-05/18 / M8-16–17 |
| R14 Secret/privacy exposure | Minimal data, redacted logs/fixtures/exports, least privilege | M3A-03/16, M5 adapters / M8-18–19 |
| R15 Unlimited work/resource use | Finite occurrence/source windows, request/worker/solver limits, measured budgets | M3B-06, M5B-04, M6-08 / M8-20/24 |
| R16 Silent operational failure | Correlation/error/freshness from first modules; health/backlog/unknown metrics and playbooks | Shared DoD, M3A-20 / M8-12–13/23–24 |

Logical database side effects should be idempotent even under concurrent retries. External notification delivery may have ambiguous outcomes; retain uncertainty rather than asserting impossible universal exactly-once delivery. Do not hold a PostgreSQL transaction open across network calls. A healthy HTTP response or connector run is not evidence that user review, a plan or a dispatch succeeded semantically.

At each persistent boundary define: operation/occurrence key, expected version, transaction scope, durable checkpoint, crash states, retryable/permanent/unknown result, bounded resource policy, redacted correlation IDs and replay/rollback path. Keep alerts actionable and avoid indefinite retry storms. “Fail safely” must have the concrete behavior and evidence listed in the relevant card.

## 9. Extensibility Acceptance

| Extension | Expected small-change path | Required proof |
| --- | --- | --- |
| New course/activity | New reviewed profile/axis + one repeated M1 task | No course-name branch in Planner; same profile contract |
| New TaskType/template | Registered versioned defaults/preset and focused fixtures | Existing accepted Tasks/history unchanged |
| New generation/order type | Defined accepted semantics + versioned rule schema/handler/Solver support | Separate graphs; unknown type rejected safely; compatible old instances |
| New evidence provider/account | One port-conforming adapter + mapping + scoped n8n config | Common source authority/dedup/replay suite passes |
| New Calendar provider | CalendarSource mapping + conformance fixtures | Existing interval/capacity/Planner logic unchanged |
| New model/predictor | Registered port implementation + validity/cost metadata | U/history intact; fallback/deterministic core unchanged |
| New renderer/surface | Renderer/transport adapter from versioned Plan/command envelope | Same workload/risk semantics; no independent truth store |
| New workflow/deployment target | Sanitized n8n/export/config adapter | Domain tests work outside the workflow; no second orchestration platform |
| Schema/rule evolution | Additive contract or explicit adapter/migration, preserved version/audit | Old version supported explicitly or rejected with reason; no silent data loss |

M8-22 verifies actual extension paths with synthetic probes. Avoid dynamic arbitrary code/plugin execution merely to claim extensibility. Supported types and ports are explicit and validated. Configuration should define courses, templates, scoped rules and routing; it cannot grant authority through untrusted external content.

## 10. Verification and Gate Evidence

Use the project's real selected toolchain after M2-16, not commands invented as if they already exist. M3A-20 supplies the reproducible targeted check entrypoint and CI; each task reports the **exact command that actually ran**. Targeted checks expand only when new changes/failures or unresolved risks justify them.

| Layer | What it proves | Main owner |
| --- | --- | --- |
| Document/contract validation | Links/IDs, dependency DAG, schema/examples and semantic references | M2-13/17–18; every docs/interface change |
| Unit/property tests | Time/interval arithmetic, budgets, graphs, pure policy invariants | M3A-02, M3B-02, M4-08–10, M6 |
| PostgreSQL integration | Atomicity, uniqueness, constraints, concurrency, audit, migration/restart | M3A-04–19, M3B-15 |
| Adapter/fixture contracts | Fake/live mapping shape, pagination, malformed/partial/auth errors | M4-04/14, M5-17, M7-14 |
| Solver oracle/regression | Proven placement versus hour sums; feasible/infeasible/unknown | M6-07/25 |
| Fault/replay/security | Crash windows, duplicate commands, expired leases, unknown dispatch, injection/leaks | M3B-15, M5-17, M8-19/24 |
| Offline end-to-end | Complete normal/emergency/generation/review loop with controlled fixtures | M6-26, M8-11 |
| Live scoped validation | Actual account/calendar/provider/delivery behavior | M4-15, M5-18–21, M6-28, enabled M7 |
| Restore/upgrade/extension/pilot | Operability, measured recovery, evolvability and real usability | M8-16–17/22/26–27 |

Minimum gate evidence: task and contract versions, changed artifact paths, commands/check methods, expected and observed results, environment/scope, sanitized failure/recovery observations, known limitations and resulting readiness. No credentials, private raw pages or whole email bodies in versioned evidence. A user-source reference is enough for INFO but cannot substitute for a running code/restore/live test.

Runtime claims follow [TESTING_PLAN](TESTING_PLAN.md): planned, implemented, fixture-tested, integration-tested, live-verified and operationally rehearsed are different. The current planning deliverable checks documents and dependencies only; it runs no database, Planner, n8n, connector or learning algorithm.

## 11. Definition of Done and Change Propagation

A code task is DONE only when the bounded behavior is implemented through frozen interfaces, its critical positive/negative/failure cases pass, credentials/raw private data are excluded, no unresolved material semantic conflict remains, and the result is recorded in PROGRESS with observed evidence. A schema/fixture/interface change updates affected adapters, task prerequisites, formats and relevant semantic specifications before consumers are declared ready.

Mandatory propagation routes:

- Product/rule/authority change → A0 + DECISIONS + affected domain/I/O/planner specs + formats + tasks/tests + PROGRESS.
- Profile/TaskType change → USER_MODEL + DATA_MODEL + relationship/planning consumers + repeated-instance ledger.
- Relationship change → TASK_RELATIONSHIP + DATA_MODEL + IO + INTEGRATION + PLANNER + reliability/security/tests + task coverage.
- Provider/transport change → INTEGRATION/AI/OPERATIONS/SECURITY + port/mapping/conformance fixtures + workflow exports + live-readiness records.
- Task split/order/interface change → this plan/catalog + prerequisites/coverage + downstream invalidation + PROGRESS.
- Numerical model/behavior change → LEARNING + PLANNER + authority/observation provenance + versioned history/tests.

Do not add a second competing roadmap/status ledger. Main plan governs execution; task catalogs describe bounded work; source specifications govern semantics; PROGRESS records actual status/evidence. Long reports are for AI; routine user output stays concise.

## 12. File Replacement and Information Preservation

- Replaced this file's coarse F1–F13/phase roadmap with one executable plan and catalogs. Section 14 maps all 13 capabilities to tasks, preserving scope and intended dependency order.
- Replaced control README/PROGRESS duplication with concise links, live-state protocol and truthful readiness. Accepted intent/decisions, source module specifications and the human Daily Brief remain authoritative.
- Removed the completed `CONSISTENCY_AUDIT.md` working report from the active tree. It held no independent accepted user facts beyond the now-integrated source documents. Sections 2/13 preserve its operational invariants and C/O identifiers; original Git history remains available at the baseline commit `384d724c36992cee931a6a9d22e698330d3fddd6`.
- Retain ALIGNMENT_PLAN: it is the reusable semantic-versus-adapter alignment method and completed A0 gate, not a competing active development plan. Retain all specialized specs: deleting them would erase important domain detail.

No unique accepted requirement, decision ID or A0 section is removed. If future cleanup would remove such information, migrate it explicitly to its semantic owner and update all references before deletion.

## 13. Preserved Audit Findings and Closed Boundaries

| Original finding | Preserved invariant / task coverage |
| --- | --- |
| C01 | Source truth ≠ canonical personal truth; explicit commands/accepted rules provide authority — M2-04, M3A-11, M5-04 |
| C02 | Fixed difficulty/importance/risk scales; only compatible engineering precision remains — M2-01, M6-11 |
| C03 | Two-day inactivity trigger fixed; transport/repetition separate — M3B-14, M6-23 |
| C04 | Course context has no primary importance scalar — M1-02, M1B-01, M6-14 |
| C05 | No generic lead time or repeated A0 questions — M1-08, M1B-01, M6-06 |
| C06 | Acceptance/completion/disposition/trust separate — M2-01, M3A-07 |
| C07 | Numeric calibration automatic; behavioral/default/personal truth changes reviewed — M8-03/06–07 |
| C08 | Whole queue retained, high-impact first, no fabricated answers — M3B-08–10, M6-21 |
| C09 | Worst-horizon emergency invokes two rounds — M6-12/18–19 |
| C10 | OPTIONAL removal alone cannot fix REQUIRED deficit — M6-19/25 |
| C11 | Parent/stage/model/user accounting counts once — M2-02, M6-02–03 |
| C12 | Every recommendation has required fields; fragment references do not duplicate work — M6-16–17 |
| C13 | Accepted human template remains; machine encoding is separately versioned — M2-10, M6-17 |
| C14 | Generic Goal semantics before persistence; real activation later — M2-09, M5B |
| C15 | Authority/audit/version/recovery safeguards start early — M3A/M3B, M3A-18/20 |
| C16 | Collection/validation/planning do not depend on full AI Router — M5-03, M6-26, M7-06 |
| C17 | Exact risk/discretionary semantics; weekly output separately gated — M6-11/14/25, M8-08 |
| C18 | Authority by subject; actual progress never overrides product policy — README, A0/DECISIONS, this plan, PROGRESS |
| C19 | User-requested detailed planning precedes M1; no invented modeling/runtime completion — this deliverable, M1-01/09 |
| C20 | Raw-content minimization ≠ deleting normal semantic history — M8-18 |
| C21 | Deadline/window/beyond-7-day/timezone/staleness limits explicit — M4-10–11, M6-06/10–12 |

| Boundary ID | Resolution / durable source | Main acceptance tasks |
| --- | --- | --- |
| O01 | Task relationships and scoped generation authority — D-071/072, TASK_RELATIONSHIP | M3B-15, M6-09 |
| O02 | Notice before recording expiration — D-073 | M3B-11–15 |
| O03 | U/B separation, parent/stage/rework accounting — DATA_MODEL §12; D-074 | M3B-07, M6-03/25 |
| O04 | Valid model-first remaining-work estimate, user fallback — D-074 | M6-02/25, M8-02 |
| O05 | Beijing/date-only 23:59/natural days including today — D-075/078 | M4-10/14, M6-11/25 |
| O06 | Required placement feasibility and coordinated horizon accounting — PLANNER §21 | M6-06–12/25 |
| O07 | Aggregate whole-day ≤40-minute SAFE remainder — D-076 | M6-14/25 |
| O08 | Explicit untouched unchanged-estimate batches — D-077 | M3B-09/15, M6-22 |

All are resolved specifications. Their code/test tasks remain incomplete until evidence exists; closing an audit question does not implement its feature.

## 14. Functional Completeness Map

| Original capability | Detailed work |
| --- | --- |
| F1 Personal domains | M1-01/02/07; shared Task schema M2-01 |
| F2 Courses/activities | M1, M1B; course-axis/backlog M5B-08 |
| F3 Input system | M2-03–05/15, M3A-11–16/21–22, M3B-08–10/17–18; guided M6-21–22 |
| F4 Persistent state | M3A; M3B relationship/review/expiry persistence |
| F5 Goals/milestones | Generic M2-09 before DB; real onboarding/generation M5B |
| F6 Calendar/time | M2-08, M3A-02, M4 |
| F7 External collection | M5 shared pipeline + repeated provider/account/layout instances |
| F8 Reconciliation/recovery | M3B-08–14 early; M5 source health; M6 daily; M8-10/23–24 |
| F9 Planner | M6 budget/feasibility/allocation/override; M8-08–09 weekly/long-term |
| F10 AI Router/jobs | M2-11/12 contracts; M7 optional adapters/export/import |
| F11 Daily output | Existing human template; M2-10 schema; M6-16–24 daily loop |
| F12 Learning/self-correction | Historical observations early; M8-01–11 with reviewed behavior |
| F13 Task relationships | M1B-04–06, M2-06, M3B-01–07; Planner M6-09 |

## 15. Plan Verification and Current Limit

Validate the complete documentation inventory, local links/anchors, unique task/decision/intent IDs, all dependency references and acyclicity, milestone counts/gates, all F1–F13 and C01–C21/O01–O08 mappings, replacement reference cleanup and critical semantic propagation. Before publishing verify the remote base head; after publishing compare remote file blobs with the checked artifacts, including retired-file deletion.

This is document/task-plan verification only. It proves neither a working implementation nor that the selected future solver/provider/deployment passes runtime tests. M0/A0 and this planning deliverable are complete; next is M1-01. Future task changes remain versioned and evidence-based.

The 2026-10-06 local verification passed for 33 Markdown files, 11 catalogs/195 task definitions, 528 local links/319 fragments, acyclic dependencies, complete milestone gates, AI-independent deterministic-release dependencies, 79 decision IDs/62 A0 sections, F/C/O/R traceability, retired-file cleanup and whitespace. Publication is verified separately against GitHub; runtime tasks are still TODO.
