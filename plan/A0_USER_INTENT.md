# WhatToDo — A0 User Intent and Interaction Model

> Status: AUTHORITATIVE USER-INTENT RECORD FOR A0
> Source: Direct user answers during Alignment Gate A0.
> Audience: AI agents and maintainers.
> Purpose: Preserve the intended user experience and semantic requirements in a compact form that future AI agents can use without relying on chat history.
> Rule: Do not reinterpret these requirements as implementation details. If later discussion changes them, update this file and all dependent plans listed in plan/README.md.

---

## 1. Core Product Outcome

The primary reason for WhatToDo to exist is not convenience alone. It is to remove the cognitive burden and risk of personally tracking a large, heterogeneous set of time-sensitive obligations.

The system is successful when:

- important tasks do not silently approach or pass deadlines without the user realizing it;
- the user no longer needs to continually remember "what have I not done?";
- the daily workload is realistic rather than systematically overfilled or underfilled;
- available time is used well without requiring the user to manually optimize the plan;
- the user can focus on executing work instead of deciding what work exists and how to arrange it;
- normal manual maintenance is limited mainly to a short morning interaction and a short evening interaction.

The central planning objective is therefore:

> Maintain a sufficiently trustworthy model of obligations, capacity, and historical effort so that each day the system can recommend a realistic amount of work that protects deadlines and uses available capacity well.

---

## 2. Normal Human-System Interaction Cadence

### Morning interaction

Expected frequency:
- normally once every morning;
- approximately 5–10 minutes.

Purpose:
1. refresh/reconcile system state;
2. surface accumulated uncertain items for user confirmation;
3. incorporate overnight/newly collected information;
4. accept any ad-hoc user constraints or requests for the day;
5. generate the daily plan using a pre-agreed routine.

Normal behavior:
- the user should not need to re-specify planning instructions every morning;
- the default planning workflow must be preset and repeatable;
- if the user adds special requirements, the system should incorporate them and regenerate/adjust the plan.

### Evening interaction

Expected frequency:
- normally once every evening;
- approximately 5–10 minutes.

Purpose:
1. review that day's plan;
2. record which items were completed;
3. record which items were not completed;
4. record actual total effort/time where useful;
5. compare actual time against the estimate;
6. update canonical task state;
7. update historical effort memory/calibration;
8. identify follow-up changes that affect future plans.

The evening interaction is the primary human confirmation point for completion state.

---

## 3. Missed-Interaction Behavior

The system must tolerate days with no human interaction.

If the user skips one or more normal interactions:

- automated collectors may continue gathering previously configured external information;
- the system may store new evidence and candidate changes;
- the system must not fabricate task completion or other uncertain personal state;
- uncertain facts remain pending rather than becoming trusted facts;
- at the next human interaction, the system performs catch-up / state reconciliation;
- accumulated uncertain items are presented together for user resolution;
- after reconciliation, planning resumes from the rebuilt trusted state.

The system should therefore support asynchronous collection without requiring continuous user presence.

---

## 4. Uncertainty Policy

This is a hard behavioral requirement.

If the system is uncertain, it must **not silently make a consequential decision and store it as fact**.

Instead:

```text
uncertain evidence
↓
candidate / pending-confirmation state
↓
batch into next interaction
↓
ask user
↓
confirmed correction/update
↓
trusted state
```

Examples:
- ambiguous deadline;
- uncertain task identity;
- possible completion detected from external data;
- conflicting source information;
- uncertain cancellation.

The design should support batching these questions so the user does not need to be interrupted continuously throughout the day.

External evidence may increase confidence or create a suggestion, but uncertainty does not grant authority.

---

## 5. Task Granularity Is Context-Dependent

There is no single universal task decomposition depth.

Different courses and task classes need different decomposition rules.

Examples of possible levels:
- one whole assignment as a Task;
- assignment split into preparation / implementation / testing / report;
- deep-work task split into meaningful stages;
- trivial fragmentable work kept as one task.

