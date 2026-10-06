# WhatToDo — Calendar and usable capacity

> Status: executable development specification; every task initially TODO. No task is implemented by this file.
> Task scope: one bounded AI execution per task or explicitly repeated instance.

[Development plan and execution rules](../DEVELOPMENT_PLAN.md) · [Live progress](../PROGRESS.md)

## Required sources

- [INTEGRATION_PLAN.md](../INTEGRATION_PLAN.md)
- [PLANNER_PLAN.md](../PLANNER_PLAN.md)
- [OPERATIONS_PLAN.md](../OPERATIONS_PLAN.md)
- [IO_CONTRACT_PLAN.md](../IO_CONTRACT_PLAN.md)

Read the source sections relevant to the chosen task, its completed prerequisite artifacts, and the shared Definition of Done before editing. Source documents control meaning; this catalog controls work decomposition. Proposed artifact paths below are logical scopes until M2-16 freezes the language-specific mapping. An adapter/schema described here does not yet exist.

## Gate: M4-16

Task order is constrained by explicit dependencies, not by credentials for unrelated live integrations. A VERIFY task runs the smallest meaningful fixture/integration set for its boundary and records actual evidence. Repeated tasks are one course/family/account/layout/playbook per execution; a template dependency means the required instance set described in the development plan.

## Tasks

### M4-01

**Confirm one calendar sync scope**

