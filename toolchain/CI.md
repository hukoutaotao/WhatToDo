# Isolated synthetic baseline CI

M3A-20 provides [.github/workflows/baseline.yml](../.github/workflows/baseline.yml)
and the same [check entrypoint](../tools/run_ci.py) for local and hosted workers.
The selected lock targets Windows x64, Python 3.13.5 and PostgreSQL 18.6; it does
not silently substitute another OS, interpreter or database.

On a fresh Windows worker with the selected Python available:

```powershell
python tools/run_ci.py --bootstrap
```

On a previously bootstrapped checkout:

```powershell
.venv/Scripts/python.exe tools/run_ci.py
```

The first command creates a local environment, installs hash-required wheels
and verifies/extracts the pinned PostgreSQL archive through the existing
[bootstrap](ADR-001.md). Both commands prepare hash-locked build/runtime wheels;
network access to the fixed public artifact sources is required for first setup.
No production account, provider token or existing PostgreSQL instance is needed.

## Checks and failure behavior

The entrypoint first checks source credential signatures/files, Markdown local
links/fragments, catalog prerequisite references/cycles and the closed workflow
policy. It then checks dependency versions, the generic baseline, static package
boundaries, thirty base contracts and ten opt-in extensions, all synthetic shape
bundles, five composed workflows, semantic traceability, database/schema drift,
configuration, authority and the full domain/unit suite.

The package phase builds a wheel and installs it in fresh owned environments,
then imports it outside the checkout without the optional database driver.
Native phases exercise migrations, authority, actual HTTP transport, read models
[backup/restore](BACKUP_RESTORE.md), [typed relationship storage](../database/RELATIONSHIP_STORAGE.md)
[creation outbox](../database/CREATION_OUTBOX.md) and
[composite generation SQL foundation](../database/GENERATION_COMMIT_FOUNDATION.md) and
[actual scoped generation runtime](../database/GENERATION_RUNTIME.md). Each native result must show both stopped
servers and equal created/dropped database counts. The HTTP phase must also show
its listener stopped. Missing evidence is a failure rather than an assumed cleanup.

All checks run sequentially and the first failure returns nonzero. Contract,
credential or authority failure prevents later package/database phases from
running. Synthetic PostgreSQL clusters use loopback, SCRAM, separate roles,
UUID-owned directories and independent server identity checks. Application
modules/schema/dependency versions are unchanged by this CI task.

Tool scripts run as modules from the checkout root; no caller `PYTHONPATH` is
needed. Child processes receive an explicit environment with required OS/tool
paths and controlled Python/pip/Git/temp settings. Provider tokens, GitHub tokens,
caller PG connection settings and pip/Git/Python overrides are not forwarded.

## Published diagnostics

Each run writes a unique closed JSON file under `.local-state/ci-artifacts`.
It contains check names, PASS/FAIL, integer exit/method/check counts, known error
codes, source-tree digest and observed native cleanup booleans. Raw child
stdout/stderr, exception messages, database rows, evidence, connection settings
and credential values are never copied into this report or printed by the runner.

The workflow uploads only those JSON files, including on failure. It does not
upload `.local-state/postgres-tests`, database archives, cluster data, package
installation reports, raw logs or the full workspace. Artifacts retain seven days.
If setup fails before the runner can start, no fabricated test report is emitted.

The source scan blocks known provider/access-key/private-key/database-URI
signatures and local credential file types; it is not a universal secret detector.
Two existing explicitly synthetic negative backup-validator URIs have individual
file/family/match hash annotations. Other values in those files remain checked.
Unknown signatures and binary source formats need a separately reviewed policy.

## Workflow and reproduction evidence

