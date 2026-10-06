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
