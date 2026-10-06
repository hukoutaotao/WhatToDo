# Output Format Specifications

This directory stores specifications, examples, schemas, and conventions for information produced by WhatToDo.

Current artifacts:

- `DAILY_BRIEF_TEMPLATE.md` — A0-approved conceptual default for the human-facing daily plan, including 1/3/7-day risk reporting and emergency-mode extension.

Authority: [I/O contract](../../plan/IO_CONTRACT_PLAN.md) and [Planner](../../plan/PLANNER_PLAN.md). Rendering must distinguish Task requiredness from today's plan role and avoid duplicate effort accounting across sections. The template is conceptual, not an implemented renderer.

The exact machine schema is not finalized yet. M2 will refine concrete structured output while preserving accepted A0 semantics unless the user changes them.

