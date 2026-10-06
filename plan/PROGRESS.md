# WhatToDo — Live Project Progress

> This file is the canonical live project-status handoff.
> Update it after every meaningful planning or implementation session.

## 1. Snapshot

Last updated: 2026-10-06

Overall status: **PRE-DEVELOPMENT ALIGNMENT**

Current milestone: **M0 complete → A0 IN PROGRESS → M1 next**

Current phase: **Phase 0 — Interaction and Information-Model Alignment**

Implementation status:
- Production system: not started
- Database implementation: not started
- n8n workflows: not started
- Calendar integration: not started
- Email integration: not started
- Learning-platform integration: not started
- Planner implementation: not started
- AI Router implementation: not started

This is intentional. The approved roadmap requires semantic/data contracts before infrastructure.

---

## 2. Completed

### Repository/planning foundation
- GitHub repository exists: `hukoutaotao/WhatToDo`.
- `plan/PROJECT_PLAN.md` defines architecture.
- `plan/DEVELOPMENT_PLAN.md` defines ordered development.
- `formats/input/` exists.
- `formats/output/` exists.
- The plan control-center documentation has been expanded.
- `plan/README.md` now defines file authority, dependency relationships, and mandatory change-propagation rules.
- `plan/DECISIONS.md` records accepted decisions.
- `plan/USER_MODEL_PLAN.md` defines the M1 collection/modeling process that becomes active after A0.
- Specialized plans now exist for alignment, user/course modeling, data model, I/O contracts, integrations, planner, AI execution, operations, security/privacy, and testing.
- `plan/ALIGNMENT_PLAN.md` defines the required pre-development interaction/information alignment gate A0.
- `plan/A0_USER_INTENT.md` stores the canonical interpretation of the user's first A0 answers and feeds downstream planning documents.
- `plan/LEARNING_PLAN.md` defines historical estimation calibration, behavior-pattern discovery, weekly analysis, and user-confirmed learned rules.

### Accepted major decisions
- Project goal is a long-lived personal task/schedule operating system, not a simple to-do list.
- Top-level life domains start as study, exercise, life administration, and other.
- n8n is the sole workflow/orchestration platform.
- Dify is out of scope.
- PostgreSQL is planned for canonical dynamic state.
- Stable declarative knowledge should be explicit/version-controlled rather than entrusted to chat memory.
- Calendar is a time-occupancy system, not the task source of truth.
- Google Calendar is preferred as automation backend; Apple Calendar may remain the user's normal client.
- AI is a replaceable execution layer.
- ChatGPT Work/Codex premium use is human-triggered rather than pretending Plus is an API subscription.
- Deterministic logic should be preferred over model calls where possible.
- Recovery after inactivity is a first-class feature.

---

## 3. Current Work

The active work is **A0: Interaction and Information-Model Alignment**.

No implementation task is active.

Current alignment progress:
- four A0 question rounds are complete and consolidated in `plan/A0_USER_INTENT.md`;
- normal cadence: morning interaction + evening interaction, roughly 5–10 minutes each;
- missed-day behavior: automated collection continues, then next interaction performs reconciliation;
- uncertainty policy: uncertain facts wait for user confirmation and are batched into the next interaction;
- task granularity is course/task-type dependent and requires a dedicated modeling stage;
- task difficulty is conceptually split into thinking depth, repetitive volume, and new-learning load;
- time model needs total effort, minimum useful continuous session, fragmentability, actual effort, and historical calibration;
- planner should estimate usable free time and recommend workload/block type, not assign exact clock times by default;
- every new long-term goal needs dedicated onboarding before automatic task generation;
- external completion evidence is advisory until user confirmation;
- normal explanations should stay concise and expand mainly for exceptions/risks.
- morning flow order is accepted: reconcile → confirmations → guided special-circumstance question → capacity → plan;
- evening review should ask all routine questions in one batch, then follow up only if necessary;
- incomplete tasks remain INCOMPLETE and store cumulative actual effort plus latest remaining-effort estimate;
- parent tasks own deadlines; task types normally use fixed decomposition templates;
- psychological resistance/procrastination should be learned primarily from history, not manually pre-scored;
- normal plans preserve roughly 40–60 minutes of buffer, with dynamic exceptions for intensive periods;
- all new task-like content requires user review before canonical task creation;
- urgent reminders may occur outside normal interactions when required effort approaches/exceeds remaining capacity;
- planner should compare 1/3/7-day available capacity against due/needed work;
- time workload and long-horizon feasibility matter more than number of tasks or daily completion percentage.
- Task is the fundamental operational unit; Course/domain layers are contextual/classification layers;
- course-level importance is not a primary planner input; importance and requiredness live on Tasks;
- deadline does not imply requiredness;
- difficulty dimensions use a 1–5 scale at task level with TaskType defaults;
- parent Task + stage/subtask daily presentation is accepted;
- Course Progress Axis is required to attach preview/lecture/note/homework/review and exam coverage;
- Exam is an independent event/object; preparation is generated as Tasks/Goals;
- dormant review/catch-up templates may activate under predefined conditions;
- risk vocabulary is SAFE / DANGER / EMERGENCY;
- weekly historical evaluation is allowed, but material learned rules require user confirmation before affecting Planner;
- historical pattern discovery is separated into LEARNING_PLAN rather than hidden inside Planner.
- Task importance uses 1–5; requiredness uses REQUIRED / OPTIONAL / EXPIRING with explicit expiration;
- no generic lead-time field: SAFE unused capacity advances future REQUIRED work;
- TaskType defaults inherit automatically to concrete Tasks unless overridden;
- Course Progress Axis units are course-defined and track teaching progress plus task-family progress;
- default academic dependency flow may be templated (preview → class → notes → homework);
- three consecutive missing post-class note tasks and exam-preparation phase are initial review activation triggers;
- 1/3/7-day risks are all reported and overall mode uses the worst horizon;
- normal review sessions should clear the whole pending confirmation queue;
- confirmation prompts may provide recommended answers;
- Daily Brief baseline template is stored at `formats/output/DAILY_BRIEF_TEMPLATE.md`, with deadlines shown by default within 3 days;
- numeric effort-prediction models may learn automatically, while behavioral/planning rules require confirmation;
- two consecutive days without normal interaction triggers a reminder;
- long-term goal onboarding fields are accepted and generated Tasks enter Planner as ordinary Tasks;
- automatic analysis/recommendation is allowed, while canonical truth and key policy remain user-reviewed.

