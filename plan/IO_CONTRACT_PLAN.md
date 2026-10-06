# WhatToDo — Input / Output Contract Planning

> Execution: [detailed development plan](DEVELOPMENT_PLAN.md) · [live progress](PROGRESS.md).
> Bounded work: [M2_CONTRACTS](tasks/M2_CONTRACTS.md) · [M3_STATE_FOUNDATION](tasks/M3_STATE_FOUNDATION.md) · [M3_RELATIONSHIPS_REVIEWS](tasks/M3_RELATIONSHIPS_REVIEWS.md) · [M6_PLANNER_DAILY_MVP](tasks/M6_PLANNER_DAILY_MVP.md).

> Conceptual contract authority. Concrete schemas/examples belong under `../formats/` once agreed.

## 1. Core Principle

Humans should interact naturally.
Machines should interact structurally.

```text
Human/raw source
↓
parse/normalize
↓
structured candidate / resolved explicit user instruction
↓
user review when not already authorized by an explicit command or accepted generation relationship
↓
validate schema, references, authority, and state version
↓
trusted state + audit
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
→ update remaining effort for worked-on future-relevant incomplete Tasks
→ list untouched/unchanged Tasks for one explicit “keep previous estimates” batch confirmation
→ obtain initial/changed estimates for uncovered incomplete Tasks
→ if missing, continue follow-up until supplied
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
- today-only "must do this Task" override
- define/change/remove typed Task relationships and approved automatic generation
- explicitly confirm a listed unchanged-estimate batch

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

For every external proposal that changes canonical personal Task facts, regardless of confidence:
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

Canonical personal-state mutations require user authority by default. D-072 permits mapped instance creation under an accepted generation relationship, and D-073 permits expiration after informing the user. Ordinary external ingestion still updates evidence/candidates; it does not bypass review.

For v1, there is no completion shortcut: even a high-confidence submission record requires user confirmation before canonical completion changes.

If the user explicitly locks a Task for today, treat that as a temporary daily planning constraint and expire it automatically at day end unless the user makes it persistent.

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

Urgent feasibility-risk notifications are allowed outside the normal morning/evening interaction. Risk-state thresholds are accepted; delivery channel, repeat suppression, and notification timing details remain deferred.

The current A0-approved human template is stored at `../formats/output/DAILY_BRIEF_TEMPLATE.md`.

M2 may refine exact wording without silently changing its accepted semantics.

Default explanation policy:
- concise during normal operation;
- expand for abnormal/risky/uncertain/surprising recommendations or when explicitly requested.

Per recommended Task, normal display should show parent remaining effort plus today's selected stage/subtask and that stage's estimated effort. Avoid expanding every child stage unless requested.

Weekly output should include a forward-risk preview covering upcoming bottlenecks, Course Progress Axis backlog, large work needing early progress, and long-term Goal pacing.

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
- realistic rendering examples using the already accepted Daily Brief template
- refinements to wording/optional detail while preserving the accepted content and 3-day deadline visibility

These should be solved before Phase 2 database design.

Provider-specific Calendar/email/learning-platform payload details are intentionally not required at this stage; they are resolved during their integration phases unless a discovery changes the internal semantic model.

---

## 10. Review, Generation, and Emergency Boundaries

A clear explicit user statement can authorize the described personal-state update after target resolution and validation. Do not require a redundant second confirmation. Ambiguous references or extra inferred changes still require review. A today-only lock distinguishes “complete today” from “advance this stage today”; do not weaken the requested action.

Normal reviews present the full pending queue, with recommendations and high-impact items first. The 5–10 minute duration is an expectation, not authority to discard lower-priority questions. Missing/unanswerable items remain pending, and any blocked reconciliation/review is visible; no fabricated answer or completion is allowed. D-065 still requires remaining effort for every future-relevant INCOMPLETE Task; D-077 now permits explicit bulk reconfirmation of untouched Tasks with existing unchanged estimates; no silent carry-forward is permitted.

Recurring/Goal/conditional work may create canonical mapped Tasks when covered by an accepted automatic-generation relationship (D-072). Outside that scope, use candidates/review. Template inheritance alone does not grant blanket authority; approved rule execution needs no repeated per-instance/field confirmation.

Overall EMERGENCY uses two rounds even if only the 3-day or 7-day horizon is infeasible. Round 1 shows a visibly provisional baseline and actual deficit. Round 2 applies user-approved removals/additional capacity, recomputes all horizons, and reports any remaining infeasibility. Removing an item from today's recommendation is not canonical cancellation/deletion of its Task, and optional removal alone does not reduce REQUIRED R. More today-capacity cannot by itself solve every future deadline/window bottleneck.

The machine contract in M2 must distinguish task requiredness from plan role (must/protect today, advance, optional), completion from disposition/trust, parent work from selected stage effort, derived model planning predictions from user-canonical estimates, and provisional from final emergency output. No implemented machine schema exists yet.

Internal O03 accounting is now resolved in DATA_MODEL_PLAN Section 12: effective model-first parent budget B governs forecast totals; stage budgets are derived allocations, with canonical user U separate and contradictory accepted estimates preserved/reconciled when material. O06 placement checks and horizon accounting are resolved in PLANNER_PLAN Section 21. D-071–D-077 resolve relationship generation, notify-before-record expiration, model-first planning, Beijing timezone/23:59, aggregate short-gap policy, and bulk unchanged-estimate review. D-078 closes O05: 1/3/7-day windows are natural days including today, ending today / today+2 / today+6 at 23:59 Asia/Shanghai. Machine output carries snapshot time, timezone, natural-day window mode, and date/cutoff bounds; elapsed time is not usable future capacity.

---

## 11. Follow-Up Interaction and Output Contract

Relationship inputs distinguish creation-trigger mapping, completion-before-completion, completion-before-start, soft sequence, and parent/stage membership. A creation event is not a completion event. Natural-language setup resolves IDs/meaning and accepted rule scope before automatic execution; unsafe or ambiguous changes stay pending.

Expiration flow: detect confirmed condition → inform user → validate latest state/version → record EXPIRED with retained history. No additional acknowledgement was requested. Notification failure remains process/pending state, not successful delivery. Uncertain expiration meaning becomes a confirmation question instead of an automatic write.

Planning uses the valid model remaining-effort prediction as the operative estimate; fallback is the accepted user value when unavailable. Machine output must retain selected planning estimate/source/model version plus canonical user estimate. Brief labels should distinguish “remaining effort for planning” from “your reported remaining effort” where they differ. A material discrepancy gets one concise note, not a new daily approval requirement.

Worked-on Tasks report completion/actual effort/updated remaining effort; untouched Tasks may share a listed “keep previous estimates” confirmation. The batch must identify covered Tasks, exclude missing initial/changed/uncertain estimates, and retain per-Task provenance. Silence or a skipped interaction supplies no confirmation.

Render daily dates and date-only 23:59 deadlines in Beijing time. Preserve explicit deadline times. The SAFE 40-minute rule applies to the whole day's discretionary remainder after reserve, not each fragment. A materially blocking/violated hard relationship may be shown as a short reason; routine output does not need a graph or implementation field names.

---

## Detailed Execution Mapping

M3A-21–22 provide bounded natural/guided input and target resolution; M3B reviews/batches and M6 normal/emergency loops consume the same authorized commands.