Therefore the system must include a dedicated modeling step for:

- per-course task taxonomy;
- per-task-type decomposition rules;
- default granularity;
- when to split;
- when not to split;
- parent/child or stage relationships;
- minimum useful actionable unit;
- extensibility for new task types/options later.

This is expected to be one of the most information-intensive setup activities.

The schema must be extensible: adding future task types or attributes should not require redesigning the whole system.

---

## 6. Course Modeling Is Intentionally Deep

A Course is not just:
- name;
- class time;
- deadline source.

The user expects a dedicated later step to describe each course in depth.

The final course model should be rich enough to influence:
- task generation;
- task decomposition;
- effort estimation;
- planner prioritization;
- suitability for large vs fragmented time;
- exam/review planning;
- risk detection;
- historical calibration;
- daily-plan presentation where relevant.

Exact course fields are not fully specified in A0 and must be developed interactively during the dedicated course-detail step.

---

## 7. Difficulty Model

Difficulty is explicitly multi-dimensional.

Current minimum dimensions for each Task / task type:

### A. Thinking depth
How much deep reasoning, concentration, debugging, or conceptual thought is required.

### B. Repetitive volume
How much repeated/mechanical volume must be processed even if each unit is not conceptually difficult.

### C. New-learning load
How much unfamiliar material must first be learned/understood before or during execution.

These dimensions should not be collapsed into one generic "difficulty" number unless a derived score is needed internally.

Exact scales and representation are deferred to the Task/Course modeling stage.

---

## 8. Time and Effort Model

The user wants more than one duration number.

At minimum, planning should eventually distinguish:

### Total effort estimate
Expected total time required for the task.

### Minimum useful continuous session
The shortest useful uninterrupted period for making meaningful progress.

### Fragmentability
Whether the work can be spread across many short fragments or requires long/deep sessions.

Conceptual examples:
- simple repetitive task → highly fragmentable;
- deep reasoning task → low fragmentability and longer minimum session;
- some tasks may be best completed in one continuous session.

### Actual total effort
At review time, the user may report how long the task actually took.

### Historical effort memory
Actual completion time should be retained and used to improve future estimates for:
- similar task type;
- same course;
- possibly the user's general estimation bias.

The system should learn from estimated-vs-actual effort rather than repeatedly making the same timing error.

---

## 9. Planner Output Philosophy

The planner should provide strong guidance but **not exact clock-by-clock scheduling by default**.

Desired behavior:
- estimate roughly how much usable free time exists that day;
- select an appropriate amount of work for that capacity;
- avoid both unrealistic overload and avoidable underutilization;
- identify which tasks should use large uninterrupted blocks;
- identify which tasks can use fragmented/short time;
- rank or group work sufficiently for execution;
- protect deadlines and long-term obligations.

Not desired by default:
- "14:00–15:30 Task A, 15:45–16:30 Task B" as the normal user-facing plan.

The system may reason internally about time-window suitability, but the normal output should remain recommendation-oriented rather than a rigid timetable.

---

## 10. Long-Term Goal Onboarding

Every newly created long-term goal should trigger a dedicated setup interaction.

Goal onboarding should establish enough information to determine:
- overall target/outcome;
- total workload or measurable target;
- target date / horizon;
- desired recurring/daily work;
- milestone or phase structure where useful;
- progress measurement;
- task-generation rules.

After onboarding is complete, WhatToDo should automatically generate/suggest the appropriate recurring work and incorporate it into daily planning.

Do not create a long-term goal as a vague single Task and expect the planner to infer the full program without setup.

---

## 11. Completion Confirmation and External Evidence

Primary completion source:
- user's evening review.

Supplementary evidence:
- external data may be used to detect that a task appears to have been completed.

Examples may eventually include:
- assignment submission;
- repository activity;
- other external completion evidence.

Policy:
- if external evidence suggests completion but the user has not confirmed it, create a confirmation question;
- do not silently mark the Task completed solely from ambiguous auxiliary evidence;
- after user confirmation, update trusted state and relevant history.

