# Exact stage commands and truthful rework

M3B-07.a supplies the detached preparation required by
[M3B-07 stage rework](../plan/tasks/M3_RELATIONSHIPS_REVIEWS.md#m3b-07).
[M3B-07.b](../plan/tasks/M3_RELATIONSHIPS_REVIEWS.md#m3b-07b) retains the full
PostgreSQL handler, pending/history/violation persistence, independent reference
resolution and atomic concurrency/recovery requirements. Runtime child and parent are now DONE at the synthetic scope recorded in
[final runtime acceptance](../reports/acceptance/M3B-07b.json) and
[parent acceptance](../reports/acceptance/M3B-07.json).

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
At the historical preparation checkpoint, twenty focused methods and 735 full methods pass. Its local CI passes 30 phases/197 unchanged native prerequisite checks, with all seventeen databases dropped and ten servers stopped. Installation matches 74 modules/75 source files/41 schemas. [M3B-07.a acceptance](../reports/acceptance/M3B-07a.json) records observed results and exact pins. That preparation checkpoint does not certify native mutations; final runtime evidence follows below.

The preparer alone does not establish runtime completion. M3B-07.b now supplies
that separately verified runtime; the complete deployed application remains later work. Live activation, personal intake,
provider/model integration and deployment remain deferred.

## Historical storage checkpoint

[Composite stage plans](../src/application/stage_commit.py) preserve the original
command bytes, exact source capture, parent hashes, stage versions and full order
snapshot. A pending journal has one metadata write and no Task/estimate effects.
A committed plan includes the Task, transition and separate relationship issues
in its receipt and full audit fingerprint. Neither value issues a permit.

[The internal PostgreSQL writer](../src/adapters/postgres_stage_commit.py) requires
an already-open checked transaction and an independently supplied exact permit.
It rechecks the stored USER authority/source, rebuilds the plan against the
current parent, retains original estimate authority/capture and writes all
effects with one epoch advance. Observation `recorded_at` is the write time;
the reported/verified estimate times retain the source capture time.

[Migration 017](runtime-migrations/017_stage_commands.sql) adds
immutable journal, relationship-issue and pending-resolution storage. Exact
parent/stage/hash references and deferred source/authority/audit guards bind
records to their original transaction. Every declared order issue must have a
stored child in that transaction; late child appends are rejected. Migration
017 is now pinned in migration-plan.json and its actual consumers/storage owners
are registered in the extension registry. The current schema has eighteen steps,
85 domain tables and 219 foreign keys. Earlier preparation and candidate
checkpoints retain their historical scope and artifact pins; unified acceptance
is recorded separately.

The [partial component checkpoint](../reports/acceptance/M3B-07b-stage-storage.json)
archives the [native report](../reports/acceptance/M3B-07b-stage-storage-native.json)
and [installation report](../reports/acceptance/M3B-07b-stage-storage-package.json).
Twelve new/32 combined focused methods and 747 full methods pass; independent
checkout/wheel/installed checks match all 77 source hashes, 76 modules and 41
schemas. Historical M3B-07.a counts above retain their original scope.

Run `.venv/Scripts/python.exe tools/verify_stage_commit.py` for the isolated
candidate probes. Fourteen new native checks cover lossless pending, needed-U
pending, actual staged-parent rework/completion, exact receipts, original
estimate provenance, SQL hash rejection, immutable history, whole-transaction
rollback, a real connection close and simultaneous-writer CAS. The 34 lifecycle
fixture checks are prerequisite evidence and are counted separately. This is
component verification; it does not establish independent account/complete
relationship resolution, relationship-issue/resolution publication, public
command replay or postcommit unknown-outcome reconciliation. Those remain
required before M3B-07.b and parent M3B-07 can be DONE. The storage checkpoint
above is historical component evidence; the following checkpoint advances those
runtime requirements.

## Historical scoped entrypoint checkpoint

[PostgresStageCommandHandler](../src/adapters/postgres_stage_commands.py) accepts
only opted-in command bytes and authenticated request context. Exact grants,
source/account scopes and optional exact definition repositories are injected
independently. Registered USER source/authority must match the command; an owned
grant cannot edit a Task whose immutable birth principal/account is foreign.
Rule-generated Task births additionally reconstruct their original accepted
rule, exact cached definitions and generation receipt ancestry.

Within one checked snapshot the handler resolves the current parent/stage and
all applicable latest incoming hard relations. Each relation is checked against
its accepted authority, normalized storage, audit and historical owner bindings.
Execution evidence uses current Task versions separately from those historical
link bindings. Actual stage completion times come from retained transitions;
unknown starts remain unknown. A reported out-of-order completion commits truth
and its separately audited relationship issue, preserving its prerequisite.

Ambiguous intent, missing necessary U and inactive-parent instructions can save
pending metadata without resolving an unrelated order graph. A later compatible
same-obligation command links matching pending journals to its transition with
full audit/receipt effects. Known earlier fields must agree; correction/new
obligation and foreign-stage instructions stay distinct. Old pending journals
remain immutable: active pending reads must exclude rows with a resolution link.

Both `execute` retries and `lookup` reconstruct the original receipt, full audit,
Task history, observations, historical order inputs and pending-resolution links.
Current grants need not be reinjected and old grants can have expired. Changed
command meaning under the same ID conflicts. `execute` retains the original
expected store revision/audit identity; `lookup` needs neither. Later Task edits
or new relationships cannot rewrite a prior result. Actual precommit connection
loss is retryable; lost acknowledgement after a real outer COMMIT is UNKNOWN
until an owned original-result lookup/retry reconciles it.

Run `.venv/Scripts/python.exe tools/verify_stage_commands.py` for current scoped
entrypoint checks, and `.venv/Scripts/python.exe tools/verify_stage_generated.py`
for actual generated stages and generated-parent receipt ancestry. The latter
also verifies parent-owned U and preserved actual-work history. Prerequisite
lifecycle, storage and generation checks are recorded separately, without adding
their repeated execution to the new entrypoint-case counts.

The linked scoped runtime checkpoint was verified before manifest activation.
Migration 017 and the extension consumers/owners are now registered. Unified CI
and final parent acceptance now pass, as recorded below. The complete application, user transport integration
and live personal activation are not established by these isolated tests.

The [scoped runtime checkpoint](../reports/acceptance/M3B-07b-stage-entry.json)
archives [15 entrypoint cases](../reports/acceptance/M3B-07b-stage-entry-native.json),
[two actual generated endpoint cases](../reports/acceptance/M3B-07b-stage-entry-generated.json)
and [clean installation](../reports/acceptance/M3B-07b-stage-entry-package.json).
Forty-two focused/757 full methods pass; all 78 checkout/wheel/installed source
hashes match, with 77 modules and 41 schemas. Component/lifecycle/generation
fixture checks are separately listed and do not inflate the 17 new native cases.
Both temporary databases are dropped and both PostgreSQL servers stop.

Storage admission retains the fixed byte/count ceilings while current execution
uses the independently configured graph limits. Historical journal reconstruction
does not silently replace a larger accepted graph with the default 4096-endpoint
policy. The boundary regression exercises 4097 facts under an explicit larger
policy and proves ordinary default-policy admission still rejects that size.

## Final runtime acceptance

[M3B-07.b](../reports/acceptance/M3B-07b.json) verifies ten requirement groups and
the complete [parent](../reports/acceptance/M3B-07.json). Final unified CI passes
32 phases, 760 methods and 228 native checks across twelve groups. The stage
groups include 14 storage, 15 entrypoint and two generated endpoint cases once;
repeated prerequisites are excluded. All nineteen databases are dropped, twelve
PostgreSQL servers and both HTTP listeners stop. Clean installation matches 77
modules/78 source hashes and 41 schemas. The pinned eighteen-step runtime is
0.13.0-stage-commands, with 85 domain tables/219 FKs plus three metadata tables;
actual restore verifies all 88 tables. Earlier seventeen SQL files, thirty base
contracts and 91 generic pins are unchanged.

Correction/new-obligation facts remain explicitly pending until their separate
reconciliation/creation facts are supplied. Unknown actual starts remain unknown.
These runtime boundaries do not activate personal profiles, providers, n8n,
models or deployment. Next M3B-08 exposes the complete unresolved review queue.
