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
- initial 12-question A0 round is complete and captured in `plan/A0_USER_INTENT.md`;
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

Remaining alignment goals:
- refine the exact morning interaction sequence;
- refine the exact evening review sequence;
- define how pending uncertainty questions are prioritized/presented;
- decide whether any urgent uncertainty should notify outside the two normal interactions;
- refine partial-progress and remaining-effort semantics;
- refine task decomposition representation and the exact difficulty scales;
- continue cross-module information-granularity alignment;
- preserve semantic-contract vs adapter-contract separation for later integrations

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
- follow-up answers on unresolved interaction details listed in `A0_USER_INTENT.md`
- confirmation/refinement of task granularity and partial-progress semantics
- further module-granularity examples, beginning with Course
- decision on whether urgent uncertainty can interrupt outside the normal morning/evening cadence

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
