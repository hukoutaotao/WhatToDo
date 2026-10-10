from copy import deepcopy
from dataclasses import FrozenInstanceError, replace
from datetime import datetime, timedelta, timezone
from hashlib import sha256
import unittest

from src.domain.provenance import capture_source, ingest_candidate, make_candidate, mark_source_deleted
from tools.check_contracts import validate_contract
from tools.validate_task_core import ROOT, load_json


NOW = datetime(2026, 1, 1, tzinfo=timezone.utc)


class ProvenanceTests(unittest.TestCase):
    def source(self, **changes):
        args = dict(provider="synthetic-provider", scope_ref="synthetic-scope", external_id="assignment-001", raw_bytes=b"synthetic submission", captured_at=NOW, source_type="LEARNING_PLATFORM", external_revision="v1")
        args.update(changes)
        return capture_source(**args)

    def proposal(self, source=None, **changes):
        args = dict(parser_version="synthetic-parser-1", action="COMPLETE_TASK", proposed_fields={"completion": "COMPLETE"}, confidence=1, target_task_id="synthetic-task", target_revision=3)
        args.update(changes)
        return make_candidate(source or self.source(), **args)

    def test_exact_bytes_hash_and_scope_isolation(self):
        first = self.source()
        self.assertEqual(first.content_hash, sha256(b"synthetic submission").hexdigest())
        self.assertNotEqual(first.source_id, self.source(scope_ref="synthetic-second-scope").source_id)
        self.assertNotEqual(first.content_hash, self.source(raw_bytes=b"synthetic submission\n").content_hash)
        self.assertEqual(first.source_id, self.source(raw_bytes=b"changed").source_id)
        self.assertNotEqual(first.record_id, self.source(raw_bytes=b"changed").record_id)

    def test_high_confidence_is_pending_not_task_completion(self):
        task = {"completion": "INCOMPLETE", "revision": 3}
        original = deepcopy(task)
        candidate = self.proposal()
        self.assertEqual(candidate.review_state, "PENDING")
        self.assertIsNone(candidate.authority_ref)
        self.assertEqual(candidate.proposed_fields["completion"], "COMPLETE")
        self.assertEqual(task, original)
        self.assertEqual(validate_contract("candidate", candidate.as_record()), ())

    def test_replay_preserves_reviewed_history(self):
        candidate = self.proposal()
        reviewed = replace(candidate, review_state="CONFIRMED", authority_ref="synthetic-user-command", reviewed_at=NOW + timedelta(hours=1), canonical_task_id="synthetic-task")
        recaptured = self.proposal(self.source(captured_at=NOW + timedelta(hours=2)))
        self.assertEqual(recaptured.candidate_id, candidate.candidate_id)
        self.assertEqual(ingest_candidate((reviewed,), recaptured), (reviewed,))
        self.assertEqual(reviewed.review_state, "CONFIRMED")
        with self.assertRaises(ValueError):
            ingest_candidate((), reviewed)

    def test_conflicting_same_parser_replay_is_not_silent(self):
        candidate = self.proposal()
        conflict = self.proposal(proposed_fields={"completion": "COMPLETE", "remaining_seconds": 0})
        self.assertEqual(candidate.candidate_id, conflict.candidate_id)
        with self.assertRaises(ValueError):
            ingest_candidate((candidate,), conflict)

    def test_source_parser_and_target_revision_changes_are_distinct(self):
        candidate = self.proposal()
        variants = (self.proposal(self.source(raw_bytes=b"changed")), self.proposal(parser_version="synthetic-parser-2"), self.proposal(target_revision=4))
        for changed in variants:
            with self.subTest(candidate_id=changed.candidate_id):
                self.assertNotEqual(candidate.candidate_id, changed.candidate_id)
                self.assertEqual(len(ingest_candidate((candidate,), changed)), 2)

    def test_tombstone_does_not_cancel_task_or_candidate(self):
        source = self.source()
        candidate = self.proposal(source)
        task = {"disposition": "ACTIVE", "completion": "INCOMPLETE"}
        tombstone = mark_source_deleted(source, NOW + timedelta(hours=1))
        self.assertEqual(source.state, "PRESENT")
        self.assertEqual(tombstone.state, "DELETED")
        self.assertEqual(tombstone.content_hash, source.content_hash)
        self.assertEqual(candidate.review_state, "PENDING")
        self.assertEqual(task["disposition"], "ACTIVE")
        self.assertEqual(mark_source_deleted(tombstone, tombstone.deleted_at), tombstone)
        with self.assertRaises(ValueError):
            self.proposal(tombstone)

    def test_external_control_fields_cannot_be_facts(self):
        for key in ("authority_ref", "principal", "acceptance", "review", "status"):
            with self.subTest(key=key), self.assertRaises(ValueError):
                self.proposal(proposed_fields={"completion": "COMPLETE", key: "USER"})

    def test_nested_facts_and_sources_are_immutable(self):
        facts = {"completion": "COMPLETE"}
        candidate = self.proposal(proposed_fields=facts)
        facts["completion"] = "INCOMPLETE"
        copy = candidate.proposed_fields
        copy["completion"] = "INCOMPLETE"
        self.assertEqual(candidate.proposed_fields["completion"], "COMPLETE")
        with self.assertRaises(FrozenInstanceError):
            candidate.review_state = "CONFIRMED"

    def test_unknown_mapping_stays_pending_and_new_provider_is_generic(self):
        candidate = self.proposal(self.source(provider="synthetic-new-provider", source_type="OTHER"), target_task_id=None, target_revision=None)
        self.assertIsNone(candidate.target_task_id)
        self.assertEqual(candidate.review_state, "PENDING")
        self.assertEqual(validate_contract("candidate", candidate.as_record()), ())

    def test_invalid_metadata_never_creates_trusted_state(self):
        for confidence in (True, -1, 1.1, float("nan"), float("inf")):
            with self.subTest(confidence=confidence), self.assertRaises(ValueError):
                self.proposal(confidence=confidence)
        with self.assertRaises(ValueError):
            self.source(captured_at=datetime(2026, 1, 1))
        with self.assertRaises(ValueError):
            mark_source_deleted(self.source(), NOW - timedelta(hours=1))

    def test_schema_cases(self):
        fixture = load_json(ROOT / "tests/fixtures/sources/cases.json")
        self.assertIs(fixture["synthetic"], True)
        for case in fixture["cases"]:
            with self.subTest(case=case["id"]):
                self.assertEqual(not validate_contract(case["contract"], case["payload"]), case["valid"])

    def test_factory_source_records_match_contract(self):
        source = self.source()
        for record in (source, mark_source_deleted(source, NOW + timedelta(hours=1))):
            with self.subTest(state=record.state):
                self.assertEqual(validate_contract("source", record.as_record()), ())


if __name__ == "__main__":
    unittest.main()
