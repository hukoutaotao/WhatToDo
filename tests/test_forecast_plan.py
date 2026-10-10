from dataclasses import replace
from datetime import datetime, timedelta
from fractions import Fraction
import unittest

from src.domain.effort import BudgetSelection, Stage, UserEstimate, partition_stages, select_budget
from src.domain.forecast import (
    PlacementEvidence, RequiredProjection, assess_forecast, forecast_fingerprint,
    overall_risk, safe_discretionary_budget,
)
from src.domain.plan_output import CompletedEmergencyReview, PlanItem, PlanSnapshot, PlanTask, WorkAllocation
from src.domain.time_windows import AvailabilityFrame, BEIJING, Interval, forecast_window
from tools.check_contracts import validate_contract
from tools.validate_task_core import ROOT, load_json


NOW = datetime(2026, 1, 1, 12, tzinfo=BEIJING)


class ForecastPlanTests(unittest.TestCase):
    def budget(self, seconds=3600, **values):
        budget = select_budget(task_id="synthetic-task", task_revision=1, snapshot_at=NOW, user_estimate=UserEstimate(seconds, "synthetic-estimate", NOW, NOW), prediction=None)
        return replace(budget, **values)

    def inputs(self, days=1, capacity=36000, required=3600, projections=None, quality="READY"):
        window = forecast_window(NOW, days)
        frame = AvailabilityFrame("synthetic-snapshot", NOW, window.cutoff, (Interval(NOW, NOW + timedelta(seconds=capacity)),) if capacity else (), (), quality, ("synthetic-capacity-gap",) if quality != "READY" else ())
        projection = RequiredProjection(self.budget(required), "REQUIRED", required, "FULL_DUE", "synthetic-projection")
        return window, frame, projections if projections is not None else (projection,)

    def evidence(self, window, frame, projections, outcome="FEASIBLE", **values):
        fingerprint = forecast_fingerprint(window, snapshot_ref=frame.snapshot_ref, availability=frame, projections=projections, hard_constraints_ref="synthetic-hard-constraints")
        result = PlacementEvidence(fingerprint, "synthetic-exact-oracle", "1", outcome, NOW + timedelta(seconds=1), "synthetic-placement-proof" if outcome in ("FEASIBLE", "INFEASIBLE") else None)
        return replace(result, **values)

    def evaluate(self, days=1, capacity=36000, required=3600, projections=None, quality="READY", outcome="FEASIBLE", evidence_values=None):
        window, frame, projections = self.inputs(days, capacity, required, projections, quality)
        placement = self.evidence(window, frame, projections, outcome, **(evidence_values or {})) if outcome is not None else None
        return assess_forecast(window, snapshot_ref=frame.snapshot_ref, availability=frame, projections=projections, hard_constraints_ref="synthetic-hard-constraints", placement=placement, assessed_at=NOW + timedelta(seconds=2))

    def plan(self, horizons=None, tasks=None, allocations=None, items=None, **values):
        result = PlanSnapshot("synthetic-plan", "synthetic-snapshot", 1, "synthetic-config-version", NOW + timedelta(seconds=3), horizons or tuple(self.evaluate(day) for day in (1, 3, 7)), tasks or (PlanTask(self.budget(), "Synthetic work", "REQUIRED"),), allocations if allocations is not None else (WorkAllocation("synthetic-allocation", "synthetic-task", 1, None, 600, "Synthetic objective", "FRAGMENTABLE"),), items if items is not None else (PlanItem("synthetic-item", "synthetic-allocation", "PROTECT_TODAY"),))
        return replace(result, **values)

    def review(self, **values):
        result = CompletedEmergencyReview("synthetic-initial-plan", "synthetic-complete-review", "synthetic-committed-review", "synthetic-user-choices", "synthetic-snapshot", "synthetic-round-two-solve", NOW - timedelta(seconds=1))
        return replace(result, **values)

    def test_exact_reserve_thresholds_and_margin(self):
        for capacity, risk in ((7200, "SAFE"), (7199, "DANGER"), (3600, "DANGER")):
            assessment = self.evaluate(capacity=capacity)
            self.assertEqual(assessment.risk, risk)
            self.assertEqual(assessment.reserve_seconds, 3600)
            self.assertEqual(assessment.margin_seconds, capacity - 3600)
        self.assertEqual(self.evaluate(capacity=3599, outcome=None).risk, "EMERGENCY")

    def test_day_reserve_does_not_shrink_for_elapsed_capacity(self):
        for day in (1, 3, 7):
            assessment = self.evaluate(day, capacity=3600, required=0)
            self.assertEqual(assessment.reserve_seconds, day * 3600)
        self.assertEqual(self.evaluate(7, capacity=3600, required=0).risk, "DANGER")

    def test_positive_hours_do_not_prove_hard_constraint_feasibility(self):
        for outcome in (None, "TIMEOUT", "UNKNOWN", "ERROR"):
            assessment = self.evaluate(outcome=outcome)
            self.assertIsNone(assessment.risk)
            self.assertEqual(assessment.verification, "INCOMPLETE")
        impossible = self.evaluate(outcome="INFEASIBLE")
        self.assertEqual(impossible.risk, "EMERGENCY")
        self.assertGreater(impossible.margin_seconds, impossible.reserve_seconds)
        self.assertEqual(impossible.aggregate_deficit_seconds, 0)
        self.assertIsNone(impossible.placement.placement_deficit_seconds)

    def test_known_aggregate_deficit_is_proof_even_without_solver_result(self):
        for outcome in (None, "TIMEOUT", "UNKNOWN"):
            assessment = self.evaluate(capacity=1800, outcome=outcome)
            self.assertEqual((assessment.risk, assessment.aggregate_deficit_seconds), ("EMERGENCY", 1800))
            self.assertEqual(assessment.verification, "PROVEN_DEFICIT")

    def test_missing_or_stale_capacity_is_not_safe_or_precisely_emergency(self):
        for quality in ("UNRESOLVED", "STALE"):
            assessment = self.evaluate(capacity=1800, quality=quality, outcome="INFEASIBLE")
            self.assertIsNone(assessment.capacity_seconds)
            self.assertIsNone(assessment.risk)
            self.assertEqual(assessment.data_quality, quality)

    def test_unknown_effort_or_missing_canonical_estimate_requires_review(self):
        missing = BudgetSelection("synthetic-task", 1, None, "UNKNOWN", "MODEL_AND_USER_MISSING", None, None, True)
        projection = RequiredProjection(missing, "REQUIRED", None, "FULL_DUE", "synthetic-pending-projection")
        assessment = self.evaluate(projections=(projection,))
        self.assertIsNone(assessment.required_seconds)
        self.assertIsNone(assessment.risk)
        provisional = self.budget(source="MODEL", user_seconds=None, reference_id="synthetic-prediction", review_needed=True)
        assessment = self.evaluate(projections=(RequiredProjection(provisional, "REQUIRED", 3600, "FULL_DUE", "synthetic-projection"),))
        self.assertEqual(assessment.required_seconds, 3600)
        self.assertIsNone(assessment.risk)

    def test_model_budget_not_user_estimate_drives_r_in_both_directions(self):
        for model, user in ((3600, 7200), (7200, 3600)):
            selected = self.budget(model, source="MODEL", user_seconds=user, reference_id="synthetic-model")
            assessment = self.evaluate(projections=(RequiredProjection(selected, "REQUIRED", model, "FULL_DUE", "synthetic-model-projection"),))
            self.assertEqual(assessment.required_seconds, model)
            self.assertEqual(selected.user_seconds, user)

    def test_repeated_parent_projection_deduplicates_and_conflicting_scope_rejects(self):
        projection = self.inputs()[2][0]
        self.assertEqual(self.evaluate(projections=(projection, projection)).required_seconds, 3600)
        with self.assertRaises(ValueError):
            self.evaluate(projections=(projection, replace(projection, projection_ref="synthetic-conflicting-proof")))
        with self.assertRaises(ValueError):
            self.evaluate(projections=(projection, replace(projection, budget=replace(projection.budget, task_revision=2))))

    def test_necessary_early_allocation_is_a_partition_not_all_distant_work(self):
        projection = RequiredProjection(self.budget(7200), "REQUIRED", Fraction(1800), "NECESSARY_EARLY", "synthetic-long-horizon-proof")
        assessment = self.evaluate(projections=(projection,))
        self.assertEqual(assessment.required_seconds, 1800)
        self.assertEqual(projection.budget.seconds, 7200)
        with self.assertRaises(ValueError):
            replace(projection, basis="FULL_DUE")

    def test_required_prerequisite_keeps_its_original_requiredness(self):
        projection = RequiredProjection(self.budget(), "OPTIONAL", 1800, "HARD_PREREQUISITE", "synthetic-prerequisite-proof", ("synthetic-required-dependent",), "synthetic-hard-relation")
        self.assertEqual(self.evaluate(projections=(projection,)).required_seconds, 1800)
        self.assertEqual(projection.requiredness, "OPTIONAL")
        with self.assertRaises(ValueError):
            replace(projection, protected_required_tasks=())
        with self.assertRaises(ValueError):
            RequiredProjection(self.budget(), "OPTIONAL", 3600, "FULL_DUE", "synthetic-not-authorized")

    def test_placement_proof_binds_current_inputs_and_time(self):
        for evidence_values in ({"input_fingerprint": "f" * 64}, {"computed_at": NOW - timedelta(seconds=1)}, {"computed_at": NOW + timedelta(seconds=10)}):
            assessment = self.evaluate(evidence_values=evidence_values)
            self.assertIsNone(assessment.risk)
            self.assertEqual(assessment.data_quality, "CONFLICTED")
        contradiction = self.evaluate(capacity=1800, outcome="FEASIBLE")
        self.assertIsNone(contradiction.risk)
        self.assertIn("PLACEMENT_AGGREGATE_CONTRADICTION", contradiction.diagnostics)

    def test_forecast_snapshot_and_cutoff_scope_cannot_be_mixed(self):
        window, frame, projections = self.inputs()
        for wrong in (replace(frame, snapshot_ref="synthetic-other"), replace(frame, cutoff=frame.cutoff - timedelta(hours=1)), replace(frame, snapshot_at=NOW + timedelta(seconds=1))):
            with self.assertRaises(ValueError):
                forecast_fingerprint(window, snapshot_ref="synthetic-snapshot", availability=wrong, projections=projections, hard_constraints_ref="synthetic-hard-constraints")

    def test_worst_horizon_and_missing_knowledge_are_separate(self):
        safe = tuple(self.evaluate(day) for day in (1, 3, 7))
        self.assertEqual(overall_risk(safe), "SAFE")
        self.assertEqual(overall_risk((safe[0], self.evaluate(3, capacity=4000), safe[2])), "DANGER")
        self.assertIsNone(overall_risk((safe[0], self.evaluate(3, outcome=None), safe[2])))
        mixed = (self.evaluate(1, outcome=None), self.evaluate(3, capacity=1800, outcome=None), safe[2])
        self.assertEqual(overall_risk(mixed), "EMERGENCY")
        with self.assertRaises(ValueError):
            overall_risk(safe[:2])

    def test_safe_small_gap_rule_uses_day_total_after_required_and_reserve(self):
        for remainder in (0, 1200, 2400):
            self.assertEqual(safe_discretionary_budget(capacity_seconds=7200 + remainder, required_seconds=3600, reserve_seconds=3600), 0)
        self.assertEqual(safe_discretionary_budget(capacity_seconds=9601, required_seconds=3600, reserve_seconds=3600), 2401)
        with self.assertRaises(ValueError):
            safe_discretionary_budget(capacity_seconds=6000, required_seconds=3600, reserve_seconds=3600)

    def test_plan_sections_reference_one_allocation_without_extra_effort(self):
        items = (PlanItem("synthetic-main", "synthetic-allocation", "PROTECT_TODAY"), PlanItem("synthetic-navigation", "synthetic-allocation", "FRAGMENTABLE_REFERENCE"))
        plan = self.plan(items=items)
        self.assertEqual(plan.selected_seconds, 600)
        self.assertEqual(plan.tasks[0].budget.seconds, 3600)
        self.assertEqual(plan.as_record()["selected_seconds"], {"numerator": 600, "denominator": 1})

    def test_plan_role_does_not_replace_requiredness(self):
        plan = self.plan(items=(PlanItem("synthetic-item", "synthetic-allocation", "OPTIONAL_ADDON"),))
        self.assertEqual(plan.tasks[0].requiredness, "REQUIRED")
        self.assertEqual(plan.items[0].role, "OPTIONAL_ADDON")
        self.assertEqual(plan.horizons[0].required_seconds, 3600)

    def test_stage_selected_effort_is_bounded_by_one_parent_partition(self):
        budget = self.budget()
        partition = partition_stages(budget, (Stage("synthetic-stage-1", "INCOMPLETE", Fraction(1)), Stage("synthetic-stage-2", "INCOMPLETE", Fraction(1))))
        task = PlanTask(budget, "Synthetic staged work", "REQUIRED", partition)
        allocation = WorkAllocation("synthetic-allocation", budget.task_id, 1, "synthetic-stage-1", 600, "Synthetic stage objective", "FRAGMENTABLE")
        plan = self.plan(tasks=(task,), allocations=(allocation,))
        self.assertEqual(plan.selected_seconds, 600)
        self.assertEqual(partition.allocations[0].seconds, 1800)
        with self.assertRaises(ValueError):
            self.plan(tasks=(task,), allocations=(replace(allocation, seconds=1801),))
        with self.assertRaises(ValueError):
            self.plan(allocations=(allocation,))

    def test_parent_stage_mixture_over_budget_and_stale_allocations_are_rejected(self):
        for allocation in (WorkAllocation("synthetic-allocation", "synthetic-task", 2, None, 600, "Stale", "EITHER"), WorkAllocation("synthetic-allocation", "synthetic-task", 1, None, 3601, "Too much", "EITHER")):
            with self.assertRaises(ValueError):
                self.plan(allocations=(allocation,))
        with self.assertRaises(ValueError):
            self.plan(items=(PlanItem("synthetic-unknown", "synthetic-missing-allocation", "ADVANCE"),))
        with self.assertRaises(ValueError):
            self.plan(items=())
        task = PlanTask(self.budget(), "Synthetic staged task", "REQUIRED", partition_stages(self.budget(), (Stage("synthetic-stage", "INCOMPLETE", Fraction(1)),)))
        allocations = (WorkAllocation("synthetic-stage-allocation", "synthetic-task", 1, "synthetic-stage", 600, "Stage", "EITHER"), WorkAllocation("synthetic-parent-allocation", "synthetic-task", 1, None, 400, "Parent", "EITHER"))
        items = tuple(PlanItem("synthetic-item-" + str(index), allocation.allocation_id, "PROTECT_TODAY") for index, allocation in enumerate(allocations))
        with self.assertRaisesRegex(ValueError, "Parent/stage"):
            self.plan(tasks=(task,), allocations=allocations, items=items)

    def test_publishable_selection_cannot_exceed_today_capacity(self):
        horizons = tuple(self.evaluate(day, capacity=100, projections=()) for day in (1, 3, 7))
        with self.assertRaisesRegex(ValueError, "today's usable capacity"):
            self.plan(horizons=horizons)

    def test_emergency_baseline_is_provisional_and_final_requires_independent_review(self):
        horizons = tuple(self.evaluate(day, capacity=1800, outcome=None) for day in (1, 3, 7))
        baseline = self.plan(horizons=horizons)
        self.assertEqual((baseline.risk, baseline.phase), ("EMERGENCY", "PROVISIONAL_EMERGENCY"))
        final = replace(baseline, emergency_review=self.review())
        self.assertEqual((final.risk, final.phase), ("EMERGENCY", "FINAL_EMERGENCY"))
        self.assertEqual(final.horizons[0].required_seconds, baseline.horizons[0].required_seconds)
        self.assertEqual(self.plan(emergency_review=self.review()).phase, "FINAL_EMERGENCY")

    def test_final_emergency_rejects_partial_scope_unknown_recompute_or_future_review(self):
        for review in (self.review(initial_plan_ref="synthetic-plan"), self.review(recomputed_snapshot_ref="synthetic-other"), self.review(completed_at=NOW + timedelta(seconds=1))):
            with self.assertRaises(ValueError):
                self.plan(emergency_review=review)
        horizons = (self.evaluate(1), self.evaluate(3, outcome=None), self.evaluate(7))
        with self.assertRaises(ValueError):
            self.plan(horizons=horizons, emergency_review=self.review())
        self.assertEqual(self.plan(horizons=horizons).phase, "UNVERIFIED")

    def test_output_catalogue_and_horizon_task_revisions_must_agree(self):
        with self.assertRaises(ValueError):
            self.plan(tasks=(PlanTask(self.budget(task_revision=2), "Stale catalogue", "REQUIRED"),), allocations=(), items=())
        with self.assertRaises(ValueError):
            self.plan(tasks=(PlanTask(self.budget(), "Wrong requiredness", "OPTIONAL"),))

    def test_plan_serializer_satisfies_schema_for_all_output_phases(self):
        emergency = tuple(self.evaluate(day, capacity=1800, outcome=None) for day in (1, 3, 7))
        unknown = tuple(self.evaluate(day, outcome=None) for day in (1, 3, 7))
        for plan in (self.plan(), self.plan(horizons=unknown), self.plan(horizons=emergency), self.plan(horizons=emergency, emergency_review=self.review()), self.plan(emergency_review=self.review())):
            self.assertEqual(validate_contract("plan", plan.as_record()), (), plan.phase)

    def test_exact_types_and_unproved_results_are_rejected(self):
        with self.assertRaises(ValueError):
            PlacementEvidence("synthetic-fingerprint", "synthetic-heuristic", "1", "INFEASIBLE", NOW, None)
        with self.assertRaises(ValueError):
            WorkAllocation("synthetic-allocation", "synthetic-task", 1, None, 1.5, "Invalid float", "EITHER")
        with self.assertRaises(ValueError):
            RequiredProjection(self.budget(), "REQUIRED", True, "FULL_DUE", "Invalid bool")

    def test_schema_cases(self):
        fixture = load_json(ROOT / "tests/fixtures/forecast_plan/cases.json")
        self.assertIs(fixture["synthetic"], True)
        for case in fixture["cases"]:
            with self.subTest(case=case["id"]):
                self.assertEqual(not validate_contract(case["contract"], case["payload"]), case["valid"])


if __name__ == "__main__":
    unittest.main()
