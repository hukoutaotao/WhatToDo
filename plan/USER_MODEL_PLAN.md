# WhatToDo — User / Course Model Plan

> Execution: [detailed development plan](DEVELOPMENT_PLAN.md) · [live progress](PROGRESS.md).
> Bounded work: [M1_USER_COURSE_MODEL](tasks/M1_USER_COURSE_MODEL.md) · [M1B_TASKTYPE_PRESETS](tasks/M1B_TASKTYPE_PRESETS.md) · [M5B_GOALS_GENERATION](tasks/M5B_GOALS_GENERATION.md).

> Purpose: Define how WhatToDo learns the user's stable working context before task/database implementation.
> Current relevance: A0 and the detailed development plan are complete; M1 remains incomplete. The current names are recorded once in the [confirmed inventory](intake/CURRENT_INVENTORY.md). Read PROGRESS for the current task and evidence; identity intake does not complete detailed modeling.

## 1. Scope

This document covers stable or semi-stable user context needed by the planner:

- top-level life domains
- current courses
- recurring exercise/training
- recurring life/administrative commitments
- course-specific task patterns
- planning-relevant preferences
- recurring routines
- long-term study characteristics

It does **not** store live task state such as "HW3 is 40% complete." That belongs in dynamic state later.

---

## 2. Initial Top-Level Domains

Accepted initial domains:

- Study / academics
- Exercise / sports
- Life administration
- Other

Subcategories may be added later if they improve planning.

---

## 3. Course Profile

Each active course should eventually have a structured profile.

Recommended fields:

### Identity
- course ID / slug
- official/common name
- term
- active/inactive

### Course-level priority
Do not assign a primary planner importance score to the Course itself.

Course is mainly a semantic/grouping context. Importance and requiredness belong to concrete Tasks, Goals, Exams, or generated review work.

### Typical task types
Examples:
- preview
- pre-lab preparation
- homework
- note organization
- lab
- programming assignment
- reading
- report
- review
- exam preparation
- project

### Work characteristics
Do not use one generic difficulty dimension by default.

At minimum use 1–5 task-level dimensions:
- thinking depth
- repetitive volume
- new-learning load

TaskType templates provide defaults; concrete Task instances inherit and may override them when needed.

Also capture where useful:
- typical total duration by task type
- derived estimation uncertainty from history (not a required user reliability score)
- minimum useful continuous session
- fragmentability
- need for uninterrupted focus
- whether repeated debugging/iteration is common

### Timing characteristics
- preferred time of day
- avoid times if any
- recurring release pattern
- recurring deadline pattern
- workload distribution and meaningful stages for large tasks; no generic start-N-days-early field

### Learning/review characteristics
- whether regular review is needed
- how far before midterm/final review should begin
- whether knowledge accumulates strongly across weeks

### Course progress axis
Each course should define an instructional progress axis.

At minimum support a course-defined progress unit:
- the unit may mean lecture/session, chapter, experiment, topic, etc.;
- before unit N;
- during unit N;
- after unit N;
- ranges such as units 1–N or A–B.

Also distinguish:
- teaching progress;
- each task family's completion progress along the axis.

Tasks, prerequisites, review conditions, and exam coverage may attach to this axis.

### Dependencies
Examples:
- preview before lab
- homework after lecture
- report after experiment
- notes before exam review

### Task decomposition preset
Each course should eventually define how its typical task classes are decomposed.

Preferred policy:
- each normal task type has a stable default decomposition template;
- special workflows that differ materially should normally become a new task type with a new template;
- avoid arbitrary per-instance template mutation as the default model.

Potential information:
- common task classes
- normal decomposition depth
- meaningful stages/subtasks
- when the whole assignment should remain one task
- when stages should become separate actionable units
- parent/child or stage order
- inherited difficulty dimensions
- inherited time/session defaults
- extensibility for new task types

The exact decomposition schema is developed in milestone M1B after the course profile is established.

Course templates may also predefine recurring dependency chains such as:
`preview → class → note organization → homework/exercise`.

Each dependency should be classifiable as:
- hard: genuinely cannot/should not proceed before prerequisite;
- soft/default sequence: preferred learning order that may be bypassed when REQUIRED feasibility is at risk.

Progress-axis backlog should be detectable when older Unit-linked tasks remain incomplete after teaching/task-family progress advances.

Initial conditional-review example:
- three consecutive incomplete post-class note-organization tasks may activate a catch-up/review task;
- entering exam-preparation phase should activate review work for the exam coverage.

---

## 4. Activity Profile

Recurring non-course activities may use a simpler profile.

Examples:
- sports team training
- recurring exercise
- household/life administration
- organization/student work

Potential fields:
- name
- domain
- recurrence
- fixed/flexible
- typical duration
- energy cost
- preparation/travel buffer
- whether it creates follow-up tasks

