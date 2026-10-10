"""Version safety, conservative evolution and independently expected workflows."""
from copy import deepcopy
from hashlib import sha256
import json
import unittest

from jsonschema import Draft202012Validator
from jsonschema.exceptions import SchemaError

from src.adapters.contract_json import ContractJSONCodec
from src.application.contract_versions import assess_evolution, canonical_hash, semantic_schema
from src.domain.authorization import CallerIdentity, Command, TaskState, authorize, change
from tests.contract_scenarios import NOW, Wire, core, effort, estimate, run_scenario
from tools.check_contract_registry import REGISTRY, trusted_schemas, validate_registry
from tools.check_contracts import ROOT, SCHEMAS
from tools.check_cross_contracts import FIXTURE, check_cases
from tools.validate_task_core import load_json


def raw(value):
    return json.dumps(value, ensure_ascii=False, allow_nan=False).encode()


class ContractVersionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.schemas = trusted_schemas()
        cls.codec = ContractJSONCodec(cls.schemas)

    def test_all_existing_shape_expectations_survive_version_admission(self):
        count = 0
        for path in sorted((ROOT / "tests/fixtures").glob("*/cases.json")):
            if path.parent.name == "task_aggregate": continue  # Separate new-contract evidence.
            bundle = load_json(path)
            for case in bundle["cases"]:
                name = case.get("contract", "task-core")
                with self.subTest(case=case["id"]):
                    original = raw(case["payload"])
                    admitted = self.codec.admit(name, original)
                    self.assertEqual(admitted.status == "SUPPORTED_SHAPE", case["valid"])
                    self.assertEqual(admitted.raw_bytes, original)
                    self.assertEqual(admitted.content_hash, sha256(original).hexdigest())
                    if case["valid"]: self.assertEqual(admitted.payload, case["payload"])
                count += 1
        self.assertEqual(count, 236)

    def test_versions_are_exact_without_guessing_or_defaulting(self):
        for version, reason in [("0.0.1", "UNSUPPORTED_VERSION"), ("1.0.0", "UNSUPPORTED_VERSION"), ("0.1.0", "UNSUPPORTED_VERSION"), ("", "UNSUPPORTED_VERSION"), (None, "VERSION_REQUIRED"), (1, "VERSION_REQUIRED")]:
            with self.subTest(version=version):
                data = dict(core("work"), schema_version=version)
                result = self.codec.admit("task-core", raw(data))
                self.assertEqual(result.reason, reason)
                self.assertEqual(result.raw_bytes, raw(data))
                with self.assertRaises(ValueError): _ = result.payload
        data = core("work"); del data["schema_version"]
        self.assertEqual(self.codec.admit("task-core", raw(data)).reason, "VERSION_REQUIRED")

    def test_unknown_contract_and_legacy_profile_are_retained(self):
        original = b'{"profile_version":"0.2.0-draft","personal_fact":"secret"}'
        result = self.codec.admit("course-profile", original)
        self.assertEqual(result.reason, "UNKNOWN_CONTRACT")
        self.assertEqual(result.raw_bytes, original)
        self.assertNotIn("secret", result.reason)
        self.assertNotIn("secret", repr(result.issues))

    def test_malformed_input_has_no_silent_repair_or_value_diagnostic(self):
        for original in (b'\xff', b'{"secret": NaN}', b'{"secret": Infinity}', b'{"secret": 1e999}', b'{"secret": 1, "secret": 2}', b'{', b'[' * 2000 + b'}'):
            with self.subTest(original=original[:30]):
                result = self.codec.admit("task-core", original)
                self.assertEqual(result.reason, "MALFORMED_JSON")
                self.assertEqual(result.raw_bytes, original)
                self.assertEqual(result.issues, ())
        self.assertEqual(self.codec.admit("task-core", b"[]").reason, "OBJECT_REQUIRED")
        self.assertIn(self.codec.admit("task-core", b'[' * 2000 + b']' * 2000).reason, ("OBJECT_REQUIRED", "MALFORMED_JSON"))
        original = b" " * 262145
        self.assertEqual(self.codec.admit("task-core", original).reason, "INPUT_TOO_LARGE")

    def test_added_fields_fail_without_discarding_original(self):
        data = dict(core("work"), unknown_field="secret-value")
        result = self.codec.admit("task-core", raw(data))
        self.assertEqual(result.reason, "INVALID_SHAPE")
        self.assertEqual(result.raw_bytes, raw(data))
        self.assertNotIn("secret-value", repr(result.issues))

    def test_supported_shape_is_not_write_authority(self):
        command = Command("external", "external", "EXTERNAL", "untrusted-claimed-grant", (change("work", 1, "UPDATE_TASK", {"user_remaining_seconds": 10}),))
        admission = self.codec.admit("command", raw(command.as_record()))
        self.assertEqual(admission.status, "SUPPORTED_SHAPE")
        with self.assertRaises(TypeError): bool(admission)
        decision = authorize(command, caller=CallerIdentity("external", "EXTERNAL", True), grants={}, tasks={"work": TaskState("work", 1)}, now=NOW)
        self.assertFalse(decision.allowed)

    def test_codec_and_payload_own_detached_snapshots(self):
        schemas = deepcopy(self.schemas)
        codec = ContractJSONCodec(schemas)
        schemas["task-core"]["properties"]["schema_version"]["const"] = "changed"
        result = codec.admit("task-core", raw(core("work")))
        payload = result.payload; payload["title"] = "changed"
        self.assertEqual(result.payload["title"], "Synthetic work")
        self.assertEqual(result.status, "SUPPORTED_SHAPE")

    def test_offline_codec_refuses_remote_reference_resolution(self):
        schema = deepcopy(self.schemas["task-core"])
        schema["properties"]["title"] = {"$ref": "https://example.invalid/external-schema"}
        with self.assertRaises(ValueError): ContractJSONCodec({"task-core": schema})

    def test_literal_reference_keys_are_instance_data(self):
        schema = {"type": "object", "properties": {"schema_version": {"const": "1"}, "literal": {"const": {"$ref": "https://example.invalid/data"}}}, "required": ["schema_version", "literal"], "additionalProperties": False}
        codec = ContractJSONCodec({"literal": schema})
        data = {"schema_version": "1", "literal": {"$ref": "https://example.invalid/data"}}
        self.assertEqual(codec.admit("literal", raw(data)).payload, data)

    def test_json_and_hash_have_explicit_input_requirements(self):
        for args in [(None, b"{}"), ("task-core", "{}"), ("task-core", bytearray(b"{}"))]:
            with self.assertRaises(ValueError): self.codec.admit(*args)
        self.assertEqual(canonical_hash({"b": 2, "a": 1}), canonical_hash({"a": 1, "b": 2}))
        with self.assertRaises(ValueError): canonical_hash({"x": float("nan")})

    def test_registry_resolves_real_schema_and_owner_artifacts(self):
        registry = load_json(REGISTRY)
        self.assertEqual(validate_registry(registry), [])
        self.assertEqual(len(registry["contracts"]), len(SCHEMAS))
        for row in registry["contracts"]:
            self.assertEqual(row["supported_versions"], ["0.1.0-draft"])
            self.assertEqual(row["adapters"], [])

    def test_registry_drift_requires_explicit_review(self):
        original = load_json(REGISTRY)
        checks = [("schema_hash", "changed", "REGISTRY_SCHEMA_DRIFT"), ("path", "missing.schema.json", "REGISTRY_SCHEMA_DRIFT"), ("supported_versions", ["future"], "REGISTRY_VERSION_OR_ADAPTER_DRIFT"), ("adapters", ["invented-converter"], "REGISTRY_VERSION_OR_ADAPTER_DRIFT"), ("database_owners", [], "REGISTRY_OWNERSHIP_DRIFT"), ("consumers", ["missing.py"], "REGISTRY_CONSUMER_MISSING")]
        for field, value, expected in checks:
            with self.subTest(field=field):
                changed = deepcopy(original);changed["contracts"][0][field] = value
                self.assertIn(expected, validate_registry(changed))
        changed = deepcopy(original); changed["contracts"][0] = changed["contracts"][1]
        self.assertIn("REGISTRY_COVERAGE_MISMATCH", validate_registry(changed))
        changed = deepcopy(original);changed["policy"]["unknown_version"] = "ACCEPT"
        self.assertIn("REGISTRY_POLICY_MISMATCH", validate_registry(changed))


