# Exact-version generation evaluator — M3B-04

[The evaluator](../src/application/generation_evaluator.py) constructs one
validated independent Task draft or one parent-with-stage draft, or returns
explicit pending facts. It performs no writes, rule selection, grant issuance,
counterpart deduplication or background work. Those belong to M3B-05/06.

## Trusted inputs

`GenerationSource` binds a typed canonical creation event to its exact original
Task revision and byte hash, original accepted authority and creation source
record. When original acceptance and derivative event authority differ, retain
the immutable creation authorization annotation and check its original grant,
principal and creation target; [the composite handoff](GENERATION_COMMIT_FOUNDATION.md)
explains this trusted-repository binding and required future independent checks.
A raw observation, discovery candidate or unpinned Task cannot enter
this interface. `AcceptedGenerationRule` binds an already stored accepted rule
to the independently resolved principal, user source record and acceptance
time. Both must originate from trusted repositories; Python values alone are
not cryptographic evidence or mutation authority. There is no public endpoint
that accepts fabricated bindings. The source principal must match the rule use.

The caller explicitly supplies one selected rule version and an intended target
ID. Source/target TaskTypes, template and rule cache keys resolve at their exact
versions. The cached rule body must equal the selected stored payload, including
its definition references. Missing keys produce PENDING, never a latest-version
fallback. An inactive rule or mismatched source TaskType is NOT_ELIGIBLE.
The occurrence key reuses the original creation event, excluding the rule version
from occurrence identity while retaining that version in the audit manifest.

## One supported declarative template

The versioned Task-template body allows `references`, `defaults`,
`creation_facts`, `source_facts` and the optional explicit `relation` described in
[the composite handoff](GENERATION_COMMIT_FOUNDATION.md). Existing definition import validates the
default shape; this consumer additionally validates its creation-specific keys.
`creation_facts` holds literal `domain`, optional `context`/exact `profile_ref`,
and stage-only `stage_weight`. `source_facts` explicitly maps these names to
JSON pointers in the original source aggregate. A name cannot occur in both.
Absent required values remain pending; explicit nullable context is preserved.
This schema is an internal consumer format, not a change to frozen wire contracts.

The accepted rule's SOURCE/DEFAULT/LITERAL mappings supply creation fields.
SOURCE supports Task-core aliases and explicit bounded RFC 6901 pointers;
only selected values are copied. Initial importance/requiredness/difficulty
and work/session defaults come from the exact target TaskType/template snapshots.
Conflicting defaults have no implicit precedence; an explicit mapped value can
resolve the affected creation field only. The source's unrelated ratings,
context, estimates and outcome are not inherited automatically.

The returned detached manifest pins the rule key/hash, source event/hash,
principal, acceptance, original user source, template/default keys/hashes/values,
resolved fields and their provenance. Copied fields retain original field evidence
and estimate observation time. Literal/default facts cite the rule's accepted
user source. Schema-essential missing or invalid facts stay PENDING. Complete,
cancelled or already-notified target outcomes cannot be inferred by creation.
An EXPIRING target additionally needs its explicit condition, with no notice.
Course/activity context needs a matching exact profile key.

## Effort and stages

A SEPARATE_TASK has an admitted complete aggregate with its own ID and budget
selection. Original total defaults remain `TEMPLATE_DEFAULT` work facts; they
never automatically become U or a model prediction. Only an explicit approved
remaining mapping creates a prepared user observation, retaining its source.
No model estimate is fabricated to fill an unknown B.

A STAGE requires a supplied current parent snapshot whose ID matches the source
and revision is not older than the captured creation. Construction increments
the parent revision and adds matching stage-detail/effort entries, preserving
all prior parent facts and stages. The draft is later subject to parent CAS.
For course/activity parents the exact current profile binding must also be
supplied and resolved, then retained in the draft. Task and Stage identities
stay distinct even when their text IDs match.
Task-level mapped fields cannot silently change the parent's ratings, requiredness,
expiration or disposition. Inherited TaskType ratings remain parent-level, rather
than independent stage fields. A closed parent or duplicate stage conflicts.
Stage U observations belong to the parent obligation, retain their own identity,
and never create a second parent budget. Existing model-first selection and exact
stage partitioning remain authoritative, including unknown weights and retained
disagreement between stage estimates and parent U.

## Handoff and verification

[Twenty-three focused methods](../tests/test_generation_evaluator.py) cover accepted
default/source/literal mapping, exact versions, missing/conflicting facts,
raw discovery and forged source/rule bindings, principal isolation, profile
scope, expiration, independent versus shared B, current/closed/duplicate parent,
stage observations, pointers, invalid shapes and detached snapshots.
Clean-wheel smoke executes a canonical mapped target and explicit pending case
without the optional PostgreSQL driver. Existing native CI groups verify the
unchanged persistence prerequisites; this pure service introduces no new SQL.

M3B-05 must independently resolve current grants, source/account scopes and
current target/parent state, derive one deterministic target identity, check
occurrence replay, persist missing facts or commit target/link/provenance/audit
atomically. A PROPOSED result here means validated construction, not an executed
or authorized canonical change. Relative-time calculations, live rule selection,
automatic cascade and personal activation are not enabled by this service.

[Acceptance](../reports/acceptance/M3B-04.json) archives eight requirement groups,
23 focused methods and the full 685-method/153-native local regression, plus
CI/installation reports and exact source hashes. All 69 checkout/wheel/installed
source files match; all fifteen SQL files match the previous checkpoint.
Fourteen databases/seven PostgreSQL servers and both HTTP listeners are cleaned up.
