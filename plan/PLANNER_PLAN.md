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
- task-level 1–5 thinking depth / repetitive volume / new-learning load
- minimum useful continuous session
- fragmentability
- course/activity profiles
- goal/milestone state
- fixed events
- total usable free time and available-window characteristics
- user constraints
- historical calibration
- optional risk signals

---

## 4. Hard vs Soft Constraints

### Hard constraints
Examples:
- class/training cannot overlap work block
- task cannot be scheduled after a hard deadline
- explicitly hard prerequisite/dependency
- minimum session length where truly required
- today-only user lock, unless physically incompatible with another hard obligation

### Soft constraints
Examples:
- default academic sequence such as preview → class → notes → homework
- prefer high-cognitive work earlier
- avoid overly dense days
- preserve buffer
- prefer grouping related work
- use fragmentable tasks in short windows

If capacity is tight, a soft academic prerequisite may be bypassed to protect REQUIRED work. Surface the exception rather than pretending the prerequisite was completed.

Soft constraints should influence scoring, not masquerade as impossibility.

---

## 5. Daily Output Philosophy

The normal planner output is recommendation-oriented, not a rigid timetable.

It should:
- estimate approximately how much usable free time exists today;
- allocate a realistic amount of work to that capacity;
- avoid chronic overfilling and unnecessary underfilling;
- preserve a SAFE reserve of about 1 hour per day after REQUIRED work when feasible;
- when SAFE and only a ~40-minute-or-smaller free gap remains, normally leave it unscheduled rather than filling it just for utilization;
- allow DANGER/EMERGENCY logic to consume the reserve when needed to protect REQUIRED work;
- identify which tasks require large uninterrupted blocks;
- identify which tasks are suitable for fragmented time;
- protect deadlines and long-term workload.

It should not, by default, assign exact clock times to every task.

Internal availability reasoning may use real time windows even when the user-facing output does not expose a minute-by-minute schedule.

Primary load metric:
- estimated work time and fit to available windows, not number of checklist items.

Primary optimization objective:
- long-horizon feasibility and deadline safety, not maximizing daily completion percentage.

Discretionary-capacity rule:
- no separate generic "start N days early" field is required;
- first ensure REQUIRED work is feasible;
- preserve the SAFE reserve when possible;
- then use Task importance as a primary criterion for additional work allocation;
- future REQUIRED work may be advanced, but it does not automatically outrank higher-importance eligible OPTIONAL/EXPIRING work once REQUIRED feasibility is protected.

---

## 6. Planning Horizons

### Daily Planner
Produces today's actionable recommendation and computes 1-day / 3-day / 7-day feasibility.

### Weekly Planner
Looks roughly 2–4 weeks ahead for:
- workload distribution
- tight future days
- large work that should begin before urgency
- Course Progress Axis backlog
- long-term Goal pacing deficits

### Long-Term Planner
Looks across the whole Goal / Exam / project horizon for:
- milestones
- phases
- recurring workload generation
- long-run feasibility

All three layers share the same canonical Task model; do not build separate task worlds.

---



## 7. Priority vs Scheduling

Keep distinct:

Priority:
- how important/urgent it is to allocate effort.

Scheduling:
- where specific work sessions fit.

A task may have high priority but still need a later focus window because the next available slot is too short.

---

## 8. Task Splitting

Parent Tasks own overall deadlines. Stages/subtasks support execution detail.

Normal task types should inherit stable decomposition templates.

Planner should eventually support:
- total remaining effort
- multiple work sessions
- minimum session length
- maximum sensible session length
- divisible vs non-divisible task
- task-type decomposition template
- concrete session objective

Avoid scheduling vague "work on assignment" blocks when a more concrete sub-goal can be generated.

Child stages/subtasks may be reopened when later work reveals rework is necessary.

Daily display should normally show:
- parent remaining effort;
- today's selected stage/subtask;
- today's stage/subtask estimate.

---

## 9. Goal Integration

