# Output Format Specifications

> Execution: [detailed development plan](../../plan/DEVELOPMENT_PLAN.md) · [live progress](../../plan/PROGRESS.md).
> Bounded work: [M2_CONTRACTS](../../plan/tasks/M2_CONTRACTS.md) · [M6_PLANNER_DAILY_MVP](../../plan/tasks/M6_PLANNER_DAILY_MVP.md) · [M8_LEARNING_RELEASE_OPERATIONS](../../plan/tasks/M8_LEARNING_RELEASE_OPERATIONS.md).

This directory stores specifications, examples, schemas, and conventions for information produced by WhatToDo.

Current artifacts:

- `DAILY_BRIEF_TEMPLATE.md` — A0-approved conceptual default for the human-facing daily plan, including 1/3/7-day risk reporting and emergency-mode extension.
- [Plan/forecast development contract](PLAN_FORECAST_CONTRACT.md) and [schema](plan.schema.json) — runnable M2-10.a output/semantic helpers with synthetic tests; no human renderer or actual solver is implemented.

Authority: [I/O contract](../../plan/IO_CONTRACT_PLAN.md) and [Planner](../../plan/PLANNER_PLAN.md). Rendering must distinguish Task requiredness from today's plan role and avoid duplicate effort accounting across sections. The template is conceptual, not an implemented renderer.

The exact release schema is not frozen yet. M2-10.a provides a runnable 0.1.0-draft handoff while M2 continues refining concrete structured output against the accepted A0 semantics.

---

Follow-up output semantics: model-first effective parent/stage estimates with canonical user estimate retained separately; concise relationship origin/blocking notes; Beijing timestamps and date-only 23:59; aggregate-day <=40-minute SAFE remainder; notice-before-record expiration; batch unchanged-estimate evening review. The 1/3/7-day forecasts use natural days including today, with Beijing-time 23:59 cutoffs on today / today+2 / today+6 (D-078). No original experience question remains pending.

---

## Detailed Execution Mapping

Concrete Plan schema is M2-10; Daily renderer and two-round emergency are M6-16–19; weekly/long-term formats are M8-08–09.
