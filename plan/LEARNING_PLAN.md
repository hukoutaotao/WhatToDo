# WhatToDo — Historical Learning and Behavior Analysis Plan

> Purpose: Define how historical execution data is converted into candidate learned patterns and estimation improvements.
> This module supports, but is separate from, Planner.

## 1. Principle

The Planner should not secretly discover and apply behavioral rules inside its normal planning pass.

Use a separate learning pipeline:

```text
Historical execution/state data
        ↓
Behavior / Estimation Analyzer
        ↓
Numeric calibration → derived prediction → Planner
        +
Candidate behavioral rule → user review → accepted rule → Planner
```

This preserves explainability and user authority.

---

## 2. Goals

The learning system should help improve:

- effort estimates;
- remaining-effort estimates;
- course/task-type duration expectations;
- recognition of chronic underestimation;
- recognition of repeated postponement;
- recognition of time-of-day performance patterns;
- recognition of task-type-specific friction;
- future planning buffers.

It should not require the user to manually score hidden statistical quantities.

---

## 3. Required Historical Data

Conceptually collect:

### Task identity/context
- task ID
- task type
- course/activity
- difficulty dimensions
- importance/requiredness
- release time
- deadline
- course-progress-axis position/range

### Planning observations
- date task appeared in plan
- planned effort
- planned stage/subtask
- available capacity that day
- risk state
- whether task was recommended but not attempted

### Execution observations
- actual effort by day/session
- cumulative actual effort
- first meaningful work time where available
- completion time
- incomplete/complete state
- latest user-confirmed remaining-effort estimate
- contemporaneous model-derived effort prediction where available
- stage/subtask completion

### Context
- time of day
- available block length
- high-intensity/exam phase
- competing required workload
- optional reason for non-completion when captured

Exact schema is deferred until Phase 2.

---

## 4. Estimation Improvement

Potential methods:
- rolling average
- robust median
- recency-weighted average
- per-course/task-type distributions
- difficulty-conditioned estimates
- user-specific bias correction
- prediction intervals / uncertainty bounds

Implementation should favor robustness and interpretability over unnecessary complexity.

The user-facing system does not need to expose all internal statistics.

When the user's current remaining-effort estimate conflicts with the model:
- keep the user's value as canonical personal state;
- keep the model prediction as derived/advisory;
- use disagreement as a possible uncertainty/risk signal;
- do not silently overwrite the user estimate.

---

## 5. Procrastination / Resistance Analysis

Do not infer "procrastination" merely from delay.

A candidate resistance signal should consider:

- time from release to first work;
- repeated plan appearances without progress;
- time from release to completion;
- whether sufficient usable capacity existed;
- whether higher-priority/required work consumed that capacity;
- whether task type shows a repeated pattern across instances.

The analyzer should prefer statements such as:
- "This task type is often postponed despite available capacity"
rather than moralized labels.

---

## 6. Weekly Evaluation

Default cadence:
- weekly evaluation is appropriate.

The analyzer may autonomously compute candidate patterns every week.

The user-facing weekly review should surface only actionable patterns, not all raw statistics. Material rule proposals should support accept / reject / defer.

Examples:
- "Programming LABs have taken 1.6× the original estimate over the last 5 instances."
- "High-thinking tasks scheduled late in the evening have lower completion rates."
- "This task type is repeatedly delayed until less than two days before deadline."

The user may request reevaluation at any time.

---

## 7. User Confirmation Boundary

A statistical observation may be computed automatically.

A learned rule or behavioral interpretation that materially changes Planner behavior should be presented to the user before becoming an accepted planning rule.

Possible states:
- OBSERVED
- CANDIDATE_RULE
- ACCEPTED
- REJECTED
- SUPERSEDED

Examples:

OBSERVED:
- median actual/estimated ratio = 1.42

AUTOMATIC_NUMERIC_MODEL:
- calibrate an internal prediction multiplier for this task type, retaining model version and supporting observations; no per-update behavioral-rule approval is needed

CANDIDATE_RULE:
- prefer daytime for this task type despite a different standing preference

ACCEPTED:
- Planner may use the approved behavioral preference

Changing a user-defined TaskType default is a configuration/policy change requiring review; it is not an internal numeric-model update.

This distinction allows estimation models to improve without silently rewriting user preferences.

---

## 8. Automatic vs Confirmed Adaptation

Allowed automatic adaptation:
- raw statistics
- descriptive aggregates
- internal numeric effort-prediction parameters/models
- numeric prediction outputs, provided they remain testable, inspectable when needed, and correctable

Require user confirmation before:
- changing an explicit user preference
- changing a planning policy
- adopting a behavioral scheduling rule from an observed pattern
- overriding a user-stated time-of-day preference
- adopting a new recurring rule

This authority distinction is fixed by D-054/D-058/D-066. Algorithms, model versioning, and presentation details remain deferred; do not reopen the permission boundary implicitly.

---

## 9. Relationship to Planner

Planner consumes:
- current effort prediction
- automatically calibrated internal numeric parameters/predictions with provenance
- accepted behavioral rules
- historical risk signals

Planner does not own:
- weekly pattern discovery
- statistical aggregation
- user-confirmation workflow for learned rules

---

## 10. Relationship to Data Model

DATA_MODEL_PLAN must support enough history to reconstruct:
- what was planned
- what happened
- what the estimate was at the time
- what capacity was available
- what task context applied

Avoid storing only the latest estimate; retain enough historical snapshots/observations to measure error.

---

## 11. Testing Requirements

Eventually test:
- stable estimates converge on repeated similar tasks
- outliers do not catastrophically distort defaults
- capacity shortage is not automatically mislabeled as procrastination
- rejected learned rules do not affect Planner
- accepted learned rules do affect Planner
- weekly recomputation is reproducible
- historical data changes do not rewrite past observations
- model/user estimate disagreement does not overwrite canonical user state

---

## 12. Current Status

Concept accepted during A0.

Exact algorithms and schemas are deferred until:
- Task model is stable;
- WorkSession/history schema exists;
- enough real usage data is available.

Do not over-engineer the statistical model before real data exists.

---

## 13. Historical Interpretation Limits

Aggregate actual effort without inventing unreported session times. Planned work is not actual execution. Preserve cancelled/expired/reopened history, but distinguish outcome types when estimating completed-task effort: an abandoned task's invested time is not its full completion duration.

Retain estimate-at-planning-time snapshots so future model updates do not rewrite past prediction errors. An updated numeric model may generate estimation-risk warnings; the accepted canonical user estimate remains separate. Exact Planner treatment of disagreement is an open design choice in CONSISTENCY_AUDIT.md.
