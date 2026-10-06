# WhatToDo — Persistence foundation and safe command path

> Status: executable development specification; every task initially TODO. No task is implemented by this file.
> Task scope: one bounded AI execution per task or explicitly repeated instance.

[Development plan and execution rules](../DEVELOPMENT_PLAN.md) · [Live progress](../PROGRESS.md)

## Required sources

- [DATA_MODEL_PLAN.md](../DATA_MODEL_PLAN.md)
- [IO_CONTRACT_PLAN.md](../IO_CONTRACT_PLAN.md)
- [OPERATIONS_PLAN.md](../OPERATIONS_PLAN.md)
- [SECURITY_PRIVACY_PLAN.md](../SECURITY_PRIVACY_PLAN.md)

Read the source sections relevant to the chosen task, its completed prerequisite artifacts, and the shared Definition of Done before editing. Source documents control meaning; this catalog controls work decomposition. Proposed artifact paths below are logical scopes until M2-16 freezes the language-specific mapping. An adapter/schema described here does not yet exist.

## Gate: M3A-19

Task order is constrained by explicit dependencies, not by credentials for unrelated live integrations. A VERIFY task runs the smallest meaningful fixture/integration set for its boundary and records actual evidence. Repeated tasks are one course/family/account/layout/playbook per execution; a template dependency means the required instance set described in the development plan.

## Tasks

### M3A-01

**Create the chosen package skeleton**

