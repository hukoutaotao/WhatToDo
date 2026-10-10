# WhatToDo — Concrete semantic contracts and implementation choices

> Status: executable development specification; every task initially TODO. No task is implemented by this file.
> Task scope: one bounded AI execution per task or explicitly repeated instance.

[Development plan and execution rules](../DEVELOPMENT_PLAN.md) · [Live progress](../PROGRESS.md)

## Required sources

- [DATA_MODEL_PLAN.md](../DATA_MODEL_PLAN.md)
- [IO_CONTRACT_PLAN.md](../IO_CONTRACT_PLAN.md)
- [TASK_RELATIONSHIP_PLAN.md](../TASK_RELATIONSHIP_PLAN.md)
- [PLANNER_PLAN.md](../PLANNER_PLAN.md)
- [SECURITY_PRIVACY_PLAN.md](../SECURITY_PRIVACY_PLAN.md)

Read the source sections relevant to the chosen task, its completed prerequisite artifacts, and the shared Definition of Done before editing. Source documents control meaning; this catalog controls work decomposition. Proposed artifact paths below are logical scopes until M2-16 freezes the language-specific mapping. An adapter/schema described here does not yet exist.

## Gate: M2-18

Task order is constrained by explicit dependencies, not by credentials for unrelated live integrations. A VERIFY task runs the smallest meaningful fixture/integration set for its boundary and records actual evidence. Repeated tasks are one course/family/account/layout/playbook per execution; a template dependency means the required instance set described in the development plan.

## Tasks

### M2-01

**Freeze core Task dimensions**

