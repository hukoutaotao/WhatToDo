# WhatToDo — Live Project Progress

Last updated: 2026-10-07 (Asia/Shanghai).

## 1. Actual State

**M1-01 identity intake and M1-02 stable-profile proposal are complete. Current task: M1-03, course-001 details, awaiting user input.**

- M0 repository/control foundation: complete.
- A0 accepted interaction/semantics alignment: complete.
- Original audit boundaries O01–O08: resolved in accepted intent/decisions and module specs.
- Detailed plan: [DEVELOPMENT_PLAN](DEVELOPMENT_PLAN.md) + 11 linked catalogs, 195 bounded definitions with explicit dependencies and acceptance; repeated real instances are still to be enumerated.
- M1 identity intake: [confirmed inventory](intake/CURRENT_INVENTORY.md), nine courses and six non-course commitments with stable provisional IDs and user-source evidence.
- M1-02 SPEC proposal: stable profile v0.1.0-draft and a clearly synthetic Course/Activity example; frozen machine validation is still future work.
- M1/M1B/M2 gates: not complete; reviewed detailed profiles, presets, concrete machine schemas and toolchain selection do not yet exist.
- Runtime, database, n8n, collectors, Calendar adapter, Planner, renderer, AI Router, learning and deployment: not implemented or runtime-verified.

M1-01 is DONE at the identity-intake boundary; M1-02 is DONE as a versioned SPEC proposal. M1-03 (scope: course-001) is BLOCKED_USER for the actual course workflow. No coding/deployment task is active. Task catalogs state initial TODO; this ledger is authoritative for actual status. Inventory intake does not complete M1 or implement runtime behavior.

## 2. Next Work and Information Gates

Current task: [M1-03](tasks/M1_USER_COURSE_MODEL.md#m1-03), course-001 — 复变函数与数理方程. The first scoped question asks what recurring work the course creates and how that work normally flows. Collect missing difficulty, duration, fragmentation and timing details in subsequent small prompts as needed; never assume a generic course's homework/preview/review pattern. Then define its axis, refine the reusable profile, and instantiate the other eight courses and six activities individually. The Other domain, exact term label and detailed scheduling facts are unknown; do not infer empty scope or fixed Calendar intervals. M1B presets and M2 contracts precede persistence.

Ask only the current task's missing facts. Already accepted: four life domains; Task-based importance/requiredness/difficulty; parent/stage structure; explicit task relationships and scoped generation; notice-before-expiry without extra acknowledgement; model-first remaining-work planning with U retained; Beijing/date-only 23:59; natural-day windows including today; daily reserve and aggregate ≤40-minute SAFE rule; explicit unchanged-estimate batches; full review/emergency/inactivity/learning authority rules. Do not reopen them.

Later input checkpoints are listed in DEVELOPMENT_PLAN §7: actual calendar/source scopes and access, real Goal examples, prototype delivery/access surface, runtime/cost/backup targets and optional model budget. They are not all requested now. Empty or remembered profiles are not current truth.

## 3. Live Task Ledger

Default status for every unlisted task/instance: TODO. M1-01 is DONE based on the current user statement and intake artifact. The list confirms identities only; no detailed profile is inferred from prior conversation or an empty template.

| ID / instance | Status | Evidence / blocker | Next action |
| --- | --- | --- | --- |
| PLAN-2026-10-06 | DONE | Detailed plan/catalogs, dependency and document checks; publication verified separately | M1-01 intake started |
| M1-01 | DONE | [Intake v1](intake/CURRENT_INVENTORY.md); source `USR-20261007-INVENTORY-01` (2026-10-07 user reply). Nine exact course names, four sports, two life activities, 15 unique IDs with identity confirmation; frequencies/term/Other remain unknown. Published as `aa00b5511b3f827c12b4960acaaaef994cd72277`; all eight changed files and main head read back successfully. | Identity prerequisite for M1-02 met; detailed profiles remain pending. |
| M1-02 | DONE | [Profile v0.1.0-draft](USER_MODEL_PLAN.md#13-m1-02-stable-profile-format-proposal), [synthetic example](examples/STABLE_PROFILE_V0_1.synthetic.json); in-session JSON/example/contract checks described below. | M1-03 representative course; refine proposal after real M1-04 evidence. |
| M1-03 | BLOCKED_USER | M1-01/02 artifacts exist; scope is course-001. Real workflow/task families for 复变函数与数理方程 have not been supplied. | Ask one natural-language question about the work this course creates; retain unknown details. |

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

## 8. Execution Session — 2026-10-07 (M1-02 and M1-03 Intake)

- Completed prerequisite: M1-01 published at `aa00b5511b3f827c12b4960acaaaef994cd72277`; 34 Markdown files/540 local links/318 fragments and 15 confirmed unique identities checked. All eight changed GitHub files and the expected main head were read back.
- M1-02 artifacts: USER_MODEL_PLAN §13, proposal version `0.1.0-draft`; examples/STABLE_PROFILE_V0_1.synthetic.json, example version 1. DATA_MODEL §14 links ownership/compatibility boundaries; the catalog links the delivered artifacts.
- Targeted check method: in-session JavaScript JSON parse and contract/example checks; source/pointer/reference resolution; synthetic isolation; no Course importance or dynamic state; valid Activity without course axis; unknown versus explicit zero; critical extension handling; Markdown paths/anchors and whitespace. Observed: two valid synthetic profiles and lossless JSON round-trip; eight negative variants rejected (live progress, known/unresolved contradiction, missing provenance, unsupported version, unknown critical extension, unresolved TaskType version, root Course importance and unsupported review marker); real-user activation of a synthetic record was also rejected. This is an ephemeral proposal check, not a shipped runtime validator or final JSON Schema test.
- Result: M1-02 DONE at SPEC scope. The shared envelope, versioning, source evidence and scoped unknowns can be exercised by M1-03/04, then refined at M1-05. No real profile has been reviewed, and no TaskType registry, database or Planner is implemented.
- Next intake: M1-03 (scope: course-001) uses the first course in the user's supplied order. This is an execution scope, not a course priority. Actual work families/workflow are BLOCKED_USER; only that course's missing facts are requested now.
- Publication check: read back every changed artifact at the new commit and verify the expected main head. Do not treat pre-publication checks as remote verification.
