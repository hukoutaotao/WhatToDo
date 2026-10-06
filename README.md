# WhatToDo

A personal task/schedule system that reduces daily planning effort through trusted Tasks, available-capacity reasoning, concise recommendations and short morning/evening reviews.

Start at the [plan control center](plan/README.md), then read [live progress](plan/PROGRESS.md) and the [detailed development plan](plan/DEVELOPMENT_PLAN.md). The plan contains **195 bounded tasks in 11 catalogs**, with dependencies, deliverables, failure checks, robustness, extensibility and acceptance gates.

Accepted meaning lives in [A0 intent](plan/A0_USER_INTENT.md), [decisions](plan/DECISIONS.md) and linked module specifications. Task relationships, model-first planning, reviewed personal state, Beijing natural-day forecasts and daily reserve rules are already aligned.

Current state: documentation only. M0/A0 and detailed planning are complete; M1/M1B/M2 and runtime implementation are not. Next task is [M1-01 — current-semester inventory](plan/tasks/M1_USER_COURSE_MODEL.md#m1-01).

Architecture: n8n-only orchestration; PostgreSQL dynamic state; versioned declarative profiles/config; Calendar occupancy; deterministic-first core and replaceable optional AI. Reliability starts with the first persistent-state prototype. The former coarse roadmap and completed audit working file have been consolidated into the new plan's rules and traceability map.