---

## 5. User Planning Preferences

These are planning rules, not personality descriptions.

Potential categories:

### Capacity
- desired maximum planned load per day
- desired buffer
- minimum unscheduled time

### Focus
- preferred focus-session length
- maximum useful focus-session length
- suitable times for cognitively heavy tasks

### Fragmentation
- which task types can fill 10–30 minute gaps
- which tasks require long uninterrupted blocks

### Deadline behavior
- feasibility-driven advancement and distribution of large work; no generic lead-time field
- whether large tasks should be spread across days
- how much emergency buffer to preserve

### Exam preparation
- desired review start time
- recurring review cadence
- mock-exam timing where relevant

### Output behavior
- whether to show exact times
- whether to explain priority
- desired detail level

Only store preferences that materially affect planning.

---

## 6. Collection Method for M1

Prerequisite:
- Alignment Gate A0 in `ALIGNMENT_PLAN.md` is accepted.
- User and AI have agreed on how information granularity and downstream effects will be discussed.

Do not ask the user to fill a giant technical form.

Recommended conversational sequence:

1. Ask for all current courses and recurring commitments.
2. Pick one representative course.
3. Ask about that course using natural language:
   - what work it creates
   - what is hard about it
   - typical duration
   - release/deadline patterns and how large work should be distributed; do not require a generic lead-time parameter
   - whether work can be fragmented
4. Draft a structured profile.
5. Let the user correct it.
6. Reuse the profile structure for the remaining courses.
7. Record only confirmed current-semester facts as project truth.

Avoid silently importing old-chat facts as current truth if the user has not confirmed they still apply.

For every proposed Course/Profile field, understand its downstream purpose. A field should not exist merely because it is easy to collect. Typical consumers include Task normalization, Planner scheduling, Goal generation, Daily Output, and historical estimation. Use the worked Course example in `ALIGNMENT_PLAN.md` as the reference style.

---

## 7. Repository Destination

During planning:
- profile schema/rationale stays in this document.

After the data format is finalized:
- concrete user/course profile files should live in a dedicated version-controlled data/config location, likely under a future `memory/` or `config/` hierarchy.
- the exact directory should be decided before implementation and recorded in DATA_MODEL_PLAN.

Do not put dynamic tasks into those profile files.

---

## 8. Interaction with Other Plans

Feeds:
- DATA_MODEL_PLAN
- PLANNER_PLAN
- DEVELOPMENT_PLAN M1/M2
- future long-term declarative memory

Affected by:
- DECISIONS
- user corrections

If course-profile fields change materially:
1. update this file
2. check DATA_MODEL_PLAN
3. check PLANNER_PLAN
4. check IO_CONTRACT_PLAN if profile input/output is exposed
5. update TESTING_PLAN fixtures when implemented
6. update PROGRESS.md

---

## 9. Relationship to M1B

M1 captures what each course/activity is like.

M1B then uses those profiles plus representative real tasks to define per-course/task-type decomposition presets.

Do not attempt to force all decomposition detail into the first course-listing conversation. The dedicated M1B step exists because this information is expected to be complex and high-volume.

---

## 10. M1 Completion Criteria

M1 is complete when:

- all current courses are listed and confirmed
- recurring non-course commitments are listed and confirmed
- at least one representative course has a detailed profile
- the profile structure works for the remaining courses without major ad hoc exceptions
- planning-relevant user preferences needed for task modeling are captured
- information is sufficiently structured to begin M1B decomposition presets, then M2 Task/I-O contract work

Do not mark M1 complete merely because a course list exists.

---

## 11. Already Accepted Defaults vs Missing User Facts

Do not re-ask A0's accepted domains, three 1–5 difficulty dimensions, Task importance 1–5, three requiredness values, one-hour/day reserve, ~40-minute SAFE small-gap policy, or recommendation-oriented output as if undecided. Collect course-specific defaults and explicit exceptions only.

Time-of-day preferences are user-confirmed profile rules; learned alternatives require approval. Exam review phases/cadence may be configured explicitly, but are not a generic lead-time field for every TaskType. Teaching progress and task-family progress values are dynamic state; the definition of their common axis is stable profile/config.

Conditional triggers can detect conditions automatically; mapped Tasks may be instantiated under an explicitly accepted automatic-generation relationship (D-072). Outside accepted rule scope, propose candidates. TaskType defaults alone are not blanket activation permission. M1 is not complete: current course/activity identities have been collected, but reviewed detailed profiles, axis definitions and task-family defaults remain pending.

---

## 12. Fixed Follow-Up Preferences and Relationship Collection

