# WhatToDo — Integration and n8n Plan

> Execution: [detailed development plan](DEVELOPMENT_PLAN.md) · [live progress](PROGRESS.md).
> Bounded work: [M4_CALENDAR_CAPACITY](tasks/M4_CALENDAR_CAPACITY.md) · [M5_INGESTION_N8N](tasks/M5_INGESTION_N8N.md).

## 1. Platform Decision

n8n is the sole workflow/orchestration platform.

Do not introduce Dify unless the user explicitly changes the accepted decision.

n8n responsibilities:
- schedules/triggers
- API calls
- connector execution
- database orchestration
- retries
- notifications
- invoking AI endpoints where appropriate
- passing normalized data between modules

Business/domain logic that needs testing and reuse should live in application code rather than becoming opaque n8n-only logic.

---

## 2. Integration Boundary

Connectors collect and normalize.
They do not decide the daily plan.

### Semantic contract first, adapter contract later

Before a connector is implemented, the internal semantic output it must produce should already be understood.

The provider-specific adapter mapping is intentionally finalized only when the real service/API/n8n connector is inspected.

Do not invent exact external field mappings during early planning. If a real integration reveals a semantic requirement that the internal model lacks, update the relevant semantic plans and propagate the change.

```text
External source
↓
Connector
↓
Normalized source record/change
↓
Validation/deduplication
↓
Candidate / pending-review layer
↓
User review for new task-like canonical content
↓
State Store
↓
Planner
```

---

## 3. Calendar Integration

Preferred backend:
- Google Calendar

User-facing client may remain:
- Apple Calendar

Semantic capabilities required:
- read recurring events
- read one-off events
- detect updates/cancellations
- preserve source event IDs
- compute free/busy
- later write clearly identified flexible study blocks

Do not:
- treat every task deadline as a calendar event by definition
- overwrite external events without clear ownership

Deferred until actual Google Calendar integration:
- exact field mapping
- calendar/event IDs and ownership mapping
- sync token/cursor strategy
- push/watch behavior
- recurrence-instance edge cases
- n8n node-specific payload behavior

---

## 4. Email Integration

Pipeline:
```text
trigger/poll
↓
filter
↓
classify
↓
extract candidate facts
↓
map to course/domain
↓
deduplicate
↓
evidence confidence + recommended interpretation
↓
review queue for canonical personal Task changes
↓
user confirmation + authorized validation
↓
canonical state update + audit
```

Need from user later:
- relevant accounts
- important senders/domains
- examples of relevant mail
- categories to ignore
- acceptable automatic actions

Initial principle:
- read/extract before considering mailbox mutation such as archive/labels.

---

## 5. Learning-Platform Integration

Likely custom connector/scraper.

Connector must be isolated behind a normalized interface so planner code never depends on webpage structure.

Detect:
- new assignment
- deadline update
- announcement
- exam information
- file/material changes if relevant

Need:
- authentication approach
- page map
- polling frequency
- change detection
- anti-duplication
- failure handling

Do not start implementation before input/task contracts stabilize.

---

## 6. Source Precedence and Conflicts

Do not implement a single global precedence number prematurely.

Use contextual precedence.

Examples:
- User explicit correction can override inferred state.
- Learning platform is strong authority for published assignment deadline.
- Later instructor email may supersede an older platform deadline.
- Calendar provider is authority for whether its event exists.

When conflicting credible sources exist:
- preserve both source records
- mark state conflicted when material
- rules may select a recommended source interpretation automatically;
- ordinary external canonical Task-fact proposals still require review; D-072 permits only mapped creation triggered by an accepted generation relationship, and D-073 permits notified expiration under confirmed conditions;
- raw source/Calendar occupancy updates remain distinct from Task truth

Completion-specific rule:
- external evidence may suggest a task is complete;
- in v1, every external completion signal creates a pending confirmation, including strong submission evidence; no accepted auto-confirmation exception exists;
- normal user confirmation, usually in the evening review, changes canonical completion state.

