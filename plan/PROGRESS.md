# WhatToDo — Live Project Progress

> This file is the canonical live project-status handoff.
> Update it after every meaningful planning or implementation session.

## 1. Snapshot

Last updated: 2026-10-06

Overall status: **DOCUMENT CONSISTENCY AUDIT COMPLETE; DETAILED PLANNING NEXT**

Current milestone: **M0 COMPLETE → A0 COMPLETE → M1 NEXT / INCOMPLETE**

Current session result: full-document consistency correction, before the newly requested detailed project plan.

Current phase: **Phase 1 — Define What the System Understands**

Implementation status:
- Production system: not started
- Database implementation: not started
- n8n workflows: not started
- Calendar integration: not started
- Email integration: not started
- Learning-platform integration: not started
- Planner implementation: not started
- Historical-learning implementation: not started
- AI Router implementation: not started

This is intentional. A0 semantic alignment is complete; M1/M1B/M2 still precede infrastructure implementation.

---

## 2. Completed

### Planning/control foundation
- GitHub repository exists: `hukoutaotao/WhatToDo`.
- `plan/README.md` defines authority, dependencies, propagation rules, and new-AI bootstrap.
- `plan/PROJECT_PLAN.md` defines architecture.
- `plan/DEVELOPMENT_PLAN.md` defines ordered milestones.
- `plan/DECISIONS.md` records accepted/superseded decisions.
- Specialized plans exist for alignment, user/course modeling, data model, I/O, integrations, Planner, historical learning, AI execution, operations, security/privacy, and testing.
- `formats/input/` and `formats/output/` exist.
- `formats/output/DAILY_BRIEF_TEMPLATE.md` stores the accepted conceptual Daily Brief.

### Alignment Gate A0 — COMPLETE
A0 is complete after five rounds of user-AI alignment plus a consistency audit.

Accepted semantics include:
- Task is the fundamental planning unit.
- Course/domain/goal/source layers provide context, grouping, defaults, generation, and long-horizon structure.
- Normal interaction is morning + evening, roughly 5–10 minutes each.
- Morning: reconcile → clear confirmations → guided special-circumstance question → capacity/risk → Daily Brief.
- Evening: one consolidated review prompt, then follow-up only where required.
- Canonical Task-state changes require user review by default.
- External evidence creates candidates; no external completion shortcut exists in v1.
- Parent Task completion is primarily INCOMPLETE / COMPLETE; progress uses cumulative actual effort, remaining effort, and child stages.
- Every future-relevant incomplete Task must receive a user-provided remaining-effort estimate in review.
- User remaining-effort estimate remains canonical; model estimate is derived/advisory.
- Child stages may be reopened for rework with audit history retained.
- Task importance uses 1–5.
- Requiredness uses REQUIRED / OPTIONAL / EXPIRING; EXPIRING has an expiration point.
- Three difficulty dimensions use 1–5: thinking depth, repetitive volume, new-learning load.
- TaskType templates provide defaults; concrete Tasks inherit and may override.
- Parent deadline + child stage/subtask planning is accepted.
- Course Progress Axis uses course-defined units and tracks teaching progress plus task-family progress.
- Default academic sequences may be soft or hard; soft sequences may be bypassed to protect REQUIRED feasibility.
- Older Unit-linked unfinished work creates backlog/accumulation warnings.
- Exam is an independent event/object; preparation is generated as Tasks/Goals.
- Initial review triggers include three consecutive missed post-class note tasks and exam-preparation phase.
- SAFE / DANGER / EMERGENCY use required-work feasibility:
  - SAFE: required work fits while preserving ~1 hour/day safety reserve.
  - DANGER: required work fits but the reserve is breached.
  - EMERGENCY: required work exceeds total usable capacity.
- 1-day / 3-day / 7-day risks are reported separately; overall mode is the worst horizon.
- When SAFE and only a ~40-minute-or-smaller residual gap remains, normally leave it free rather than filling it for utilization.
- No generic "start N days early" field is required.
- First protect REQUIRED feasibility and safety reserve; then use Task importance as a primary criterion for discretionary capacity.
- Today-only user Task locks are supported and expire at day end.
- Daily / Weekly / Long-Term Planner horizons share one canonical Task model.
- Weekly planning includes forward risk, bottlenecks, Course backlog, and Goal pacing.
- Numeric effort models may learn automatically; behavioral/planning rules require user approval.
- Historical COMPLETE / CANCELLED / EXPIRED / reopened-stage records are preserved.
- Two consecutive days without normal interaction triggers a reconciliation reminder.
- Long-term Goals require onboarding; generated Tasks enter Planner like ordinary Tasks.
- A0 separates internal semantic contracts from provider-specific adapter contracts.

Authority:
- detailed user intent: `A0_USER_INTENT.md`
- gate/closure: `ALIGNMENT_PLAN.md`
- accepted decisions: `DECISIONS.md`

---

