# Exact stage commands and truthful rework

M3B-07.a supplies the detached preparation required by
[M3B-07 stage rework](../plan/tasks/M3_RELATIONSHIPS_REVIEWS.md#m3b-07).
[M3B-07.b](../plan/tasks/M3_RELATIONSHIPS_REVIEWS.md#m3b-07b) retains the full
PostgreSQL handler, pending/history/violation persistence, independent reference
resolution and atomic concurrency/recovery requirements. Parent M3B-07 remains
IN_PROGRESS until that runtime acceptance passes.

## Opt-in contract and independent authority

[stage-command](../formats/extensions/stage-command.schema.json) is an additive
`0.1.0-stage-command` extension, independently registered in the
[extension registry](../formats/extension-registry.json). Thirty base schemas,
their frozen codec and ninety-one generic pins are unchanged. The private package
now carries 41 schemas. No SQL migration is introduced by preparation.

A command binds USER principal, command/root references, current parent revision,
existing stage identity/revision, operation `REWORK` or `COMPLETE` and exact fields.
Fields distinguish `SAME_OBLIGATION`, unresolved intent, correction and a new
obligation; optional parent/stage remaining estimates and a reported completion
timestamp retain their separate meanings. The timestamp retains its offset and
microseconds. Unknown versions, duplicate keys, extra approval fields, boolean
revisions and unrelated Task/actual-work fields are rejected.

`StageCommandGrant` is independently injected, exact to the complete command
fingerprint and USER source/capture time, with issuance, expiry and active state.
Preparation validates caller, grant, time and separate parent/stage revisions.
Constructing a schema-valid command or grant value does not prove registered
source/account authority; M3B-07.b must resolve and compare actual immutable rows.

## Detached effects

`prepare_stage_command` returns `PreparedStageCommand` with either PREPARED Task,
supporting user estimates and a transition proposal, or effect-free PENDING with
a closed reason and missing information. It performs no SQL and issues no permit.

- Genuine rework targets an existing completed stage. It becomes INCOMPLETE and
  its parent becomes/stays INCOMPLETE in the same proposed aggregate. Stage identity,
  title, weight, unrelated stages, profile/timing/work facts and original snapshot
  are preserved. Parent current completion time is cleared; the previous time
  remains in the transition and prior immutable snapshot.
- A previously confirmed positive parent U is retained when the parent is already
  incomplete. Completed, zero or unknown parent U requires a fresh positive user
  estimate. No stage/parent estimate is guessed or mechanically adjusted. An old
  completed-stage estimate is not reused as its new remaining estimate; without
  a supplied new stage estimate its current U becomes unknown and old history stays.
- Stage completion confirms only the stage and its zero U. Completing all stages
  cannot infer final parent completion, reduce parent U or fabricate actual effort.
  A reported stage timestamp stays in transition evidence, not the parent timestamp.
- Prediction values are retained with invalid/applicable flags cleared for the new
  parent revision. Separately supplied stage U is not added to the parent budget.
  Changed field provenance points to the exact source; unrelated provenance remains.
- Unresolved intent, correction and new obligations remain PENDING with distinct
  reasons and no proposed canonical effects. Known correction/new-obligation intent asks for its missing facts rather than the already resolved intent. Correction must reconcile the old
  record; a new obligation requires the creation path. Inactive parents require
  explicit reactivation rather than a silent disposition change.

## Truthful order evidence

`StageOrderSnapshot` carries independently selected typed relation versions and
execution evidence with owner/current revisions. It rejects duplicate identities,
count/traversal/payload overflow and target/owner/time drift. This constructor
does not certify a complete or current database scope: the runtime handler must
select all applicable scoped relationships and resolve actual current/history
evidence in its checked snapshot.

For incoming hard links, incomplete prerequisites, contradictory exact times and
missing timing evidence remain explicit diagnostics in the transition proposal.
The confirmed stage completion remains true. Prerequisite completion and actual
start times are never fabricated. START_PREREQUISITE uses actual start evidence;
COMPLETION_ORDER uses reported completion time. SOFT_SEQUENCE has no hard effect.
Unresolved required execution references retain an effect-free pending result.
Current incomplete prerequisite evidence and a proved temporal order violation
are distinct diagnostic codes.

The proposed transition retains command/source references, separate before/after
stage/parent revisions and outcomes, historical parent completion time, reported
stage time, historical stage completion/actual-start evidence, the complete order-input hash, exact relation/evidence pins and diagnostics. M3B-07.b must persist
these together with Task/observations/authority/audit/receipt/epoch, then verify
the original full receipt on replay. A confirmed instruction needs no second
per-instance approval.

## Verification and continuation

Run `.venv/Scripts/python.exe -m unittest tests.test_stage_commands -q` for targeted
authority, identity, history, budget, pending, timestamp and truth/order checks.
`tools/run_ci.py` verifies the full regression and isolated installation, including
installed stage rework and effect-free pending preparation without a permit.
Twenty focused methods and 735 full methods pass. Final local CI passes 30 phases/197 unchanged native prerequisite checks, with all seventeen databases dropped and ten servers stopped. Installation matches 74 modules/75 source files/41 schemas. [M3B-07.a acceptance](../reports/acceptance/M3B-07a.json) records observed results and exact pins. This does not certify new native stage mutations.

The next card is M3B-07.b. This preparer is not a deployed stage mutation handler,
a durable pending queue or completed parent M3B-07. Live activation, personal intake,
provider/model integration and deployment remain deferred.
