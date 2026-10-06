# WhatToDo — Replaceable optional AI and manual premium jobs

> Status: executable development specification; every task initially TODO. No task is implemented by this file.
> Task scope: one bounded AI execution per task or explicitly repeated instance.

[Development plan and execution rules](../DEVELOPMENT_PLAN.md) · [Live progress](../PROGRESS.md)

## Required sources

- [AI_EXECUTION_PLAN.md](../AI_EXECUTION_PLAN.md)
- [IO_CONTRACT_PLAN.md](../IO_CONTRACT_PLAN.md)
- [SECURITY_PRIVACY_PLAN.md](../SECURITY_PRIVACY_PLAN.md)
- [LEARNING_PLAN.md](../LEARNING_PLAN.md)

Read the source sections relevant to the chosen task, its completed prerequisite artifacts, and the shared Definition of Done before editing. Source documents control meaning; this catalog controls work decomposition. Proposed artifact paths below are logical scopes until M2-16 freezes the language-specific mapping. An adapter/schema described here does not yet exist.

## Gate: M7-15

Task order is constrained by explicit dependencies, not by credentials for unrelated live integrations. A VERIFY task runs the smallest meaningful fixture/integration set for its boundary and records actual evidence. Repeated tasks are one course/family/account/layout/playbook per execution; a template dependency means the required instance set described in the development plan.

## Tasks

### M7-01

**Confirm automated AI scope and cost limits**

