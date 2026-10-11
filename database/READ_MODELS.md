# Owned Task, pending and semantic-history read models

M3A-17 provides a basic read service over the existing accepted Task/audit/evidence
repositories. It returns owned versioned records and retained outcomes. It does
not produce a feasibility-verified Daily Brief or alter personal course data.

- [Query and snapshot values](../src/application/read_models.py)
- [PostgreSQL projections](../src/adapters/postgres_read_models.py)
- [Authenticated prototype transport](../formats/input/PROTOTYPE_COMMAND_TRANSPORT.md)
- [Read query contract](../formats/extensions/read-query.schema.json)
- [Read page contract](../formats/extensions/read-page.schema.json)
- [Native acceptance](../reports/acceptance/M3A-17.json)

## Trusted runtime handoff

Construct `PostgresReadService` with an idle autocommit connection, explicitly
selected extension codec, checked migration plan/application version, injected
clock, independent `cursor_key` bytes (32-128 bytes) and independently registered
`SourceScope` values. The factory supplies account scopes for that authenticated
principal. It must retain the cursor key across process restarts; changing the
key invalidates old cursors. JSON cannot supply caller identity or account grants.

Call `query(raw_query_bytes, RequestContext(...), caller=authenticated_user)`.
The result is `PortResult[ReadPage]`. A complete initial query captures immutable
references and projects the first page in one schema-checked repeatable-read
transaction. Later pages use read-only transactions over the captured versions.
Only the initial query writes process metadata; neither path changes canonical
Tasks, authority, audits, receipts, actual-work observations or the store epoch.

For HTTP, grant the independent credential the `QUERY_STATE` operation and full
Task reference scope. Use the existing `/v1/commands` endpoint with exact query
JSON text in `payload` and `{}` in `parameters`. Inject `read_cursor_key` into
`PostgresPrototypeBackend`; absent configuration returns
`READ_SERVICE_UNCONFIGURED`. Existing explicit operation grants are not silently
expanded. Authentication and operation/reference scope checks precede the factory.
The success envelope has `data.kind = READ_PAGE` and its closed result matches the
read-page contract. This is a local prototype handoff for future n8n integration;
no provider, real credentials or live channel is configured here.

## Query and page contract

Every `0.1.0-read-query` has exactly these fields:

| Field | Meaning |
| --- | --- |
| view | TASKS, HISTORY or PENDING |
| task_id | Exact owned Task ID for HISTORY; null otherwise |
| filters | Exact completion/disposition/trust/domain/context filters; each nullable |
| pending_kind | Nullable MANUAL_CREATION, EVIDENCE_CANDIDATE, EVIDENCE_CONFLICT or CLARIFICATION |
| include_closed | PENDING only; false on other views |
| page_size | Integer 1-100; rejects boolean/float/string coercion |
| cursor | Null for a new snapshot; opaque signed continuation otherwise |

Filters always include all five keys. Context is null or an exact `{kind,id}`
reference, not a display-name match. Only TASKS accepts non-null filters; other
views require all null. Only PENDING accepts pending-kind/closed flags. Unsupported
versions, unknown fields and inapplicable combinations fail explicitly. Query
input is bounded to 8 KiB before schema admission.

A page retains snapshot ID, captured store revision, observation/expiry instants,
query fingerprint, source-scope coverage, items, `has_more` and `next_cursor`.
A terminal page uses false/null. Empty results are successful only for the
requested authorized view; unavailable Task history is a typed error, not an
empty list. `source_scope_state` is CONFIGURED for registered evidence scopes,
UNCONFIGURED when no evidence scopes were supplied, and NOT_APPLICABLE for
Task/history or only owned manual/clarification pending. UNCONFIGURED is not a
claim that all external accounts have no pending work.

## Views and retained truth

TASKS reads owned current heads, including retained COMPLETE/CANCELLED/EXPIRED
records unless a filter excludes them. CURRENT means current at snapshot capture.
Each item has Task ID/revision, title, domain/context/type, separate completion
and disposition, requiredness/importance/three-axis difficulty, independent trust,
nullable canonical user remaining, actual seconds, nullable original total,
lossless timing and minimal field/source references. Unknown remaining is null;
completed zero is an observation with zero seconds. Actual work is independent
and never subtracted from remaining. No completion/work times are inferred.
Internal authority/default payloads, prediction/stage payloads, source bodies,
provider locators and transport credentials are omitted from this basic view.

