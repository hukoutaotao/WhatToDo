# Manual Task creation from a resolved user instruction

M3A-12 provides `prepare_manual_task` and `PostgresManualTaskHandler.create`.
It connects a single independently resolved user creation instruction to
[schema/authority validation](COMMAND_VALIDATION.md), durable Task storage and
the atomic command ledger. Raw natural language interpretation and pending
review/resolution remain M3A-21/22. No real user channel or course is activated.

## Facts and approved defaults

The handler admits the frozen command and requires an independently
authenticated USER_COMMAND caller, one CREATE_TASK target, matching command
and request IDs, and a separately registered `ResolvedManualIntent`. The
intent binds the normalized command fingerprint, original statement, sourced
observation time, domain/context/reference/work facts and exact approved default
uses. Command JSON cannot populate that registry or manufacture a root grant.

`ApprovedDefaultUse` is independently supplied trusted resolver output. It names
an exact TaskType/template version, acceptance reference and original user
approval source. The persisted acceptance/source must match and belong to the
registered account scope. Cache presence alone never approves defaults or
authorizes creation. Ready drafts still require the independently registered,
persisted exact root creation grant checked by M3A-11.

Selected immutable Git definitions provide initial importance, requiredness,
difficulty and session/total defaults. The handler retains version, content
hash, approved source, copied values and field provenance in the atomic creation
annotation. Explicit user values override only their own fields. Contradictory
defaults have no implicit precedence. Existing Tasks and old retries preserve
their original defaults after another definition version is registered.

Unknown timing and remaining effort stay unknown. A copied original total is
stored as TEMPLATE_DEFAULT with its exact definition reference; a separately
reported total is USER_REPORT. Neither becomes U or a prediction. Explicit
initial U receives a deterministic independent USER_REMAINING observation with
the sourced time and root statement/grant, staged in the same transaction as
Task history, authority annotation, audit, receipt and store epoch. Zero U does
not assert completion. Fresh creation starts INCOMPLETE/ACTIVE with no claimed
delivery, completion time, actual work or inferred stages.

The supporting observation hook accepts only typed resolved user estimates
actually referenced by the exact permitted Task payload. Ownership, value,
source, root authority and observation/verification time are checked before
staging. Append checks the actual SQL row. A rollback removes the observation
as well as the Task/receipt; replay inserts neither again. Actual-work addition,
completion reporting and standalone stage commands remain later handler cards.

## Durable pending details

Missing title/domain/ratings, unresolved exact TaskType/course-profile versions,
missing expiry conditions and conflicting approved defaults produce
`SUCCESS / PENDING_DETAILS` with a `ManualCreationOutcome(state='PENDING')`.
It has no canonical task ID, creation event or commit receipt. It carries an
explicit missing-field list and the complete retained interpretation for review.
Malformed facts and untrusted callers fail rather than being silently repaired.

The tenth forward migration, `009_manual_creation_pending`, adds an immutable
owner for lossless manual drafts. The frozen Candidate contract cannot represent
these unresolved domain/profile/default facts, so its allowlist is unchanged.
The draft retains the desired technical target ID, command/intent/source identity,
original known facts, default snapshots, conflict/missing paths and original
proposal bytes/hash. SQL verifies envelope/hash/source bindings and prohibits
update/delete/truncate. Principal/command/interpretation uniqueness deduplicates
repeated input. No Task, Task audit, authority or store epoch is minted for a
pending result.

`get_pending` requires the original authenticated principal and registered source
account scope. It returns the original known facts and missing fields across a
fresh connection. Pending drafts are historical interpretations, never a second
canonical truth store. Review resolution will append its own decisions/linkage
under M3A-21/22; this card does not invent an acknowledgement or mark an old draft
resolved from a guessed later task.

## Creation identity and retry

The handler preserves the original request ID, expected store epoch and audit ID.
Atomic publication creates one Task identity whose creation transaction is that
request. The returned receipt and `creation_event_ref` identify the same canonical
creation, available to later relationship/outbox handlers. This is an event link,
not a separately dispatched event or notification.

Owned replay reads the original immutable after-version and verified command,
audit and creation provenance. It rebuilds the original concrete request, then
uses the command service's ledger checks. It does not require live intent/default
readers, an active new grant or another approval. Changed meaning, audit or
expected version under the same ID conflicts; no new Task/observation is created.
Unknown or unavailable commit outcomes preserve the coordinator's result.

## Verification and next scope

```powershell
.venv\Scripts\python.exe -m unittest tests.test_manual_tasks -q
.venv\Scripts\python.exe tools/verify_manual_tasks.py
.venv\Scripts\python.exe tools/verify_migrations.py
.venv\Scripts\python.exe tools/verify_package_install.py
```

Ten focused methods, 26 native manual-create checks and 406 full methods pass.
Native regression also retains 25 authorization checks, 22 atomicity checks,
21 ledger checks, 31 Task checks and 34 evidence checks. Migration acceptance
passes 29 checks with ten steps, 68 domain tables and 163 foreign keys plus
separate metadata. Nine prior SQL pins and the 91-artifact generic baseline are
unchanged; the prior nine-step checkpoint manifest is preserved.

Fresh offline installation across 45 modules verifies ready and pending drafts,
separate initial U and the explicit optional-driver result. Tests use actual
Git objects and owned isolated PostgreSQL databases, inject a real server SQL
error after observation staging, and stop all owned clusters/drop their databases.
They use synthetic resolver/caller/approval inputs and no real accounts.

Next ready card is M3A-13 allowlisted Task fact updates. Frozen command fields
cannot express deadline or standalone stage edits; their contract evolution
must be explicit. Complete StateStore/read services, raw intent interpretation,
pending review, generation dispatch and runtime activation remain open.
Executed evidence is [M3A-12](../reports/acceptance/M3A-12.json);
[PROGRESS](../plan/PROGRESS.md) records current status and later work.