The single workflow uses push/pull_request/manual triggers, read-only repository
permission, an ephemeral Windows 2022 worker and no deployment step. Checkout
does not persist credentials. Actions are fixed to actual commit SHAs, verified
against official [checkout v6.0.3](https://github.com/actions/checkout/releases/tag/v6.0.3),
[setup-python v6.2.0](https://github.com/actions/setup-python/releases/tag/v6.2.0)
and [upload-artifact v6.0.0](https://github.com/actions/upload-artifact/releases/tag/v6.0.0).
Configuration follows [GitHub workflow syntax](https://docs.github.com/en/actions/reference/workflows-and-actions/workflow-syntax).
The `.yml` file uses the JSON flow-style subset of
[YAML 1.2](https://yaml.org/spec/1.2.2/); this permits exact standard-library parsing
without adding an unpinned YAML dependency.

```powershell
.venv/Scripts/python.exe -m unittest tests.test_ci_baseline -q
.venv/Scripts/python.exe tools/verify_ci_rehearsal.py
```

The rehearsal creates a new checkout from current source files, without Git
credentials, environment, database or previous test state. It may seed only the
SHA/size-verified public PostgreSQL ZIP; Python environment and extracted binaries
are created afresh. It runs the workflow entrypoint, then introduces and restores
three deliberate failures: a credential file, an invalid contract fixture and an
authority regression. Each must block at its own gate without publishing the
private failure diagnostic. The original worktree is preserved.

[Acceptance reports](../reports/acceptance) distinguish the fresh Windows worker
rehearsal from a hosted GitHub Actions run. This task does not publish the workflow,
configure branch protection, run remote Actions or certify full runtime release,
live integration, planning or deployment.

The M3B-01 local extension run passes 26 phases, 617 full methods and 132 native
checks across six owned servers/thirteen dropped databases. This is a local
previously bootstrapped checkout run; earlier fresh-worker reports retain their
historical artifact pins. Hosted Actions is still unverified.

The M3B-02 portable graph extension passes 648 full methods and retains all 132
native regression checks. Installed graph cases also pass without the optional
driver; all 66 checkout/wheel/installed source hashes match. The frozen generic
baseline and fourteen-step SQL schema are unchanged.

The M3B-03 local extension run passes 27 phases, 662 full methods and 153 native
checks across seven owned servers/fourteen dropped databases. Both HTTP listeners
stop. All 68 checkout/wheel/installed source hashes match, with 67 modules and
40 schemas. The new fifteenth SQL step is additive; earlier fourteen SQL raw
hashes and the generic baseline are unchanged. See [acceptance](../reports/acceptance/M3B-03.json).

The M3B-04 pure generation extension passes 27 phases, 685 full methods and the
existing 153 native checks. Installed canonical/pending mapping cases run without
the optional driver; all 69 source hashes match, with 68 modules/40 schemas.
The fifteen-step SQL chain is unchanged. [Acceptance](../reports/acceptance/M3B-04.json)
retains the local-checkout scope and separate historical checkpoints.

The historical M3B-05.a checkpoint passes 28 phases, 701 full methods and 164 native checks across eight groups. All fifteen databases are dropped, all eight PostgreSQL servers and both HTTP listeners stop. The new generation group proves metadata/schema constraints only; actual automatic counterpart concurrency/recovery is still M3B-05.b.

The historical M3B-05 checkpoint passes 29 phases, 709 full methods and 181 native checks across nine groups. All sixteen databases are dropped, all nine PostgreSQL servers and both HTTP listeners stop. The runtime group verifies seventeen automatic generation boundaries, including actual concurrent writes, precommit disconnects and successful-commit lost-acknowledgement recovery. Bounded delivery/cascade/restart orchestration is covered by the added `native_generation_worker` group.

M3B-06 adds a tenth native group for finite cascades, checkpoints, changed-input recovery, root budgets, fencing, renewal, real checkpoint disconnects and bounded retries. Its prerequisite generation checks are reported separately, avoiding duplicate summary counts. The M3B-06 baseline passes 30 phases, 715 full methods and 197 native checks. All seventeen databases are dropped, all ten owned PostgreSQL servers and both HTTP listeners stop. Clean installation verifies 73 modules and 74 matching source hashes across checkout/wheel/install; 40 schemas and seventeen SQL resources resolve. [Acceptance](../reports/acceptance/M3B-06.json) records exact scope and artifact pins.

M3B-07.a final local CI passes 30 phases/735 full methods and the unchanged 197 native prerequisite-regression checks. All seventeen databases are dropped, ten servers and both HTTP listeners stop. Installation verifies 74 modules/75 exact source hashes/41 schemas. This verifies detached stage rework/order preparation and installed pending behavior; a native stage command mutation handler remains M3B-07.b. [Acceptance](../reports/acceptance/M3B-07a.json) retains that boundary.

M3B-07.b adds native_stage_commands and native_stage_generated. The first
includes its 14 internal storage cases exactly once together with 15 scoped
entrypoint cases; the second verifies two actual generated endpoint cases.
Repeated lifecycle/generation fixture checks do not inflate these counts.
Duplicate or inconsistent component case declarations fail the summary gate.
[Final acceptance](../reports/acceptance/M3B-07b.json) passes 32 phases, 760 full
methods and 228 native checks across twelve groups. All nineteen databases,
twelve PostgreSQL servers and both HTTP listeners are cleaned up. Installation
verifies 77 modules/78 source hashes/41 schemas; eighteen migrations resolve
0.13.0-stage-commands with 85 domain tables/219 FKs plus three metadata tables.
The earlier seventeen SQL files and generic baseline remain unchanged. This is
local isolated verification, without hosted publication or live activation.

M3B-08 adds `native_review_storage` and `native_review_sources`. Storage checks
whole-capture rollback, immutable ordered membership and continuation; source
checks enumerate admitted Task/manual/clarification/evidence/generation/stage
sources, original-request recovery and actual acknowledgement loss. Repeated
prerequisite fixture cases are excluded from new-case counts. Exact case counts
and HTTP cleanup are required by the summary gate. [Final
acceptance](../reports/acceptance/M3B-08.json) passes 34 phases, 781 full
methods and 247 native checks across fourteen groups. All twenty-three owned
databases, fourteen PostgreSQL servers and all HTTP listeners are cleaned up.
Installation verifies 81 modules/82 exact source hashes/43 schemas; nineteen
migrations resolve 0.14.0-review-queue with 87 domain tables/221 FKs plus
three metadata tables, and actual backup restore verifies all 90 tables. The
earlier eighteen SQL files and generic baseline remain unchanged. This is local
isolated verification, without hosted publication or live activation.

M3B-09 adds `native_review_batches`. It builds the actual nineteen-step
lifecycle predecessor (34 fixture checks reported separately), upgrades through
the pinned twentieth step and verifies confirmed-batch verification without
Task/U mutation, worked-on exclusion, silence-confirms-none, stale-member
conflicts, changed-estimate exclusion, overlap rejection by handler and SQL
unique, original replay, foreign-authority denial, immutable history and
fresh-connection journal reconstruction. [Final
acceptance](../reports/acceptance/M3B-09.json) passes 35 phases, 799 full
methods and 259 native checks across fifteen groups. All twenty-four owned
databases, fifteen PostgreSQL servers and all HTTP listeners are cleaned up.
Installation verifies 83 modules/84 exact source hashes/44 schemas; twenty
migrations resolve 0.15.0-review-batches with 89 domain tables/230 FKs plus
three metadata tables, and actual backup restore verifies all 92 tables
including restored batch replay. The earlier nineteen SQL files and generic
baseline remain unchanged. This is local isolated verification, without hosted
publication or live activation.
