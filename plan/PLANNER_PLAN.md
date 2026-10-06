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
- user-reported remaining effort plus valid model remaining-effort prediction and selected effective planning budget/source
- accepted typed Task relationships: generation origins, completion order, start prerequisites, soft sequencing
- task-level 1–5 thinking depth / repetitive volume / new-learning load
- minimum useful continuous session
- fragmentability
- course/activity profiles
- goal/milestone state
- fixed events
- total usable free time and available-window characteristics
- user constraints, Beijing planning timezone and date-only 23:59 deadline default
- historical calibration
- optional risk signals

---

## 4. Hard vs Soft Constraints

### Hard constraints
Examples:
- class/training cannot overlap work block
- required delivery deadlines are hard obligation constraints; a missed deadline creates visible infeasibility/overdue state, not automatic Task cancellation or a ban on all recovery work
- explicitly hard prerequisite/dependency or completion-order relation (distinguish finish-before-start from finish-before-finish)
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
- when SAFE and aggregate whole-day discretionary capacity after required work/reserve is at most 40 minutes, leave it free rather than filling it for utilization; individual short windows may still be used when aggregate capacity is greater;
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

These margin labels assume REQUIRED work can be placed before its deadlines under the hard constraints. Section 21 checks that prerequisite; a proven placement deficit is EMERGENCY even when unrelated free hours make the aggregate margin positive.

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

REQUIRED tasks should not be treated as casually deferrable.

The A0 semantic thresholds are now fixed by Section 12. Implementation may still tune partial-day handling and numerical rounding without changing those semantics.

---

## 14. Historical Procrastination Signal

Pattern discovery belongs to `LEARNING_PLAN.md`, not to the Planner itself.

Planner may consume automatic numeric predictions/descriptive risk signals and user-accepted behavioral planning rules. Unconfirmed behavioral rules must not affect allocation.

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

- course/task-specific allocation details and explicit daily capacity constraints
- any explicit exceptions to the already accepted one-hour reserve / ~40-minute SAFE small-gap defaults
- study-time preferences
- minimum focus blocks
- explicit exam phase/coverage/review cadence configuration, not generic TaskType lead time
- large-assignment strategy
- tolerance for fragmented scheduling
- rendering refinements to the accepted recommendation-oriented default; exact clock scheduling is not required
- course-specific hard vs soft dependency exceptions
- weekly/long-term planning preferences where they materially differ from defaults

---

## 17. Dependencies

Requires:
- DATA_MODEL_PLAN
- Calendar integration
- Goal model
- Output contract
- automatic numeric predictions and user-accepted behavioral rules from LEARNING_PLAN where available

Feeds:
- Daily plan
- AI jobs for fuzzy/strategic decisions
- Historical-learning metrics
- reconciliation replanning

---

## 18. Required Emergency Interaction

Use the overall worst-horizon mode. Overall EMERGENCY requires two rounds (A0 Section 38, Daily Brief template):
1. Display a visibly provisional normal-rule baseline, affected horizons, at-risk obligations, capacity deficit, and proposed lower-importance/non-required sacrifices. Ask what the user will remove/defer and how much additional time is realistic.
2. Recompute with the user's choices, then publish the final emergency-day recommendation and the remaining risk/deficit, if any.

Never silently cancel REQUIRED work or treat removal from a daily list as cancellation. Since R measures REQUIRED work, removing OPTIONAL items alone cannot turn C - R from negative to nonnegative. Do not label an infeasible baseline/final result safe or claim a guaranteed feasible schedule when hard constraints conflict. Today-only locks remain highest-priority overrides with visible conflicts; they are not evidence of execution.

## 19. Forecast and Effort Accounting Requirements

- C is usable capacity after configured fixed occupancy, no-work boundaries, and relevant buffers; do not subtract the safety reserve into C and then subtract it again via S.
- Forecast R counts the same obligation once across parent/stages and across plan sections. Selected daily effort is part of remaining work. Horizon forecasts overlap; their risk labels are reported separately, not added together.
- A positive aggregate C - R is not by itself proof of feasibility. Deadline-prefix bottlenecks, release times, hard prerequisites, and minimum useful windows can make work impossible even with sufficient total hours. The accepted feasibility rules must be implemented with suitable checks, not weakened to calendar-date labels.
- Required work due beyond 7 days may need effort today to preserve long-run feasibility. Daily/weekly/long-term layers coordinate; R must not blindly omit necessary early allocations or count every future Task's full effort as due today.
- Overdue REQUIRED work remains visible until the user confirms its disposition. EXPIRING work is distinct; detect time/condition crossings without inventing canonical transition permission.
- User-reported remaining effort stays canonical; under D-074 use a valid model remaining-effort prediction as B for allocation/forecasting, with user-estimate fallback if unavailable. This is not max(user, model). Parent/stage accounting uses B once (DATA_MODEL_PLAN §12); window-infeasibility handling is in §21.
- Preserve reserve before discretionary work. D-076 fixes the small-gap scope: aggregate whole-day discretionary remainder at most 40 minutes stays free in SAFE; it is not a per-window restriction. Do not subtract the reserve twice.
- Use Asia/Shanghai (Beijing time), not server locale, for “today”, override expiry, and missed-interaction days. Date-only deadlines default to local 23:59; preserve explicit times. Natural-day vs rolling-hour 1/3/7-day horizon mode remains O05; do not claim the user selected it.

