# WhatToDo — A0 User Intent and Interaction Model

> Execution: [detailed development plan](DEVELOPMENT_PLAN.md) · [live progress](PROGRESS.md).
> Bounded work: [M2_CONTRACTS](tasks/M2_CONTRACTS.md).

> Status: A0 COMPLETE — AUTHORITATIVE USER-INTENT RECORD
> Source: Direct user answers during Alignment Gate A0.
> Audience: AI agents and maintainers.
> Purpose: Preserve the intended user experience and semantic requirements in a compact form that future AI agents can use without relying on chat history.
> Reading rule: Sections summarize successive A0 rounds; the text is reconciled to the final accepted decisions, not a list of alternative policies. The resolved cross-document invariants and C/O traceability are preserved in DEVELOPMENT_PLAN Sections 2/13. New genuine semantic conflicts are recorded as affected-task blockers in PROGRESS before resolution.
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

Each dimension uses the accepted 1–5 scale (Section 31 / D-037). Exact field representation is deferred to M1B/M2.

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
- in v1, do not mark the Task completed from any external evidence, including an unambiguous submission record, without user confirmation;
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

### External source fact
Can establish what the source published, such as its assignment deadline. It updates evidence/provenance automatically, but does not establish or change an accepted personal Task deadline until user review (Sections 23, 25, 57–58 / D-033, D-064).

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

If a future-relevant incomplete Task has neither an updated remaining-time estimate nor an explicit unchanged-estimate confirmation, ask for it. Section 60 permits one bulk confirmation for untouched Tasks whose previous estimates still hold.

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

## 21. Daily Safety Reserve and Small-Gap Policy

The normal SAFE threshold uses a target of **1 hour of unallocated capacity per day** after REQUIRED work is accounted for.

This hour serves as:
- rest space;
- contingency for estimate error;
- protection against unexpected events.

When the reserve falls below the target but REQUIRED work can still fit, the relevant horizon becomes DANGER.

When even all usable capacity is insufficient for REQUIRED work, the relevant horizon becomes EMERGENCY.

This is a planning safety threshold, not a guarantee that exactly one continuous hour must appear on the calendar.

Small-gap rule:
- when overall state is SAFE and the aggregate discretionary capacity remaining across the whole day, after protecting REQUIRED work and the one-hour reserve, is **40 minutes or less**, do not schedule extra work merely to maximize utilization; this is not a per-window ban;
- in DANGER or EMERGENCY, such time may be used when an eligible task can productively fit.

During high-intensity periods, DANGER/EMERGENCY logic may consume part or all of the normal reserve.

---

## 22. Emergency / Capacity-Risk Mode

An explicit emergency/risk mode is required.

The system should not assume tasks with real deadlines can simply be postponed.

Tasks use REQUIRED / OPTIONAL / EXPIRING and a separate importance score of 1–5 (Section 42). A deadline alone does not imply REQUIRED.

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

The SAFE/DANGER/EMERGENCY thresholds are fixed by Section 37. Notification delivery, repeat suppression, numerical rounding, and endpoint precision remain implementation details. Section 61 fixes natural-day scope and remaining-only capacity; these are not deferred choices.

---

## 23. Review of External Discoveries and Authorized Generation

Externally discovered task-like content must be reviewed before canonical creation. Execution of an explicitly accepted automatic-generation relationship has prior scoped authorization under Section 60; it is not an external-discovery confidence shortcut.

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
- user confirmation is required for externally discovered new task content and uncertain changes; Section 60 defines the bounded exception for execution of a preapproved automatic-generation relationship.

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

The inactivity trigger is two consecutive days without normal interaction (Section 55 / D-055). Notification channel and repeat-delivery details remain deferred.

---

## 25. Conservative Canonical State Policy

When human interaction is missing, the canonical factual database should remain conservative.

Without user confirmation:
- do not create a canonical personal task from collected evidence alone; an accepted generation relationship may instantiate its mapped target when its canonical source trigger occurs (Section 60);
- do not change the accepted task deadline/meaning;
- do not mark tasks complete;
- do not change personal progress/remaining-effort facts;
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

