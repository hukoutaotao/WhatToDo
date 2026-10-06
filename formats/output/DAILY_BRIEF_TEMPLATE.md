# WhatToDo — Daily Brief Template

> Status: A0-approved conceptual template.
> This is the default human-facing daily output structure.
> Exact wording may evolve during M2, but semantic sections should remain stable unless the user changes them.

# <Date>

## Today at a Glance

- Usable free time: <X h Y min>
- Risk:
  - 1 day: <SAFE | DANGER | EMERGENCY>
  - 3 days: <SAFE | DANGER | EMERGENCY>
  - 7 days: <SAFE | DANGER | EMERGENCY>
- Overall mode: <SAFE | DANGER | EMERGENCY>

<Only show a short explanation here when the state is DANGER/EMERGENCY or otherwise abnormal.>

## Must Complete / Protect Today

For each item:

- <Parent Task>
  - Today: <specific stage/subtask>
  - Estimated effort: <duration>
  - Work style: <large uninterrupted block | fragmentable | either>
  - Deadline: <show if within 3 days or risky>

## Advance Today for Future Feasibility

For future required work that should be pulled forward:

- <Parent Task>
  - Today: <specific stage/subtask>
  - Estimated effort: <duration>
  - Reason: <brief reason only if useful, e.g. future 3-day capacity is tight>
  - Deadline: <show if within 3 days or risky>

## Fragmentable / Short-Gap Work

- <Task / stage> — <estimated effort or useful chunk>

## Optional if Capacity Remains

- <Task / stage> — <estimated effort>

## Risks / Exceptions

<Normally omit or keep very short.>

Examples:
- 3-day capacity is DANGER: required work leaves little margin.
- Task X has 5 h usable capacity before deadline but ~6 h remaining effort.
- Pending confirmation materially affects today's plan.

---

# Emergency Mode Extension

When overall mode is EMERGENCY, first show the normal plan above, then add:

## Emergency Adjustment Needed

- Capacity deficit: <summary>
- At-risk required tasks: <items>
- Suggested lower-importance / non-required items to remove:
  - <candidate>
  - <candidate>
- Additional time needed: <estimate>

Questions for the user:
1. Which suggested items can be removed or deferred?
2. How much additional time can you realistically make available today?

After the user answers, regenerate the final emergency-day plan.

---

# Display Rules

- Keep routine output concise.
- Show parent Task plus the concrete stage/subtask to advance.
- Show estimated effort for recommended work.
- Do not assign exact clock times by default.
- Show explicit deadlines by default only when within 3 days, risky, or requested.
- Show all 1-day / 3-day / 7-day risk states.
- Overall mode equals the most severe horizon.
- Prefer actionable recommendations over explanation.
- Expand explanations only for abnormal/risky/surprising situations or when requested.
