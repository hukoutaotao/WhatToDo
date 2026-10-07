# WhatToDo — Confirmed Current Inventory

Intake version: 1. Updated: 2026-10-07 (Asia/Shanghai).

[User model](../USER_MODEL_PLAN.md) · [M1 tasks](../tasks/M1_USER_COURSE_MODEL.md) · [Live progress](../PROGRESS.md)

## 1. Source and Scope

Source ID: `USR-20261007-INVENTORY-01`. Source: the user's reply to M1-01, received 2026-10-07 at 12:37:25 Asia/Shanghai in this development conversation. This reply directly confirms the names below; it is sufficient authority for recording those names without a second acknowledgement.

The user listed nine courses in the order preserved here, then ice hockey, tennis, basketball and football as fixed sports arrangements, then laundry and cup washing as the main life arrangements. Names are retained in Chinese exactly as supplied. No previous-chat course, sport, student-work or schedule has been imported.

This is an identity/domain intake, not a reviewed detailed profile, current workload list, Calendar import or automatic-generation authorization. The academic term's official label/ID is unknown; the intake date is not a fabricated term label.

## 2. Courses

| Stable provisional ID | User order | User-provided name | Domain | Identity confirmation |
| --- | --- | --- | --- | --- |
| course-001 | 1 | 复变函数与数理方程 | study | USER_CONFIRMED |
| course-002 | 2 | 物理实验 | study | USER_CONFIRMED |
| course-003 | 3 | 马克思主义基本原理 | study | USER_CONFIRMED |
| course-004 | 4 | 离散数学 | study | USER_CONFIRMED |
| course-005 | 5 | 基础物理学 | study | USER_CONFIRMED |
| course-006 | 6 | 数据结构与算法 | study | USER_CONFIRMED |
| course-007 | 7 | 电子电路与系统基础实验 | study | USER_CONFIRMED |
| course-008 | 8 | 电子电路与系统基础 | study | USER_CONFIRMED |
| course-009 | 9 | 信号与系统 | study | USER_CONFIRMED |

The circuits experiment and circuits theory course are separate courses (`course-007` and `course-008`). Do not merge them through shared words or inferred source mappings. An official English name, course code or alias remains unknown unless the user or an independently scoped source provides it.

## 3. Non-Course Commitments

| Stable provisional ID | User-provided name | Domain | Identity confirmation |
| --- | --- | --- | --- |
| activity-001 | 冰球 | exercise | USER_CONFIRMED |
| activity-002 | 网球 | exercise | USER_CONFIRMED |
| activity-003 | 篮球 | exercise | USER_CONFIRMED |
| activity-004 | 足球 | exercise | USER_CONFIRMED |
| activity-005 | 洗衣服 | life_administration | USER_CONFIRMED |
| activity-006 | 洗杯子 | life_administration | USER_CONFIRMED |

For activity-001 through activity-004, the user's description of fixed arrangements is retained as reported intent. It does not establish immutable Calendar intervals, recurrence frequency, weekdays, duration, travel/preparation buffers or whether a particular session can move. Those facts remain unknown. Laundry/cup washing are confirmed life activities; no frequency, deadline, importance or estimated duration is inferred.

## 4. Confirmation and Identity Rules

- USER_CONFIRMED applies to the listed identity/name and category only. Detailed profiles, axes, task-family defaults and schedules remain pending.
- IDs are assigned by the AI as engineering metadata; retain them when display names, ordering or profile paths change. Never renumber existing items when inserting another course/activity. Keep explicit aliases/merge history if an identity correction is later authorized.
- Provisional means academic term/source mappings and final file placement are not frozen; it does not mean the user's listed name is unconfirmed.
- The nine courses and six non-course items are the supplied inventory. The Other domain has not been assessed and is not implicitly an empty list; additional commitments can be appended without overwriting existing IDs. No claim is made that every minor life activity was enumerated.
- Unknown is distinct from zero, false, an explicitly empty set, an optional field being not applicable, and user rejection. Missing facts are recorded as unknown rather than given convenient defaults.

## 5. Pending Facts and Next Modeling Scope

| Scope | Missing facts | Owner |
| --- | --- | --- |
| Courses | Official term label; work families, course-specific task defaults, workflow, progress-unit definitions, workload/session/review patterns | M1-03/04/06; task presets in M1B |
| Sports | Actual fixed/flexible occupancy, recurrence, durations, buffers and follow-up work | One M1-07 instance per activity |
| Life | Recurrence/conditions, effort/session characteristics and relevant constraints | One M1-07 instance per activity |
| User capacity | Missing waking/no-work/focus windows and genuine exceptions to accepted A0 defaults | M1-08 |
| Other/additions | Not assessed; do not infer absence from this reply | Subsequent scoped intake when relevant |

Use course-001 (the first course in the user's sequence) as the initial representative modeling scope after M1-02. This is an execution choice, not an inferred course priority. The other eight courses instantiate M1-06 individually after M1-05; the six activities instantiate M1-07 individually. Changing the representative course before its review is permitted with an explicit progress entry.

## 6. Acceptance Evidence and Limits

M1-01 checks: nine exact course names, four sport names and two life names; 15 unique stable provisional IDs; confirmation state and domain recorded for every item; the two circuits courses remain distinct; each unknown above is preserved. The source statement supplies the INFO evidence. Subsequent development must use this file rather than reconstructing the list from memory.

M1-01 can finish at the identity-intake boundary. M1 as a milestone remains incomplete until detailed profiles, axis definitions, capacity preferences and M1-09 evidence exist. No runtime or scheduling test was performed by this intake.
