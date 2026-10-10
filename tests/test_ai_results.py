"""Synthetic AI handoff checks; no provider, personal data or canonical writes."""

from dataclasses import FrozenInstanceError, asdict, replace
from datetime import datetime, timedelta, timezone
from decimal import Decimal
import json
from pathlib import Path
import unittest

from src.domain.ai_results import AIJob, AIResult, BehaviorCandidate, ImportRecord, NumericEligibility, TargetBinding, Usage, export_job, validate_import
from src.domain.authorization import TaskState
from src.domain.effort import UserEstimate, select_budget
from tools.check_contracts import validate_contract
from tools.validate_task_core import load_json


class AIResultTests(unittest.TestCase):
    def setUp(self):
        self.start = datetime(2026, 1, 1, tzinfo=timezone.utc)
        self.now = self.start + timedelta(minutes=4)
        self.target = TargetBinding("TASK", "synthetic-task", 2)
        self.job = AIJob("synthetic-job", 1, "synthetic-calibration", "MANUAL_PREMIUM", 3, "Synthetic job", "synthetic-minimal-context", "a" * 64, "synthetic-snapshot", (self.target,), "ai-result:0.1.0-draft", "NUMERIC_REMAINING", self.start)
        self.job, self.artifact = export_job(self.job, exported_at=self.start + timedelta(minutes=1))
        self.payload = {"quantity_kind": "REMAINING", "task_id": self.target.id, "task_revision": 2, "prediction_id": "synthetic-external-prediction", "model_id": "synthetic-model", "model_version": "v1", "remaining_seconds": 600, "computed_at": (self.start + timedelta(minutes=2)).isoformat(), "valid_until": (self.start + timedelta(hours=1)).isoformat(), "uncertainty_ref": None}
        self.result = AIResult("synthetic-result", self.job.job_id, 1, self.job.context_hash, self.job.snapshot_ref, self.job.output_contract_ref, "NUMERIC_REMAINING", "synthetic-executor", self.start + timedelta(minutes=3), json.dumps(self.payload), Usage())
        self.eligibility = NumericEligibility("synthetic-eligibility", self.target.id, 2, "synthetic-model", "v1", self.job.context_hash, self.job.snapshot_ref, self.start, self.start + timedelta(hours=2))
        self.task = TaskState(self.target.id, 2)

    def run_import(self, job=None, result=None, **changes):
        options = dict(current_snapshot_ref=self.job.snapshot_ref, current_context_hash=self.job.context_hash, target_revisions={(self.target.kind, self.target.id): 2}, tasks={self.task.task_id: self.task}, eligibility=self.eligibility, now=self.now)
        options.update(changes)
        return validate_import(job or self.job, result or self.result, **options)

    def changed_payload(self, **changes):
        return replace(self.result, payload_json=json.dumps({**self.payload, **changes}))

    def behavior_import(self, policy="PREFERENCE", target_kind="PREFERENCE"):
        target = TargetBinding(target_kind, "synthetic-policy-target", 2)
        job = replace(self.job, expected_kind="BEHAVIOR_PROPOSAL", targets=(target,))
        payload = dict(proposal_id="synthetic-proposal", target=asdict(target), policy_kind=policy, description="Synthetic proposed change", proposed_value={"synthetic_setting": 1200}, confidence="1.0")
        result = replace(self.result, kind="BEHAVIOR_PROPOSAL", payload_json=json.dumps(payload))
        options = dict(target_revisions={(target.kind, target.id): 2}, eligibility=None)
        return job, result, options

    def test_export_is_immutable_reference_only_and_replay_is_stable(self):
        pending = replace(self.job, status="PENDING", exported_at=None)
        exported, artifact = export_job(pending, exported_at=self.job.exported_at)
        self.assertEqual(pending.status, "PENDING")
        self.assertEqual(exported.status, "EXPORTED")
        replay, second = export_job(exported, exported_at=self.now)
        self.assertEqual(replay, exported)
        self.assertEqual(second, artifact)
        self.assertEqual(artifact["external_content_role"], "DATA_NOT_INSTRUCTIONS")
        self.assertNotIn("raw_context", artifact)
        self.assertNotIn("api_key", artifact)
        with self.assertRaises(ValueError):
            export_job(exported, exported_at=self.start)

    def test_cancelled_job_cannot_export_or_activate_result(self):
        job = replace(self.job, status="CANCELLED")
        with self.assertRaises(ValueError):
            export_job(job, exported_at=self.now)
        self.assertEqual(self.run_import(job).state, "REJECTED")
        self.assertEqual(self.run_import(replace(self.job, status="PENDING", exported_at=None)).reason, "JOB_NOT_ELIGIBLE")

    def test_numeric_prediction_drives_budget_below_and_above_u_without_rewrite(self):
        user = UserEstimate(1800, "synthetic-estimate", self.start, self.start)
        for seconds in (0, 600, 3600):
            with self.subTest(seconds=seconds):
                outcome = self.run_import(result=self.changed_payload(remaining_seconds=seconds))
                self.assertEqual(outcome.state, "VALIDATED_NUMERIC")
                budget = select_budget(task_id=self.task.task_id, task_revision=2, snapshot_at=self.now, user_estimate=user, prediction=outcome.prediction.prediction)
                self.assertEqual((budget.seconds, budget.source, budget.user_seconds), (seconds, "MODEL", 1800))
                self.assertEqual(user.seconds, 1800)
                self.assertEqual(self.task.completion, "INCOMPLETE")
        with self.assertRaises(FrozenInstanceError):
            self.task.completion = "COMPLETE"

    def test_missing_u_remains_review_needed_even_with_numeric_result(self):
        outcome = self.run_import()
        budget = select_budget(task_id=self.task.task_id, task_revision=2, snapshot_at=self.now, user_estimate=None, prediction=outcome.prediction.prediction)
        self.assertEqual(budget.seconds, 600)
        self.assertTrue(budget.review_needed)

    def test_independent_current_model_eligibility_is_required(self):
        eligibility_cases = [None, replace(self.eligibility, model_version="v2"), replace(self.eligibility, context_hash="b" * 64), replace(self.eligibility, task_revision=3), replace(self.eligibility, snapshot_ref="synthetic-other-snapshot"), replace(self.eligibility, valid_until=self.now), replace(self.eligibility, evaluated_at=self.now + timedelta(minutes=1))]
        for eligibility in eligibility_cases:
            with self.subTest(eligibility=eligibility):
                self.assertEqual(self.run_import(eligibility=eligibility).reason, "NUMERIC_ELIGIBILITY_UNRESOLVED")

    def test_job_and_result_scope_mismatch_is_rejected(self):
        for changes in ({"job_id": "synthetic-other-job"}, {"job_revision": 2}, {"context_hash": "b" * 64}, {"snapshot_ref": "synthetic-other-snapshot"}, {"output_contract_ref": "synthetic-other-contract"}, {"kind": "BEHAVIOR_PROPOSAL"}):
            with self.subTest(changes=changes):
                self.assertEqual(self.run_import(result=replace(self.result, **changes)).reason, "JOB_SCOPE_MISMATCH")

    def test_current_context_snapshot_and_all_targets_must_resolve(self):
        for changes in ({"current_snapshot_ref": "synthetic-other"}, {"current_context_hash": "b" * 64}, {"target_revisions": {}}, {"target_revisions": {("TASK", self.target.id): 3}}):
            with self.subTest(changes=changes):
                self.assertEqual(self.run_import(**changes).state, "REJECTED")
        added = TargetBinding("TASK", "synthetic-second-task", 1)
        self.assertEqual(self.run_import(replace(self.job, targets=(self.target, added))).reason, "TARGET_REVISION_UNRESOLVED")

    def test_inactive_completed_unknown_and_stale_tasks_cannot_receive_prediction(self):
        for task in (None, replace(self.task, revision=3), replace(self.task, completion="COMPLETE"), replace(self.task, disposition="CANCELLED"), replace(self.task, disposition="EXPIRED")):
            with self.subTest(task=task):
                tasks = {} if task is None else {task.task_id: task}
                self.assertEqual(self.run_import(tasks=tasks).reason, "NUMERIC_TARGET_NOT_ACTIVE")
        self.assertEqual(self.run_import(result=self.changed_payload(task_id="synthetic-unknown-task")).state, "REJECTED")

    def test_total_effort_and_canonical_control_fields_are_rejected(self):
        for changes in ({"quantity_kind": "TOTAL"}, {"user_remaining_seconds": 0}, {"completion": "COMPLETE"}, {"applicable": True}, {"principal": "USER"}, {"remaining_seconds": True}, {"remaining_seconds": -1}, {"remaining_seconds": 1.5}):
            with self.subTest(changes=changes):
                self.assertEqual(self.run_import(result=self.changed_payload(**changes)).state, "REJECTED")

    def test_result_and_prediction_chronology_are_bounded(self):
        for finished_at in (self.start, self.now + timedelta(seconds=1)):
            self.assertEqual(self.run_import(result=replace(self.result, finished_at=finished_at)).state, "REJECTED")
        for changes in ({"computed_at": self.start.isoformat()}, {"computed_at": self.now.isoformat()}, {"valid_until": self.now.isoformat()}, {"valid_until": (self.start + timedelta(hours=3)).isoformat()}, {"computed_at": "2026-01-01T00:02:00"}):
            with self.subTest(changes=changes):
                self.assertEqual(self.run_import(result=self.changed_payload(**changes)).state, "REJECTED")

    def test_accepted_replay_is_no_effect_even_after_cancellation_or_stale_context(self):
        original = self.run_import()
        replay = self.run_import(replace(self.job, status="CANCELLED"), history=original.history, current_snapshot_ref="synthetic-new-snapshot", now=self.now + timedelta(days=1))
        self.assertEqual(replay.state, "REPLAY")
        self.assertIsNone(replay.prediction)
        self.assertIsNone(replay.behavior)
        self.assertEqual(replay.history, original.history)
        self.assertEqual(replay.record.validated_at, self.now)

    def test_same_identity_conflicting_content_does_not_replace_history(self):
        original = self.run_import()
        conflict = self.run_import(result=self.changed_payload(remaining_seconds=1200), history=original.history)
        self.assertEqual(conflict.state, "CONFLICT")
        self.assertEqual(conflict.history, original.history)
        self.assertIsNone(conflict.prediction)

    def test_rejected_wrong_job_result_retains_its_source_identity_on_replay(self):
        wrong = replace(self.result, job_id="synthetic-wrong-job", job_revision=5)
        rejected = self.run_import(result=wrong)
        self.assertEqual((rejected.record.job_id, rejected.record.job_revision), (wrong.job_id, 5))
        replay = self.run_import(result=wrong, history=rejected.history)
        self.assertEqual(replay.state, "REPLAY")
        self.assertEqual(replay.record.validation_state, "REJECTED")
        with self.assertRaises(ValueError):
            self.run_import(history=rejected.history + rejected.history)

    def test_all_behavior_policies_remain_pending_at_full_confidence(self):
        for policy, target_kind in (("PREFERENCE", "PREFERENCE"), ("TASKTYPE_DEFAULT", "TASKTYPE"), ("RELATIONSHIP_RULE", "RELATIONSHIP_RULE"), ("DECOMPOSITION", "TASK")):
            job, result, options = self.behavior_import(policy, target_kind)
            outcome = self.run_import(job, result, **options)
            self.assertEqual(outcome.state, "PENDING_REVIEW")
            self.assertEqual(outcome.behavior.review_state, "PENDING")
            self.assertEqual(outcome.behavior.confidence, Decimal(1))
            self.assertIsNone(outcome.prediction)
            self.assertFalse(hasattr(outcome, "grant"))

    def test_behavior_cannot_accept_itself_or_escape_target_scope(self):
        job, result, options = self.behavior_import()
        for changes in ({"review_state": "ACCEPTED"}, {"confidence": "NaN"}, {"confidence": "1.1"}, {"confidence": 1}, {"target": {"kind": "PREFERENCE", "id": "synthetic-other", "revision": 2}}, {"policy_kind": "TASK_COMPLETION"}):
            changed = replace(result, payload_json=json.dumps({**result.payload, **changes}))
            self.assertEqual(self.run_import(job, changed, **options).state, "REJECTED")
        candidate = self.run_import(job, result, **options).behavior
        with self.assertRaises(ValueError):
            replace(candidate, review_state="ACCEPTED")

    def test_payloads_are_copied_and_nested_duplicate_or_nonfinite_json_rejected(self):
        payload = self.result.payload
        payload["remaining_seconds"] = 9999
        self.assertEqual(self.result.payload["remaining_seconds"], 600)
        for raw in ('{"x":{"a":1,"a":2}}', '{"x":NaN}', '{"x":Infinity}', '[]'):
            with self.subTest(raw=raw), self.assertRaises(ValueError):
                replace(self.result, payload_json=raw)
        job, result, options = self.behavior_import()
        candidate = self.run_import(job, result, **options).behavior
        copy = candidate.proposed_value
        copy["synthetic_setting"] = 0
        self.assertEqual(candidate.proposed_value["synthetic_setting"], 1200)

    def test_usage_unknown_is_distinct_from_zero_and_cost_is_exact(self):
        self.assertIsNone(Usage().as_record()["cost_amount"])
        self.assertEqual(Usage(0, 0, Decimal(0), "SYNTHETIC").as_record()["cost_amount"], "0")
        self.assertEqual(Usage(10, 2, Decimal("0.0125"), "SYNTHETIC").as_record()["cost_amount"], "0.0125")
        for changes in ({"input_tokens": True}, {"output_tokens": -1}, {"cost_amount": Decimal("NaN"), "currency": "SYNTHETIC"}, {"cost_amount": Decimal("0.1")}):
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                Usage(**changes)

    def test_typed_serialization_satisfies_closed_contracts(self):
        outcome = self.run_import()
        job, result, options = self.behavior_import()
        behavior = self.run_import(job, result, **options)
        records = [("ai-job", self.job.as_record()), ("ai-export", self.artifact), ("ai-result", self.result.as_record()), ("ai-result", result.as_record()), ("remaining-prediction", outcome.prediction.as_record()), ("behavior-candidate", behavior.behavior.as_record()), ("ai-import-record", outcome.record.as_record())]
        for contract, record in records:
            with self.subTest(contract=contract):
                self.assertFalse(validate_contract(contract, record))

    def test_synthetic_schema_expectations(self):
        fixture = load_json(Path(__file__).parent / "fixtures/ai_results/cases.json")
        self.assertTrue(fixture["synthetic"])
        for case in fixture["cases"]:
            with self.subTest(case=case["id"]):
                self.assertEqual(not validate_contract(case["contract"], case["payload"]), case["valid"])


if __name__ == "__main__":
    unittest.main()