- Type: `DEV`. Initial status: `TODO`.
- Prerequisites: [M2-18](M2_CONTRACTS.md#m2-18)
- Deliverable / bounded file scope: src/domain, application, ports; package manifest.
- Work: Implement only the chosen package/module layout, dependency lock and one domain value smoke check. Keep API/workflow/provider code out of the domain layer.
- Acceptance / failure and extension checks: Import boundaries are checked; clean install works with pinned dependencies; no optional model credential is required.
- Completion evidence: artifact paths + exact targeted command/check or user-source reference + observed result + remaining limitations, recorded in PROGRESS. Do not mark done from code presence alone.

### M3A-02

**Add deterministic clock and time primitives**

- Type: `DEV`. Initial status: `TODO`.
- Prerequisites: [M3A-01](M3_STATE_FOUNDATION.md#m3a-01)
- Deliverable / bounded file scope: Clock adapter and time-value module.
- Work: Implement UTC instants, explicit date-only values, Beijing-local arithmetic and injected clock; use schema-approved precision.
- Acceptance / failure and extension checks: Server locale cannot change today; month/year rollover and 23:59 default pass; explicit timestamps are preserved.
- Completion evidence: artifact paths + exact targeted command/check or user-source reference + observed result + remaining limitations, recorded in PROGRESS. Do not mark done from code presence alone.

### M3A-03

**Add layered non-secret configuration loading**

- Type: `DEV`. Initial status: `TODO`.
- Prerequisites: [M3A-01](M3_STATE_FOUNDATION.md#m3a-01)
- Deliverable / bounded file scope: config loader and .example configuration.
- Work: Load stable profile/rule versions and environment-secret references with startup validation. Document precedence and support a synthetic test config.
- Acceptance / failure and extension checks: Missing credentials for disabled optional adapters do not break core startup; malformed enabled configuration fails clearly; no secret value appears in errors.
- Completion evidence: artifact paths + exact targeted command/check or user-source reference + observed result + remaining limitations, recorded in PROGRESS. Do not mark done from code presence alone.

### M3A-04

**Add isolated PostgreSQL dev/test harness**

- Type: `DEV`. Initial status: `TODO`.
- Prerequisites: [M3A-01](M3_STATE_FOUNDATION.md#m3a-01) · [M3A-03](M3_STATE_FOUNDATION.md#m3a-03)
- Deliverable / bounded file scope: dev environment and test-db launcher.
- Work: Provide reproducible local DB setup, health readiness, disposable test databases and least-privilege application/test role separation.
- Acceptance / failure and extension checks: Integration tests target PostgreSQL, not SQLite substitutes; test cleanup cannot reach production; credentials stay outside tracked files.
- Completion evidence: artifact paths + exact targeted command/check or user-source reference + observed result + remaining limitations, recorded in PROGRESS. Do not mark done from code presence alone.

### M3A-05

**Implement migration runner and schema-version checks**

- Type: `DEV`. Initial status: `TODO`.
- Prerequisites: [M3A-04](M3_STATE_FOUNDATION.md#m3a-04)
- Deliverable / bounded file scope: migration runner and first metadata migration.
- Work: Implement ordered checksummed migrations and startup compatibility checks; document forward migration and restore-based recovery for non-reversible changes.
- Acceptance / failure and extension checks: A migration failure leaves an explicit recoverable state; rerun is safe; incompatible application/schema versions are blocked before mutation.
- Completion evidence: artifact paths + exact targeted command/check or user-source reference + observed result + remaining limitations, recorded in PROGRESS. Do not mark done from code presence alone.

### M3A-06

**Persist profiles, templates and versions**

- Type: `DEV`. Initial status: `TODO`.
- Prerequisites: [M3A-05](M3_STATE_FOUNDATION.md#m3a-05)
- Deliverable / bounded file scope: profile/template repositories and migration.
- Work: Persist references/cache for accepted declarative versions and immutable TaskType defaults; keep Git authoritative for stable definitions.
- Acceptance / failure and extension checks: A new default version never rewrites existing Tasks; unresolved profile IDs fail referential checks; fake/test profiles share the same format.
- Completion evidence: artifact paths + exact targeted command/check or user-source reference + observed result + remaining limitations, recorded in PROGRESS. Do not mark done from code presence alone.

### M3A-07

**Persist Task and stage aggregates**

- Type: `DEV`. Initial status: `TODO`.
- Prerequisites: [M3A-06](M3_STATE_FOUNDATION.md#m3a-06)
- Deliverable / bounded file scope: Task/stage repository and migration.
- Work: Implement only aggregate CRUD/query storage and distinct completion/disposition/trust dimensions; expose no bypass write API.
- Acceptance / failure and extension checks: Foreign keys and allowed values reject invalid aggregates; parent/stage ownership cannot point to unrelated obligations; unit and repository tests cover one round-trip.
- Completion evidence: artifact paths + exact targeted command/check or user-source reference + observed result + remaining limitations, recorded in PROGRESS. Do not mark done from code presence alone.

### M3A-08

**Persist evidence and pending confirmations**

- Type: `DEV`. Initial status: `TODO`.
- Prerequisites: [M3A-07](M3_STATE_FOUNDATION.md#m3a-07)
- Deliverable / bounded file scope: source/candidate repositories and migration.
- Work: Store immutable source versions, field provenance, conflicts and pending items with deduplication; accepted-state records remain separate.
- Acceptance / failure and extension checks: Repeated source observation does not duplicate identical candidates; pending evidence cannot alter canonical state; raw content can later be minimized without losing semantic history.
- Completion evidence: artifact paths + exact targeted command/check or user-source reference + observed result + remaining limitations, recorded in PROGRESS. Do not mark done from code presence alone.

### M3A-09

**Implement atomic audit and optimistic concurrency**

- Type: `DEV`. Initial status: `TODO`.
- Prerequisites: [M3A-07](M3_STATE_FOUNDATION.md#m3a-07)
- Deliverable / bounded file scope: transaction/audit/version module.
- Work: Commit authorized aggregate update and audit together; compare expected versions and roll back conflicting writes.
- Acceptance / failure and extension checks: Two writers on one version cannot both overwrite; failure after audit/state staging rolls both back; old expected-version errors are distinguishable from retryable transport failure.
- Completion evidence: artifact paths + exact targeted command/check or user-source reference + observed result + remaining limitations, recorded in PROGRESS. Do not mark done from code presence alone.

### M3A-10

**Implement command deduplication**

- Type: `DEV`. Initial status: `TODO`.
- Prerequisites: [M3A-09](M3_STATE_FOUNDATION.md#m3a-09)
- Deliverable / bounded file scope: command ledger and request fingerprint.
- Work: Record stable command IDs, request hashes and committed results inside the same transaction. Replays return original outcomes; changed payloads under the same ID fail.
- Acceptance / failure and extension checks: Concurrent/restarted duplicate commands mutate once; a timeout retry does not repeat completion or effort addition; dedup history survives process restart.
- Completion evidence: artifact paths + exact targeted command/check or user-source reference + observed result + remaining limitations, recorded in PROGRESS. Do not mark done from code presence alone.

### M3A-11

**Implement schema and authority validation pipeline**

- Type: `DEV`. Initial status: `TODO`.
- Prerequisites: [M3A-08](M3_STATE_FOUNDATION.md#m3a-08) · [M3A-10](M3_STATE_FOUNDATION.md#m3a-10)
- Deliverable / bounded file scope: command validation and authorization services.
- Work: Check schema, references, exact principal/rule scope, state version and authorized fields before handlers. External text and AI results remain proposals.
- Acceptance / failure and extension checks: A fake approval ID, unknown target or extra inferred field is rejected with no state/audit mutation; clear resolved user instructions are not prompted twice.
- Completion evidence: artifact paths + exact targeted command/check or user-source reference + observed result + remaining limitations, recorded in PROGRESS. Do not mark done from code presence alone.

### M3A-12

**Implement manual Task creation**

- Type: `DEV`. Initial status: `TODO`.
- Prerequisites: [M3A-11](M3_STATE_FOUNDATION.md#m3a-11)
- Deliverable / bounded file scope: create-Task handler.
- Work: Create one accepted Task from a resolved authorized user instruction, copying approved defaults with provenance and linking one canonical creation event.
- Acceptance / failure and extension checks: Retry yields the same Task; missing essential facts stay pending; source/template defaults alone cannot authorize the call.
- Completion evidence: artifact paths + exact targeted command/check or user-source reference + observed result + remaining limitations, recorded in PROGRESS. Do not mark done from code presence alone.

### M3A-13

**Implement one Task fact patch**

- Type: `DEV`. Initial status: `TODO`.
- Prerequisites: [M3A-12](M3_STATE_FOUNDATION.md#m3a-12)
- Deliverable / bounded file scope: update-Task handler.
- Work: Patch explicit deadline/importance/requiredness or effort facts via versioned allowlisted fields; preserve previous values and source authority.
- Acceptance / failure and extension checks: Unrelated fields are untouched; stale patch cannot overwrite a newer correction; explicit source time is not changed to date-only 23:59.
- Completion evidence: artifact paths + exact targeted command/check or user-source reference + observed result + remaining limitations, recorded in PROGRESS. Do not mark done from code presence alone.

### M3A-14

**Implement completion and cancellation handlers**

- Type: `DEV`. Initial status: `TODO`.
- Prerequisites: [M3A-13](M3_STATE_FOUNDATION.md#m3a-13)
- Deliverable / bounded file scope: completion/cancellation handlers.
- Work: Record user-confirmed COMPLETE with U=0, or distinct CANCELLED with history. Keep actual effort and disposition semantics separate.
- Acceptance / failure and extension checks: Submission evidence cannot call completion; cancelled work is not completed effort; repeated completion is harmless and retained history is not hard-deleted.
- Completion evidence: artifact paths + exact targeted command/check or user-source reference + observed result + remaining limitations, recorded in PROGRESS. Do not mark done from code presence alone.

### M3A-15

**Implement work-observation persistence**

- Type: `DEV`. Initial status: `TODO`.
- Prerequisites: [M3A-14](M3_STATE_FOUNDATION.md#m3a-14)
- Deliverable / bounded file scope: effort/session observation handler and migration.
- Work: Store reported cumulative/new actual effort with observation IDs and user U updates; do not fabricate unreported session timestamps.
- Acceptance / failure and extension checks: Duplicate reports do not add effort twice; planned blocks are never actual sessions; time spent alone cannot decrement U or complete a Task.
- Completion evidence: artifact paths + exact targeted command/check or user-source reference + observed result + remaining limitations, recorded in PROGRESS. Do not mark done from code presence alone.

### M3A-16

**Implement authenticated prototype command transport**

- Type: `DEV`. Initial status: `TODO`.
- Prerequisites: [M3A-11](M3_STATE_FOUNDATION.md#m3a-11) · [M2-15](M2_CONTRACTS.md#m2-15) · [M3A-22](M3_STATE_FOUNDATION.md#m3a-22)
- Deliverable / bounded file scope: prototype API/CLI adapter.
- Work: Expose existing handlers through the chosen authenticated prototype transport, with size limits, caller identity and typed errors; no direct arbitrary SQL or provider writes.
- Acceptance / failure and extension checks: Unauthenticated or wrong-scope writes fail before handlers; fixtures call the same contract as n8n; internal core remains transport-independent.
- Completion evidence: artifact paths + exact targeted command/check or user-source reference + observed result + remaining limitations, recorded in PROGRESS. Do not mark done from code presence alone.

### M3A-17

**Add basic read model and semantic history view**

- Type: `DEV`. Initial status: `TODO`.
- Prerequisites: [M3A-15](M3_STATE_FOUNDATION.md#m3a-15) · [M3A-16](M3_STATE_FOUNDATION.md#m3a-16)
- Deliverable / bounded file scope: Task/history query service.
- Work: Return active Tasks, pending items and retained outcomes with version/provenance, without presenting a simple list as a feasibility-verified Daily Brief.
- Acceptance / failure and extension checks: CANCELLED/EXPIRED/COMPLETE history is queryable; secret/raw evidence is excluded by default; query pagination is stable.
- Completion evidence: artifact paths + exact targeted command/check or user-source reference + observed result + remaining limitations, recorded in PROGRESS. Do not mark done from code presence alone.

### M3A-18

**Add minimal backup and restore probe**

- Type: `OPS`. Initial status: `TODO`.
- Prerequisites: [M3A-17](M3_STATE_FOUNDATION.md#m3a-17)
- Deliverable / bounded file scope: development backup/restore scripts and instructions.
- Work: Back up the synthetic prototype DB/config references and restore into a separate database; validate canonical state, audit and command ledger.
- Acceptance / failure and extension checks: Restore is actually exercised in test isolation; original DB is not overwritten; backup contains no source credential exports; corruption is detected.
- Completion evidence: artifact paths + exact targeted command/check or user-source reference + observed result + remaining limitations, recorded in PROGRESS. Do not mark done from code presence alone.

### M3A-19

**Close the persistence foundation gate**

- Type: `VERIFY`. Initial status: `TODO`.
- Prerequisites: [M3A-18](M3_STATE_FOUNDATION.md#m3a-18) · [M3A-20](M3_STATE_FOUNDATION.md#m3a-20) · [M3A-02](M3_STATE_FOUNDATION.md#m3a-02)
- Deliverable / bounded file scope: reports/acceptance/M3A.md.
- Work: Run a bounded create→patch→effort→complete journey plus stale-write, duplicate-command, unauthorized-write and restore scenarios.
- Acceptance / failure and extension checks: PostgreSQL evidence proves atomicity and replay behavior; no live connector/model is needed; smoke setup can be reproduced from a clean clone.
- Completion evidence: artifact paths + exact targeted command/check or user-source reference + observed result + remaining limitations, recorded in PROGRESS. Do not mark done from code presence alone.

### M3A-20

**Add isolated baseline CI checks**

- Type: `DEV`. Initial status: `TODO`.
- Prerequisites: [M3A-01](M3_STATE_FOUNDATION.md#m3a-01)
- Deliverable / bounded file scope: one CI workflow and targeted check entrypoint.
- Work: Run pinned install, domain/unit/contract/document checks with synthetic fixtures and isolated PostgreSQL where needed; publish redacted failure artifacts without live-provider secrets.
- Acceptance / failure and extension checks: A clean CI worker reproduces local targeted checks; no production credential is required; failed contract/secret/authority checks block the change and do not run deployment.
- Completion evidence: artifact paths + exact targeted command/check or user-source reference + observed result + remaining limitations, recorded in PROGRESS. Do not mark done from code presence alone.

### M3A-21

**Normalize one direct-user intent [repeat per command class]**

- Type: `DEV`. Initial status: `TODO`.
- Prerequisites: [M3A-11](M3_STATE_FOUNDATION.md#m3a-11) · [M2-15](M2_CONTRACTS.md#m2-15)
- Deliverable / bounded file scope: one direct-input parser/guided-input adapter.
- Work: Normalize one bounded natural-language or guided-input command class into the frozen proposal envelope; carry authenticated user context and preserve the exact statement. Start with deterministic supported phrases/guidance; uncertain text remains a clarification candidate without requiring the full AI Router.
- Acceptance / failure and extension checks: The user need not type JSON; obvious supported commands resolve naturally; unsupported/ambiguous phrases are not guessed or executed; external text cannot pretend to be the authenticated user.
- Completion evidence: artifact paths + exact targeted command/check or user-source reference + observed result + remaining limitations, recorded in PROGRESS. Do not mark done from code presence alone.

### M3A-22

**Resolve Task references and concise follow-up**

- Type: `DEV`. Initial status: `TODO`.
- Prerequisites: [M3A-21](M3_STATE_FOUNDATION.md#m3a-21) · [M3A-07](M3_STATE_FOUNDATION.md#m3a-07)
- Deliverable / bounded file scope: target-resolution and clarification service.
- Work: Resolve stable IDs or human names using current course/Task context; return explicit ambiguity/missing-field questions and resume the same versioned command after a clear user answer.
- Acceptance / failure and extension checks: Duplicate/similar Task names cannot mutate the wrong record; a confirmation reply is scoped to the listed proposal/version; resolved explicit commands do not ask an identical extra approval; human labels remain independent of provider IDs.
- Completion evidence: artifact paths + exact targeted command/check or user-source reference + observed result + remaining limitations, recorded in PROGRESS. Do not mark done from code presence alone.
