# WhatToDo — Testing and Quality Plan

> Execution: [detailed development plan](DEVELOPMENT_PLAN.md) · [live progress](PROGRESS.md).
> Bounded work: [M2_CONTRACTS](tasks/M2_CONTRACTS.md) · [M3_STATE_FOUNDATION](tasks/M3_STATE_FOUNDATION.md) · [M3_RELATIONSHIPS_REVIEWS](tasks/M3_RELATIONSHIPS_REVIEWS.md) · [M6_PLANNER_DAILY_MVP](tasks/M6_PLANNER_DAILY_MVP.md) · [M8_LEARNING_RELEASE_OPERATIONS](tasks/M8_LEARNING_RELEASE_OPERATIONS.md).

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
- in SAFE, aggregate whole-day discretionary remainder <=40 minutes after required work/reserve is left free; it is not a per-window ban
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
- external newly discovered task-like content remains candidate until user confirmation; mapped counterpart creation under a preapproved generation relationship is separately authorized (D-072).
- external deadline/progress/completion candidates do not mutate accepted task state without confirmation; generation/expiration exceptions are limited to D-072/D-073 and never auto-complete Tasks.
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
- Effective parent planning budget B=4 h + selected 1 h stage consumes 1 h today and represents 4 h forecast workload, not 5 h. If the user says U=4 h and model predicts B=6 h, use 6 h for planning, retain U=4 h separately, and never count 10 h. Conflicting parent/stage estimates follow DATA_MODEL_PLAN Section 12: effective B controls forecast totals, derived stage budgets are separate, and accepted contradictions that affect planning are surfaced.
- Each risk inequality is checked at its boundary: C - R = S is SAFE; C - R = 0 is DANGER for positive S; negative is EMERGENCY. Report all three horizons and the worst mode.
- 1-day SAFE + 3-day EMERGENCY enters overall EMERGENCY and the two-round interaction. The baseline is provisional, and the final plan reports any unresolved deficit.
- Removing only OPTIONAL work cannot mathematically fix a negative C - R for REQUIRED work. Daily removal never silently cancels/deletes canonical Tasks.
- S is not subtracted twice. Discretionary allocation respects the reserve; the small-gap policy does not grant authority to fill reserved rest capacity.
- Aggregate hours are sufficient but an early deadline/release/hard dependency/minimum block prevents completion: expose the bottleneck rather than certify a feasible plan. A proven hard placement deficit is EMERGENCY; a heuristic/solver timeout is incomplete verification rather than proof of infeasibility (PLANNER_PLAN Section 21).
- Required work beyond 7 days can be advanced to prevent a later bottleneck; importance governs discretionary work once feasibility is protected.
- Review presents the whole confirmation queue, keeps unanswered items pending, and follows up for missing future-relevant remaining effort. A missing interaction never fabricates progress.
- Today-only override respects configured local day boundaries and preserves the distinction between “complete” and “advance”. No server-timezone assumption.
- Course progress with holes in older units produces backlog warnings; latest/max unit alone cannot erase the holes.
- Repeated conditional/Goal generation is idempotent under the accepted relationship rule scope; unaccepted/raw trigger evidence does not authorize canonical creation. Template defaults alone are not permission.
- Time passing a deadline does not automatically cancel/expire REQUIRED work. EXPIRING follows notify-before-record under its confirmed condition, without a new acknowledgement; raw source deletion does not delete Tasks.
- Completed/cancelled/expired/reopened outcomes retain relevant history; raw-content minimization can coexist with retained semantic audit records.

These are planned acceptance cases, not executed runtime tests. Original audit boundaries are resolved and preserved in DEVELOPMENT_PLAN Sections 2/13. New genuine semantic conflicts must be resolved for the affected fixture. The current planning deliverable verifies document/task-plan consistency only; the per-task catalogs define later executable checks.

---

## 10. Resolved Internal-Boundary Acceptance Cases

O03 refined by D-074: effective B=4 h with weights 1:3 produces stage budgets 1 h and 3 h; if U=4 h and model B=6 h, stage budgets are 1.5 h and 4.5 h with 6 h total forecast work, while U remains 4 h. An updated effective parent planning budget recomputes derived allocations while preserving historical model and user estimates. User-confirmed stage rework updates the stage and same parent consistently in one audit transaction; ambiguous follow-up meaning stays pending. Conflicting user estimates are preserved and reconciled when material, never silently overwritten.

