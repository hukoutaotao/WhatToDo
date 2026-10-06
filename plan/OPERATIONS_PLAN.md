# WhatToDo — Operations and Deployment Plan

## 1. Target Topology

```text
GitHub
├── source
├── plans
├── versioned config
└── workflows/config exports where appropriate

Local development
├── VS Code
├── Codex
└── tests

Always-on runtime
├── n8n
├── PostgreSQL
├── planner/application service
├── connectors
└── scheduled jobs
```

Final operation must not require the user's laptop to remain powered on.

---

## 2. Environments

Plan for at least:
- development
- production

Potential later:
- test/staging

Keep:
- credentials separate
- database data separate
- external webhook URLs separate
- destructive testing out of production

---

## 3. Configuration

Version control:
- non-secret configuration
- schemas
- rules
- workflow definitions where safe
- migrations

Never commit:
- passwords
- OAuth refresh tokens
- API keys
- session cookies
- private raw personal data unless intentionally designed and protected

Use environment variables/secret stores for credentials.

---

## 4. Deployment Timing

Do not select a cloud/VPS vendor yet.

Selection should happen when Phase 2/3 makes runtime requirements clearer:
- CPU/RAM
- persistent storage
- outbound network
- HTTPS/domain
- backup requirements
- location/latency
- cost

---

## 5. PostgreSQL Operations

Future requirements:
- migrations
- backups
- restore test
- connection security
- least-privilege application role
- retention for audit/source data
- indexes only after query patterns become clear

A backup that has never been restored is not considered fully verified.

---

## 6. n8n Operations

Future requirements:
- persistent n8n state
- credential storage
- workflow export/version discipline
- execution logs
- retry/error workflows
- disabled/test workflows separated from production
- clear naming

Avoid manually editing production-only workflows without reflecting important changes in repository-backed documentation/export.

---

## 7. Observability

Minimum future signals:
- last successful connector sync
- failed workflows
- planner generation failure
- stale source
- database health
- daily plan generated/not generated
- reconciliation status
- pending user-confirmation backlog
- deadline feasibility/risk alerts
- missed-user-update reminder state
- consecutive days without normal user interaction

Prefer actionable logs over verbose raw dumps.

---

## 8. Failure Behavior

System should fail safely.

Examples:
- Calendar unavailable → do not pretend free/busy is current.
- Learning platform fails → mark source stale; preserve prior state.
- AI provider fails → fall back or defer; do not corrupt state.
- Database unavailable → stop mutations and surface failure.
- n8n workflow partially fails → retry idempotently.

Risk-state inequalities, the one-hour/day reserve, and the two-day inactivity trigger are accepted. Delivery channels, alert repeat suppression/escalation, and numerical rounding remain deferred; D-078 fixes natural-day windows, and elapsed time must not be counted as usable capacity. Operations must support proactive risk alerts and missing-update reminders.

Current semantic reminder rule:
- after two consecutive days without a normal user interaction, proactively request a state update/reconciliation.

---

## 9. Backup / Recovery

Future recovery plan must cover:
- PostgreSQL
- versioned declarative memory
- n8n workflows/config
- secrets recovery process
- deployment config

GitHub already provides version history for repository-tracked content but is not a substitute for database backup.

---

## 10. Dependencies

Affected by:
- DECISIONS
- DATA_MODEL_PLAN
- INTEGRATION_PLAN
- AI_EXECUTION_PLAN
- SECURITY_PRIVACY_PLAN

Do not finalize deployment vendor before requirements are known.

---

## 11. Runtime Time and State Safety

The accepted planning timezone is Asia/Shanghai (Beijing time). Normal-interaction day tracking, next-local-midnight override expiry, and daily dates use it, not server locale. Date-only deadlines default to local 23:59; supplied explicit times remain intact. D-078 fixes natural-day forecast windows including today, ending today / today+2 / today+6 at local 23:59. Recompute the anchor date and all windows at Beijing midnight; intraday recalculation counts only remaining usable time. Provider edge fixtures and numerical precision are later implementation work.

Treat pending review, source sync health, and last trusted state as different observability dimensions. A connector success does not prove user reconciliation succeeded. A partial evening response must not be recorded as a fully completed review while required fields remain missing; D-077 permits explicit bulk confirmation of untouched unchanged estimates; missing or uncovered facts still keep review incomplete.

Minimum backup/audit/state-version/staleness/confirmation protection begins with persistent-state prototypes, and safe replay begins with the first connector. Phase 7 extends resilience; it cannot be the first time these protections exist.

---

## 12. Relationship and Expiration Runtime Processes

Observe accepted generation rule versions, canonical source events, deduplication/occurrence keys, cascade failures, graph conflicts, and pending target facts. Persist source creation/outbox and generation audit so retry/restart cannot create multiple counterparts or turn unaccepted evidence into a trigger. Rule changes do not automatically regenerate historical counterparts.

Notify-before-record expiration requires explicit process state: detected confirmed condition → dispatch user-facing notice → revalidate current Task/version/condition → commit EXPIRED/history. “Informed” means successful dispatch through the chosen user-facing channel, not merely writing a log/unsent queue item; no read receipt/acknowledgement is required. Failed dispatch stays pending/retryable. Record notification and transition IDs to avoid duplicate notices/writes and audit any state change between them.

Runtime, channel, service code, and workflows do not yet exist. Preserve stale-state handling and safe fallback while model predictions or notification services are unavailable.
