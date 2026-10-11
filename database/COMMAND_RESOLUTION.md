# Owned Task reference resolution and clarification

M3A-22 supplies a [pure resolver](../src/application/task_resolution.py) and
[PostgreSQL process service](../src/adapters/postgres_resolution.py). It consumes
bounded normalized input from an independently authenticated caller. Creation
can enter through [M3A-21 direct-user proposals](../formats/input/DIRECT_USER_CREATION.md).
Other freeform command classes remain separate normalization instances.

## Names, IDs and current context

Explicit IDs use exact identity comparison and never fall back to titles or
provider IDs. Human names use NFC, trimmed case-insensitive exact matching. A
unique exact name resolves immediately. Duplicate exact names list all matches;
substring/similarity suggestions always require selection, even for one match.
Task choices include stable ID, revision, title, course and separate completion
and disposition. Completed/cancelled/expired Tasks stay available for explicit
reference; resolution does not alter their lifecycle.

Current Task heads are readable only when their independently registered
acceptance authority belongs to the authenticated principal. Course display
names/aliases are injected separately per principal, with stable IDs and a
versioned registry hash. An exact course selector restricts Task matching;
ambiguous aliases first ask which course. Choosing a course that yields one
exact Task resolves without another identical approval. Delegated access from
another principal requires later explicit read-scope work.

Snapshots have a 1,000-reference limit; larger owned sets return an explicit
error rather than silently hiding choices. Control characters are visibly
escaped in labels. No raw source body or effort record is rendered in a choice.
If there are no listed candidates, the current reply cannot select an unlisted
ID. Refresh can present a changed current snapshot; a corrected target intent
must use a new command identity. A resolved command whose target changed also
requires a new intent rather than silently replacing its target revision.

## Versioned same-command follow-up

Three closed, explicitly selected extension contracts are registered in
[the extension registry](../formats/extension-registry.json):

- `resolution-intent` / `0.1.0-resolution-intent`: CREATE, COMPLETE, CANCEL or
  UPDATE intent; stable session/command/principal IDs, ID/name/course selector,
  bounded command fields and explicit creation facts.
- `resolution-session` / `0.1.0-resolution-session`: exact immutable presented
  frame, revision and predecessor, source chain, snapshot/registry hash,
  listed choices, retained known facts, remaining questions and resolved target.
- `clarification-reply` / `0.1.0-clarification-reply`: independent reply ID,
  session ID, expected revision, exact frame SHA-256, selection and text answers.

Replies require a registered independent user/account binding and an immutable
PRESENT USER source with the exact submitted bytes. Capture time must fall
between the presented question and the injected current time. An external
source or a payload-supplied caller cannot become a user answer.

An exact listed ID or numbered selection chooses only the original list. Saying
"confirm" when several items are listed leaves the command pending. Unrelated
new Tasks do not reorder or enlarge that original list. Changes to a listed
Task or course registry conflict; an explicit refresh creates a new frame
revision. Old revision/hash replies cannot advance the refreshed command.

Creation asks only missing title, importance, requiredness, difficulty and domain.
Known fields cannot be overwritten by a clarification answer. Valid answers
remain recorded when another answer is invalid; the next question concerns only
remaining fields. Omitted/unknown remaining effort stays unknown. No estimated
total, actual work, timestamps or default importance is fabricated. All frames
retain the original command identity. Existing manual pending history stays
immutable when the final same-command creation succeeds.

## Storage, replay and authorized handoff

[Migration 011](runtime-migrations/011_command_resolution.sql) adds three process
owners and seven FKs. The runtime now has twelve steps,
`0.7.0-command-resolution`, 72 domain tables/176 FKs plus three metadata tables.
The exact old eleven-step prefix is retained in
[the M3A-21 snapshot](../reports/acceptance/M3A-21-migration-plan.json).
These tables are not Tasks, grants, audits or store-epoch revisions.

`begin`/`begin_creation`, `get`, `reply`, `refresh` and `handoff` return typed
PortResults. Creation and reply publication append immutable frames, CAS the
owned head and journal each reply atomically. Readers check bytes, hashes,
projections and predecessor fact/identity continuity. A separate transaction
lock prevents competing replies from both advancing one question. Failure
before commit rolls the entire process update back. Lost commit acknowledgement
returns UNKNOWN; replay/read observes the durable original result.

Begin replay preserves the original intent/source. Reply-ID replay returns its
original after-frame, including after later clarification or Task changes.
Changed bytes/source under the same reply ID conflict. Owned historical reads
and replay need no current account binding or parser. Wrong principals cannot
read/replay another user's frame.

Handoff retains the original command ID, exact selected Task revision, source
chain and frame version/hash. Creation also supplies a ResolvedManualIntent.
It refreshes the store epoch for unrelated changes without replacing the chosen
Task. It does not register grants or execute arbitrary SQL. Publication still
requires the existing independently authorized manual/fact/lifecycle handler.
Canonical receipt lookup permits historical handoff replay after successful
publication; changed command/root content under that ID conflicts.

## Verification and remaining work

Run from the checkout:

```powershell
.venv/Scripts/python.exe -m unittest tests.test_task_resolution tests.test_direct_creation -q
.venv/Scripts/python.exe tools/verify_resolution.py
.venv/Scripts/python.exe tools/verify_package_install.py
```

Twenty-two focused resolution methods and 21 creation regression methods pass;
the full suite passes 496 methods. [Native resolution acceptance](../reports/acceptance/M3A-22.json)
passes 23 checks, including original-prefix upgrade, actual creation/completion
handoff, owner/source/version isolation, partial-field retention, old pending
history, rollback, lost acknowledgement and concurrent reply protection.
Migration, evidence, Task storage, manual creation, work reporting and direct
creation regression reports are archived under `M3A-22-*`. All seven final
native clusters dropped their databases and stopped.

[Clean offline installation](../reports/acceptance/M3A-22-package.json) verifies
56 modules, 36 selected schemas (30 base plus six opt-in) and all 57 installed
Python source files. Installed clarification/resolution/handoff works without
checkout imports; database use explicitly reports the absent optional driver.
All 91 generic-baseline pins and original base schemas remain unchanged.

Next ready card is M3A-16 authenticated prototype transport. This module does
not select a live channel, activate personal profiles, import Calendar data,
parse relative dates or complete the other freeform command classes. Personal
intake and full runtime/integration/planning/learning/deployment remain open.
