"""Verify offline decision/fixture/test traceability and composed scenarios.

Successful checks certify this development catalog, never release/live gates.
"""

import ast
import json
from pathlib import Path
import re
import unittest

from tools.check_contracts import validate_contract
from tools.validate_task_core import ROOT, load_json


CATALOG = ROOT / "tests/fixtures/semantic/catalog.json"
SCENARIOS = ROOT / "tests/fixtures/semantic/scenarios.json"
INPUTS = {
    "MODEL_FORECAST": {"user_seconds", "model_seconds", "capacity_seconds"},
    "HARD_WINDOW": {"slot_seconds", "day_slots", "required_slots", "eligible_slots"},
    "EXTERNAL_AUTHORITY": {"confidence", "proposed_completion"},
    "BATCH_COMMIT": {"untouched_id", "worked_id", "user_seconds", "include_worked_in_batch"},
    "GENERATION_ORDER": {"source_type", "target_type", "preparation_seconds", "source_seconds"},
    "NOTICE_EXPIRY": {"initial_dispatch", "user_seconds"},
    "ROLLOVER": {"before", "after", "date_only"},
    "SAFE_GAP": {"required_seconds", "reserve_seconds", "gap_seconds", "fragment_seconds"},
}


def validate_scenarios(bundle):
    errors = []
    if set(bundle) != {"synthetic", "scenario_version", "scenarios"} or bundle.get("synthetic") is not True or bundle.get("scenario_version") != "0.1.0-draft" or not isinstance(bundle.get("scenarios"), list) or not bundle["scenarios"]:
        return ("SCENARIO_BUNDLE",)
    ids = set()
    decisions = set(re.findall(r"^## (D-\d{3})\b", (ROOT / "plan/DECISIONS.md").read_text(encoding="utf-8"), re.M))
    for case in bundle["scenarios"]:
        if not isinstance(case, dict) or set(case) != {"id", "kind", "decisions", "inputs", "expected"}:
            errors.append("SCENARIO_FIELDS")
            continue
        name = case["id"]
        if not isinstance(name, str) or not re.fullmatch(r"SC-\d{3}", name) or name in ids:
            errors.append("SCENARIO_ID")
        ids.add(name)
        kind = case["kind"]
        if kind not in INPUTS or not isinstance(case["inputs"], dict) or set(case["inputs"]) != INPUTS.get(kind):
            errors.append("SCENARIO_INPUTS:" + str(name))
        if not isinstance(case["expected"], dict) or not case["expected"]:
            errors.append("SCENARIO_EXPECTATIONS:" + str(name))
        if not isinstance(case["decisions"], list) or not case["decisions"] or len(set(case["decisions"])) != len(case["decisions"]) or set(case["decisions"]) - decisions:
            errors.append("SCENARIO_DECISIONS:" + str(name))
        if kind == "HARD_WINDOW":
            values = case["inputs"]
            if not all(type(values.get(key)) is int and values[key] > 0 for key in ("slot_seconds", "day_slots", "required_slots")) or values.get("day_slots", 97) > 96 or not isinstance(values.get("eligible_slots"), list) or any(type(slot) is not int or not 0 <= slot < values["day_slots"] for slot in values.get("eligible_slots", [])):
                errors.append("BOUNDED_GRID_REQUIRED:" + str(name))
    return tuple(errors)


