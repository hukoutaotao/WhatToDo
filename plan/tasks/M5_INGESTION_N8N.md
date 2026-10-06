# WhatToDo — External evidence ingestion and n8n automation

> Status: executable development specification; every task initially TODO. No task is implemented by this file.
> Task scope: one bounded AI execution per task or explicitly repeated instance.

[Development plan and execution rules](../DEVELOPMENT_PLAN.md) · [Live progress](../PROGRESS.md)

## Required sources

- [INTEGRATION_PLAN.md](../INTEGRATION_PLAN.md)
- [AI_EXECUTION_PLAN.md](../AI_EXECUTION_PLAN.md)
- [SECURITY_PRIVACY_PLAN.md](../SECURITY_PRIVACY_PLAN.md)
- [DATA_MODEL_PLAN.md](../DATA_MODEL_PLAN.md)

Read the source sections relevant to the chosen task, its completed prerequisite artifacts, and the shared Definition of Done before editing. Source documents control meaning; this catalog controls work decomposition. Proposed artifact paths below are logical scopes until M2-16 freezes the language-specific mapping. An adapter/schema described here does not yet exist.

## Gate: M5-21

Task order is constrained by explicit dependencies, not by credentials for unrelated live integrations. A VERIFY task runs the smallest meaningful fixture/integration set for its boundary and records actual evidence. Repeated tasks are one course/family/account/layout/playbook per execution; a template dependency means the required instance set described in the development plan.

## Tasks

### M5-01

**Define ingestion execution and checkpoint policy**

