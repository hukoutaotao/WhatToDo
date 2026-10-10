"""Independent draft-design failure probes; no PostgreSQL is exercised here."""
from copy import deepcopy
from fractions import Fraction
from tempfile import TemporaryDirectory
from pathlib import Path
import re
import unittest

from src.domain.effort import Stage
from tools.check_database_design import DESIGN, OWNERSHIP, validate_design, validate_ownership
from tools.render_database_design import render_migrations, check_files
from tools.validate_task_core import load_json


def table(model, name):
    return next(t for t in model["tables"] if t["name"] == name)


class DatabaseDesignTests(unittest.TestCase):
    def setUp(self):
        self.model = load_json(DESIGN)
        self.ownership = load_json(OWNERSHIP)

    def reject(self, mutate, expected):
        mutate(self.model)
        self.assertIn(expected, validate_design(self.model))

    def test_all_contracts_have_resolved_relational_owners_without_runtime_claim(self):
        self.assertEqual(validate_design(self.model), [])
        self.assertEqual(validate_ownership(self.ownership, self.model), [])
        self.assertIsNone(self.ownership["runtime_version"])
        self.assertEqual(self.ownership["status"], "DRAFT_NOT_APPLICATION_MIGRATED")

    def test_rule_version_cannot_become_part_of_occurrence_identity(self):
        self.reject(lambda m: table(m, "generation_occurrence")["unique"][0].append("rule_version"), "semantic.identity.generation_occurrence")

    def test_source_scope_and_unknown_revision_dedup_remain_explicit(self):
        self.reject(lambda m: table(m, "source_record").update(nulls_not_distinct=False), "semantic.source_null_identity")
        self.model = load_json(DESIGN)
        self.reject(lambda m: table(m, "source_identity").update(unique=[]), "semantic.identity.source_identity")

    def test_unchanged_verification_cannot_bind_another_task_or_frame_version(self):
        for target in ("review_member", "effort_observation"):
            with self.subTest(target=target):
                self.model = load_json(DESIGN)
                self.reject(lambda m: table(m, "estimate_verification").update(foreign_keys=[f for f in table(m, "estimate_verification")["foreign_keys"] if f["target"] != target]), "semantic.binding.estimate_verification")

    def test_task_estimate_requires_exact_observation_value_and_kind(self):
        self.reject(lambda m: table(m, "task_revision")["foreign_keys"].pop(3), "semantic.binding.task_revision")

    def test_derived_prediction_cannot_own_canonical_user_remaining(self):
        self.reject(lambda m: table(m, "remaining_prediction")["columns"].append({"name": "user_remaining_seconds", "type": "whattodo.seconds", "nullable": True}), "semantic.derived_not_u.remaining_prediction")

    def test_predictions_require_independent_applicability_and_matching_job_result(self):
        for target in ("numeric_eligibility", "ai_result", "ai_job_revision"):
            with self.subTest(target=target):
                self.model = load_json(DESIGN)
                self.reject(lambda m: table(m, "remaining_prediction").update(foreign_keys=[f for f in table(m, "remaining_prediction")["foreign_keys"] if f["target"] != target]), "semantic.binding.remaining_prediction")

    def test_history_update_cannot_be_enabled_to_simplify_lifecycle_state(self):
        for name in ("source_record", "audit_entry", "effort_observation", "model_lifecycle_event", "ai_job_event"):
            with self.subTest(table=name):
                self.model = load_json(DESIGN)
                self.reject(lambda m: table(m, name).update(immutable=False), "guard.mutable_scope")

    def test_state_audit_and_receipt_are_bound_to_the_same_transaction(self):
        self.reject(lambda m: table(m, "task_revision").update(foreign_keys=[f for f in table(m, "task_revision")["foreign_keys"] if f["target"] != "audit_change"]), "semantic.audit.task_revision")
        self.model = load_json(DESIGN)
        self.reject(lambda m: table(m, "command_transaction").update(foreign_keys=[f for f in table(m, "command_transaction")["foreign_keys"] if f["target"] != "audit_entry"]), "semantic.binding.command_transaction")

    def test_foreign_keys_reject_type_unique_and_missing_target_errors(self):
        mutations = [
            (lambda m: table(m, "task_head")["columns"][1].update(type="smallint"), "foreign_key.type"),
            (lambda m: table(m, "task_head")["foreign_keys"][0].update(target_columns=["title", "revision", "transaction_ref"]), "foreign_key.target_unique"),
            (lambda m: table(m, "task_head")["foreign_keys"][0].update(target="nonexistent_table"), "foreign_key.missing_target"),
        ]
        for mutation, expected in mutations:
            self.model = load_json(DESIGN)
            self.reject(mutation, expected)

    def test_safe_forecast_cannot_discard_hard_placement_or_protected_reserve(self):
        self.reject(lambda m: table(m, "forecast_horizon").update(checks=[c for c in table(m, "forecast_horizon")["checks"] if c["name"] != "safe_proof"]), "semantic.safe_proof")

    def test_completed_stage_retains_exact_fraction_without_inventing_parent_u(self):
        self.assertEqual(Stage("stage", "COMPLETE", Fraction(1, 3)).weight, Fraction(1, 3))
        columns = {c["name"]: c for c in table(self.model, "stage_revision")["columns"]}
        self.assertTrue(columns["user_remaining_seconds"]["nullable"])
        self.assertEqual(columns["weight_denominator"]["type"], "whattodo.positive_integer")
        self.reject(lambda m: table(m, "stage_revision")["checks"].append({"name": "complete_zero", "expression": "completion <> 'COMPLETE' OR user_remaining_seconds = 0"}), "semantic.stage_not_parent_u")

    def test_all_domain_work_styles_remain_representable(self):
        self.reject(lambda m: next(c for c in table(m, "plan_allocation")["checks"] if c["name"] == "session_mode").update(expression="session_mode IN ('FRAGMENTABLE','CONTIGUOUS')"), "semantic.work_styles")

    def test_nonfinite_numbers_and_time_cannot_bypass_design_domains(self):
        self.reject(lambda m: next(d for d in m["domains"] if d["name"] == "seconds").update(check="VALUE >= 0"), "semantic.finite_numeric")
        self.model = load_json(DESIGN)
        self.reject(lambda m: next(d for d in m["domains"] if d["name"] == "instant").update(check="TRUE"), "semantic.finite_time")

    def test_terminal_delivery_and_stable_occurrence_guards_cannot_be_removed(self):
        self.reject(lambda m: m["mutable_guards"]["generation_occurrence"].update(conditions=[]), "guard.terminal")
        self.model = load_json(DESIGN)
        self.reject(lambda m: m.update(partial_unique_indexes=[]), "semantic.one_terminal_delivery")

    def test_rejected_ai_outputs_can_be_retained_without_resolved_job(self):
        columns = {c["name"]: c for c in table(self.model, "ai_result")["columns"]}
        self.assertTrue(columns["resolved_job_id"]["nullable"])
        self.assertTrue(columns["resolved_job_revision"]["nullable"])
        self.reject(lambda m: table(m, "ai_result").update(checks=[c for c in table(m, "ai_result")["checks"] if c["name"] != "resolved_scope"]), "semantic.rejected_result_history")

    def test_renderer_checks_identifiers_expressions_and_bootstrap_before_writing(self):
        self.reject(lambda m: table(m, "task_head").update(name='task_head"; DROP TABLE x'), "table.identifier")
        self.model = load_json(DESIGN)
        self.reject(lambda m: next(d for d in m["domains"] if d["name"] == "ref").update(check="TRUE; DROP SCHEMA whattodo"), "domain.expression")
        self.model = load_json(DESIGN)
        self.reject(lambda m: table(m, "schema_migration").update(batch=5), "semantic.migration_bootstrap")
        with self.assertRaises(ValueError): render_migrations(self.model, self.ownership)

    def test_ownership_drift_and_false_applied_evidence_are_rejected(self):
        for mutate, expected in [
            (lambda o: o.update(runtime_version="18.0"), "ownership.evidence"),
            (lambda o: o["migration_batches"][0]["tables"].pop(), "ownership.batch_scope"),
            (lambda o: o["contract_ownership"][0].update(tables=["missing_table"]), "ownership.contract_target"),
        ]:
            original = deepcopy(self.ownership)
            mutate(original)
            self.assertIn(expected, validate_ownership(original, self.model))

    def test_generated_migration_order_resolves_forward_and_cyclic_references(self):
        batches = render_migrations(self.model, self.ownership)
        full = "\n".join(batches.values())
        positions = {name: full.index(f'CREATE TABLE "whattodo"."{name}" (') for name in [t["name"] for t in self.model["tables"]]}
        constraints = list(re.finditer(r'ALTER TABLE "whattodo"\."(\w+)" ADD CONSTRAINT .*?REFERENCES "whattodo"\."(\w+)"', full, re.S))
        self.assertEqual(len(constraints), sum(len(t["foreign_keys"]) for t in self.model["tables"]))
        for match in constraints:
            source, target = match.groups()
            self.assertLess(positions[source], match.start())
            self.assertLess(positions[target], match.start())
        self.assertEqual(full.count("DEFERRABLE INITIALLY DEFERRED"), len(constraints))
        self.assertNotIn("CASCADE", full)

    def test_sql_guards_cover_history_and_mutable_heads_without_self_granted_roles(self):
        full = "\n".join(render_migrations(self.model, self.ownership).values())
        self.assertEqual(full.count('CREATE TRIGGER "preserve_history"'), sum(t["immutable"] for t in self.model["tables"]))
        self.assertEqual(full.count('CREATE TRIGGER "preserve_row"'), 5)
        self.assertEqual(full.count('CREATE TRIGGER "guard_version"'), 5)
        self.assertIn("UNIQUE NULLS NOT DISTINCT", full)
        self.assertIn('REVOKE ALL ON SCHEMA "whattodo" FROM PUBLIC', full)
        self.assertNotIn("GRANT ", full)
        self.assertNotIn("SECURITY DEFINER", full)
        for batch in render_migrations(self.model, self.ownership).values():
            self.assertIn("BEGIN;", batch)
            self.assertTrue(batch.endswith("COMMIT;\n"))

    def test_draft_sql_drift_check_does_not_repair_or_overwrite_files(self):
        rendered = render_migrations(self.model, self.ownership)
        self.assertEqual(check_files(rendered), [])
        with TemporaryDirectory() as directory:
            path = Path(directory)
            for name, sql in rendered.items(): (path / name).write_text(sql, encoding="utf-8")
            target = path / next(iter(rendered))
            target.write_text("local modified draft\n", encoding="utf-8")
            self.assertIn(target.name, check_files(rendered, path))
            self.assertEqual(target.read_text(encoding="utf-8"), "local modified draft\n")


if __name__ == "__main__":
    unittest.main()
