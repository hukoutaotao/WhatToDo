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

---

## 2. Input Source Classes

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
- Today must do
- Today should do
- If time remains
- Fixed schedule
- Fragment tasks
- Risks
- Weekly progress

The user will define exact brevity/order during M2.

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
