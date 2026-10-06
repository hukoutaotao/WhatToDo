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

Semantic flow:
```text
refresh external evidence
→ reconcile state
→ batch/present pending uncertainty questions
→ accept user corrections / special constraints
→ generate today's concise plan
```

The user should not need to restate normal planning rules every morning.

### Evening interaction
Expected normal duration: roughly 5–10 minutes.

Semantic flow:
```text
review today's planned items
→ confirm completed / incomplete
→ capture actual effort where useful
→ confirm externally detected completion candidates
→ update state
→ update historical estimation data
→ carry forward/replan as needed
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
- create
- update/correct
- complete
- cancel
- delete/withdraw source fact
- merge duplicate
- conflict

Avoid treating all incoming text as "create new task."

---

## 5. Direct User Authority

Explicit user corrections are usually authoritative for personal state.

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
- Today must do
- Today should do
- If time remains
- tasks best suited to large uninterrupted blocks
- fragmentable/short-gap tasks
- fixed commitments if useful
- Risks
- Weekly progress

Do not require exact clock assignment for every task in the normal output.

The user will define exact brevity/order during M2.

Default explanation policy:
- concise during normal operation;
- expand for abnormal/risky/uncertain/surprising recommendations or when explicitly requested.

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
