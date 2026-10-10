from copy import deepcopy
from dataclasses import replace
from datetime import datetime, timedelta, timezone
import unittest

from src.domain.authorization import (
    AuthorityGrant, CallerIdentity, Command, CreationRecord, NoticeEvidence,
    RuleScope, TaskState, authorize, change,
)
from tools.check_contracts import validate_contract
from tools.validate_task_core import ROOT, load_json


NOW = datetime(2026, 1, 1, 12, tzinfo=timezone.utc)


class AuthorizationTests(unittest.TestCase):
    def user(self, fields=None):
        patch = change("synthetic-task", 3, "UPDATE_TASK", fields or {"importance": 4})
        command = Command("synthetic-command", "synthetic-user", "USER_COMMAND", "synthetic-authority", (patch,))
        grant = AuthorityGrant(command.authority_ref, command.principal_id, command.origin, command.command_id, command.changes, "synthetic-explicit-user-statement", NOW - timedelta(minutes=1))
        return command, grant, CallerIdentity(command.principal_id, command.origin, True)

    def evaluate(self, command, grant, caller, **options):
        args = dict(caller=caller, grants={grant.grant_id: grant}, tasks={"synthetic-task": TaskState("synthetic-task", 3)}, now=NOW)
        args.update(options)
        return authorize(command, **args)

    def rule(self, fields=None):
        scope = RuleScope("synthetic-rule", "1", "synthetic-source-task", "synthetic-created-event", "synthetic-occurrence", "preparation")
        patch = change("synthetic-generated-task", None, "CREATE_TASK", fields or {"title": "Synthetic preparation", "completion": "INCOMPLETE"})
        command = Command("synthetic-rule-command", "synthetic-system", "RELATIONSHIP_RULE", "synthetic-rule-authority", (patch,), scope)
        grant = AuthorityGrant(command.authority_ref, command.principal_id, command.origin, command.command_id, command.changes, "synthetic-approved-rule", NOW - timedelta(minutes=1), rule_scope=scope, essential_fields=frozenset({"title"}))
        caller = CallerIdentity(command.principal_id, command.origin, True)
        tasks = {scope.source_task_id: TaskState(scope.source_task_id, 8, completion="COMPLETE")}
        creations = {scope.creation_event_ref: CreationRecord(scope.creation_event_ref, scope.source_task_id, scope.occurrence_key, True)}
        return command, grant, caller, tasks, creations

    def expiry(self):
        patch = change("synthetic-preview", 3, "EXPIRE_TASK", {"disposition": "EXPIRED", "expiration_notice_ref": "synthetic-delivery"})
        command = Command("synthetic-expiry-command", "synthetic-system", "EXPIRATION_PROCESS", "synthetic-expiry-authority", (patch,))
        grant = AuthorityGrant(command.authority_ref, command.principal_id, command.origin, command.command_id, command.changes, "synthetic-accepted-D073-policy", NOW - timedelta(minutes=1))
        caller = CallerIdentity(command.principal_id, command.origin, True)
        state = TaskState("synthetic-preview", 3, "EXPIRING", expiration_condition_ref="synthetic-class-start")
        notice = NoticeEvidence("synthetic-delivery", state.task_id, 3, state.expiration_condition_ref, True, NOW - timedelta(minutes=10), "DELIVERED", NOW - timedelta(minutes=5))
        return command, grant, caller, {state.task_id: state}, {notice.notice_id: notice}

    def test_explicit_user_authority_needs_no_duplicate_approval(self):
        command, grant, caller = self.user({"completion": "COMPLETE", "user_remaining_seconds": 0})
        decision = self.evaluate(command, grant, caller)
        self.assertTrue(decision.allowed)
        self.assertEqual(decision.request_fingerprint, command.fingerprint)
        self.assertEqual(validate_contract("command", command.as_record()), ())

    def test_unauthenticated_and_forged_principal(self):
        command, grant, caller = self.user()
        self.assertEqual(self.evaluate(command, grant, replace(caller, authenticated=False)).reason, "UNAUTHENTICATED")
        self.assertEqual(self.evaluate(replace(command, principal_id="forged-user"), grant, caller).reason, "CALLER_SCOPE_MISMATCH")

    def test_external_claimed_user_and_known_reference_do_not_grant_authority(self):
        command, grant, caller = self.user({"completion": "COMPLETE"})
        external = CallerIdentity(caller.principal_id, "EXTERNAL", True)
        self.assertEqual(self.evaluate(command, grant, external).reason, "EXTERNAL_IS_NOT_AUTHORITY")
        self.assertEqual(self.evaluate(replace(command, origin="EXTERNAL"), grant, caller).reason, "EXTERNAL_IS_NOT_AUTHORITY")

    def test_unknown_inactive_expired_and_future_grants_are_rejected(self):
        command, grant, caller = self.user()
        self.assertEqual(self.evaluate(command, grant, caller, grants={}).reason, "UNREGISTERED_AUTHORITY")
        for invalid in (replace(grant, active=False), replace(grant, expires_at=NOW), replace(grant, issued_at=NOW + timedelta(seconds=1))):
            with self.subTest(invalid=invalid):
                self.assertEqual(self.evaluate(command, invalid, caller).reason, "INACTIVE_AUTHORITY")

    def test_same_field_wrong_value_and_inferred_extra_are_rejected(self):
        command, grant, caller = self.user()
        for fields in ({"importance": 5}, {"importance": 4, "completion": "COMPLETE"}):
            changed = replace(command, changes=(change("synthetic-task", 3, "UPDATE_TASK", fields),))
            self.assertEqual(self.evaluate(changed, grant, caller).reason, "EXACT_CHANGE_SCOPE_MISMATCH")

    def test_wrong_target_command_id_and_stale_version(self):
        command, grant, caller = self.user()
        changed = replace(command, changes=(change("synthetic-other-task", 3, "UPDATE_TASK", {"importance": 4}),))
        self.assertEqual(self.evaluate(changed, grant, caller).reason, "EXACT_CHANGE_SCOPE_MISMATCH")
        self.assertEqual(self.evaluate(replace(command, command_id="another-command"), grant, caller).reason, "EXACT_CHANGE_SCOPE_MISMATCH")
        self.assertEqual(self.evaluate(command, grant, caller, tasks={"synthetic-task": TaskState("synthetic-task", 4)}).reason, "STALE_STATE_VERSION")
        self.assertEqual(self.evaluate(command, grant, caller, tasks={}).reason, "UNKNOWN_TARGET")

    def test_exact_batch_scope_and_no_omitted_requested_target(self):
        command, grant, caller = self.user()
        second = change("synthetic-second", 2, "UPDATE_TASK", {"importance": 3})
        command = replace(command, changes=command.changes + (second,), batch_ref="synthetic-batch", batch_members=("synthetic-task", "synthetic-second"))
        grant = replace(grant, changes=command.changes, batch_ref=command.batch_ref, batch_members=command.batch_members)
        tasks = {"synthetic-task": TaskState("synthetic-task", 3), "synthetic-second": TaskState("synthetic-second", 2)}
        self.assertTrue(self.evaluate(command, grant, caller, tasks=tasks).allowed)
        self.assertEqual(self.evaluate(replace(command, batch_ref="forged-batch"), grant, caller, tasks=tasks).reason, "BATCH_SCOPE_MISMATCH")
        with self.assertRaises(ValueError):
            replace(command, batch_members=("synthetic-task",))
        partial = replace(command, changes=(command.changes[0],), batch_members=("synthetic-task",))
        self.assertEqual(self.evaluate(partial, grant, caller, tasks=tasks).reason, "EXACT_CHANGE_SCOPE_MISMATCH")

    def test_creation_expects_absent_target(self):
        command, grant, caller = self.user()
        command = replace(command, changes=(change("synthetic-task", None, "CREATE_TASK", {"title": "Synthetic creation"}),))
        grant = replace(grant, changes=command.changes)
        self.assertEqual(self.evaluate(command, grant, caller).reason, "TARGET_ALREADY_EXISTS")
        self.assertTrue(self.evaluate(command, grant, caller, tasks={}).allowed)

    def test_rule_mapping_requires_canonical_creation_not_raw_evidence(self):
        command, grant, caller, tasks, creations = self.rule()
        self.assertTrue(self.evaluate(command, grant, caller, tasks=tasks, creations=creations).allowed)
        self.assertEqual(self.evaluate(command, grant, caller, tasks=tasks, creations={}).reason, "CANONICAL_CREATION_REQUIRED")
        wrong = {key: replace(value, canonical_creation=False) for key, value in creations.items()}
        self.assertEqual(self.evaluate(command, grant, caller, tasks=tasks, creations=wrong).reason, "CANONICAL_CREATION_REQUIRED")
        self.assertEqual(validate_contract("command", command.as_record()), ())

    def test_rule_cannot_complete_or_cancel_counterpart(self):
        for fields in ({"title": "Synthetic", "completion": "COMPLETE"}, {"title": "Synthetic", "disposition": "CANCELLED"}):
            command, grant, caller, tasks, creations = self.rule(fields)
            self.assertEqual(self.evaluate(command, grant, caller, tasks=tasks, creations=creations).reason, "RULE_CANNOT_ASSERT_OUTCOME")

    def test_rule_scope_and_missing_essential_facts(self):
        command, grant, caller, tasks, creations = self.rule()
        wrong = replace(command, rule_scope=replace(command.rule_scope, target_role="different-role"))
        self.assertEqual(self.evaluate(wrong, grant, caller, tasks=tasks, creations=creations).reason, "RULE_SCOPE_MISMATCH")
        incomplete = replace(grant, essential_fields=frozenset({"title", "user_remaining_seconds"}))
        self.assertEqual(self.evaluate(command, incomplete, caller, tasks=tasks, creations=creations).reason, "MISSING_ESSENTIAL_FACTS")

    def test_generation_key_survives_rule_version_edit(self):
        command, *_ = self.rule()
        self.assertEqual(command.rule_scope.generation_key, replace(command.rule_scope, version="2").generation_key)
        self.assertNotEqual(command.rule_scope.generation_key, replace(command.rule_scope, occurrence_key="another-occurrence").generation_key)

    def test_delivered_notice_authorizes_expiry_without_read_ack(self):
        command, grant, caller, tasks, notices = self.expiry()
        self.assertTrue(self.evaluate(command, grant, caller, tasks=tasks, notices=notices).allowed)
        self.assertEqual(validate_contract("command", command.as_record()), ())

    def test_pending_failed_unknown_and_future_notice_do_not_authorize_expiry(self):
        command, grant, caller, tasks, notices = self.expiry()
        notice = next(iter(notices.values()))
        for status in ("PENDING", "FAILED", "UNKNOWN"):
            candidate = replace(notice, delivery_state=status, delivered_at=None)
            result = self.evaluate(command, grant, caller, tasks=tasks, notices={candidate.notice_id: candidate})
            self.assertEqual(result.reason, "CONFIRMED_NOTICE_REQUIRED")
        for candidate in (replace(notice, condition_confirmed=False), replace(notice, delivered_at=NOW + timedelta(seconds=1))):
            self.assertEqual(self.evaluate(command, grant, caller, tasks=tasks, notices={candidate.notice_id: candidate}).reason, "CONFIRMED_NOTICE_REQUIRED")

    def test_notice_scope_and_state_revalidation(self):
        command, grant, caller, tasks, notices = self.expiry()
        notice = next(iter(notices.values()))
        self.assertEqual(self.evaluate(command, grant, caller, tasks=tasks, notices={}).reason, "NOTICE_SCOPE_MISMATCH")
        for candidate in (replace(notice, task_revision=2), replace(notice, task_id="another-task"), replace(notice, condition_ref="another-condition")):
            self.assertEqual(self.evaluate(command, grant, caller, tasks=tasks, notices={candidate.notice_id: candidate}).reason, "NOTICE_SCOPE_MISMATCH")
        state = next(iter(tasks.values()))
        self.assertEqual(self.evaluate(command, grant, caller, tasks={state.task_id: replace(state, revision=4)}, notices=notices).reason, "STALE_STATE_VERSION")

    def test_completed_required_and_inactive_tasks_cannot_expire(self):
        command, grant, caller, tasks, notices = self.expiry()
        state = next(iter(tasks.values()))
        for candidate in (replace(state, completion="COMPLETE"), replace(state, requiredness="REQUIRED"), replace(state, disposition="CANCELLED")):
            self.assertEqual(self.evaluate(command, grant, caller, tasks={candidate.task_id: candidate}, notices=notices).reason, "TASK_NOT_EXPIRABLE")

    def test_expiry_does_not_rewrite_effort_or_completion_even_with_grant(self):
        command, grant, caller, tasks, notices = self.expiry()
        extra = change("synthetic-preview", 3, "EXPIRE_TASK", {"disposition": "EXPIRED", "expiration_notice_ref": "synthetic-delivery", "user_remaining_seconds": 0})
        command = replace(command, changes=(extra,))
        grant = replace(grant, changes=command.changes)
        self.assertEqual(self.evaluate(command, grant, caller, tasks=tasks, notices=notices).reason, "EXPIRY_CANNOT_REWRITE_EFFORT_OR_COMPLETION")
        command, grant, caller = self.user({"disposition": "EXPIRED"})
        self.assertEqual(self.evaluate(command, grant, caller).reason, "EXPIRED_REQUIRES_NOTICE_PROCESS")

    def test_values_are_immutable_and_authorizer_has_no_write_effect(self):
        fields = {"importance": 4}
        command, grant, caller = self.user(fields)
        fields["importance"] = 5
        command.changes[0].fields["importance"] = 5
        self.assertEqual(command.changes[0].fields["importance"], 4)
        tasks = {"synthetic-task": TaskState("synthetic-task", 3)}
        before = deepcopy(tasks)
        self.assertTrue(self.evaluate(command, grant, caller, tasks=tasks).allowed)
        self.assertEqual(tasks, before)

    def test_duplicate_targets_and_untrusted_typed_flags_rejected(self):
        command, _, _ = self.user()
        with self.assertRaises(ValueError):
            replace(command, changes=command.changes + command.changes)
        with self.assertRaises(ValueError):
            CallerIdentity("synthetic-user", "USER_COMMAND", "true")
        with self.assertRaises(ValueError):
            CreationRecord("event", "task", "occurrence", "true")

    def test_schema_cases(self):
        fixture = load_json(ROOT / "tests/fixtures/authorization/cases.json")
        self.assertIs(fixture["synthetic"], True)
        for case in fixture["cases"]:
            with self.subTest(case=case["id"]):
                self.assertEqual(not validate_contract(case["contract"], case["payload"]), case["valid"])

    def test_invalid_values_cannot_be_authorized_by_reference_alone(self):
        for fields in ({"importance": 6}, {"importance": True}, {"user_remaining_seconds": -1}, {"completion": "IN_PROGRESS"}, {"difficulty": {"thinking_depth": 3}}):
            with self.subTest(fields=fields), self.assertRaises(ValueError):
                self.user(fields)


if __name__ == "__main__":
    unittest.main()
