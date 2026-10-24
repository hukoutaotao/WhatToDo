# Complete review queue — runtime handoff

M3B-08 is **DONE** at its synthetic scope. Final unified acceptance passes 34
CI phases, 781 full methods and 247 native checks across fourteen groups, with
23 owned databases dropped, fourteen PostgreSQL servers and all HTTP listeners
stopped. Clean installation verifies 81 modules, all 82 matching
checkout/wheel/installed source files and 43 schemas. The complete
[acceptance](../reports/acceptance/M3B-08.json) archives the observed evidence;
historical capture and source checkpoints are preserved. No personal workflow
is activated.

- `src/application/review_queue.py` defines the registered query/page contracts,
  immutable questions, full-capture hashes and authenticated cursors. A shorter
  target duration changes no membership; low-priority and future questions remain.
- `src/adapters/postgres_review_queue.py` is an internal transaction-bound store.
  A page reloads the stored owner, query, account-scope hash and expiry before
  reading captured rows. New canonical data does not rewrite an existing page.
- `src/adapters/postgres_review_sources.py` enumerates every scoped active
  incomplete Task plus admitted manual/clarification/evidence/generation/stage
  pending sources. There is no deadline horizon or optional/importance filter.
  Unknown work remains unknown. Unadmitted legacy sources or unavailable
  generation definitions produce explicit coverage blockers.
  Generated birth receipts use the admitted history depth ceiling rather than
  the default execution policy; the queue does not authorize new generation.
- `src/adapters/postgres_review_service.py` exposes raw query admission with
  independently authenticated caller and configured account scope, stable
  initial-request replay and signed continuation. Actual capture commit followed
  by lost acknowledgement returns UNKNOWN; retry recovers the original frame.
- `database/runtime-migrations/018_review_queue.sql` is the pinned nineteenth step.
  It rejects missing entries, payload corruption, historical mutation and entry
  insertion outside the new capture transaction. Failed capture rolls back the
  header and every entry; capture does not change canonical Tasks or store epoch.
- `formats/extensions/review-queue-query.schema.json` and the companion page
  schema are independently registered opt-in extensions. The package selects
  43 schemas and nineteen migrations at `0.14.0-review-queue`; the default thirty
  contracts and all eighteen prior SQL files are unchanged.

The wire byte budget includes group metadata, cursors and envelope fields as
well as question bodies. A page advances only past returned questions. If a
whole capture cannot fit even one question beside its metadata, admission fails
explicitly; the implementation does not drop questions or groups to make it fit.
Presentation and successful synchronization never submit answers or establish
personal reconciliation, including an empty queue. Expiry invalidates a cursor
without deleting its unanswered history.
Resolved clarification waiting for execution and source-coverage blockers have
`requires_response=false`; other outstanding questions retain true. Neither
case contains a submitted answer. Legal producer questions up to 1 MiB fit the
explicit 2 MiB item and 4 MiB complete-page ceilings without shortening intent.

Historical component commands remain reproducible. Run
`.venv\Scripts\python.exe -m unittest tests.test_review_queue -q` for pure
checks and `.venv\Scripts\python.exe tools/verify_review_queue_storage.py` for
the owned local PostgreSQL component probes. The latter uses synthetic supplied
questions and explicitly reports incomplete source coverage.
Run `tools/verify_review_sources.py` for actual admitted read, stage and generation
fixtures, including initial-request replay, scope isolation, low-priority future
tasks, missing personal estimates, ready intent, concurrency and acknowledgement
loss. Repeated prerequisite fixture cases are counted separately.

The pinned nineteenth step resolves `0.14.0-review-queue` with 87 domain
tables/221 FKs plus three metadata tables; actual backup restore verifies all
90 tables. M3B-09 scoped unchanged-estimate batches is next; answer submission
and evening review coordination are separate cards.
