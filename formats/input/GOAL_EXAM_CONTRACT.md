# Goal, milestone and Exam — development draft 0.1.0

Scope: [M2-09.a](../../plan/tasks/M2_CONTRACTS.md#m2-09a). Schemas: [Goal configuration](goal.schema.json), [onboarding assessment](goal-onboarding.schema.json), [progress observation](goal-progress.schema.json), [milestone](milestone.schema.json) and [Exam](exam.schema.json). Implementation: [pure helpers](../../src/domain/goals.py); evidence: [synthetic cases](../../tests/fixtures/goals/cases.json), [tests](../../tests/test_goals.py).

## Setup and generation boundaries

A Goal configuration preserves outcome, total workload or measured target, explicit horizon knowledge, cadence, phases, progress measurement and generation-rule choice. Unknown fields remain null; explicitly no due date, recurring cadence or phases differs from an unanswered question. Quantities use exact nonnegative decimal strings and explicit units. Goal workload is a configuration/measurement value, not canonical Task remaining effort.

`assess_onboarding` identifies every missing setup field and whether the complete configuration has accepted provenance. A partial setup cannot be labeled complete accepted onboarding. A known empty generation-rule list selects candidate-only suggestions; nonempty stable/versioned references require registry/scope/authority resolution. Neither an acceptance-reference string nor a rule-reference list grants automatic generation authority. Custom cadence descriptions retain user meaning but are not executable recurrence definitions.

These generic checks support later guided Goal setup without collecting any real Goal now. Actual activation still needs reviewed M5B-01 intake, resolved trigger/template/field mappings and the ordinary scoped generation mechanism. The canonical-Task creation rule draft is not silently extended to execute Goal/Exam triggers.

## Measurements and checkpoints

Goal progress is a separate source-backed observation bound to Goal/revision, unit and observation time. `measured_target_fraction` calculates an exact ratio when quantities are compatible; it never infers completion from reaching/exceeding the target or adds separate observations as new increments. Zero targets and absent/qualitative measurements yield no invented ratio. Explicit reported outcome/completion remains separate; no underlying Task is completed through this function.

Milestones are version-bound checkpoints with optional phase/target/due references. Phase and milestone IDs/positions must be unique. `validate_milestones` diagnoses stale Goal scope or unresolved phase links without modifying history. Goals and milestones introduce no extra Planner budget: their actual work remains ordinary generated Tasks, whose parent/stage accounting is supplied by the effort module.

## Independent Exam events

An Exam is an independent event/context record, with optional course and explicit axis/version/unit coverage references. UNKNOWN timing and DATE_ONLY timing preserve absence of a concrete interval. A date-only Exam is not a Task deadline and does not become an exam starting at 23:59. EXACT_EVENT preserves the source interval and timezone. Coverage IDs require the later course-axis registry to verify semantic order/range; strings alone cannot prove known coverage.

Exam configuration carries no Task completion, U or duplicated workload. Preparation phases generate ordinary Tasks under independently accepted mappings. Updating/removing external Exam evidence cannot cancel existing preparation Tasks through these pure helpers.

## Execution and remaining handoff

```powershell
python -m unittest discover -s tests -p 'test_goals.py' -v
python -m tools.check_contracts --examples tests/fixtures/goals/cases.json
```

Schemas validate structure; typed helpers check setup, exact quantities and scope. No actual Goal intake, canonical Goal mutation, persistent observation/replay repository, recurrence expansion, rule/axis resolution, real Exam calendar entry or automatic preparation generator is enabled. Every fixture is synthetic.
