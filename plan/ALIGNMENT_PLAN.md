# WhatToDo — Interaction and Information-Model Alignment Plan

> Status: ACTIVE
> Purpose: Complete human-AI alignment before implementation begins.
> This is the authoritative plan for the pre-development alignment gate.
> User-specific accepted/working intent from A0 is stored in `A0_USER_INTENT.md` and must be read together with this file.

## 1. Why This Stage Exists

The project will be developed primarily through large-model-assisted work. Therefore, implementation must not begin merely because the high-level architecture is understood.

Before development starts, the user and AI must share the same understanding of:

- how they will collaborate during planning and implementation
- what each module means
- what information each module needs
- the required granularity of that information
- which information is stable vs dynamic
- which source is authoritative
- which downstream modules consume each piece of information
- what behavior each field affects
- what can be defined conceptually now
- what must be deferred until a real external system is connected

This alignment stage is intentionally prior to database, n8n, connector, planner, and AI implementation.

---

## 2. Interaction Model: User ↔ AI During Development

### User role

The user is the authority for:
- intended behavior
- real-life workflow
- course/task meaning
- planning preferences
- acceptable automation
- what information matters
- whether the system's representation matches reality

The user does not need to:
- design database tables
- write JSON
- choose implementation-specific field names
- understand connector APIs
- manually maintain technical planning documents

### AI role

The AI is responsible for:
- eliciting only the information needed for the current alignment topic
- translating natural-language intent into structured models
- identifying hidden dependencies
- distinguishing semantic requirements from implementation details
- proposing schemas and module contracts
- recording accepted decisions in the repository
- updating dependent plan files
- avoiding premature implementation
- surfacing unresolved questions before they become code-level ambiguity

### Review loop

Preferred loop:

```text
User explains intent / examples
        ↓
AI builds structured interpretation
        ↓
AI explains the interpretation in human terms
        ↓
User corrects or accepts
        ↓
AI updates canonical plan documents
        ↓
Only after alignment gate passes: implementation
```

The user should not need to read long AI-oriented plan files. Those files exist primarily so future AI agents can continue consistently.

---

## 3. Interaction Model During Later Implementation

Once alignment is complete:

1. AI reads `plan/README.md` and `PROGRESS.md`.
2. AI identifies the current milestone and authoritative plan.
3. AI performs the implementation task.
4. AI updates tests and affected planning documents.
5. AI updates `PROGRESS.md`.
6. User reviews behavior/results rather than low-level internal documentation unless desired.

For major semantic changes, return to the alignment logic before modifying implementation.

---

## 4. Information-Model Alignment Template

Before implementing any module, define the following:

### A. Module purpose
What real-world problem does the module solve?

### B. Information it needs
What concepts/fields are required?

### C. Information granularity
How precise must each field be?

Examples:
- exact timestamp vs date-only
- one scalar difficulty score vs several dimensions
- task-level estimate vs task-type historical distribution

### D. Source / authority
Who or what provides the information?
- user
- calendar
- email
- learning platform
- system inference
- planner history

### E. Stability
Is it:
- stable profile data
- slowly changing configuration
- dynamic operational state
- derived/temporary data

### F. Downstream consumers
Which modules use it?

### G. Behavioral effect
Exactly what changes because this information exists?

### H. Confidence / correction
Can it be inferred?
Can it be wrong?
How is it corrected?

### I. Deferred implementation details
Which details cannot be known until a real service/API is connected?

### J. Examples and edge cases
Use realistic examples before freezing the model.

A module is not semantically aligned until these questions are answered sufficiently for its current development phase.

---

## 5. Example: Course Information Granularity and Effects

A Course is not just a name. Its profile exists because course-level differences should change downstream behavior.

