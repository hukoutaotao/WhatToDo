# WhatToDo — Reliable relationships, reviews and expiration

> Status: executable development specification; every task initially TODO. No task is implemented by this file.
> Task scope: one bounded AI execution per task or explicitly repeated instance.

[Development plan and execution rules](../DEVELOPMENT_PLAN.md) · [Live progress](../PROGRESS.md)

## Required sources

- [TASK_RELATIONSHIP_PLAN.md](../TASK_RELATIONSHIP_PLAN.md)
- [IO_CONTRACT_PLAN.md](../IO_CONTRACT_PLAN.md)
- [DATA_MODEL_PLAN.md](../DATA_MODEL_PLAN.md)
- [OPERATIONS_PLAN.md](../OPERATIONS_PLAN.md)

Read the source sections relevant to the chosen task, its completed prerequisite artifacts, and the shared Definition of Done before editing. Source documents control meaning; this catalog controls work decomposition. Proposed artifact paths below are logical scopes until M2-16 freezes the language-specific mapping. An adapter/schema described here does not yet exist.

## Gate: M3B-16

Task order is constrained by explicit dependencies, not by credentials for unrelated live integrations. A VERIFY task runs the smallest meaningful fixture/integration set for its boundary and records actual evidence. Repeated tasks are one course/family/account/layout/playbook per execution; a template dependency means the required instance set described in the development plan.

## Tasks

### M3B-01

**Persist typed relationship rules and instances**

