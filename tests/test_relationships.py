from copy import deepcopy
from dataclasses import replace
from datetime import datetime, timedelta, timezone
import unittest

from src.domain.authorization import AuthorityGrant, CallerIdentity, Command, CreationRecord, RuleScope, TaskState, authorize, change
from src.domain.relationships import (
    Endpoint, ExecutionTimes, FieldMapping, GenerationOccurrence, RelationshipRule,
    TaskRelation, check_execution_order, check_relationships, literal, resolve_generation,
)
from tools.check_contracts import validate_contract
from tools.validate_task_core import ROOT, load_json


NOW = datetime(2026, 1, 1, 12, tzinfo=timezone.utc)
A, B = Endpoint("TASK", "synthetic-lab"), Endpoint("TASK", "synthetic-preparation")
ENDPOINTS = frozenset((A, B))


class RelationshipTests(unittest.TestCase):
    def rule(self, **values):
        result = RelationshipRule("synthetic-rule", "1", True, "synthetic-user-rule", "CANONICAL_CREATION", "synthetic-lab-type", "synthetic-preparation-type", "synthetic-template", "1", "preparation", "SEPARATE_TASK", ("title", "completion", "disposition", "requiredness"), (
            FieldMapping("title", "SOURCE", "preparation_title", None),
            literal("completion", "INCOMPLETE"), literal("disposition", "ACTIVE"),
            FieldMapping("requiredness", "DEFAULT", "requiredness", None),
        ))
        return replace(result, **values)

    def scope(self, **values):
        return replace(RuleScope("synthetic-rule", "1", A.id, "synthetic-created-event", "synthetic-occurrence", "preparation"), **values)

    def link(self, kind, before=B, after=A, identity="synthetic-link"):
        return TaskRelation(identity, 1, kind, before, after, "synthetic-user-relation")

    def resolve(self, rule=None, scope=None, **values):
        args = dict(creation=CreationRecord("synthetic-created-event", A.id, "synthetic-occurrence", True), source_type_ref="synthetic-lab-type", source_fields={"preparation_title": "Synthetic preparation"}, template_ref="synthetic-template", template_version="1", defaults={"requiredness": "REQUIRED"}, occurrences={})
        args.update(values)
        return resolve_generation(rule or self.rule(), scope or self.scope(), **args)

    def test_reverse_generation_and_execution_order_are_separate_graphs(self):
        for kind in ("COMPLETION_ORDER", "START_PREREQUISITE"):
            self.assertEqual(check_relationships((self.rule(),), (self.link(kind),), endpoints=ENDPOINTS), ())

    def test_actual_generation_cycle_reports_only_offending_rules(self):
        reverse = self.rule(rule_id="synthetic-reverse", source_type_ref="synthetic-preparation-type", target_type_ref="synthetic-lab-type")
        unrelated = self.rule(rule_id="synthetic-unrelated", source_type_ref="synthetic-x", target_type_ref="synthetic-y")
        issues = check_relationships((unrelated, reverse, self.rule()), (), endpoints=ENDPOINTS)
        self.assertEqual([(item.code, item.identities) for item in issues], [("RECURSIVE_GENERATION", ("synthetic-reverse", "synthetic-rule"))])
        self.assertEqual(issues, check_relationships((self.rule(), reverse, unrelated), (), endpoints=ENDPOINTS))

    def test_recursive_self_generation_and_inactive_rules(self):
        rule = self.rule(target_type_ref="synthetic-lab-type")
        self.assertEqual(check_relationships((rule,), (), endpoints=ENDPOINTS)[0].identities, (rule.rule_id,))
        self.assertEqual(check_relationships((replace(rule, active=False),), (), endpoints=ENDPOINTS), ())

    def test_finite_generation_chain_does_not_require_recursion_limit(self):
        rules = tuple(self.rule(rule_id=f"synthetic-rule-{i}", source_type_ref=f"synthetic-type-{i}", target_type_ref=f"synthetic-type-{i+1}") for i in range(1100))
        self.assertEqual(check_relationships(rules, (), endpoints=frozenset()), ())

    def test_hard_cycle_is_found_across_start_and_completion_event_edges(self):
        links = (self.link("COMPLETION_ORDER", A, B, "synthetic-finish"), self.link("START_PREREQUISITE", B, A, "synthetic-start"))
        issues = check_relationships((), links, endpoints=ENDPOINTS)
        self.assertEqual([(item.code, item.identities) for item in issues], [("CONTRADICTORY_HARD_ORDER", ("synthetic-finish", "synthetic-start"))])
        self.assertEqual(check_relationships((), links[:1], endpoints=ENDPOINTS), ())

    def test_soft_reverse_preference_does_not_block_hard_order(self):
        links = (self.link("START_PREREQUISITE", A, B, "synthetic-hard"), self.link("SOFT_SEQUENCE", B, A, "synthetic-soft"))
        self.assertEqual(check_relationships((), links, endpoints=ENDPOINTS), ())
        executions = {A: ExecutionTimes(A, NOW, NOW + timedelta(minutes=30)), B: ExecutionTimes(B, NOW + timedelta(minutes=30), NOW + timedelta(minutes=60))}
        self.assertEqual(check_execution_order(links, executions), ())

    def test_unresolved_link_endpoint_is_not_silently_removed(self):
        missing = Endpoint("TASK", "synthetic-unknown")
        issue = check_relationships((), (self.link("START_PREREQUISITE", missing),), endpoints=ENDPOINTS)[0]
        self.assertEqual((issue.code, issue.identities), ("UNRESOLVED_ENDPOINT", ("synthetic-link",)))

    def test_stage_membership_has_explicit_accounting_identity(self):
        stage = Endpoint("STAGE", B.id)
        membership = self.link("STAGE_MEMBERSHIP", A, stage)
        endpoints = ENDPOINTS | {stage}
        self.assertEqual(check_relationships((), (membership,), endpoints=endpoints), ())
        second = self.link("STAGE_MEMBERSHIP", B, stage, "synthetic-second-parent")
        self.assertEqual(check_relationships((), (membership, second), endpoints=endpoints)[0].code, "MULTIPLE_STAGE_PARENTS")
        with self.assertRaises(ValueError):
            self.link("STAGE_MEMBERSHIP", A, B)
        # A Task and a stage sharing a text ID remain distinct typed endpoints.
        self.assertNotEqual(stage, B)

    def test_generation_resolves_only_approved_bindings_and_template_version(self):
        self.assertEqual(self.resolve().state, "PROPOSED")
        self.assertEqual(self.resolve().fields, {"title": "Synthetic preparation", "completion": "INCOMPLETE", "disposition": "ACTIVE", "requiredness": "REQUIRED"})
        self.assertEqual(self.resolve(template_version="2").reason, "RULE_SCOPE_MISMATCH")
        self.assertEqual(self.resolve(scope=self.scope(version="2")).reason, "RULE_SCOPE_MISMATCH")
        self.assertEqual(self.resolve(source_type_ref="synthetic-wrong-type").reason, "RULE_SCOPE_MISMATCH")

    def test_external_discovery_or_wrong_creation_event_cannot_generate(self):
        self.assertEqual(self.resolve(creation=CreationRecord("synthetic-created-event", A.id, "synthetic-occurrence", False)).state, "NOT_ELIGIBLE")
        self.assertEqual(self.resolve(creation=CreationRecord("synthetic-wrong-event", A.id, "synthetic-occurrence", True)).reason, "CANONICAL_CREATION_REQUIRED")
        self.assertEqual(self.resolve(rule=self.rule(active=False, acceptance_ref=None)).reason, "RULE_INACTIVE")

    def test_missing_and_invalid_target_facts_stay_pending(self):
        result = self.resolve(source_fields={}, defaults={})
        self.assertEqual((result.state, result.missing_fields, result.fields), ("PENDING", ("requiredness", "title"), None))
        self.assertEqual(self.resolve(defaults={"requiredness": None}).missing_fields, ("requiredness",))
        self.assertEqual(self.resolve(defaults={"requiredness": "MANDATORY"}).reason, "INVALID_MAPPED_FACTS")

    def test_mapping_cannot_infer_completion_or_cancellation(self):
        for field, value in (("completion", "COMPLETE"), ("disposition", "CANCELLED")):
            rule = self.rule(mappings=tuple(literal(field, value) if mapping.target_field == field else mapping for mapping in self.rule().mappings))
            self.assertEqual(self.resolve(rule=rule).reason, "CREATION_CANNOT_INFER_OUTCOME")
        with self.assertRaises(ValueError):
            literal("authority_ref", "synthetic-forgery")

    def test_rule_version_and_retries_do_not_duplicate_created_occurrence(self):
        old = GenerationOccurrence(self.scope(), "SEPARATE_TASK", "CREATED", B.id)
        key = old.scope.generation_key
        scope, rule = self.scope(version="2"), self.rule(version="2")
        self.assertEqual(scope.generation_key, key)
        result = self.resolve(rule=rule, scope=scope, occurrences={key: old})
        self.assertEqual((result.state, result.recorded, result.fields), ("ALREADY_RECORDED", old, None))
        self.assertEqual(self.resolve(occurrences={key: old}).state, "ALREADY_RECORDED")
        self.assertNotEqual(self.scope(target_role="other").generation_key, key)
        self.assertNotEqual(self.scope(occurrence_key="other").generation_key, key)

    def test_occurrence_kind_change_conflicts_instead_of_reinterpreting_work(self):
        old = GenerationOccurrence(self.scope(), "SEPARATE_TASK", "CREATED", B.id)
        self.assertEqual(self.resolve(rule=self.rule(obligation_kind="STAGE"), occurrences={old.scope.generation_key: old}).state, "CONFLICT")
        self.assertEqual(self.resolve(rule=self.rule(obligation_kind="STAGE")).state, "PROPOSED")

    def test_pending_resolution_can_recover_without_creating_a_task(self):
        pending = GenerationOccurrence(self.scope(), "SEPARATE_TASK", "PENDING", missing_fields=("title",))
        result = self.resolve(occurrences={pending.scope.generation_key: pending})
        self.assertEqual(result.state, "PROPOSED")
        self.assertEqual(pending.target_id, None)
        self.assertEqual(pending.state, "PENDING")

    def test_completion_order_allows_early_start_but_start_prerequisite_does_not(self):
        executions = {A: ExecutionTimes(A, NOW, NOW + timedelta(minutes=60)), B: ExecutionTimes(B, NOW, NOW + timedelta(minutes=30))}
        self.assertEqual(check_execution_order((self.link("COMPLETION_ORDER"),), executions), ())
        self.assertEqual(check_execution_order((self.link("START_PREREQUISITE"),), executions)[0].code, "ORDER_VIOLATION")

    def test_real_out_of_order_completion_is_preserved_and_reported(self):
        executions = {A: ExecutionTimes(A, NOW, NOW + timedelta(minutes=30)), B: ExecutionTimes(B, NOW, NOW + timedelta(minutes=60))}
        before = deepcopy(executions)
        self.assertEqual(check_execution_order((self.link("COMPLETION_ORDER"),), executions)[0].code, "ORDER_VIOLATION")
        self.assertEqual(executions, before)
        self.assertEqual(check_execution_order((self.link("COMPLETION_ORDER"),), {A: executions[A]})[0].code, "ORDER_EVIDENCE_MISSING")

    def test_mapped_proposal_still_needs_independent_authority(self):
        result, scope = self.resolve(), self.scope()
        patch = change(B.id, None, "CREATE_TASK", result.fields)
        command = Command("synthetic-command", "synthetic-system", "RELATIONSHIP_RULE", "synthetic-grant", (patch,), scope)
        caller = CallerIdentity(command.principal_id, command.origin, True)
        tasks = {A.id: TaskState(A.id, 1)}
        creations = {scope.creation_event_ref: CreationRecord(scope.creation_event_ref, A.id, scope.occurrence_key, True)}
        args = dict(caller=caller, tasks=tasks, now=NOW, creations=creations)
        self.assertFalse(authorize(command, grants={}, **args).allowed)
        grant = AuthorityGrant(command.authority_ref, command.principal_id, command.origin, command.command_id, command.changes, "synthetic-resolved-user-rule", NOW, rule_scope=scope, essential_fields=frozenset(self.rule().essential_fields))
        self.assertTrue(authorize(command, grants={grant.grant_id: grant}, **args).allowed)
        self.assertEqual(tasks, {A.id: TaskState(A.id, 1)})

    def test_records_are_structurally_valid_and_resolved_fields_are_copies(self):
        records = (("relationship-rule", self.rule().as_record()), ("task-relation", self.link("COMPLETION_ORDER").as_record()), ("generation-occurrence", GenerationOccurrence(self.scope(), "SEPARATE_TASK", "CREATED", B.id).as_record()))
        for contract, record in records:
            self.assertEqual(validate_contract(contract, record), (), contract)
        result = self.resolve()
        fields = result.fields
        fields["title"] = "Changed copy"
        self.assertEqual(result.fields["title"], "Synthetic preparation")

    def test_duplicate_scope_and_invalid_typed_records_are_rejected(self):
        with self.assertRaises(ValueError):
            check_relationships((self.rule(), self.rule()), (), endpoints=ENDPOINTS)
        with self.assertRaises(ValueError):
            self.rule(mappings=self.rule().mappings + (literal("title", "Duplicate"),))
        with self.assertRaises(ValueError):
            self.rule(active=True, acceptance_ref=None)
        with self.assertRaises(ValueError):
            GenerationOccurrence(self.scope(), "SEPARATE_TASK", "PENDING")
        with self.assertRaises(ValueError):
            ExecutionTimes(A, NOW + timedelta(minutes=1), NOW)
        with self.assertRaises(ValueError):
            literal("importance", float("nan"))

    def test_schema_cases(self):
        fixture = load_json(ROOT / "tests/fixtures/relationships/cases.json")
        self.assertIs(fixture["synthetic"], True)
        for case in fixture["cases"]:
            with self.subTest(case=case["id"]):
                self.assertEqual(not validate_contract(case["contract"], case["payload"]), case["valid"])


if __name__ == "__main__":
    unittest.main()
