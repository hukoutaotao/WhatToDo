# Time, events and availability — development draft 0.1.0

Scope: [M2-08.a](../../plan/tasks/M2_CONTRACTS.md#m2-08a). Schemas: [normalized due](normalized-due.schema.json), [forecast windows](forecast-window.schema.json), [today locks](today-lock.schema.json), [Calendar events](calendar-event.schema.json) and [availability](availability.schema.json). Implementation: [time/interval helpers](../../src/domain/time_windows.py); evidence: [synthetic cases](../../tests/fixtures/time_windows/cases.json), [tests](../../tests/test_time_windows.py).

## Source time and user days

`normalize_due` preserves explicit timezone-aware instants, original text, offset, precision and source reference. Date-only due dates use Asia/Shanghai 23:59 with D-075 default-policy provenance. Naive timestamps, ambiguous text and invalid dates are rejected rather than guessed. Human natural-language/time-only resolution remains a later application boundary; this API receives resolved dates or explicit RFC3339 values.

`forecast_window` accepts 1/3/7 natural days including the snapshot's Beijing date, with cutoffs at today/today+2/today+6 23:59. Remaining capacity begins at the snapshot; at or after the one-day cutoff its remaining interval is empty without changing covered-date metadata. Horizon snapshots overlap and must be evaluated separately. Date boundaries never reset U or infer completion.

Today locks bind task/revision, accepted-statement reference and COMPLETE versus ADVANCE intent. They are active from creation up to, excluding, the next Beijing midnight. This differs from a forecast/deadline 23:59 cutoff. A lock neither changes requiredness nor authorizes canonical completion, and does not bypass hard relationships. Stable preferences remain separate from these temporary objects.

## Occupancy and usable intervals

Finite intervals use half-open bounds and exact fractional-second durations. Union merges overlap and adjacency, then usable intervals clip availability to snapshot/cutoff and subtract the occupied union. Arithmetic normalizes instants to UTC, including DST folds. Empty verified availability is known zero; missing/stale input is unknown. Capacity excludes occupancy/no-work/buffer intervals supplied by the trusted adapter, without subtracting the reserve a second time.

Calendar events retain provider/account scope/external identity, source-record reference, revision, event meaning, explicit timing and occupancy state. Conflicting revisions or duplicate canonical source occurrences require resolution. CANCELLED events cease occupying time without cancelling linked Tasks. Transparent/reminder occupancy is explicit; event presence does not imply blocking or Task completion. UNKNOWN occupancy or relevant tentative blocking events are returned as unresolved identities, not counted as free time.

`AvailabilityFrame` carries input quality and missing/stale references. Its evaluated seconds are unavailable until READY; known intervals in an unresolved result are provisional context only. A consumer must carry unresolved event/source references into that frame rather than silently ignore them. Source freshness, completeness and scope come from the later trusted adapters, not from a JSON flag.

All-day Calendar date ranges retain source timezone and exclusive next-date midnight, distinct from date-only Task deadlines. DST days can occupy 23 or 25 actual hours. This draft accepts already resolved finite occurrences; recurrence expansion, all-day source mapping and Calendar ownership reconciliation remain adapter work.

## Execution and remaining handoff

```powershell
python -m unittest discover -s tests -p 'test_time_windows.py' -v
python -m tools.check_contracts --examples tests/fixtures/time_windows/cases.json
```

The offline harness uses the observed tzdata 2025.2 package pinned with the contract dependencies; this is not a latest-version claim or final deployment selection. Shape validation cannot verify delivery/authority/provider truth. No personal availability, actual Calendar import, recurrence scheduler, reserve/risk classification or plan execution is enabled. Fixtures are synthetic and include an independent minute-grid occupancy oracle.
