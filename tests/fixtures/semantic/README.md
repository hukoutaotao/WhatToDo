# Offline Semantic Traceability and Scenarios

M2-13.a connects accepted requirements to existing structural/domain tests and composed synthetic workflows. [Decisions](../../../plan/DECISIONS.md) remain authoritative; the catalog is an evidence index, not a competing policy or release checklist. [Live progress](../../../plan/PROGRESS.md) records executed results.

## Artifacts and Command

- [catalog.json](catalog.json): inventories all 80 current decision IDs; 18 bounded semantic rows map 58 of those IDs to concrete fixture IDs, test methods and scenarios. The remaining 22 decisions are explicitly unmapped. A row is partial offline evidence for its stated requirement, not complete implementation of each linked decision.
- [scenarios.json](scenarios.json): 11 synthetic workflows with independent, explicit input and expected output. The expectations are authored from accepted semantics, never generated from observed implementation output.
- [Scenario helpers](../../semantic_scenarios.py): compose existing domain helpers and no-I/O fake adapters. They read only scenario kind/inputs, not expected output.
- [Catalog checker](../../../tools/check_semantic_catalog.py): verifies scoped metadata, stable identities, decision inventory, existing positive/negative schema cases, real test-method references and complete scenario mapping, then compares observed scenarios and executes all 50 unique referenced test methods.
- [Focused regressions](../../test_semantic_catalog.py): verify broken/duplicate references, missing limitations, unknown scenario fields, bounded oracle work and independent expectations.

Run from the repository root:

```powershell
python -m tools.check_semantic_catalog
python -m unittest tests.test_semantic_catalog -q
```

The existing Task-core bundle predates the shared per-case `contract` field; the checker resolves that known legacy bundle specifically to `task-core`, preserving its actual expected cases. Other bundles use their explicit contract names. Schema validity is checked against each case's expected validity, independently of behavioral tests.

## Composed Evidence

| Scenario | Accepted boundary / observed composition |
| --- | --- |
| SC-001 | B below U drives required forecast; canonical U unchanged. |
| SC-002 | B above U can change SAFE to DANGER without rewriting U. |
| SC-003 | A positive whole-day capacity margin does not make a hard-window task feasible. |
| SC-004 | Confidence-one external completion claim remains pending and cannot authorize canonical completion. |
| SC-005 | Exact eligible untouched batch produces an audited verification; worked task and pending candidate keep full review open. |
| SC-006 | Canonical source maps preparation generation while preparation has reverse completion order; authorization, stable occurrence replay and parent counting remain separate. |
| SC-007 | Unknown notice blocks resend, original receipt reconciliation permits revalidation, then scoped expiry retains INCOMPLETE/U history. |
| SC-008 | Confirmed failed notice permits a new registered attempt; delivery alone still precedes current-condition revalidation and exact authorization. |
| SC-009 | Beijing midnight changes all natural-day cutoffs, clips remaining capacity and expires the today lock; date-only due remains 23:59. |
| SC-010 | The 40-minute SAFE threshold uses the whole-day remainder after one reserve; short fragments do not independently erase it. |
| SC-011 | An unchanged batch containing a worked Task is invalid as a whole, produces no verification and is not silently narrowed or committed. |

SC-003 independently enumerates every possible contiguous placement for one synthetic task on a finite integer grid, then feeds the resulting evidence into the forecast contract. The fixture has 16 daily slots, requires two consecutive slots and permits the Task in only one slot. It proves that finite case exactly; it is not the production solver or a certificate for arbitrary hard constraints. The checker caps grid enumeration at 96 slots. Forecast tests separately cover missing/stale/contradictory proof and horizon binding.

Batch/expiry scenarios seed their exact TransactionPermits in trusted test setup after domain decisions. They demonstrate the composition and fake atomic audit behavior, not an implemented command-to-permit service, production Task pipeline or PostgreSQL transaction. No complete real review, provider delivery or actual Task outcome is inferred.

## Evidence Levels and Unfinished Scope

All rows declare `OFFLINE_DEVELOPMENT` and carry explicit remaining limitations. A missing/stale reference fails checks. When a decision or scenario is added, the complete inventory/unmapped set must be refreshed explicitly; silently dropping an uncovered requirement fails checks. Refinements such as D-072/D-074/D-078 must be read with their older decision IDs; the map does not reinstate superseded wording.

The 22 unmapped decisions are outside this catalog's currently exercised scope. Even the 58 mapped decisions have remaining release obligations. A successful catalog command means the declared references and scoped synthetic outcomes passed; it does not prove full A0/M2/runtime acceptance. The complete task catalogs and future release audits remain authoritative for missing application behavior.

Pending evidence includes profile/preset/reference activation, ordinary morning/evening interaction, Planner selection and complete solver, real rendering/publication, learned policy adoption, source accounts/freshness, runtime/toolchain finalization, PostgreSQL crash durability, migrations, idempotent outbox, actual backup/restore and operational deployment. No personal course/progress data, credentials or real accounts are used by these scenarios.
