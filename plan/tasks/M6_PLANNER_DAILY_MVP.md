# WhatToDo — Deterministic Planner and daily operating loop

> Status: executable development specification; every task initially TODO. No task is implemented by this file.
> Task scope: one bounded AI execution per task or explicitly repeated instance.

[Development plan and execution rules](../DEVELOPMENT_PLAN.md) · [Live progress](../PROGRESS.md)

## Required sources

- [PLANNER_PLAN.md](../PLANNER_PLAN.md)
- [DATA_MODEL_PLAN.md](../DATA_MODEL_PLAN.md)
- [IO_CONTRACT_PLAN.md](../IO_CONTRACT_PLAN.md)
- [TASK_RELATIONSHIP_PLAN.md](../TASK_RELATIONSHIP_PLAN.md)
- [TESTING_PLAN.md](../TESTING_PLAN.md)

Read the source sections relevant to the chosen task, its completed prerequisite artifacts, and the shared Definition of Done before editing. Source documents control meaning; this catalog controls work decomposition. Proposed artifact paths below are logical scopes until M2-16 freezes the language-specific mapping. An adapter/schema described here does not yet exist.

## Gate: M6-29

Task order is constrained by explicit dependencies, not by credentials for unrelated live integrations. A VERIFY task runs the smallest meaningful fixture/integration set for its boundary and records actual evidence. Repeated tasks are one course/family/account/layout/playbook per execution; a template dependency means the required instance set described in the development plan.

## Tasks

### M6-01

**Build one consistent planning snapshot**

