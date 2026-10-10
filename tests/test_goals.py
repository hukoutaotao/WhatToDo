from dataclasses import replace
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from fractions import Fraction
import unittest

from src.domain.goals import (
    Cadence, Exam, ExamCoverage, GoalConfig, GoalPhase, GoalProgress, GoalTarget,
    Measure, Milestone, RuleReference, assess_onboarding, measured_target_fraction,
    validate_milestones,
)
from src.domain.time_windows import Interval, normalize_due
from tools.check_contracts import validate_contract
from tools.validate_task_core import ROOT, load_json


NOW = datetime(2026, 1, 1, 12, tzinfo=timezone.utc)


class GoalTests(unittest.TestCase):
    def goal(self, **values):
        config = GoalConfig("synthetic-goal", 1, "Synthetic reading goal", "ACCEPTED", "synthetic-user-setup", GoalTarget("Synthetic outcome", Measure(Decimal(100), "synthetic-pages")), None, "QUANTITY", "synthetic-pages", True, normalize_due(date(2026, 6, 1), source_ref="synthetic-user-date"), Cadence("WEEKLY", "Synthetic weekly cadence", 2), (), ())
        return replace(config, **values)

    def draft(self, **values):
        return self.goal(acceptance="DRAFT", acceptance_ref=None, **values)

    def progress(self, amount="100", completion="INCOMPLETE", **values):
        record = GoalProgress("synthetic-goal", 1, "synthetic-observation", NOW, "synthetic-user-progress", Measure(Decimal(amount), "synthetic-pages"), completion)
        return replace(record, **values)

    def milestone(self, **values):
        result = Milestone("synthetic-milestone", "synthetic-goal", 1, "Synthetic checkpoint", 1, None, Measure(Decimal(50), "synthetic-pages"), None)
        return replace(result, **values)

    def exam(self, **values):
        result = Exam("synthetic-exam", 1, "Synthetic exam", "synthetic-course", "ACCEPTED", "synthetic-user-exam", "synthetic-user-date", "DATE_ONLY", date(2026, 6, 1), None)
        return replace(result, **values)

    def test_partial_setup_keeps_all_missing_facts_without_defaults(self):
        goal = self.draft(target=None, workload=None, progress_measure_kind=None, progress_unit=None, target_due_known=False, target_due=None, cadence=None, phases=None, generation_rules=None)
        readiness = assess_onboarding(goal)
        self.assertFalse(readiness.configuration_ready)
        self.assertEqual(set(readiness.missing_fields), {"target", "workload_or_measured_target", "progress_measure", "target_due_or_explicit_none", "cadence_or_explicit_none", "phases_or_explicit_none", "generation_rules_or_candidate_only", "acceptance"})
        self.assertEqual(readiness.generation_state, "PENDING")
        self.assertIsNone(goal.workload)
        self.assertIsNone(goal.phases)

    def test_complete_setup_still_needs_review_and_rule_resolution(self):
        self.assertEqual(assess_onboarding(self.draft()).missing_fields, ("acceptance",))
        ready = assess_onboarding(self.goal())
        self.assertTrue(ready.configuration_ready)
        self.assertEqual(ready.generation_state, "CANDIDATE_ONLY")
        scoped = assess_onboarding(self.goal(generation_rules=(RuleReference("synthetic-rule", "1"),)))
        self.assertEqual(scoped.generation_state, "RULE_RESOLUTION_REQUIRED")

    def test_explicit_no_horizon_cadence_or_phases_differs_from_unknown(self):
        goal = self.goal(target_due=None, target_due_known=True, cadence=Cadence("NONE", "Explicit one-off work"), phases=(), generation_rules=())
        self.assertTrue(assess_onboarding(goal).configuration_ready)
        draft = replace(goal, acceptance="DRAFT", acceptance_ref=None, target_due_known=False, cadence=None, phases=None)
        self.assertIn("target_due_or_explicit_none", assess_onboarding(draft).missing_fields)
        self.assertIn("cadence_or_explicit_none", assess_onboarding(draft).missing_fields)

    def test_target_measure_or_total_workload_can_complete_setup(self):
        qualitative = self.goal(target=GoalTarget("Synthetic qualitative outcome"), workload=Measure(Decimal(10), "synthetic-hours"), progress_measure_kind="CONFIRMED_OUTCOME", progress_unit=None)
        self.assertTrue(assess_onboarding(qualitative).configuration_ready)
        self.assertTrue(assess_onboarding(self.goal(workload=None)).configuration_ready)
        with self.assertRaises(ValueError):
            self.goal(target=GoalTarget("Unknown scope"), workload=None)

    def test_numeric_attainment_never_infers_confirmed_completion(self):
        for amount, ratio in (("50", Fraction(1, 2)), ("100", Fraction(1)), ("150", Fraction(3, 2))):
            progress = self.progress(amount)
            self.assertEqual(measured_target_fraction(self.goal(), progress), ratio)
            self.assertEqual(progress.completion, "INCOMPLETE")
        confirmed = self.progress("50", "COMPLETE")
        self.assertEqual(measured_target_fraction(self.goal(), confirmed), Fraction(1, 2))
        self.assertEqual(confirmed.completion, "COMPLETE")

    def test_progress_ratio_is_exact_and_not_sum_of_observations(self):
        goal = self.goal(target=GoalTarget("Synthetic one-third", Measure(Decimal(3), "synthetic-pages")))
        self.assertEqual(measured_target_fraction(goal, self.progress("1")), Fraction(1, 3))
        self.assertEqual(measured_target_fraction(goal, self.progress("2", observation_id="synthetic-next-observation")), Fraction(2, 3))

    def test_progress_revision_and_units_require_resolution(self):
        for progress in (self.progress(goal_revision=2), self.progress(goal_id="synthetic-other-goal"), self.progress(reported=Measure(Decimal(1), "synthetic-hours"))):
            with self.assertRaises(ValueError):
                measured_target_fraction(self.goal(), progress)
        self.assertIsNone(measured_target_fraction(self.goal(), self.progress(reported=None)))

    def test_zero_target_or_qualitative_outcome_has_no_invented_ratio(self):
        zero = self.goal(target=GoalTarget("Explicit zero target", Measure(Decimal(0), "synthetic-pages")))
        self.assertIsNone(measured_target_fraction(zero, self.progress("0")))
        qualitative = self.goal(target=GoalTarget("Synthetic qualitative target"), workload=Measure(Decimal(1), "synthetic-unit"), progress_measure_kind="CONFIRMED_OUTCOME", progress_unit=None)
        self.assertIsNone(measured_target_fraction(qualitative, self.progress(reported=None)))

    def test_goal_and_milestones_have_no_duplicate_task_effort(self):
        goal, milestone = self.goal(), self.milestone()
        self.assertEqual(validate_milestones(goal, (milestone,)), ())
        for record in (goal.as_record(), milestone.as_record(), self.exam().as_record()):
            self.assertNotIn("user_remaining_seconds", record)
            self.assertNotIn("budget_seconds", record)
            self.assertNotIn("task_completion", record)

    def test_milestone_scope_phase_and_positions_are_checked(self):
        phase = GoalPhase("synthetic-phase", "Synthetic phase", 1)
        goal = self.goal(phases=(phase,))
        milestone = self.milestone(phase_ref=phase.phase_id)
        self.assertEqual(validate_milestones(goal, (milestone,)), ())
        self.assertEqual(validate_milestones(goal, (replace(milestone, goal_revision=2),)), ("STALE_MILESTONE_SCOPE:synthetic-milestone",))
        self.assertEqual(validate_milestones(self.goal(), (milestone,)), ("UNRESOLVED_PHASE_REFERENCE:synthetic-milestone",))
        with self.assertRaises(ValueError):
            validate_milestones(goal, (milestone, milestone))
        with self.assertRaises(ValueError):
            self.goal(phases=(phase, phase))

    def test_date_only_exam_does_not_become_deadline_2359_or_occupancy(self):
        exam = self.exam()
        self.assertEqual(exam.exam_date, date(2026, 6, 1))
        self.assertIsNone(exam.interval)
        self.assertEqual(exam.timing_kind, "DATE_ONLY")
        unknown = replace(exam, timing_kind="UNKNOWN", exam_date=None)
        self.assertIsNone(unknown.interval)
        with self.assertRaises(ValueError):
            replace(exam, interval=Interval(NOW, NOW + timedelta(hours=1)))

    def test_exact_exam_retains_source_timezone_and_independent_axis_coverage(self):
        start = datetime(2026, 6, 1, 9, tzinfo=timezone(timedelta(hours=8)))
        interval = Interval(start, start + timedelta(hours=2))
        coverage = ExamCoverage("synthetic-axis", "1", "synthetic-unit-1", "synthetic-unit-3")
        exam = self.exam(timing_kind="EXACT_EVENT", exam_date=None, interval=interval, coverage=coverage)
        self.assertIs(exam.interval, interval)
        self.assertEqual(exam.as_record()["interval"]["start"], "2026-06-01T09:00:00+08:00")
        self.assertEqual(exam.coverage.axis_ref, "synthetic-axis")
        self.assertNotIn("completion", exam.as_record())

    def test_invalid_quantities_cadence_and_accepted_partial_setup_are_rejected(self):
        for amount in (Decimal(-1), Decimal("NaN"), Decimal("Infinity"), 1.0):
            with self.assertRaises(ValueError):
                Measure(amount, "synthetic-unit")
        for cadence in (("DAILY", "Unresolved", None), ("NONE", "No recurring work", 1), ("WEEKLY", "Invalid count", True)):
            with self.assertRaises(ValueError):
                Cadence(*cadence)
        with self.assertRaises(ValueError):
            self.goal(generation_rules=None)
        with self.assertRaises(ValueError):
            self.goal(generation_rules=(RuleReference("synthetic-rule", "1"), RuleReference("synthetic-rule", "2")))

    def test_serialized_records_and_negative_zero_are_valid(self):
        for contract, record in (("goal", self.goal().as_record()), ("goal", self.draft(target=None).as_record()), ("milestone", self.milestone().as_record()), ("exam", self.exam().as_record()), ("goal-progress", self.progress().as_record()), ("goal-onboarding", assess_onboarding(self.goal()).as_record()), ("goal-onboarding", assess_onboarding(self.draft()).as_record())):
            self.assertEqual(validate_contract(contract, record), (), contract)
        zero_goal = self.goal(target=GoalTarget("Negative-zero representation", Measure(Decimal("-0.00"), "synthetic-pages")))
        self.assertEqual(zero_goal.target.measure.as_record()["amount"], "0")
        self.assertEqual(validate_contract("goal", zero_goal.as_record()), ())

    def test_schema_cases(self):
        fixture = load_json(ROOT / "tests/fixtures/goals/cases.json")
        self.assertIs(fixture["synthetic"], True)
        for case in fixture["cases"]:
            with self.subTest(case=case["id"]):
                self.assertEqual(not validate_contract(case["contract"], case["payload"]), case["valid"])


if __name__ == "__main__":
    unittest.main()
