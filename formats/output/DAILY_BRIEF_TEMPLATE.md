# WhatToDo — Daily Brief Template

> Execution: [detailed development plan](../../plan/DEVELOPMENT_PLAN.md) · [live progress](../../plan/PROGRESS.md).
> Bounded work: [M2_CONTRACTS](../../plan/tasks/M2_CONTRACTS.md) · [M6_PLANNER_DAILY_MVP](../../plan/tasks/M6_PLANNER_DAILY_MVP.md).

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
  - Remaining effort for planning: <effective model-first budget B; user-estimate fallback if needed>
  - Today: <specific stage/subtask>
  - Today's stage estimate: <duration>
  - Work style: <large uninterrupted block | fragmentable | either>
  - Deadline: <show if within 3 days or risky>

## Advance Today for Future Feasibility

For future required work that should be pulled forward:

- <Parent Task>
  - Remaining effort for planning: <effective model-first budget B; user-estimate fallback if needed>
  - Today: <specific stage/subtask>
  - Today's stage estimate: <duration>
  - Work style: <large uninterrupted block | fragmentable | either>
  - Reason: <brief reason only if useful, e.g. future 3-day capacity is tight>
  - Deadline: <show if within 3 days or risky>

## Fragmentable / Short-Gap Work

<Prefer work-style labels on items above. If using this section, reference those items without counting them again; for a new recommendation show parent remaining effort + selected stage/chunk estimate.>

- <Parent Task> — remaining for planning <B>; today <stage/chunk>, <estimate>; <deadline when within 3 days, risky, or requested>

## Optional if Capacity Remains

- <Parent Task> — remaining for planning <B>; today <stage/chunk>, <estimate>; <work style>; <deadline when within 3 days, risky, or requested>

## Risks / Exceptions

<Normally omit or keep very short.>

Examples:
- 3-day capacity is DANGER: required work leaves little margin.
- Task X has 5 h usable capacity before deadline but ~6 h remaining effort.
- Pending confirmation materially affects today's plan.

---

# Emergency Mode Extension

Label Round 1 “Provisional baseline — emergency adjustment pending”; do not imply it is feasible/final. Overall mode controls this flow even if only a 3-day or 7-day horizon is EMERGENCY.

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

After the user answers, regenerate the final emergency-day plan and recompute every affected horizon. Preserve visible residual deficits. Removing optional recommendations alone does not reduce REQUIRED workload R, and removing a plan item does not cancel its canonical Task.

---

# Display Rules

- Keep routine output concise.
- Show parent Task plus the concrete stage/subtask to advance.
- Show parent effective remaining effort for planning and today's selected stage/subtask estimate. If materially different, add a concise “your estimate U; planning uses model B” note; do not overwrite or conflate them.
- Do not assign exact clock times by default.
- Show explicit deadlines by default only when within 3 days, risky, or requested.
- Show all 1-day / 3-day / 7-day risk states.
- Overall mode equals the most severe horizon.
- SAFE conceptually preserves about one hour of reserve per represented day; DANGER means REQUIRED still fits but this reserve is breached; EMERGENCY means REQUIRED no longer fits in total usable capacity.
- In SAFE, leave aggregate whole-day discretionary capacity <=40 minutes free after protecting required work/reserve; do not apply this as a ban on each short window.
- Prefer actionable recommendations over explanation.
- Expand explanations only for abnormal/risky/surprising situations or when requested.

---

# Rendering and Accounting Notes

- Empty optional sections may be omitted. Every newly recommended item shows parent remaining effort, today's selected stage/chunk estimate, and work style. For an unsplit Task, today's concrete objective may be the Task itself.
- “Protect today”, “advance”, and “optional if capacity remains” are daily plan roles, not replacements for REQUIRED / OPTIONAL / EXPIRING. A REQUIRED Task can appear as optional additional advancement only after its required feasibility is protected.
- SAFE discretionary selection uses importance after feasibility/reserve, so high-importance OPTIONAL/EXPIRING work is not automatically excluded because future REQUIRED work exists.
- Count a Task/stage allocation once. Fragmentability is preferably a label; repeated references are navigation aids, not extra workload.
- The one-hour reserve is separate from aggregate whole-day <=40-minute discretionary remainder (D-076). Beijing time and date-only 23:59 are fixed; D-078 fixes natural-day windows including today, ending today / today+2 / today+6 at Beijing-time 23:59.
- Unresolved confirmations or stale capacity are visible data-quality exceptions; do not present uncertain input as a precise safe guarantee. Confirmation review is a prerequisite workflow, not a footnote that authorizes using unconfirmed facts.

---

# Follow-Up Display Rules

- Display dates/deadlines in Beijing time (Asia/Shanghai). For date-only deadlines use accepted 23:59; preserve explicitly specified times. Label the accepted 1/3/7-day natural-day windows with cutoffs today / today+2 / today+6 at 23:59; include today and count only its remaining usable capacity, not elapsed hours.
- A valid model remaining-effort prediction supplies B for daily allocation/risk; fallback source is the user estimate when unavailable. The selected stage estimate is part of B, not an extra obligation. The original user estimate remains accessible and is shown when material to understanding a discrepancy.
- Use concise relation notes only when meaningful: “generated from Task X”, “must finish before Task Y”, or “blocked by prerequisite”. Completion order alone does not imply a start block.
- Inform the user of confirmed expiration before recording EXPIRED, without adding an unrequested acknowledgement step. Pending notification is not already recorded expiration or completion.
- Evening output can list worked-on Tasks for individual updates and untouched/unchanged Tasks in one “keep previous estimates” batch. No silent acceptance of missing answers.

---

## Detailed Execution Mapping

Preserve this human baseline in M2-10 and M6-16–19. Render from versioned machine Plan, not independently recomputed totals; fixture/live evidence are separate.
