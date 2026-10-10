"""Regression tests of accepted boundaries, not personal intake assertions."""

from copy import deepcopy
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from tools.validate_task_core import CASES_PATH, ROOT, load_json, validate_task_core


class TaskCoreContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.fixture = load_json(CASES_PATH)
        cls.base = cls.fixture["cases"][0]["payload"]

    def test_semantic_regressions(self):
        self.assertIs(self.fixture["synthetic"], True)
        identities = [case["id"] for case in self.fixture["cases"]]
        self.assertEqual(len(identities), len(set(identities)))
        for case in self.fixture["cases"]:
            with self.subTest(case=case["id"], boundary=case["note"]):
                self.assertEqual(not validate_task_core(case["payload"]), case["valid"])

    def test_validation_is_pure_and_repeatable(self):
        payload = deepcopy(self.base)
        before = deepcopy(payload)
        self.assertEqual(validate_task_core(payload), ())
        self.assertEqual(validate_task_core(payload), ())
        self.assertEqual(payload, before)

    def test_issue_path_and_redaction(self):
        payload = deepcopy(self.base)
        payload["importance"] = "PRIVATE-INPUT-VALUE"
        issues = validate_task_core(payload)
        self.assertTrue(any(issue.path == "/importance" and issue.constraint == "type" for issue in issues))
        self.assertNotIn("PRIVATE-INPUT-VALUE", repr(issues))

    def test_rejects_nonobject_input(self):
        for payload in (None, [], "task", 3):
            with self.subTest(payload=payload):
                self.assertTrue(validate_task_core(payload))

    def test_strict_json_preserves_truth(self):
        # Silent duplicate-key overwrites can change a completion statement.
        invalid_inputs = (
            '{"completion":"INCOMPLETE","completion":"COMPLETE"}',
            '{"nested":{"importance":1,"importance":5}}',
            '{"importance":NaN}',
            '{"importance":Infinity}',
            '{"importance":-Infinity}',
        )
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "input.json"
            for content in invalid_inputs:
                with self.subTest(content=content):
                    path.write_text(content, encoding="utf-8")
                    with self.assertRaises(ValueError):
                        load_json(path)

    def test_cli_works_outside_repository(self):
        with tempfile.TemporaryDirectory() as directory:
            result = subprocess.run(
                [sys.executable, str(ROOT / "tools/validate_task_core.py"), "--examples"],
                cwd=directory, capture_output=True, text=True, check=False,
            )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("Checked 29 synthetic cases.", result.stdout)

    def test_cli_exit_codes_and_redaction(self):
        script = str(ROOT / "tools/validate_task_core.py")
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "input.json"
            payload = deepcopy(self.base)
            payload["importance"] = "PRIVATE-INPUT-VALUE"
            path.write_text(json.dumps(payload), encoding="utf-8")
            result = subprocess.run([sys.executable, script, str(path)], capture_output=True, text=True)
            self.assertEqual(result.returncode, 1)
            self.assertIn("/importance: violates type", result.stdout)
            self.assertNotIn("PRIVATE-INPUT-VALUE", result.stdout + result.stderr)
            path.write_text('{"importance":NaN}', encoding="utf-8")
            result = subprocess.run([sys.executable, script, str(path)], capture_output=True, text=True)
            self.assertEqual(result.returncode, 2)
            self.assertNotIn("NaN", result.stdout + result.stderr)
            path.write_text(json.dumps(self.base), encoding="utf-8")
            result = subprocess.run([sys.executable, script, str(path)], capture_output=True, text=True)
            self.assertEqual(result.returncode, 0)


if __name__ == "__main__":
    unittest.main()
