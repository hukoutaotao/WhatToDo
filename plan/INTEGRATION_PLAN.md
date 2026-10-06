# WhatToDo — Integration and n8n Plan

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

```text
External source
↓
Connector
↓
Normalized source record/change
↓
Validation/deduplication
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

Required capabilities:
- read recurring events
- read one-off events
- detect updates/cancellations
- preserve source event IDs
- compute free/busy
- later write clearly identified flexible study blocks

Do not:
- treat every task deadline as a calendar event by definition
- overwrite external events without clear ownership

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
confidence/trust handling
↓
state update or review queue
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
- resolve automatically only with a defined rule
- otherwise ask the user

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
