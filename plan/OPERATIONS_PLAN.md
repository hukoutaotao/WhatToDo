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

Notification channels and exact thresholds are deferred, but operations must support proactive alerts for deadline-feasibility risk and prolonged missing user updates.

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
