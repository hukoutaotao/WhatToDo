# Scoped unchanged-estimate batches — runtime handoff

M3B-09 is **DONE** at its synthetic scope. Final unified acceptance passes 35
CI phases, 799 full methods and 259 native checks across fifteen groups, with
24 owned databases dropped, fifteen PostgreSQL servers and all HTTP listeners
stopped. Clean installation verifies 83 modules, all 84 matching
checkout/wheel/installed source files and 44 schemas. The complete
[acceptance](../reports/acceptance/M3B-09.json) archives the observed evidence.
No personal workflow is activated.

- `src/application/review_batches.py` defines the versioned batch command,
  per-member bindings (task ID, revision, original observation ID and seconds),
  the independent grant, deterministic verification identities bound to
  review/frame, statement, batch, task and estimate, and the immutable journal
  plus exact commit plan. One invalid member rejects the whole batch. A batch
  without an explicit confirmed flag records no member verification: silence
  confirms none.
- `src/adapters/postgres_review_batches.py` is the scoped entrypoint and
  internal writer. It independently resolves caller identity, registered
  authority and per-member current evidence — the current Task head, the
  factual worked-on state derived from committed positive actual-work
  observations after the estimate's observation time, and any prior
  verification of the same estimate — inside one owned transaction. The writer
  re-reads and re-validates every member before publication. Verification
  preserves original U, its observation ID and observation time; it records a
  separate verification time and never mutates Tasks, stages or actual work.
- `database/runtime-migrations/019_review_batches.sql` is the pinned twentieth
  step at `0.15.0-review-batches`. `review_batch_confirmation` binds the
  command bytes, exact fingerprint, review/frame/statement identity and state
  through its runtime payload. `review_batch_verification` pins each member's
  task revision and original estimate (observation ID, seconds, observation
  time) with the separate verification time; `UNIQUE(task_id, observation_id)`
  rejects overlapping confirmed batches at the SQL level even if a writer is
  bypassed, and every verification writes one `UNCHANGED_VERIFICATION`
  `effort_observation` row bound to its batch without any numeric seconds.
- `formats/extensions/review-batch.schema.json` is the registered opt-in
  contract. The package selects 44 schemas and twenty migration steps; the
  base thirty contracts and all nineteen prior SQL raw hashes are unchanged.

Member eligibility follows the accepted review contract: only current,
future-relevant, ACTIVE/INCOMPLETE Tasks with an existing estimate qualify.
Worked-on (positive actual work after the estimate), missing, changed
(observation ID or seconds) estimates are excluded — any such member rejects
the whole command. A stale member version conflicts instead of silently
approving changed values. Work status that cannot be stated as untouched
requires an explicit no-work statement; a positive new-work increment can never
hide inside a batch. Confirming an estimate invents no completion answer and
no actual-work observation of zero.

Run `.venv\Scripts\python.exe -m unittest tests.test_review_batches -q` for the
seventeen focused checks and `.venv\Scripts\python.exe tools/verify_review_batches.py`
for the owned local PostgreSQL probes. The latter builds its actual
nineteen-step predecessor through the lifecycle fixture (34 prerequisite
checks reported separately), upgrades through the pinned twentieth step and
runs eleven new batch cases. The pinned twentieth step resolves
`0.15.0-review-batches` with 89 domain tables/230 FKs plus three metadata
tables; actual backup restore verifies all 92 tables including restored batch
replay. M3B-10 consolidated evening review state is next; personal activation
remains deferred.
