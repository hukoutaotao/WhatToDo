# WhatToDo — Interaction and Information-Model Alignment Plan

> Status: COMPLETE
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
| TaskType importance / requiredness defaults | importance 1–5; REQUIRED / OPTIONAL / EXPIRING | Task creation, planner | initializes Task-level attributes; no primary Course importance score |
| typical task types | homework, lab, preview | input normalization, task templates, planner | determines likely structure and handling |
| TaskType difficulty defaults | thinking depth / repetitive volume / new-learning load, each 1–5 | Task creation, estimator, planner | distinguishes reasoning, repetition, and new learning |
| workload / volume | usually large | planner, estimator | affects early allocation and risk |
| typical duration | LAB often 3–5 h | estimator, planner | determines how much capacity to reserve |
| derived estimation uncertainty | historical duration variation | estimator, risk logic | flags prediction risk; not a required manual reliability score |
| minimum useful session | e.g. 90 min | scheduler | prevents placing task into unusably short gaps |
| fragmentability | low / medium / high | scheduler | determines whether short gaps are usable |
| preferred time | e.g. daytime for hard coding | planner | soft scheduling preference |
| deadline pattern | often weekly | task generator, connector matching | supports recurring expectations |
| dependency pattern | preview → lab → report, with hard/soft edges | task graph, planner | hard edges bind; soft order may be bypassed with an exception note |
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

Alignment Gate A0 is **COMPLETE**.

The user explicitly accepted the current level of information/interaction alignment after the final A0 round.

Completed alignment includes:
- twice-daily normal interaction and missed-interaction recovery;
- conservative canonical-state authority and confirmation boundaries;
- Task-centric model, TaskType defaults, parent/stage semantics, and remaining-effort tracking;
- importance 1–5 and REQUIRED / OPTIONAL / EXPIRING semantics;
- three-dimensional difficulty;
- Course Progress Axis, teaching/task-family progress, dependency/backlog semantics, and Exam model;
- one-hour-per-day SAFE reserve and SAFE / DANGER / EMERGENCY feasibility rules;
- daily / weekly / long-term Planner horizons;
- today-only user overrides;
- Daily Brief semantics;
- historical numeric learning vs reviewed behavioral rules;
- long-term Goal onboarding and Task parity;
- semantic-contract vs provider-adapter separation.

A0 completion checklist:

- [x] User-AI development interaction model accepted
- [x] Major modules identified
- [x] Required information categories are understood for near-term work
- [x] Information granularity is sufficient to begin M1
- [x] Cross-module effects are documented
- [x] Stable vs dynamic vs derived information is distinguished conceptually
- [x] Semantic contracts are separated from provider-specific adapter contracts
- [x] Deferred implementation/provider questions are explicitly marked
- [x] Course/user modeling approach is accepted
- [x] Task modeling approach is ready for M1/M1B/M2 refinement
- [x] Input/output alignment process is accepted
- [x] Planner risk/priority/authority philosophy is accepted
- [x] Historical-learning authority boundary is accepted

A0 does **not** freeze:
- real Calendar API field names
- n8n workflow node configuration
- PostgreSQL table definitions
- learning-platform selectors
- exact planner scoring formula
- exact statistical estimation algorithm
- exact model provider
- implementation/UI details that do not alter accepted semantics

Those belong to later milestones.

If later work reveals a semantic contradiction, update A0/decisions deliberately; do not silently diverge.

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

A0 is accepted. M1 remains the next incomplete semantic milestone. Follow the current handoff in PROGRESS.md: complete the requested post-audit detailed planning first, then collect actual course/activity information under M1.

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

