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
Candidate learned pattern
        ↓
User review
        ↓
Accepted parameter/rule
        ↓
Planner
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
- latest remaining-effort estimate
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

CANDIDATE_RULE:
- multiply future default estimate for this task type by 1.35

ACCEPTED:
- Planner may use this multiplier

This distinction allows estimation models to improve without silently rewriting user preferences.

---

## 8. Automatic vs Confirmed Adaptation

Potentially safe automatic updates:
- raw statistics
- descriptive aggregates
- model prediction outputs used as advisory estimates, if the user can inspect/correct them

Require user confirmation before:
- changing an explicit user preference
- changing a planning policy
- labeling a persistent behavioral pattern in a way that affects scheduling
- overriding a user-stated time-of-day preference
- adopting a new recurring rule

Exact boundary may be refined later.

---

## 9. Relationship to Planner

Planner consumes:
- current effort prediction
- accepted calibration parameters
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

---

## 12. Current Status

Concept accepted during A0.

Exact algorithms and schemas are deferred until:
- Task model is stable;
- WorkSession/history schema exists;
- enough real usage data is available.

Do not over-engineer the statistical model before real data exists.
