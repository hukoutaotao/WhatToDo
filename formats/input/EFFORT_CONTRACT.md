# Effort and observations — development draft 0.1.0

Scope: [M2-02.a](../../plan/tasks/M2_CONTRACTS.md#m2-02a). [Effort snapshot schema](effort.schema.json), [work-observation schema](work-observation.schema.json), [pure module](../../src/domain/effort.py), [synthetic schema cases](../../tests/fixtures/effort/cases.json) and [regression tests](../../tests/test_effort.py).

## Representation and selection

Durations are nonnegative integer seconds. User remaining estimate U retains observation identity, original observation time and separate verification time. Remaining predictions retain identity, model version, task revision, computation/validity times and explicit validity/applicability. Timestamps require offsets and real calendar dates. The pure value constructors also enforce chronological ordering.

`select_budget` returns an immutable derived snapshot. An applicable valid prediction for the current task revision supplies B even below U; otherwise U supplies USER_FALLBACK with a reason. Predictions computed in the future, expired at the snapshot, invalid, inapplicable or tied to another revision are excluded. The prediction validity interval is `[computed_at, valid_until)`. These are explicit model metadata, not an invented validity duration or user preference. No valid B/U produces UNKNOWN, not zero. Missing U remains review-pending even if a valid model allows provisional forecasting.

EXPIRED/CANCELLED history returns NOT_ACTIVE and no selected active workload while retaining U. A confirmed COMPLETE task needs explicit zero U and supplies zero derived work. An incomplete task with a zero estimate remains incomplete; estimates never confirm completion. Neither elapsed work nor a date boundary decrements U.

## Parent and stage accounting

`partition_stages` partitions B across unfinished stages using positive, accepted weights. Exact Fraction arithmetic avoids dropping work through rounding; consumers choose final display/scheduling precision later. Unknown weights retain parent-only planning with a diagnostic, not invented equal user estimates. Completed stages get no unfinished allocation; all completed stages do not imply the parent is complete. Reopened stages are new immutable values, preserving the former state.

Canonical user stage estimates remain separate. Their known total may disagree with parent U; the result reports that fact without scaling either user's value or creating a reconciliation command. `sum_obligations` deduplicates identical parent references, rejects conflicting snapshots, adds distinct generated obligation IDs, excludes inactive history and reports missing active budgets explicitly. StageAllocation values are rejected by the parent-total function to prevent parent-plus-stage counting.

## Observations and authority

WorkObservation supports separately confirmed USER_REMAINING values, ACTUAL_WORK increments and UNCHANGED_VERIFICATION records. ACTUAL_WORK means newly reported work seconds for this observation, not a cumulative total silently treated as another increment. Parsing cumulative self-reports/work-session intervals remains a later source/application contract; callers must not label them as increments without a resolved meaning.

Unchanged verification carries a batch reference and no new numerical value; it is not evidence of work or a new estimate observation. `append_observation` returns a new immutable tuple, treats exact replay as the same observation and rejects identity conflicts. `actual_seconds` counts unique actual increments only. Neither function updates a user estimate or marks the parent complete.

Source/authority references here preserve traceability, but schema success and pure constructors do not prove authorization or resolve batch membership. Actual writes, explicit corrections, rework transactions and reference/version checks remain application/persistence work. No personal profile or live Task is imported.

## Run

```powershell
python -m unittest discover -s tests -p 'test_*.py' -v
python -m tools.check_contracts --examples tests/fixtures/effort/cases.json
python -m tools.check_contracts --contract effort path/to/snapshot.json
```

The shared [contract-check dependency](../../requirements-contracts.txt) includes the RFC3339 checker so date-time validation is enabled rather than a silent annotation. The final application toolchain and complete Task freeze remain separate. This slice's tests cover model-above/below-user, stale/invalid/missing models, missing/future U, truthful expired history, exact stage partitions, unknown weights, stage rework, canonical disagreement, repeated/separate obligations, immutable replay and observation separation.