- Type: `INFO`. Initial status: `TODO`.
- Prerequisites: [M6-26](M6_PLANNER_DAILY_MVP.md#m6-26)
- Deliverable / bounded file scope: AI provider/budget/scope intake.
- Work: Resolve acceptable automated model provider/account, job categories, latency/cost caps and manual premium escalation. Plus is not API credit.
- Acceptance / failure and extension checks: Missing budget/provider blocks only automated AI tasks; deterministic MVP remains usable; no ChatGPT web automation is authorized.
- Completion evidence: artifact paths + exact targeted command/check or user-source reference + observed result + remaining limitations, recorded in PROGRESS. Do not mark done from code presence alone.

### M7-02

**Map one provider adapter and cost metadata**

- Type: `SPEC`. Initial status: `TODO`.
- Prerequisites: [M7-01](M7_OPTIONAL_AI.md#m7-01) · [M2-11](M2_CONTRACTS.md#m2-11)
- Deliverable / bounded file scope: AI adapter ADR and fake responses.
- Work: Check current primary docs for selected provider API/schema/cost reporting; define timeout/rate/auth/error behavior behind a provider-neutral port.
- Acceptance / failure and extension checks: No provider-specific field leaks into Task core; unknown cost is distinguished from zero; context export excludes secrets.
- Completion evidence: artifact paths + exact targeted command/check or user-source reference + observed result + remaining limitations, recorded in PROGRESS. Do not mark done from code presence alone.

### M7-03

**Implement AIJob persistence and lifecycle**

- Type: `DEV`. Initial status: `TODO`.
- Prerequisites: [M3A-19](M3_STATE_FOUNDATION.md#m3a-19) · [M2-11](M2_CONTRACTS.md#m2-11)
- Deliverable / bounded file scope: AIJob repository/migration.
- Work: Persist job identity, context/schema versions, manual/automatic executor class and validated/rejected/cancelled result history.
- Acceptance / failure and extension checks: Restart/repeated result imports do not duplicate jobs or state writes; cancelled jobs cannot apply stale proposals.
- Completion evidence: artifact paths + exact targeted command/check or user-source reference + observed result + remaining limitations, recorded in PROGRESS. Do not mark done from code presence alone.

### M7-04

**Implement minimized context builder**

- Type: `DEV`. Initial status: `TODO`.
- Prerequisites: [M7-03](M7_OPTIONAL_AI.md#m7-03)
- Deliverable / bounded file scope: AI job context builder.
- Work: Export only job-relevant redacted context with snapshot/target versions and output schema; clearly delimit external source text as data.
- Acceptance / failure and extension checks: Credentials/raw unrelated personal history are absent; unknown facts remain unknown; malicious source instructions cannot become system instructions or approval.
- Completion evidence: artifact paths + exact targeted command/check or user-source reference + observed result + remaining limitations, recorded in PROGRESS. Do not mark done from code presence alone.

### M7-05

**Implement one automated provider adapter**

- Type: `DEV`. Initial status: `TODO`.
- Prerequisites: [M7-02](M7_OPTIONAL_AI.md#m7-02) · [M7-04](M7_OPTIONAL_AI.md#m7-04)
- Deliverable / bounded file scope: one model provider adapter.
- Work: Call only selected allowed job classes with request bounds, secret injection and typed result/cost metadata.
- Acceptance / failure and extension checks: 429/auth/timeout/malformed payload remain safe failures; adapter can be swapped through registration; no direct DB mutation is possible.
- Completion evidence: artifact paths + exact targeted command/check or user-source reference + observed result + remaining limitations, recorded in PROGRESS. Do not mark done from code presence alone.

### M7-06

**Implement routing, budget and failure fallback**

- Type: `DEV`. Initial status: `TODO`.
- Prerequisites: [M7-05](M7_OPTIONAL_AI.md#m7-05)
- Deliverable / bounded file scope: AI Router policy module.
- Work: Prefer deterministic work, enforce caps and bounded retry, optionally escalate to manual job; retain useful deterministic extraction/planning on provider failure.
- Acceptance / failure and extension checks: Budget exhaustion cannot block a basic plan; repeated failed calls cannot exceed configured bound; routes are configuration-driven rather than course-specific.
- Completion evidence: artifact paths + exact targeted command/check or user-source reference + observed result + remaining limitations, recorded in PROGRESS. Do not mark done from code presence alone.

### M7-07

**Implement schema and adversarial result validation**

- Type: `DEV`. Initial status: `TODO`.
- Prerequisites: [M7-06](M7_OPTIONAL_AI.md#m7-06) · [M3A-11](M3_STATE_FOUNDATION.md#m3a-11)
- Deliverable / bounded file scope: AI proposal validator extension.
- Work: Validate schema, IDs, exact allowed fields, numeric/time ranges, provenance and snapshot versions before existing authorization handlers.
- Acceptance / failure and extension checks: Valid JSON/confidence cannot grant authority; invented IDs, stale results and extra preference/completion changes are rejected without mutation.
- Completion evidence: artifact paths + exact targeted command/check or user-source reference + observed result + remaining limitations, recorded in PROGRESS. Do not mark done from code presence alone.

### M7-08

**Implement one extraction-assisted candidate job**

- Type: `DEV`. Initial status: `TODO`.
- Prerequisites: [M7-07](M7_OPTIONAL_AI.md#m7-07) · [M5-03](M5_INGESTION_N8N.md#m5-03)
- Deliverable / bounded file scope: optional extraction job type.
- Work: Add one low-cost email/platform extraction class that returns candidates through the common parser/candidate contract, not canonical writes.
- Acceptance / failure and extension checks: Model unavailable/malformed leaves evidence usable; no high-confidence auto-acceptance; same task class can run via another conforming provider.
- Completion evidence: artifact paths + exact targeted command/check or user-source reference + observed result + remaining limitations, recorded in PROGRESS. Do not mark done from code presence alone.

### M7-09

**Implement one decomposition suggestion job**

- Type: `DEV`. Initial status: `TODO`.
- Prerequisites: [M7-07](M7_OPTIONAL_AI.md#m7-07) · [M1B-03](M1B_TASKTYPE_PRESETS.md#m1b-03)
- Deliverable / bounded file scope: optional decomposition proposal job.
- Work: Suggest a bounded TaskType/stage refinement using reviewed context and required output contract; keep defaults/config changes pending until authorized.
- Acceptance / failure and extension checks: Suggested decomposition cannot double workload or silently rewrite old templates; rejection retains prior accepted preset.
- Completion evidence: artifact paths + exact targeted command/check or user-source reference + observed result + remaining limitations, recorded in PROGRESS. Do not mark done from code presence alone.

### M7-10

**Implement manual premium-job export**

- Type: `DEV`. Initial status: `TODO`.
- Prerequisites: [M7-04](M7_OPTIONAL_AI.md#m7-04) · [M7-03](M7_OPTIONAL_AI.md#m7-03)
- Deliverable / bounded file scope: manual job export package.
- Work: Produce user-triggered Work/Codex context, prompt and expected result schema with no unattended UI/API dependency.
- Acceptance / failure and extension checks: Export retains job/snapshot IDs and minimal context; no Plus billing bypass or browser automation; one job is bounded and reviewable.
- Completion evidence: artifact paths + exact targeted command/check or user-source reference + observed result + remaining limitations, recorded in PROGRESS. Do not mark done from code presence alone.

### M7-11

**Implement manual result import**

- Type: `DEV`. Initial status: `TODO`.
- Prerequisites: [M7-10](M7_OPTIONAL_AI.md#m7-10) · [M7-07](M7_OPTIONAL_AI.md#m7-07)
- Deliverable / bounded file scope: manual result import/review adapter.
- Work: Accept one structured result against job/schema/snapshot versions and route accepted proposal fields through existing handlers.
- Acceptance / failure and extension checks: Repeated imports apply once; expired context/unknown IDs remain rejected/pending; user confirmation is not fabricated from model prose.
- Completion evidence: artifact paths + exact targeted command/check or user-source reference + observed result + remaining limitations, recorded in PROGRESS. Do not mark done from code presence alone.

### M7-12

**Implement one optional strategic suggestion job**

- Type: `DEV`. Initial status: `TODO`.
- Prerequisites: [M7-09](M7_OPTIONAL_AI.md#m7-09) · [M7-11](M7_OPTIONAL_AI.md#m7-11)
- Deliverable / bounded file scope: strategic proposal job type.
- Work: Provide a replaceable suggestion for multi-week/course/Goal strategy; require explicit policy approval and deterministic feasibility recalculation.
- Acceptance / failure and extension checks: Suggestion cannot override hard required feasibility or silently adopt behavioral policy; failure leaves M6 output available.
- Completion evidence: artifact paths + exact targeted command/check or user-source reference + observed result + remaining limitations, recorded in PROGRESS. Do not mark done from code presence alone.

### M7-13

**Add AI latency/cost/quality telemetry**

- Type: `DEV`. Initial status: `TODO`.
- Prerequisites: [M7-08](M7_OPTIONAL_AI.md#m7-08) · [M7-12](M7_OPTIONAL_AI.md#m7-12)
- Deliverable / bounded file scope: redacted AI telemetry/read model.
- Work: Record provider/model/job class, measured latency, known/unknown cost and validation outcome; relate usefulness to accepted/rejected proposals.
- Acceptance / failure and extension checks: Metrics exclude raw prompts/secrets; provider change preserves comparable job-class records; model spend is auditable and bounded.
- Completion evidence: artifact paths + exact targeted command/check or user-source reference + observed result + remaining limitations, recorded in PROGRESS. Do not mark done from code presence alone.

### M7-14

**Run optional-AI failure/security fixtures**

- Type: `VERIFY`. Initial status: `TODO`.
- Prerequisites: [M7-13](M7_OPTIONAL_AI.md#m7-13)
- Deliverable / bounded file scope: AI adapter/fallback/adversarial report.
- Work: Exercise disabled/unavailable AI, invalid JSON, hallucinated IDs, stale manual result, prompt injection, duplicate import and cost-cap exhaustion.
- Acceptance / failure and extension checks: Canonical state changes only under exact authority; deterministic daily loop still runs; at least two fake provider implementations pass the same port tests.
- Completion evidence: artifact paths + exact targeted command/check or user-source reference + observed result + remaining limitations, recorded in PROGRESS. Do not mark done from code presence alone.

### M7-15

**Close optional-AI gate**

- Type: `VERIFY`. Initial status: `TODO`.
- Prerequisites: [M7-14](M7_OPTIONAL_AI.md#m7-14) · [M6-29](M6_PLANNER_DAILY_MVP.md#m6-29)
- Deliverable / bounded file scope: reports/acceptance/M7.md.
- Work: Verify allowed live provider scope separately from fakes, manual premium path and operator cost/failure controls; mark unused optional AI disabled.
- Acceptance / failure and extension checks: M7 completion is not a prerequisite for using the M6 deterministic MVP; a live provider remains unverified without redacted real evidence.
- Completion evidence: artifact paths + exact targeted command/check or user-source reference + observed result + remaining limitations, recorded in PROGRESS. Do not mark done from code presence alone.
