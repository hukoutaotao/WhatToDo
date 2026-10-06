# WhatToDo — Testing and Quality Plan

## 1. Goal

Testing must verify not only code correctness but also state safety and planning realism.

Never report a capability as verified solely because code exists or CI passes.

---

## 2. Test Layers

### Unit tests
For:
- date/time functions
- priority calculations
- normalization
- validators
- state transitions
- deduplication

### Contract/schema tests
For:
- normalized inputs
- output plans
- AI proposals
- connector payloads

### Integration tests
For:
- PostgreSQL
- n8n-to-service calls
- Calendar connector
- email connector
- learning-platform connector

### Replay/fixture tests
Use captured/redacted representative source payloads to reproduce:
- deadline changes
- cancellations
- duplicates
- ambiguous messages
- recurring events

### End-to-end tests
For milestone acceptance:
```text
source/input
→ state
→ planner
→ daily brief
```

---

## 3. Planner Regression Tests

Create scenarios with expected invariants:
- no overlap with fixed event
- urgent large task starts before deadline
- minimum session length respected
- daily capacity not exceeded
- long-term goal not permanently starved
- stale state blocks false precision

Do not overfit tests to one exact schedule when multiple schedules are acceptable.
Test invariants and quality constraints.

---

## 4. AI Tests

Test:
- valid structured result
- malformed JSON/schema
- hallucinated task ID
- stale snapshot
- contradictory proposal
- provider timeout
- low confidence
- malicious instructions contained in external source text

AI output must fail closed on unsafe mutation.

---

## 5. Connector Tests

Every connector should test:
- first sync
- repeated sync idempotency
- changed source
- deleted/cancelled source
- pagination
- auth failure
- rate limit/transient failure
- duplicate prevention
- timezone handling

---

## 6. Data Migration Tests

Once PostgreSQL exists:
- forward migration
- fresh database setup
- representative existing-data migration
- backup/restore verification before calling recovery ready

---

## 7. Phase Acceptance Gates

### Phase 1
- Real courses/tasks fit schemas.
- Input examples normalize without ad hoc hacks.
- Output example satisfies user preference.

### Phase 2
- State persists.
- CRUD/state transitions work.
- provenance/audit works.
- simple daily brief generated.

### Phase 3
- Calendar free/busy is correct for representative days.
- recurring and one-off changes work.

### Phase 4
- connectors ingest without duplicates.
- failures preserve prior trusted state.

### Phase 5
- planner respects hard constraints and capacity.
- daily output usable without premium AI.

### Phase 6
- model swap/failure does not break canonical system.
- invalid proposals rejected.

### Phase 7
- multi-day inactivity recovery succeeds on realistic fixture.
- historical calibration changes estimates without corrupting history.

---

## 8. Verification Language

Use:
- Planned
- Implemented
- Tested
- Verified locally
- Verified in production/runtime

Do not collapse these into "done."

Update PROGRESS.md with the strongest actually demonstrated state.
