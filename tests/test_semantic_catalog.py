from copy import deepcopy
import unittest

from tests.semantic_scenarios import run_scenario
from tools.check_semantic_catalog import CATALOG, SCENARIOS, validate_catalog, validate_scenarios
from tools.validate_task_core import load_json


class SemanticCatalogTests(unittest.TestCase):
    def test_every_composed_scenario_matches_independently_authored_expectation(self):
        bundle = load_json(SCENARIOS)
        self.assertFalse(validate_scenarios(bundle))
        for case in bundle["scenarios"]:
            with self.subTest(scenario=case["id"]):
                self.assertEqual(run_scenario(case), case["expected"])

    def test_catalog_resolves_decisions_cases_methods_and_all_scenarios(self):
        self.assertFalse(validate_catalog(load_json(CATALOG)))

    def test_broken_references_duplicate_ids_and_missing_limitations_are_rejected(self):
        mutations = [lambda data: data["boundaries"][0]["decision_ids"].append("D-999"), lambda data: data["boundaries"][0]["tests"].append("tests.test_missing.NoTest.test_missing"), lambda data: data["boundaries"][0]["schema_cases"][0].update(case_id="missing-case"), lambda data: data["boundaries"][0]["scenarios"].append("SC-999"), lambda data: data["boundaries"].append(deepcopy(data["boundaries"][0])), lambda data: data["boundaries"][0].update(remaining=[]), lambda data: data.update(unmapped_decisions=[]), lambda data: data.update(scope="LIVE_RELEASE_ACCEPTANCE")]
        original = load_json(CATALOG)
        for index, mutate in enumerate(mutations):
            data = deepcopy(original)
            mutate(data)
            with self.subTest(index=index):
                self.assertTrue(validate_catalog(data))

    def test_scenario_unknown_fields_duplicate_identity_and_unbounded_oracle_rejected(self):
        original = load_json(SCENARIOS)
        for mutate in (lambda data: data["scenarios"][0]["inputs"].update(ignored_secret="synthetic"), lambda data: data["scenarios"].append(deepcopy(data["scenarios"][0])), lambda data: data["scenarios"][2]["inputs"].update(day_slots=10000000)):
            data = deepcopy(original)
            mutate(data)
            self.assertTrue(validate_scenarios(data))

    def test_runner_does_not_derive_observed_results_from_expectations(self):
        case = load_json(SCENARIOS)["scenarios"][0]
        changed = deepcopy(case)
        changed["expected"]["budget_seconds"] = 99999
        self.assertEqual(run_scenario(changed), run_scenario(case))
        self.assertNotEqual(run_scenario(changed), changed["expected"])


if __name__ == "__main__":
    unittest.main()
