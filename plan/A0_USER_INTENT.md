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

## 17. A0 Items Still Requiring Follow-Up

The 12 initial questions established strong requirements but did not completely finish A0.

Still to align in later A0 rounds:
- exact morning interaction sequence and what is shown first;
- exact evening review sequence;
- how pending uncertainties are prioritized/presented;
- exact task decomposition representation;
- scales/labels for the three difficulty dimensions;
- whether and how partial progress is entered;
- how remaining effort is updated after partial completion;
- rules for automatic vs manual task creation from external sources;
- what constitutes "enough" free time for different task categories;
- daily output layout;
- overload/underload tolerance;
- exceptions that may warrant urgent notification outside the normal twice-daily interaction;
- semantics for missed multiple days and backlog recovery;
- per-course profile details;
- per-goal onboarding fields;
- which external completion signals will eventually be supported.

Do not treat these as implementation blockers yet; resolve them through subsequent A0 conversations before the dependent modules are frozen.
