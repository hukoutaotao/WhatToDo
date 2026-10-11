# WhatToDo

A personal task/schedule system that reduces daily planning effort through trusted Tasks, available-capacity reasoning, concise recommendations and short morning/evening reviews.

Start at the [plan control center](plan/README.md), then read [live progress](plan/PROGRESS.md) and the [detailed development plan](plan/DEVELOPMENT_PLAN.md). The plan contains **195 base tasks in 11 catalogs** plus explicitly recorded development children, with dependencies, deliverables, failure checks, robustness, extensibility and acceptance gates.

Accepted meaning lives in [A0 intent](plan/A0_USER_INTENT.md), [decisions](plan/DECISIONS.md) and linked module specifications. Task relationships, model-first planning, reviewed personal state, Beijing natural-day forecasts and daily reserve rules are already aligned.

Current state: sixteen offline development slices run with synthetic regression checks: Task core, effort accounting, provenance, authorization, reviews, relationships, expiration, time/occupancy, Goals/Exams, [Plan/forecast handoff](formats/output/PLAN_FORECAST_CONTRACT.md), [AI-result handoff](formats/input/AI_RESULT_CONTRACT.md), [application ports/fakes](formats/input/APPLICATION_PORTS_CONTRACT.md) [semantic traceability/scenarios](tests/fixtures/semantic/README.md) and [guided review prototype](formats/input/GUIDED_REVIEW_PROTOTYPE.md). A [checked relational/migration draft](database/README.md) additionally maps their ownership; [a local Python/PostgreSQL spike](toolchain/ADR-001.md) now verifies it against an isolated synthetic database. No application database or service is activated. Their contracts are indexed in [input formats](formats/input/README.md) and [output formats](formats/output/README.md). M0/A0 and detailed planning are complete; M1/M1B and the application runtime are not; the D-080 generic M2 baseline now passes with pinned inputs/ownership. The user has prioritized autonomous system development before remaining personal intake; missing facts remain unknown. Confirmed names are recorded in the [current inventory](plan/intake/CURRENT_INVENTORY.md). Use live progress for the next ready task.

Architecture: n8n-only orchestration; PostgreSQL dynamic state; versioned declarative profiles/config; Calendar occupancy; deterministic-first core and replaceable optional AI. Reliability starts with the first persistent-state prototype. The former coarse roadmap and completed audit working file have been consolidated into the new plan's rules and traceability map.

[Cross-contract/version checks](formats/input/CONTRACT_EVOLUTION.md) additionally compose five offline workflows through the existing domain/schema/fake-port boundaries. Unsupported versions retain their original bytes and fail explicitly; supported shapes still require domain and authority checks. No application release gate is closed by these checks.

The [generic Task aggregate](formats/input/TASK_AGGREGATE_CONTRACT.md) now joins Task/effort/time/session/source facts with consistency checks and actual isolated PostgreSQL probes. Historical checkpoints are preserved; live progress records the current generic gate and its limits.

The [private package foundation](toolchain/PACKAGE.md) adds a verified clean
offline installation, injected UTC clocks/Beijing date values and
[layered configuration](config/README.md). These modules are available for the
next persistence tasks. Course intake remains partly deferred; missing personal
facts do not block this generic development scope.

An [isolated PostgreSQL test harness](toolchain/POSTGRES_TESTS.md) now separates
application, migration and read-only test roles, checks SCRAM authentication and
cleans up its own test databases on success or failure. This enables the next
migration and repository development tasks.

The [migration executor and startup gate](database/RUNTIME_MIGRATIONS.md) now
apply pinned SQL atomically, retain failure/retry history and reject incompatible
or incomplete schemas. Native checks cover replay, rollback, connection loss
and commit-acknowledgement reconciliation; application repositories remain next.

[Versioned definition repositories](database/DEFINITION_REPOSITORIES.md) now
cache exact Git-backed profiles/templates with immutable defaults and checked
dependencies. Native tests prove new defaults preserve existing Task history;
schema and authority validation is now available. Remaining course
details and other personal intake stay deferred until later activation work.

[Task/stage repositories](database/TASK_REPOSITORIES.md) now preserve current
and historical aggregate bytes, separate lifecycle/trust values and permanently
bound stage ownership. Their internal append operation requires a separately
prepared exact-permit/audited transaction; the complete command service remains
later work. Native tests cover persistent roundtrip and rollback.

[Source/candidate repositories](database/EVIDENCE_REPOSITORIES.md) now retain
scope-bound source versions, field provenance, conflicts and pending history.
Native tests cover tombstones, raw-content minimization and reviewed replay,
with canonical Task/authority/audit state preserved. Current progress records
715 regression methods and a seventeen-step runtime schema with 82 domain tables.

[Atomic Task transactions](database/ATOMIC_TRANSACTIONS.md) now commit exact-permit
updates, full audits, command receipts and version advances together. Native
checks prove simultaneous-writer protection and rollback, and preserve unknown
outcomes after lost commit acknowledgement. Strict resolved-authority validation
is implemented; later work and stage handlers remain planned.

[Durable command replay](database/COMMAND_LEDGER.md) now returns original owned
receipts after concurrent retries, lost acknowledgement or restart. Changed
content under one ID conflicts; later Task edits and expired permits preserve
historical replay. Receipt lookup retains unknown outcomes until observed.

[Command validation and resolved authority](database/COMMAND_VALIDATION.md) now
check strict shape, independent source-backed grants, current references and
complete Task effects before publication. Native evidence covers rejected forged
approval/extra fields, accepted rule scope, verified expiry and changes after
validation. Clear resolved instructions and owned retries need no second approval.
Manual Task creation is now implemented; personal intake remains deferred.

