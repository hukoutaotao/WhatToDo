# Private Python package foundation

The selected Windows x64 / Python 3.13.5 development package is
`whattodo-core==0.1.0.dev0`. It is private and has not been published. Import
paths retain `src.domain`, `src.application` and `src.adapters` to preserve the
pinned M2 interfaces. Use a dedicated environment rather than global installs.

`pyproject.toml` declares build dependencies, runtime dependencies, an optional
PostgreSQL driver extra and the `whattodo-smoke` entry point. Build/runtime locks
pin the cached wheels with SHA-256. The full native toolchain lock remains
separate. The package includes all 30 contract schemas, their registry and the
synthetic runtime example. It excludes personal intake, plans, tests and tools.
The installed package also includes the six pinned SQL resources and migration
manifest; [runtime migration loading](../database/RUNTIME_MIGRATIONS.md) works
without importing the optional driver until database operations are called.

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