Confirmed preferences: Beijing time (Asia/Shanghai); date-only deadlines default to 23:59; valid model remaining-effort predictions drive planning; SAFE leaves aggregate whole-day discretionary remainder <=40 minutes free; evening review may batch-confirm untouched unchanged estimates. Do not re-ask these defaults. The user selected natural-day 1/3/7-day horizons including today, ending today / today+2 / today+6 at 23:59 Asia/Shanghai (D-078). This is a confirmed preference, not an onboarding question.

In M1/M1B collect course/TaskType patterns for counterpart generation and required completion/start order. Ask about the actual workflow and relevant target fields, not graph terminology. Task 1 creation → Task 2 generation does not imply Task 1 executes first. Pre-lab preparation may be generated after its lab Task is created but must finish before the lab under its separate order relation.

Stable generation/order templates belong with versioned profile/rule knowledge; concrete Task links/runtime generation and user review state belong in PostgreSQL. Confirmed rule execution needs no repeated per-instance acceptance within its exact mapping/scope. Course-specific differences refine these rules without assigning primary Course importance.

---

## 13. M1-02 Stable Profile Format Proposal

Proposal version: `whatodo.stable-profile / 0.1.0-draft`. Status: SPEC proposal, to be exercised by M1-03/04 and refined at M1-05. It is not the frozen M2 machine schema or a runtime validator. Artifact: [one synthetic example bundle](examples/STABLE_PROFILE_V0_1.synthetic.json); it includes one Course and one Activity and explicit reference stubs, all fictional.

### 13.1 Ownership and Identity

Use one versioned envelope with `kind = COURSE | ACTIVITY` and kind-specific stable payloads. IDs come from the [inventory](intake/CURRENT_INVENTORY.md) for real items; IDs never depend on display name, row position or filename. Profile revision identifies content changes separately from contract/schema version. Term/source aliases may be added later without replacing the item ID.

No primary Course importance is required or permitted in this proposal. Importance, requiredness and the three 1–5 difficulty defaults belong to TaskTypes/Tasks; profiles bind versioned TaskType definitions. A Course without any root priority score is valid.

### 13.2 Envelope Fields

| Field | Proposal type / requirement | Meaning and consumer |
| --- | --- | --- |
| `profile_format` | Required string, exactly `whatodo.stable-profile` | Explicit format discriminator; never inferred from filename |
| `profile_schema_version` | Required version string, currently `0.1.0-draft` | Contract compatibility and validation |
| `profile_id` | Required immutable nonempty ID | Course/activity association, source matching, output grouping |
| `profile_revision` | Required positive integer | Exact reviewed snapshot; future updates compare expected revision |
| `kind` | Required `COURSE` or `ACTIVITY` | Selects the small payload contract |
| `domain` | Required `study`, `exercise`, `life_administration` or `other`; COURSE uses study | Existing accepted domains; no course-name branch in Planner |
| `record_mode` | Required `USER_PROFILE` or `SYNTHETIC` | Prevents a test example being loaded as personal truth |
| `review_status` | Required `DRAFT` or `REVIEWED` | Whole-profile review readiness; independent of each known field's provenance |
| `review_evidence` | Required for REVIEWED: `{source_id, profile_revision}` | User review source must cover this exact profile revision; optional/absent for DRAFT |
| `display_name` | Required nonempty user-provided name, or clearly fictional fixture name | Human/source identity; editing the name does not change ID |
| `term_ref` | Optional known nonempty term ID/string; unresolved if not supplied | Academic context; intake date is not an invented term |
| `profile` | Required object with the appropriate payload below | Stable definitions consumed by normalization/planning |
| `unresolved_fields` | Required array of unique JSON Pointer paths to omitted, unknown fields | Unknown never becomes zero, false or an empty set |
| `provenance` | Required source list and field-to-source map | Review, correction, trust, downstream traceability |
| `extensions` | Required object, empty when no extensions exist | Registered additive data; rules below prevent silent semantic overrides |

An explicitly supplied zero/false/empty list is a known value with source evidence. An omitted field listed in unresolved_fields is unknown. A field genuinely not applicable to this kind is omitted and not listed as unknown; Course-only axis data does not become a missing Activity axis. Known and unresolved declarations for the same path are contradictory and invalid.

A source contains a stable local source ID, authority (`USER_STATEMENT`, `ACCEPTED_DEFAULT`, `ENGINEERING_METADATA`, `SYNTHETIC`, or `UNREVIEWED_SOURCE`) and an exact source reference/description. `field_sources` maps JSON Pointer paths to source IDs. A parent-path source covers its descendants unless a more specific field mapping overrides it. Every planning-relevant supplied field needs a resolvable source. IDs/version/revision and other engineering metadata are identified as engineering choices, not invented user preferences.

UNREVIEWED_SOURCE can appear in a DRAFT as a proposal; it never becomes confirmed personal truth through confidence. REVIEWED requires the relevant user statements/accepted defaults and explicit scoped profile review, not an AI-written status. SYNTHETIC records remain fixtures regardless of their other fields; they are rejected at any real-user activation boundary.

