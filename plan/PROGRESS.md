# WhatToDo — Live Project Progress

Last updated: 2026-10-07 (Asia/Shanghai).

## 1. Actual State

**M1-01 identity intake is complete: nine courses and six non-course commitments. Next ready task: M1-02.**

- M0 repository/control foundation: complete.
- A0 accepted interaction/semantics alignment: complete.
- Original audit boundaries O01–O08: resolved in accepted intent/decisions and module specs.
- Detailed plan: [DEVELOPMENT_PLAN](DEVELOPMENT_PLAN.md) + 11 linked catalogs, 195 bounded definitions with explicit dependencies and acceptance; repeated real instances are still to be enumerated.
- M1 identity intake: [confirmed inventory](intake/CURRENT_INVENTORY.md), nine courses and six non-course commitments with stable provisional IDs and user-source evidence.
- M1/M1B/M2 gates: not complete; reviewed detailed profiles, presets, concrete machine schemas and toolchain selection do not yet exist.
- Runtime, database, n8n, collectors, Calendar adapter, Planner, renderer, AI Router, learning and deployment: not implemented or runtime-verified.

M1-01 is DONE at the identity-intake boundary. M1-02 is ready without additional user facts. No coding/deployment task is active. Task catalogs state initial TODO; this ledger is authoritative for actual status. Inventory intake does not complete M1 or implement runtime behavior.

## 2. Next Work and Information Gates

