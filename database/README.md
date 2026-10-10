# PostgreSQL Ownership and Migration Draft

M2-14.a provides a checked draft, not an application database. M2-01.b extends the [ownership manifest](design/ownership.json) to 30 contracts and 51 relational tables. The [relational model](design/relational.json) declares columns, exact types, keys, checks, 130 foreign keys, one partial unique index and mutable-head guards. PostgreSQL 18 documentation is the reference; the [local toolchain spike](../toolchain/ADR-001.md) separately selects and verifies a project-local 18.6 test runtime. No application database is activated.

Canonical Task/effort, immutable evidence/observations/audit, reviewed configuration/authority, generation/notice state, Goal/Exam, source occupancy, derived Plan/model output and operational outbox/checkpoints have separate owners. Stable course/activity/type defaults remain Git-owned; database configuration registration records identity/version/hash/source references, rather than another authoritative copy of defaults.

PostgreSQL CHECK constraints cannot guarantee facts in other rows/tables; explicit primary/unique/foreign keys protect relational identity, while scoped authority and temporal/state conditions require transactional application checks. NULL semantics must also be explicit rather than assuming that a CHECK excludes unknown values. See the [official constraint reference](https://www.postgresql.org/docs/18/ddl-constraints.html). The [isolation reference](https://www.postgresql.org/docs/18/transaction-iso.html) informs the later CAS/locking/retry design; the [schema reference](https://www.postgresql.org/docs/18/ddl-schemas.html) informs qualified ownership/access.

The five generated batches are [foundation](migrations/001_foundation.sql), [Task/effort/review](migrations/002_task_effort_review.sql), [relationships/notices](migrations/003_relationships_notices.sql), [Goals/Calendar/Plans](migrations/004_goals_calendar_plans.sql) and [AI/operations](migrations/005_ai_operations.sql). Forward and cyclic foreign keys are added after both tables exist. All five batches must pass an isolated migration/constraint rehearsal before any adapter activates the schema. The first batch creates migration metadata and the initial store epoch; a future migration runner must check IDs/hashes and record each applied batch atomically. No runner is implemented by this draft.

## Ownership and history

Captured sources, observations, review frames/responses, versioned domain records, predictions and audit records are append-only. Source deletion, model evaluation/status and job execution/status use separate event logs so an unchanged semantic identity need not be overwritten. Canonical Task/effort belongs to accepted state; a derived prediction has no canonical U column. Exact rational stage weights and allocation/forecast quantities use integer numerators/denominators, while SQL NULL preserves unknown estimates, usage and dates. Numeric/date domains exclude nonfinite values. A completed Stage may retain an absent/old estimate; parent completion and effective effort are separate domain rules.

Only store epoch, current Task head, generation occurrence, outbox and collector checkpoint are mutable. Generated guards preserve their identities, require revision +1 and retain terminal created/delivered identities. Generation uniqueness excludes rule version. Source-record uniqueness treats an unknown external revision as the same nullable deduplication component. Receipt/audit references form a deferred pair; Task/occurrence/outbox/checkpoint audit references bind aggregate ID, revision and transaction. These are proposed database constraints, not proof of authenticated writes or durable transactions.

No runtime role or login is created. Draft DDL revokes PUBLIC schema/table/function privileges and declares history update/delete/truncate guards. An owner can change those protections; later deployment must separate migration ownership from scoped runtime roles and verify grants. Triggers cannot replace caller authentication, exact authority resolution or application validation. See the [trigger reference](https://www.postgresql.org/docs/18/sql-createtrigger.html) and [finite-time functions](https://www.postgresql.org/docs/18/functions-datetime.html).

## Checks and application obligations

Run from the repository root:

```powershell
python tools/check_database_design.py
python tools/render_database_design.py --check
python -m unittest tests.test_database_design -q
```

The checker verifies design structure/reference/type/unique-target consistency, current contract owners and critical accepted scopes. The 21 original design methods and aggregate methods include negative mutations for narrowed batch/observation/detail/provenance bindings, duplicate generation identity, missing audit/eligibility references, mutable history, lost work styles/reserve proof and false runtime evidence. SQL drift checking is read-only. Explicit `python tools/render_database_design.py` regenerates the five checked-in draft files; it never connects to a database. Regeneration is a draft operation; applied/frozen batches require subsequent forward migrations.

These checks do not parse PostgreSQL, execute CHECK expressions/triggers, test locks/crashes or prove migration application. The [native foundation probes](probes/001_foundation.sql) have executed in an isolated PostgreSQL 18.6 cluster. The [current aggregate report](../reports/acceptance/M2-01b.json) records five applied test migrations, 51 tables, 130 foreign keys, foundation/transaction checks and 14 additional aggregate checks. The [historical spike report](../reports/acceptance/M2-16a.json) retains 49 tables/124 foreign keys and its [original SQL checkpoint](../reports/acceptance/M2-16a-baseline/migrations/002_task_effort_review.sql). Neither evidence set verifies every constraint, full adapters or the entire application.

The transaction adapter must independently revalidate caller authority, expected versions/current model/job/Task status, successful notice delivery/current expiration condition, whole unchanged-batch eligibility, graph acyclicity, exact stage/parent accounting, planning proof applicability and final emergency review. Aggregate CAS, JSON-to-column consistency, exact source-scope matching, current milestone-position uniqueness and latest lifecycle projection also remain adapter checks. Nullable composite foreign keys use PostgreSQL's default MATCH SIMPLE; conditional row checks protect the declared optional pairs, and application validation must reject missing semantic references. JSON fields retain reviewed snapshots/extensions/opaque evidence and wrapped collections; they grant no authority. Lossless codecs and full frozen-schema coverage remain future gates.

M2-14.a's SPEC/VERIFY completion and its actual evidence are recorded in [live progress](../plan/PROGRESS.md); full M2/runtime/PostgreSQL durability remain open.

No credentials, real course state, collector account, production channel or user availability has been inferred. The existing [application ports](../formats/input/APPLICATION_PORTS_CONTRACT.md) and [semantic evidence](../tests/fixtures/semantic/README.md) retain their original limitations.