## 20. Failures and Missing Information

Unknown/stale capacity or missing task facts cannot produce falsely precise SAFE claims. Retain the last trusted facts, expose data quality/blocked review, and recompute after confirmation. Three feasibility states remain accepted; missing knowledge is separate metadata, not a new invented risk state. Minimal missed-interaction handling is required for the MVP; Phase 7 adds broader recovery/weekly analysis.

---

## 21. O06 Resolved — Feasibility Checks and Horizon Accounting

Resolution type: internal engineering specification to preserve accepted deadline safety, three risk states, and long-horizon advancement. It does not introduce an additional user choice or an implemented scheduling algorithm.

- Build a versioned availability/required-work snapshot using D-074 model-first remaining-effort prediction with explicit user-estimate fallback. Normalize usable windows, release dates, deadlines, hard prerequisites, task continuity/minimum session constraints, and confirmed today-only locks. Count parent obligations once under DATA_MODEL_PLAN Section 12.
- Evaluate actual required-work placement feasibility within those windows, not just aggregate free hours. Every deadline prefix is a constraint. Include dependencies' required work; a task unavailable until late cannot consume earlier free time. Soft academic sequences may be bypassed under the accepted policy with an exception note; hard dependencies remain binding.
- Use one coordinated longer-horizon workload projection for required work beyond day 7. Determine necessary early allocations from release/deadline/window restrictions and remaining later capacity, then feed those derived allocations into shorter-horizon workload accounting. Do not count a distant Task's entire budget as due today, and do not add its parent/stage representations twice. Preserve provenance for the projected early allocation and do not mutate the Task's accepted deadline.
- Compute each horizon's C, counted REQUIRED workload R, and reserve target S separately. Horizon snapshots overlap and are not summed. C excludes configured occupancy/no-work/buffers, but not S. Report the accepted C-R margin alongside any placement bottleneck.
- A proven required-work placement deficit before a relevant deadline is EMERGENCY even if total hours elsewhere in the horizon look adequate: those hours are not usable for that obligation. If required placement is feasible, apply the accepted reserve inequalities: SAFE when C-R >= S, DANGER when 0 <= C-R < S. Overall mode remains the worst 1/3/7-day result. Longer-horizon bottlenecks also appear in the weekly/long-term forward preview, with their necessary early workload propagated into the daily projection.
- Solve hard-constraint placement independently of importance-based discretionary selection. Choose optional/additional work only after required feasibility/reserve are protected. A heuristic failing to find a placement is not proof that none exists; run an exact constraint check or report incomplete verification/data quality rather than invent an EMERGENCY proof or SAFE guarantee.
- Keep the implementation interchangeable (e.g. a deterministic constraint solver with a small exact fixture oracle). No provider/language/library is selected here. Respect task-specific indivisibility and minimum sessions; an overly relaxed hour-sum calculation cannot certify executable feasibility.

Acceptance cases: abundant total hours but an early deadline has too few usable hours; several short windows cannot fit one continuous stage; hard dependency pushes work beyond a deadline; far-future work must start today because later capacity is full; parent/stage work is counted once; known feasible fixtures remain feasible; solver timeout is not confused with proven infeasibility.

---

## 22. Follow-Up Planner Integration

TASK_RELATIONSHIP_PLAN defines separate generation and ordering graphs. Planner consumes concrete accepted instances, not raw discoveries. Explicit Task 2-before-Task 1 completion order is hard and does not automatically imply Task 1 cannot start first; enforce stronger start prerequisites only when specified. Include any necessary prerequisite work for required feasibility, without pretending it was completed. Report confirmed historical violations rather than falsifying them.

Effective planning budget B is the valid model prediction of unfinished effort, even when lower than the user's reported U; the latest user answer selected model-first planning rather than an automatic conservative maximum. Use model validity/uncertainty diagnostics and retained history, and show material estimate differences. B does not require a live LLM/provider; no prediction means fallback to U with clear provenance. Split B across stages once, never U+B or parent+stage sum.

For SAFE discretionary capacity, protect required workload and reserve first, then sum the day's remaining usable discretionary windows. If total is <=40 minutes, leave it free. If total is greater, fragmentable tasks may use short individual windows when their own minimum session constraints permit. The 40-minute rule changes discretionary allocation, not the C-R risk inequalities.

At a confirmed expiration condition, a pending notify-before-record process can expose derived no-longer-useful status for recommendations, but cannot claim canonical EXPIRED before the notice step. Preserve discrepancy/process visibility; never infer task completion. Exact 1/3/7-day boundary selection still awaits one user choice; core constraints/model estimates remain preparable meanwhile.