## 29. Task-Centric System Model

The fundamental operational unit of WhatToDo is the **Task**.

Courses, study, exercise, life administration, and other groupings are contextual/classification layers around tasks. They help humans and AI understand provenance, meaning, grouping, and defaults, but the planner ultimately reasons about concrete tasks.

Planning-relevant properties such as:
- importance;
- requiredness;
- three-dimensional difficulty;
- effort;
- remaining effort;
- minimum useful continuous session;
- fragmentability;
- completion state;

belong primarily to individual Task instances or to TaskType templates that provide defaults for Task instances.

Course-level importance is **not** a primary planning variable. If a course matters, that importance should ultimately be expressed through the importance/requiredness of its tasks, goals, exams, or generated review work.

---

## 30. Importance vs Requiredness

Keep two distinct Task dimensions:

### Requiredness
Whether the task must ultimately be completed.

A task with a deadline is not automatically required.

Examples:
- mandatory submitted homework → required;
- optional exercise with an expiry/deadline → optional;
- preparation task that becomes irrelevant after the class occurs → may expire without completion.

### Importance
How strongly the task should influence planning among available/required work.

Importance affects:
- earlier/later placement;
- emergency-mode removal recommendations;
- allocation under scarcity.

Planner invariant:
- required work must be protected sufficiently to remain feasible;
- importance helps choose ordering and sacrifices when not everything can fit.

Task importance uses the accepted integer 1–5 scale (Section 42 / D-043).

---

## 31. Three-Dimensional Difficulty Scale

The accepted three dimensions are:
1. thinking depth;
2. repetitive volume;
3. new-learning load.

Each uses a **1–5 scale**.

These dimensions apply primarily to Task instances.

Normal creation flow:
- a TaskType template provides default 1–5 values;
- when a concrete task is created, its task-level values are initialized from the template;
- task values may later be overridden when the specific instance materially differs.

The user is not expected to manually maintain hidden derived statistics used only for prediction quality.

---

## 32. Estimation Accuracy Is an Internal Learning Problem

The user does not require a visible "estimate reliability" field.

Instead, the system should maintain whatever historical/calibration data is necessary to make future effort estimates increasingly accurate.

The optimization objective is prediction quality, not exposing every statistical intermediate to the user.

Possible internal techniques may later include:
- per-course/task-type rolling averages;
- robust medians/quantiles;
- difficulty-conditioned estimates;
- recency weighting;
- user-specific estimation bias;
- uncertainty intervals.

The exact algorithm is an implementation/design problem to solve later, provided its outputs remain inspectable and correctable.

---

## 33. Daily Display of Parent Tasks and Stages

The normal daily plan should show:

```text
Parent Task
→ specific stage/subtask to advance today
```

Example:
```text
DSA LAB2
Today: finish implementation + start debugging
```

Subtasks/stages may have independent completion states.

The parent task remains INCOMPLETE until the overall obligation is complete.

This allows:
- overall deadline tracking at parent level;
- precise daily execution at stage level;
- resuming from the correct stage the next day.

---

## 34. Course Progress Axis

Add a course-level **progress axis** that provides a semantic location for instructional progress and task attachment.

Purpose:
- represent where the course currently is;
- attach preview/lecture/note/homework/review tasks to instructional progress;
- represent prerequisite order;
- define exam coverage;
- generate review work over a range of course progress.

The axis supports positions and ranges in course-defined units (Section 45); lesson/session is one example, not a required universal unit.

For lesson N, useful semantic positions include:
- before lesson N;
- during lesson N;
- after lesson N.

Useful ranges include:
- lesson 1 through lesson N;
- lesson A through lesson B.

Examples:
- preview task → attached before lesson 5;
- lecture event → lesson 5;
- note organization → after lesson 5;
- exercise task → after lesson 5 or after notes for lesson 5;
- exam coverage → lessons 1–8.