- Type: `DEV`. Initial status: `TODO`.
- Prerequisites: [M4-16](M4_CALENDAR_CAPACITY.md#m4-16) · [M5-20](M5_INGESTION_N8N.md#m5-20) · [M5B-11](M5B_GOALS_GENERATION.md#m5b-11)
- Deliverable / bounded file scope: versioned planning snapshot service.
- Work: Read canonical Tasks, relations, models, availability and rules consistently; store all source versions and data-quality/finite-generation coverage. Include current scoped user locks/constraints from M3B-17–18 as snapshot inputs, not late appended recommendations.
- Acceptance / failure and extension checks: Concurrent writes cannot mix incompatible aggregate versions; snapshot can be replayed without providers; stale/unknown input is not a precision-safe guarantee.
- Completion evidence: artifact paths + exact targeted command/check or user-source reference + observed result + remaining limitations, recorded in PROGRESS. Do not mark done from code presence alone.

### M6-02

**Select model-first effective budgets**

- Type: `DEV`. Initial status: `TODO`.
- Prerequisites: [M6-01](M6_PLANNER_DAILY_MVP.md#m6-01)
- Deliverable / bounded file scope: effective effort selection module.
- Work: Use applicable valid remaining-work model B, otherwise canonical U with fallback provenance; retain U independently and reject total-duration misuse.
- Acceptance / failure and extension checks: U=2/B=4 selects 4; U=4/B=2 selects 2; unavailable prediction falls back to U; no max(U,B), U+B or fabricated valid prediction.
- Completion evidence: artifact paths + exact targeted command/check or user-source reference + observed result + remaining limitations, recorded in PROGRESS. Do not mark done from code presence alone.

### M6-03

**Allocate parent budgets into stage chunks**

- Type: `DEV`. Initial status: `TODO`.
- Prerequisites: [M6-02](M6_PLANNER_DAILY_MVP.md#m6-02)
- Deliverable / bounded file scope: derived stage/session allocation module.
- Work: Partition B across unfinished stages using accepted weights, retain separate user observations and session constraints; handle missing weights transparently.
- Acceptance / failure and extension checks: B=6 with 1:3 yields 1.5/4.5 once; no parent+stage sum; material accepted-estimate contradiction remains visible rather than overwriting facts.
- Completion evidence: artifact paths + exact targeted command/check or user-source reference + observed result + remaining limitations, recorded in PROGRESS. Do not mark done from code presence alone.

### M6-04

**Classify deadline, expiry and actionable state**

- Type: `DEV`. Initial status: `TODO`.
- Prerequisites: [M6-01](M6_PLANNER_DAILY_MVP.md#m6-01) · [M6-03](M6_PLANNER_DAILY_MVP.md#m6-03)
- Deliverable / bounded file scope: task eligibility/risk classification.
- Work: Distinguish active/blocked/overdue/no-longer-useful/expired/completed Tasks and exact releases/deadlines. Pending expiry notice may inform derived usefulness only.
- Acceptance / failure and extension checks: Overdue REQUIRED remains visible; raw expiry detection does not claim canonical EXPIRED; no blocked existing Task is treated as nonexistent.
- Completion evidence: artifact paths + exact targeted command/check or user-source reference + observed result + remaining limitations, recorded in PROGRESS. Do not mark done from code presence alone.

### M6-05

**Build required-work obligation set**

- Type: `DEV`. Initial status: `TODO`.
- Prerequisites: [M6-04](M6_PLANNER_DAILY_MVP.md#m6-04)
- Deliverable / bounded file scope: required-work/dependency projection.
- Work: Include required work and necessary hard prerequisites with separate counterpart accounting; preserve deadlines and relevant available windows.
- Acceptance / failure and extension checks: Generated separate obligations count once each; soft academic sequence is not promoted to hard by default; source origin grants no automatic priority.
- Completion evidence: artifact paths + exact targeted command/check or user-source reference + observed result + remaining limitations, recorded in PROGRESS. Do not mark done from code presence alone.

### M6-06

**Project necessary early work beyond day 7**

- Type: `DEV`. Initial status: `TODO`.
- Prerequisites: [M6-05](M6_PLANNER_DAILY_MVP.md#m6-05)
- Deliverable / bounded file scope: bounded longer-horizon workload projection.
- Work: Prepare one coordinated bounded longer-horizon workload model and sound necessary-early-work lower bounds from later capacity/deadline/release constraints. Carry coverage/provenance into the Solver; lower bounds alone are not a complete feasibility certificate.
- Acceptance / failure and extension checks: Distant work with insufficient later capacity contributes necessary early work once; its whole B is not counted as due today. Missing future capacity is explicit; final placement/projection certification belongs to M6-10, not a premature SAFE result.
- Completion evidence: artifact paths + exact targeted command/check or user-source reference + observed result + remaining limitations, recorded in PROGRESS. Do not mark done from code presence alone.

### M6-07

**Build a small exact feasibility oracle**

- Type: `DEV`. Initial status: `TODO`.
- Prerequisites: [M6-05](M6_PLANNER_DAILY_MVP.md#m6-05)
- Deliverable / bounded file scope: tests/fixtures/planner exact oracle.
- Work: For bounded synthetic integer-time cases, enumerate/solve feasible work placement independently enough to check production heuristics, with deliberate infeasible cases.
- Acceptance / failure and extension checks: Oracle detects early-deadline and continuity deficits despite aggregate surplus; fixture bounds prevent combinatorial runaway; timeout is not proof of infeasibility.
- Completion evidence: artifact paths + exact targeted command/check or user-source reference + observed result + remaining limitations, recorded in PROGRESS. Do not mark done from code presence alone.

### M6-08

**Select bounded production feasibility approach**

- Type: `SPIKE`. Initial status: `TODO`.
- Prerequisites: [M6-06](M6_PLANNER_DAILY_MVP.md#m6-06) · [M6-07](M6_PLANNER_DAILY_MVP.md#m6-07)
- Deliverable / bounded file scope: solver ADR and executable benchmark.
- Work: Compare at most two suitable deterministic approaches against the oracle; select a replaceable Solver port implementation with result/proof/time-limit semantics.
- Acceptance / failure and extension checks: Feasible/infeasible/unknown outcomes are explicit; heuristic failure cannot become EMERGENCY proof; selected libraries/versions are verified against current primary docs when implemented.
- Completion evidence: artifact paths + exact targeted command/check or user-source reference + observed result + remaining limitations, recorded in PROGRESS. Do not mark done from code presence alone.

### M6-09

**Implement hard temporal relationship constraints**

- Type: `DEV`. Initial status: `TODO`.
- Prerequisites: [M6-08](M6_PLANNER_DAILY_MVP.md#m6-08)
- Deliverable / bounded file scope: solver relationship constraint module.
- Work: Enforce finish-before-finish separately from explicit finish-before-start; respect release times, task continuity and configured endpoints.
- Acceptance / failure and extension checks: Task 1 may start before Task 2 under finish-before-finish; a stronger start prerequisite blocks it; contradictory order is diagnosed without inventing completion timestamps.
- Completion evidence: artifact paths + exact targeted command/check or user-source reference + observed result + remaining limitations, recorded in PROGRESS. Do not mark done from code presence alone.

### M6-10

**Implement deadline/window/minimum-session feasibility**

- Type: `DEV`. Initial status: `TODO`.
- Prerequisites: [M6-09](M6_PLANNER_DAILY_MVP.md#m6-09)
- Deliverable / bounded file scope: production feasibility evaluator.
- Work: Place required work in actual usable intervals with indivisibility/minimum-session constraints and deadline-prefix checks; return certificate/diagnostic outcome. Finalize coordinated longer-horizon placement and necessary early allocation evidence from M6-06; enforce normalized current user locks before daily allocation.
- Acceptance / failure and extension checks: Early deadline deficit and many short windows for one continuous task are proven infeasible; known oracle-feasible cases remain feasible; timeout remains unknown.
- Completion evidence: artifact paths + exact targeted command/check or user-source reference + observed result + remaining limitations, recorded in PROGRESS. Do not mark done from code presence alone.

### M6-11

**Compute natural-day C/R/S and horizon modes**

- Type: `DEV`. Initial status: `TODO`.
- Prerequisites: [M6-06](M6_PLANNER_DAILY_MVP.md#m6-06) · [M6-10](M6_PLANNER_DAILY_MVP.md#m6-10)
- Deliverable / bounded file scope: 1/3/7-day risk module.
- Work: Compute each overlapping calendar horizon separately from snapshot remaining capacity, counted required work and 1/3/7-hour reserves; apply feasibility before margin labels.
- Acceptance / failure and extension checks: C-R=S is SAFE; C-R=0 is DANGER for positive S; negative/proven placement deficit is EMERGENCY; no double reserve subtraction or forecast summing.
- Completion evidence: artifact paths + exact targeted command/check or user-source reference + observed result + remaining limitations, recorded in PROGRESS. Do not mark done from code presence alone.

### M6-12

**Implement worst-horizon and data-quality output**

- Type: `DEV`. Initial status: `TODO`.
- Prerequisites: [M6-11](M6_PLANNER_DAILY_MVP.md#m6-11)
- Deliverable / bounded file scope: overall mode/quality reporting.
- Work: Select worst known risk, carry placement/estimation/stale/unknown diagnostics separately and disclose incomplete proof/data coverage.
- Acceptance / failure and extension checks: 1-day SAFE plus 3-day EMERGENCY yields overall EMERGENCY; unknown input does not become a fourth accepted risk state or falsely precise SAFE.
- Completion evidence: artifact paths + exact targeted command/check or user-source reference + observed result + remaining limitations, recorded in PROGRESS. Do not mark done from code presence alone.

### M6-13

**Allocate required protection and reserve**

- Type: `DEV`. Initial status: `TODO`.
- Prerequisites: [M6-12](M6_PLANNER_DAILY_MVP.md#m6-12)
- Deliverable / bounded file scope: daily protected allocation module.
- Work: Derive work necessary today for feasible obligations and retain the accepted reserve when possible; surface conflicts rather than force impossible blocks.
- Acceptance / failure and extension checks: Long-horizon early work is included once; fixed occupancy is never overlapped; DANGER/EMERGENCY reserve use is explicit rather than a silent policy change.
- Completion evidence: artifact paths + exact targeted command/check or user-source reference + observed result + remaining limitations, recorded in PROGRESS. Do not mark done from code presence alone.

### M6-14

**Allocate discretionary capacity by importance**

- Type: `DEV`. Initial status: `TODO`.
- Prerequisites: [M6-13](M6_PLANNER_DAILY_MVP.md#m6-13)
- Deliverable / bounded file scope: discretionary selector.
- Work: After feasibility/reserve, rank eligible additional work mainly by Task importance, then useful fit/session constraints; honor whole-day <=40-minute SAFE remainder.
- Acceptance / failure and extension checks: Higher-importance OPTIONAL/EXPIRING can outrank safe future REQUIRED extras; three 20-minute windows may support work when total >40; short gaps are not categorically banned.
- Completion evidence: artifact paths + exact targeted command/check or user-source reference + observed result + remaining limitations, recorded in PROGRESS. Do not mark done from code presence alone.

### M6-15

**Implement today-only locks and soft bypass**

- Type: `DEV`. Initial status: `TODO`.
- Prerequisites: [M6-14](M6_PLANNER_DAILY_MVP.md#m6-14) · [M3A-02](M3_STATE_FOUNDATION.md#m3a-02) · [M3B-18](M3_RELATIONSHIPS_REVIEWS.md#m3b-18)
- Deliverable / bounded file scope: override/soft-sequence planning module.
- Work: Respect “complete today” versus “advance today” and next-Beijing-midnight expiry; bypass only allowed soft sequence under REQUIRED-feasibility pressure. Integrate the already persisted override inputs by recalculating snapshot/feasibility/allocation, never by appending a locked Task after feasibility has run.
- Acceptance / failure and extension checks: A lock cannot violate hard occupancy/order; conflict is shown; soft bypass does not claim prerequisite completion; one-day choice never becomes persistent preference.
- Completion evidence: artifact paths + exact targeted command/check or user-source reference + observed result + remaining limitations, recorded in PROGRESS. Do not mark done from code presence alone.

### M6-16

**Build actionable stage recommendations**

- Type: `DEV`. Initial status: `TODO`.
- Prerequisites: [M6-15](M6_PLANNER_DAILY_MVP.md#m6-15)
- Deliverable / bounded file scope: Daily Plan item builder.
- Work: Select concrete stage/chunk objectives, B/source, today estimate and work-style labels; represent plan role independently from requiredness.
- Acceptance / failure and extension checks: Every new recommendation has accepted required fields; repeated fragment references add no workload; no default exact clock-time schedule is imposed.
- Completion evidence: artifact paths + exact targeted command/check or user-source reference + observed result + remaining limitations, recorded in PROGRESS. Do not mark done from code presence alone.

### M6-17

**Implement concise Daily Brief renderer**

- Type: `DEV`. Initial status: `TODO`.
- Prerequisites: [M6-16](M6_PLANNER_DAILY_MVP.md#m6-16)
- Deliverable / bounded file scope: renderer matching DAILY_BRIEF_TEMPLATE.
- Work: Render date, usable time, all horizons, overall mode, recommended work and concise meaningful risks/relations/estimate differences.
- Acceptance / failure and extension checks: Renderer consumes machine Plan only; missing/invalid fields fail visibly; provider/backend field names do not clutter normal user output.
- Completion evidence: artifact paths + exact targeted command/check or user-source reference + observed result + remaining limitations, recorded in PROGRESS. Do not mark done from code presence alone.

### M6-18

**Implement provisional emergency first round**

- Type: `DEV`. Initial status: `TODO`.
- Prerequisites: [M6-12](M6_PLANNER_DAILY_MVP.md#m6-12) · [M6-17](M6_PLANNER_DAILY_MVP.md#m6-17)
- Deliverable / bounded file scope: emergency interaction first-round coordinator.
- Work: When any horizon is EMERGENCY, present provisional baseline, affected obligations/deficit and realistic removal/additional-capacity questions.
- Acceptance / failure and extension checks: A 3/7-day emergency triggers this even if today is SAFE; baseline is never marked final/feasible; removing OPTIONAL alone is not claimed to reduce REQUIRED R.
- Completion evidence: artifact paths + exact targeted command/check or user-source reference + observed result + remaining limitations, recorded in PROGRESS. Do not mark done from code presence alone.

### M6-19

**Implement emergency choice and second-round recalculation**

- Type: `DEV`. Initial status: `TODO`.
- Prerequisites: [M6-18](M6_PLANNER_DAILY_MVP.md#m6-18)
- Deliverable / bounded file scope: emergency response/replan coordinator.
- Work: Resolve user sacrifices and added capacity through proper commands/overrides, recompute all horizons and render final recommendations plus remaining infeasibility.
- Acceptance / failure and extension checks: Daily list removal does not cancel Task; stale response is version checked; insufficient added time or unchanged hard bottleneck remains visibly infeasible.
- Completion evidence: artifact paths + exact targeted command/check or user-source reference + observed result + remaining limitations, recorded in PROGRESS. Do not mark done from code presence alone.

### M6-20

**Persist Plan snapshots and replay provenance**

- Type: `DEV`. Initial status: `TODO`.
- Prerequisites: [M6-17](M6_PLANNER_DAILY_MVP.md#m6-17) · [M6-19](M6_PLANNER_DAILY_MVP.md#m6-19)
- Deliverable / bounded file scope: Plan repository/migration and replay command.
- Work: Store calculation snapshot, model/rule/config versions, allocations, renderer version and provisional/final status; avoid treating planned time as observed work.
- Acceptance / failure and extension checks: Old plan/prediction errors survive model changes; replay uses frozen inputs; same snapshot cannot accidentally publish twice under distinct retry IDs.
- Completion evidence: artifact paths + exact targeted command/check or user-source reference + observed result + remaining limitations, recorded in PROGRESS. Do not mark done from code presence alone.

### M6-21

**Implement guided morning operating loop**

- Type: `DEV`. Initial status: `TODO`.
- Prerequisites: [M6-20](M6_PLANNER_DAILY_MVP.md#m6-20) · [M3B-10](M3_RELATIONSHIPS_REVIEWS.md#m3b-10)
- Deliverable / bounded file scope: morning review/plan coordinator.
- Work: Refresh/reconcile evidence, present full pending queue and one special-circumstances question, apply user answers and calculate concise plan.
- Acceptance / failure and extension checks: No routine rule restatement is needed; unresolved facts stay visible/pending; a failed refresh does not erase trusted state or fabricate capacity.
- Completion evidence: artifact paths + exact targeted command/check or user-source reference + observed result + remaining limitations, recorded in PROGRESS. Do not mark done from code presence alone.

### M6-22

**Connect evening review to recalculation**

- Type: `DEV`. Initial status: `TODO`.
- Prerequisites: [M6-21](M6_PLANNER_DAILY_MVP.md#m6-21) · [M3B-10](M3_RELATIONSHIPS_REVIEWS.md#m3b-10)
- Deliverable / bounded file scope: evening→history→replan pipeline.
- Work: Use consolidated questionnaire/individual/batch handlers, update observations and replan from latest snapshot instead of blindly rolling unfinished work.
- Acceptance / failure and extension checks: Partial evening answers do not complete review; repeated messages do not add effort twice; model/user estimates retain different roles.
- Completion evidence: artifact paths + exact targeted command/check or user-source reference + observed result + remaining limitations, recorded in PROGRESS. Do not mark done from code presence alone.

### M6-23

**Implement proactive risk and inactivity notices**

- Type: `DEV`. Initial status: `TODO`.
- Prerequisites: [M6-22](M6_PLANNER_DAILY_MVP.md#m6-22) · [M3B-14](M3_RELATIONSHIPS_REVIEWS.md#m3b-14) · [M3B-12](M3_RELATIONSHIPS_REVIEWS.md#m3b-12)
- Deliverable / bounded file scope: alert dedup/state coordinator.
- Work: Produce accepted risk alerts and two-day reconciliation reminders through NotificationSink with bounded repetition; distinguish urgent exceptions from normal cadence.
- Acceptance / failure and extension checks: Repeated recalculation does not spam identical notices; unknown dispatch remains visible; missing normal interactions are computed by Beijing date, not connector traffic.
- Completion evidence: artifact paths + exact targeted command/check or user-source reference + observed result + remaining limitations, recorded in PROGRESS. Do not mark done from code presence alone.

### M6-24

**Create scheduled daily n8n orchestration**

- Type: `DEV`. Initial status: `TODO`.
- Prerequisites: [M6-23](M6_PLANNER_DAILY_MVP.md#m6-23) · [M4-13](M4_CALENDAR_CAPACITY.md#m4-13)
- Deliverable / bounded file scope: versioned test daily/review/alert workflows.
- Work: Schedule morning/evening generation using configured times and authenticated application calls; carry idempotency/snapshot IDs and error routes.
- Acceptance / failure and extension checks: Overlapping/restarted triggers produce one logical plan/notice occurrence; exporting workflows excludes credentials; n8n remains the only workflow platform.
- Completion evidence: artifact paths + exact targeted command/check or user-source reference + observed result + remaining limitations, recorded in PROGRESS. Do not mark done from code presence alone.

### M6-25

**Run Planner semantic regression fixtures**

- Type: `VERIFY`. Initial status: `TODO`.
- Prerequisites: [M6-24](M6_PLANNER_DAILY_MVP.md#m6-24)
- Deliverable / bounded file scope: planner regression/port conformance report.
- Work: Check budget direction, parent/stage totals, window infeasibility, distant early work, reserve boundary, discretionary order, natural dates, today locks and solver unknown.
- Acceptance / failure and extension checks: Compare bounded cases with exact oracle; metamorphic interval/order changes preserve invariants; optional model failure still produces a useful labeled fallback.
- Completion evidence: artifact paths + exact targeted command/check or user-source reference + observed result + remaining limitations, recorded in PROGRESS. Do not mark done from code presence alone.

### M6-26

**Run normal and emergency offline journeys**

- Type: `VERIFY`. Initial status: `TODO`.
- Prerequisites: [M6-25](M6_PLANNER_DAILY_MVP.md#m6-25)
- Deliverable / bounded file scope: reports/acceptance/M6-offline.md.
- Work: Replay synthetic morning→plan→work report→evening→replan and 3-day-emergency two-round journeys with notification/restart faults.
- Acceptance / failure and extension checks: Confirmed truth, constraints, full queue, batch scope and residual deficit remain correct across retries; this proves fixture behavior, not live connectivity.
- Completion evidence: artifact paths + exact targeted command/check or user-source reference + observed result + remaining limitations, recorded in PROGRESS. Do not mark done from code presence alone.

### M6-27

**Select release runtime and delivery configuration**

- Type: `OPS`. Initial status: `TODO`.
- Prerequisites: [M6-26](M6_PLANNER_DAILY_MVP.md#m6-26) · [M4-15](M4_CALENDAR_CAPACITY.md#m4-15) · [M5-21](M5_INGESTION_N8N.md#m5-21) · [M2-15](M2_CONTRACTS.md#m2-15)
- Deliverable / bounded file scope: deployment/delivery ADR and capacity budget.
- Work: Use measured prototype resources and actual scopes to choose always-on environment, HTTPS, secret/backup storage and production notification surface; ask only missing spend/channel preferences.
- Acceptance / failure and extension checks: No vendor purchase/deployment is performed by writing this plan; production topology does not require the user laptop; concrete quotas/limits and fallback settings are recorded.
- Completion evidence: artifact paths + exact targeted command/check or user-source reference + observed result + remaining limitations, recorded in PROGRESS. Do not mark done from code presence alone.

### M6-28

**Run limited live shadow daily trial**

- Type: `VERIFY`. Initial status: `TODO`.
- Prerequisites: [M6-27](M6_PLANNER_DAILY_MVP.md#m6-27)
- Deliverable / bounded file scope: reports/acceptance/M6-live.md.
- Work: Run one bounded real reviewed daily cycle with scoped live sources and delivery; compare proposed recommendations with manual facts before unattended use.
- Acceptance / failure and extension checks: Live scope/data quality/notifications are evidenced separately; fake passes cannot certify real scheduling; no model or collector auto-completes Tasks.
- Completion evidence: artifact paths + exact targeted command/check or user-source reference + observed result + remaining limitations, recorded in PROGRESS. Do not mark done from code presence alone.

### M6-29

**Close deterministic daily MVP gate**

- Type: `VERIFY`. Initial status: `TODO`.
- Prerequisites: [M6-26](M6_PLANNER_DAILY_MVP.md#m6-26) · [M6-28](M6_PLANNER_DAILY_MVP.md#m6-28)
- Deliverable / bounded file scope: reports/acceptance/M6.md.
- Work: Require offline semantic/fault checks and live shadow evidence, minimal backups/restores, auth, source freshness and operator recovery instructions.
- Acceptance / failure and extension checks: Morning/evening/emergency loop is usable with AI disabled; all enabled production sources/delivery are verified; remaining optional providers are explicitly disabled.
- Completion evidence: artifact paths + exact targeted command/check or user-source reference + observed result + remaining limitations, recorded in PROGRESS. Do not mark done from code presence alone.