class EvolutionTests(unittest.TestCase):
    def setUp(self):
        self.old = {"$schema": "https://json-schema.org/draft/2020-12/schema", "$id": "urn:old", "type": "object", "properties": {"name": {"type": "string"}}, "required": ["name"], "additionalProperties": False}
        self.consumers = ("synthetic-producer", "synthetic-strict-consumer")

    def assess(self, new, old=None):
        return assess_evolution(self.old if old is None else old, new, consumers=self.consumers)

    def test_optional_addition_breaks_strict_old_consumers(self):
        new = deepcopy(self.old);new["properties"]["note"] = {"type": "string"}
        result = self.assess(new)
        self.assertEqual(result.classification, "OPTIONAL_FIELD_ADDED_STRICT_CONSUMER_BREAK")
        self.assertTrue(result.old_input_accepted_by_new)
        self.assertFalse(result.new_input_accepted_by_old)
        self.assertEqual(result.invalidated_consumers, self.consumers)
        self.assertTrue(Draft202012Validator(new).is_valid({"name": "old"}))
        self.assertFalse(Draft202012Validator(self.old).is_valid({"name": "new", "note": "value"}))

    def test_required_addition_breaks_existing_producers(self):
        old = deepcopy(self.old);old["properties"]["note"] = {"type": "string"}
        new = deepcopy(old);new["required"].append("note")
        result = self.assess(new, old)
        self.assertEqual(result.classification, "REQUIRED_FIELD_ADDED")
        self.assertFalse(result.old_input_accepted_by_new)
        self.assertTrue(result.new_input_accepted_by_old)
        self.assertTrue(Draft202012Validator(old).is_valid({"name": "old"}))
        self.assertFalse(Draft202012Validator(new).is_valid({"name": "old"}))

    def test_annotation_change_does_not_drop_instance_map_keys(self):
        new = deepcopy(self.old);new["description"] = "Updated prose"
        self.assertEqual(self.assess(new).classification, "UNCHANGED_VALIDATION")
        old = {"const": {"description": "one"}}
        new = {"const": {"description": "two"}}
        self.assertEqual(self.assess(new, old).classification, "REVIEW_REQUIRED")
        props = {"type": "object", "properties": {"description": {"type": "string", "description": "prose"}}}
        self.assertIn("description", semantic_schema(props)["properties"])
        self.assertNotIn("description", semantic_schema(props)["properties"]["description"])

    def test_default_is_not_silently_treated_as_prose(self):
        old = deepcopy(self.old);old["properties"]["name"]["default"] = "one"
        new = deepcopy(old);new["properties"]["name"]["default"] = "two"
        self.assertEqual(self.assess(new, old).classification, "REVIEW_REQUIRED")

    def test_id_and_reference_changes_require_affected_evidence(self):
        new = deepcopy(self.old);new["$id"] = "urn:new"
        result = self.assess(new)
        self.assertEqual(result.classification, "IDENTITY_CHANGED")
        self.assertTrue(result.version_bump_required)
        old = deepcopy(self.old);old["properties"]["name"] = {"$ref": "relative.json"}
        new = deepcopy(old);new["$id"] = "urn:new"
        self.assertEqual(self.assess(new, old).classification, "REVIEW_REQUIRED")

    def test_complex_or_unsatisfiable_addition_is_not_claimed_proven(self):
        for addition in (False, {"type": "string", "maxLength": -0}, {"$ref": "#/$defs/item"}):
            new = deepcopy(self.old);new["properties"]["extra"] = addition
            result = self.assess(new)
            self.assertEqual(result.classification, "REVIEW_REQUIRED")
            self.assertIsNone(result.new_input_accepted_by_old)
        new = deepcopy(self.old);new["if"] = {"required": ["name"]}
        self.assertEqual(self.assess(new).classification, "REVIEW_REQUIRED")

    def test_invalid_schema_or_missing_consumer_is_not_evolution_evidence(self):
        with self.assertRaises(ValueError): assess_evolution(self.old, self.old, consumers=())
        with self.assertRaises(SchemaError): self.assess({"required": "not-an-array"})


