"""A development gate cannot silently drift or become real activation."""
from copy import deepcopy
import unittest
from tools.check_generic_baseline import BASELINE,validate_baseline
from tools.validate_task_core import load_json


class GenericBaselineTests(unittest.TestCase):
    def test_current_pins_and_actual_native_scope_resolve(self):
        self.assertEqual(validate_baseline(load_json(BASELINE)),[])

    def test_drift_missing_owner_or_wider_activation_requires_review(self):
        original=load_json(BASELINE)
        changed=deepcopy(original);changed["artifacts"][0]["sha256"]="0"*64
        self.assertIn("BASELINE_ARTIFACT_DRIFT",validate_baseline(changed))
        changed=deepcopy(original);changed["artifacts"]=[p for p in changed["artifacts"] if p["path"]!="src/application/ports.py"]
        self.assertIn("BASELINE_OWNERSHIP_GAP",validate_baseline(changed))
        changed=deepcopy(original);changed["real_activation"]="ENABLED"
        self.assertIn("BASELINE_ACTIVATION_SCOPE",validate_baseline(changed))

    def test_outside_paths_are_rejected_before_read(self):
        changed=load_json(BASELINE);changed["artifacts"].append(dict(path="../outside-owned-workspace",sha256="0"*64))
        self.assertIn("BASELINE_PATH_SCOPE",validate_baseline(changed))


if __name__=="__main__":unittest.main()