External evidence is an assistant to confirmation, not an unrestricted replacement for it.

---

## 12. Explanation Style

Default user-facing behavior:
- concise;
- plan-first;
- minimal routine explanation.

Explain more when:
- something is abnormal;
- capacity is insufficient;
- a deadline is at risk;
- the system makes a surprising recommendation;
- state is uncertain/conflicted;
- a major replan occurs;
- the user asks why.

Routine recommendations should not be burdened with unnecessary reasoning text.

---

## 13. Robustness and Extensibility Requirements

The project must tolerate future expansion.

Design requirements:
- new task types should be addable;
- new course-specific attributes should be addable;
- new data sources should be addable behind connectors/adapters;
- new planning dimensions should not require rewriting unrelated modules;
- unknown future options should be represented through extensible schemas/configuration where appropriate;
- planning logic should consume semantic fields, not depend directly on one external provider's payload.

Avoid rigid enums or schemas that make every new user concept a migration crisis unless strict enumeration is truly beneficial.

---

## 14. Derived Daily Lifecycle

The intended normal daily lifecycle is approximately:

```text
Overnight / between interactions
Automated sources collect evidence
        ↓
Morning
Reconcile new evidence
Resolve pending uncertainties with user
Apply special instructions
Estimate today's usable capacity
Generate concise daily recommendations
        ↓
Daytime
User executes work
Collectors may continue gathering evidence
        ↓
Evening
Review planned items
Confirm completed / incomplete
Record actual effort
Resolve detected completion candidates
Update state
Update historical effort memory
Carry unfinished work forward appropriately
```

Exact UX and message format remain to be specified later.

---

## 15. Important Separation of Authority

### Trusted user statement
Can directly establish/correct personal state after validation.

### External confirmed source fact
Can establish facts that source is authoritative for, such as a published assignment deadline when unambiguous.

### System inference / detector
May create a candidate, suggestion, or confirmation request.

### Planner recommendation
Does not itself change reality.

This distinction is essential for preserving trust.

---

## 16. Required Dedicated Modeling Steps Added by A0

The development plan must include explicit steps for:

### Course Detail Modeling
For each course, define planning-relevant semantics in depth.

### Course / Task-Type Decomposition Presets
For each course/task class, define:
- normal decomposition depth;
- stage structure;
- difficulty dimensions;
- fragmentability;
- minimum continuous session;
- estimation behavior;
- extensibility rules.

### Long-Term Goal Onboarding Model
Define the setup interaction/template used whenever a new long-term goal is created.

These are not optional nice-to-have details. They are prerequisites for a planner that represents the user's real workflow.

---

## 17. Second-Round Interaction Protocol

### Morning sequence

The accepted normal order is:

```text
1. Refresh/reconcile newly collected information
2. Present pending items requiring confirmation
3. Ask a guided question for today's special circumstances
   ("Is there anything special today that needs to be arranged?")
4. Incorporate user corrections / special requirements
5. Estimate today's usable free time
6. Generate the daily plan
```

The morning flow should be guided rather than requiring the user to remember what information to volunteer.

### Evening sequence

The system should minimize conversation turns.

Default behavior:
1. Present all information the user should report in one consolidated prompt.
2. Include the day's relevant planned tasks/items in that prompt.
3. Ask for completion status, actual time, and remaining-time estimate for incomplete work.
4. Let the user answer everything in one message.
5. If the answer is sufficient, finish the review without unnecessary follow-up.
6. Only ask additional questions for unresolved/missing information.

---

## 18. Binary Completion State with Effort Tracking

At the primary Task level, completion is conceptually binary:

- COMPLETE
- INCOMPLETE

A task that is partly worked on but not finished remains INCOMPLETE.

For every incomplete task after work has occurred, retain at least:
- cumulative actual time already invested;
- latest estimated remaining time.

Example:

