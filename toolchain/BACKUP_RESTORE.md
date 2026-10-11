# Synthetic development backup and restore

M3A-18 backs up the owned prototype and restores into a different, newly created
database. [Acceptance](../reports/acceptance/M3A-18.json) records the actual
PostgreSQL checks. This is a development probe, not a production recovery service.

From the repository root, after the pinned [toolchain setup](ADR-001.md):

```powershell
.venv/Scripts/python.exe -m unittest tests.test_development_backup -q
.venv/Scripts/python.exe tools/verify_backup_restore.py
```

The second command starts a UUID-owned PostgreSQL 18.6 cluster on loopback with
SCRAM and separate roles. It creates synthetic state, exports a custom archive,
restores two separate databases, exercises failure cases, drops all three test
databases and stops its server. Its redacted report is written under
`.local-state/postgres-tests/<run-id>/backup-restore-report.json`. Synthetic
archives remain local for inspection; do not publish them as CI failure artifacts.

## Bundle and API

[development_backup.py](../tools/development_backup.py) is a development tool;
it is outside the installed application package. Its callable boundary is:

```python
bundle = create_backup(harness, source_database, plan=plan,
                       application_version=version, config=config, clock=clock)
restored = restore_backup(harness, empty_database, bundle, plan=plan,
                          application_version=version)
validate_restored(harness, empty_database, bundle, plan=plan,
                  application_version=version)
```

The caller owns a `PostgresHarness`, its tracked database identities, the exact
migration plan, reviewed `RuntimeConfig` and an aware clock. Arbitrary servers,
connection strings, roles and filesystem destinations are not accepted. The
returned immutable `BackupBundle` holds a directory and an independently retained
manifest SHA-256. Preserve that pin outside the bundle; a hash read from a modified
manifest cannot replace it.

Each `backup_<uuid>` directory has exactly three files:

| File | Contents |
| --- | --- |
| `database.dump` | Custom archive of `whattodo` and `whattodo_meta` |
| `configuration-refs.json` | Definition identity/version/hash, adapter modes and secret environment-variable names |
| `manifest.json` | Application/schema/PostgreSQL versions, migration hashes, source identity, file pins and state/catalog digests |

Configuration references carry no activation authority, secret values, definition
file paths or global role passwords. The database archive retains the synthetic
definition cache and source evidence needed to verify persistence. Runtime
credentials, cursor signing keys and external Git definition sources must be
rebound independently by a trusted caller.

## Consistency and restoration checks

The archive and row/catalog digests share one exported repeatable-read snapshot;
the exporter transaction stays open during `pg_dump --snapshot`. A native test
commits another Task during capture and proves that both archive and digests keep
the earlier state. Sequence state is compared before and after capture; a change
rejects the bundle rather than claiming a coherent export. Snapshot export is
supported by [PostgreSQL's dump interface](https://www.postgresql.org/docs/18/app-pgdump.html).

Validation streams typed, length-delimited, ordered row digests for all 76 tables,
including migration metadata, immutable audit versions and command receipts. Ten
catalog categories cover columns, constraints, indexes, functions, triggers,
domains, table/sequence grants, function grants, schema grants and sequence
definitions. CHECK comparison normalizes associative AND/OR groups while retaining
operands, order, precedence and constraint flags. ACL comparison expands effective
grants, including default ACLs; PostgreSQL distinguishes lowercase `s` for sequence
defaults from uppercase `S` for foreign servers in
[its catalog functions](https://www.postgresql.org/docs/18/functions-info.html).

Restore rejects the source database, occupied targets, unsupported versions,
changed migration pins, unknown bundle files, oversized files and corrupt hashes
before starting its client. It restores with `--single-transaction`,
`--exit-on-error` and `--no-owner`, retaining reviewed ACLs and recreating
constraints/triggers. It uses no clean/create, superuser or trigger disabling
options. PostgreSQL documents the all-or-nothing transaction behavior in
[pg_restore](https://www.postgresql.org/docs/18/app-pgrestore.html).

The native probe verifies current/historical Task bytes, independent completion
and cancellation, original due-time offset/microseconds, total/U/actual-work
values, owned receipt lookup/replay, pending clarification and continued read
pagination. It also verifies application/verifier privilege restrictions.
A deliberately missing function causes a late trigger-creation failure: the
entire restore rolls back and retry into the same empty target succeeds.
A later extra table is detected even with unchanged migration receipts.

## Credentials, errors and limits

Each client receives an explicit environment containing only required OS values
and owned PostgreSQL settings. It does not inherit provider credentials or caller
PG connection overrides. The temporary password file lives outside the bundle and
is removed on success or failure. Reports contain stable error codes and bounded
schema-category diagnostics; client stderr and raw database rows are not emitted.

Archive, manifest and configuration limits are respectively 128 MiB, 2 MiB and
256 KiB. A successful validation returns `VERIFIED`, the table count and captured
store revision. A restored-state mismatch returns
`BACKUP_RESTORED_STATE_OR_SCHEMA_DRIFT`; client rollback failure returns
`BACKUP_RESTORE_FAILED`. A postrestore validation failure leaves that separate
target isolated and unaccepted; it never authorizes a cutover.

Checksums detect corruption, not the authority or safety of executable database
content. Only trusted synthetic archives are accepted in this harness. This probe
does not establish production retention, continuous recovery, remote storage,
point-in-time recovery, deployment or personal activation.
