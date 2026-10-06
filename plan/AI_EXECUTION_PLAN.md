# WhatToDo — AI Execution and Cost Strategy

## 1. Principle

AI is optional infrastructure around a deterministic core.

Changing model/provider must not require redesigning canonical data.

---

## 2. Execution Classes

### Level 0 — No AI
Use deterministic code for:
- dates
- deadlines
- free/busy
- state lookup
- fixed rules
- dedup keys
- simple transforms
- capacity math

### Level 1 — Cheap / normal automated model
Candidate uses:
- email classification
- extracting structured facts from text
- course mapping
- simple summarization
- low-risk decomposition

Potential provider:
- any suitable low-cost API or local/OpenAI-compatible model

No provider is fixed yet.

### Level 2 — Premium manual reasoning
Use when quality materially matters:
- complex multi-week replanning
- semester strategy
- difficult reconciliation
- new course-model design
- architectural review

Primary intended surfaces:
- ChatGPT Work for life/planning operations
- Codex for code/repository development

---

## 3. ChatGPT Plus Boundary

Do not:
- treat Plus as API credit
- automate ChatGPT web UI to bypass API billing
- make unattended backend workflows depend on manual ChatGPT availability

Do:
- create structured premium AI jobs
- export context
- let user trigger Work/Codex
- ingest structured result back through validation

---

## 4. AI Job Concept

Potential fields:
- job ID
- job type
- priority
- executor class
- reason
- context reference
- expected output schema
- status
- created time
- result reference
- validation status

Potential statuses:
- pending
- exported
- completed
- validated
- rejected
- cancelled

---

## 5. Structured Proposal Boundary

Prefer:
```text
AI result
↓
structured proposal
↓
schema validation
↓
domain/authority/state-version validation
↓
user confirmation if not already explicitly authorized
↓
atomic authorized state mutation + audit
```

Do not grant models unrestricted direct database mutation for ordinary planning/extraction.

---

## 6. Cost Policy

Order of preference:
1. deterministic code
2. cheap automated model
3. stronger automated model only when justified
4. premium manual ChatGPT reasoning

Track automated:
- provider
- model
- tokens/cost if available
- job type
- success/failure
- latency where useful

Use this data later to decide whether expensive models actually improve outcomes.

---

## 7. Data-Minimization Policy

Send only the context necessary for the AI job.

Examples:
- email classifier should not receive unrelated personal history
- course task extractor should receive relevant course mapping, not full calendar history
- planner may need broader state but should still avoid irrelevant raw source content

Review SECURITY_PRIVACY_PLAN before adding external providers.

---

## 8. Validation

Validator should check:
- schema
- referenced IDs
- allowed actions
- hard deadlines/constraints
- impossible time ranges
- stale snapshot/version
- unauthorized fields

Model confidence is evidence, not authority.

---

## 9. Dependencies

Depends on:
- DATA_MODEL_PLAN
- IO_CONTRACT_PLAN
- PLANNER_PLAN
- SECURITY_PRIVACY_PLAN

Operationally interacts with:
- n8n
- API credentials
- manual Work/Codex job handoff

Testing:
- mock model outputs
- malformed output
- hallucinated IDs
- stale proposals
- provider failure

---

## 10. Permission and Milestone Clarifications

Validation is necessary but not sufficient authority. High confidence, valid JSON, or a premium model result cannot bypass canonical Task-fact review. A clear resolved direct user command is already authorization for that exact change; extra inferred changes are candidates.

Core write validation, confirmation, version checks, and audit start with Phase 2 persistence. Phase 6 extends them with model-output schemas/provider routing; it does not introduce the first validator. A lightweight reviewed/optional extraction path may precede the full Router; ordinary planning and recovery never require a model call.

Structured proposals may contain derived recommendation scores, but must not confuse them with the user's 1–5 importance or stored remaining effort. Automatic numeric learning updates derived predictions, not canonical user estimates, template defaults, or behavioral rules.