## 3. Current Work

The completed work is the requested full-document consistency audit. The immediate next work is **detailed project planning**, per the user's latest instruction. M1 remains the next incomplete semantic milestone; no course/activity profiles were collected or approved in this audit.

No implementation task is active.

M1 objective:
- collect the user's current courses and recurring non-course commitments;
- model one representative course deeply;
- establish a reusable Course/Activity profile and Course Progress Axis;
- apply the structure to the remaining courses/activities.

Important:
- do not silently import old-chat course facts as current-semester truth;
- confirm current-semester information with the user;
- Task remains the eventual planning unit even though M1 models Course/Activity context.

---

## 4. Immediate Next Actions

First prepare a detailed project plan using the reconciled documents and CONSISTENCY_AUDIT.md. Do not implement or restart broad A0 questioning. Distinguish accepted requirements, missing user facts, open semantic edges, proposed technical choices, and runtime acceptance gates.

After that planning work, the semantic prerequisite sequence remains:

1. Collect and confirm all current courses.
2. Collect recurring exercise/training and recurring life/other commitments.
3. Select one representative course for detailed modeling.
4. Define its Course Progress Axis and planning-relevant course semantics.
5. Validate the profile structure with the user.
6. Apply the structure to the remaining courses/activities.
7. Complete M1 acceptance criteria.
8. Move to M1B for per-course/task-type decomposition presets.
9. Then move to M2 Task and I/O contracts.
10. Only after those semantic contracts stabilize, begin persistence/infrastructure work.

---

## 5. Pending User Information

Needed when M1 begins (not collected in this audit):
- current semester course list
- recurring exercise/training
- recurring life/administrative/other commitments
- one representative course to model first
- per-course task patterns and progress-unit meaning as M1 proceeds

Needed later for M1B:
- representative task types for each course/activity
- decomposition templates
- difficulty defaults
- minimum useful session
- fragmentability
- hard vs soft dependency exceptions

Needed later for M2:
- concrete task creation/update/completion examples
- exact machine-facing Task schema decisions
- input/output examples and remaining edge cases

Needed later:
- timetable and real Calendar integration details
- email-source rules
- learning-platform access/details
- model-cost policy

Do not request later-stage information prematurely unless it becomes necessary to resolve a current dependency.

---

## 6. Blockers

No technical blocker is known.

Current dependency:
- M1 requires confirmed current-semester user/course/activity information.

---

## 7. Deferred Work

Do not start these yet:
- exact PostgreSQL tables/migrations
- n8n deployment/workflows
- Calendar API adapter mapping
- Email connector
- Learning-platform scraper
- exact Planner scoring formula
- exact scheduling algorithm
- AI Router implementation
- cloud/VPS selection
- historical-learning implementation

Reason:
- these depend on M1/M1B/M2 contracts and would create avoidable rework if started now.

---

## 8. Verification Status

Verified:
- planning files and format directories exist in the GitHub repository;
- A0 requirements are consolidated into repository planning documents;
- A0 cross-file consistency audit completed for the final rule changes;
- A0 is accepted as complete;
- M1 is the next incomplete semantic milestone, after the requested detailed planning work.
- This session inspected all 21 existing Markdown documents at base commit `c1ce632e26c2a7b497e1a87074dc39bacd7af04f`, reconciled their policies, and added CONSISTENCY_AUDIT.md.
- Local document checks cover links, decision IDs, stale rule phrases, and dependent requirement propagation. This is document-level verification only.

Not yet verified:
- any runtime behavior
- any connector
- any database
- any scheduling behavior
- any automatic Daily Brief generation
- any learning algorithm

---

## 9. Progress Update Protocol

After each meaningful session, update at least:
- last updated date if material progress occurred
- current milestone/phase
- completed items
- current work
- immediate next actions
- pending user information
- blockers
- verification status

When a milestone is completed:
1. mark it complete here;
2. move Current milestone to the next milestone;
3. check `DEVELOPMENT_PLAN.md` acceptance criteria;
4. do not advance based on intent alone.

---

## 10. Consistency Audit Handoff — 2026-10-06

Read CONSISTENCY_AUDIT.md for the exact findings, affected files, and open questions. Repairs cover A0/register internal conflicts, old architectural shortcuts, course/template semantics, Task lifecycle/trust separation, learning permissions, emergency review, workload accounting, roadmap prerequisites, tests, and format placeholders.

Remaining planning dependencies include Goal/recurring/conditional activation authority, canonical expiration authority, parent/stage effort reconciliation, forecast estimate choice, local horizon conventions, window-bottleneck aggregation, reserve/small-gap accounting, and full-queue review UX. None is silently treated as user-approved.

No database, workflow, connector, Planner, model path, profile schema, or machine I/O schema was implemented. A0 stays complete; M1/M1B/M2 stay incomplete. The user need not review long AI-oriented documents; provide a concise user summary and use the repository for future detailed planning.