- Type: `SPEC`. Initial status: `TODO`.
- Prerequisites: [M1B-09](M1B_TASKTYPE_PRESETS.md#m1b-09)
- Deliverable / bounded file scope: formats/input/task.schema and examples.
- Work: Define versioned Task identity, acceptance, binary completion, disposition, trust/overdue metadata, importance and three difficulty dimensions. Give valid/invalid examples.
- Acceptance / failure and extension checks: No single status enum conflates acceptance, progress and expiry; REQUIRED/OPTIONAL/EXPIRING remain exactly the accepted requiredness vocabulary.
- Completion evidence: artifact paths + exact targeted command/check or user-source reference + observed result + remaining limitations, recorded in PROGRESS. Do not mark done from code presence alone.

### M2-01.a

**Implement the offline Task-core contract while personal intake is deferred**

- Type: `DEV` (bounded schema/validator development child). Initial status: `TODO`.
- Prerequisites: [M1-05](M1_USER_COURSE_MODEL.md#m1-05), accepted A0 Task semantics and explicit development-first instruction [D-080](../DECISIONS.md#d-080--develop-the-system-before-completing-personal-intake). This child does not claim M1-09/M1B-09 are passed.
- Deliverable / bounded file scope: [Task-core draft contract](../../formats/input/TASK_CORE_CONTRACT.md), schema, offline validator, synthetic cases, focused tests and contract-check dependency.
- Work: Encode identity and independent acceptance/completion/disposition/requiredness/importance/difficulty/derived metadata. Reject malformed state axes and preserve cancelled/expired history. Use generic context and unresolved references without registering real course presets or importing personal progress.
- Acceptance / failure and extension checks: Positive/negative synthetic cases run offline; duplicate JSON keys cannot silently overwrite a fact; error output omits submitted values; validation never writes state or grants authority. The final toolchain, full Task contract and live activation remain later gates.
- Completion evidence: runnable checks and observed results in PROGRESS. Completing this child is not completing parent M2-01 or M2-18; M1B-09 still precedes final adoption against reviewed presets.

### M2-01.b

**Compose the generic Task aggregate before persistence**

- Type: `CODE + VERIFY`. Initial status: `TODO`; bounded generic follow-up under D-080, without activating real course presets or completing M1/M1B.
- Prerequisites: M2-01.a core axes, M2-02.a effort/stages, M2-08.a normalized time, M2-12.a internal ownership and M2-17.a version/cross-contract evidence.
- Deliverable / bounded file scope: a versioned generic Task aggregate contract/schema, explicit source/type/time/session references, codec/consistency helpers and synthetic valid/invalid examples; registry/database ownership must reflect any new contract.
- Work: Compose existing Task core and effort snapshots without incompatible identity/revision/completion/disposition. Carry release/deadline, provenance and minimum-session/fragmentability facts explicitly, preserving unknowns. Resolve the relevant accepted data-model sections before adding fields. Keep template defaults, observations, derived predictions and command authority separate. Register exact reusable schema ownership rather than hard-coded course branches.
- Acceptance / failure and extension checks: Roundtrip retains exact explicit facts; mismatched snapshots and units fail; nullable unknowns are never invented as zero or configured personal capacity. Cancelled/expired history and completed-work effort semantics remain consistent. A structurally supported aggregate cannot grant authority or become a public arbitrary write API. Existing contracts retain their versions/hashes unless deliberately reviewed; new aggregate ownership is checked.
- Completion evidence: targeted synthetic tests, registry/design consistency checks and actual integration limits in PROGRESS. This fills a generic contract gap identified in M2-18; profile/preset activation, durable repositories and the complete M2 gate remain separately assessed.

### M2-02

**Freeze effort, stages and work observations**

- Type: `SPEC`. Initial status: `TODO`.
- Prerequisites: [M2-01](M2_CONTRACTS.md#m2-01)
- Deliverable / bounded file scope: effort/stage/session schemas.
- Work: Define canonical user U, model remaining-work prediction, effective B, weights, actual effort and observation/verification times; encode parent/stage accounting and truthful rework.
- Acceptance / failure and extension checks: U=4 and B=6 yields 6, not 10 forecast hours; stages partition B; actual time does not mechanically decrement U or imply completion.
- Completion evidence: artifact paths + exact targeted command/check or user-source reference + observed result + remaining limitations, recorded in PROGRESS. Do not mark done from code presence alone.

### M2-02.a

**Implement the offline effort and accounting contract**

- Type: `DEV` (bounded early-development child). Initial status: `TODO`.
- Prerequisites: [M2-01.a](M2_CONTRACTS.md#m2-01a), accepted D-066/074 and parent/stage accounting semantics; development-order authority is D-080. Final preset/toolchain adoption remains separate.
- Deliverable / bounded file scope: development effort/stage/observation schemas, pure budget-selection checks and synthetic accounting examples.
- Work: Keep canonical user U separate from model remaining prediction B; applicable valid B drives planning even when smaller than U, otherwise fall back to U with provenance. Represent missing U/B as unresolved rather than zero, stages as one partitioned obligation and separate generated work independently. Record observations without mechanically reducing U or implying completion.
- Acceptance / failure and extension checks: U=4/B=6 yields 6, U=6/B=4 yields 4; missing/stale/inapplicable model and missing U are distinct; expired history retains U; actual work and stage completion cannot create parent completion. No personal task imports or database writes.
- Completion evidence: targeted runnable fixture tests and exact limitations in PROGRESS. Completing this child does not close parent M2-02 or M2-18.

### M2-03

**Freeze source and candidate contracts**

- Type: `SPEC`. Initial status: `TODO`.
- Prerequisites: [M2-01](M2_CONTRACTS.md#m2-01)
- Deliverable / bounded file scope: source/candidate schemas.
- Work: Define provenance, source hashes/IDs, parser versions, conflicts, confidence and pending acceptance; preserve raw evidence versus canonical facts.
- Acceptance / failure and extension checks: A high-confidence submission produces a completion candidate, not COMPLETE; a source deletion does not cancel its accepted Task.
- Completion evidence: artifact paths + exact targeted command/check or user-source reference + observed result + remaining limitations, recorded in PROGRESS. Do not mark done from code presence alone.

### M2-03.a

**Implement offline source provenance and candidate boundaries**

- Type: `DEV` (early-development child). Initial status: `TODO`.
- Prerequisites: [M2-01.a](M2_CONTRACTS.md#m2-01a), [M2-02.a](M2_CONTRACTS.md#m2-02a), accepted source/confirmation/truth boundaries and D-080.
- Deliverable / bounded file scope: development source/candidate schemas, immutable provenance/candidate helpers, synthetic fixtures and focused tests.
- Work: Preserve source identity/hash, scope, parser version, proposed facts, target/version, confidence and review state. External discoveries and completion evidence remain pending regardless of confidence. Deterministic parser replay preserves candidate identity and review history; changed facts/versions are distinguishable.
- Acceptance / failure and extension checks: A strong external completion signal never writes COMPLETE; source deletion does not cancel a Task; untrusted fields cannot mint authority; same-evidence replay adds no second candidate; conflicting replay is diagnosed. Generic provider metadata works without hard-coded course/account branches.
- Completion evidence: executed synthetic/contract tests in PROGRESS. Actual collectors, authority resolution, persistent deduplication and live provider access remain later tasks.

### M2-04

**Freeze command and authorization envelope**

- Type: `SPEC`. Initial status: `TODO`.
- Prerequisites: [M2-01](M2_CONTRACTS.md#m2-01) · [M2-03](M2_CONTRACTS.md#m2-03)
- Deliverable / bounded file scope: formats/input/command.schema and authority matrix.
- Work: Define command ID, principal/origin, resolved targets, expected version, exact authorized fields, batch membership and approval/rule reference.
- Acceptance / failure and extension checks: An explicit user command needs no duplicate approval; inferred extra updates stay pending; external content cannot mint a principal or authorization reference.
- Completion evidence: artifact paths + exact targeted command/check or user-source reference + observed result + remaining limitations, recorded in PROGRESS. Do not mark done from code presence alone.

### M2-04.a

**Implement command envelopes and scoped authorization checks offline**

- Type: `DEV` (early-development child). Initial status: `TODO`.
- Prerequisites: [M2-01.a](M2_CONTRACTS.md#m2-01a), [M2-03.a](M2_CONTRACTS.md#m2-03a), accepted direct-user/generation/expiry authority semantics and D-080.
- Deliverable / bounded file scope: development command schema, authority matrix, pure validation/authorization module and synthetic tests.
- Work: Bind command identity, trusted caller/origin, resolved targets, expected state revision, exact authorized fields and batch/rule scope. User authority comes from trusted transport/resolved instructions, not an external content field. Explicit user instructions need no duplicate approval; inferred extra mutations remain pending.
- Acceptance / failure and extension checks: Forged principal/reference, unlisted target/field, stale revision and external completion claims cannot authorize writes. A valid rule may authorize only mapped creation; expiry needs verified notice/revalidation. Keep pure checks separate from actual PostgreSQL transactions and transport authentication.
- Completion evidence: executed fixtures and remaining reference/transport/persistence limits in PROGRESS. Completing this child does not certify a real caller, notification provider or parent M2-04/M2-18.

### M2-05

**Freeze review and unchanged-estimate batch contracts**

- Type: `SPEC`. Initial status: `TODO`.
- Prerequisites: [M2-02](M2_CONTRACTS.md#m2-02) · [M2-04](M2_CONTRACTS.md#m2-04)
- Deliverable / bounded file scope: review/questionnaire/batch schemas.
- Work: Define full pending-queue presentation, worked-on individual updates, untouched unchanged batches, per-Task verification and partial-review status.
- Acceptance / failure and extension checks: Silence and missing initial estimates do not confirm anything; a partial answer never becomes a completed normal review; original estimate observation time is retained.
- Completion evidence: artifact paths + exact targeted command/check or user-source reference + observed result + remaining limitations, recorded in PROGRESS. Do not mark done from code presence alone.

### M2-05.a

**Implement full review coverage and unchanged-estimate batches offline**

- Type: `DEV` (early-development child). Initial status: `TODO`.
- Prerequisites: [M2-02.a](M2_CONTRACTS.md#m2-02a), [M2-04.a](M2_CONTRACTS.md#m2-04a), accepted D-065/077 and normal-review semantics.
- Deliverable / bounded file scope: development review/batch schema, pure coverage/verification helpers, synthetic examples and focused tests.
- Work: Present the full current pending queue and relevant task questionnaire. Individual worked-on answers retain completion, actual-report meaning and a current U; explicit untouched batches identify every member, bind estimate/revision, preserve original observation time and record verification separately. Missing/uncertain/changed/worked estimates cannot enter unchanged batches.
- Acceptance / failure and extension checks: Silence/preselected suggestions do not confirm; partial replies do not close a normal review; skipped queue items remain visible. Batch replay is idempotent, changed membership/version/estimate is rejected, work/cumulative meaning is retained without inventing actual effort or completion. Assess response coverage separately from persisted review completion.
- Completion evidence: executed synthetic tests and transport/persistence limits in PROGRESS. No actual personal review is completed by fixtures.

### M2-06

**Freeze typed relationship objects**

- Type: `SPEC`. Initial status: `TODO`.
- Prerequisites: [M2-01](M2_CONTRACTS.md#m2-01) · [M2-04](M2_CONTRACTS.md#m2-04)
- Deliverable / bounded file scope: rule/relation/occurrence schemas.
- Work: Define generation, completion/start order, soft sequence and membership separately; stable rule identity, version, field mapping and occurrence key.
- Acceptance / failure and extension checks: The generation/order reverse pair is not a false cycle; genuine recursive generation and hard-order contradiction are diagnosable; changing rule version does not duplicate old targets.
- Completion evidence: artifact paths + exact targeted command/check or user-source reference + observed result + remaining limitations, recorded in PROGRESS. Do not mark done from code presence alone.

### M2-06.a

**Implement typed relationships and occurrence checks offline**

- Type: `DEV` (early-development child). Initial status: `TODO`.
- Prerequisites: [M2-01.a](M2_CONTRACTS.md#m2-01a), [M2-04.a](M2_CONTRACTS.md#m2-04a), accepted D-071/072 and TASK_RELATIONSHIP_PLAN.
- Deliverable / bounded file scope: development rule/relation/occurrence schemas, pure typed graph and ordering checks, stable occurrence identity and synthetic tests.
- Work: Separate canonical-creation generation, completion order, start prerequisites, soft sequence and parent/stage membership. Retain rule acceptance/template/mapping scope and provenance without treating a reference as authority. Check generation and hard ordering independently; bind occurrence identity to stable rule/source/role/occurrence rather than rule version.
- Acceptance / failure and extension checks: Reverse generation/order pairs are valid; recursive generation and contradictory hard order return precise offending identities. A completion prerequisite does not imply a start prerequisite; soft sequence is bypassable. Stage membership is distinct from a generated separate obligation. Rule edits/retries preserve occurrence identity; missing target facts remain pending and real out-of-order completion is reported truthfully.
- Completion evidence: runnable synthetic fixtures/tests in PROGRESS. Actual template/authority resolution, generation transactions, persistent uniqueness and Planner scheduling remain later work; this child does not close M2-06/M2-18.

### M2-07

**Freeze expiration and notification process contracts**

- Type: `SPEC`. Initial status: `TODO`.
- Prerequisites: [M2-04](M2_CONTRACTS.md#m2-04)
- Deliverable / bounded file scope: expiration-notice and dispatch-result schemas.
- Work: Define detected condition, pending notice, confirmed/failed/unknown delivery, post-notice version revalidation and retained transition history. Select no delivery provider yet.
- Acceptance / failure and extension checks: Unsent queue entries are not “informed”; no new acknowledgement is required; ambiguous delivery or stale state does not authorize EXPIRED.
- Completion evidence: artifact paths + exact targeted command/check or user-source reference + observed result + remaining limitations, recorded in PROGRESS. Do not mark done from code presence alone.

### M2-07.a

**Implement offline expiration notice lifecycle and revalidation**

- Type: `DEV` (early-development child). Initial status: `TODO`.
- Prerequisites: [M2-04.a](M2_CONTRACTS.md#m2-04a), accepted D-073 and notification/expiration semantics.
- Deliverable / bounded file scope: development expiration/dispatch schemas, immutable lifecycle helpers and synthetic tests.
- Work: Distinguish confirmed condition detection, queued attempts, confirmed/failed/unknown delivery, explicit reconciliation and latest-state revalidation. Preserve attempts, correlation/evidence references and stable notice identity without selecting a provider.
- Acceptance / failure and extension checks: Queue entries cannot prove delivery. Unknown delivery blocks automatic resend; confirmed failure permits retry. Replay is idempotent. Completed/changed-version/changed-condition Tasks cannot be overwritten after delivery. No extra acknowledgement is needed; neither completion nor canonical U is changed by this pure process.
- Completion evidence: executed synthetic lifecycle/authorization tests in PROGRESS. Actual notification transport, condition evaluation, durable retries/outbox and audited EXPIRED transactions remain later tasks.

### M2-08

**Freeze events, occupancy and time contracts**

- Type: `SPEC`. Initial status: `TODO`.
- Prerequisites: [M2-01](M2_CONTRACTS.md#m2-01)
- Deliverable / bounded file scope: event/availability schemas and date fixtures.
- Work: Define source event ownership, exact instant versus date-only, Asia/Shanghai 23:59 defaults, recurrence concepts and finite availability windows. Include stable preference constraints versus dynamic scoped today-only locks with complete/advance meaning and next-midnight expiry.
- Acceptance / failure and extension checks: Explicit source times survive normalization; today-lock expiry is next midnight; natural-day bounds include today and elapsed capacity is excluded.
- Completion evidence: artifact paths + exact targeted command/check or user-source reference + observed result + remaining limitations, recorded in PROGRESS. Do not mark done from code presence alone.

### M2-08.a

**Implement offline time normalization and occupancy windows**

- Type: `DEV` (early-development child). Initial status: `TODO`.
- Prerequisites: [M2-01.a](M2_CONTRACTS.md#m2-01a), accepted D-075/078 and time/capacity semantics; D-080 permits synthetic development before Calendar/capacity intake.
- Deliverable / bounded file scope: development time/event/window schemas, pure normalization/interval helpers and synthetic boundary tests.
- Work: Preserve explicit instants/timezones, normalize date-only due to Asia/Shanghai 23:59, represent natural-day 1/3/7-day horizons including today, next-local-midnight today locks and finite occupancy/availability intervals. Elapsed time and overlapping occupancy must not create capacity; provider events remain separate from accepted Tasks.
- Acceptance / failure and extension checks: Timezone/day rollover, explicit-time preservation, today-lock expiry, natural-day cutoff and interval overlap/clipping are deterministic without a live Calendar or guessed personal schedule.
- Completion evidence: runnable synthetic tests in PROGRESS. Actual Calendar ownership/scopes, recurring-event expansion, personal availability and Planner capacity/reserve decisions remain later work.

### M2-09

**Freeze generic Goal and Exam contracts**

- Type: `SPEC`. Initial status: `TODO`.
- Prerequisites: [M2-01](M2_CONTRACTS.md#m2-01) · [M2-06](M2_CONTRACTS.md#m2-06)
- Deliverable / bounded file scope: goal/milestone/exam/onboarding schemas.
- Work: Define target, workload/measure, target date, cadence, phases and progress; Exam is an independent fixed event; generated work uses ordinary Tasks and accepted rule scope.
- Acceptance / failure and extension checks: Goal configuration is not itself Task completion; milestones do not create a parallel workload total; missing generation mappings remain pending.
- Completion evidence: artifact paths + exact targeted command/check or user-source reference + observed result + remaining limitations, recorded in PROGRESS. Do not mark done from code presence alone.

### M2-09.a

**Implement generic Goal onboarding and independent Exam records offline**

- Type: `DEV` (early-development child). Initial status: `TODO`.
- Prerequisites: [M2-06.a](M2_CONTRACTS.md#m2-06a), [M2-08.a](M2_CONTRACTS.md#m2-08a), accepted D-022/047 and Goal/Task separation.
- Deliverable / bounded file scope: development Goal/Milestone/Exam/progress schemas, pure onboarding/measurement helpers and synthetic tests.
- Work: Retain target/outcome, measured target or total workload, explicit known/unknown horizon/cadence/phases, generation references and dynamic source-backed progress. Keep Goal configuration, milestone checkpoints, Exam fixed events and ordinary Task obligations separate. Date-only Exam timing does not invent an exam start or use deadline 23:59.
- Acceptance / failure and extension checks: Partial onboarding remains pending; numeric target attainment does not imply confirmed completion; milestones/Goal amounts are not extra Task effort; missing rule mappings grant no generation authority; exact Exam time preserves timezone and unknown coverage/time stays unknown. No real Goal onboarding or automatic generator is enabled.
- Completion evidence: targeted runnable synthetic/schema tests in PROGRESS. Actual Goal intake, axis/rule resolution, persistence and scoped generation remain later work.

### M2-10

**Freeze Plan and forecast output contracts**

- Type: `SPEC`. Initial status: `TODO`.
- Prerequisites: [M2-02](M2_CONTRACTS.md#m2-02) · [M2-06](M2_CONTRACTS.md#m2-06) · [M2-08](M2_CONTRACTS.md#m2-08)
- Deliverable / bounded file scope: formats/output/plan.schema and fixtures.
- Work: Define snapshot/version, B/source, C/R/S, natural-day bounds, data-quality state, solver outcome, plan role versus requiredness and provisional/final emergency flags.
- Acceptance / failure and extension checks: Unknown/stale input is distinct from SAFE/DANGER/EMERGENCY; overlapping forecasts are not summed; display does not count repeated fragment references twice.
- Completion evidence: artifact paths + exact targeted command/check or user-source reference + observed result + remaining limitations, recorded in PROGRESS. Do not mark done from code presence alone.

### M2-10.a

**Implement offline Plan/forecast output and certainty checks**

- Type: `DEV` (early-development child). Initial status: `TODO`.
- Prerequisites: [M2-02.a](M2_CONTRACTS.md#m2-02a), [M2-06.a](M2_CONTRACTS.md#m2-06a), [M2-08.a](M2_CONTRACTS.md#m2-08a), accepted model-first accounting, risk/feasibility/reserve and Daily Brief semantics.
- Deliverable / bounded file scope: development Plan/forecast output schema, pure classification/accounting validation and synthetic checks.
- Work: Bind snapshot/versions, 1/3/7 natural-day windows, effective budget provenance, C/R/S, hard-placement evidence, input quality and solver outcome. Keep plan role separate from requiredness, repeated Task/stage references separate from obligations and provisional emergency distinct from finalized post-review output.
- Acceptance / failure and extension checks: Unknown/stale input or an unresolved solver outcome alone cannot prove SAFE/DANGER/EMERGENCY. A known aggregate deficit or proven hard-placement deficit may establish EMERGENCY; positive aggregate margin still needs hard-placement evidence. Horizon totals overlap and are never summed; fragment/section references cannot double count one budget. Final emergency requires the completed second review/solve boundary.
- Completion evidence: executed synthetic/schema tests in PROGRESS. A real solver/oracle, authenticated emergency review, persisted snapshots, actual personal capacity and human renderer remain separate downstream tasks.

### M2-11

**Freeze AI-job and learning-result contracts**

- Type: `SPEC`. Initial status: `TODO`.
- Prerequisites: [M2-02](M2_CONTRACTS.md#m2-02) · [M2-04](M2_CONTRACTS.md#m2-04)
- Deliverable / bounded file scope: AIJob/prediction/behavior-rule schemas.
- Work: Define manual export/import, validation state, model metadata and versioned numeric predictions versus candidate reviewed behavioral policy.
- Acceptance / failure and extension checks: Predictions cannot overwrite canonical U or preferences; a valid schema/model confidence alone cannot grant write authority.
- Completion evidence: artifact paths + exact targeted command/check or user-source reference + observed result + remaining limitations, recorded in PROGRESS. Do not mark done from code presence alone.

### M2-11.a

**Implement offline AI-job and learning-result validation boundaries**

- Type: `DEV` (early-development child). Initial status: `TODO`.
- Prerequisites: [M2-02.a](M2_CONTRACTS.md#m2-02a), [M2-03.a](M2_CONTRACTS.md#m2-03a), [M2-04.a](M2_CONTRACTS.md#m2-04a), accepted optional AI/numeric-versus-policy learning semantics.
- Deliverable / bounded file scope: development AI-job/result, remaining-prediction and behavior-candidate schemas; immutable export/import validation helpers and synthetic tests.
- Work: Bind job/context hashes, schema/model versions, scoped target revisions, snapshots, manual/automatic executor class and result history. Separate valid derived remaining-work predictions from policy/configuration proposals, preserve canonical U and keep behavioral proposals pending. Export references/explicit minimized context only; no provider selection or call.
- Acceptance / failure and extension checks: Stale/cancelled/mismatched/unknown-ID/extra-field results do not activate changes. Numeric remaining prediction can feed B after validity/applicability checks; original-total prediction cannot substitute for remaining effort. Schema validity/confidence never grants Task, preference, default or rule mutation authority. Replays preserve identity and diagnose conflicting output.
- Completion evidence: executed synthetic/schema checks in PROGRESS. Actual model/provider/budget, minimized real context, persistent jobs/replay and reviewed behavioral-policy adoption remain future gates; no live model or actual manual premium job is required.

### M2-12

**Define ports and module ownership**

- Type: `SPEC`. Initial status: `TODO`.
- Prerequisites: [M2-03](M2_CONTRACTS.md#m2-03) · [M2-07](M2_CONTRACTS.md#m2-07) · [M2-08](M2_CONTRACTS.md#m2-08) · [M2-10](M2_CONTRACTS.md#m2-10)
- Deliverable / bounded file scope: application ports and error taxonomy.
- Work: Specify StateStore, Clock, CalendarSource, EvidenceSource, NotificationSink, Predictor, Solver and Renderer requests/results; typed retryable/permanent/conflict/unknown outcomes.
- Acceptance / failure and extension checks: Fake adapters can satisfy the same contracts as live providers; domain code has no provider SDK, credential or n8n-node dependencies; new adapters do not change Task semantics.
- Completion evidence: artifact paths + exact targeted command/check or user-source reference + observed result + remaining limitations, recorded in PROGRESS. Do not mark done from code presence alone.

### M2-12.a

**Develop application-port contracts and synthetic fake adapters**

- Type: `CODE + VERIFY`. Initial status: `TODO`; bounded offline development child of M2-12 under D-080, not completion of all runtime integration.
- Prerequisites: runnable M2-03.a, M2-04.a, M2-07.a, M2-08.a, M2-10.a and M2-11.a contracts. Generic fixtures do not need additional personal intake.
- Deliverable / bounded file scope: application request/result protocols, error taxonomy, no-I/O fake adapters and focused synthetic tests, plus an ownership/interface note.
- Work: Define StateStore, Clock, CalendarSource, EvidenceSource, NotificationSink, Predictor, Solver and Renderer with explicit unknown/retryable/permanent/conflict outcomes. Preserve state/audit transaction requirements, notification delivery ambiguity and derived-vs-canonical ownership. Use resolved domain records where possible; no live SDK, credential, backend service or n8n workflow is introduced.
- Acceptance / failure and extension checks: Fakes satisfy the same interface as intended live adapters; results cannot turn unknown into zero/success, expose arbitrary mutation authority or promote external data to canonical truth. Failed state/audit writes leave neither partial state nor partial history; stale/idempotent/conflicting retry fixtures are distinct. Domain modules remain provider-independent.
- Completion evidence: executed targeted tests and limitations in PROGRESS. PostgreSQL durability, real adapters, exact live transport and runtime/toolchain selection remain separate gates.

### M2-13

**Build semantic fixture catalog**

- Type: `SPEC`. Initial status: `TODO`.
- Prerequisites: [M2-05](M2_CONTRACTS.md#m2-05) · [M2-09](M2_CONTRACTS.md#m2-09) · [M2-10](M2_CONTRACTS.md#m2-10) · [M2-11](M2_CONTRACTS.md#m2-11)
- Deliverable / bounded file scope: tests/fixtures/semantic and requirement map.
- Work: Create synthetic positive/negative fixtures for each accepted boundary and core workflow; preserve a decision-to-fixture mapping independent of implementation.
- Acceptance / failure and extension checks: Contains U<B/U>B, hard window infeasibility, notice failure, batch scope, reverse relationship graphs and natural-day rollover; fixtures contain no current private user data.
- Completion evidence: artifact paths + exact targeted command/check or user-source reference + observed result + remaining limitations, recorded in PROGRESS. Do not mark done from code presence alone.

### M2-13.a

**Develop the offline semantic fixture map and cross-domain scenarios**

- Type: `SPEC + CODE + VERIFY`. Initial status: `TODO`; bounded offline development child of M2-13 under D-080.
- Prerequisites: runnable M2-01.a through M2-12.a contracts, synthetic bundles and focused tests. Additional personal intake/live accounts are unnecessary.
- Deliverable / bounded file scope: tests/fixtures/semantic requirement/scenario catalog, a focused cross-domain scenario runner, and a traceability/limitations note.
- Work: Map accepted decisions to concrete positive/negative fixture IDs and test evidence; exercise composed effort/forecast, source/authority, batch/commit, relationship/generation, notice/reconciliation/expiry and natural-day rollover scenarios. Expected outcomes are explicit accepted semantics, not generated from implementation output.
- Acceptance / failure and extension checks: U<B/U>B, positive aggregate capacity with infeasible hard windows, failed/unknown notice, exact batch membership, reverse graph types and Beijing rollover have executable synthetic evidence. Referenced cases/test methods/decision IDs must resolve and unique scenario IDs remain stable. Missing application/persistence/live evidence is reported as pending rather than certified by domain tests.
- Completion evidence: executed catalog and scenario checks in PROGRESS. Full frozen-release acceptance, reference resolution, live providers and PostgreSQL end-to-end validation remain later gates.

### M2-14

**Design PostgreSQL ownership and constraints**

- Type: `SPEC`. Initial status: `TODO`.
- Prerequisites: [M2-12](M2_CONTRACTS.md#m2-12) · [M2-13](M2_CONTRACTS.md#m2-13)
- Deliverable / bounded file scope: schema design and migration sequence.
- Work: Map frozen contracts to separate aggregate tables/logs, foreign keys, uniqueness/version constraints, outbox/checkpoints and semantic history retention; stage migrations into small batches.
- Acceptance / failure and extension checks: Exactly one occurrence per source/rule/role is enforceable in PostgreSQL; audit and state share transactions; no JSON-only design evades referential/version checks.
- Completion evidence: artifact paths + exact targeted command/check or user-source reference + observed result + remaining limitations, recorded in PROGRESS. Do not mark done from code presence alone.

### M2-14.a

**Develop relational ownership, constraint and migration design**

- Type: `SPEC + VERIFY`. Initial status: `TODO`; bounded offline development child of M2-14 under D-080.
- Prerequisites: runnable M2-01.a through M2-13.a contracts, port ownership and scoped semantic traceability. Final schema freeze/runtime toolchain and full user intake remain separately unresolved.
- Deliverable / bounded file scope: database ownership/constraint map, versioned draft PostgreSQL schema/migration sequence and executable design consistency checks with synthetic examples.
- Work: Separate canonical Task/state/effort, immutable source/candidate/review/observation histories, rules/occurrences/relations, notices/attempts, Goal/Exam, derived Plan/model records, transaction audit/receipt, outbox and collector checkpoints. Use explicit relational IDs/versions/foreign keys/uniqueness where semantics require them; opaque JSON extensions cannot replace those constraints. Bind transaction/state/audit/outbox ownership and failure/replay behavior to ports.
- Acceptance / failure and extension checks: Canonical source/rule/role occurrence identity remains stable across rule versions; no duplicate parent/stage budgets or source-driven completion; notice success and current-state revalidation precede expiry; unknown is distinct from zero/absence. Ordered small migrations preserve history, and constraint ownership/reference maps resolve. Any executed SQL/design checks are reported at their actual evidence level.
- Completion evidence: artifacts, checks and remaining limitations in PROGRESS. Final contract/runtime choices, installed/live PostgreSQL execution, migration application, crash/fault/restore verification and actual repository adapters remain separate gates; a parsed draft is not a migrated database.

### M2-15

**Choose prototype delivery and access contract**

- Type: `SPEC`. Initial status: `TODO`.
- Prerequisites: [M2-04](M2_CONTRACTS.md#m2-04) · [M2-07](M2_CONTRACTS.md#m2-07) · [M2-12](M2_CONTRACTS.md#m2-12)
- Deliverable / bounded file scope: prototype transport/channel/access ADR.
- Work: Resolve one prototype review/brief/notification surface and authenticated caller path using user needs; choose service auth/scopes without selecting unrelated email providers.
- Acceptance / failure and extension checks: Human normal input is natural language/guided responses, not hand-written JSON; test channel exists; real channel choice is a scoped user checkpoint; no unauthenticated mutation endpoint.
- Completion evidence: artifact paths + exact targeted command/check or user-source reference + observed result + remaining limitations, recorded in PROGRESS. Do not mark done from code presence alone.

### M2-15.a

**Develop an offline guided review prototype**

- Type: `CODE + VERIFY`. Initial status: `TODO`; generic development child under D-080. Does not select a real delivery channel or service authentication policy.
- Prerequisites: M2-04.a authority, M2-05.a full-frame/batch review, M2-12.a ports and M2-16.a local toolchain. User-specific information/accounts are unnecessary for synthetic fixtures.
- Deliverable / bounded file scope: provider-independent guided review presentation/response helpers, a local synthetic demo and focused tests/interface documentation.
- Work: Display every Task and pending candidate in a version-bound frame; accept concise guided/natural responses without requiring users to write JSON. Keep unfinished/unknown/default answers distinct, preserve exact batch membership and remaining-versus-actual measure, and retain raw user statement references for later independent authentication/validation.
- Acceptance / failure and extension checks: A suggestion cannot submit itself or create authority; ambiguous/partial answers leave review open. Unknown IDs, stale frame/task revisions, missing estimates, worked batch members and unconfirmed completion cannot be silently accepted or narrowed. Candidate decisions remain proposed until a separate trusted commit. The synthetic demo performs no canonical/database/provider writes.
- Completion evidence: executed presentation/parser/coverage tests and demo transcript in PROGRESS. Real transport, trusted caller binding, persistent response handling and chosen user surface remain separate M2-15/application gates.

### M2-16

**Select one implementation toolchain**

- Type: `SPIKE`. Initial status: `TODO`.
- Prerequisites: [M2-12](M2_CONTRACTS.md#m2-12) · [M2-14](M2_CONTRACTS.md#m2-14)
- Deliverable / bounded file scope: technical ADR and reproducible toolchain manifest.
- Work: Bound the comparison to Python versus TypeScript unless a blocker is evidenced; test date arithmetic, schema validation, PostgreSQL transactions and a fake port. Pin supported versions and map logical paths to real files.
- Acceptance / failure and extension checks: A clean machine runs one command for targeted checks; language/versions are explicit engineering choices, not invented user preferences; SDK-specific code remains behind adapters.
- Completion evidence: artifact paths + exact targeted command/check or user-source reference + observed result + remaining limitations, recorded in PROGRESS. Do not mark done from code presence alone.

### M2-16.a

**Run the isolated implementation-toolchain spike**

- Type: `SPIKE + CODE + VERIFY`. Initial status: `TODO`; generic development child under D-080, independent of actual intake/live delivery-channel selection.
- Prerequisites: M2-12.a ports, M2-13.a semantic fixtures and M2-14.a checked relational draft. Full contract freeze remains open.
- Deliverable / bounded file scope: engineering ADR, pinned project-local development dependencies, reproducible verification command and isolated PostgreSQL transaction/migration probes. Compare Python versus TypeScript using measured compatibility/reuse and replacement costs.
- Work: Verify date arithmetic/schema validation/fake port on the selected stack and actual PostgreSQL rollback/receipt/audit behavior in an isolated synthetic database. Any downloaded development binaries/dependencies stay project-local; do not modify global services, accounts, credentials or live data. Preserve explicit not-run evidence when an individual native check has not executed.
- Acceptance / failure and extension checks: One command reports exact runtime/dependency versions and distinguishes checks actually run from unavailable checks. PostgreSQL transaction claims require actual native execution. A local design check alone cannot select/freeze the complete runtime or close the full M2 gate.
- Completion evidence: exact commands, observed versions/results, reproducibility manifest and limitations in PROGRESS. Actual user channel, deployment, full domain codecs/adapters and operating durability remain later gates.

### M2-17

**Check all contracts together**

- Type: `VERIFY`. Initial status: `TODO`.
- Prerequisites: [M2-15](M2_CONTRACTS.md#m2-15) · [M2-16](M2_CONTRACTS.md#m2-16)
- Deliverable / bounded file scope: contract consistency and evolution report.
- Work: Walk one morning/evening scenario, one generation+order case, one expiration case and one generic Goal through schemas/ports; define additive versus breaking version behavior.
- Acceptance / failure and extension checks: No field carries incompatible meanings across contracts; old-version input is either explicitly adapted or rejected with reason; no silent accepted-data loss.
- Completion evidence: artifact paths + exact targeted command/check or user-source reference + observed result + remaining limitations, recorded in PROGRESS. Do not mark done from code presence alone.

### M2-17.a

**Verify offline contract consistency and explicit evolution boundaries**

- Type: `VERIFY + CODE`. Initial status: `TODO`; bounded offline child under D-080. Full M2-17/18 release gates remain separate.
- Prerequisites: M2-01.a through M2-16.a runnable scoped contracts, guided prototype, semantic catalog, relational draft and native toolchain spike. Real user transport/intake/deployment remain unresolved and unnecessary for these synthetic checks.
- Deliverable / bounded file scope: explicit contract/version compatibility manifest, cross-contract check/scenario runner and focused evolution regression evidence.
- Work: Compose morning/evening review, generation/order, delivered expiry and generic Goal paths across domain/schema/port boundaries. Declare which current draft versions are supported, reject unknown/breaking input with reason and preserve legacy snapshots rather than silently replacing accepted data. Resolve ownership/version references to actual artifacts.
- Acceptance / failure and extension checks: Values retain their meanings across helpers/wire schemas/ports; no canonical U overwrite, silent authority promotion, dropped review scope or unknown-as-zero conversion. A valid version/schema is not reference resolution or authority. Unsupported versions fail conservatively; additive/breaking changes name invalidated downstream evidence. No fake/live evidence conflation or full release certification.
- Completion evidence: executed synthetic scenarios/version negative cases and actual remaining gates in PROGRESS. Full schema freeze/codecs, application transaction/transport, real preset activation and final release acceptance remain future tasks.

### M2-18

**Close the M2 contract gate**

- Type: `VERIFY`. Initial status: `TODO`.
- Prerequisites: [M2-17](M2_CONTRACTS.md#m2-17)
- Deliverable / bounded file scope: reports/acceptance/M2.md.
- Work: Freeze core schema versions, output baseline, selected toolchain/path mapping and critical assumptions. Required unresolved semantics block affected coding; provider credentials do not block fake adapters.
- Acceptance / failure and extension checks: M2 contracts and relevant accepted semantics are demonstrably usable before M3; planned artifacts are not claimed implemented; every later code task has stable input/output ownership. Under D-080, the offline/generic gate may use reviewed representative examples and explicitly synthetic presets without complete semester intake. Real profile/preset activation still requires the corresponding M1/M1B review; this gate cannot certify missing personal capacity or enabled live providers.
- Completion evidence: artifact paths + exact targeted command/check or user-source reference + observed result + remaining limitations, recorded in PROGRESS. Do not mark done from code presence alone.