class CrossContractTests(unittest.TestCase):
    def test_five_workflows_match_independent_expectations(self):
        bundle = load_json(FIXTURE)
        results = check_cases(bundle)
        self.assertEqual(len(results), 5)
        self.assertEqual(sum(row["actual"]["validated_records"] for row in results), 31)
        for row in results:
            with self.subTest(scenario=row["id"]): self.assertTrue(row["matched"])

    def test_altered_expectation_is_detected(self):
        bundle = load_json(FIXTURE);bundle["cases"][0]["expected"]["canonical_user_seconds"] = 300
        results = check_cases(bundle)
        self.assertFalse(results[0]["matched"])
        self.assertTrue(all(row["matched"] for row in results[1:]))

    def test_missing_or_duplicate_workflow_is_rejected(self):
        bundle = load_json(FIXTURE);bundle["cases"][0] = bundle["cases"][1]
        with self.assertRaises(ValueError): check_cases(bundle)
        bundle = load_json(FIXTURE);bundle["synthetic"] = False
        with self.assertRaises(ValueError): check_cases(bundle)

    def test_task_effort_snapshot_mismatch_is_detected(self):
        wire = Wire();wire.check("task-core", dict(core("work"), revision=2))
        wire.check("effort", effort("work", estimate("work", 1200)))
        with self.assertRaises(AssertionError): wire.finish()


if __name__ == "__main__": unittest.main()