- Type: `INFO`. Initial status: `TODO`.
- Prerequisites: [M3B-16](M3_RELATIONSHIPS_REVIEWS.md#m3b-16)
- Deliverable / bounded file scope: calendar provider/scope intake record.
- Work: Confirm actual calendars, timetable source, read scope, no-work/buffer settings and known placeholder events; do not assume old course ICS is current truth.
- Acceptance / failure and extension checks: Provider/calendar IDs and busy/free meaning are scoped; calendar writing remains optional and unimplemented; missing access blocks only live tasks.
- Completion evidence: artifact paths + exact targeted command/check or user-source reference + observed result + remaining limitations, recorded in PROGRESS. Do not mark done from code presence alone.

### M4-02

**Map one Calendar adapter contract**

- Type: `SPEC`. Initial status: `TODO`.
- Prerequisites: [M4-01](M4_CALENDAR_CAPACITY.md#m4-01) · [M2-08](M2_CONTRACTS.md#m2-08)
- Deliverable / bounded file scope: calendar mapping ADR and synthetic provider fixtures.
- Work: Inspect current official provider docs when implementing the chosen adapter; map exact IDs, timezones, recurrence exceptions, deletion, paging and refresh/checkpoint semantics.
- Acceptance / failure and extension checks: Provider-specific fields are grounded rather than guessed; source deletion affects its occupancy, not Task completion; calendar identity survives normalization.
- Completion evidence: artifact paths + exact targeted command/check or user-source reference + observed result + remaining limitations, recorded in PROGRESS. Do not mark done from code presence alone.

### M4-03

**Implement normalized Event persistence**

- Type: `DEV`. Initial status: `TODO`.
- Prerequisites: [M4-02](M4_CALENDAR_CAPACITY.md#m4-02) · [M3A-19](M3_STATE_FOUNDATION.md#m3a-19)
- Deliverable / bounded file scope: Event repository/migration.
- Work: Store exact normalized event versions, ownership, source IDs, busy/free and recurrence-instance references separately from Tasks.
- Acceptance / failure and extension checks: Same event from refresh/upsert is deduplicated; two calendars’ IDs do not collide; event edits preserve source version history.
- Completion evidence: artifact paths + exact targeted command/check or user-source reference + observed result + remaining limitations, recorded in PROGRESS. Do not mark done from code presence alone.

### M4-04

**Implement Calendar fake and port conformance**

- Type: `DEV`. Initial status: `TODO`.
- Prerequisites: [M4-03](M4_CALENDAR_CAPACITY.md#m4-03)
- Deliverable / bounded file scope: CalendarSource fake and contract tests.
- Work: Feed synthetic normal/cancelled/recurring/multi-zone events through the frozen port. Establish reusable adapter tests before live network implementation.
- Acceptance / failure and extension checks: Fake and future live adapter use identical request/result shape; recurrence exceptions and all-day events cannot silently become arbitrary local hours.
- Completion evidence: artifact paths + exact targeted command/check or user-source reference + observed result + remaining limitations, recorded in PROGRESS. Do not mark done from code presence alone.

### M4-05

**Implement live Calendar read/page adapter**

- Type: `DEV`. Initial status: `TODO`.
- Prerequisites: [M4-04](M4_CALENDAR_CAPACITY.md#m4-04)
- Deliverable / bounded file scope: one live read-only calendar adapter.
- Work: Implement scoped paging/normalization for the selected provider only, with credential injection and bounded request limits; no writes or business Task mutation.
- Acceptance / failure and extension checks: Expired credentials/rate limits return typed errors; partial pages cannot look like a complete empty calendar; secret-bearing payloads are not logged.
- Completion evidence: artifact paths + exact targeted command/check or user-source reference + observed result + remaining limitations, recorded in PROGRESS. Do not mark done from code presence alone.

### M4-06

**Implement incremental sync and full-resync fallback**

- Type: `DEV`. Initial status: `TODO`.
- Prerequisites: [M4-05](M4_CALENDAR_CAPACITY.md#m4-05)
- Deliverable / bounded file scope: calendar checkpoint/recovery service.
- Work: Persist checkpoints only after durable processed batches; handle invalid cursors with bounded full resync and idempotent upserts.
- Acceptance / failure and extension checks: Crash mid-page and repeated full resync converge without duplicate events; stale checkpoints preserve last trusted occupancy and visible sync status.
- Completion evidence: artifact paths + exact targeted command/check or user-source reference + observed result + remaining limitations, recorded in PROGRESS. Do not mark done from code presence alone.

### M4-07

**Normalize recurrence and cross-zone windows**

- Type: `DEV`. Initial status: `TODO`.
- Prerequisites: [M4-04](M4_CALENDAR_CAPACITY.md#m4-04) · [M3A-02](M3_STATE_FOUNDATION.md#m3a-02)
- Deliverable / bounded file scope: recurrence/interval normalization module.
- Work: Use the verified provider expansion or bounded local expansion chosen in M4-02; handle exceptions, cross-midnight/all-day and provider DST even though planning uses Beijing.
- Acceptance / failure and extension checks: Recurring exceptions do not resurrect cancelled occupancy; explicit instants remain correct across server locale/DST; infinite recurrence expansion is impossible.
- Completion evidence: artifact paths + exact targeted command/check or user-source reference + observed result + remaining limitations, recorded in PROGRESS. Do not mark done from code presence alone.

### M4-08

**Merge busy intervals deterministically**

- Type: `DEV`. Initial status: `TODO`.
- Prerequisites: [M4-07](M4_CALENDAR_CAPACITY.md#m4-07)
- Deliverable / bounded file scope: interval union/subtraction module.
- Work: Merge overlapping/adjacent occupied intervals inside finite windows; clip bounds consistently and preserve why time is unavailable.
- Acceptance / failure and extension checks: Overlapping events are counted once; malformed negative intervals fail; permutation of input events does not change usable totals.
- Completion evidence: artifact paths + exact targeted command/check or user-source reference + observed result + remaining limitations, recorded in PROGRESS. Do not mark done from code presence alone.

### M4-09

**Apply no-work, buffers and minimum-window constraints**

- Type: `DEV`. Initial status: `TODO`.
- Prerequisites: [M4-08](M4_CALENDAR_CAPACITY.md#m4-08) · [M1-08](M1_USER_COURSE_MODEL.md#m1-08)
- Deliverable / bounded file scope: availability policy module.
- Work: Subtract accepted no-work/buffer/routine occupancy once; derive usable windows without applying the 40-minute rule as a blanket per-window ban.
- Acceptance / failure and extension checks: Fixed training is not subtracted twice; short windows remain available for fragmentable work; reserve is not removed here before risk C is computed.
- Completion evidence: artifact paths + exact targeted command/check or user-source reference + observed result + remaining limitations, recorded in PROGRESS. Do not mark done from code presence alone.

### M4-10

**Build natural-day availability snapshots**

- Type: `DEV`. Initial status: `TODO`.
- Prerequisites: [M4-09](M4_CALENDAR_CAPACITY.md#m4-09)
- Deliverable / bounded file scope: versioned 1/3/7-day capacity snapshot.
- Work: Anchor d in Asia/Shanghai; cut off at d/d+2/d+6 23:59 and clip to calculation time. Record Calendar/config versions and provenance.
- Acceptance / failure and extension checks: At Oct 6 15:00 Beijing the cutoffs are Oct 6/8/12; elapsed time is excluded; year rollover and overlapping-horizon accounting pass.
- Completion evidence: artifact paths + exact targeted command/check or user-source reference + observed result + remaining limitations, recorded in PROGRESS. Do not mark done from code presence alone.

### M4-11

**Implement Calendar freshness and degraded capacity**

- Type: `DEV`. Initial status: `TODO`.
- Prerequisites: [M4-06](M4_CALENDAR_CAPACITY.md#m4-06) · [M4-10](M4_CALENDAR_CAPACITY.md#m4-10)
- Deliverable / bounded file scope: capacity quality-state policy.
- Work: Mark stale/partial/unknown occupancy separately from risk mode; preserve last trusted snapshot and allow explicit user-corrected availability as a provenance-bearing fallback.
- Acceptance / failure and extension checks: Calendar failure cannot manufacture free hours or precise SAFE assurance; unavailable data is visible without cancelling Tasks; recovery replaces stale data idempotently.
- Completion evidence: artifact paths + exact targeted command/check or user-source reference + observed result + remaining limitations, recorded in PROGRESS. Do not mark done from code presence alone.

### M4-12

**Expose availability query and prototype preview**

- Type: `DEV`. Initial status: `TODO`.
- Prerequisites: [M4-11](M4_CALENDAR_CAPACITY.md#m4-11) · [M3A-16](M3_STATE_FOUNDATION.md#m3a-16)
- Deliverable / bounded file scope: availability read endpoint and preview renderer.
- Work: Return finite windows/capacity/data quality using the same snapshot API the Planner will consume; human preview is concise and not a final risk-certified Daily Brief.
- Acceptance / failure and extension checks: Machine values and human totals agree; stale provenance is visible; provider fields/credentials do not appear in ordinary output.
- Completion evidence: artifact paths + exact targeted command/check or user-source reference + observed result + remaining limitations, recorded in PROGRESS. Do not mark done from code presence alone.

### M4-13

**Add safe n8n Calendar sync workflow**

- Type: `DEV`. Initial status: `TODO`.
- Prerequisites: [M4-06](M4_CALENDAR_CAPACITY.md#m4-06) · [M3A-16](M3_STATE_FOUNDATION.md#m3a-16)
- Deliverable / bounded file scope: versioned disabled/test Calendar workflow export.
- Work: Orchestrate adapter calls with configured schedules, authenticated service calls, correlation IDs and bounded retry; keep interval/domain logic in reusable code.
- Acceptance / failure and extension checks: Import into a clean test n8n succeeds without production credentials; overlapping executions deduplicate; provider/business logic is not copied into multiple workflow nodes.
- Completion evidence: artifact paths + exact targeted command/check or user-source reference + observed result + remaining limitations, recorded in PROGRESS. Do not mark done from code presence alone.

### M4-14

**Run calendar failure and replay fixtures**

- Type: `VERIFY`. Initial status: `TODO`.
- Prerequisites: [M4-12](M4_CALENDAR_CAPACITY.md#m4-12) · [M4-13](M4_CALENDAR_CAPACITY.md#m4-13)
- Deliverable / bounded file scope: calendar integration/replay report.
- Work: Exercise partial pages, invalid cursor, token failure, double delivery, changed recurrence, placeholder busy/free and restart.
- Acceptance / failure and extension checks: Last trusted state survives failures; checkpoints do not skip uncommitted events; Task state is untouched by external calendar edits.
- Completion evidence: artifact paths + exact targeted command/check or user-source reference + observed result + remaining limitations, recorded in PROGRESS. Do not mark done from code presence alone.

### M4-15

**Validate one real scoped Calendar round trip**

- Type: `VERIFY`. Initial status: `TODO`.
- Prerequisites: [M4-14](M4_CALENDAR_CAPACITY.md#m4-14)
- Deliverable / bounded file scope: reports/acceptance/M4-live.md.
- Work: With available user-approved scope, compare provider events and normalized occupancy for one finite interval. Record provider version/scope and redacted evidence.
- Acceptance / failure and extension checks: Live read evidence is separate from fake fixture passes; missing credentials stays BLOCKED_USER and does not invalidate deterministic capacity tests.
- Completion evidence: artifact paths + exact targeted command/check or user-source reference + observed result + remaining limitations, recorded in PROGRESS. Do not mark done from code presence alone.

### M4-16

**Close the Calendar/capacity contract gate**

- Type: `VERIFY`. Initial status: `TODO`.
- Prerequisites: [M4-14](M4_CALENDAR_CAPACITY.md#m4-14)
- Deliverable / bounded file scope: reports/acceptance/M4.md.
- Work: Verify all domain/port/capacity tasks and data-quality behavior; record live M4-15 readiness separately before production use.
- Acceptance / failure and extension checks: M6 may use passed synthetic capacity fixtures without claiming live sync works; production Calendar use requires M4-15 evidence.
- Completion evidence: artifact paths + exact targeted command/check or user-source reference + observed result + remaining limitations, recorded in PROGRESS. Do not mark done from code presence alone.
