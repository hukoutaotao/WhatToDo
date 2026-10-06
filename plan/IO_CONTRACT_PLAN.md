# WhatToDo — Input / Output Contract Planning

> Conceptual contract authority. Concrete schemas/examples belong under `../formats/` once agreed.

## 1. Core Principle

Humans should interact naturally.
Machines should interact structurally.

```text
Human/raw source
↓
parse/normalize
↓
structured candidate
↓
validate
↓
trusted state
```

For output:

```text
trusted state + planner
↓
structured Plan
↓
renderer
↓
human Daily Brief / other surfaces
```

Do not make the user manually author JSON for ordinary use.

### Semantic contract vs adapter contract

Before implementation, define the internal semantic contract: what WhatToDo needs to know and what that information means.

Provider-specific adapter contracts should be defined when the real integration is examined.

Example:
- semantic Calendar concept now: start/end, fixed/flexible, busy/free, ownership, recurrence concept
- Google Calendar mapping later: exact API fields, IDs, sync tokens, webhook/watch behavior, recurrence edge cases

Do not guess provider-specific details merely to make an early schema look complete.

---

## 2. Input Source Classes

## 2A. Normal Human Interaction Contract

### Morning interaction
Expected normal duration: roughly 5–10 minutes.

Accepted semantic flow:
```text
refresh/reconcile external evidence
→ batch/present items requiring user review
→ ask a guided special-circumstances question
  ("Is there anything special today that needs to be arranged?")
→ accept corrections / special constraints
→ estimate usable free time
→ generate today's concise plan
```

The user should not need to restate normal planning rules every morning.

### Evening interaction
Expected normal duration: roughly 5–10 minutes.

Interaction rule:
- present the full normal review questionnaire once;
- let the user answer in one message;
- ask follow-up only for missing/ambiguous information.

Semantic flow:
```text
show/report requirements for all relevant items
→ confirm COMPLETE / INCOMPLETE
→ capture cumulative/new actual effort
→ for every incomplete task, capture latest estimated remaining effort
→ confirm externally detected completion candidates
→ update state
→ update historical estimation data
→ replan rather than mechanically roll unfinished tasks forward
```

If a normal interaction is skipped, external collection may continue; unresolved personal state is reconciled at the next interaction.

---

### A. Direct user input
Examples:
- New task
- Completion
- Partial progress
- Deadline correction
- Cancellation
- New goal
- Schedule change
- Effort estimate correction

Need:
- Natural-language interpretation
- Reference resolution
- Structured patch proposal
- Confirmation when ambiguity materially changes state

### B. Calendar
Produces:
- Fixed events
- One-off changes
- optional flexible planned blocks

Must preserve external event ID and source calendar.

### C. Email
Produces candidate facts:
- task
- deadline change
- event
- announcement
- cancellation
- administrative action

### D. Learning platform
Produces candidate facts:
- assignment
- deadline
- announcement
- exam
- material/update

### E. Internal system/history
Produces:
- recurring generated tasks
- risk signals
- stale-state markers
- work-session observations
- AI jobs

---

## 3. Normalized Input Requirements

Every normalized external input should be able to carry:
- source type
- source identifier
- source timestamp
- ingestion timestamp
- intended entity/action
- extracted structured fields
- confidence
- parser/extractor version where relevant
- raw-source reference or hash
- deduplication key/strategy

A normalized input is not automatically trusted state.

If confidence is insufficient for a consequential change:
- keep it as a candidate/pending-confirmation object;
- do not silently mutate trusted state;
- batch it into the next normal interaction.

Externally detected possible completion is specifically advisory until confirmed by the user.

---

## 4. Update Semantics

Input must distinguish:
- candidate create
- confirmed create
- update/correct
- complete
- incomplete with updated remaining effort
- cancel
- delete/withdraw source fact
- merge duplicate
- conflict

Avoid treating all incoming text as "create new task."

---

## 5. Direct User Authority

Explicit user corrections are authoritative for personal task state.

New task-like content discovered externally must be reviewed by the user before canonical task creation.

More generally, consequential canonical personal task-state mutations require user confirmation by default. Automated ingestion updates evidence/candidates, not accepted operational truth.

Normal morning/evening review should attempt to clear the entire pending confirmation queue in that interaction.

Where responsible, present a recommended interpretation/template so the user can confirm or modify rather than rebuild the record manually.

Example:
"This homework is actually due Friday, not Thursday."

The system should:
1. Resolve target task.
2. Create structured change.
3. Preserve correction provenance.
4. Update trusted state after validation.
5. Trigger replanning if material.

---

## 6. Output Layers

### Structured machine output
A Daily Plan should eventually include:
- plan date
- generation time
- state snapshot/version reference
- fixed events
- scheduled task sessions
- must-do tasks
- should-do tasks
- optional tasks
- risks
- long-term/weekly progress
- explanations/reasons where configured

### Human output
Must be easy to scan.

Potential sections:
- approximate usable free time today
- overall near-term capacity/risk status: SAFE / DANGER / EMERGENCY
- Today must do
- Today should do
- If time remains
- tasks best suited to large uninterrupted blocks
- fragmentable/short-gap tasks
- fixed commitments if useful
- Risks
- Weekly progress

Do not require exact clock assignment for every task in the normal output.

Risk output should report 1-day, 3-day, and 7-day states separately. Overall mode uses the most severe horizon.

Urgent feasibility-risk notifications are allowed outside the normal morning/evening interaction; exact channel and threshold are deferred.

The current A0-approved human template is stored at `../formats/output/DAILY_BRIEF_TEMPLATE.md`.

M2 may refine exact wording without silently changing its accepted semantics.

Default explanation policy:
- concise during normal operation;
- expand for abnormal/risky/uncertain/surprising recommendations or when explicitly requested.

Show an explicit deadline by default when it is within 3 days, when the task is risky, or when the user requests detail.

---

## 7. Stability and Versioning

Once machine schemas are implemented:
- version them
- avoid undocumented breaking changes
- include schema version in payloads where useful
- maintain migration/conversion logic when required

Concrete files under `formats/` should eventually include:
- specification
- schema
- valid examples
- invalid/edge examples
- version history

---

## 8. Relationship with formats/

`IO_CONTRACT_PLAN.md`:
- why the contract works this way
- conceptual requirements
- cross-source semantics

`../formats/input/`:
- concrete input schemas/examples

`../formats/output/`:
- concrete output schemas/examples

If a concrete format contradicts this file:
- determine whether implementation or plan is newer/correct
- update both to restore consistency
- record material design changes in DECISIONS if needed

---

## 9. Phase 1 Questions

Need from user:
- realistic task-creation examples
- completion/progress/correction examples
- examples of ambiguous instructions
- preferred daily brief
- exact information the user wants visible every day

These should be solved before Phase 2 database design.

Provider-specific Calendar/email/learning-platform payload details are intentionally not required at this stage; they are resolved during their integration phases unless a discovery changes the internal semantic model.
