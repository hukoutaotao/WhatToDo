"""Whole-Task facts retain their meanings before any authority/persistence path."""
from copy import deepcopy
from datetime import timedelta
from fractions import Fraction
import json
import unittest

from src.adapters.contract_json import ContractJSONCodec
from src.adapters.fakes import FakeClock, FakeStateStore
from src.application.ports import AggregateKey, CommitRequest, RecordWrite, RequestContext
from src.application.task_aggregate import admit_task
from src.domain.task_aggregate import TaskAggregate
from tests.contract_scenarios import NOW, USER
from tools.check_contract_registry import trusted_schemas
from tools.check_database_design import DESIGN, OWNERSHIP, validate_design, validate_ownership
from tools.render_task_aggregate_schema import TARGET, render
from tools.validate_task_core import ROOT, load_json
from src.application.contract_versions import canonical_hash


FIXTURE = ROOT / "tests/fixtures/task_aggregate/cases.json"


def encoded(record): return json.dumps(record, ensure_ascii=False, allow_nan=False).encode()


class TaskAggregateTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.cases = load_json(FIXTURE)["cases"]
        cls.codec = ContractJSONCodec(trusted_schemas())

    def example(self, name="aggregate-unknown-facts"):
        return deepcopy(next(c["payload"] for c in self.cases if c["id"] == name))

    def admit(self, value): return admit_task(self.codec, encoded(value))

    def test_shape_examples_and_valid_semantic_roundtrips(self):
        self.assertEqual(len(self.cases), 22)
        for case in self.cases:
            with self.subTest(case=case["id"]):
                data = encoded(case["payload"]);wire = self.codec.admit("task-aggregate", data)
                self.assertEqual(wire.status == "SUPPORTED_SHAPE", case["valid"])
                self.assertEqual(wire.raw_bytes, data)
                admitted = self.admit(case["payload"])
                self.assertEqual(admitted.status == "CONSISTENT_FACTS", case["valid"])
                if case["valid"]: self.assertEqual(admitted.aggregate.as_record(), case["payload"])

    def test_independently_valid_components_cannot_disagree_in_scope(self):
        for field, value in [("task_id", "other"), ("task_revision", 2), ("completion", "COMPLETE"), ("disposition", "CANCELLED")]:
            with self.subTest(field=field):
                data = self.example();data["effort"][field] = value
                if field == "completion": data["effort"]["user_remaining"]["seconds"] = 0
                result = self.admit(data)
                self.assertEqual(result.wire.status, "SUPPORTED_SHAPE")
                self.assertEqual(result.status, "REJECTED")
                self.assertIn("CORE_EFFORT_SCOPE", [i.constraint for i in result.issues])
                self.assertIsNone(result.aggregate)

    def test_stage_titles_and_effort_have_identical_membership(self):
        for mutate in [lambda d:d["stage_details"].pop(), lambda d:d["stage_details"].append(deepcopy(d["stage_details"][0])), lambda d:d["effort"]["stages"].append(deepcopy(d["effort"]["stages"][0]))]:
            data = self.example("aggregate-stages-retain-historical-completed-stage-u");mutate(data)
            result = self.admit(data)
            self.assertEqual(result.wire.status, "SUPPORTED_SHAPE")
            self.assertEqual(result.status, "REJECTED")

    def test_known_zero_and_unknown_are_distinct(self):
        data = self.example();data["effort"]["user_remaining"] = None
        aggregate = self.admit(data).aggregate
        self.assertIsNone(aggregate.budget(at=NOW).seconds)
        self.assertEqual(aggregate.release_due_window, "UNKNOWN")
        data["effort"]["user_remaining"] = self.example()["effort"]["user_remaining"]
        data["effort"]["user_remaining"]["seconds"] = 0
        self.assertEqual(self.admit(data).aggregate.budget(at=NOW).seconds, 0)

    def test_total_actual_and_model_are_not_subtracted_from_u(self):
        data = self.example("aggregate-explicit-facts-and-original-total-below-current-u")
        data["effort"]["prediction"] = dict(seconds=300,prediction_id="derived",model_ref=dict(id="model",version="1"),task_revision=1,computed_at=NOW.isoformat(),valid_until=(NOW+timedelta(hours=1)).isoformat(),valid=True,applicable=True)
        result = self.admit(data);budget = result.aggregate.budget(at=NOW)
        self.assertEqual((budget.seconds,budget.source),(300,"MODEL"))
        self.assertEqual(result.aggregate.as_record()["effort"]["user_remaining"]["seconds"],2400)
        self.assertEqual(result.aggregate.as_record()["work"]["total_estimate"]["seconds"],1800)
        data["effort"]["prediction"]["task_revision"] = 9
        retained = self.admit(data).aggregate
        self.assertEqual(retained.as_record()["effort"]["prediction"]["task_revision"],9)
        self.assertEqual(retained.budget(at=NOW).source,"USER_FALLBACK")

    def test_completed_stage_old_estimate_does_not_add_to_parent(self):
        data = self.example("aggregate-stages-retain-historical-completed-stage-u")
        aggregate = self.admit(data).aggregate
        partition = aggregate.stage_partition(at=NOW)
        self.assertEqual(len(partition.allocations),1)
        self.assertEqual(partition.allocations[0].seconds,Fraction(2400))
        self.assertEqual(aggregate.as_record()["effort"]["stages"][1]["user_remaining"]["seconds"],600)

    def test_history_lifecycle_is_not_completed_or_zeroed_by_expiry(self):
        for name in ("aggregate-expired-retains-positive-u","aggregate-cancelled-retains-effort"):
            aggregate = self.admit(self.example(name)).aggregate
            self.assertEqual(aggregate.as_record()["core"]["completion"],"INCOMPLETE")
            self.assertEqual(aggregate.as_record()["effort"]["user_remaining"]["seconds"],2400)
            self.assertEqual(aggregate.budget(at=NOW).source,"NOT_ACTIVE")
            self.assertIsNone(aggregate.budget(at=NOW).seconds)

    def test_incomplete_work_cannot_have_current_completion_timestamp(self):
        data = self.example();data["timing"]["completed_at"] = NOW.isoformat()
        result = self.admit(data)
        self.assertEqual(result.wire.status,"SUPPORTED_SHAPE")
        self.assertEqual(result.status,"REJECTED")
        complete = self.example("aggregate-complete-with-unknown-historical-completion-time")
        self.assertIsNone(self.admit(complete).aggregate.as_record()["timing"]["completed_at"])

    def test_time_source_offsets_and_precision_are_preserved(self):
        data = self.example("aggregate-explicit-facts-and-original-total-below-current-u")
        self.assertEqual(self.admit(data).aggregate.as_record(),data)
        data["timing"]["release"]["instant"] = "2026-01-01T01:00:00Z"
        self.assertEqual(self.admit(data).status,"REJECTED")
        data = self.example();data["effort"]["user_remaining"]["observed_at"] = "2025-12-31T00:00:00.0000001Z"
        result = self.admit(data)
        self.assertEqual(result.wire.status,"SUPPORTED_SHAPE")
        self.assertEqual(result.status,"REJECTED")

    def test_normalized_deadline_cannot_lose_original_source_instant(self):
        data = self.example("aggregate-explicit-facts-and-original-total-below-current-u")
        due = data["timing"]["deadline"]["value"]
        due.update(input_kind="EXPLICIT_INSTANT",original_value="2026-01-03T00:00:00Z",default_policy_ref=None)
        result = self.admit(data)
        self.assertEqual(result.wire.status,"SUPPORTED_SHAPE")
        self.assertEqual(result.status,"REJECTED")

    def test_reversed_or_zero_windows_are_retained_without_safe_claim(self):
        data = self.example("aggregate-explicit-facts-and-original-total-below-current-u")
        for timestamp, state in [("2026-01-04T00:00:00Z","REVERSED"),(data["timing"]["deadline"]["value"]["instant"],"ZERO_WIDTH")]:
            data["timing"]["release"].update(instant=timestamp,original_value=timestamp)
            admitted = self.admit(data)
            self.assertEqual(admitted.status,"CONSISTENT_FACTS")
            self.assertEqual(admitted.aggregate.release_due_window,state)
            self.assertEqual(admitted.aggregate.as_record(),data)

    def test_missing_duplicate_or_self_provenance_remains_rejected(self):
        for items in [[dict(field="/core/not-present",source_ref="secret-source")],[dict(field="/provenance/0",source_ref="secret-source")],[dict(field="/core/title",source_ref="a"),dict(field="/core/title",source_ref="b")],[dict(field="/core/~2bad",source_ref="secret-source")]]:
            data = self.example();data["provenance"] = items
            result = self.admit(data)
            self.assertEqual(result.status,"REJECTED")
            self.assertNotIn("secret-source",repr(result.issues))

    def test_estimate_chronology_and_integer_representation_fail_explicitly(self):
        data = self.example();data["effort"]["user_remaining"]["verified_at"] = "2025-12-30T00:00:00Z"
        self.assertEqual(self.admit(data).status,"REJECTED")
        for change in [lambda d:d["core"].update(revision=1.0),lambda d:d["work"].update(minimum_session_seconds=1200.0)]:
            data = self.example();change(data);result = self.admit(data)
            self.assertEqual(result.wire.status,"SUPPORTED_SHAPE")
            self.assertEqual(result.status,"REJECTED")

    def test_admitted_snapshot_is_immutable_and_does_not_issue_a_permit(self):
        data = self.example();result = self.admit(data);snapshot = result.aggregate.as_record()
        snapshot["core"]["title"] = "changed"
        self.assertEqual(result.aggregate.as_record(),data)
        with self.assertRaises(TypeError): bool(result)
        store = FakeStateStore(clock=FakeClock(NOW))
        request = CommitRequest(RequestContext("untrusted-write","correlation"),USER.principal_id,1,(RecordWrite(AggregateKey("TASK","aggregate-work"),None,json.dumps(data)),),"audit","source")
        outcome = store.commit(request,caller=USER,permit_ref="untrusted-reference")
        self.assertEqual(outcome.code,"EXACT_ACTIVE_PERMIT_REQUIRED")
        snapshot = store.snapshot(RequestContext("read","read")).value
        self.assertEqual(snapshot.records,())
        self.assertEqual(snapshot.audit,())

    def test_original_contracts_and_native_checkpoint_are_preserved(self):
        old = load_json(ROOT / "reports/acceptance/M2-17a-registry.json")
        self.assertEqual(len(old["contracts"]),29)
        for row in old["contracts"]:
            self.assertEqual(canonical_hash(load_json(ROOT / row["path"])),row["schema_hash"])
        self.assertEqual(TARGET.read_text(encoding="utf-8"),render())

    def test_relational_owners_are_present_and_append_only(self):
        model, owner = load_json(DESIGN),load_json(OWNERSHIP)
        self.assertEqual(validate_design(model),[])
        self.assertEqual(validate_ownership(owner,model),[])
        self.assertEqual(len(model["tables"]),51)
        self.assertEqual(sum(len(t["foreign_keys"]) for t in model["tables"]),130)
        for name in ("task_details_revision","task_field_provenance"):
            self.assertTrue(next(t for t in model["tables"] if t["name"]==name)["immutable"])

    def test_relational_scope_and_estimate_guards_cannot_be_removed(self):
        original = load_json(DESIGN)
        for name in ("task_details_revision","task_field_provenance"):
            model = deepcopy(original);table = next(t for t in model["tables"] if t["name"]==name)
            table["foreign_keys"] = []
            self.assertIn("semantic.binding."+name,validate_design(model))
        model = deepcopy(original);table = next(t for t in model["tables"] if t["name"]=="task_details_revision")
        table["checks"] = [c for c in table["checks"] if c["name"]!="total_binding"]
        self.assertIn("semantic.total_estimate_binding",validate_design(model))


if __name__ == "__main__": unittest.main()
