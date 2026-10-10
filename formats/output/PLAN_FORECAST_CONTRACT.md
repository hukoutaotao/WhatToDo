# Plan and forecasts — development draft 0.1.0

Scope: [M2-10.a](../../plan/tasks/M2_CONTRACTS.md#m2-10a). [Output schema](plan.schema.json), [forecast helpers](../../src/domain/forecast.py), [Plan handoff](../../src/domain/plan_output.py), [synthetic cases](../../tests/fixtures/forecast_plan/cases.json) and [tests](../../tests/test_forecast_plan.py). Human sections remain governed by the [Daily Brief template](DAILY_BRIEF_TEMPLATE.md).

## Scoped accounting and risk

Each forecast retains the same state snapshot, exact 1/3/7-day natural window, availability quality, effective parent budgets, required-work projection and hard-constraint snapshot reference. Counts use exact rational seconds. C excludes configured occupancy/no-work/buffers; S remains 3,600 seconds per represented day, never proportionally reduced or subtracted into C. R uses selected model-first B with preserved canonical U, not U+B.

FULL_DUE counts all of an active REQUIRED parent's remaining B. NECESSARY_EARLY counts a derived part of longer-horizon work with projection provenance. HARD_PREREQUISITE can protect REQUIRED dependent work without changing the prerequisite's original requiredness. One parent appears once per horizon; identical replay deduplicates and differing allocations/revisions require resolution. Projection generation, deadline/release/minimum-session reasoning and long-horizon coordination remain the later Planner/oracle responsibility. This module does not invent those allocations.

Placement evidence binds a SHA256 fingerprint of window, availability, budgets/projections and hard-constraint reference. Evidence must match the current input and calculation time. Trusted FEASIBLE/INFEASIBLE outcomes carry a witness/proof reference; TIMEOUT/UNKNOWN/ERROR are not infeasibility proofs. This draft does not implement an exact solver or verify the truth of an opaque witness reference; the later trusted Solver port must supply that guarantee.

For complete current input, negative C-R proves an aggregate EMERGENCY without requiring a successful solver run. A bound hard-placement infeasibility proof also establishes EMERGENCY despite positive margin. Proven feasible placement permits SAFE when C-R >= S and DANGER otherwise. Unknown/stale facts, missing canonical-estimate review or invalid/conflicting evidence retain null risk and separate quality/verification diagnostics. Missing knowledge is not a fourth risk label.

The three horizons overlap and are never summed. Overall risk uses the worst known result; a proven emergency remains visible when another horizon is unresolved, while an unresolved horizon prevents a complete SAFE/DANGER claim. `safe_discretionary_budget` protects R and reserve, then leaves an aggregate daily remainder <=2,400 seconds free. It does not prohibit each short fragment or implement selection/minimum-session policy.

## Recommendations and single-count allocations

The Plan task catalogue carries parent budget, requiredness and optional exact stage partition. Counted daily allocations refer to that current catalogue and contain concrete objective/work-style information. Plan section items reference allocation IDs; repeated navigation references add no effort. Allocations cannot exceed parent B or the selected stage quota, mix parent and stage representations as new work, refer to stale revisions or remain without a concrete recommendation.

PROTECT_TODAY, ADVANCE and OPTIONAL_ADDON are presentation roles, not replacements for REQUIRED/OPTIONAL/EXPIRING. Fixed events retain their Calendar meaning and ownership. Normal/final selections cannot exceed known daily capacity. These checks are necessary output/accounting checks, not sufficient proof of a feasible recommendation placement; the actual allocator/solver must still verify hard relations, session constraints, locks, reserve and protected work. Default output carries objectives without demanding an exact timetable.

## Emergency rounds and authority handoff

An emergency with no completed second-round evidence is PROVISIONAL_EMERGENCY. Unknown normal results are UNVERIFIED. FINAL_EMERGENCY needs an independently retrieved `CompletedEmergencyReview`, its committed complete review/user choices, prior-plan reference and current recomputed snapshot, plus known recomputed horizon risks. A recovered SAFE result can still be the final emergency-day output; residual EMERGENCY deficits remain visible.

The review class is a trusted application handoff, not a constructor proving authentication or a JSON string granting authority. The application must load the committed complete review and recomputation records and verify those references. No user reply, partial response, optional-item omission or fake reference alone completes this workflow. Removing an item neither cancels its canonical Task nor reduces REQUIRED R by itself.

## Execution and remaining scope

```powershell
python -m unittest discover -s tests -p 'test_forecast_plan.py' -v
python -m tools.check_contracts --examples tests/fixtures/forecast_plan/cases.json
```

The schema checks shape; typed helpers check scoped arithmetic/allocations using trusted records. No personal Plan, real exact oracle/solver, projection generator, authenticated emergency interaction, renderer, persistent snapshot or Calendar write is enabled. All evidence and records in the tests are synthetic.
