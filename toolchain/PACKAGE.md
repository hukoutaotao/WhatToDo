# Private Python package foundation

The selected Windows x64 / Python 3.13.5 development package is
`whattodo-core==0.1.0.dev0`. It is private and has not been published. Import
paths retain `src.domain`, `src.application` and `src.adapters` to preserve the
pinned M2 interfaces. Use a dedicated environment rather than global installs.

`pyproject.toml` declares build dependencies, runtime dependencies, an optional
PostgreSQL driver extra and the `whattodo-smoke` entry point. Build/runtime locks
pin the cached wheels with SHA-256. The full native toolchain lock remains
separate. The package includes all 30 base contract schemas and their registry,
plus eight explicitly selected extensions for [fact patches](../database/TASK_FACT_PATCHES.md),
[reported actual work](../database/WORK_REPORTS.md) and
[owned reference/clarification](../database/COMMAND_RESOLUTION.md) and
[prototype transport](../formats/input/PROTOTYPE_COMMAND_TRANSPORT.md),
a separate extension registry, and the synthetic runtime example. Default
schema loading still supplies only the base 30 contracts. It excludes personal
intake, plans, tests and tools.
The installed package also includes the seventeen pinned SQL resources and migration
manifest; [runtime migration loading](../database/RUNTIME_MIGRATIONS.md) works
without importing the optional driver until database operations are called.
The [typed relationship storage values/port](../database/RELATIONSHIP_STORAGE.md)
are included; this configuration/transaction port does not activate generation.
The [creation-event outbox](../database/CREATION_OUTBOX.md) values and internal
delivery port are included, with clean-install value checks and optional-driver
absence retained. Delivery processing does not complete the source Task.
The [bounded relationship graph service](../database/RELATIONSHIP_GRAPH_VALIDATION.md)
also runs without the optional PostgreSQL driver; clean-install checks exercise
separate reverse directions, a true hard-order cycle and a traversal limit.
The [generation evaluator](../database/GENERATION_EVALUATOR.md) also constructs
exact-version canonical target and missing-facts drafts without the optional
driver. Its installed smoke retains source/default provenance and unknown U;
actual counterpart persistence and independent authority are later work.
The installed [lifecycle handlers](../database/TASK_LIFECYCLE.md) execute complete
and cancel preparation without the optional driver, and return explicit
driver-unavailable results for database operations. Their source/time/zero
behavior and the separate fact-patch extension are included in clean-install
acceptance; this package does not activate live channels or real profiles.

After the wheel caches have been prepared, run:

```powershell
.venv\Scripts\python.exe tools/verify_package_install.py
```

This creates two new, ignored project-owned environments, builds with pinned
dependencies and installs the resulting wheel offline. It checks imports from
the installed package outside the checkout, compiles all schema resources,
exercises the entry point and validates packaged clocks/configuration without
model credentials or the optional PostgreSQL driver. Existing environments
are preserved. Reports remain under `.dev-tools/package-validation/<run-id>`.
This is local installation evidence, not deployment or cross-platform release
acceptance. Cached wheel hashes are integrity pins, not publisher signatures.

`tools/check_import_boundaries.py` performs static import/clock checks. Domain
code depends on deterministic standard-library/domain modules; application
code cannot import concrete adapters or provider SDKs. Static checks complement
behavior tests; they are not a runtime sandbox.

`UtcInstant` normalizes explicit aware instants to UTC. `ExplicitInstant` retains
the original timestamp/offset and accepts at most microsecond precision.
`DateOnly` retains a calendar date and uses D-075's Beijing 23:59 normalization.
`SystemClock` and `FrozenClock` implement the existing Clock port. Year rollover,
date-only normalization, offset precision and distinct DST fold instants have
focused tests. No scheduler or canonical transition is supplied by these values.

See [configuration precedence and version rules](../config/README.md). Config
loading preserves versioned data and checks secret references without starting
providers or treating definition content as activation authority.

The manifest follows the official
[Python packaging guide](https://packaging.python.org/en/latest/guides/writing-pyproject-toml/)
and [setuptools data-file documentation](https://setuptools.pypa.io/en/latest/userguide/datafiles.html).
Local checks are the authority for the reported installation results.

The installed authenticated prototype API uses a separate bounded envelope
codec, preserving the frozen inner contract limits. It routes to existing handlers
with independent credentials and principal-scoped account bindings. Clean-install
acceptance verifies unauthenticated rejection and explicit optional-driver failure;
it neither starts a live listener nor selects a real user channel.

The installed [read models](../database/READ_MODELS.md) include strict owned query
admission, independently keyed pagination and minimal projections. The current
[acceptance](../reports/acceptance/M3A-17-package.json) covers 62 modules, 40 selected
schemas and all 63 matching installed source files outside the checkout. Database
query operations return explicit optional-driver errors in that clean environment.

[M3A-18 backup/restore](BACKUP_RESTORE.md) adds development-only tools under
`tools/` and tests; application modules, wheel resources and migration pins are
unchanged. The backup tool is not shipped as an application entrypoint. Its native
probe uses the owned local PostgreSQL harness and exports configuration references
without activating adapters.

[Synthetic CI](CI.md) now prepares those locked wheel caches, checks the package
outside a fresh checkout and runs the current domain/contract/native baselines.
The workflow and rehearsal tools remain development artifacts and are not packaged
as application capabilities. Hosted Actions publication remains separate.

[M3A-19 foundation acceptance](../reports/acceptance/M3A.md) reruns bootstrap,
clean package installation, native command/read/restore checks and exact source
comparison in another new checkout. It freezes this prototype evidence at schema
0.8.0-read-models; later relationship/review/runtime work is outside this gate.

[Composite generation preparation](../database/GENERATION_COMMIT_FOUNDATION.md) is also installed without the optional driver. Installed smoke reconstructs its exact receipt/audit and occurrence payload; preparation issues no permit. Current verification matches all 75 source files across checkout/wheel/install, with 74 modules and 41 schemas. The [scoped generation policy/handler](../database/GENERATION_RUNTIME.md) is included; installed smoke exercises explicit optional-driver absence, while native checks verify actual atomic generation and recovery.

[Bounded processing](../database/GENERATION_PROCESSING.md) is installed with typed checkpoints and explicit optional-driver absence. Seventeen SQL resources resolve the current generation-processing schema.

[Stage command preparation](../database/STAGE_COMMANDS.md) is installed with the eleventh opt-in extension. Installed smoke reopens one existing stage, binds a fresh parent estimate and retains unresolved intent without effects; it issues no permit and needs no PostgreSQL driver. All 75 source files match checkout/wheel/install.