[Manual Task creation](database/MANUAL_TASK_CREATION.md) now copies independently
approved exact-version defaults with provenance, persists missing/conflicting
facts as lossless pending drafts and creates one accepted Task per command.
Explicit initial U is a separate observation committed with the Task and audit;
retries return the original creation without new facts or another approval.
[Explicit Task fact updates](database/TASK_FACT_PATCHES.md) now preserve source
provenance, deadline precision, history and original-request replay, with atomic
due/remaining support facts. Fifteen focused methods, 32 native checks and the
421-method full suite pass. The default 30 schemas remain unchanged; the new
contract requires explicit selection. [User-confirmed completion and
cancellation](database/TASK_LIFECYCLE.md) now publish parent/stage zero U atomically,
retain actual-work history and avoid inferred work timestamps. Fourteen focused
methods, 34 native lifecycle checks and 435 full methods pass. The next ready
module records reported actual work. Current-semester profile activation, later
handlers and the complete runtime remain separate work.

[Actual-work reporting](database/WORK_REPORTS.md) now retains original increment
or cumulative reports, settles actual increments and deduplicates observation
IDs across transport retries. The exact permit, full audit and receipt bind both
the Task revision and immutable report. Spent time preserves U/completion;
explicit U is separate, and unreported session bounds stay unknown. Native
rollback/concurrency/restart checks and clean offline installation pass. The
next ready scope is Task/history read models; personal intake and full
runtime activation remain deferred.

[Direct-user creation input](formats/input/DIRECT_USER_CREATION.md) now supports
bounded Chinese phrases and ordinary guided text answers. It retains exact
statements, independent caller/account context and the frozen proposal envelope,
then hands clear input to the existing authorized creation service. Missing facts
stay pending; uncertainty cannot silently create a Task. Native integration,
actual stdin and installed-package checks pass. Other command classes and the
complete transport/runtime remain later work.

[Owned reference resolution and clarification](database/COMMAND_RESOLUTION.md)
now resolves exact IDs/unique names, asks only necessary scoped questions and
retains partial answers under the original command. Immutable history, source
ownership, stale-reply rejection, concurrency and lost acknowledgement pass
native checks. Resolved commands still use existing authorized handlers. The
next ready card is Task/history read models; personal intake stays
deferred and the complete system is unfinished.

[Authenticated prototype transport](formats/input/PROTOTYPE_COMMAND_TRANSPORT.md)
now exposes existing handlers through a loopback-only HTTP API and the same
versioned machine envelope intended for n8n. Independent credential/operation/
Task scope checks precede handlers; source scopes remain bound to each principal.
Typed unknown results preserve postcommit reconciliation. Actual HTTP/native
handoff and clean installation pass; Task/history read models are next.

[Owned read models](database/READ_MODELS.md) expose Task/history/pending views with
retained outcomes, minimal provenance and durable signed pagination. Thirty-one
focused methods, 20 native read checks and current storage/transport regressions
pass. [Synthetic backup/restore](toolchain/BACKUP_RESTORE.md) now preserves the
76-table prototype, audit/receipts and configuration references in a separately
restored database. Concurrent capture, corruption rejection and actual late
restore rollback pass. [Isolated baseline CI](toolchain/CI.md) now reproduces
pinned setup, package/contract/domain/document checks and synthetic PostgreSQL in
a fresh Windows checkout. Credential, contract and authority regressions block
later phases; diagnostics exclude raw output and database artifacts. Next ready
work is canonical-event outbox persistence; live activation stays deferred.

[Persistence foundation acceptance](reports/acceptance/M3A.md) now verifies the
same-Task HTTP create/patch/work/complete journey, stale and unauthorized writes,
atomic rollback/replay and independent restore in a freshly bootstrapped checkout.
All 15 bounded requirements, 602 methods and 113 native checks pass. The broader
relationship/review runtime, integrations, planning and deployment remain open.

[Typed relationship storage](database/RELATIONSHIP_STORAGE.md) now preserves accepted rule/link versions and exact provenance. Current regression passes 715 methods and 197 native checks; personal intake remains deferred.

[Bounded relationship graph validation](database/RELATIONSHIP_GRAPH_VALIDATION.md) now verifies separately typed graphs, precise diagnostics and explicit generation resource limits. Current package includes 73 modules/74 source files; scoped generation and bounded processing are implemented, while personal activation remains deferred.

[Canonical creation outbox](database/CREATION_OUTBOX.md) now preserves the first source snapshot atomically and supports scoped delivery leases, retry/restart recovery and fenced result replay. Delivery state remains separate from Task completion. Rule evaluation and scoped atomic target generation are available; bounded delivery orchestration remains next.

[Exact-version generation evaluation](database/GENERATION_EVALUATOR.md) now constructs a validated independent Task or shared-parent stage, or explicit pending facts, with original source/default/template provenance. [Scoped counterpart persistence and deduplication](database/GENERATION_RUNTIME.md) are now verified.

[Composite generation foundation](database/GENERATION_COMMIT_FOUNDATION.md) now prepares exact Task/stage/link/occurrence effects and provides immutable occurrence history with legacy-preserving migration. M3B-05.a and the [scoped runtime](database/GENERATION_RUNTIME.md) are verified; parent M3B-05 is DONE. Actual concurrent deduplication, parent-stage CAS, disconnect rollback and lost-acknowledgement reconciliation pass. [M3B-06 bounded processing](database/GENERATION_PROCESSING.md) integrates durable checkpoints, lease fencing, cumulative chain budgets and recovery. M3B-06 is DONE after 30-phase CI and clean installation; truthful stage rework follows.
