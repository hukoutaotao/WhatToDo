from dataclasses import replace
from datetime import datetime, timedelta, timezone
import unittest

from src.domain.authorization import AuthorityGrant, CallerIdentity, Command, TaskState, authorize, change
from src.domain.expiration import (
    ConditionEvidence, DispatchAttempt, DispatchResult, begin_dispatch,
    detect_expiration, reconcile_dispatch, record_dispatch, revalidate_expiration,
)
from tools.check_contracts import validate_contract
from tools.validate_task_core import ROOT, load_json


NOW = datetime(2026, 1, 1, 12, tzinfo=timezone.utc)
MINUTE = timedelta(minutes=1)
TASK = TaskState("synthetic-task", 2, "EXPIRING", expiration_condition_ref="synthetic-condition")
CONDITION = ConditionEvidence("synthetic-condition-evidence", TASK.expiration_condition_ref, True, NOW)


class ExpirationTests(unittest.TestCase):
    def notice(self):
        return detect_expiration(TASK, CONDITION, now=NOW).notice

    def queued(self):
        return begin_dispatch(self.notice(), attempt_id="synthetic-attempt", started_at=NOW + MINUTE, correlation_ref="synthetic-correlation")

    def result(self, notice, state="DELIVERED", attempt_id="synthetic-attempt", started_at=None, finished_at=None):
        attempt = DispatchAttempt(attempt_id, started_at or NOW + MINUTE, state, finished_at or NOW + 3 * MINUTE, NOW + 2 * MINUTE if state == "DELIVERED" else None, "synthetic-result-evidence", "synthetic-correlation")
        return DispatchResult(notice.notice_id, attempt)

    def delivered(self):
        notice = self.queued()
        return record_dispatch(notice, self.result(notice))

    def current_condition(self, **values):
        return replace(CONDITION, observed_at=NOW + 4 * MINUTE, **values)

    def evaluate(self, notice=None, task=TASK, condition=None, checked_at=None):
        return revalidate_expiration(notice or self.delivered(), task, condition or self.current_condition(), checked_at=checked_at or NOW + 5 * MINUTE)

    def test_detection_is_stable_but_does_not_expire_or_send(self):
        result = detect_expiration(TASK, CONDITION, now=NOW)
        self.assertEqual((result.state, result.notice.delivery_state, result.notice.attempts), ("NOTICE_REQUIRED", "PENDING", ()))
        self.assertEqual(result.notice.notice_id, detect_expiration(TASK, replace(CONDITION, evidence_id="synthetic-refreshed"), now=NOW + MINUTE).notice.notice_id)
        self.assertEqual(TASK.disposition, "ACTIVE")
        self.assertEqual(TASK.completion, "INCOMPLETE")

    def test_required_optional_completed_and_inactive_are_not_expired(self):
        for task in (replace(TASK, requiredness="REQUIRED"), replace(TASK, requiredness="OPTIONAL"), replace(TASK, completion="COMPLETE"), replace(TASK, disposition="CANCELLED"), replace(TASK, disposition="EXPIRED")):
            self.assertEqual(detect_expiration(task, CONDITION, now=NOW).state, "NOT_APPLICABLE")

    def test_uncertain_future_false_and_wrong_conditions_do_not_trigger(self):
        for condition in (replace(CONDITION, confirmed=None), replace(CONDITION, observed_at=NOW + MINUTE), replace(CONDITION, condition_ref="synthetic-wrong")):
            self.assertEqual(detect_expiration(TASK, condition, now=NOW).state, "UNCERTAIN")
        self.assertEqual(detect_expiration(TASK, replace(CONDITION, confirmed=False), now=NOW).state, "NOT_APPLICABLE")

    def test_queued_entry_and_crash_before_result_are_not_delivery(self):
        self.assertEqual(self.evaluate(notice=self.notice()).reason, "NOTICE_NOT_DELIVERED")
        notice = self.queued()
        self.assertEqual(self.evaluate(notice=notice).reason, "NOTICE_NOT_DELIVERED")
        with self.assertRaises(ValueError):
            begin_dispatch(notice, attempt_id="synthetic-unsafe-retry", started_at=NOW + 5 * MINUTE)

    def test_confirmed_failure_allows_retry_and_preserves_attempts(self):
        queued = self.queued()
        failed = record_dispatch(queued, self.result(queued, "FAILED"))
        self.assertEqual(self.evaluate(notice=failed).reason, "NOTICE_NOT_DELIVERED")
        retry = begin_dispatch(failed, attempt_id="synthetic-retry", started_at=NOW + 4 * MINUTE, correlation_ref="synthetic-correlation")
        success = record_dispatch(retry, DispatchResult(retry.notice_id, DispatchAttempt("synthetic-retry", NOW + 4 * MINUTE, "DELIVERED", NOW + 6 * MINUTE, NOW + 5 * MINUTE, "synthetic-retry-receipt", "synthetic-correlation")))
        self.assertEqual([item.state for item in success.attempts], ["FAILED", "DELIVERED"])
        self.assertEqual(len(success.dispatch_history), 2)
        self.assertEqual(queued.delivery_state, "PENDING")
        with self.assertRaises(ValueError):
            begin_dispatch(failed, attempt_id="synthetic-too-early", started_at=NOW + 2 * MINUTE)

    def test_unknown_blocks_resend_until_original_result_reconciled(self):
        queued = self.queued()
        unknown = record_dispatch(queued, self.result(queued, "UNKNOWN"))
        self.assertEqual(self.evaluate(notice=unknown).reason, "NOTICE_NOT_DELIVERED")
        with self.assertRaises(ValueError):
            begin_dispatch(unknown, attempt_id="synthetic-resend", started_at=NOW + 4 * MINUTE)
        success = self.result(unknown, finished_at=NOW + 4 * MINUTE)
        with self.assertRaises(ValueError):
            record_dispatch(unknown, success)
        reconciled = reconcile_dispatch(unknown, success)
        self.assertTrue(self.evaluate(notice=reconciled).ready)
        self.assertEqual([result.attempt.state for result in reconciled.dispatch_history], ["UNKNOWN", "DELIVERED"])
        self.assertEqual(unknown.delivery_state, "UNKNOWN")

    def test_unknown_reconciled_failure_allows_safe_retry(self):
        queued = self.queued()
        unknown = record_dispatch(queued, self.result(queued, "UNKNOWN"))
        failed = reconcile_dispatch(unknown, self.result(unknown, "FAILED", finished_at=NOW + 4 * MINUTE))
        retry = begin_dispatch(failed, attempt_id="synthetic-new-attempt", started_at=NOW + 5 * MINUTE)
        self.assertEqual(retry.delivery_state, "PENDING")
        self.assertEqual(len(retry.attempts), 2)

    def test_request_and_result_replay_are_idempotent(self):
        queued = self.queued()
        self.assertEqual(begin_dispatch(queued, attempt_id="synthetic-attempt", started_at=NOW + MINUTE, correlation_ref="synthetic-correlation"), queued)
        result = self.result(queued)
        delivered = record_dispatch(queued, result)
        self.assertEqual(record_dispatch(delivered, result), delivered)
        self.assertEqual(len(delivered.dispatch_history), 1)
        with self.assertRaises(ValueError):
            begin_dispatch(delivered, attempt_id="synthetic-extra-notice", started_at=NOW + 4 * MINUTE)

    def test_wrong_notice_attempt_correlation_and_conflicting_results_are_rejected(self):
        queued = self.queued()
        result = self.result(queued)
        for wrong in (replace(result, notice_id="synthetic-other-notice"), replace(result, attempt=replace(result.attempt, attempt_id="synthetic-other-attempt")), replace(result, attempt=replace(result.attempt, correlation_ref="synthetic-other-correlation"))):
            with self.assertRaises(ValueError):
                record_dispatch(queued, wrong)
        with self.assertRaises(ValueError):
            record_dispatch(record_dispatch(queued, result), self.result(queued, "FAILED"))

    def test_delivered_notice_is_ready_without_read_acknowledgement(self):
        decision = self.evaluate()
        self.assertTrue(decision.ready)
        self.assertEqual(decision.notice_evidence.delivery_state, "DELIVERED")
        self.assertEqual(decision.notice_evidence.task_revision, TASK.revision)
        self.assertEqual(TASK.disposition, "ACTIVE")

    def test_post_delivery_completion_and_scope_races_cannot_overwrite(self):
        for task in (replace(TASK, completion="COMPLETE"), replace(TASK, disposition="CANCELLED"), replace(TASK, requiredness="REQUIRED")):
            self.assertEqual(self.evaluate(task=task).reason, "TASK_NOT_EXPIRABLE")
        for task in (replace(TASK, revision=3), replace(TASK, task_id="synthetic-other"), replace(TASK, expiration_condition_ref="synthetic-changed-condition")):
            self.assertEqual(self.evaluate(task=task).reason, "STALE_NOTICE_SCOPE")

    def test_condition_is_checked_again_after_delivery(self):
        for condition in (self.current_condition(confirmed=False), self.current_condition(confirmed=None), self.current_condition(condition_ref="synthetic-wrong"), CONDITION):
            self.assertEqual(self.evaluate(condition=condition).reason, "CURRENT_CONDITION_UNCONFIRMED")
        self.assertEqual(self.evaluate(condition=self.current_condition(), checked_at=NOW + MINUTE).reason, "FUTURE_EVIDENCE")

    def test_ready_notice_still_requires_scoped_transaction_authority(self):
        evidence = self.evaluate().notice_evidence
        patch = change(TASK.task_id, TASK.revision, "EXPIRE_TASK", {"disposition": "EXPIRED", "expiration_notice_ref": evidence.notice_id})
        command = Command("synthetic-expire-command", "synthetic-system", "EXPIRATION_PROCESS", "synthetic-expire-grant", (patch,))
        caller = CallerIdentity(command.principal_id, command.origin, True)
        args = dict(caller=caller, tasks={TASK.task_id: TASK}, now=NOW + 5 * MINUTE, notices={evidence.notice_id: evidence})
        self.assertFalse(authorize(command, grants={}, **args).allowed)
        grant = AuthorityGrant(command.authority_ref, command.principal_id, command.origin, command.command_id, command.changes, "synthetic-D073-policy", NOW)
        self.assertTrue(authorize(command, grants={grant.grant_id: grant}, **args).allowed)
        self.assertEqual(patch.fields, {"disposition": "EXPIRED", "expiration_notice_ref": evidence.notice_id})

    def test_serialized_states_and_results_satisfy_schemas(self):
        for notice in (self.notice(), self.queued(), self.delivered()):
            self.assertEqual(validate_contract("expiration-notice", notice.as_record()), ())
        queued = self.queued()
        unknown = record_dispatch(queued, self.result(queued, "UNKNOWN"))
        reconciled = reconcile_dispatch(unknown, self.result(unknown, finished_at=NOW + 4 * MINUTE))
        self.assertEqual(validate_contract("expiration-notice", reconciled.as_record()), ())
        for state in ("DELIVERED", "FAILED", "UNKNOWN"):
            self.assertEqual(validate_contract("dispatch-result", self.result(queued, state).as_record()), ())

    def test_typed_chronology_and_explicit_delivery_validation(self):
        with self.assertRaises(ValueError):
            DispatchAttempt("synthetic-invalid", NOW, "DELIVERED", NOW + MINUTE, NOW - MINUTE, "synthetic-evidence")
        with self.assertRaises(ValueError):
            DispatchAttempt("synthetic-invalid", NOW, "UNKNOWN", NOW + MINUTE, NOW, "synthetic-evidence")
        with self.assertRaises(ValueError):
            begin_dispatch(self.notice(), attempt_id="synthetic-too-early", started_at=NOW - MINUTE)
        with self.assertRaises(ValueError):
            ConditionEvidence("synthetic-id", CONDITION.condition_ref, 1, NOW)

    def test_schema_cases(self):
        fixture = load_json(ROOT / "tests/fixtures/expiration/cases.json")
        self.assertIs(fixture["synthetic"], True)
        for case in fixture["cases"]:
            with self.subTest(case=case["id"]):
                self.assertEqual(not validate_contract(case["contract"], case["payload"]), case["valid"])


if __name__ == "__main__":
    unittest.main()
