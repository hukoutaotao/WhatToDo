"""Composite stage history preserves evidence without granting mutation rights."""
from copy import deepcopy
from dataclasses import replace
from datetime import timedelta
import json
import unittest

from src.application.command_ledger import validate_audit_fingerprint
from src.application.definitions import canonical
from src.application.ports import RequestContext
from src.application.stage_commit import StageCommandJournal, can_resolve_stage_pending, order_from_payload, prepare_stage_commit
from src.application.stage_commands import StageExecutionEvidence, StageOrderSnapshot
from src.application.relationship_validation import GraphLimits
from src.domain.relationships import Endpoint
from src.application.transactions import TransactionError
from tests import test_stage_commands as fixtures


class StageCommitTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        fixtures.StageCommandTests.setUpClass()
        cls.fixture = fixtures.StageCommandTests()
        cls.codec = cls.fixture.codec

    def build(self, *, fields=None, operation='REWORK', stage='stage-2', order=None, raw=None, **kwargs):
        c, g, before = self.fixture.fixture(fields=fields, operation=operation, stage=stage)
        plan = prepare_stage_commit(self.codec, raw or canonical(c.as_record()).encode(), g, before,
            caller=fixtures.USER, now=fixtures.NOW, context=RequestContext(c.command_id, 'trace'),
            expected_store_revision=5, audit_id='audit', order=order or StageOrderSnapshot(), **kwargs)
        return c, g, before, plan

    def test_pending_retains_exact_raw_without_task_estimate_or_transition_effects(self):
        for intent, field in (('UNRESOLVED', 'intent'), ('CORRECTION', 'correction_facts'), ('NEW_OBLIGATION', 'new_obligation_facts')):
            c, _, before, plan = self.build(fields=dict(intent=intent))
            self.assertEqual(plan.journal.state, 'PENDING')
            self.assertEqual(plan.journal.before_task_hash, before.content_hash)
            self.assertEqual(plan.journal.missing_fields, (field,))
            self.assertIsNone(plan.task); self.assertFalse(plan.observations); self.assertFalse(plan.issues)
            self.assertEqual(len(plan.request.writes), 1)
            self.assertEqual(plan.request.writes[0].key.kind, 'STAGE_PENDING')
            self.assertEqual(plan.journal.raw_command, canonical(c.as_record()).encode())
            self.assertIsNone(plan.journal.transition)

    def test_larger_configured_snapshot_roundtrips_without_becoming_the_default_execution_policy(self):
        c,g,before=self.fixture.fixture()
        facts=tuple(StageExecutionEvidence(Endpoint('TASK',f'node-{n}'),f'node-{n}',1,'INCOMPLETE') for n in range(4097))
        order=StageOrderSnapshot((),facts,replace(GraphLimits(),max_endpoints=5000))
        with self.assertRaisesRegex(TransactionError,'STAGE_ORDER_RESOURCE_LIMIT'):order_from_payload(order.payload)
        plan=prepare_stage_commit(self.codec,canonical(c.as_record()).encode(),g,before,caller=fixtures.USER,now=fixtures.NOW,
            context=RequestContext(c.command_id,'trace'),expected_store_revision=5,audit_id='audit',order=order)
        self.assertEqual(StageCommandJournal.from_payload(plan.journal.payload),plan.journal)
        self.assertEqual(len(plan.journal.payload['order_snapshot']['executions']),4097)
        self.assertFalse(hasattr(plan,'permit'))

    def test_committed_plan_binds_parent_stage_history_and_original_user_observations(self):
        c, g, before, plan = self.build(fields=dict(intent='SAME_OBLIGATION', parent_remaining_seconds=900, stage_remaining_seconds=200))
        self.assertEqual(plan.journal.kind, 'STAGE_TRANSITION')
        self.assertEqual(plan.journal.after_task_hash, plan.task.content_hash)
        self.assertEqual(plan.task.revision, before.revision + 1)
        self.assertEqual({w.key.kind for w in plan.request.writes}, {'TASK', 'STAGE_TRANSITION'})
        self.assertEqual({o.authority_ref for o in plan.observations}, {c.authority_ref})
        self.assertEqual({o.observed_at for o in plan.observations}, {g.source_observed_at})
        self.assertEqual(plan.journal.transition['previous_stage_completion'], 'COMPLETE')
        self.assertFalse(hasattr(plan, 'permit'))
        row = plan.journal.sql_row(c.command_id, plan.audits[-1].change_ref)
        self.assertEqual(row['after_task_revision'], plan.task.revision)
        self.assertEqual(row['before_stage_revision'], c.expected_stage_revision)

    def test_receipt_and_every_audit_reconstruct_one_exact_request(self):
        for intent in ('SAME_OBLIGATION', 'UNRESOLVED'):
            _, _, _, plan = self.build(fields=dict(intent=intent))
            validate_audit_fingerprint(plan.receipt, principal_id='user', expected_store_revision=5,
                source_ref='source', correlation_ref='trace', changes=tuple(a.tuple for a in plan.audits))
            self.assertEqual(plan.receipt.store_revision, 6)
            self.assertEqual(set(plan.receipt.changed_keys), {w.key for w in plan.request.writes})
            self.assertEqual(len({a.change_ref for a in plan.audits}), len(plan.audits))

    def test_actual_out_of_order_completion_has_separate_audited_issue_and_no_prerequisite_write(self):
        c, g, before = self.fixture.fixture(operation='COMPLETE', stage='stage-1')
        order = self.fixture.order(before)
        plan = prepare_stage_commit(self.codec, canonical(c.as_record()).encode(), g, before, caller=fixtures.USER,
            now=fixtures.NOW, context=RequestContext(c.command_id, 'trace'), expected_store_revision=5, audit_id='audit', order=order)
        self.assertEqual(len(plan.issues), 1)
        self.assertEqual(plan.issues[0]['code'], 'PREREQUISITE_INCOMPLETE')
        self.assertEqual({w.key.kind for w in plan.request.writes}, {'TASK', 'STAGE_TRANSITION', 'STAGE_RELATIONSHIP_ISSUE'})
        self.assertFalse(any(w.key.id == 'prerequisite' for w in plan.request.writes))
        self.assertEqual(plan.journal.payload['order_snapshot'], order.payload)
        self.assertEqual(StageCommandJournal.from_payload(plan.journal.payload), plan.journal)

    def test_raw_format_and_unicode_are_retained_losslessly_without_changing_command_scope(self):
        c, g, before = self.fixture.fixture()
        raw = json.dumps(c.as_record(), indent=2, ensure_ascii=False).encode()
        plan = prepare_stage_commit(self.codec, raw, g, before, caller=fixtures.USER, now=fixtures.NOW,
            context=RequestContext(c.command_id, 'trace'), expected_store_revision=5, audit_id='audit')
        stored = StageCommandJournal.from_payload(plan.journal.payload)
        self.assertEqual(stored.raw_command, raw)
        self.assertEqual(stored.command.fingerprint, c.fingerprint)
        self.assertNotEqual(raw, canonical(c.as_record()).encode())

    def test_changed_scope_raw_hash_and_added_payload_fields_fail_closed(self):
        _, _, _, plan = self.build()
        for changes in (dict(command_fingerprint='0'*64), dict(raw_command_hash='0'*64),
                        dict(record_id='other'), dict(approved=True), dict(kind='STAGE_PENDING')):
            with self.assertRaises(RuntimeError):StageCommandJournal.from_payload(plan.journal.payload | changes)
        payload = plan.journal.payload; payload['command']['target_ref']['stage_id'] = 'foreign'
        with self.assertRaises(RuntimeError):StageCommandJournal.from_payload(payload)

    def test_pending_cannot_acquire_an_after_task_or_fake_transition(self):
        _, _, _, plan = self.build(fields=dict(intent='UNRESOLVED'))
        with self.assertRaisesRegex(TransactionError, 'JOURNAL_EFFECTS'):
            replace(plan.journal, after_task_hash='a'*64)
        with self.assertRaisesRegex(TransactionError, 'JOURNAL_EFFECTS'):
            replace(plan.journal, transition_json='{}')

    def test_transition_rejects_bool_revision_foreign_command_and_changed_input_hash(self):
        _, _, _, plan = self.build()
        for name, value in (('stage_revision', True), ('previous_parent_revision', True), ('order_input_hash', 'a'*64), ('source_ref', 'foreign')):
            t = plan.journal.transition; t[name] = value
            with self.assertRaisesRegex(TransactionError, 'TRANSITION_BINDING'):
                replace(plan.journal, transition_json=canonical(t))

    def test_relation_and_execution_snapshots_are_detached_and_structurally_exact(self):
        _, _, before = self.fixture.fixture(operation='COMPLETE', stage='stage-1')
        order = self.fixture.order(before, prior_complete='COMPLETE', completed_at=fixtures.NOW-timedelta(minutes=1))
        self.assertEqual(order_from_payload(order.payload), order)
        for modify in (lambda v:v.update(extra=True), lambda v:v['relations'][0]['before'].update(task_id='foreign'),
                       lambda v:v['executions'][0].update(completion='UNKNOWN')):
            value = deepcopy(order.payload); modify(value)
            with self.assertRaises(RuntimeError):order_from_payload(value)

    def test_detached_read_cannot_mutate_original_evidence_audits_or_request_fingerprint(self):
        _, _, _, plan = self.build()
        fingerprint = plan.request.fingerprint
        body = plan.journal.payload; body['command']['fields']['intent'] = 'NEW_OBLIGATION'
        body['transition']['previous_stage_completion'] = 'INCOMPLETE'
        audit = plan.audits[-1].tuple; audit[-1]['source_ref'] = 'foreign'
        self.assertEqual(plan.request.fingerprint, fingerprint)
        self.assertEqual(plan.journal.command.fields['intent'], 'SAME_OBLIGATION')
        self.assertEqual(plan.journal.transition['previous_stage_completion'], 'COMPLETE')

    def test_duplicate_hard_issue_or_unrelated_relation_is_rejected(self):
        c, g, before = self.fixture.fixture(operation='COMPLETE', stage='stage-1')
        plan = prepare_stage_commit(self.codec, canonical(c.as_record()).encode(), g, before, caller=fixtures.USER,
            now=fixtures.NOW, context=RequestContext(c.command_id, 'trace'), expected_store_revision=5, audit_id='audit',
            order=self.fixture.order(before))
        t = plan.journal.transition; t['issues'].append(deepcopy(t['issues'][0]))
        with self.assertRaisesRegex(TransactionError, 'DUPLICATE_ISSUE'):replace(plan.journal, transition_json=canonical(t))
        t = plan.journal.transition; t['issues'][0]['relation_id'] = 'foreign'
        with self.assertRaisesRegex(TransactionError, 'ISSUE_BINDING'):replace(plan.journal, transition_json=canonical(t))

    def test_foreign_request_id_and_unresolved_grant_cannot_build_commit(self):
        c, g, before = self.fixture.fixture()
        with self.assertRaisesRegex(TransactionError, 'REQUEST_SCOPE'):
            prepare_stage_commit(self.codec, canonical(c.as_record()).encode(), g, before, caller=fixtures.USER,
                now=fixtures.NOW, context=RequestContext('foreign', 'trace'), expected_store_revision=5, audit_id='audit')
        with self.assertRaisesRegex(TransactionError, 'EXACT_SCOPE'):
            prepare_stage_commit(self.codec, canonical(c.as_record()).encode(), replace(g, command=replace(c, stage_id='foreign')),
                before, caller=fixtures.USER, now=fixtures.NOW, context=RequestContext(c.command_id, 'trace'), expected_store_revision=5, audit_id='audit')

    def test_fresh_same_obligation_command_links_pending_with_a_separate_full_audit(self):
        c,g,before,old=self.build(fields=dict(intent='UNRESOLVED'))
        fresh=replace(c,command_id='fresh',authority_ref='fresh-root',fields_json=canonical(dict(intent='SAME_OBLIGATION')))
        grant=replace(g,command=fresh,evidence_ref='fresh-source')
        plan=prepare_stage_commit(self.codec,canonical(fresh.as_record()).encode(),grant,before,caller=fixtures.USER,
            now=fixtures.NOW,context=RequestContext('fresh','trace'),expected_store_revision=6,audit_id='fresh-audit',pending=(old.journal,))
        self.assertEqual(len(plan.resolutions),1)
        self.assertEqual(plan.resolutions[0]['pending_ref'],old.journal.record_id)
        self.assertEqual(plan.resolutions[0]['transition_ref'],plan.journal.record_id)
        self.assertEqual(old.journal.state,'PENDING')
        self.assertEqual({w.key.kind for w in plan.request.writes},{'TASK','STAGE_TRANSITION','STAGE_PENDING_RESOLUTION'})
        validate_audit_fingerprint(plan.receipt,principal_id='user',expected_store_revision=6,source_ref='fresh-source',
            correlation_ref='trace',changes=tuple(a.tuple for a in plan.audits))

    def test_resolution_never_converts_correction_new_obligation_or_foreign_stage_into_rework(self):
        c,_,_=self.fixture.fixture()
        for intent in ('CORRECTION','NEW_OBLIGATION'):
            _,_,_,old=self.build(fields=dict(intent=intent))
            self.assertFalse(can_resolve_stage_pending(old.journal,c))
        _,_,_,old=self.build(fields=dict(intent='UNRESOLVED'))
        for changed in (replace(c,stage_id='foreign'),replace(c,principal_id='foreign'),replace(c,operation='COMPLETE'),
            replace(c,expected_stage_revision=c.expected_stage_revision+1)):
            self.assertFalse(can_resolve_stage_pending(old.journal,changed))

    def test_resolution_preserves_known_user_facts_but_can_supply_an_explicitly_missing_estimate(self):
        c,_,_=self.fixture.fixture(operation='COMPLETE',stage='stage-1')
        _,_,_,old=self.build(operation='COMPLETE',stage='stage-1',fields=dict(intent='UNRESOLVED',completed_at=fixtures.NOW.isoformat()))
        self.assertFalse(can_resolve_stage_pending(old.journal,c))
        with_time=replace(c,fields_json=canonical(dict(intent='SAME_OBLIGATION',completed_at=fixtures.NOW.isoformat())))
        self.assertTrue(can_resolve_stage_pending(old.journal,with_time))

    def test_duplicate_or_unrelated_pending_resolution_cannot_enter_exact_commit_plan(self):
        c,g,before=self.fixture.fixture()
        _,_,_,old=self.build(fields=dict(intent='UNRESOLVED'))
        with self.assertRaisesRegex(TransactionError,'RESOLUTION_LIMIT'):
            prepare_stage_commit(self.codec,canonical(c.as_record()).encode(),g,before,caller=fixtures.USER,
                now=fixtures.NOW,context=RequestContext(c.command_id,'trace'),expected_store_revision=5,audit_id='audit',pending=(old.journal,old.journal))
        _,_,_,correction=self.build(fields=dict(intent='CORRECTION'))
        with self.assertRaisesRegex(TransactionError,'RESOLUTION_SCOPE'):
            prepare_stage_commit(self.codec,canonical(c.as_record()).encode(),g,before,caller=fixtures.USER,
                now=fixtures.NOW,context=RequestContext(c.command_id,'trace'),expected_store_revision=5,audit_id='audit',pending=(correction.journal,))
