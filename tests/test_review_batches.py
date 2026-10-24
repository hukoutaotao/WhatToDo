"""Scoped batch confirmation verifies untouched estimates without mutating them."""
from copy import deepcopy
from dataclasses import replace
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import unittest

from src.adapters.contract_json import ContractJSONCodec
from src.adapters.extension_contracts import load_supported_schemas
from src.adapters.packaged_contracts import load_contract_schemas
from src.application.command_ledger import validate_audit_fingerprint
from src.application.definitions import canonical
from src.application.ports import RequestContext
from src.application.review_batches import (BatchMember, BatchTaskEvidence, ReviewBatchCommand, ReviewBatchGrant,
    ReviewBatchJournal, admit_review_batch, prepare_batch_commit, prepare_review_batch, verification_identity)
from src.application.task_storage import admit_storage
from src.application.transactions import TransactionError
from src.domain.authorization import CallerIdentity

ROOT=Path(__file__).resolve().parents[1]
NOW=datetime(2026,1,1,tzinfo=timezone.utc)
USER=CallerIdentity('user','USER_COMMAND',True)
CASE='aggregate-explicit-facts-and-original-total-below-current-u'


class ReviewBatchTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.codec=ContractJSONCodec(load_supported_schemas(root=ROOT))
        cases=json.loads((ROOT/'tests/fixtures/task_aggregate/cases.json').read_text(encoding='utf-8'))['cases']
        cls.value=next(c['payload'] for c in cases if c['id']==CASE)

    def record(self,value=None):
        return admit_storage(self.codec,canonical(deepcopy(value or self.value)).encode())

    def command(self,record,*,confirmed=True,extra_members=(),no_work_statement=None,members=None):
        if members is None:
            estimate=record.aggregate.as_record()['effort']['user_remaining']
            base=BatchMember(record.task_id,record.revision,estimate['observation_id'],estimate['seconds'])
            members=(base,*extra_members)
        return ReviewBatchCommand('command','user','grant','review-1',3,'statement-1','batch-1',confirmed,
            members,no_work_statement)

    def grant(self,command,*,observed=None):
        return ReviewBatchGrant(command,'source',NOW-timedelta(minutes=5),
            observed or NOW-timedelta(minutes=1),NOW+timedelta(hours=1))

    def evidence(self,record,*,work_status='UNTOUCHED',prior=None):
        return BatchTaskEvidence(record,work_status,None,
            prior_verification_id=prior, prior_batch_record_id='review-batch-'+'a'*64 if prior else None)

    def prepare(self,command,grant,evidence,caller=USER):
        return prepare_review_batch(command,grant,evidence,caller=caller,now=NOW)

    def test_opt_in_roundtrip_preserves_exact_members_and_base_contracts(self):
        record=self.record();c=self.command(record)
        raw=canonical(c.as_record()).encode()
        self.assertEqual(admit_review_batch(self.codec,raw),c)
        self.assertEqual(admit_review_batch(self.codec,json.dumps(c.as_record(),indent=2).encode()).fingerprint,c.fingerprint)
        base=load_contract_schemas(root=ROOT);self.assertEqual(len(base),30)
        self.assertNotEqual(ContractJSONCodec(base).admit('review-batch',raw).status,'SUPPORTED_SHAPE')
        supported=load_supported_schemas(root=ROOT)
        self.assertEqual({k:supported[k] for k in base},base)

    def test_extra_approval_duplicate_members_and_bad_shape_fail_closed(self):
        record=self.record();c=self.command(record)
        for patch in ({'approved':True},{'schema_version':'new'},{'origin':'EXTERNAL'}):
            with self.assertRaises(TransactionError):admit_review_batch(self.codec,canonical(c.as_record()|patch).encode())
        base=BatchMember(record.task_id,record.revision,'observation-aggregate-work',2400)
        with self.assertRaisesRegex(TransactionError,'DUPLICATE'):
            ReviewBatchCommand('command','user','grant','review-1',3,'statement-1','batch-1',True,(base,base))
        with self.assertRaisesRegex(TransactionError,'MEMBERS'):
            ReviewBatchCommand('command','user','grant','review-1',3,'statement-1','batch-1',True,())
        with self.assertRaisesRegex(TransactionError,'MEMBERS'):
            ReviewBatchCommand('command','user','grant','review-1',3,'statement-1','batch-1',True,
                tuple(BatchMember(f'task-{n}',1,'observation',100) for n in range(101)))

    def test_exact_independent_user_authority_is_required(self):
        record=self.record();c=self.command(record);g=self.grant(c)
        evidence=(self.evidence(record),)
        with self.assertRaisesRegex(TransactionError,'INDEPENDENT_GRANT'):self.prepare(c,None,evidence)
        with self.assertRaisesRegex(TransactionError,'EXACT_SCOPE'):
            self.prepare(c,replace(g,command=replace(c,batch_id='other-batch')),evidence)
        for caller in (CallerIdentity('foreign','USER_COMMAND',True),CallerIdentity('user','EXTERNAL',True),
            CallerIdentity('user','USER_COMMAND',False)):
            with self.assertRaisesRegex(TransactionError,'TRUSTED_USER'):self.prepare(c,g,evidence,caller=caller)
        for grant in (replace(g,active=False),replace(g,expires_at=NOW),replace(g,issued_at=NOW+timedelta(seconds=1))):
            with self.assertRaises(TransactionError):self.prepare(c,grant,evidence)
        with self.assertRaisesRegex(TransactionError,'FUTURE_OBSERVATION'):
            self.prepare(c,replace(g,source_observed_at=NOW+timedelta(seconds=1)),evidence)

    def test_confirmed_batch_verifies_each_untouched_member_without_task_mutation(self):
        record=self.record();c=self.command(record);g=self.grant(c)
        prepared=self.prepare(c,g,(self.evidence(record),))
        self.assertEqual(prepared.state,'CONFIRMED');self.assertEqual(prepared.code,'REVIEW_BATCH_CONFIRMED')
        v=prepared.verifications[0]
        self.assertEqual(v.task_id,record.task_id);self.assertEqual(v.task_revision,record.revision)
        self.assertEqual(v.observation_id,'observation-aggregate-work');self.assertEqual(v.seconds,2400)
        self.assertEqual(v.observed_at,record.aggregate.as_record()['effort']['user_remaining']['observed_at'])
        self.assertEqual(v.verified_at,g.source_observed_at.isoformat())
        self.assertEqual(v.verification_id,verification_identity(c,c.members[0]))
        self.assertTrue(v.verification_id.startswith('verification-'))
        # The untouched Task record itself is not part of the writes.
        plan=prepare_batch_commit(self.codec,canonical(c.as_record()).encode(),g,(self.evidence(record),),
            caller=USER,now=NOW,context=RequestContext(c.command_id,'trace'),expected_store_revision=5,audit_id='audit')
        kinds={w.key.kind for w in plan.request.writes}
        self.assertNotIn('TASK',kinds);self.assertIn('REVIEW_BATCH_CONFIRMED',kinds)
        self.assertIn('REVIEW_VERIFICATION',kinds)
        self.assertNotIn('TASK',{k.kind for k in plan.receipt.changed_keys})

    def test_deterministic_identity_binds_review_statement_batch_and_task(self):
        record=self.record();c=self.command(record)
        other=replace(c,user_statement_ref='statement-2')
        self.assertNotEqual(verification_identity(c,c.members[0]),verification_identity(other,other.members[0]))
        self.assertEqual(verification_identity(c,c.members[0]),verification_identity(c,c.members[0]))
        # A second identical confirmation replays to the same identity, so an
        # overlapping prior verification must be the explicit conflict instead.
        with self.assertRaisesRegex(TransactionError,'OVERLAPPING'):
            self.prepare(c,self.grant(c),(self.evidence(record,prior='verification-'+'b'*64),))

    def test_silence_confirms_none_and_unconfirmed_batch_has_no_verification_effects(self):
        for confirmed in (None,False):
            record=self.record();c=self.command(record,confirmed=confirmed);g=self.grant(c)
            prepared=self.prepare(c,g,(self.evidence(record),))
            self.assertEqual(prepared.state,'NOT_CONFIRMED')
            self.assertEqual(prepared.code,'REVIEW_BATCH_NOT_CONFIRMED')
            self.assertEqual(prepared.verifications,())
            plan=prepare_batch_commit(self.codec,canonical(c.as_record()).encode(),g,(self.evidence(record),),
                caller=USER,now=NOW,context=RequestContext(c.command_id,'trace'),expected_store_revision=5,audit_id='audit')
            self.assertEqual({w.key.kind for w in plan.request.writes},{'REVIEW_BATCH_NOT_CONFIRMED'})
            self.assertEqual(len(plan.journal.verifications),0)
            self.assertEqual(plan.journal.code,'REVIEW_BATCH_NOT_CONFIRMED')

    def test_worked_on_member_is_excluded_from_confirmation(self):
        record=self.record();c=self.command(record)
        with self.assertRaisesRegex(TransactionError,'WORKED_ON'):
            self.prepare(c,self.grant(c),(self.evidence(record,work_status='WORKED'),))

    def test_unknown_work_status_requires_explicit_no_work_statement(self):
        record=self.record()
        c=self.command(record);c_unknown=self.command(record,no_work_statement=True)
        with self.assertRaisesRegex(TransactionError,'WORK_STATUS'):
            self.prepare(c,self.grant(c),(self.evidence(record,work_status='UNKNOWN'),))
        prepared=self.prepare(c_unknown,self.grant(c_unknown),(self.evidence(record,work_status='UNKNOWN'),))
        self.assertEqual(prepared.state,'CONFIRMED')
        self.assertTrue(prepared.verifications[0].no_work_statement)
        c_false=self.command(record,no_work_statement=False)
        with self.assertRaisesRegex(TransactionError,'WORK_STATUS'):
            self.prepare(c_false,self.grant(c_false),(self.evidence(record,work_status='UNKNOWN'),))

    def test_missing_or_changed_estimate_is_excluded(self):
        value=deepcopy(self.value);value['effort']['user_remaining']=None
        record=self.record(value);c=self.command(record,members=(BatchMember(record.task_id,record.revision,'observation-aggregate-work',2400),))
        with self.assertRaisesRegex(TransactionError,'MISSING_ESTIMATE'):
            self.prepare(c,self.grant(c),(self.evidence(record),))
        record2=self.record()
        c2=self.command(record2,members=(BatchMember(record2.task_id,record2.revision,'other-observation',2400),))
        with self.assertRaisesRegex(TransactionError,'CHANGED_ESTIMATE'):
            self.prepare(c2,self.grant(c2),(self.evidence(record2),))
        c3=self.command(record2,members=(BatchMember(record2.task_id,record2.revision,'observation-aggregate-work',9999),))
        with self.assertRaisesRegex(TransactionError,'CHANGED_ESTIMATE'):
            self.prepare(c3,self.grant(c3),(self.evidence(record2),))

    def test_stale_member_version_conflicts_instead_of_silently_approving(self):
        record=self.record()
        stale=self.command(record,members=(BatchMember(record.task_id,record.revision+1,'observation-aggregate-work',2400),))
        with self.assertRaisesRegex(TransactionError,'STALE_MEMBER'):
            self.prepare(stale,self.grant(stale),(self.evidence(record),))
        # A revision bumped after the frame was presented also conflicts.
        value=deepcopy(self.value);value['core']['revision']=value['effort']['task_revision']=record.revision+1
        newer=self.record(value)
        c=self.command(record)
        with self.assertRaisesRegex(TransactionError,'STALE_MEMBER'):
            self.prepare(c,self.grant(c),(self.evidence(newer),))

    def test_complete_expired_or_cancelled_members_are_ineligible(self):
        cases=json.loads((ROOT/'tests/fixtures/task_aggregate/cases.json').read_text(encoding='utf-8'))['cases']
        for name in ('aggregate-complete-with-unknown-historical-completion-time','aggregate-expired-retains-positive-u',
                'aggregate-cancelled-retains-effort'):
            value=next(c['payload'] for c in cases if c['id']==name)
            record=self.record(value);estimate=record.aggregate.as_record()['effort']['user_remaining']
            c=ReviewBatchCommand('command','user','grant','review-1',3,'statement-1','batch-1',True,
                (BatchMember(record.task_id,record.revision,estimate['observation_id'],estimate['seconds']),))
            with self.assertRaisesRegex(TransactionError,'INELIGIBLE'):
                self.prepare(c,self.grant(c),(self.evidence(record),))

    def test_verification_time_cannot_precede_the_original_observation(self):
        record=self.record();c=self.command(record)
        g=self.grant(c,observed=datetime(2025,1,1,tzinfo=timezone.utc))
        with self.assertRaisesRegex(TransactionError,'BEFORE_OBSERVATION'):
            self.prepare(c,g,(self.evidence(record),))

    def test_one_invalid_member_rejects_the_whole_batch(self):
        good=self.record()
        value=deepcopy(self.value)
        value['core']['task_id']=value['effort']['task_id']='task-b'
        for detail in value.get('stage_details',[]):detail['task_id']='task-b'
        bad=self.record(value)
        good_member=BatchMember(good.task_id,good.revision,'observation-aggregate-work',2400)
        bad_member=BatchMember(bad.task_id,bad.revision,'observation-aggregate-work',2400)
        c=ReviewBatchCommand('command','user','grant','review-1',3,'statement-1','batch-1',True,(good_member,bad_member))
        evidence=(self.evidence(good),self.evidence(bad,work_status='WORKED'))
        with self.assertRaisesRegex(TransactionError,'WORKED_ON'):
            self.prepare(c,self.grant(c),evidence)
        evidence_mismatch=(self.evidence(good),self.evidence(bad))
        c_mismatch=ReviewBatchCommand('command','user','grant','review-1',3,'statement-1','batch-1',True,
            (good_member,BatchMember(bad.task_id,bad.revision,'observation-other',2400)))
        with self.assertRaisesRegex(TransactionError,'CHANGED_ESTIMATE'):
            self.prepare(c_mismatch,self.grant(c_mismatch),evidence_mismatch)
        with self.assertRaisesRegex(TransactionError,'EVIDENCE_SCOPE'):
            self.prepare(c,self.grant(c),(self.evidence(good),))

    def test_journal_roundtrip_is_lossless_and_tamper_evident(self):
        record=self.record();c=self.command(record);g=self.grant(c)
        plan=prepare_batch_commit(self.codec,canonical(c.as_record()).encode(),g,(self.evidence(record),),
            caller=USER,now=NOW,context=RequestContext(c.command_id,'trace'),expected_store_revision=5,audit_id='audit')
        journal=ReviewBatchJournal.from_payload(plan.journal.payload())
        self.assertEqual(journal,plan.journal)
        for changes in (dict(command_fingerprint='0'*64),dict(raw_command_hash='0'*64),dict(record_id='other'),
                dict(state='NOT_CONFIRMED'),dict(code='OTHER_CODE')):
            with self.assertRaises(RuntimeError):ReviewBatchJournal.from_payload(plan.journal.payload()|changes)
        payload=plan.journal.payload();payload['command']['batch_id']='foreign'
        with self.assertRaises(RuntimeError):ReviewBatchJournal.from_payload(payload)
        row=plan.journal.sql_row('transaction-1','change-1')
        self.assertEqual(row['review_id'],'review-1');self.assertEqual(row['member_count'],1)
        self.assertTrue(row['confirmed']);self.assertEqual(row['state'],'CONFIRMED')

    def test_receipt_and_audits_reconstruct_one_exact_request(self):
        record=self.record();c=self.command(record);g=self.grant(c)
        plan=prepare_batch_commit(self.codec,canonical(c.as_record()).encode(),g,(self.evidence(record),),
            caller=USER,now=NOW,context=RequestContext(c.command_id,'trace'),expected_store_revision=5,audit_id='audit')
        validate_audit_fingerprint(plan.receipt,principal_id='user',expected_store_revision=5,
            source_ref='source',correlation_ref='trace',changes=tuple(a.tuple for a in plan.audits))
        self.assertEqual(plan.receipt.store_revision,6)
        self.assertEqual(set(plan.receipt.changed_keys),{w.key for w in plan.request.writes})
        self.assertEqual(len({a.change_ref for a in plan.audits}),len(plan.audits))
        self.assertTrue(all(w.expected_revision is None for w in plan.request.writes))
        self.assertFalse(hasattr(plan,'permit'))

    def test_raw_format_is_retained_losslessly_without_changing_scope(self):
        record=self.record();c=self.command(record);g=self.grant(c)
        raw=json.dumps(c.as_record(),indent=2,ensure_ascii=False).encode()
        plan=prepare_batch_commit(self.codec,raw,g,(self.evidence(record),),caller=USER,now=NOW,
            context=RequestContext(c.command_id,'trace'),expected_store_revision=5,audit_id='audit')
        stored=ReviewBatchJournal.from_payload(plan.journal.payload())
        self.assertEqual(stored.raw_command,raw)
        self.assertEqual(stored.command.fingerprint,c.fingerprint)
        self.assertNotEqual(raw,canonical(c.as_record()).encode())

    def test_no_zero_actual_work_is_inferred_from_unchanged_estimates(self):
        record=self.record();c=self.command(record);g=self.grant(c)
        plan=prepare_batch_commit(self.codec,canonical(c.as_record()).encode(),g,(self.evidence(record),),
            caller=USER,now=NOW,context=RequestContext(c.command_id,'trace'),expected_store_revision=5,audit_id='audit')
        for write in plan.request.writes:
            body=write.body_json
            self.assertNotIn('actual_work',body);self.assertNotIn('WORK_REPORT',body)
        self.assertEqual(record.aggregate.as_record(),deepcopy(self.value))