Tasks may declare prerequisites through this structure.

Example:
```text
notes_for_lesson_5
    ↓ prerequisite
exercise_for_lesson_5
```

The progress axis is a semantic model; exact storage and UI are deferred.

---

## 35. Exam Modeling

An exam should be modeled as an independent event/object rather than a normal Task.

The exam should carry:
- time/date;
- course association;
- coverage expressed using the course progress axis;
- optional importance/weight metadata later.

Exam preparation is generated as one or more Tasks/Goals derived from:
- exam date;
- coverage range;
- review policy;
- current course progress;
- backlog/review state.

This enables exam review to use the same Task-based planner while preserving the fact that the exam itself is an event.

---

## 36. Conditional Review / Catch-Up Tasks

The system may support dormant/conditional task templates for:
- note catch-up;
- review;
- backlog cleanup;
- exam-preparation cleanup.

These tasks are not always active.

They may activate when predefined conditions are met, for example:
- course progress advances beyond a threshold while notes lag;
- a configured review interval is reached;
- exam sprint/review phase begins;
- backlog crosses an accepted threshold.

The user prefers these conditions to be configured ahead of time rather than the system spontaneously inventing arbitrary review work.

---

## 37. Risk State Vocabulary

Use three high-level feasibility states for each planning horizon.

Let:
- `C` = usable capacity in the horizon;
- `R` = expected effort of REQUIRED work that must be completed in the horizon;
- `S` = safety reserve target, approximately **1 hour per day represented in the horizon**.

### SAFE
`C - R >= S`

Required work is feasible while preserving the normal safety reserve.

### DANGER
`0 <= C - R < S`

Required work is still mathematically feasible, but the normal safety reserve has been consumed.

### EMERGENCY
`C - R < 0`

Even using all usable capacity, REQUIRED work is projected not to fit.

For the 1/3/7-day forecasts, the safety reserve scales with the number of days in the horizon. D-078 fixes natural-day horizons including today; usable capacity counts only remaining time. The accepted one-hour-per-represented-day reserve remains unchanged. Numerical rounding and endpoint precision are implementation details, not permission to change the horizon or silently reduce the reserve.

---

## 38. Emergency-Mode Daily Interaction

When the overall mode is EMERGENCY (including an EMERGENCY 3-day or 7-day horizon), daily planning becomes a two-round interaction. The final result must recompute every affected horizon.

### Round 1
The system should still present the **normal plan produced under normal planning rules**, so the user can see the baseline obligations and recommendations.

Then the system should:
- identify the feasibility problem;
- suggest which lower-importance/non-required tasks are candidates for removal;
- explain the principle behind those suggested removals;
- ask the user which items they are willing to remove;
- ask how much additional time they can realistically squeeze out today.

### Round 2
Using:
- user-selected removals;
- extra time the user can provide;

the system recalculates and returns the final emergency-day plan.

The system may recommend sacrifices, but the user retains final authority over what is removed.

---

## 39. Weekly Re-Evaluation of Learned Defaults

The system may autonomously perform a weekly evaluation of historical planning/execution data.

Potential outputs:
- revised effort estimates;
- observed task-type duration patterns;
- procrastination/resistance patterns;
- time-of-day performance patterns;
- recurring underestimation;
- task-template parameter suggestions.

The user must be able to intervene at any time.

A learned behavioral rule that would materially change Planner behavior should be presented to the user for confirmation before becoming an accepted planning rule.

---

## 40. Historical Learning Architecture

Pattern discovery should not be treated as a hidden responsibility of the Planner itself.

Use a conceptual separation:

```text
Execution / WorkSession / plan history
        ↓
Historical Learning / Behavior Analyzer
        ↓
Internal numeric calibration → advisory prediction → Planner
Behavioral pattern → candidate rule → user review → accepted rule → Planner
```

The Planner consumes automatically calibrated numeric predictions and user-accepted behavioral rules. The analyzer computes numeric models and discovers candidate behavioral patterns. Numeric learning does not overwrite user-confirmed estimates or template defaults (Sections 54, 58).