O06: a 7-day total-capacity surplus cannot hide an impossible first-day deadline or minimum-session constraint. Confirm feasible placement before applying reserve margins. Early required allocation for a distant deadline is derived once from the longer projection. An exact infeasibility result differs from a heuristic failure/timeout. These are specification acceptance cases; no executable Planner exists yet.

---

## 11. Accepted Follow-Up Regression Cases

- Canonical Task 1 creation under an accepted generation rule produces exactly one mapped Task 2 across retries; raw unaccepted discovery does not trigger canonical cascades. Missing essential mapping facts remain pending.
- Task 1 → generates Task 2 and Task 2 → completes before Task 1 are a valid combination in distinct graphs. Reject true uncontrolled generation loops/hard-order cycles, not that valid pair.
- Finish-before-finish permits Task 1 to start earlier; finish-before-start does not. Hard relations affect feasible recommendations; truthful confirmed out-of-order completion is recorded with a violation, never rejected/fabricated.
- Distinguish generated separate obligations from stages. Separate Tasks contribute their own B once each; stages partition one B. Cancellation/reopening does not silently propagate to counterparts.
- EXPIRING reaches an accepted condition: user-facing notice dispatch precedes canonical EXPIRED. Delivery failure keeps transition pending; no acknowledgement is required; uncertain conditions require clarification. Normal history remains, and expiration never implies COMPLETE.
- U=2 h, model B=4 h: allocate/forecast using 4 h and keep U=2 h. U=4 h, model B=2 h: use 2 h, not max=4 h. No valid prediction: fall back to U with source/diagnostic metadata. A total-task prediction is not accepted as remaining work without the appropriate interpretation.
- Asia/Shanghai is the user planning timezone regardless of server locale. Date-only deadline maps to local 23:59 with default provenance; explicit 18:00 stays 18:00; explicit other-zone instant is preserved. Today-only override expires at next Beijing midnight, not default task cutoff.
- After required work/reserve, discretionary aggregate 40 minutes in SAFE stays free; aggregate 60 minutes in three 20-minute windows may use fragmentable work. A single 30-minute window is not automatically excluded when day's aggregate is larger. Reserve is subtracted once.
- Evening batch “keep previous estimates” confirms only the listed untouched unchanged Tasks, with per-Task provenance and retained original estimate time. Worked-on/new/missing/changed estimates and ambiguous completion remain individual review; silence confirms nothing.
- D-078 selects natural-day windows including today; fixtures enforce today / today+2 / today+6 at 23:59 Asia/Shanghai, remaining-only capacity, and the existing reserve. Schema/library choice remains engineering work rather than an unanswered experience decision.

These are planned conceptual acceptance cases. No runtime tests ran, because this repository remains documentation only.

---

## 12. Natural-Day Window Acceptance Cases

- At a Beijing-time snapshot of 2026-10-06 15:00, the 1/3/7-day cutoffs are 2026-10-06 / 2026-10-08 / 2026-10-12 at 23:59. They are not 2026-10-07 / 09 / 13 at 15:00. Today counts as day 1.
- Intraday C excludes elapsed portions of today, past sessions, and occupied windows; numerical model remaining-work budget B and user effort U retain their separate provenance. The reserve defaults remain 1/3/7 hours per represented-day policy, with no silent proportional discount.
- At 2026-10-06 16:01 UTC, the Beijing anchor date is 2026-10-07; 1/3/7-day cutoffs become October 7 / 9 / 13 at 23:59 regardless of server timezone. At a Beijing anchor of 2026-12-31, the cutoffs are 2026-12-31 / 2027-01-02 / 2027-01-06 at 23:59; month/year rollover uses local calendar arithmetic.
- A date-only Task deadline follows the accepted 23:59 default; explicit 18:00 and explicit other-zone instants stay intact. Forecast boundaries do not rewrite actual Task deadlines or today-lock expiry.
- Windows overlap and are not summed. Preserve deadline-prefix feasibility, necessary early work for deadlines beyond day 7, and worst-horizon mode. O05 is resolved; do not label these fixtures as awaiting user approval.

These are conceptual acceptance cases, not executed runtime tests.

---

## Detailed Execution Mapping

Each card defines focused acceptance. M3A-20 adds isolated CI; PostgreSQL/fault/oracle/offline/live/restore evidence remain distinct, not inferred from document presence.
