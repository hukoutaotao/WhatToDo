# Input Format Specifications

> Execution: [detailed development plan](../../plan/DEVELOPMENT_PLAN.md) · [live progress](../../plan/PROGRESS.md).
> Bounded work: [M2_CONTRACTS](../../plan/tasks/M2_CONTRACTS.md) · [M3_STATE_FOUNDATION](../../plan/tasks/M3_STATE_FOUNDATION.md).

This directory stores specifications, examples, schemas, and conventions for information entering WhatToDo.

Status: conceptual input semantics accepted in A0. Runnable [Task-core](TASK_CORE_CONTRACT.md), [effort/observation](EFFORT_CONTRACT.md), [source/candidate](SOURCE_CANDIDATE_CONTRACT.md), [command/authority](COMMAND_AUTHORITY_CONTRACT.md), [review/batch](REVIEW_BATCH_CONTRACT.md), [relationships](RELATIONSHIP_CONTRACT.md), [expiration/notification](EXPIRATION_NOTICE_CONTRACT.md), [time/occupancy](TIME_WINDOW_CONTRACT.md), [Goals/Exams](GOAL_EXAM_CONTRACT.md) and [AI-result handoff](AI_RESULT_CONTRACT.md) development drafts exist under the corresponding M2 development children; full Task encoding and release freeze remain M2 work. The user's development-first instruction permits independent contract/fixture development while personal intake is deferred, without certifying M1/M1B or live readiness.

Authority: [I/O contract](../../plan/IO_CONTRACT_PLAN.md), [data model](../../plan/DATA_MODEL_PLAN.md), [accepted intent](../../plan/A0_USER_INTENT.md).

Internal application interfaces: [ports and adapter ownership](APPLICATION_PORTS_CONTRACT.md) define StateStore, Clock, CalendarSource, EvidenceSource, NotificationSink, Predictor, Solver and Renderer. Typed protocols and no-I/O fakes are runnable; they are not wire schemas, live adapters or a persistent application.

Offline human-input prototype: [guided review](GUIDED_REVIEW_PROTOTYPE.md) displays the full queue, accepts guided text/explicit batches and has a synthetic CLI demo. It creates proposed review responses only; real transport, authentication and persistent commits remain separate.

Offline compatibility baseline: [version admission and cross-contract evolution](CONTRACT_EVOLUTION.md) resolves the 29-schema registry, retains unsupported input bytes and executes five synthetic workflows. It does not freeze the release or turn schema support into write authority.

[Generic Task aggregate](TASK_AGGREGATE_CONTRACT.md) now composes core/effort/time facts with original total estimates, session requirements, stage identity and source pointers. Its new schema raises the current registry to 30 contracts while preserving all 29 earlier schemas and historical evidence.

Carry forward: natural-language direct user commands, external evidence/candidates, full-queue confirmation, consolidated evening review, user-canonical remaining effort for future-relevant incomplete Tasks, and temporary today-only locks. A clear user command can authorize its resolved change; external confidence alone cannot.

Later deliverables: versioned schemas, valid/invalid/edge examples, provenance/deduplication/update semantics, and semantic-vs-provider adapter mapping. Use the [concrete contract tasks](../../plan/tasks/M2_CONTRACTS.md) and [preserved semantic boundaries](../../plan/DEVELOPMENT_PLAN.md#2-frozen-product-invariants) before freezing schemas. Do not reinterpret the empty schema directory as missing A0 product decisions.

---

## Accepted follow-up inputs

The [Task relationship specification](../../plan/TASK_RELATIONSHIP_PLAN.md) covers generation rules and typed completion/start ordering; M2 schemas must distinguish them from parent stages. Canonical source creation may generate mapped targets under accepted rules without repeated instance review.

Review inputs include explicit batch confirmation of listed untouched Tasks' unchanged estimates. Worked-on/changed/missing estimates require their own updates. Time parsing uses Asia/Shanghai and date-only 23:59 while preserving explicit times. Canonical user effort is separate from model-first planning predictions; expiration informs before recording, without an extra acknowledgement requirement.

D-078 fixes 1/3/7-day forecasts to natural days including today in Asia/Shanghai, with 23:59 cutoffs on today / today+2 / today+6. No original experience question remains pending; do not ask for this choice again.

---

## Detailed Execution Mapping

Machine schemas/examples are M2 deliverables; [task-core.schema.json](task-core.schema.json) and its executable synthetic checks are the first development slice. Bounded natural-input/reference resolution remains M3A-21–22. Additional contracts, final release freezes and the full application remain planned; use the indexed development contracts above for the actual implemented scope.