Required data foundations are already conceptually planned, but must be extended to include:
- planned task/session;
- actual completion;
- actual effort;
- estimated remaining effort snapshots;
- release time;
- first meaningful work time when available;
- completion time;
- daily available capacity;
- reasons/categories for non-completion when available;
- time-of-day/session context;
- task type/course;
- difficulty dimensions;
- postponement history.

This is sufficient in principle to support the user's examples:
- "DSA LAB takes ~40% longer than expected";
- "this task type is repeatedly postponed";
- "high-thinking tasks perform poorly at certain times".

Exact persisted schemas are deferred until Phase 2.

---

## 41. User Authority Over Learned Rules

If a learned pattern conflicts with an explicit user rule or preference:

1. do not silently override the user's rule;
2. show the observed evidence/pattern in a concise form;
3. suggest the possible rule change;
4. let the user accept, reject, or modify it;
5. only then update the accepted planning rule.

Historical evidence informs the user; it does not automatically outrank explicit user intent.

---

## 42. Task Importance and Requiredness

### Importance

Task importance uses a **1–5 scale**.

Importance affects:
- ordering among feasible work;
- sacrifice/removal suggestions during emergency replanning;
- which optional work is protected;
- how strongly a task competes for remaining discretionary capacity.

### Requiredness

Use three primary values:

- `REQUIRED`: must ultimately be completed.
- `OPTIONAL`: beneficial but may be skipped.
- `EXPIRING`: only useful until a defined expiration point; after that it may become irrelevant without completion.

`EXPIRING` requires an explicit expiration time/condition.

A deadline and an expiration are not the same concept.

Examples:
- formal homework → REQUIRED + deadline;
- optional practice → OPTIONAL, possibly with a useful-by date;
- preview before class → EXPIRING at/around the class event.

---

## 43. No Separate Lead-Time Rule: Protect Feasibility, Then Use Importance

Do **not** introduce a generic "start this task type N days early" property as a core mechanism.

Preferred principle:

```text
first make all REQUIRED work feasible
↓
preserve the SAFE reserve when possible
↓
if discretionary capacity remains
↓
rank eligible work mainly by Task importance
↓
advance the most valuable work
```

Therefore:
- future REQUIRED work may be advanced;
- high-importance OPTIONAL/EXPIRING work may also be chosen once REQUIRED feasibility is protected;
- the Planner should not blindly pull REQUIRED work from arbitrarily far in the future while ignoring importance and rest.

No generic lead-time field is needed.

---

## 44. TaskType Defaults at Creation

When a TaskType is created/configured, the user will define its default planning properties, including default three-dimensional difficulty.

A concrete Task normally inherits the TaskType defaults automatically.

The user should not need to reconfirm default values for every new Task.

A concrete Task may override defaults when the specific instance materially differs.

---

## 45. Flexible Course Progress Units

A Course Progress Axis must not hard-code "lesson number" as the only structure.

Each course may define what one progress `unit` means.

Examples:
- one lecture/session;
- one chapter;
- one experiment;
- one topic/module;
- another course-specific instructional unit.

The axis still supports relative semantic positions:
- before unit N;
- during unit N;
- after unit N;
- range A–B.

This keeps the model reusable across very different courses.

---

## 46. Teaching Progress vs Task Progress

A course should distinguish:

### Teaching progress
Where instruction itself has reached on the Course Progress Axis.

### Task-family progress
How far different task families have progressed along that same axis.

Examples:
- teaching reached unit 8;
- notes completed through unit 6;
- exercises completed through unit 5;
- previews completed through unit 8.

This allows the system to detect structured lag rather than relying on a single vague "course progress" value.

---

## 47. Default Academic Task Dependency Flow

Course/task templates may predefine a normal learning sequence such as:

```text
preview
→ class/teaching event
→ note organization
→ exercise/homework
```

Dependency semantics must distinguish:

### Hard dependency
The downstream task is genuinely impossible or invalid before the prerequisite.

### Default/soft sequence
The order is educationally preferred but may be bypassed when capacity is tight and a REQUIRED downstream task must be protected.

If the Planner bypasses a normal sequence, it should surface the exception rather than silently pretending the prerequisite was completed.

### Backlog detection
If teaching/task-family progress moves ahead while older Unit-linked tasks remain incomplete (for example, teaching reaches Unit 6 while Unit 5 work remains open), the system should report a backlog/accumulation warning.

Specific courses may override their default dependency structure.

---

## 48. Conditional Review / Catch-Up Activation

Confirmed initial activation examples:

### Repeated missing post-class notes
If post-class note-organization tasks remain incomplete for **three consecutive relevant units**, activate/generate a review/catch-up task according to the course template.

### Exam-preparation phase
When a course enters the configured exam-preparation/sprint phase, generate review tasks for the relevant exam coverage.

Additional activation rules may be configured later.

The system should use predefined conditions rather than spontaneously inventing arbitrary review obligations.

---

## 49. Risk Computation and Aggregation

Risk should be based on **feasibility margin**, not merely the calendar date.

For each horizon (at minimum 1 day, 3 days, 7 days), compare:

```text
usable capacity
vs
required expected effort
```

Interpretation:
- clear margin → SAFE;
- small margin where ordinary uncertainty could cause failure → DANGER;
- expected infeasibility → EMERGENCY.

The category thresholds are fixed by Section 37 / D-059. Calibration may improve effort predictions; it must not silently change the accepted one-hour-per-day reserve or category inequalities.

### Multi-horizon reporting

Report the 1-day, 3-day, and 7-day state separately.

Overall system mode follows the most severe horizon:
- any EMERGENCY horizon → overall EMERGENCY;
- otherwise, any DANGER horizon → overall DANGER;
- otherwise → SAFE.

Therefore one DANGER horizon is enough to enter DANGER mode even if the other horizons are SAFE.

---

## 50. Confirmation Queue Must Be Fully Cleared in Normal Reviews

Morning/evening reviews should not intentionally leave ordinary pending confirmations unresolved merely because they are lower priority.

All pending confirmation items should normally be presented and resolved during the interaction.

Ordering may still prioritize high-impact items first for readability, but the goal is to clear the full confirmation queue in that review session.

---

## 51. Recommended Answer Templates for Confirmation

When asking for confirmation, the system should provide a proposed interpretation/default answer whenever it can do so responsibly.

Example:

```text
Detected candidate:
Assignment 4 — due Oct 12

Recommended:
- create Task: yes
- requiredness: REQUIRED
- task type: normal homework
- inherited default difficulty: 3 / 3 / 2

Confirm or modify?
```

This minimizes user effort while preserving the confirmation boundary.

---

## 52. Daily Brief Content

The accepted normal Daily Brief should contain, at minimum:

- approximate usable free time today;
- 1-day / 3-day / 7-day risk status;
- overall risk mode;
- must-complete / required work for today;
- work that should be advanced today for future feasibility;
- parent Task + concrete stage/subtask to advance;
- estimated effort for each recommended item;
- indication of large-block vs fragmentable work;
- short abnormal/risk notes only when needed.

The normal Brief should remain concise.

### Deadline visibility

Show explicit deadline information by default when:
- the deadline is within the next **3 days**;
- the task is currently risky;
- the user requests expanded detail.

Do not clutter every normal task with distant deadlines.

A concrete reusable template is maintained under:
`formats/output/DAILY_BRIEF_TEMPLATE.md`.

---

## 53. Weekly Learned-Pattern Review

The weekly historical-learning report should show only **actionable** patterns, not raw statistics for their own sake.

Examples:
- repeated effort underestimation large enough to justify changing prediction;
- repeated postponement despite sufficient capacity;
- meaningful time-of-day performance pattern;
- recurring template mismatch.

Each material behavioral/planning recommendation should support:
- accept;
- reject;
- defer / no action yet.