New-task rule:
- even apparently clear assignment/task discoveries should enter as candidates first;
- morning/evening review confirms or corrects them before canonical task creation;
- raw source records may still be stored automatically.

Urgent-notification rule:
- integrations may deliver notifications, but feasibility/risk determination belongs to Planner/risk logic;
- connector code should not independently invent urgency.

---

## 7. Idempotency and Deduplication

Every connector should be safe to run repeatedly.

Use:
- external IDs
- content hashes
- update timestamps
- normalized dedup keys
- source-specific cursor/checkpoint where available

Goal:
Repeated polling must not create duplicate tasks.

---

## 8. Sync Strategy

Prefer:
- event-driven updates where reliable
- periodic reconciliation as safety net

Never assume push/webhook delivery is perfect.

Track:
- last successful sync
- source cursor/token
- last full reconciliation
- failures/retries

---

## 9. n8n Workflow Organization

Future recommendation:
- small composable workflows, not one enormous graph
- explicit input/output payloads
- shared error handling
- environment-specific credentials
- workflow version/export strategy

Potential workflow families:
- calendar_sync
- email_ingest
- learning_platform_sync
- daily_refresh
- daily_plan_trigger
- weekly_review_trigger
- reconciliation
- notifications

Exact naming/implementation deferred.

---

## 10. Dependencies

Depends on:
- DATA_MODEL_PLAN
- IO_CONTRACT_PLAN

Feeds:
- State store
- PLANNER_PLAN
- AI_EXECUTION_PLAN where extraction uses AI

Security impact:
- Always review SECURITY_PRIVACY_PLAN when adding a new external source or credential.

Testing impact:
- Add connector fixtures and replay tests in TESTING_PLAN.

---

## 11. Planning Dependencies and Safety Foundations

Email account/provider selection is open; Gmail is an example, not a requirement. Do not infer current accounts from old chat. Calendar's Google preference is accepted, but exact credentials/IDs/mapping are later integration facts.

From the first ingestion prototype, preserve candidates, provenance, deduplication, checkpoints, errors/staleness, and safe replay. Source deletion does not automatically cancel a canonical Task. A Calendar-owned event may refresh occupancy within configured sync scope without confirming a Task or inventing personal progress.

Phase 4 may use deterministic extraction, manual reviewed imports, or a narrowly validated optional extractor. Full AI Router deployment remains Phase 6. Collectors must remain useful when an extraction model is unavailable; uncertain content stays evidence/pending, and no safety boundary waits for the Router.

---

## 12. Relationship Events, Expiration Notices, and Time Defaults

Raw external discovery is not canonical Task creation and cannot trigger a relationship cascade. Once a source Task is accepted/created, application/domain logic emits the canonical event and evaluates explicitly accepted rules under TASK_RELATIONSHIP_PLAN. n8n may orchestrate those events/notifications; the connector does not invent rule scope, ordering, deadlines, or task completion.

Approved rules produce fully mapped canonical counterparts without redundant review, with provenance/idempotency; unresolved essential target fields go to the review queue. Completion signals from email/platform remain advisory even for rule-generated Tasks. Source deletion/cancellation does not silently propagate Task cancellation.

For a confirmed expiration condition: notify first, then record EXPIRED only after successful user-facing dispatch, latest-state validation, and deduplication. This is not a requirement to wait for a read receipt or extra acknowledgement. Failed notices remain pending/retryable; uncertain conditions require clarification. Exact delivery channel remains unselected.

Normalize date-only deadlines to 23:59 Asia/Shanghai while retaining source date/default provenance. Explicit timestamps/source zones are preserved and only converted for display. Server-timezone defaults must not affect user dates or next-midnight override expiry.

---

## Detailed Execution Mapping

One provider/account/layout per explicit task instance; common port/dedup/replay behavior is validated before live scoped evidence. No connector bypasses personal-state authority.
