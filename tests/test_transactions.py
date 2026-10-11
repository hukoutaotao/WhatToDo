from copy import deepcopy
from dataclasses import replace
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import unittest

from src.adapters.contract_json import ContractJSONCodec
from src.application.ports import (AggregateKey,CommitRequest,RecordWrite,
    RequestContext,TransactionPermit)
from src.application.transactions import TransactionError,prepare_transaction
from src.domain.authorization import CallerIdentity
from tools.check_contract_registry import trusted_schemas

ROOT=Path(__file__).resolve().parents[1]
NOW=datetime(2026,1,1,tzinfo=timezone.utc)
CALLER=CallerIdentity('principal','USER_COMMAND',True)


class TransactionPreparationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.codec=ContractJSONCodec(trusted_schemas())
        cls.example=json.loads((ROOT/'tests/fixtures/task_aggregate/cases.json').read_text(encoding='utf-8'))['cases'][0]['payload']

    def request(self, *, task_id='task', epoch=1, expected=None):
        value=deepcopy(self.example)
        value['core']['task_id']=value['effort']['task_id']=task_id
        value['core']['revision']=value['effort']['task_revision']=(expected or 0)+1
        value['effort']['user_remaining']=None
        return CommitRequest(RequestContext('request','correlation'),'principal',epoch,
            (RecordWrite(AggregateKey('TASK',task_id),expected,json.dumps(value)),),'audit','source')

    def prepare(self,request,**kw):
        permit=TransactionPermit('permit','principal','USER_COMMAND',request.fingerprint,
            NOW-timedelta(minutes=1),NOW+timedelta(hours=1))
        options=dict(caller=CALLER,permit=permit,at=NOW);options.update(kw)
        return prepare_transaction(self.codec,request,**options)

    def test_prepared_receipt_and_unknown_facts_do_not_fabricate_effort(self):
        r=self.request();p=self.prepare(r)
        self.assertEqual(p.receipt.store_revision,2)
        self.assertEqual(p.receipt.request_fingerprint,r.fingerprint)
        self.assertIsNone(p.writes[0].record.aggregate.budget(at=NOW).seconds)
        d=p.receipt_body;d['changed_keys'][0]['id']='changed'
        self.assertEqual(p.receipt.changed_keys[0].id,'task')
        self.assertNotIn('Synthetic work',repr(p))

    def test_audit_identity_is_stable_but_separates_distinct_tasks(self):
        a=self.prepare(self.request());b=self.prepare(self.request(task_id='other'))
        self.assertEqual(a.writes[0].change_ref,self.prepare(self.request()).writes[0].change_ref)
        self.assertNotEqual(a.writes[0].change_ref,b.writes[0].change_ref)

    def test_approval_text_and_unauthenticated_callers_cannot_authorize(self):
        for caller in (CallerIdentity('principal','USER_COMMAND',False),
                CallerIdentity('principal','EXTERNAL',True),CallerIdentity('other','USER_COMMAND',True)):
            with self.assertRaisesRegex(TransactionError,'UNTRUSTED_CALLER'):
                self.prepare(self.request(),caller=caller)
        with self.assertRaisesRegex(TransactionError,'EXACT_ACTIVE_PERMIT_REQUIRED'):
            self.prepare(self.request(),permit={'active':True})

    def test_expired_inactive_and_different_scope_permits_are_rejected(self):
        r=self.request();permit=TransactionPermit('permit','principal','USER_COMMAND',r.fingerprint,
            NOW-timedelta(minutes=1),NOW+timedelta(hours=1))
        for p in (replace(permit,active=False),replace(permit,request_fingerprint='f'*64),
                replace(permit,origin='RELATIONSHIP_RULE'),replace(permit,expires_at=NOW)):
            with self.assertRaisesRegex(TransactionError,'EXACT_ACTIVE_PERMIT_REQUIRED'):
                self.prepare(r,permit=p)

    def test_task_identity_and_revision_must_match_exact_requested_write(self):
        r=self.request();w=r.writes[0]
        for altered in (replace(w,key=AggregateKey('TASK','other')),
                replace(w,expected_revision=1)):
            with self.assertRaisesRegex(TransactionError,'TRANSACTION_EXACT_WRITE_REQUIRED'):
                self.prepare(replace(r,writes=(altered,)))

    def test_unsupported_aggregate_is_not_silently_stored_as_task(self):
        r=self.request();r=replace(r,writes=(replace(r.writes[0],key=AggregateKey('GOAL','task')),))
        with self.assertRaisesRegex(TransactionError,'TRANSACTION_UNSUPPORTED_AGGREGATE'):
            self.prepare(r)

    def test_revision_exhaustion_and_duplicate_bindings_fail_before_io(self):
        with self.assertRaisesRegex(TransactionError,'TRANSACTION_REVISION_LIMIT'):
            self.prepare(self.request(epoch=9223372036854775807))
        with self.assertRaisesRegex(TransactionError,'TRANSACTION_BINDING_REGISTRY'):
            self.prepare(self.request(),bindings=(('task',None),))

    def test_transaction_batch_has_a_finite_write_bound(self):
        base=self.request();writes=tuple(self.request(task_id=f'task-{i}').writes[0] for i in range(101))
        with self.assertRaisesRegex(TransactionError,'TRANSACTION_SIZE_LIMIT'):
            self.prepare(replace(base,writes=writes))


if __name__=='__main__':unittest.main()
