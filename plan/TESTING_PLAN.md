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
- urgent large task is advanced before deadline
- minimum session length respected
- daily capacity not exceeded
- SAFE uses approximately one hour of reserve per represented day
- DANGER triggers when REQUIRED work fits but the safety reserve is breached
- EMERGENCY triggers when REQUIRED work exceeds total usable capacity
- in SAFE mode, a ~40-minute-or-smaller residual gap is normally left unscheduled
- 1/3/7-day capacity deficits are detected
- DANGER signals reserve breach; overall EMERGENCY triggers only on an infeasible horizon, not merely an approaching deadline
- task count does not substitute for workload-time calculation
- long-term goal not permanently starved
- SAFE discretionary work uses Task importance after REQUIRED feasibility is protected
- today-only user Task lock affects only the current day
- soft academic prerequisites can be bypassed under REQUIRED-feasibility pressure while hard prerequisites remain enforced
- Course Progress Axis backlog is surfaced
- reopened child stages retain audit history
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

### Alignment Gate A0
- User-AI interaction model is documented and accepted.
- Module information categories and granularity are sufficiently understood for near-term work.
- Cross-module effects are documented.
- Semantic contracts are distinguished from provider adapter contracts.
- Integration-specific unknowns are explicitly deferred instead of guessed.

Additional A0 behavioral acceptance:
- Task is documented as the fundamental planning unit;
- course-level importance is not used as a primary Planner variable;
- importance and requiredness are distinct and deadline does not imply requiredness;
- three difficulty dimensions use 1–5 task-level scales with TaskType defaults;
- Course Progress Axis and Exam coverage semantics are documented;
- learned behavioral rules require confirmation before materially changing Planner;
- numeric effort-prediction parameters may adapt automatically and remain testable/correctable;
- Task importance 1–5 and REQUIRED/OPTIONAL/EXPIRING semantics are represented;
- worst-horizon risk aggregation reports 1/3/7-day states correctly;
- Daily Brief template semantics and 3-day deadline visibility rule are represented;
- morning and evening interaction semantics are recorded;
- uncertainty does not silently mutate trusted state;
- task difficulty can represent the three accepted dimensions;
- task granularity may vary by course/task type;
- planner output does not require exact clock scheduling by default;
- historical actual effort can feed future estimation;
- goal onboarding and completion-confirmation behavior are explicitly represented.

### Phase 1
- Real courses/tasks fit schemas.
- Input examples normalize without ad hoc hacks.
- Output example satisfies user preference.

### Phase 2
- State persists.
- CRUD/state transitions work.
- provenance/audit works.
- confirmation/authority checks prevent unauthorized canonical Task changes.
- pending state, versioned writes, effort snapshots, and minimal staleness/reconciliation persist across restarts.
- simple daily brief generated.

### Phase 3
- Calendar free/busy is correct for representative days.
- recurring and one-off changes work.

### Phase 4
- connectors ingest without duplicates.
- failures preserve prior trusted state.
- newly discovered task-like content remains candidate until user confirmation.
- deadline/progress/completion candidates do not mutate accepted task state without confirmation.
- even strong external submission evidence does not auto-complete a Task in v1.
- repeated polling does not bypass the confirmation boundary.

### Phase 5
- planner respects hard constraints and capacity.
- daily output usable without premium AI.
- planner avoids impossible overfill on representative scenarios;
- planner can distinguish deep-block tasks from fragmentable tasks;
- planner compares 1/3/7-day required effort against available capacity;
- planner triggers risk/emergency behavior on infeasible horizons;
- planner optimizes workload time rather than task count;
- SAFE discretionary work is chosen primarily by Task importance after REQUIRED feasibility/reserve are protected; higher-importance OPTIONAL/EXPIRING work may outrank additional future REQUIRED work;
- overall risk equals the worst 1/3/7-day horizon;
- normal output follows the Daily Brief semantic template and shows deadlines within 3 days;
- parent remaining effort and today's stage estimate are represented;
- history/structured outputs retain the inputs needed for later weekly forward-risk/backlog review; full Weekly Planner output is accepted at Phase 7, not claimed implemented in the daily MVP;
- normal output remains concise while risk/exception scenarios expose useful explanation.

### Phase 6
- model swap/failure does not break canonical system.
- invalid proposals rejected.

### Phase 7
- multi-day inactivity recovery succeeds on realistic fixture.
- historical calibration changes estimates without corrupting history.
- weekly analyzer can reproduce candidate learned patterns from historical fixtures.
- rejected learned rules do not affect Planner.
- accepted learned rules do affect Planner.
- internal numeric estimation can adapt without requiring behavioral-rule approval.
- model prediction disagreement does not overwrite the user-confirmed remaining estimate.
- COMPLETE/CANCELLED/EXPIRED and reopened-stage history remain available for learning.
- capacity-driven delay is not automatically classified as procrastination.
- two-day missed-interaction state can trigger the configured reminder workflow.

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

---

## 9. Cross-Document Regression Scenarios to Define Before Code

- A clear user command commits only its resolved authorized update; no duplicate confirmation is required. Ambiguous references remain pending.
- High-confidence published deadlines and strong submission evidence update source/candidate records without automatically mutating canonical Task facts.
- Internal numeric calibration changes derived predictions without rule approval; it does not rewrite user estimates, TaskType defaults, past snapshots, or explicit preferences.
- Parent 4 h remaining + selected 1 h stage consumes 1 h of today's allocation and represents 4 h total remaining, not 5 h. Conflicting parent/stage estimates are resolved under the M2 contract.
- Each risk inequality is checked at its boundary: C - R = S is SAFE; C - R = 0 is DANGER for positive S; negative is EMERGENCY. Report all three horizons and the worst mode.
- 1-day SAFE + 3-day EMERGENCY enters overall EMERGENCY and the two-round interaction. The baseline is provisional, and the final plan reports any unresolved deficit.
- Removing only OPTIONAL work cannot mathematically fix a negative C - R for REQUIRED work. Daily removal never silently cancels/deletes canonical Tasks.
- S is not subtracted twice. Discretionary allocation respects the reserve; the small-gap policy does not grant authority to fill reserved rest capacity.
- Aggregate hours are sufficient but an early deadline/release/hard dependency/minimum block prevents completion: expose the bottleneck rather than certify a feasible plan. Exact mode aggregation is finalized before the scenario becomes executable.
- Required work beyond 7 days can be advanced to prevent a later bottleneck; importance governs discretionary work once feasibility is protected.
- Review presents the whole confirmation queue, keeps unanswered items pending, and follows up for missing future-relevant remaining effort. A missing interaction never fabricates progress.
- Today-only override respects configured local day boundaries and preserves the distinction between “complete” and “advance”. No server-timezone assumption.
- Course progress with holes in older units produces backlog warnings; latest/max unit alone cannot erase the holes.
- Repeated conditional/Goal generation is idempotent and follows the authority contract resolved in M2. Trigger detection itself does not constitute acceptance.
- Time passing a deadline does not automatically cancel/expire REQUIRED work. Expiration handling follows the explicit permission contract; raw source deletion does not delete Tasks.
- Completed/cancelled/expired/reopened outcomes retain relevant history; raw-content minimization can coexist with retained semantic audit records.

These are planned acceptance cases, not executed runtime tests. Unresolved edges in CONSISTENCY_AUDIT.md must be settled before pinning an exact expected behavior. The current audit verifies documents/references and requirement propagation only.