---

## 54. Numeric Prediction Learning vs Behavioral Rule Learning

Use two different permission levels.

### Numeric estimation model
May automatically learn/update internal predictive parameters from history.

Examples:
- duration bias;
- task-type effort distribution;
- calibration factor;
- prediction uncertainty.

This automatic adaptation is allowed because it improves numerical estimates rather than rewriting user policy.

It must still be:
- testable;
- inspectable when needed;
- correctable;
- based on retained history.

### Behavioral / planning rules
Require user review before adoption.

Examples:
- "avoid high-thinking tasks at night";
- "always schedule this task type earlier";
- "change a standing preference."

This distinction is a hard design requirement.

---

## 55. Missing-Interaction Reminder

If there has been no normal user interaction for **two consecutive days**, proactively remind the user to perform a state update/reconciliation.

This is separate from urgent deadline-feasibility alerts, which may trigger sooner.

Exact notification channel is deferred.

---

## 56. Long-Term Goal Onboarding Contract

A new long-term Goal requires a dedicated onboarding interaction containing at least:

- goal definition;
- target/end date;
- total workload or measurable quantity;
- desired outcome/quality level;
- milestone/phase structure where useful;
- preferred recurring/daily allocation;
- required vs adjustable components.

The system should propose a decomposition/task-generation plan.

The user reviews/approves it before activation.

After activation, tasks generated from the Goal enter Planner as ordinary Tasks with no special scheduling privilege merely because their source is a Goal.

Goal-generated Tasks are first-class peers of manually created/course-generated Tasks.

---

## 57. System Permission Boundary

The accepted default authority boundary is:

### May happen automatically
- ingest raw external evidence;
- create candidate tasks/changes;
- compute risk and capacity forecasts;
- compute numeric effort predictions;
- update internal numeric estimation models from history;
- compute descriptive/actionable historical patterns;
- generate Daily Plan recommendations;
- generate proposed interpretations/templates for confirmation.

### Requires user review/confirmation
- create/change canonical Task facts outside the exact preauthorized generation and notice-before-record expiration scope in Section 60;
- change completion/progress/remaining-effort facts;
- alter explicit user preferences;
- adopt new behavioral/planning rules;
- activate important long-term planning structures after onboarding;
- finalize consequential plan changes where the accepted workflow explicitly requires review.

Core principle:
**automatic analysis and recommendation are allowed; canonical truth and key planning policy require user authority, either a direct reviewed update or the exact accepted rule scope in Section 60.**

---

## 58. Final A0 Decisions

### Parent/stage effort display
Normal Daily Brief display should show:
- parent Task remaining total effort;
- today's selected stage/subtask;
- today's stage/subtask estimated effort.

Do not expand every child-stage estimate unless requested.

### Reopening child stages
A completed child stage/subtask may be reopened when later work reveals rework is necessary.

Historical state changes must remain auditable.

### Today-only user lock
If the user explicitly says a Task must be completed/advanced today, create a temporary highest-priority daily override.

The Planner must replan around it.

If the request is physically incompatible with other hard obligations, surface the conflict rather than silently ignoring the user's instruction.

The override expires automatically at the end of the day unless the user explicitly converts it into a persistent rule.

### External completion evidence
For v1, **no external completion signal bypasses confirmation**.

Even a strong source such as "submitted at 21:35" produces:
- candidate evidence;
- recommended completion confirmation;
- no canonical completion change until the user approves.

### Remaining-effort requirement
For every INCOMPLETE Task that remains relevant to future planning, evening review must obtain a user-updated estimate or an explicit confirmation that the prior user-provided estimate still holds. Untouched/unchanged Tasks may be confirmed together (Section 60).

If neither an updated estimate nor an applicable unchanged-estimate confirmation is supplied, continue asking; do not treat omission as confirmation.

The system may offer a model estimate as assistance, but it must not silently substitute it for the user's canonical estimate.

