# M3A persistence foundation acceptance

Status: **PASS at the synthetic generic prototype scope**, verified 2026-10-10.
[Machine evidence](M3A.json) records the executed fresh-worker results, exact probe
IDs, runtime artifact hashes and cleanup. [Live progress](../../plan/PROGRESS.md)
remains the authority for later work.

The accepted foundation provides authorized, audited, replayable PostgreSQL
Task operations and scoped prototype reads. It closes
[M3A-19](../../plan/tasks/M3_STATE_FOUNDATION.md#m3a-19) and permits the next
relationship/review phase. It does not close the full application or user setup.

## Reproduce

On the selected Windows x64 / Python 3.13.5 toolchain, from the repository root:

```powershell
.venv/Scripts/python.exe tools/verify_persistence_foundation.py
```

[The gate entrypoint](../../tools/verify_persistence_foundation.py) copies current
source into a new UUID directory under `.dev-tools/foundation-validation` without
Git credentials, environment, database or previous test state. It may seed only
the public PostgreSQL ZIP after checking its exact size/SHA; bootstrap verifies it
again and extracts fresh binaries. It runs `python tools/run_ci.py --bootstrap`
there, followed by six targeted time primitive methods and exact installed-source
comparison. First setup needs access to the pinned public package/archive sources.

The resulting `foundation-report.json` stays in the owned validation directory.
No production endpoint is accepted, no global service/environment is changed,
and the existing worktree is not overwritten. CI publication is limited to its
[closed diagnostics](../../toolchain/CI.md); databases, backups and raw logs are
not uploaded.

## Requirement-to-evidence audit

This table follows the card's actual acceptance scope. Exact executed probe IDs
are retained in the machine report; assertions were checked in the current native
verifier implementations, not inferred from test names alone.

| Requirement | Executed evidence and result |
| --- | --- |
| Create → patch → effort → complete | [Actual loopback HTTP verifier](../../tools/verify_command_transport.py) applies these operations to the same `api-task` through existing independently authorized handlers. Task/audit/receipt publication succeeds; explicit U and actual work stay separate; completion zeroes U and preserves history. |
| Stale writes | [Authorization verifier](../../tools/verify_authorization_pipeline.py) commits a concurrent winner between validation and publication. The stale loser conflicts without publishing its Task/audit/receipt; the winner remains intact. |
| Duplicate commands | HTTP replay returns the original receipt and leaves state unchanged. Restarted lookup/retry and [restored replay](../../tools/verify_backup_restore.py) recover original owned commits without new grants or duplicate publication. |
| Unauthorized writes | Independent HTTP principal/Task scope and domain grant/source-account checks reject forged, external and unauthenticated callers without canonical effects. Authentication alone cannot replace an exact domain grant. |
| Atomic failure and unknown commit | A real precommit failure rolls back Task/audit/receipt/epoch. Same-command retry commits once. Lost acknowledgement after a real commit remains UNKNOWN until lookup/replay observes the original receipt. |
| Separate restore and original source preservation | [Backup verifier](../../tools/verify_backup_restore.py) restores 73 domain/three metadata tables and catalog/sequence state into a separate empty database. Typed row digests, canonical history, due offset/microseconds and audit/receipt lookup match; the source and its later concurrent Task remain unchanged. |
| Corrupt/failed restore | Corruption is rejected before client start. An actual late trigger-creation failure rolls the whole restore back; trusted retry succeeds. Source/occupied targets are rejected and later catalog drift is detected. |
| Clean source checkout without providers | New checkout/bootstrap runs all 26 CI phases with no inherited Python environment, database or credentials. No live model, connector, Calendar or n8n service is used. |
| Time and current artifact compatibility | Six focused clock/time methods pass. All 63 installed Python files match the current 62-module source tree; 40 selected schemas and thirteen migration pins are checked at `0.8.0-read-models`. |
| Cleanup | All twelve native databases are dropped; all five PostgreSQL servers and both HTTP listeners stop. Initial/client password files are absent. |

The full suite passes **602 methods**. Native groups pass **113 checks**:
29 migrations, 25 authority, 23 HTTP transport, 20 reads and 16 backup/restore.
The six targeted clock methods are part of that suite, not six additional unique
tests. Fifteen explicit gate requirements pass. Current library/tool/test/schema/
SQL/config inputs have 209 exact artifact hashes in the report; the source-tree
digest is the pre-acceptance snapshot, before writing this report and progress.

## Prerequisites, preservation and limits

[M3A-02 time values](M3A-02.json),
[M3A-18 backup/restore](M3A-18.json) and
[M3A-20 CI](M3A-20.json) were DONE before this gate ran. The gate executes their
current relevant behavior again. Earlier acceptance reports retain their original
scopes and hashes; the new report records current inputs. No application module,
dependency, contract or migration is changed by this verification task. Thirty
base contracts and ninety-one generic baseline pins remain intact.

This is a reproducible fresh local Windows source checkout, not an observed hosted
GitHub Actions run or a remote publication. The prototype's independent callers,
grants, source bindings and cursor keys are supplied by synthetic trusted fixtures;
real user/account activation is separate. CREATE_TASK is the implemented first
natural/guided normalization class; other repeated classes remain incomplete.

Relationship persistence/graph evaluation, event outbox/generation, complete review
and expiration application paths, other full StateStore operations, provider/n8n/
model integration, personal intake, planning/learning, production recovery and
deployment remain open. The semantic catalog still explicitly retains unmapped
decisions. This gate does not certify those later requirements or a full release.

Next ready card: [M3B-01 typed relationship repositories](../../plan/tasks/M3_RELATIONSHIPS_REVIEWS.md#m3b-01).
