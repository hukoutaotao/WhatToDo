# WhatToDo — Security and Privacy Plan

> Execution: [detailed development plan](DEVELOPMENT_PLAN.md) · [live progress](PROGRESS.md).
> Bounded work: [M3_STATE_FOUNDATION](tasks/M3_STATE_FOUNDATION.md) · [M5_INGESTION_N8N](tasks/M5_INGESTION_N8N.md) · [M7_OPTIONAL_AI](tasks/M7_OPTIONAL_AI.md) · [M8_LEARNING_RELEASE_OPERATIONS](tasks/M8_LEARNING_RELEASE_OPERATIONS.md).

## 1. Scope

WhatToDo may process highly personal operational data:
- schedule
- course obligations
- email content/metadata
- task history
- routines
- goals
- potentially learning-platform account data

Security is a cross-cutting requirement, not a final polish step.

---

## 2. Data-Minimization Principles

Collect only what serves planning.

Prefer:
- structured extracted facts over indefinite retention of full raw content when raw retention is unnecessary
- source references/hashes where sufficient
- limited context sent to AI providers

Do not replicate all email/calendar data into WhatToDo without a clear need.

---

## 3. Credential Rules

Never commit:
- passwords
- API keys
- OAuth refresh tokens
- cookies/session tokens
- database passwords

Use:
- n8n credential storage
- environment variables
- provider OAuth
- server secret management as appropriate

---

## 4. Least Privilege

Connectors should request only needed permissions.

Examples:
- read-only email first unless mailbox mutation is explicitly required
- calendar read before write if write is not yet needed
- learning-platform credentials should not be exposed to model prompts

---

## 5. AI Provider Exposure

Before sending data to any external model:
- identify job purpose
- minimize context
- omit secrets
- omit irrelevant personal information
- record provider/model for automated jobs where practical

Do not send raw authentication material to models.

---

## 6. Logs

Logs must not casually dump:
- full email bodies
- tokens
- passwords
- session cookies
- database credentials

Prefer IDs, error codes, and redacted summaries.

---

## 7. Repository Privacy

Before placing personal profiles/data into Git:
- confirm whether repository visibility and content are appropriate
- separate reusable schema/config from sensitive live personal state where possible

Dynamic personal state belongs in database rather than Git by default.

---

## 8. Deletion and Retention

Exact retention policy is deferred, but design should support:
- deleting source records when appropriate
- expiring unnecessary raw content
- retaining enough audit metadata to explain material state changes

Do not design irreversible accumulation by accident.

---

## 9. Threats to Consider Later

- leaked credentials
- compromised n8n
- overly broad OAuth scopes
- malicious/untrusted email or webpage text causing prompt injection
- connector replay/duplicate actions
- AI-generated unsafe mutations
- accidental publication of personal data
- stale auth/session handling

External content must be treated as data, not trusted instructions to the AI/system.

---

## 10. Change Trigger

Any new connector, external AI provider, write permission, or new category of personal data requires reviewing this file.

---

## 11. Canonical History vs Raw-Content Retention

D-069 preserves normal Task outcomes (COMPLETE/CANCELLED/EXPIRED), rework, estimate history, and material transitions. This does not require indefinite storage of full raw emails/pages, secrets, or unnecessary personal content. Source references/hashes/redacted evidence may be sufficient; exact retention/access rules remain deferred.

Deleting external content must not silently delete/cancel the accepted Task. Explicit privacy removal, erroneous-record correction, or duplicate merge can legitimately remove records with appropriate handling; ordinary finished/expired/cancelled history is not routine garbage to purge.

Confirmation evidence and field-level write authority must accompany validation. Repository-backed profiles follow accepted D-005 while sensitive live state stays in PostgreSQL. This audit does not move private data to a new service or change repository visibility.

---

## 12. Follow-Up Automation Boundaries

Accepted RelationshipRule scope is the authorization for mapped counterpart creation; it is not a general write grant to connectors/models. Keep the approving user statement, rule/version, source occurrence, target mapping, and field provenance in audit. Relationship commands still obey least privilege and input-as-data handling; external prompt text cannot approve rules.

Expiration notice content should disclose only relevant task/condition information. Inform before recording under D-073, retain semantic Task history, and never report a delivery/read acknowledgement that did not occur. Batch estimate confirmation preserves scoped per-Task provenance, not invented personal progress. Model-first allocation leaves canonical user estimates intact; retention/minimization rules continue to apply.

---

## Detailed Execution Mapping

Authority/access/redaction start in M3 and every adapter; M8-18–19 verify retention/privacy and release artifacts without deleting normal semantic history.