### User estimate vs model estimate
When user and model estimates conflict:
- preserve the user's estimate as canonical personal state;
- retain the model prediction separately as derived information; Section 60 authorizes using a valid model remaining-effort prediction to arrange time and forecast risk;
- allow the model disagreement to create an estimation-risk warning;
- do not overwrite the user estimate automatically.

### SAFE-state discretionary ordering
Once REQUIRED feasibility and the safety reserve are protected, Task importance (1–5) becomes a primary criterion for using additional capacity.

There is no invariant that future REQUIRED work always outranks higher-importance OPTIONAL/EXPIRING work once REQUIRED feasibility is already secured.

### Planning horizons
Use three coordinated planner layers:

- **Daily Planner**: today's actionable work + 1/3/7-day feasibility.
- **Weekly Planner**: next roughly 2–4 weeks, workload distribution, backlog, upcoming bottlenecks, and forward risk preview.
- **Long-Term Planner**: whole Goal/Exam/project horizon, phases, milestones, and long-run workload generation.

These layers share the same canonical Task model rather than maintaining separate task worlds.

### Weekly forward-risk preview
Weekly review should explicitly surface future risk, including:
- unusually tight future days;
- large work that should start before it becomes urgent;
- Course Progress Axis backlog;
- long-term Goal pacing deficits.

### History retention
Preserve historical records for:
- COMPLETE;
- CANCELLED;
- EXPIRED;
- reopened stages;
- previous estimates and state transitions.

Do not hard-delete normal historical outcomes.

Deletion/merge is reserved mainly for:
- erroneous records;
- duplicates;
- data that must be removed for explicit policy/privacy reasons.

---

## 59. A0 Closure

The user considers the current information/interaction alignment sufficient to begin M1.

A0 is therefore **COMPLETE**.

The purpose of A0 was to align semantics, authority, interaction, and planning philosophy—not to freeze every future implementation detail.

Remaining implementation-specific choices, including exact database schema, connector mappings, numerical tuning, UI wording refinements, and provider-specific APIs, are intentionally deferred to their appropriate milestones.

If later development reveals a genuine semantic conflict, return to the A0 principles and update the authoritative documents rather than silently diverging.

---

## 60. Accepted Follow-Up Answers — 2026-10-06

Source: the user's direct answers to the six experience questions, plus an explicit instruction to synchronize the entire document system. These refine earlier sections; A0 remains complete and no implementation milestone is claimed finished.

### Task relationship system (question 1)

Add a system for defining relationships between Tasks. Minimum examples: canonical creation of Task 1 automatically generates its corresponding Task 2; Task 2 must complete before Task 1 completes. Generation direction, completion ordering, start prerequisites, and parent/stage structure have distinct semantics (TASK_RELATIONSHIP_PLAN.md).

An explicitly accepted automatic-generation relationship preauthorizes its mapped instances; execution need not ask the identical question again. This is a scoped rule-execution exception, not permission to accept arbitrary external discoveries or invent missing target facts. Template defaults alone do not grant unrelated automation. All generated Tasks share ordinary Task planning/effort semantics.

### Expiration notice before recording (question 2)

For an EXPIRING Task reaching its already accepted expiration condition, first inform the user, then record EXPIRED and retain its history. The user requested notification before recording, not an additional confirmation click or acknowledgement. If the condition/meaning is uncertain, resolve it as a pending question. Overdue REQUIRED work does not automatically expire. Completion is never inferred from expiration.

### Use model prediction for planning (question 3)

Use a valid model prediction of remaining effort to allocate time and compute required-work feasibility. Keep the user's remaining-effort estimate separately as canonical user-reported state; model planning does not overwrite it. This selects the model value when available, not the maximum of user/model by default, and not only when the model is more pessimistic. If no applicable valid prediction is available, use the retained user estimate with explicit estimate provenance/fallback. A stored/calibrated numerical model suffices; a live LLM call is not required.

Parent user-reported effort, parent effective planning budget, and today's model-based stage allocation must be identifiable when they differ. Routine output remains concise and shows the operative estimate; material disagreement gets a short note.