def test_ids():
    result = set()
    for path in (ROOT / "tests").glob("test_*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in tree.body:
            if isinstance(node, ast.ClassDef):
                for method in node.body:
                    if isinstance(method, ast.FunctionDef) and method.name.startswith("test_"):
                        result.add(f"tests.{path.stem}.{node.name}.{method.name}")
    return result


def validate_catalog(catalog, scenarios=None):
    errors = []
    keys = {"synthetic", "catalog_version", "scope", "decision_source", "decision_ids", "boundaries", "unmapped_decisions", "scenario_file"}
    if not isinstance(catalog, dict) or set(catalog) != keys or catalog.get("synthetic") is not True or catalog.get("catalog_version") != "0.1.0-draft" or catalog.get("scope") != "OFFLINE_DEVELOPMENT_NOT_RELEASE_ACCEPTANCE" or catalog.get("decision_source") != "plan/DECISIONS.md" or catalog.get("scenario_file") != "tests/fixtures/semantic/scenarios.json":
        return ("CATALOG_SCOPE_OR_FIELDS",)
    known = set(re.findall(r"^## (D-\d{3})\b", (ROOT / catalog["decision_source"]).read_text(encoding="utf-8"), re.M))
    if not isinstance(catalog["decision_ids"], list) or len(set(catalog["decision_ids"])) != len(catalog["decision_ids"]) or set(catalog["decision_ids"]) != known:
        errors.append("DECISION_INVENTORY")
    scenarios = scenarios if scenarios is not None else load_json(SCENARIOS)
    errors.extend(validate_scenarios(scenarios))
    scenario_ids = {case["id"] for case in scenarios.get("scenarios", []) if isinstance(case, dict) and isinstance(case.get("id"), str)}
    methods = test_ids()
    bundles = {}
    for path in (ROOT / "tests/fixtures").glob("*/cases.json"):
        body = load_json(path)
        if body.get("synthetic") is not True or len({case["id"] for case in body["cases"]}) != len(body["cases"]):
            errors.append("FIXTURE_IDENTITY:" + path.parent.name)
        bundles[path.parent.name] = {case["id"]: case for case in body["cases"]}
    if not isinstance(catalog["boundaries"], list) or not catalog["boundaries"]:
        return tuple(errors + ["BOUNDARIES_REQUIRED"])
    mapped, covered_scenarios, identities = set(), set(), set()
    for row in catalog["boundaries"]:
        if not isinstance(row, dict) or set(row) != {"id", "decision_ids", "requirement", "scope", "schema_cases", "tests", "scenarios", "remaining"}:
            errors.append("BOUNDARY_FIELDS")
            continue
        name = row["id"]
        if not isinstance(name, str) or not re.fullmatch(r"SB-\d{3}", name) or name in identities:
            errors.append("BOUNDARY_ID")
        identities.add(name)
        if row["scope"] != "OFFLINE_DEVELOPMENT" or not isinstance(row["requirement"], str) or not row["requirement"].strip() or not isinstance(row["remaining"], list) or not row["remaining"] or not all(isinstance(item, str) and item.strip() for item in row["remaining"]):
            errors.append("BOUNDARY_SCOPE_OR_LIMITATIONS:" + str(name))
        if not isinstance(row["decision_ids"], list) or not row["decision_ids"] or len(set(row["decision_ids"])) != len(row["decision_ids"]) or set(row["decision_ids"]) - known:
            errors.append("BOUNDARY_DECISION:" + str(name))
        mapped.update(row["decision_ids"])
        if not isinstance(row["tests"], list) or not row["tests"] or len(set(row["tests"])) != len(row["tests"]) or set(row["tests"]) - methods:
            errors.append("BOUNDARY_TEST:" + str(name))
        if not isinstance(row["scenarios"], list) or len(set(row["scenarios"])) != len(row["scenarios"]) or set(row["scenarios"]) - scenario_ids:
            errors.append("BOUNDARY_SCENARIO:" + str(name))
        covered_scenarios.update(row["scenarios"])
        if not isinstance(row["schema_cases"], list):
            errors.append("BOUNDARY_CASES:" + str(name))
            continue
        references = set()
        for reference in row["schema_cases"]:
            if not isinstance(reference, dict) or set(reference) != {"bundle", "case_id"}:
                errors.append("FIXTURE_REFERENCE_FIELDS:" + str(name))
                continue
            identity = (reference["bundle"], reference["case_id"])
            case = bundles.get(identity[0], {}).get(identity[1])
            if identity in references or case is None:
                errors.append("FIXTURE_REFERENCE:" + str(name))
            elif (not validate_contract(case.get("contract", "task-core" if identity[0] == "task_core" else ""), case["payload"])) is not case["valid"]:
                errors.append("FIXTURE_EXPECTATION:" + str(name))
            references.add(identity)
    if not isinstance(catalog["unmapped_decisions"], list) or len(set(catalog["unmapped_decisions"])) != len(catalog["unmapped_decisions"]) or set(catalog["unmapped_decisions"]) != known - mapped:
        errors.append("UNMAPPED_DECISIONS")
    if covered_scenarios != scenario_ids:
        errors.append("UNMAPPED_SCENARIOS")
    return tuple(errors)


def main():
    try:
        catalog, scenarios = load_json(CATALOG), load_json(SCENARIOS)
        errors = validate_catalog(catalog, scenarios)
        if errors:
            print("INVALID " + ",".join(errors))
            return 1
        from tests.semantic_scenarios import run_scenario
        for case in scenarios["scenarios"]:
            if run_scenario(case) != case["expected"]:
                print("FAIL " + case["id"])
                return 1
        names = sorted({name for row in catalog["boundaries"] for name in row["tests"]})
        suite = unittest.TestSuite(unittest.defaultTestLoader.loadTestsFromName(name) for name in names)
        result = unittest.TextTestRunner(verbosity=0).run(suite)
        if not result.wasSuccessful():
            return 1
        print(f"PASS {len(catalog['decision_ids'])} decision IDs inventoried; {len(catalog['boundaries'])} bounded maps; {len(scenarios['scenarios'])} composed scenarios; {len(names)} referenced tests executed; {len(catalog['unmapped_decisions'])} decisions remain unmapped.")
        print("OFFLINE DEVELOPMENT evidence only; runtime/persistence/live gates remain pending.")
        return 0
    except (ValueError, TypeError, KeyError, OSError):
        print("INVALID malformed catalog/scenario or unresolved scenario execution")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
