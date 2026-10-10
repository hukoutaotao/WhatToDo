"""Run scoped synthetic cross-contract workflows, never a live release check."""
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path: sys.path.insert(0, str(ROOT))
from tests.contract_scenarios import RUNNERS, run_scenario
from tools.check_contract_registry import REGISTRY, validate_registry
from tools.validate_task_core import load_json

FIXTURE = ROOT / "tests/fixtures/contracts/cross_scenarios.json"


def check_cases(bundle):
    if not isinstance(bundle, dict) or bundle.get("synthetic") is not True or bundle.get("evidence_level") != "OFFLINE_FIXTURE_SEEDS_NOT_LIVE_AUTHORITY":
        raise ValueError("Explicit synthetic evidence scope required")
    cases = bundle.get("cases")
    if not isinstance(cases, list) or len(cases) != len(RUNNERS): raise ValueError("Five workflow expectations required")
    if not all(isinstance(c, dict) and isinstance(c.get("id"), str) and c["id"] and isinstance(c.get("kind"), str) and isinstance(c.get("inputs"), dict) and isinstance(c.get("expected"), dict) for c in cases):
        raise ValueError("Malformed scenario fixture")
    if len({c["id"] for c in cases}) != len(cases) or {c["kind"] for c in cases} != set(RUNNERS):
        raise ValueError("Unique scenario identities/complete workflow coverage required")
    results = []
    for case in cases:
        actual = run_scenario(case)
        results.append({"id": case["id"], "matched": actual == case["expected"], "actual": actual})
    return results


def main():
    try:
        errors = validate_registry(load_json(REGISTRY))
        if errors: raise ValueError("Contract registry drift: " + ",".join(errors))
        results = check_cases(load_json(FIXTURE))
    except (ValueError, TypeError, KeyError, OSError, AssertionError) as exc:
        print("FAIL: " + str(exc), file=sys.stderr); return 1
    for row in results: print(("PASS " if row["matched"] else "FAIL ") + row["id"])
    print("Five composed offline workflows; 31 wire records; independently seeded authority/permits; live release remains open")
    return 0 if all(row["matched"] for row in results) else 1


if __name__ == "__main__": raise SystemExit(main())