Next ready task: [M1-02](tasks/M1_USER_COURSE_MODEL.md#m1-02), a versioned stable profile proposal and synthetic example grounded in the completed inventory. Then model course-001 (the first course supplied), its axis, refine the reusable profile, and instantiate the other eight courses and six activities individually. The Other domain, exact term label and detailed scheduling facts are unknown; do not infer empty scope or fixed Calendar intervals. M1B presets and M2 contracts precede persistence.

Ask only the current task's missing facts. Already accepted: four life domains; Task-based importance/requiredness/difficulty; parent/stage structure; explicit task relationships and scoped generation; notice-before-expiry without extra acknowledgement; model-first remaining-work planning with U retained; Beijing/date-only 23:59; natural-day windows including today; daily reserve and aggregate ≤40-minute SAFE rule; explicit unchanged-estimate batches; full review/emergency/inactivity/learning authority rules. Do not reopen them.

Later input checkpoints are listed in DEVELOPMENT_PLAN §7: actual calendar/source scopes and access, real Goal examples, prototype delivery/access surface, runtime/cost/backup targets and optional model budget. They are not all requested now. Empty or remembered profiles are not current truth.

## 3. Live Task Ledger

Default status for every unlisted task/instance: TODO. M1-01 is DONE based on the current user statement and intake artifact. The list confirms identities only; no detailed profile is inferred from prior conversation or an empty template.

| ID / instance | Status | Evidence / blocker | Next action |
| --- | --- | --- | --- |
| PLAN-2026-10-06 | DONE | Detailed plan/catalogs, dependency and document checks; publication verified separately | M1-01 intake started |
| M1-01 | DONE | [Intake v1](intake/CURRENT_INVENTORY.md); source `USR-20261007-INVENTORY-01` (2026-10-07 user reply). Nine exact course names, four sports, two life activities, 15 unique IDs with identity confirmation; frequencies/term/Other remain unknown. | M1-02 stable profile proposal; no detailed course/activity readiness yet. |

During execution, add only active, blocked, completed or explicitly NOT_ENABLED tasks/instances here. Record: ID/scope, contract/artifact versions, changed paths, exact checks or user-source reference, observed result, limitations and downstream readiness. Keep a concise session history; do not paste another full roadmap.

Use TODO, IN_PROGRESS, BLOCKED_USER, BLOCKED_DEPENDENCY, DONE, NOT_ENABLED as defined in DEVELOPMENT_PLAN §5. NOT_ENABLED is an explicit optional release-scope decision, not implemented DONE. After a breaking change, invalidate affected downstream evidence and name the affected task IDs.

## 4. Verification Boundaries

The completed detailed-plan deliverable verified Markdown/task-plan consistency, local links/anchors, identifiers, dependencies and acyclicity, capability/robustness mappings, retired-file cleanup and the published file set. It does not run runtime tests for future artifacts.

Previous detailed-plan local checks passed: 33 Markdown files, 11 catalogs, 195 unique task definitions, 528 local links and 319 linked anchors; acyclic dependencies and milestone gate coverage; deterministic release without a mandatory M7 dependency; all 79 decision IDs and 62 A0 sections; preserved F1–F13, C01–C21, O01–O08 and R01–R16 mappings; retired-file/stale-status cleanup and whitespace checks. Remote head/blob/deletion verification is recorded by publication results, not inferred from these local checks.

Future task reports must distinguish planned, implemented, fixture-tested, PostgreSQL integration-tested, live-verified, restore-rehearsed and operating-pilot evidence. A fake connector/notification test never proves actual credentials or delivery. A schema or task card is not an implementation.

## 5. Retained History and Document Ownership

Prior accepted facts remain in [A0_USER_INTENT](A0_USER_INTENT.md), [DECISIONS](DECISIONS.md) and specialized specs. D-001–D-078 and A0 Sections 1–61 are preserved; D-079/A0 §62 record this detailed-plan request. The retired audit's C/O traceability is now DEVELOPMENT_PLAN §13.

Earlier documentation commits: full audit `12189642e300dacf62a46bae9d8a51d8c1a61530`, internal boundary resolution `af78d7d2fe7fb4e8902fdbb58ae81886e1d94a5d`, answer synchronization `a8fb03655221f180dd859c26da36f3f7703441ba`, natural-day clarification `384d724c36992cee931a6a9d22e698330d3fddd6`. These are documentation changes, not runtime releases.

Execution order/tasks: DEVELOPMENT_PLAN and catalogs. Actual evidence/status: this file. Product policy: A0/DECISIONS. Do not infer completion from milestone names, technology availability, old chat or generated documentation.

## 6. Execution Session — 2026-10-07 (Development Start)

- User source: the request to use the GitHub progress document and start development if it exists. This authorizes beginning the planned execution sequence.
- Observed baseline: PROGRESS already exists; M1-01 has no prerequisites and requires confirmed current-semester courses/recurring activities. The catalog and USER_MODEL_PLAN agree on inventory-first intake.
- Changed scope: this progress ledger only. No accepted product decision, course profile, code, database or deployment was changed.
- Targeted checks: each intended text replacement occurs exactly once; existing Markdown links are preserved; the M1-01 ledger entry is unique and BLOCKED_USER; no trailing whitespace is introduced. Publication is checked by reading back the committed file and branch head; those remote results must not be inferred from the pre-publication text checks.
- Remaining limitation: no confirmed inventory has been received. M1-02 remains TODO with M1-01 incomplete; this session provides no runtime-test evidence.

## 7. Execution Session — 2026-10-07 (M1-01)

- User source: `USR-20261007-INVENTORY-01`; nine current courses, four named sports and two named life arrangements. The names are authoritative; no historical facts were imported.
- Artifact: intake/CURRENT_INVENTORY.md, version 1. All 15 items have stable provisional IDs and identity confirmation. The circuits theory/experiment courses are distinct; term, schedules, detailed profiles and Other-domain coverage remain unknown.
- Propagation: root/control README, USER_MODEL, ALIGNMENT, PROJECT and DEVELOPMENT_PLAN now link to the identity artifact and defer live next-task readiness to this ledger. Product policy/decisions and task dependencies did not change.
- Targeted checks: exact ordered names/counts, unique IDs, per-item confirmation, unknown-boundary wording, Markdown link targets/anchors and whitespace. Publication is checked separately by committed-file read-back and expected main head.
- Result: M1-01 DONE; M1-02 ready. M1-03 and repeated instances are not complete. No runtime-test or Calendar-delivery evidence exists.