- Type: `DEV`. Initial status: `TODO`.
- Prerequisites: [M3A-19](M3_STATE_FOUNDATION.md#m3a-19)
- Deliverable / bounded file scope: relationship repositories and migration.
- Work: Store accepted rule versions, concrete typed links and authorization/mapping provenance; maintain separate generation and temporal-order representations.
- Acceptance / failure and extension checks: A reversed generation/order pair persists correctly; bad target IDs fail; rule version changes preserve old instances.
- Completion evidence: artifact paths + exact targeted command/check or user-source reference + observed result + remaining limitations, recorded in PROGRESS. Do not mark done from code presence alone.

### M3B-02

**Validate relationship graphs**

- Type: `DEV`. Initial status: `TODO`.
- Prerequisites: [M3B-01](M3_RELATIONSHIPS_REVIEWS.md#m3b-01)
- Deliverable / bounded file scope: graph validation service.
- Work: Detect uncontrolled generation recursion and contradictory hard-order cycles separately; validate soft/membership links without treating them as hard edges.
- Acceptance / failure and extension checks: Valid reverse-direction example passes; genuine loops report the offending IDs; bounded finite chains have explicit depth/work limits.
- Completion evidence: artifact paths + exact targeted command/check or user-source reference + observed result + remaining limitations, recorded in PROGRESS. Do not mark done from code presence alone.

### M3B-03

**Persist canonical-event outbox**

- Type: `DEV`. Initial status: `TODO`.
- Prerequisites: [M3B-02](M3_RELATIONSHIPS_REVIEWS.md#m3b-02)
- Deliverable / bounded file scope: outbox repository and migration.
- Work: Write canonical creation event with source Task transaction; claim deliveries with leases and durable processing/result state.
- Acceptance / failure and extension checks: Crash before commit yields neither Task nor event; crash after commit leaves replayable event; expired worker lease can be recovered without losing the event.
- Completion evidence: artifact paths + exact targeted command/check or user-source reference + observed result + remaining limitations, recorded in PROGRESS. Do not mark done from code presence alone.

### M3B-04

**Implement one generation-rule evaluator**

- Type: `DEV`. Initial status: `TODO`.
- Prerequisites: [M3B-03](M3_RELATIONSHIPS_REVIEWS.md#m3b-03)
- Deliverable / bounded file scope: mapped-target construction service.
- Work: Resolve one accepted generation mapping from a canonical source occurrence and return a validated target or pending-facts result; use TaskType defaults with provenance.
- Acceptance / failure and extension checks: Raw discovery cannot trigger it; missing essential facts are not invented; separate targets own their B while stages share parent B.
- Completion evidence: artifact paths + exact targeted command/check or user-source reference + observed result + remaining limitations, recorded in PROGRESS. Do not mark done from code presence alone.

### M3B-05

**Implement idempotent counterpart creation**

- Type: `DEV`. Initial status: `TODO`.
- Prerequisites: [M3B-04](M3_RELATIONSHIPS_REVIEWS.md#m3b-04)
- Deliverable / bounded file scope: generation-occurrence repository/handler.
- Work: Use source ID + stable rule ID + target role/occurrence identity as unique occurrence key; create target/link/audit atomically under rule authorization.
- Acceptance / failure and extension checks: Concurrent retries create one counterpart; rule version edits do not recreate it; no redundant per-instance confirmation is emitted for fully authorized targets.
- Completion evidence: artifact paths + exact targeted command/check or user-source reference + observed result + remaining limitations, recorded in PROGRESS. Do not mark done from code presence alone.

### M3B-05.a

**Prepare composite generation transactions and immutable occurrence storage**

- Type: `DEV`. Initial status: `TODO`.
- Prerequisites: [M3B-04](M3_RELATIONSHIPS_REVIEWS.md#m3b-04)
- Deliverable / bounded file scope: portable generation commit plans, append-only occurrence history and forward migration.
- Work: Derive stable target/link/occurrence identity from the canonical source and accepted rule/role; compose target or parent-stage changes, optional explicit typed link and occurrence revision into one exact receipt/audit fingerprint. Retain pending facts and original source/rule/version/default provenance. Add exact source/head/history references without changing prior SQL or base wire contracts.
- Acceptance / failure and extension checks: Rule version edits retain occurrence/target identity; malformed drafts and inferred temporal links fail; separate and stage effects remain distinct; SQL preserves historical receipts/rows, rejects source drift, missing history and mutation of terminal created occurrences, and supports append-only pending-to-created revisions. Preparation confers no mutation authority.
- Completion evidence: targeted pure and owned native checks, installed source match and acceptance report in PROGRESS. Parent M3B-05 remains IN_PROGRESS until M3B-05.b is complete.

### M3B-05.b

**Execute scoped generation commits and verify concurrency/recovery**

- Type: `DEV`. Initial status: `TODO`.
- Prerequisites: [M3B-05.a](M3_RELATIONSHIPS_REVIEWS.md#m3b-05a)
- Deliverable / bounded file scope: scoped application-role occurrence repository/handler and native failure/concurrency verifier.
- Work: Independently resolve canonical source, active accepted rule/root authority, exact definitions and graph constraints; re-evaluate construction, derive exact internal permits, then commit Task/stage, relation, occurrence/history, provenance, receipt/audit and epoch together. Resolve missing facts without a redundant per-instance confirmation queue. Enforce stable occurrence replay before any recreation.
- Acceptance / failure and extension checks: Concurrent retries commit one counterpart; rule edits/cancel/reopen do not recreate or implicitly cancel it; changed and foreign source/principal/account scopes fail; real precommit disconnect rolls back all effects and successful-commit acknowledgement loss reconciles to the original receipt; current parent CAS and stage/shared-budget behavior remain correct. No live worker or personal activation.
- Completion evidence: scoped handler/native acceptance, full regression/installation, exact artifact pins and PROGRESS. Only then mark parent M3B-05 DONE.

### M3B-06

**Implement bounded cascade and recovery processing**

- Type: `DEV`. Initial status: `TODO`.
- Prerequisites: [M3B-05](M3_RELATIONSHIPS_REVIEWS.md#m3b-05)
- Deliverable / bounded file scope: outbox consumer/generation retry path.
- Work: Process accepted finite chains with checkpoints, bounded batches, typed retries and visible permanent failures. This worker executes domain events, not a second workflow platform.
- Acceptance / failure and extension checks: Restart resumes unfinished work; recursive/oversized cascades stop visibly; cancel/reopen source never silently cancels/recreates its counterpart.
- Completion evidence: artifact paths + exact targeted command/check or user-source reference + observed result + remaining limitations, recorded in PROGRESS. Do not mark done from code presence alone.

### M3B-07

**Implement truthful stage rework**

- Type: `DEV`. Initial status: `TODO`.
- Prerequisites: [M3B-02](M3_RELATIONSHIPS_REVIEWS.md#m3b-02) · [M3A-15](M3_STATE_FOUNDATION.md#m3a-15)
- Deliverable / bounded file scope: stage-reopen command handler.
- Work: Reopen the existing stage and keep/reopen its parent INCOMPLETE in one authorized audited transaction; preserve completion history and distinguish new obligations.
- Acceptance / failure and extension checks: Ambiguous rework stays pending; reporting out-of-order real completion records truth plus a relationship violation; no fabricated prerequisite completion.
- Completion evidence: artifact paths + exact targeted command/check or user-source reference + observed result + remaining limitations, recorded in PROGRESS. Do not mark done from code presence alone.

### M3B-07.a

**Prepare exact stage commands and truthful rework effects**

- Type: `DEV`. Initial status: `TODO`.
- Prerequisites: [M3B-02](#m3b-02) and [M3A-15](M3_STATE_FOUNDATION.md#m3a-15).
- Deliverable / bounded file scope: opt-in stage command contract, typed exact grant, detached stage/parent preparation and execution-order diagnostics.
- Work: Preserve stage identity and historical values; genuine rework updates the existing stage and parent together, retains positive parent U or asks for a confirmed estimate when necessary, invalidates predictions and distinguishes unresolved/correction/new-obligation intent. Stage completion preserves truthful reported time and violations without fabricating prerequisite or parent completion.
- Acceptance / failure and extension checks: Shape never grants authority; unknown version/extra approval/foreign caller/stale parent or stage fail; pending intent/needed U has no proposed canonical effects; preparation is immutable and issues no permit; base contracts and SQL remain unchanged.
- Completion evidence: targeted methods, current full regression and isolated installation, exact artifact pins and PROGRESS. Parent M3B-07 remains IN_PROGRESS until M3B-07.b passes.

### M3B-07.b

**Commit scoped stage rework and truthful completion atomically**

- Type: `DEV`. Initial status: `TODO`.
- Prerequisites: [M3B-07.a](#m3b-07a).
- Deliverable / bounded file scope: PostgreSQL stage command handler, transition/violation/pending persistence and additive migration.
- Work: Resolve independent USER authority, account, current parent/stage and complete bounded current relationship/execution evidence. Apply prepared effects and their immutable transition/violation/observation histories in one exact-permit audited CAS transaction; retain unresolved intent and distinguish new obligations. No per-instance redundant confirmation for resolved instructions.
- Acceptance / failure and extension checks: Native staged-parent rework, needed-estimate pending, new/correction intent routing, genuine out-of-order completion, foreign principal/account denial, stable replay, simultaneous CAS, real precommit connection loss and postcommit unknown acknowledgement reconciliation. Prior completion/timing/actual work survive; no implied prerequisite/parent completion.
- Completion evidence: observed native/full regression/installation, exact report pins and ledger; only then mark parent M3B-07 DONE.

### M3B-08

**Implement full-queue review read model**

- Type: `DEV`. Initial status: `TODO`.
- Prerequisites: [M3A-17](M3_STATE_FOUNDATION.md#m3a-17) · [M3B-06](M3_RELATIONSHIPS_REVIEWS.md#m3b-06)
- Deliverable / bounded file scope: pending-review query/service.
- Work: Present every unresolved item, with high-impact first and durable pagination/grouping; include all future-relevant incomplete Tasks needing estimates.
- Acceptance / failure and extension checks: A 5–10 minute target cannot drop low-priority questions; unanswered items persist; sync success cannot mark personal reconciliation complete.
- Completion evidence: artifact paths + exact targeted command/check or user-source reference + observed result + remaining limitations, recorded in PROGRESS. Do not mark done from code presence alone.

### M3B-09

**Implement scoped unchanged-estimate batches**

- Type: `DEV`. Initial status: `TODO`.
- Prerequisites: [M3B-08](M3_RELATIONSHIPS_REVIEWS.md#m3b-08)
- Deliverable / bounded file scope: batch-confirmation command handler.
- Work: Record one explicit confirmation for a listed set of untouched unchanged Tasks, with per-Task version/provenance and separate verification time.
- Acceptance / failure and extension checks: Worked-on/new/missing/changed estimates are excluded; silence confirms none; stale member version produces a conflict rather than silently approving changed values.
- Completion evidence: artifact paths + exact targeted command/check or user-source reference + observed result + remaining limitations, recorded in PROGRESS. Do not mark done from code presence alone.

### M3B-10

**Implement consolidated evening review state**

- Type: `DEV`. Initial status: `TODO`.
- Prerequisites: [M3B-09](M3_RELATIONSHIPS_REVIEWS.md#m3b-09) · [M3B-07](M3_RELATIONSHIPS_REVIEWS.md#m3b-07)
- Deliverable / bounded file scope: evening-review session coordinator.
- Work: Apply resolved individual updates and authorized batches through existing commands; follow up only for missing/ambiguous answers and mark completion only when required items resolve.
- Acceptance / failure and extension checks: Partial answers remain partial; repeated answers do not duplicate effort; completing review is not inferred merely from receiving any message.
- Completion evidence: artifact paths + exact targeted command/check or user-source reference + observed result + remaining limitations, recorded in PROGRESS. Do not mark done from code presence alone.

### M3B-11

**Persist expiration process state**

- Type: `DEV`. Initial status: `TODO`.
- Prerequisites: [M3B-03](M3_RELATIONSHIPS_REVIEWS.md#m3b-03) · [M2-07](M2_CONTRACTS.md#m2-07)
- Deliverable / bounded file scope: expiration process repository/migration.
- Work: Detect accepted expiry conditions, persist Task/version/condition evidence and pending notice state; distinguish overdue REQUIRED work from EXPIRING.
- Acceptance / failure and extension checks: Condition crossing alone cannot write EXPIRED; source deletion cannot expire a Task; restart retains pending notice and avoids duplicate transition records.
- Completion evidence: artifact paths + exact targeted command/check or user-source reference + observed result + remaining limitations, recorded in PROGRESS. Do not mark done from code presence alone.

### M3B-12

**Implement notification port and fake delivery**

- Type: `DEV`. Initial status: `TODO`.
- Prerequisites: [M3B-11](M3_RELATIONSHIPS_REVIEWS.md#m3b-11)
- Deliverable / bounded file scope: NotificationSink fake/dispatch coordinator.
- Work: Support idempotency reference and confirmed/failed/unknown dispatch outcomes; retain attempts and correlation IDs. Unknown result is not automatically success or safe to resend.
- Acceptance / failure and extension checks: Unsent outbox/log entry is not notification; crash after possible delivery produces visible unknown state; no extra user read receipt is required.
- Completion evidence: artifact paths + exact targeted command/check or user-source reference + observed result + remaining limitations, recorded in PROGRESS. Do not mark done from code presence alone.

### M3B-13

**Implement notice-before-record expiration transition**

- Type: `DEV`. Initial status: `TODO`.
- Prerequisites: [M3B-12](M3_RELATIONSHIPS_REVIEWS.md#m3b-12)
- Deliverable / bounded file scope: expiration transition handler.
- Work: After confirmed user-facing dispatch, recheck latest Task version/condition and commit EXPIRED with audit/history; reject changed conditions or completion races.
- Acceptance / failure and extension checks: Failed/unknown delivery leaves transition pending; completed-after-notice Task is not overwritten; EXPIRED never implies COMPLETE or zero successful-work estimate.
- Completion evidence: artifact paths + exact targeted command/check or user-source reference + observed result + remaining limitations, recorded in PROGRESS. Do not mark done from code presence alone.

### M3B-14

**Implement normal interaction day tracking**

- Type: `DEV`. Initial status: `TODO`.
- Prerequisites: [M3B-10](M3_RELATIONSHIPS_REVIEWS.md#m3b-10) · [M3A-02](M3_STATE_FOUNDATION.md#m3a-02)
- Deliverable / bounded file scope: interaction/reminder state repository.
- Work: Track explicit completed/partial normal interactions in Beijing local days and two-consecutive-day inactivity; persist reminder dedup/suppression state.
- Acceptance / failure and extension checks: Receiving connector or bot traffic is not user interaction; partial review is visible; UTC/server-day boundaries cannot alter the accepted reminder trigger.
- Completion evidence: artifact paths + exact targeted command/check or user-source reference + observed result + remaining limitations, recorded in PROGRESS. Do not mark done from code presence alone.

### M3B-15

**Run restart/concurrency relationship scenarios**

- Type: `VERIFY`. Initial status: `TODO`.
- Prerequisites: [M3B-06](M3_RELATIONSHIPS_REVIEWS.md#m3b-06) · [M3B-13](M3_RELATIONSHIPS_REVIEWS.md#m3b-13) · [M3B-14](M3_RELATIONSHIPS_REVIEWS.md#m3b-14)
- Deliverable / bounded file scope: relationship/review fault-injection fixtures.
- Work: Exercise duplicate source events, consumer crash, stale batch, unknown notification delivery and source/target reverse order using PostgreSQL and injected Clock.
- Acceptance / failure and extension checks: No duplicate canonical counterpart, false review completion or unauthorized expiry survives failures; logs identify rule/command/task without leaking raw personal content.
- Completion evidence: artifact paths + exact targeted command/check or user-source reference + observed result + remaining limitations, recorded in PROGRESS. Do not mark done from code presence alone.

### M3B-16

**Close the full M3 prototype gate**

- Type: `VERIFY`. Initial status: `TODO`.
- Prerequisites: [M3B-15](M3_RELATIONSHIPS_REVIEWS.md#m3b-15) · [M3B-18](M3_RELATIONSHIPS_REVIEWS.md#m3b-18)
- Deliverable / bounded file scope: reports/acceptance/M3.md.
- Work: Demonstrate user-authorized Tasks, scoped generation, typed order, rework, review/batch, expiry and reminder primitives with persistent replay history.
- Acceptance / failure and extension checks: All M3A/M3B critical failures and restore evidence are linked; prototype transport works naturally for reviewed input; a Task list is not claimed a verified Planner output.
- Completion evidence: artifact paths + exact targeted command/check or user-source reference + observed result + remaining limitations, recorded in PROGRESS. Do not mark done from code presence alone.

### M3B-17

**Persist scoped constraints and temporary locks**

- Type: `DEV`. Initial status: `TODO`.
- Prerequisites: [M3A-19](M3_STATE_FOUNDATION.md#m3a-19) · [M2-08](M2_CONTRACTS.md#m2-08)
- Deliverable / bounded file scope: constraint/override repository and migration.
- Work: Persist versioned accepted constraint references and dynamic today-only Task locks separately from stable profile defaults; keep complete-versus-advance scope and intended expiry.
- Acceptance / failure and extension checks: A temporary instruction never overwrites a persistent profile; unrelated Task requiredness is unchanged; stale writes and unknown target IDs fail; history retains expired override versions.
- Completion evidence: artifact paths + exact targeted command/check or user-source reference + observed result + remaining limitations, recorded in PROGRESS. Do not mark done from code presence alone.

### M3B-18

**Implement today-lock command and day-end expiry**

- Type: `DEV`. Initial status: `TODO`.
- Prerequisites: [M3B-17](M3_RELATIONSHIPS_REVIEWS.md#m3b-17) · [M3A-11](M3_STATE_FOUNDATION.md#m3a-11) · [M3A-02](M3_STATE_FOUNDATION.md#m3a-02)
- Deliverable / bounded file scope: today-lock create/update/expiry handlers.
- Work: Resolve one clear user complete-today or advance-today command through existing authorization, then expire its temporary planning constraint at the next Beijing midnight; persistent conversion requires explicit scope.
- Acceptance / failure and extension checks: No redundant approval for a resolved command; server date cannot prolong the lock; expiry never completes/cancels/expires the Task itself; retry is idempotent and current snapshot sees the correct lock.
- Completion evidence: artifact paths + exact targeted command/check or user-source reference + observed result + remaining limitations, recorded in PROGRESS. Do not mark done from code presence alone.