- Type: `SPEC`. Initial status: `TODO`.
- Prerequisites: [M3B-16](M3_RELATIONSHIPS_REVIEWS.md#m3b-16) · [M2-12](M2_CONTRACTS.md#m2-12)
- Deliverable / bounded file scope: ingestion run/checkpoint/error contract.
- Work: Define source scopes, observation identity, parser version, page acknowledgement and durable run state; separate transport retries from semantic replay.
- Acceptance / failure and extension checks: Checkpoint advances only for durably processed batches; source/provider changes do not remove accepted personal history; ingestion is usable without a model.
- Completion evidence: artifact paths + exact targeted command/check or user-source reference + observed result + remaining limitations, recorded in PROGRESS. Do not mark done from code presence alone.

### M5-02

**Implement common source ingestion service**

- Type: `DEV`. Initial status: `TODO`.
- Prerequisites: [M5-01](M5_INGESTION_N8N.md#m5-01)
- Deliverable / bounded file scope: source ingest application service.
- Work: Persist source versions and dedup observations through one authenticated entrypoint; reject malformed/oversized payloads with typed errors.
- Acceptance / failure and extension checks: Duplicate calls converge; partial failures preserve previous state; one new evidence adapter can reuse the service without new Task write permissions.
- Completion evidence: artifact paths + exact targeted command/check or user-source reference + observed result + remaining limitations, recorded in PROGRESS. Do not mark done from code presence alone.

### M5-03

**Implement parser registry and deterministic extractor**

- Type: `DEV`. Initial status: `TODO`.
- Prerequisites: [M5-02](M5_INGESTION_N8N.md#m5-02)
- Deliverable / bounded file scope: parser interface/registry and one synthetic extractor.
- Work: Create versioned deterministic candidate extraction from one controlled fixture shape; retain spans/references/confidence and unresolved course/Task targets.
- Acceptance / failure and extension checks: Malformed/ambiguous dates stay pending; extraction does not create canonical Tasks; switching parser versions retains source/candidate provenance.
- Completion evidence: artifact paths + exact targeted command/check or user-source reference + observed result + remaining limitations, recorded in PROGRESS. Do not mark done from code presence alone.

### M5-04

**Implement candidate merge and conflict detection**

- Type: `DEV`. Initial status: `TODO`.
- Prerequisites: [M5-03](M5_INGESTION_N8N.md#m5-03) · [M3A-08](M3_STATE_FOUNDATION.md#m3a-08)
- Deliverable / bounded file scope: candidate comparison/reconciliation module.
- Work: Merge identical observations, retain conflicting credible deadline meanings and produce concise review suggestions without confidence auto-acceptance.
- Acceptance / failure and extension checks: Source disagreement does not overwrite user correction; repeated polling does not multiply questions; source deletion remains evidence, not cancellation.
- Completion evidence: artifact paths + exact targeted command/check or user-source reference + observed result + remaining limitations, recorded in PROGRESS. Do not mark done from code presence alone.

### M5-05

**Confirm one email provider/account scope [repeat]**

- Type: `INFO`. Initial status: `TODO`.
- Prerequisites: [M5-01](M5_INGESTION_N8N.md#m5-01)
- Deliverable / bounded file scope: email source intake record.
- Work: Confirm actual account/provider, relevant folders/labels, read-only access and desired evidence categories. Do not treat Gmail as mandatory or assume remembered accounts are active.
- Acceptance / failure and extension checks: One adapter/account scope is explicit; mailbox mutation is not granted; required credential setup is deferred to the live adapter task.
- Completion evidence: artifact paths + exact targeted command/check or user-source reference + observed result + remaining limitations, recorded in PROGRESS. Do not mark done from code presence alone.

### M5-06

**Map one email provider [repeat per distinct provider]**

- Type: `SPEC`. Initial status: `TODO`.
- Prerequisites: [M5-05](M5_INGESTION_N8N.md#m5-05)
- Deliverable / bounded file scope: provider mapping ADR and fixtures.
- Work: Inspect current official provider docs for IDs, paging, threading/change semantics, auth and limits; bind only the approved read scope.
- Acceptance / failure and extension checks: Provider identifiers can be deduplicated across account scopes; reset/revocation behavior is defined; no API fields are guessed from a different provider.
- Completion evidence: artifact paths + exact targeted command/check or user-source reference + observed result + remaining limitations, recorded in PROGRESS. Do not mark done from code presence alone.

### M5-07

**Implement one email read adapter [repeat]**

- Type: `DEV`. Initial status: `TODO`.
- Prerequisites: [M5-06](M5_INGESTION_N8N.md#m5-06) · [M5-02](M5_INGESTION_N8N.md#m5-02)
- Deliverable / bounded file scope: one EvidenceSource email adapter.
- Work: Implement read/page/normalize and bounded sync for one provider; share auth/config per account without cloning domain behavior.
- Acceptance / failure and extension checks: Transport failure/rate limit is typed; credentials/bodies are redacted; adapter returns source evidence only and conforms to shared fake tests.
- Completion evidence: artifact paths + exact targeted command/check or user-source reference + observed result + remaining limitations, recorded in PROGRESS. Do not mark done from code presence alone.

### M5-08

**Implement email checkpoint recovery**

- Type: `DEV`. Initial status: `TODO`.
- Prerequisites: [M5-07](M5_INGESTION_N8N.md#m5-07)
- Deliverable / bounded file scope: email checkpoint/resync service.
- Work: Apply durable page acknowledgement, observation identity and source freshness per account; recover invalid cursors with bounded resync.
- Acceptance / failure and extension checks: Crash/restart and repeated messages create neither duplicate source facts nor canonical changes; partial sync cannot appear fully healthy.
- Completion evidence: artifact paths + exact targeted command/check or user-source reference + observed result + remaining limitations, recorded in PROGRESS. Do not mark done from code presence alone.

### M5-09

**Create one n8n email ingestion workflow [repeat]**

- Type: `DEV`. Initial status: `TODO`.
- Prerequisites: [M5-08](M5_INGESTION_N8N.md#m5-08) · [M3A-16](M3_STATE_FOUNDATION.md#m3a-16)
- Deliverable / bounded file scope: versioned disabled/test email workflow export.
- Work: Wire the selected account adapter into common ingestion with scoped schedule and error workflow; export reusable non-secret configuration.
- Acceptance / failure and extension checks: A second account reuses the workflow template; overlapping runs are idempotent; disabled imports cannot poll production accidentally.
- Completion evidence: artifact paths + exact targeted command/check or user-source reference + observed result + remaining limitations, recorded in PROGRESS. Do not mark done from code presence alone.

### M5-10

**Confirm one learning-platform scope**

- Type: `INFO`. Initial status: `TODO`.
- Prerequisites: [M5-01](M5_INGESTION_N8N.md#m5-01)
- Deliverable / bounded file scope: learning platform/pages/access intake.
- Work: Confirm actual platform, required pages/data categories and allowed access method; inspect a representative page with authorized read scope.
- Acceptance / failure and extension checks: Scope and missing login/access facts are explicit; no scraping method, selector or account identity is invented.
- Completion evidence: artifact paths + exact targeted command/check or user-source reference + observed result + remaining limitations, recorded in PROGRESS. Do not mark done from code presence alone.

### M5-11

**Map platform extraction and change evidence**

- Type: `SPEC`. Initial status: `TODO`.
- Prerequisites: [M5-10](M5_INGESTION_N8N.md#m5-10)
- Deliverable / bounded file scope: platform mapping ADR and sanitized snapshots.
- Work: Prefer available supported API/export; otherwise define one bounded HTML read/parser mapping with stable IDs, login-wall detection and selector-change diagnostics.
- Acceptance / failure and extension checks: Login/error pages cannot become an empty successful feed; snapshot fixtures are redacted; external prompt text is data, never executable instructions.
- Completion evidence: artifact paths + exact targeted command/check or user-source reference + observed result + remaining limitations, recorded in PROGRESS. Do not mark done from code presence alone.

### M5-12

**Implement one platform fetch adapter**

- Type: `DEV`. Initial status: `TODO`.
- Prerequisites: [M5-11](M5_INGESTION_N8N.md#m5-11) · [M5-02](M5_INGESTION_N8N.md#m5-02)
- Deliverable / bounded file scope: one EvidenceSource platform adapter.
- Work: Fetch one approved page/API scope with credential injection, request bounds and durable source observations; keep parsing separated.
- Acceptance / failure and extension checks: Auth failure, layout failure and retryable timeout are distinguishable; previously trusted evidence is retained; no completion shortcut is introduced.
- Completion evidence: artifact paths + exact targeted command/check or user-source reference + observed result + remaining limitations, recorded in PROGRESS. Do not mark done from code presence alone.

### M5-13

**Implement one platform parser [repeat per layout]**

- Type: `DEV`. Initial status: `TODO`.
- Prerequisites: [M5-12](M5_INGESTION_N8N.md#m5-12) · [M5-03](M5_INGESTION_N8N.md#m5-03)
- Deliverable / bounded file scope: versioned platform parser and fixture set.
- Work: Extract one stable task/announcement layout into candidates with source spans and exact published times. New unrelated layouts get separate task instances.
- Acceptance / failure and extension checks: Missing/changed selectors fail visibly; ambiguous timezone/assignment identity stays pending; one page cannot silently overwrite canonical deadlines.
- Completion evidence: artifact paths + exact targeted command/check or user-source reference + observed result + remaining limitations, recorded in PROGRESS. Do not mark done from code presence alone.

### M5-14

**Create platform n8n sync/error workflow**

- Type: `DEV`. Initial status: `TODO`.
- Prerequisites: [M5-13](M5_INGESTION_N8N.md#m5-13) · [M3A-16](M3_STATE_FOUNDATION.md#m3a-16)
- Deliverable / bounded file scope: versioned disabled/test platform workflow export.
- Work: Orchestrate bounded fetch/ingest/checkpoint runs and surface permanent auth/layout failures without infinite retries.
- Acceptance / failure and extension checks: Restart/schedule overlap deduplicates; failure state remains visible; restoring workflow export does not require embedded cookies.
- Completion evidence: artifact paths + exact targeted command/check or user-source reference + observed result + remaining limitations, recorded in PROGRESS. Do not mark done from code presence alone.

### M5-15

**Implement source health and reconciliation summary**

- Type: `DEV`. Initial status: `TODO`.
- Prerequisites: [M5-04](M5_INGESTION_N8N.md#m5-04) · [M5-09](M5_INGESTION_N8N.md#m5-09) · [M5-14](M5_INGESTION_N8N.md#m5-14)
- Deliverable / bounded file scope: source health query and review summary.
- Work: Combine evidence freshness, conflicts and pending questions without confusing connector success with user-confirmed truth.
- Acceptance / failure and extension checks: Every unresolved item remains available in full queue; stale source is labeled; state corrections route through existing commands, not connector SQL.
- Completion evidence: artifact paths + exact targeted command/check or user-source reference + observed result + remaining limitations, recorded in PROGRESS. Do not mark done from code presence alone.

### M5-16

**Add retry, quarantine and replay tools**

- Type: `DEV`. Initial status: `TODO`.
- Prerequisites: [M5-15](M5_INGESTION_N8N.md#m5-15)
- Deliverable / bounded file scope: bounded ingestion retry/quarantine/replay commands.
- Work: Retry transient failures with capped backoff; quarantine permanent malformed/layout failures and replay selected observations via original idempotency keys.
- Acceptance / failure and extension checks: Unknown delivery/write outcomes are not blindly repeated; replay cannot bypass authority or delete old history; poison pages do not block unrelated sources forever.
- Completion evidence: artifact paths + exact targeted command/check or user-source reference + observed result + remaining limitations, recorded in PROGRESS. Do not mark done from code presence alone.

### M5-17

**Run ingestion crash and malicious-content tests**

- Type: `VERIFY`. Initial status: `TODO`.
- Prerequisites: [M5-16](M5_INGESTION_N8N.md#m5-16)
- Deliverable / bounded file scope: source pipeline fault/security fixtures.
- Work: Inject crash after persist/before checkpoint, duplicate notifications, conflicting sources, login walls, prompt-injection text and source deletions.
- Acceptance / failure and extension checks: No skipped durable batch, false sync health, unauthorized Task mutation or secret leak; new parser/provider passes the common contract suite.
- Completion evidence: artifact paths + exact targeted command/check or user-source reference + observed result + remaining limitations, recorded in PROGRESS. Do not mark done from code presence alone.

### M5-18

**Validate one live email scope [repeat]**

- Type: `VERIFY`. Initial status: `TODO`.
- Prerequisites: [M5-17](M5_INGESTION_N8N.md#m5-17)
- Deliverable / bounded file scope: reports/acceptance/M5-email_<scope>.md.
- Work: Run a read-only finite scoped sync and compare redacted source/candidate results with actual provider records; avoid sending email or modifying the mailbox.
- Acceptance / failure and extension checks: Live credential/provider evidence is separate from fixture results; unavailable access is BLOCKED_USER; false-positive extraction remains reviewable.
- Completion evidence: artifact paths + exact targeted command/check or user-source reference + observed result + remaining limitations, recorded in PROGRESS. Do not mark done from code presence alone.

### M5-19

**Validate one live platform scope**

- Type: `VERIFY`. Initial status: `TODO`.
- Prerequisites: [M5-17](M5_INGESTION_N8N.md#m5-17)
- Deliverable / bounded file scope: reports/acceptance/M5-platform.md.
- Work: Read the approved finite platform scope and verify IDs, published deadlines, paging and changed-page behavior using redacted evidence.
- Acceptance / failure and extension checks: No fake evidence is presented as a live test; login/selector changes are detected; credentials never enter repository fixtures.
- Completion evidence: artifact paths + exact targeted command/check or user-source reference + observed result + remaining limitations, recorded in PROGRESS. Do not mark done from code presence alone.

### M5-20

**Close ingestion contract and offline replay gate**

- Type: `VERIFY`. Initial status: `TODO`.
- Prerequisites: [M5-17](M5_INGESTION_N8N.md#m5-17)
- Deliverable / bounded file scope: reports/acceptance/M5-offline.md.
- Work: Verify common ingest/parser/replay/source-health contracts and synthetic email/platform journeys; identify separate missing live-adapter instances.
- Acceptance / failure and extension checks: Deterministic Planner work can proceed against passed fixtures; this gate does not declare live automation or account access complete.
- Completion evidence: artifact paths + exact targeted command/check or user-source reference + observed result + remaining limitations, recorded in PROGRESS. Do not mark done from code presence alone.

### M5-21

**Close live ingestion production gate**

- Type: `VERIFY`. Initial status: `TODO`.
- Prerequisites: [M5-18](M5_INGESTION_N8N.md#m5-18) · [M5-19](M5_INGESTION_N8N.md#m5-19) · [M5-20](M5_INGESTION_N8N.md#m5-20)
- Deliverable / bounded file scope: reports/acceptance/M5-live.md.
- Work: Require live evidence for every enabled actual account/platform scope plus workflow import/replay health; explicitly disable unready optional adapters.
- Acceptance / failure and extension checks: A configured production source has tested permissions, freshness and failure handling; missing optional provider cannot silently report success.
- Completion evidence: artifact paths + exact targeted command/check or user-source reference + observed result + remaining limitations, recorded in PROGRESS. Do not mark done from code presence alone.
