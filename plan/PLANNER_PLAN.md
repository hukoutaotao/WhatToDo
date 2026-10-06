# WhatToDo — Planner Design Plan

## 1. Planner Mission

Given trusted current state, goals, and available time, produce a realistic actionable plan.

The Planner must not scrape sources or own external authentication.

---

## 2. Deterministic-First Principle

Use code for facts and constraints that can be computed reliably:
- deadline distance
- remaining effort
- free/busy windows
- overlap/conflict
- hard dependencies
- minimum session length
- maximum capacity
- overdue status
- recurring goal quotas

Use AI only for genuinely fuzzy judgment.

---

## 3. Planner Inputs

Expected conceptual inputs:
- active tasks
- deadlines
- progress/remaining effort
- course/activity profiles
- goal/milestone state
- fixed events
- available windows
- user constraints
- historical calibration
- optional risk signals

---

## 4. Hard vs Soft Constraints

### Hard constraints
Examples:
- class/training cannot overlap work block
- task cannot be scheduled after a hard deadline
- dependency must be completed first
- minimum session length where truly required

### Soft constraints
Examples:
- prefer high-cognitive work earlier
- avoid overly dense days
- preserve buffer
- prefer grouping related work
- use fragmentable tasks in short windows

Soft constraints should influence scoring, not masquerade as impossibility.

---

## 5. Planning Horizons

### Daily
Concrete executable plan.

### Weekly
Capacity/risk balancing and distribution.

### Multi-week
Exam preparation, large projects, milestone pacing.

The same data model should support all horizons; do not build three unrelated planners.

---

## 6. Priority vs Scheduling

Keep distinct:

Priority:
- how important/urgent it is to allocate effort.

Scheduling:
- where specific work sessions fit.

A task may have high priority but still need a later focus window because the next available slot is too short.

---

## 7. Task Splitting

Planner should eventually support:
- total remaining effort
- multiple work sessions
- minimum session length
- maximum sensible session length
- divisible vs non-divisible task
- concrete session objective

Avoid scheduling vague "work on assignment" blocks when a more concrete sub-goal can be generated.

---

## 8. Goal Integration

Long-term goals must inject workload before urgency becomes extreme.

Example:
English exam:
- vocabulary cadence
- reading cadence
- mock-exam phase
- final review phase

Goal workload should compete for real capacity alongside coursework.

---

## 9. Daily Plan Output

Structured result should support:
- must do
- should do
- optional
- fixed events
- scheduled sessions
- risks
- reasons/explanations
- weekly/goal progress

Human rendering is governed by IO_CONTRACT_PLAN and formats/output.

---

## 10. Explainability

For material choices, planner should be able to give compact reasons such as:
- deadline approaching
- large remaining effort
- only suitable focus window today
- prerequisite for another task
- long-term goal falling behind

Do not expose hidden chain-of-thought. Store concise decision factors instead.

---

## 11. Failure Modes to Guard Against

- Overfilling the day
- Scheduling impossible overlaps
- Pushing large tasks to deadline
- Repeatedly postponing low-urgency long-term goals
- Ignoring transition/buffer time
- Treating all courses/tasks as equal
- Making a plan dependent on one model call
- Silently planning from stale state

---

## 12. User Inputs Needed Before Implementation

- desired daily load
- buffer preference
- study-time preferences
- minimum focus blocks
- exam-review lead time
- large-assignment strategy
- tolerance for fragmented scheduling
- whether exact time blocks are desired in final output

---

## 13. Dependencies

Requires:
- DATA_MODEL_PLAN
- Calendar integration
- Goal model
- Output contract

Feeds:
- Daily plan
- AI jobs for fuzzy/strategic decisions
- Historical-learning metrics
- reconciliation replanning