```text
Original estimate: 4 h
Worked today: 2 h
New estimated remaining: 5 h

Canonical meaning:
- status = INCOMPLETE
- actual invested = 2 h (plus any earlier sessions)
- estimated remaining = 5 h
```

Do not derive remaining effort mechanically as original estimate minus time spent.

If the task is complete:
- status = COMPLETE;
- estimated remaining time = 0.

The user's preferred progress report is therefore primarily **remaining effort**, not a required percentage.

If an incomplete task is reported without a remaining-time estimate, the evening interaction should ask for it.

---

## 19. Parent Task and Fixed Task-Type Decomposition Templates

The preferred structural model is:

```text
Parent Task
- owns the overall deadline
- owns the final complete/incomplete status
- represents the external obligation

    ↓

Stages / Subtasks
- support more detailed planning and execution
- may carry their own planning attributes
- do not replace the parent deadline unless explicitly modeled
```

For ordinary recurring work, each **task type** should normally have a stable decomposition template.

Example idea:

```text
Course: DSA
Task type: Programming LAB
Template:
  understand problem
  design
  implement
  debug/test
  report
```

If a genuinely special workflow is needed, the preferred model is to define a new task type with its own template rather than arbitrarily changing the normal template for one instance.

Templates must remain extensible because new task types will be added over time.

---

## 20. Behavioral Procrastination / Psychological Resistance

Do not require the user to pre-score "psychological resistance" for every task.

Instead, treat resistance/procrastination as primarily a **learned historical signal**.

Potential observations:
- time from task release to first meaningful work;
- time from release to completion;
- repeated postponement across daily plans;
- whether delay occurred despite sufficient available capacity;
- whether delay was plausibly caused by workload pressure instead;
- course/task-type patterns.

The system should distinguish, as far as evidence permits:
- "not done because capacity was insufficient"
from
- "not done despite reasonable opportunity."

This signal may later influence planning:
- earlier prompting;
- more buffer;
- earlier placement of repeatedly postponed task types;
- risk warnings.

Exact inference methodology is deferred until sufficient real history exists.

---

## 21. Daily Capacity Buffer

Planning should prioritize deadline safety first, then use available capacity efficiently.

Normal preference:
- preserve approximately **40–60 minutes of unallocated/rest buffer per day** rather than planning every available minute.

This is both:
- genuine rest space;
- contingency capacity when estimates or events change.

The buffer is not a hard invariant.

During explicitly recognized intensive periods such as exam sprint/review phases, planned study load may intentionally increase and the buffer may shrink.

Planner policy must therefore be:
- deadline and critical-goal safety first;
- reasonable daily buffer under normal conditions;
- dynamic higher load when justified by a recognized high-intensity phase.

---

## 22. Emergency / Capacity-Risk Mode

An explicit emergency/risk mode is required.

The system should not assume tasks with real deadlines can simply be postponed.

Tasks should eventually carry a concept such as:
- required / necessary;
- optional / deferrable;
with richer importance semantics developed later.

A major risk signal is **required effort versus remaining usable capacity before deadline**.

Example:

```text
Task estimated remaining effort = 6 h
Usable free time before its deadline = 5 h
→ feasibility deficit
→ urgent warning / emergency behavior
```

Emergency behavior may include:
- alerting the user immediately rather than waiting for the next normal interaction;
- identifying which obligation is at risk;
- showing the effort/capacity deficit;
- recommending that the user reclaim, compress, or reprioritize other time;
- increasing planned workload during critical periods where necessary.

Exact notification channel and thresholds are deferred, but the semantic condition is required.

---

## 23. Mandatory Human Review for New Canonical Tasks

All newly discovered task-like content must be reviewed by the user before it becomes canonical task state.

Even if an external source appears unambiguous, the normal flow is:

```text
external source / detector
↓
candidate new task or candidate change
↓
morning/evening review batch
↓
user reviews and confirms/corrects
↓
canonical Task/state mutation
```

Reason:
Published deadlines and the user's operational interpretation may differ, and task meaning may need correction.