Remaining alignment goals:
- decide desired conservatism for SAFE vs DANGER thresholds without fixing implementation math prematurely;
- confirm whether REQUIRED / OPTIONAL / EXPIRING are sufficient for v1;
- decide whether stage/subtask effort should be shown separately from parent remaining effort;
- finalize user-facing section labels/wording for the Daily Brief if needed;
- confirm whether any external completion-evidence class should receive a shortcut in v1;
- perform one final semantic consistency review before closing A0

The course model will be used as the first detailed worked example, but current-semester course data should not yet be collected as if M1 had already begun.

---

## 4. Immediate Next Actions

Execute in this order:

1. Continue A0 follow-up using unresolved items in `A0_USER_INTENT.md`.
2. Refine morning/evening interaction and uncertainty-batch behavior.
3. Discuss module information granularity, beginning with Course.
4. Confirm how course information affects Task, Planner, Goal, Input, Output, and historical estimation.
5. Refine task-decomposition and partial-progress semantics.
6. Identify information categories needed now versus details intentionally deferred.
7. Confirm the semantic-contract vs adapter-contract rule.
8. Complete Alignment Gate A0.
9. Update `PROGRESS.md` to enter M1.
10. Only then collect the full current course/activity list.

---

## 5. Pending User Information

Needed now for A0:
- short final answers on the narrow remaining items in `A0_USER_INTENT.md`
- preferred conservatism of risk thresholds
- whether the three requiredness classes are sufficient for v1
- stage/subtask effort display preference
- any desired external-completion shortcut policy
- final consistency confirmation

Needed after A0 for M1:
- Current semester course list
- Recurring sports/training schedule or categories
- Recurring life/other commitments
- Course-specific workload/difficulty/task patterns

Needed later for M2:
- Real task examples
- Natural-language examples of task creation/correction/completion
- Daily output preferences

Needed later:
- Timetable and Calendar rules
- Email-source rules
- Learning-platform details
- Planning preferences
- Model-cost policy

Do not request later-stage information prematurely unless it becomes necessary to resolve a current design dependency.

---

## 6. Blockers

No technical blocker is currently known.

Primary dependency:
- A0 requires enough user-AI discussion to confirm the interaction model and semantic granularity philosophy.
- M1 starts only after A0 is accepted.

---

## 7. Deferred Work

Do not start these yet:
- Exact PostgreSQL tables/migrations
- n8n deployment/workflows
- Calendar API integration
- Email connector
- Learning-platform scraper
- Priority formula
- Scheduling algorithm
- AI Router implementation
- Cloud/VPS selection
- Historical-learning implementation

Reason:
- These depend on Phase 1 contracts and would create avoidable rework if started now.

---

## 8. Verification Status

Verified:
- Planning files and format directories exist in the GitHub repository.
- n8n-only decision has been incorporated into planning.

Not yet verified:
- Any runtime behavior
- Any connector
- Any database
- Any scheduling behavior
- Any automatic daily plan generation

---

## 9. Progress Update Protocol

After each meaningful session, update at least:
- Last updated date if material progress occurred
- Current milestone/phase
- Completed items
- Current work
- Immediate next actions
- Pending user information
- Blockers
- Verification status

When a milestone is completed:
1. Mark it complete here.
2. Move Current milestone to the next milestone.
3. Check whether `DEVELOPMENT_PLAN.md` acceptance criteria are actually satisfied.
4. Do not advance based on intent alone.
