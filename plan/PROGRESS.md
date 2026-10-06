# WhatToDo — Live Project Progress

> This file is the canonical live project-status handoff.
> Update it after every meaningful planning or implementation session.

## 1. Snapshot

Last updated: 2026-10-06

Overall status: **PLANNING / DOMAIN MODELING**

Current milestone: **M0 complete → M1 next**

Current phase: **Phase 1 — Define What the System Understands**

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
- `plan/USER_MODEL_PLAN.md` defines the active M1 collection/modeling process.
- Specialized plans now exist for data model, I/O contracts, integrations, planner, AI execution, operations, security/privacy, and testing.

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

No implementation task is currently active.

The next active planning work is **M1: User and Course Model**.

The repository does not yet contain an authoritative current-semester course/activity profile. Do not infer one from old chats and silently write it as project truth. Obtain/confirm it from the user during M1.

---

## 4. Immediate Next Actions

Execute in this order:

1. Ask/collect the user's complete current course list and recurring non-course commitments.
2. Choose one representative course.
3. Model that course in detail:
   - task types
   - workload
   - cognitive difficulty
   - fragmentation
   - typical duration
   - deadline patterns
   - exam/review behavior
4. Derive a reusable course-profile format.
5. Apply it to remaining courses/activities.
6. Collect several real tasks.
7. Design Task schema and lifecycle.
8. Finalize input contract.
9. Finalize output contract.
10. Only then begin persistent-state implementation.

---

## 5. Pending User Information

Needed for M1:
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
- M1 requires current user/domain information before the semantic model can be finalized.

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
