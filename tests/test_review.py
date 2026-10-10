from dataclasses import replace
from datetime import datetime, timedelta, timezone
import unittest

from src.domain.authorization import CallerIdentity
from src.domain.effort import UserEstimate
from src.domain.review import (
    ActualReport, CandidateAnswer, EstimateBinding, ReviewFrame, ReviewResponse,
    ReviewTask, TaskAnswer, UnchangedBatch, assess_review, questionnaire,
)
from tools.check_contracts import validate_contract
from tools.validate_task_core import ROOT, load_json


NOW = datetime(2026, 1, 1, 12, tzinfo=timezone.utc)
CALLER = CallerIdentity("synthetic-user", "USER_COMMAND", True)


class ReviewTests(unittest.TestCase):
    def task(self, identity="synthetic-task", **changes):
        estimate = UserEstimate(600, "estimate-" + identity, NOW - timedelta(days=1), NOW - timedelta(hours=2))
        value = ReviewTask(identity, 3, 4, "INCOMPLETE", "ACTIVE", True, estimate, "UNTOUCHED", "CURRENT")
        return replace(value, **changes)

    def frame(self, tasks=None, candidates=()):
        return ReviewFrame("synthetic-review", 2, "synthetic-full-queue-snapshot", NOW - timedelta(minutes=10), tuple(tasks or [self.task()]), tuple(candidates))

    def response(self, **changes):
        value = ReviewResponse("synthetic-review", 2, True, "synthetic-explicit-user-reply")
        return replace(value, **changes)

    def assess(self, frame, response, **changes):
        args = dict(caller=CALLER, response_at=NOW)
        args.update(changes)
        return assess_review(frame, response, **args)

    def batch(self, task=None, **changes):
        task = task or self.task()
        binding = EstimateBinding(task.task_id, task.revision, task.user_estimate.observation_id, task.user_estimate.seconds)
        value = UnchangedBatch("synthetic-batch", True, (binding,), True, None)
        return replace(value, **changes)

    def test_full_questionnaire_keeps_every_task_and_queue_item_without_default_answers(self):
        frame = self.frame([self.task("task-low", importance=1), self.task("task-high", importance=5)], ["candidate-low", "candidate-high", "candidate-later"])
        output = questionnaire(frame)
        self.assertEqual([task["task_id"] for task in output["tasks"]], ["task-high", "task-low"])
        self.assertEqual([item["candidate_id"] for item in output["pending_candidates"]], list(frame.pending_candidate_ids))
        self.assertTrue(all(task["completion_answer"] is None for task in output["tasks"]))

    def test_silence_and_populated_unsubmitted_suggestions_do_not_confirm(self):
        frame = self.frame(candidates=["candidate-1"])
        for response in (None, self.response(submitted=False, user_statement_ref=None, task_answers=(TaskAnswer("synthetic-task", 3, "COMPLETE"),))):
            result = self.assess(frame, response)
            self.assertFalse(result.responses_complete)
            self.assertEqual(result.pending_task_ids, ("synthetic-task",))
            self.assertEqual(result.pending_candidate_ids, ("candidate-1",))
            self.assertEqual(result.task_effects, ())

    def test_partial_reply_does_not_close_full_queue(self):
        frame = self.frame([self.task("task-1"), self.task("task-2")], ["candidate-1", "candidate-2"])
        response = self.response(task_answers=(TaskAnswer("task-1", 3, "INCOMPLETE", True, 300),), candidate_answers=(CandidateAnswer("candidate-1", "REJECTED"),))
        result = self.assess(frame, response)
        self.assertFalse(result.responses_complete)
        self.assertEqual(result.pending_task_ids, ("task-2",))
        self.assertEqual(result.pending_candidate_ids, ("candidate-2",))

    def test_complete_responses_are_separate_from_committed_review(self):
        frame = self.frame(candidates=["candidate-1"])
        response = self.response(task_answers=(TaskAnswer("synthetic-task", 3, "INCOMPLETE", True, 300),), candidate_answers=(CandidateAnswer("candidate-1", "CONFIRMED"),))
        result = self.assess(frame, response)
        self.assertTrue(result.responses_complete)
        self.assertEqual(result.task_effects[0].user_estimate.seconds, 300)
        self.assertEqual(frame.tasks[0].user_estimate.seconds, 600)
        self.assertFalse(hasattr(result, "persisted_review_complete"))
        self.assertEqual(validate_contract("review-response", response.as_record()), ())

    def test_worked_incomplete_requires_individual_remaining_even_if_old_estimate_exists(self):
        frame = self.frame([self.task(work_status="WORKED")])
        result = self.assess(frame, self.response(task_answers=(TaskAnswer("synthetic-task", 3, "INCOMPLETE", True),)))
        self.assertEqual(result.pending_task_ids, ("synthetic-task",))
        self.assertIsNone(result.task_effects[0].user_estimate)

    def test_unchanged_batch_preserves_original_number_observation_and_records_verification(self):
        task = self.task()
        frame = self.frame([task])
        response = self.response(batches=(self.batch(task),))
        result = self.assess(frame, response)
        self.assertTrue(result.responses_complete)
        verification = result.verifications[0]
        updated = verification.verified_estimate
        self.assertEqual(updated.seconds, task.user_estimate.seconds)
        self.assertEqual(updated.observed_at, task.user_estimate.observed_at)
        self.assertEqual(updated.observation_id, task.user_estimate.observation_id)
        self.assertEqual(updated.verified_at, NOW)
        self.assertIsNone(verification.no_work_statement)
        self.assertIsNone(result.task_effects[0].actual_report)
        self.assertEqual(result, self.assess(frame, response))

    def test_batch_verification_alone_does_not_invent_completion_confirmation(self):
        result = self.assess(self.frame(), self.response(batches=(self.batch(confirm_existing_completion=None),)))
        self.assertFalse(result.responses_complete)
        self.assertEqual(result.pending_task_ids, ("synthetic-task",))
        self.assertEqual(len(result.verifications), 1)

    def test_unknown_work_requires_explicit_no_work_scope_for_batch(self):
        frame = self.frame([self.task(work_status="UNKNOWN")])
        result = self.assess(frame, self.response(batches=(self.batch(),)))
        self.assertEqual(result.verifications, ())
        result = self.assess(frame, self.response(batches=(self.batch(no_work_statement=True),)))
        self.assertTrue(result.responses_complete)
        self.assertTrue(result.verifications[0].no_work_statement)

    def test_batch_excludes_worked_changed_uncertain_missing_and_inactive_estimates(self):
        variants = [self.task(work_status="WORKED"), self.task(estimate_status="CHANGED"), self.task(estimate_status="UNCERTAIN"), self.task(user_estimate=None, estimate_status="MISSING"), self.task(disposition="EXPIRED"), self.task(completion="COMPLETE")]
        batch = self.batch()
        for task in variants:
            with self.subTest(task=task):
                result = self.assess(self.frame([task]), self.response(batches=(batch,)))
                self.assertFalse(result.responses_complete)
                self.assertEqual(result.verifications, ())

    def test_batch_binds_exact_members_current_revision_estimate_id_and_value(self):
        frame = self.frame()
        original = self.batch()
        binding = original.members[0]
        for wrong in (replace(binding, task_id="unknown-task"), replace(binding, expected_revision=2), replace(binding, observation_id="different-estimate"), replace(binding, seconds=601)):
            result = self.assess(frame, self.response(batches=(replace(original, members=(wrong,)),)))
            self.assertEqual(result.verifications, ())
            self.assertFalse(result.responses_complete)

    def test_unanswered_or_declined_batch_is_not_confirmation(self):
        for flag in (None, False):
            result = self.assess(self.frame(), self.response(batches=(self.batch(confirmed=flag),)))
            self.assertEqual(result.verifications, ())
            self.assertFalse(result.responses_complete)

    def test_new_work_answer_cannot_hide_in_unchanged_batch(self):
        result = self.assess(self.frame(), self.response(task_answers=(TaskAnswer("synthetic-task", 3, "INCOMPLETE", True),), batches=(self.batch(),)))
        self.assertEqual(result.verifications, ())
        self.assertFalse(result.responses_complete)

    def test_actual_total_and_increment_remain_distinct_without_estimate_subtraction(self):
        for measure in ("CUMULATIVE", "INCREMENT"):
            response = self.response(task_answers=(TaskAnswer("synthetic-task", 3, "INCOMPLETE", True, 600, ActualReport(900, measure)),))
            result = self.assess(self.frame(), response)
            self.assertTrue(result.responses_complete)
            self.assertEqual(result.task_effects[0].actual_report.measure, measure)
            self.assertEqual(result.task_effects[0].user_estimate.seconds, 600)

    def test_explicit_completion_zero_and_zero_incomplete_do_not_conflate(self):
        result = self.assess(self.frame(), self.response(task_answers=(TaskAnswer("synthetic-task", 3, "COMPLETE"),)))
        self.assertEqual(result.task_effects[0].user_estimate.seconds, 0)
        result = self.assess(self.frame(), self.response(task_answers=(TaskAnswer("synthetic-task", 3, "INCOMPLETE", True, 0),)))
        self.assertEqual(result.task_effects[0].completion, "INCOMPLETE")
        contradictory = self.assess(self.frame(), self.response(task_answers=(TaskAnswer("synthetic-task", 3, "COMPLETE", remaining_seconds=600),)))
        self.assertFalse(contradictory.responses_complete)
        self.assertEqual(contradictory.task_effects, ())

    def test_stale_frame_task_and_external_submissions_stay_pending(self):
        frame = self.frame()
        response = self.response(task_answers=(TaskAnswer("synthetic-task", 3, "COMPLETE"),))
        for result in (self.assess(frame, replace(response, frame_revision=1)), self.assess(frame, response, caller=replace(CALLER, origin="EXTERNAL")), self.assess(frame, response, caller=replace(CALLER, authenticated=False)), self.assess(frame, replace(response, task_answers=(TaskAnswer("synthetic-task", 2, "COMPLETE"),)))):
            self.assertFalse(result.responses_complete)
            self.assertEqual(result.task_effects, ())
            self.assertEqual(result.pending_task_ids, ("synthetic-task",))

    def test_unknown_queue_answer_cannot_silently_close_review(self):
        response = self.response(task_answers=(TaskAnswer("synthetic-task", 3, "COMPLETE"),), candidate_answers=(CandidateAnswer("not-in-presented-queue", "CONFIRMED"),))
        result = self.assess(self.frame(), response)
        self.assertFalse(result.responses_complete)
        self.assertEqual(result.candidate_effects, ())

    def test_duplicate_response_and_overlapping_confirmed_batches_rejected(self):
        answer = TaskAnswer("synthetic-task", 3, "COMPLETE")
        with self.assertRaises(ValueError):
            self.response(task_answers=(answer, answer))
        with self.assertRaises(ValueError):
            self.response(batches=(self.batch(), self.batch(batch_id="another-batch")))

    def test_schema_cases(self):
        fixture = load_json(ROOT / "tests/fixtures/review/cases.json")
        self.assertIs(fixture["synthetic"], True)
        for case in fixture["cases"]:
            with self.subTest(case=case["id"]):
                self.assertEqual(not validate_contract(case["contract"], case["payload"]), case["valid"])


if __name__ == "__main__":
    unittest.main()
