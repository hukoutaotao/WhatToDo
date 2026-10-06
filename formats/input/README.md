# Input Format Specifications

This directory stores specifications, examples, schemas, and conventions for information entering WhatToDo.

Status: conceptual input semantics accepted in A0; no implemented machine schema exists. M2 finalizes exact encoding and examples after M1/M1B.

Authority: [I/O contract](../../plan/IO_CONTRACT_PLAN.md), [data model](../../plan/DATA_MODEL_PLAN.md), [accepted intent](../../plan/A0_USER_INTENT.md).

Carry forward: natural-language direct user commands, external evidence/candidates, full-queue confirmation, consolidated evening review, user-canonical remaining effort for future-relevant incomplete Tasks, and temporary today-only locks. A clear user command can authorize its resolved change; external confidence alone cannot.

Later deliverables: versioned schemas, valid/invalid/edge examples, provenance/deduplication/update semantics, and semantic-vs-provider adapter mapping. Review open boundaries in [consistency audit](../../plan/CONSISTENCY_AUDIT.md) before freezing schemas. Do not reinterpret the empty schema directory as missing A0 product decisions.

---

## Accepted follow-up inputs

The [Task relationship specification](../../plan/TASK_RELATIONSHIP_PLAN.md) covers generation rules and typed completion/start ordering; M2 schemas must distinguish them from parent stages. Canonical source creation may generate mapped targets under accepted rules without repeated instance review.

Review inputs include explicit batch confirmation of listed untouched Tasks' unchanged estimates. Worked-on/changed/missing estimates require their own updates. Time parsing uses Asia/Shanghai and date-only 23:59 while preserving explicit times. Canonical user effort is separate from model-first planning predictions; expiration informs before recording, without an extra acknowledgement requirement.

The natural-day vs rolling-hour 1/3/7-day horizon subquestion remains pending; no other answered choice should be treated as undecided.