Long-term goals must inject workload before urgency becomes extreme.

Example:
English exam:
- vocabulary cadence
- reading cadence
- mock-exam phase
- final review phase

Goal workload should compete for real capacity alongside coursework.

Once generated and accepted, Goal-derived Tasks enter Planner exactly like ordinary Tasks; source does not grant special scheduling privilege.

---

## 10. Daily Plan Output

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

## 11. Explainability

Default user-facing explanations should be minimal.

For abnormal, risky, uncertain, surprising, or major-replanning choices, planner should be able to give compact reasons such as:
- deadline approaching
- large remaining effort
- only suitable focus window today
- prerequisite for another task
- long-term goal falling behind

Do not expose hidden chain-of-thought. Store concise decision factors instead.

---

## 12. Risk States

Use three high-level states:
- SAFE
- DANGER
- EMERGENCY

Determine them from feasibility margin between usable capacity and REQUIRED expected effort.

For a horizon representing D days:
- C = usable capacity
- R = REQUIRED expected effort
- S ≈ D hours of safety reserve (1 hour per represented day)

Then:
- SAFE when C - R >= S
- DANGER when 0 <= C - R < S
- EMERGENCY when C - R < 0

Evaluate 1-day, 3-day, and 7-day horizons separately.

Overall mode uses the worst horizon:
- any EMERGENCY → overall EMERGENCY;
- else any DANGER → overall DANGER;
- else SAFE.

Exact handling of partial days and numerical rounding is deferred to implementation.

## 13. Emergency / Risk Mode

A risk mode is required when remaining required effort approaches or exceeds remaining usable capacity before one or more deadlines.

Core conceptual trigger:
```text
required remaining effort before deadline
vs
usable free time before deadline
```

Emergency behavior may:
- warn immediately outside the normal twice-daily cadence;
- show the feasibility deficit;
- recommend reclaiming or intensifying time;
- increase today's recommended workload;
- reduce normal buffer when justified.

Most deadline-bearing required tasks should not be treated as casually deferrable.

Exact risk thresholds and terminology remain to be aligned.

---

## 14. Historical Procrastination Signal

Pattern discovery belongs to `LEARNING_PLAN.md`, not to the Planner itself.

Planner may consume accepted learned signals.

Do not require a manual psychological-resistance score.

Later historical analysis may infer delay tendency from:
- release-to-first-work delay;
- repeated postponement;
- release-to-completion delay;
- whether sufficient capacity existed during the delay.

Avoid falsely labeling capacity-driven delay as procrastination.

---

## 15. Failure Modes to Guard Against

- Overfilling the day
- Scheduling impossible overlaps
- Pushing large tasks to deadline
- Repeatedly postponing low-urgency long-term goals
- Ignoring transition/buffer time
- Treating all courses/tasks as equal
- Making a plan dependent on one model call
- Silently planning from stale state
- Marking uncertain state as fact instead of surfacing confirmation
- Overusing short fragments for tasks that need deep continuity
- Ignoring historical underestimation patterns
- Ignoring older Unit-linked unfinished work after teaching/task-family progress moves ahead
- Treating soft academic sequence dependencies as absolute when REQUIRED feasibility is at risk
- Letting today-only user overrides persist beyond the day

---

## 16. User Inputs Needed Before Implementation

- desired daily load
- buffer preference
- study-time preferences
- minimum focus blocks
- exam-review lead time
- large-assignment strategy
- tolerance for fragmented scheduling
- whether exact time blocks are desired in final output
- course-specific hard vs soft dependency exceptions
- weekly/long-term planning preferences where they materially differ from defaults

---

## 17. Dependencies

Requires:
- DATA_MODEL_PLAN
- Calendar integration
- Goal model
- Output contract
- accepted learned parameters from LEARNING_PLAN where available

Feeds:
- Daily plan
- AI jobs for fuzzy/strategic decisions
- Historical-learning metrics
- reconciliation replanning
