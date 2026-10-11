# Versioned declarative definition repositories

M3A-06 adds a read-only Git source, an atomic PostgreSQL cache and an in-memory
test repository. Stable definitions remain authoritative in Git. This module
stores explicit versions and their dependencies; importing a definition does
not activate a real course, generate a Task or approve a command.

The shared envelope is the same as [runtime configuration](../config/README.md):

```json
{
  "kind": "TASKTYPE",
  "id": "synthetic-work",
  "version": "1",
  "body": {
    "defaults": {"importance": 3, "total_estimate_seconds": 1800},
    "references": [
      {"kind": "COURSE_PROFILE", "id": "synthetic-course", "version": "1"}
    ]
  }
}
```

Supported kinds are COURSE_PROFILE, ACTIVITY_PROFILE, TASKTYPE, TASK_TEMPLATE,
RELATIONSHIP_RULE and PREFERENCE. The body retains its original fields and raw
UTF-8 bytes. Its optional `references` field contains exact kind/ID/version
dependencies; no latest-version selection or course-specific branch occurs.
This cache reference language does not freeze the full machine Profile or
decomposition-policy schema. Unknown extensions are retained as data and gain
no execution or generation meaning from registration.

## Exact source and immutable versions

[GitDefinitionSource](../src/adapters/git_definitions.py) requires an existing
local repository root and an explicit 40/64-character commit ID, relative POSIX
blob path and canonical envelope SHA-256. It checks commit/blob identity,
the Git object hash, UTF-8/JSON validity and the expected content hash. It rejects
duplicate JSON keys, non-finite numbers, unsafe paths and blobs over 1 MiB.
Uncommitted worktree edits cannot change an exact-commit import. There is no
fetch, checkout, staging, branch update or remote operation.

[Definition values](../src/application/definitions.py) detach mutable JSON
access from retained bytes. Registration binds `(kind, id, version)` to its
first content hash and Git origin. Identical replay preserves initial bytes,
origin and registration time; different content under that identity fails
with `DEFINITION_IMMUTABLE_CONFLICT`. A change requires a new version.

TaskType/template defaults validate importance, requiredness, three difficulty
ratings, durations, fragmentation and workload unit when present. Missing or
null values remain unknown, while an explicit zero total is retained. A
`DefaultSnapshot` is an initial reference; it does not set canonical user
remaining effort, model predictions, actual work or generation authority.
New defaults never update already stored Tasks or their heads.

## Database and transaction boundaries

[006_definition_cache.sql](runtime-migrations/006_definition_cache.sql) is an
additive seventh step in the [migration manifest](migration-plan.json). Its
checkpoint schema version is `0.2.0-definition-cache`. It preserves the original five
domain SQL sources and metadata migration. The M3A-06 checkpoint has 53 domain
tables and 133 foreign keys; three runtime metadata tables are counted
separately. The original M3A-05 six-step manifest is preserved in
[its acceptance snapshot](../reports/acceptance/M3A-05-migration-plan.json).
M3A-07 subsequently adds [Task/stage storage](TASK_REPOSITORIES.md), bringing
the eight-step checkpoint to 57 tables/144 FKs. M3A-08 adds
[source/candidate storage](EVIDENCE_REPOSITORIES.md); the current nine-step schema
has 67 domain tables/162 FKs. M3A-06's seven-step
manifest is also preserved as [a checkpoint](../reports/acceptance/M3A-06-migration-plan.json).

| Artifact | Stored meaning |
| --- | --- |
| configuration_revision | Existing immutable identity/hash/Git-origin header |
| definition_cache | Original body bytes, raw hash, blob path/OID and exact header FK |
| definition_reference | Ordered exact-version dependencies with source/target FKs |

Native checks bind raw bytes to their SHA-256 and require the JSON header and
body object to match the cached identity. Composite and dependency foreign
keys are deferred to permit order-independent batch imports. Update, delete
and truncate history mutations are rejected. The PostgreSQL reader rechecks
the envelope/hash/blob and dependency projection when reconstructing a record.

[PostgresDefinitionRepository](../src/adapters/postgres_definitions.py) reads
only through a schema-checked transaction. Registration additionally requires
the schema-owning migration role and a real GitDefinitionSource. A separate
registry advisory lock serializes imports. All headers, bodies and dependency
rows commit together; a missing reference rolls the entire batch back. An
existing incompatible header fails rather than being overwritten.

`schema_checked_transaction` holds a shared migration lock throughout each
repository operation. It checks the complete migration prefix, supported
application version and recovery state in the same transaction. A migration
cannot run between readiness checking and the operation. The application role
can read definitions but cannot modify any of the three definition tables.
Schema readiness and the migration role do not constitute user Task authority.

`resolve_task_definitions` resolves the exact TaskType and transitive dependency
versions. A COURSE/ACTIVITY context also requires an explicitly supplied matching
Profile key with a registered version. Missing IDs or versions fail rather than
selecting a convenient profile. Reference cycles are traversed once; this is
definition dependency data, not a Task generation/order graph.

## Reproduction and evidence

```powershell
.venv\Scripts\python.exe -m unittest tests.test_definitions tests.test_migrations -q
.venv\Scripts\python.exe tools/verify_definition_repository.py
.venv\Scripts\python.exe tools/verify_migrations.py
.venv\Scripts\python.exe tools/verify_package_install.py
```

[MemoryDefinitionRepository](../src/adapters/memory_definitions.py) uses the
same envelope, immutable values, atomic dependency resolution and versioned
defaults as PostgreSQL. [Focused tests](../tests/test_definitions.py) cover
version conflicts, unknown/zero distinctions, exact profile versions, detached
defaults and negative input cases.

The native verifier creates synthetic commit objects only in a new owned
scratch Git repository and uses the isolated PostgreSQL harness. It proves
all six kinds round-trip, missing dependency rollback, preserved old migration
receipts, read-only application access, native FK/check constraints and lock
exclusion. A synthetic historical Task revision/head remains unchanged after
a new default version is imported. That probe uses existing core Task rows;
the complete Task aggregate repository and canonical creation handler remain
M3A-07 and later work. Current native, migration and clean offline installation
results are archived under [M3A-06 acceptance](../reports/acceptance/M3A-06.json).

Real intake files are unchanged. Full Profile review/activation, real task
creation, decomposition execution and deployment remain separate work.
