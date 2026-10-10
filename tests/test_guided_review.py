from dataclasses import replace
from datetime import datetime, timedelta, timezone
import unittest

from src.application.guided_review import candidate_reply, prepare_response, present_review, render_review, task_reply, unchanged_reply
from src.domain.authorization import CallerIdentity
from src.domain.effort import UserEstimate
from src.domain.review import ReviewFrame, ReviewTask, assess_review
from tools.check_contracts import validate_contract

NOW = datetime(2026, 1, 1, 12, tzinfo=timezone.utc)
CALLER = CallerIdentity("synthetic-user", "USER_COMMAND", True)


class GuidedReviewTests(unittest.TestCase):
    def setUp(self):
        self.tasks = tuple(ReviewTask("task-" + str(i), 3, i, "INCOMPLETE", "ACTIVE", True, UserEstimate(i * 600, "estimate-" + str(i), NOW - timedelta(days=1), NOW - timedelta(hours=2)), "UNTOUCHED", "CURRENT") for i in (1, 2))
        self.frame = ReviewFrame("review", 2, "queue", NOW - timedelta(minutes=10), self.tasks, ("candidate-1",))
        self.view = present_review(self.frame, task_labels={"task-1": "低优先任务", "task-2": "高优先任务"}, candidate_labels={"candidate-1": "合成的外部作业"})

    def response(self, **changes):
        return prepare_response(self.view, current_frame=self.frame, submitted=True, statement_ref="captured-user-source", **changes)

    def coverage(self, response, **changes):
        values = dict(caller=CALLER, response_at=NOW); values.update(changes)
        return assess_review(self.frame, response, **values)

    def test_full_view_retains_low_priority_and_pending_candidates_without_answers(self):
        output = render_review(self.view)
        self.assertIn("高优先任务", output)
        self.assertIn("低优先任务", output)
        self.assertIn("合成的外部作业", output)
        self.assertLess(output.index("高优先任务"), output.index("低优先任务"))
        response, issues = self.response()
        self.assertEqual(issues, ())
        self.assertEqual(response.task_answers, ())
        self.assertFalse(self.coverage(response).responses_complete)

    def test_guided_natural_estimate_and_actual_preserve_their_different_meanings(self):
        parsed = task_reply(self.view, 1, completion="未完成", remaining="约40分钟", worked="做过", actual="20分钟", actual_measure="本次新增")
        response, issues = self.response(task_replies=(parsed,))
        self.assertFalse(validate_contract("review-response", response.as_record()))
        self.assertEqual(issues, ())
        effect = self.coverage(response).task_effects[0]
        self.assertEqual(effect.user_estimate.seconds, 2400)
        self.assertEqual(effect.actual_report.seconds, 1200)
        self.assertEqual(effect.actual_report.measure, "INCREMENT")
        self.assertFalse(self.coverage(response).responses_complete)
        self.assertEqual(self.tasks[1].user_estimate.seconds, 1200)

    def test_ambiguous_duration_measure_and_completion_cannot_silently_close_review(self):
        for args in (dict(remaining="20~30分钟"), dict(actual="20分钟"), dict(completion="差不多完成了"), dict(remaining="0.1秒"), dict(remaining="-1分钟")):
            with self.subTest(args=args):
                response, issues = self.response(task_replies=(task_reply(self.view, 1, **args),))
                self.assertTrue(issues)
                self.assertFalse(response.submitted)
                self.assertEqual(self.coverage(response).task_effects, ())

    def test_completed_answer_and_unknown_estimate_do_not_guess_work_or_candidate_decision(self):
        response, issues = self.response(task_replies=(task_reply(self.view, 1, completion="完成了"),))
        effect = self.coverage(response).task_effects[0]
        self.assertEqual(effect.completion, "COMPLETE")
        self.assertEqual(effect.user_estimate.seconds, 0)
        self.assertIsNone(effect.actual_report)
        self.assertIsNone(effect.worked_on)
        self.assertEqual(self.coverage(response).pending_candidate_ids, ("candidate-1",))
        draft = task_reply(self.view, 2, remaining="不确定")
        self.assertIsNone(draft.answer.remaining_seconds)

    def test_cumulative_actual_is_retained_without_subtracting_from_remaining(self):
        parsed = task_reply(self.view, 1, completion="未完成", remaining="0.5小时", actual="80分钟", actual_measure="累计")
        response, _ = self.response(task_replies=(parsed,))
        effect = self.coverage(response).task_effects[0]
        self.assertEqual(effect.user_estimate.seconds, 1800)
        self.assertEqual(effect.actual_report.measure, "CUMULATIVE")
        self.assertEqual(effect.actual_report.seconds, 4800)

    def test_defaults_and_missing_submission_are_not_user_confirmation(self):
        batch = unchanged_reply(self.view, (1, 2), batch_id="batch")
        response, _ = self.response(batches=(batch,))
        self.assertEqual(self.coverage(response).verifications, ())
        response, _ = prepare_response(self.view, current_frame=self.frame, submitted=False, statement_ref="captured-user-source", task_replies=(task_reply(self.view, 1, completion="完成了"),))
        self.assertIsNone(response.user_statement_ref)
        self.assertEqual(self.coverage(response).task_effects, ())

    def test_explicit_batch_preserves_all_members_values_and_original_observations(self):
        batch = unchanged_reply(self.view, (1, 2), batch_id="batch", confirm_estimate="确认", confirm_completion="确认", no_work="没做")
        candidate = candidate_reply(self.view, 1, "拒绝")
        response, issues = self.response(batches=(batch,), candidate_replies=(candidate,))
        coverage = self.coverage(response)
        self.assertTrue(coverage.responses_complete)
        self.assertFalse(issues)
        self.assertEqual({v.original_estimate.observation_id for v in coverage.verifications}, {"estimate-1", "estimate-2"})
        self.assertEqual({v.verified_estimate.seconds for v in coverage.verifications}, {600, 1200})
        self.assertTrue(all(v.verified_estimate.observed_at == NOW - timedelta(days=1) for v in coverage.verifications))
        self.assertEqual(coverage.candidate_effects[0].resolution, "REJECTED")

    def test_missing_or_worked_batch_member_is_never_dropped_to_make_the_batch_pass(self):
        missing = replace(self.frame, tasks=(replace(self.tasks[0], user_estimate=None), self.tasks[1]))
        batch, issues = unchanged_reply(present_review(missing), (1, 2), batch_id="batch", confirm_estimate="确认")
        self.assertIsNone(batch)
        self.assertIn("BATCH_ESTIMATE_MISSING", issues)
        worked = replace(self.frame, tasks=(replace(self.tasks[0], work_status="WORKED"), self.tasks[1]))
        view = present_review(worked)
        proposal = unchanged_reply(view, (1, 2), batch_id="batch", confirm_estimate="确认", confirm_completion="确认", no_work="没做")
        self.assertEqual(len(proposal[0].members), 2)
        response, _ = prepare_response(view, current_frame=worked, submitted=True, statement_ref="source", batches=(proposal,))
        coverage = assess_review(worked, response, caller=CALLER, response_at=NOW)
        self.assertEqual(coverage.verifications, ())
        self.assertTrue(coverage.issues[0].startswith("INVALID_UNCHANGED_BATCH"))

    def test_changed_frame_or_estimate_and_unknown_selection_cannot_bind_old_input(self):
        for changed in (replace(self.frame, revision=3), replace(self.frame, tasks=(replace(self.tasks[0], user_estimate=UserEstimate(700, "new-estimate", NOW, NOW)), self.tasks[1]))):
            with self.assertRaises(ValueError): prepare_response(self.view, current_frame=changed, submitted=True, statement_ref="source")
        for number in (0, 3, True):
            with self.assertRaises(ValueError): task_reply(self.view, number, completion="完成了")
        with self.assertRaises(ValueError): present_review(self.frame, task_labels={"task-2": "Only high priority"})

    def test_parsed_candidate_confirmation_cannot_authenticate_an_external_caller(self):
        response, _ = self.response(candidate_replies=(candidate_reply(self.view, 1, "确认"),))
        coverage = self.coverage(response, caller=CallerIdentity("external", "EXTERNAL", True))
        self.assertEqual(coverage.candidate_effects, ())
        self.assertIn("USER_SUBMISSION_REQUIRED", coverage.issues)

    def test_conflicting_no_work_or_complete_estimate_requires_clarification(self):
        for values in (dict(completion="完成了", remaining="10分钟"), dict(worked="没做", actual="10分钟", actual_measure="本次新增")):
            response, issues = self.response(task_replies=(task_reply(self.view, 1, **values),))
            self.assertTrue(issues)
            self.assertFalse(response.submitted)

    def test_external_title_controls_cannot_hide_the_rest_of_the_frame(self):
        view = present_review(self.frame, task_labels={"task-1": "正常事项", "task-2": "外部标题\x1b[2J\u202e\n伪装行"})
        output = render_review(view)
        self.assertNotIn("\x1b", output)
        self.assertNotIn("\u202e", output)
        self.assertIn("\\u001b", output)
        self.assertIn("正常事项", output)


if __name__ == "__main__": unittest.main()