Therefore:
- automated collection is allowed;
- automatic candidate creation is allowed;
- automatic insertion into canonical factual task state is not the default;
- user confirmation is required for new task content and uncertain changes.

The exact review UI is deferred.

---

## 24. Proactive Notification Policy

The system normally communicates during morning/evening interactions, but urgent reminders outside those windows are allowed and desired.

Important trigger class:
- projected remaining required effort is approaching or exceeding remaining usable capacity before a deadline.

Other urgent trigger classes may be added later.

The reminder should be actionable, e.g.:
- deadline at risk;
- estimated effort remaining;
- usable time remaining;
- need to reclaim or intensify time.

Separately, if the system has gone too long without receiving user state updates, it may proactively remind the user to perform a reconciliation/update.

Exact inactivity threshold and notification channels (email, etc.) will be decided later.

---

## 25. Conservative Canonical State Policy

When human interaction is missing, the canonical factual database should remain conservative.

Without user confirmation:
- do not mark tasks complete;
- do not infer personal progress as fact;
- do not silently convert probable states into trusted state.

Even strong external evidence may be stored as:
- raw evidence;
- a candidate;
- "likely completed / pending confirmation."

It should not become trusted completion state unless a future explicit policy exception is separately accepted.

This conservative rule applies especially to personal task-state facts.

---

## 26. Planner Optimization Target: Time and Long-Horizon Feasibility

The primary planning resource is **time**, not number of tasks.

A day containing:
- two large tasks
may be fuller than
- six small tasks.

Therefore daily load should primarily be evaluated by estimated work time and suitability for available blocks, not item count.

For unfinished tasks:
- do not simply "roll them over" mechanically;
- keep them INCOMPLETE with updated remaining effort;
- rerun planning using deadline, remaining effort, importance/necessity, and future capacity.

The system should optimize for **long-term overall feasibility**, not cosmetic daily completion rate.

---

## 27. Multi-Horizon Capacity Forecasting

A core planner/risk concept is to compare future available capacity with work that should be completed within corresponding horizons.

At minimum, support conceptual forecasts for:
- next 1 day;
- next 3 days;
- next 7 days.

For each horizon compute/estimate:

```text
usable free time
vs
expected effort of work that should/must be completed in that horizon
```

Use the comparison to determine:
- whether work should be advanced earlier;
- whether the current plan is comfortable, tight, or infeasible;
- whether to warn the user;
- whether to increase today's recommended workload;
- whether a deadline-risk emergency is emerging.

This is more important than simply labeling a task "must do today" based only on its date.

The planner should deliberately advance future work when later capacity is insufficient.

---

## 28. Long-Term Optimization Principle

The system's objective is not to maximize daily plan completion percentage.

Primary objective:
- achieve long-term overall feasibility and deadline safety across the user's obligations.

This may mean:
- doing non-urgent work today because future days are overloaded;
- increasing effort during exam-sprint phases;
- preserving buffer on normal days;
- recommending early progress on large tasks.

A daily plan is good when it contributes to long-horizon success, not merely when every listed item is checked off.

---

## 29. A0 Items Still Requiring Follow-Up

After the first two rounds, the following still require alignment before A0 can close:

- exact presentation/prioritization of confirmation questions in morning/evening review;
- whether any canonical state changes besides new tasks/completion may be automatically accepted, or whether all meaningful task facts require confirmation;
- exact semantics/scales for the three difficulty dimensions;
- exact information model for importance vs necessity/requiredness;
- detailed Course fields and how each affects downstream modules;
- exact task-type template representation;
- exact handling of subtasks/stages in user-facing daily plans;
- daily plan output layout;
- risk-level terminology and thresholds for comfortable/tight/emergency states;
- how the 40–60 minute buffer interacts with days containing little or no discretionary time;
- how to infer procrastination without falsely blaming capacity shortages;
- exact stale-user-interaction reminder policy;
- per-goal onboarding fields;
- external completion evidence classes to support later.

Resolve these through subsequent A0 conversation before dependent semantic models are frozen.