| Course information | Example meaning | Main consumers | Behavioral effect |
| --- | --- | --- | --- |
| course identity | "Data Structures and Algorithms" | task model, connectors, output | groups tasks and source mappings |
| importance | high / medium / contextual | planner | affects allocation when capacity is scarce |
| typical task types | homework, lab, preview | input normalization, task templates, planner | determines likely structure and handling |
| cognitive difficulty | high reasoning/debugging load | planner | influences time-of-day and focus-window choice |
| workload / volume | usually large | planner, estimator | affects early allocation and risk |
| typical duration | LAB often 3–5 h | estimator, planner | determines how much capacity to reserve |
| estimation uncertainty | duration is hard to predict | planner, risk logic | adds buffer / avoids deadline compression |
| minimum useful session | e.g. 90 min | scheduler | prevents placing task into unusably short gaps |
| fragmentability | low / medium / high | scheduler | determines whether short gaps are usable |
| preferred time | e.g. daytime for hard coding | planner | soft scheduling preference |
| deadline pattern | often weekly | task generator, connector matching | supports recurring expectations |
| dependency pattern | preview → lab → report | task graph, planner | enforces order |
| exam/review pattern | review should start 2 weeks early | goal system, planner | generates future workload |
| cumulative knowledge | strongly cumulative | planner, weekly review | discourages persistent backlog |

This table is an example of the required semantic depth.

The exact final Course schema is not frozen by this file. During M1, the user and AI will determine which fields are actually necessary and whether some dimensions need to be split or removed.

---

## 6. Module-Level Information Alignment

Before implementation, each major module must eventually receive the same treatment.

### User / Course Model
Align now, in detail.

Need to understand:
- course/activity categories
- recurring task types
- difficulty dimensions
- workload
- timing/fragmentation
- dependencies
- review/exam patterns
- planning-relevant preferences

### Task Model
Align immediately after course model.

Need to understand:
- what counts as one Task
- parent/child decomposition
- deadline semantics
- progress
- effort estimates
- status lifecycle
- source/provenance
- task dependencies
- uncertainty/confidence

### Input Model
Align conceptually before implementation.

Need to understand:
- user natural-language input
- create/update/complete/cancel semantics
- source authority
- ambiguity handling
- normalization target

Provider-specific API payload fields are deferred.

### Output Model
Align conceptually before implementation.

Need to understand:
- what user sees daily
- detail level
- ordering
- time-block precision
- risk information
- explanations
- long-term progress

Rendering mechanics may be implemented later.

### Long-Term Goal Model
Align conceptually before implementation.

Need to understand:
- Goal vs Milestone vs Task
- pacing
- recurrence
- review windows
- completion criteria

### Calendar / Time Model
Align only the semantic layer now.

Define conceptually:
- fixed vs flexible event
- busy interval
- recurrence
- travel/preparation buffer if relevant
- movable vs immovable
- user-owned planned work block
- availability constraints

Defer until actual Google Calendar integration:
- exact API field mapping
- calendar IDs
- event IDs
- webhook/watch details
- recurrence expansion behavior
- sync tokens/cursors
- provider-specific edge cases

These implementation details must be determined against the real API/connector rather than guessed in advance.

### Email Model
Align semantic needs before implementation:
- what types of messages matter
- candidate facts to extract
- source authority/conflict behavior

Defer provider-specific metadata and exact Gmail/n8n node behavior until integration.

### Learning Platform Model
Align semantic outputs before implementation:
- assignment
- deadline change
- announcement
- exam
- material update

Defer DOM selectors, authentication, request flow, and scraper-specific interfaces until real access is examined.

### Planner
Align the meaning of inputs and preferences before code.
Exact scoring formula may remain deferred until representative data exists.

### AI Router
Align task classes and trust boundary now.
Exact model/provider configuration can remain deferred.

---

## 7. Semantic Contract vs Adapter Contract

Use two levels of interface definition.

### Semantic Contract
Defined before implementation.

Example for Calendar:

```text
Event
- start
- end
- busy/free
- fixed/flexible
- recurrence concept
- source
- ownership
```

This describes what WhatToDo needs to know.

### Adapter Contract
Defined when integrating the real provider.

Example:

```text
Google Calendar API field X
→ internal Event.start
Google Calendar recurring instance behavior
→ internal recurrence handling
```

This describes how an external system maps into WhatToDo.

Rule:
Do not block semantic alignment on provider details that can only be learned during integration.
Do not freeze adapter details before the provider is actually inspected.

---

## 8. Alignment Gate A0

No implementation phase may begin until A0 is complete.

Current status:
- Initial 12-question A0 round completed.
- Second follow-up A0 round completed.
- Third A0 round on task-centric modeling, Course Progress Axis, Exam semantics, risk states, and historical learning completed.
- Fourth A0 round on importance/requiredness, safe-capacity advancement, output template, automatic numeric learning, reminder policy, and authority boundaries completed.
- The consolidated results are captured in `A0_USER_INTENT.md`.
- A0 is **near completion**; only a narrow final consistency/threshold/display review remains.

