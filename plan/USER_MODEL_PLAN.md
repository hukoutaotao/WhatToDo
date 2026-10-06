# WhatToDo — User / Course Model Plan

> Purpose: Define how WhatToDo learns the user's stable working context before task/database implementation.
> Current relevance: This becomes the active modeling document after Alignment Gate A0 is accepted. The project is currently still in A0.

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
- estimation uncertainty
- minimum useful continuous session
- fragmentability
- need for uninterrupted focus
- whether repeated debugging/iteration is common

### Timing characteristics
- preferred time of day
- avoid times if any
- recurring release pattern
- recurring deadline pattern
- lead time desirable for large tasks

### Learning/review characteristics
- whether regular review is needed
- how far before midterm/final review should begin
- whether knowledge accumulates strongly across weeks

### Course progress axis
Each course should define an instructional progress axis.

At minimum support:
- lesson/session identifiers;
- before lesson N;
- during lesson N;
- after lesson N;
- ranges such as lessons 1–N or A–B.

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
- desired lead time
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
   - how early work should start
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
- information is sufficiently structured to begin M2 Task/I-O contract work

Do not mark M1 complete merely because a course list exists.