### 13.3 Stable Payloads

| Kind / field | Proposal shape | Ownership and downstream effect |
| --- | --- | --- |
| Both: `task_family_refs` | Array of `{family_id, task_type_ref: {id, version}}` | References exact TaskType defaults/decomposition; changing a definition does not silently rewrite existing Tasks |
| COURSE: `progress_axis` | `{axis_id, axis_version, unit_kind, unit_label, ordered_units?}`; each declared unit has stable id/label | Defines chapter/lesson/experiment/topic semantics; actual M1-04 may refine range encoding |
| COURSE: `learning_patterns` | Optional reviewed stable review/cumulative-knowledge context | Exam/Goal/review setup; no implicit activation or generic start-N-days-early rule |
| Both: `timing_patterns` | Optional reviewed release/deadline or time-of-day pattern definitions | Instantiation/scheduling context; concrete release/deadline timestamps stay with Tasks/Events |
| Both: `relationship_rule_refs` | Array of exact rule ID/version references, unknown until reviewed | Links stable generation/order templates; reference presence does not grant authority |
| ACTIVITY: `activity_category` | Optional nonempty descriptive category ID | Allows another sport/life category through configuration rather than Planner branches |
| ACTIVITY: `schedule_intent` | Optional `FIXED_COMMITMENT`, `FLEXIBLE` or `MIXED` | Describes stable intent; even FIXED_COMMITMENT does not supply busy intervals or prove immovability |
| ACTIVITY: `recurrence` | Optional reviewed recurrence/condition definition; at this proposal stage kind/description suffice | M1-07 collects actual cadence; M2/M5B define machine occurrence rules and accepted activation |
| ACTIVITY: `work_characteristics` | Optional typical effort/session minutes and fragmentability | Stable tendencies, never a concrete Task's user remaining effort, selected prediction or actual effort |
| ACTIVITY: `buffers` | Optional nonnegative preparation/travel minutes | Calendar capacity normalization; overlapping occupancy/work must be counted once |

Work characteristics and TaskType defaults distinguish thinking depth, repetitive volume and new-learning load; a generic course-difficulty scalar is not added. Duration tendencies are templates/context, not live U or B. Continuous-session constraints/fragmentability must be reviewed for the relevant family/activity; absent values remain unresolved.

No live Task IDs/status, actual work sessions, user remaining-effort values, numerical model predictions, concrete occurrence times, teaching position, task-family completion position, completed-unit set, backlog holes, Exam coverage instance or temporary day override belongs in a stable profile. Those remain PostgreSQL operational state later. The axis definition can enumerate units but must not label them completed.

### 13.4 Validation, Review and Compatibility

1. Validate discriminator/version, kind/domain, immutable ID, positive revision and declared field shapes. Reject unsupported major/breaking contracts explicitly; no best-effort conversion that silently drops fields.
2. Check source IDs, referenced field paths and unresolved/known contradictions. A DRAFT can be a valid partial profile while remaining unusable for a consumer that needs a missing constraint. Report that exact missing field; do not assume a frequency, duration or available slot.
3. Resolve referenced TaskType/rule ID and version against the registry of that scope. Synthetic stubs resolve only within the example bundle and are not an implemented registry. Unresolved real references block their affected consumer; they do not block unrelated identity display.
4. REVIEWED is scoped to one profile/revision with review evidence. Any material edited field needs appropriate review; retain previous versions/evidence. A revision cannot silently replace history or migrate live Task values.
5. Adding another activity category, course name or progress-unit label uses the same fields. Adding core planning behavior or a new domain/kind requires an explicit compatible contract/consumer change.
6. Each extension has a namespaced key and `{version, critical, payload}`. Extensions cannot shadow core fields, grant automation authority or execute code. Registered handlers validate consumed extensions. Preserve unknown noncritical payloads as opaque data; they cannot affect planning. Unknown critical extensions block the affected consumer with a reason.
7. Contract edits require an explicit supported adapter/migration or clear rejection for old incompatible revisions. Round-trip compatible data without dropping IDs, provenance or noncritical extensions. M1-05 refines the proposal, M2 freezes machine contracts and M2-16 selects concrete language/path mapping.

Acceptance exercised by the synthetic bundle: Course with no primary importance; chapter axis with no dynamic completion; Activity with no course axis; explicitly known zero buffers; omitted unknown term; versioned TaskType reference with fixture-only stub; noncritical opaque extension. These are contract/example checks, not live user profiles, runtime tests or final machine-schema conformance.

## Detailed Execution Mapping

Profiles/presets are one reviewed course/activity/family per repeated task. M1-01's identity artifact is the linked inventory; detailed profile readiness and the next task are in PROGRESS. Do not confuse confirmed names with reviewed detailed profiles.
