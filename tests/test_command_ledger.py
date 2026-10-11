from copy import deepcopy
from dataclasses import asdict,replace
import json
import unittest

from src.application.command_ledger import receipt_from_row,validate_audit_fingerprint,validate_caller
from src.application.ports import AggregateKey,CommitReceipt,CommitRequest,RecordWrite,RequestContext
from src.application.transactions import TransactionError
from src.domain.authorization import CallerIdentity


class CommandLedgerTests(unittest.TestCase):
    def setUp(self):
        self.request=CommitRequest(RequestContext('request','first-attempt'),'principal',7,
            (RecordWrite(AggregateKey('TASK','b'),2,'{"title":"b"}'),
             RecordWrite(AggregateKey('TASK','a'),None,'{"title":"a"}')),'audit','source')
        self.receipt=CommitReceipt('request',self.request.fingerprint,8,'audit',tuple(w.key for w in self.request.writes))
        self.body=json.loads(json.dumps(asdict(self.receipt)))
        self.changes=(('TASK','a',None,1,None,{'title':'a'}),
            ('TASK','b',2,3,{'title':'before b'},{'title':'b'}))

    def decode(self,body):
        return receipt_from_row(body,request_id='request',request_hash=self.request.fingerprint,
            store_revision=8,audit_id='audit')

    def verify(self,changes=None,**kw):
        args=dict(principal_id='principal',expected_store_revision=7,source_ref='source',
            correlation_ref='reconciliation-attempt',changes=self.changes if changes is None else changes)
        args.update(kw);return validate_audit_fingerprint(self.receipt,**args)

    def test_receipt_preserves_original_order_and_detaches_mutable_body(self):
        r=self.decode(self.body);self.body['changed_keys'][0]['id']='other'
        self.assertEqual(r,self.receipt)
        self.assertEqual(tuple(k.id for k in r.changed_keys),('b','a'))

    def test_changed_or_legacy_receipt_headers_are_not_reconstructed_as_success(self):
        for field,value in [('request_id','other'),('request_fingerprint','f'*64),
                ('store_revision',True),('audit_id','other')]:
            d=deepcopy(self.body);d[field]=value
            with self.assertRaisesRegex(TransactionError,'COMMAND_RECEIPT_INVALID'):self.decode(d)
        for d in ({'synthetic':True},dict(self.body,authority='claimed-approval')):
            with self.assertRaisesRegex(TransactionError,'COMMAND_RECEIPT_INVALID'):self.decode(d)

    def test_duplicate_or_untyped_changed_keys_are_rejected(self):
        for keys in ([],[self.body['changed_keys'][0]]*2,[{'kind':'TASK','id':True}],
                [{'kind':'TASK','id':'a','revision':1}]):
            d=deepcopy(self.body);d['changed_keys']=keys
            with self.assertRaisesRegex(TransactionError,'COMMAND_RECEIPT_INVALID'):self.decode(d)

    def test_original_fingerprint_ignores_attempt_ids_and_write_order(self):
        retry=replace(self.request,context=RequestContext('request','different-attempt'),writes=tuple(reversed(self.request.writes)))
        self.assertEqual(retry.fingerprint,self.request.fingerprint)
        self.verify()

    def test_changed_semantics_cannot_reuse_the_original_audit_fingerprint(self):
        for kw in ({'principal_id':'other'},{'expected_store_revision':8},
                {'source_ref':'other-source'}):
            with self.assertRaisesRegex(TransactionError,'COMMAND_RECEIPT_INVALID'):self.verify(**kw)
        changes=list(self.changes);changes[0]=(*changes[0][:-1],{'title':'changed'})
        with self.assertRaisesRegex(TransactionError,'COMMAND_RECEIPT_INVALID'):self.verify(tuple(changes))

    def test_missing_audit_or_changed_key_cannot_return_a_valid_receipt(self):
        for changes in (self.changes[:1],(self.changes[0],self.changes[0]),
                (('TASK','unrelated',None,1,None,{'title':'a'}),self.changes[1])):
            with self.assertRaisesRegex(TransactionError,'COMMAND_RECEIPT_INVALID'):self.verify(changes)

    def test_audit_revisions_must_be_a_single_step_with_truthful_before_value(self):
        for before,after,old in ((None,2,None),(2,4,{}),(2,3,None),(True,2,{})):
            changes=(self.changes[0],('TASK','b',before,after,old,{'title':'b'}))
            with self.assertRaisesRegex(TransactionError,'COMMAND_RECEIPT_INVALID'):self.verify(changes)

    def test_untrusted_receipt_callers_fail_before_reading_storage(self):
        for caller in (CallerIdentity('principal','EXTERNAL',True),
                CallerIdentity('principal','USER_COMMAND',False),{'authenticated':True}):
            with self.assertRaisesRegex(TransactionError,'UNTRUSTED_CALLER'):validate_caller(caller)
        with self.assertRaisesRegex(TransactionError,'UNTRUSTED_CALLER'):
            validate_caller(CallerIdentity('other','USER_COMMAND',True),principal_id='principal')


if __name__=='__main__':unittest.main()
