from copy import deepcopy
from dataclasses import FrozenInstanceError, replace
from datetime import datetime, timedelta, timezone
from fractions import Fraction
import unittest

from src.domain.effort import (
    RemainingPrediction, Stage, UserEstimate, WorkObservation,
    actual_seconds, append_observation, partition_stages, select_budget, sum_obligations,
)
from tools.check_contracts import validate_contract
from tools.validate_task_core import ROOT, load_json


NOW = datetime(2026, 1, 1, 12, tzinfo=timezone.utc)


class EffortTests(unittest.TestCase):
    def estimate(self, seconds=14400):
        return UserEstimate(seconds, "synthetic-estimate", NOW - timedelta(hours=2), NOW - timedelta(hours=1))

    def prediction(self, seconds=21600, **changes):
        value = RemainingPrediction(seconds, "synthetic-prediction", "synthetic-model", "1", 3, NOW - timedelta(minutes=10), NOW + timedelta(hours=1), True, True)
        return replace(value, **changes)

    def choose(self, **changes):
        args = dict(task_id="synthetic-task", task_revision=3, snapshot_at=NOW, user_estimate=self.estimate(), prediction=self.prediction())
        args.update(changes)
        return select_budget(**args)

    def observation(self, identity="synthetic-work", **changes):
        value = WorkObservation(identity, "synthetic-task", "ACTUAL_WORK", 1200, NOW - timedelta(minutes=30), NOW, "synthetic-source", "synthetic-user-command")
        return replace(value, **changes)

    def test_model_above_and_below_user(self):
        for prediction_seconds in (21600, 7200, 0):
            with self.subTest(prediction=prediction_seconds):
                estimate = self.estimate()
                selection = self.choose(user_estimate=estimate, prediction=self.prediction(prediction_seconds))
                self.assertEqual(selection.seconds, prediction_seconds)
                self.assertEqual(selection.source, "MODEL")
                self.assertEqual(estimate.seconds, 14400)
                self.assertEqual(selection.user_seconds, 14400)

    def test_model_fallbacks(self):
        variants = (
            (None, "MODEL_MISSING"),
            (self.prediction(valid=False), "MODEL_INVALID"),
            (self.prediction(applicable=False), "MODEL_INAPPLICABLE"),
            (self.prediction(task_revision=2), "MODEL_REVISION_MISMATCH"),
            (self.prediction(computed_at=NOW + timedelta(seconds=1)), "MODEL_FROM_FUTURE"),
            (self.prediction(valid_until=NOW), "MODEL_STALE"),
        )
        for prediction, reason in variants:
            with self.subTest(reason=reason):
                selection = self.choose(prediction=prediction)
                self.assertEqual((selection.source, selection.seconds, selection.reason), ("USER_FALLBACK", 14400, reason))

    def test_missing_user_is_still_review_pending_with_model(self):
        selection = self.choose(user_estimate=None)
        self.assertEqual(selection.seconds, 21600)
        self.assertTrue(selection.review_needed)
        selection = self.choose(user_estimate=None, prediction=None)
        self.assertIsNone(selection.seconds)
        self.assertEqual(selection.source, "UNKNOWN")

    def test_future_user_estimate_is_not_current_fallback(self):
        future = UserEstimate(3600, "synthetic-future", NOW + timedelta(seconds=1), NOW + timedelta(seconds=1))
        selection = self.choose(user_estimate=future, prediction=None)
        self.assertIsNone(selection.seconds)
        self.assertIn("USER_FROM_FUTURE", selection.reason)
        self.assertEqual(future.seconds, 3600)

    def test_expired_and_cancelled_keep_user_estimate(self):
        for disposition in ("EXPIRED", "CANCELLED"):
            with self.subTest(disposition=disposition):
                estimate = self.estimate()
                selection = self.choose(disposition=disposition, user_estimate=estimate)
                self.assertIsNone(selection.seconds)
                self.assertEqual(selection.source, "NOT_ACTIVE")
                self.assertEqual(estimate.seconds, 14400)
                self.assertEqual(sum_obligations([selection]).seconds, 0)

    def test_complete_needs_explicit_zero_and_zero_does_not_complete(self):
        with self.assertRaises(ValueError):
            self.choose(completion="COMPLETE")
        selection = self.choose(completion="COMPLETE", user_estimate=self.estimate(0))
        self.assertEqual((selection.source, selection.seconds), ("COMPLETED", 0))
        selection = self.choose(user_estimate=self.estimate(0), prediction=None)
        self.assertEqual(selection.source, "USER_FALLBACK")
        self.assertNotEqual(selection.source, "COMPLETED")

    def test_exact_stage_partition_no_double_count(self):
        selection = self.choose(prediction=self.prediction(7))
        stages = [Stage("stage-1", "INCOMPLETE", Fraction(1)), Stage("stage-2", "INCOMPLETE", Fraction(2)), Stage("finished-stage", "COMPLETE", Fraction(100))]
        result = partition_stages(selection, stages)
        self.assertEqual([allocation.seconds for allocation in result.allocations], [Fraction(7, 3), Fraction(14, 3)])
        self.assertEqual(sum(allocation.seconds for allocation in result.allocations), selection.seconds)
        self.assertEqual(sum_obligations([selection, selection]).seconds, 7)
        with self.assertRaises(ValueError):
            sum_obligations([selection, result.allocations[0]])

    def test_weights_unknown_use_parent_without_fabrication(self):
        selection = self.choose()
        result = partition_stages(selection, [Stage("stage-1", "INCOMPLETE", None)])
        self.assertIsNone(result.allocations)
        self.assertEqual(result.parent_seconds, 21600)
        self.assertEqual(result.reason, "WEIGHTS_UNKNOWN")

    def test_all_stages_complete_does_not_complete_parent(self):
        selection = self.choose()
        result = partition_stages(selection, [Stage("stage-1", "COMPLETE", Fraction(1))])
        self.assertEqual(result.reason, "NO_UNFINISHED_STAGES")
        self.assertEqual(result.parent_seconds, 21600)
        self.assertEqual(selection.source, "MODEL")

    def test_rework_restores_stage_accounting_without_losing_snapshot(self):
        stage = Stage("stage-1", "COMPLETE", Fraction(1))
        reopened = replace(stage, completion="INCOMPLETE")
        self.assertEqual(stage.completion, "COMPLETE")
        result = partition_stages(self.choose(), [reopened])
        self.assertEqual(result.allocations[0].seconds, 21600)

    def test_stage_canonical_estimates_are_not_scaled(self):
        stage = Stage("stage-1", "INCOMPLETE", Fraction(1), self.estimate(7200))
        result = partition_stages(self.choose(), [stage])
        self.assertTrue(result.canonical_disagreement)
        self.assertEqual(stage.user_estimate.seconds, 7200)
        self.assertEqual(result.allocations[0].seconds, 21600)

    def test_separate_obligations_add_repeated_references_do_not(self):
        first = self.choose()
        second = replace(first, task_id="synthetic-counterpart")
        self.assertEqual(sum_obligations([first, first, second]).seconds, 43200)
        with self.assertRaises(ValueError):
            sum_obligations([first, replace(first, task_revision=4)])

    def test_unknown_obligation_total_is_not_zero(self):
        unresolved = self.choose(user_estimate=None, prediction=None)
        result = sum_obligations([unresolved])
        self.assertIsNone(result.seconds)
        self.assertEqual(result.unresolved_task_ids, ("synthetic-task",))

    def test_observations_are_immutable_idempotent_and_not_estimate_decrements(self):
        estimate = self.estimate()
        observation = self.observation()
        before = ()
        after = append_observation(before, observation)
        self.assertEqual(before, ())
        self.assertEqual(append_observation(after, observation), after)
        self.assertEqual(actual_seconds(after + after, "synthetic-task"), 1200)
        self.assertEqual(estimate.seconds, 14400)
        with self.assertRaises(FrozenInstanceError):
            observation.seconds = 0
        with self.assertRaises(ValueError):
            append_observation(after, replace(observation, seconds=2000))

    def test_verification_and_remaining_estimate_are_not_actual_work(self):
        verification = self.observation("synthetic-verify", kind="UNCHANGED_VERIFICATION", seconds=None, batch_ref="synthetic-batch")
        remaining = self.observation("synthetic-remaining", kind="USER_REMAINING")
        self.assertEqual(actual_seconds([verification, remaining], "synthetic-task"), 0)
        with self.assertRaises(ValueError):
            self.observation(kind="PLANNED_SESSION")
        with self.assertRaises(ValueError):
            self.observation(kind="UNCHANGED_VERIFICATION", batch_ref="synthetic-batch")

    def test_invalid_values_and_times_fail_explicitly(self):
        for value in (True, -1, 2.5):
            with self.subTest(value=value), self.assertRaises(ValueError):
                self.estimate(value)
        with self.assertRaises(ValueError):
            self.choose(snapshot_at=datetime(2026, 1, 1))
        with self.assertRaises(ValueError):
            self.observation(recorded_at=NOW - timedelta(days=1))
        with self.assertRaises(ValueError):
            self.prediction(valid_until=NOW - timedelta(days=1))
        with self.assertRaises(ValueError):
            partition_stages(self.choose(), [Stage("duplicate", "INCOMPLETE", Fraction(1)), Stage("duplicate", "INCOMPLETE", Fraction(1))])

    def test_schema_regression_bundle(self):
        fixture = load_json(ROOT / "tests/fixtures/effort/cases.json")
        self.assertIs(fixture["synthetic"], True)
        for case in fixture["cases"]:
            with self.subTest(case=case["id"]):
                original = deepcopy(case["payload"])
                self.assertEqual(not validate_contract(case["contract"], case["payload"]), case["valid"])
                self.assertEqual(case["payload"], original)


if __name__ == "__main__":
    unittest.main()