HISTORY reads immutable Task revisions in ascending order. Every item links its
exact command, audit/change IDs, origin, commit/store revision/time and source
reference. The service verifies full before/after audit values against repository
versions before returning a minimal semantic change list. Revision-only and
provenance-only differences are excluded from that list. Actual seconds are
captured separately for each historical commit boundary. Completion, cancellation
and expiry remain independently visible; current state cannot rewrite old events.

PENDING returns four minimal summaries. Manual creation exposes known title and
missing fields, not internal proposal JSON. Candidate/conflict records require
registered source-account scopes. A candidate's content revision and its
`pending_ref` review-state revision are distinct. Oversized external
candidate titles remain unknown in this summary; their exact immutable proposals
remain retained and are not coerced into Task facts. Conflict summaries exclude
observed conflicting wire. Clarification exposes question/choices/missing fields;
an answered RESOLVED frame stays OPEN until a matching audited canonical command
actually commits. A matching commit closes it as RESOLVED; another committed
outcome under the command closes it as SUPERSEDED. `include_closed` retains these
summaries. Manual pending closes from the owned canonical creation receipt,
without deleting its immutable proposal history.

## Stable pagination and failure behavior

Migration `012_read_snapshots` adds one immutable process-metadata table, not a
Task effect. The current thirteen-step schema is `0.8.0-read-models`: 73 domain
tables/177 foreign keys plus three migration metadata tables. All twelve previous
migration receipts and the original five SQL drafts remain unchanged.

Snapshots persist exact version references, captured pending states and actual
seconds. Signed cursors bind snapshot ID, position, authenticated principal and
query fingerprint (including filters/page size). A new insertion, Task mutation,
actual report, answer or pending closure cannot change subsequent pages. Restart
with the same key preserves the snapshot. Changing filters/page size/principal
conflicts; tampering or a different key fails validation. Evidence-account binding
changes conflict rather than silently broadening/narrowing access.

The default snapshot lifetime is 24 hours and may be explicitly configured from
one second through seven days. An expired cursor returns READ_SNAPSHOT_EXPIRED;
the consumer starts a new query rather than silently mixing pages. Snapshots are
immutable and retained; physical retention cleanup is a separate future operation.
Capture allows at most 50,000 references and 8 MiB of internal metadata. Excess
queries fail explicitly. Public pages remain within the frozen 256 KiB contract
limit, with a 240,000-byte item budget and at most the requested number of items.
A large item fails explicitly; a byte-limited page can contain fewer items while
retaining a correct continuation. No dataset is silently truncated.

Owned raw bytes/hash/projection or audit drift returns a typed failure rather
than an empty success. Scope/query/expiry conflicts are distinguished from
permanent input/integrity failures and retryable database unavailability.
Precommit cache faults roll back metadata and leave canonical state unchanged.
The HTTP wrapper preserves its existing UNKNOWN reconciliation behavior if a
backend exit or response serialization fails after its transaction returns.
QUERY_STATE creates no canonical command receipt. A lost query response can be
read again with the same cursor; when the initial result is lost, a new initial
query produces a new coherent snapshot without any canonical mutation.

## Observed evidence

- `.venv/Scripts/python.exe -m unittest tests.test_read_models -q`: 31 methods pass.
- `.venv/Scripts/python.exe -m unittest discover -s tests -q`: 556 methods pass.
- `.venv/Scripts/python.exe tools/verify_read_models.py`: 20 native checks pass,
  including actual HTTP, restart/interleaved pagination, all retained outcomes,
  pending closure/version separation, source/caller isolation, typed failures,
  immutable cache guards and rollback.
- Current native regressions: [migration 29](../reports/acceptance/M3A-17-migrations.json),
  [transport 23](../reports/acceptance/M3A-17-transport.json),
  [resolution 23](../reports/acceptance/M3A-17-resolution.json),
  [evidence 34](../reports/acceptance/M3A-17-evidence.json),
  [Task storage 31](../reports/acceptance/M3A-17-tasks.json). Every owned database was
  dropped and every HTTP/PostgreSQL server stopped.
- [Fresh offline installation](../reports/acceptance/M3A-17-package.json) checks
  62 modules, 40 selected schemas and 63 byte-identical installed Python files;
  query/cursor/projection and authenticated routing work without the optional
  database driver and return its explicit unavailable result.

The thirty base contracts, ninety-one baseline pins and dependencies are unchanged.
This closes only M3A-17. Backup/restore, foundation gate, later application
services, provider/n8n/model runtime, planning, learning and deployment remain
separate work. Personal intake and activation remain deferred under D-080.