### Beijing time and date-only cutoff (question 4)

Planning timezone: Asia/Shanghai (Beijing time, UTC+08:00). For a deadline that only names a date, apply that date's 23:59 Beijing-time cutoff and retain the original date-only evidence/default provenance. Preserve explicitly specified source/user times and source timezones; do not replace a supplied specific time with the default. Day-end override expiry is the next local midnight, a separate concept.

The user subsequently selected option A: natural-day horizons including today, with 23:59 Beijing-time cutoffs on today / today+2 / today+6. Section 61 and D-078 record that accepted clarification; O05 is resolved.

### Whole-day small-gap rule (question 5, option A)

After REQUIRED feasibility and the one-hour reserve are protected, if the aggregate remaining discretionary capacity across the entire day is at most 40 minutes, leave it free in SAFE. Do not apply a blanket 40-minute minimum to each individual window. With more aggregate capacity, eligible fragmentable work may use individual windows of 40 minutes or less. DANGER/EMERGENCY may use productive short gaps under existing rules.

### Consolidated unchanged-estimate review (question 6, option A)

Update worked-on Tasks individually. For Tasks not worked on and whose estimate remains unchanged, present a clearly scoped batch and let the user confirm “keep the previous estimates.” Record per-Task confirmation provenance while preserving the original numeric estimate and observation time; review verification time may advance. Do not require duplicate per-Task numeric entry.

Silence is not confirmation. New Tasks lacking a previous user estimate, changed/uncertain estimates, Tasks actually worked on, and unresolved completion candidates still need their appropriate review. Do not infer zero time spent for an untouched Task unless the user's statement actually covers it.

---

## 61. Accepted Natural-Day Forecast Windows — 2026-10-06

Source: the user's explicit answer “A。自然日” to the final O05 subquestion. This completes the horizon scope without reopening any other accepted preference.

Use Asia/Shanghai local dates, including today as day 1. The 1-day window ends today at 23:59; 3-day ends today+2 at 23:59; 7-day ends today+6 at 23:59. These are calendar-date windows, not rolling 24/72/168 hours from the calculation instant.

An intraday forecast counts only usable capacity remaining after its calculation snapshot; elapsed portions of today are not future capacity. Keep the accepted one-hour reserve per represented day (1/3/7-hour default targets), model-first remaining-work budget, real deadline/window feasibility checks, and worst-horizon aggregation. This choice does not authorize proportional reserve reduction, shifting explicit source deadlines, or shortening a Task's actual deadline to the forecast boundary. Numerical rounding and machine endpoint precision are later engineering work consistent with the accepted 23:59 cutoff.

All original O01–O08 boundaries are resolved. The detailed development plan is now complete; M1/M1B/M2 and runtime implementation remain incomplete. PROGRESS and task catalogs determine the next work, not this historical clarification.

---

## 62. Detailed Development Planning Requirement — 2026-10-06

The user requested a detailed complete development plan in plan/, decomposed into tasks small enough for one AI development execution, with particular emphasis on robustness and extensibility. Link it into the complete documentation system and replace unnecessary files while preserving the project's documented information.

DEVELOPMENT_PLAN and plan/tasks catalogs implement this planning requirement. Each task identifies prerequisites, bounded outcome, acceptance and failure/extension checks; real courses/providers/patterns use explicit repeated instances. Reliability begins with persistence/ingestion, not a final polish stage. Semantic source documents remain authoritative; this request does not change accepted task/authority/planning rules or claim runtime implementation.

The coarse roadmap is replaced at DEVELOPMENT_PLAN.md; the completed audit working report is retired after its invariants and C/O traceability are migrated into the new plan. Current status/evidence remains PROGRESS. Routine technical choices are made at their bounded tasks; unknown current-semester facts are collected without importing old-chat assumptions.

---

## Detailed Execution Mapping

All task catalogs preserve these accepted semantics; engineering tasks cannot silently alter them.