A0 requires:

- [x] Initial user-AI daily interaction model captured
- [x] Normal morning/evening cadence captured
- [x] Uncertainty must be queued for user confirmation rather than silently resolved
- [x] Planner is recommendation-oriented rather than exact clock scheduling by default
- [x] Multi-dimensional task difficulty concept captured
- [x] Historical actual-time memory requirement captured
- [x] Dedicated course/task decomposition modeling requirement captured
- [x] Dedicated long-term-goal onboarding requirement captured
- [x] Morning guided interaction order accepted
- [x] Evening one-batch review pattern accepted
- [x] Binary parent-task completion + remaining-effort tracking accepted
- [x] Parent-task + stage/subtask structure accepted
- [x] Fixed default decomposition template per normal task type accepted
- [x] History-derived procrastination signal accepted conceptually
- [x] Normal 40–60 minute daily buffer target accepted
- [x] Emergency/capacity-risk reminder concept accepted
- [x] New canonical task requires user review
- [x] 1/3/7-day capacity forecasting accepted
- [x] Long-horizon feasibility is the planner objective
- [x] Task established as the fundamental planning unit
- [x] Course-level importance removed from primary Planner semantics
- [x] Importance and requiredness separated
- [x] 1–5 task-level difficulty scales accepted
- [x] Course Progress Axis accepted
- [x] Exam modeled independently from preparation Tasks
- [x] SAFE / DANGER / EMERGENCY vocabulary accepted
- [x] Historical learning separated from Planner with user-confirmed rule adoption
- [x] Task importance 1–5 accepted
- [x] REQUIRED / OPTIONAL / EXPIRING accepted
- [x] No generic lead-time field; safe-capacity advancement accepted
- [x] Course-defined progress units + teaching/task-family progress accepted
- [x] Default academic dependency templates accepted
- [x] Conditional note-review and exam-review triggers accepted
- [x] Worst-horizon SAFE/DANGER/EMERGENCY aggregation accepted
- [x] Full confirmation queue + recommended-answer prompts accepted
- [x] Daily Brief baseline structure/template accepted
- [x] Automatic numeric learning vs reviewed behavioral rules accepted
- [x] Two-day missed-interaction reminder accepted
- [x] Long-term goal onboarding fields and equal Planner treatment accepted
- [x] Overall automatic-analysis vs reviewed-truth/policy boundary accepted
- [ ] Final narrow threshold/display consistency items accepted
- [ ] Major modules identified
- [ ] For each near-term module, required information categories are understood
- [ ] Information granularity is discussed enough to avoid obvious ambiguity
- [ ] Cross-module effects are documented
- [ ] Stable vs dynamic vs derived information is distinguished
- [ ] Semantic contracts are separated from provider-specific adapter contracts
- [ ] Deferred questions are explicitly marked rather than guessed
- [ ] Course/user modeling approach is accepted
- [ ] Task modeling approach is ready to begin
- [ ] Input/output alignment process is accepted

A0 does not require:
- real Calendar API field names
- n8n workflow node configuration
- PostgreSQL table definitions
- learning-platform selectors
- exact planner formula
- exact model provider

Those belong to later milestones.

---

## 9. Required Deliverable Before M1

The output of this alignment stage is not code.

It is a shared mental model represented in:
- this file
- USER_MODEL_PLAN
- DATA_MODEL_PLAN
- IO_CONTRACT_PLAN
- relevant decisions
- PROGRESS

Once A0 is accepted, proceed to M1 and collect actual course/activity information.

---

## 10. Change Propagation

If the interaction model or information-granularity philosophy changes:

Update:
1. this file
2. DECISIONS.md
3. DEVELOPMENT_PLAN.md if gate/order changes
4. USER_MODEL_PLAN.md
5. DATA_MODEL_PLAN.md
6. IO_CONTRACT_PLAN.md
7. affected specialized plans
8. PROGRESS.md

If a provider-specific detail is discovered later:
- update the relevant specialized integration plan
- update semantic plans only if the discovery changes the internal meaning, not merely field mapping
