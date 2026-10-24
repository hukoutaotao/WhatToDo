"""Full queue ranking/paging retains every question and never invents answers."""
from dataclasses import replace
from datetime import datetime,timedelta,timezone
from pathlib import Path
import json
import unittest
from unittest.mock import patch

from src.adapters.contract_json import ContractJSONCodec
from src.adapters.extension_contracts import load_supported_schemas
from src.application.definitions import canonical
from src.application.review_queue import (ReviewQueueCursor,ReviewQueueItem,ReviewQueueQuery,ReviewQueueSnapshot,
    MAX_PAGE_BYTES,admit_review_queue_query,make_review_queue_snapshot,make_review_queue_page)
from src.application.transactions import TransactionError

ROOT=Path(__file__).resolve().parents[1]
NOW=datetime(2026,1,1,tzinfo=timezone.utc)


class ReviewQueueTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        schemas=load_supported_schemas(root=ROOT)
        cls.codec=ContractJSONCodec(schemas)
    def item(self,n,*,priority=5,importance=1,group='course',kind='TASK_ESTIMATE'):
        return ReviewQueueItem(kind,f'task-{n}',1,'ESTIMATE_VERIFICATION',f'Future task {n}',priority,importance,group,
            ('source',),f'task-{n}',1,canonical(dict(work_status='UNKNOWN',estimate_status='UNCERTAIN')))
    def snapshot(self,items,query=None,**kwargs):
        return make_review_queue_snapshot(query or ReviewQueueQuery(3,5),tuple(items),snapshot_id='snapshot',principal_id='user',request_id='request',
            scope_hash='a'*64,store_revision=1,last_transaction_ref=None,observed_at=NOW,expires_at=NOW+timedelta(days=1),**kwargs)
    def test_draft_contract_roundtrip_rejects_approval_filters_versions_and_duplicate_keys(self):
        q=ReviewQueueQuery(3,5)
        self.assertEqual(admit_review_queue_query(self.codec,canonical(q.as_record()).encode()),q)
        for changed in (dict(approved=True),dict(filters={'importance':5}),dict(schema_version='future')):
            with self.assertRaises(TransactionError):admit_review_queue_query(self.codec,canonical(q.as_record()|changed).encode())
        raw=canonical(q.as_record()).replace('"page_size":3','"page_size":3,"page_size":1').encode()
        with self.assertRaises(TransactionError):admit_review_queue_query(self.codec,raw)
    def test_time_target_never_truncates_low_priority_or_future_task_questions(self):
        items=[self.item(i,importance=1 if i else 5) for i in range(40)]
        short=self.snapshot(items,ReviewQueueQuery(3,1));long=self.snapshot(items,ReviewQueueQuery(3,120))
        self.assertEqual(short.items,long.items)
        self.assertEqual(short.header['item_count'],40)
        self.assertEqual(sum(g['item_count'] for g in short.header['groups']),40)
        self.assertTrue(all(i.payload['answer'] is None for i in short.items))
    def test_rank_is_high_impact_then_known_importance_and_stable_identity(self):
        low=self.item(2,priority=5,importance=1);important=self.item(3,priority=5,importance=5);conflict=self.item(4,priority=0,importance=None)
        snapshot=self.snapshot([low,important,conflict])
        self.assertEqual(snapshot.items,(conflict,important,low))
        self.assertIsNone(snapshot.items[0].importance)
    def test_complete_cursor_walk_returns_every_item_once_across_group_and_page_boundaries(self):
        snapshot=self.snapshot([self.item(i,group=f'course-{i%4}') for i in range(17)])
        signer=ReviewQueueCursor(b'x'*32);q=ReviewQueueQuery(3,5);index=0;seen=[]
        while True:
            page=make_review_queue_page(snapshot,q,index=index,signer=signer)
            self.assertEqual(self.codec.admit('review-queue-page',canonical(page).encode()).status,'SUPPORTED_SHAPE')
            self.assertEqual(page['total_items'],17);self.assertFalse(page['personal_reconciliation_complete'])
            seen.extend(i['item_id'] for i in page['items'])
            if page['next_cursor'] is None:break
            sid,index=ReviewQueueCursor(b'x'*32).decode(page['next_cursor'],principal_id='user',query_hash=q.fingerprint)
            self.assertEqual(sid,'snapshot')
        self.assertEqual(seen,[i.item_id for i in snapshot.items]);self.assertEqual(len(set(seen)),17)
    def test_partial_view_or_empty_queue_does_not_mean_personal_reconciliation(self):
        signer=ReviewQueueCursor(b'x'*32)
        for items in ([],[self.item(i) for i in range(10)]):
            page=make_review_queue_page(self.snapshot(items),ReviewQueueQuery(3,5),index=0,signer=signer)
            self.assertFalse(page['personal_reconciliation_complete'])
            self.assertTrue(page['enumeration_complete'])
        blocked=self.snapshot([],coverage_blockers=('UNADMITTED_REVIEW_SOURCE',))
        page=make_review_queue_page(blocked,ReviewQueueQuery(3,5),index=0,signer=signer)
        self.assertFalse(page['enumeration_complete']);self.assertFalse(page['personal_reconciliation_complete'])
    def test_original_questions_and_unknown_work_are_immutable_and_unanswered_after_reads(self):
        snapshot=self.snapshot([self.item(1)]);body=snapshot.items[0].payload
        body['details']['work_status']='UNTOUCHED';body['answer']=True
        page=make_review_queue_page(snapshot,ReviewQueueQuery(3,5),index=0,signer=ReviewQueueCursor(b'x'*32))
        page['items'][0]['answer']=True
        self.assertEqual(snapshot.items[0].payload['details']['work_status'],'UNKNOWN')
        self.assertIsNone(snapshot.items[0].payload['answer'])
    def test_snapshot_hash_and_group_counts_cannot_omit_an_unanswered_item(self):
        snapshot=self.snapshot([self.item(i) for i in range(4)])
        with self.assertRaisesRegex(TransactionError,'MEMBERSHIP'):replace(snapshot,items=snapshot.items[:-1])
        h=snapshot.header;h['groups'][0]['item_count']-=1
        with self.assertRaisesRegex(TransactionError,'GROUPS'):ReviewQueueSnapshot(canonical(h),snapshot.items)
        with self.assertRaisesRegex(TransactionError,'ITEMS'):self.snapshot([self.item(1),self.item(1)])
    def test_cursor_cannot_switch_owner_query_key_index_or_signature(self):
        signer=ReviewQueueCursor(b'x'*32);q=ReviewQueueQuery(3,5);token=signer.encode('snapshot',50001,'user',q.fingerprint)
        self.assertEqual(signer.decode(token,principal_id='user',query_hash=q.fingerprint),('snapshot',50001))
        for owner,query in (('foreign',q),('user',ReviewQueueQuery(3,10))):
            with self.assertRaisesRegex(TransactionError,'SCOPE_CONFLICT'):signer.decode(token,principal_id=owner,query_hash=query.fingerprint)
        for other in (token+'=',token[:-1]+'!',token+'.extra','x'*2049):
            with self.assertRaisesRegex(TransactionError,'CURSOR_INVALID'):signer.decode(other,principal_id='user',query_hash=q.fingerprint)
        with self.assertRaises(TransactionError):ReviewQueueCursor(b'y'*32).decode(token,principal_id='user',query_hash=q.fingerprint)
    def test_snapshot_time_epoch_and_boolean_values_are_checked(self):
        for kwargs in (dict(page_size=True,target_minutes=5),dict(page_size=0,target_minutes=5),dict(page_size=3,target_minutes=False)):
            with self.assertRaises(TransactionError):ReviewQueueQuery(**kwargs)
        snapshot=self.snapshot([self.item(1)])
        for changed in (dict(expires_at=NOW.isoformat()),dict(store_revision=True),dict(last_transaction_ref='unexpected')):
            with self.assertRaises(TransactionError):ReviewQueueSnapshot(canonical(snapshot.header|changed),snapshot.items)
    def test_wire_items_cannot_claim_an_answer_or_drop_the_response_requirement(self):
        item=self.item(1)
        self.assertEqual(ReviewQueueItem.from_payload(item.payload),item)
        for changed in (dict(answer=True),dict(requires_response=False),dict(requires_response=1),dict(extra='approval'),dict(item_id='other')):
            with self.assertRaises(TransactionError):ReviewQueueItem.from_payload(item.payload|changed)

    @patch('src.application.review_queue.MAX_PAGE_BYTES',1048576)
    def test_page_byte_limit_includes_group_metadata_and_resumes_at_the_first_unreturned_item(self):
        # Three individually valid large questions fit the old item-only
        # budget, but not the actual response with its complete group index.
        heavy=[replace(self.item(i,priority=0),details_json=canonical(dict(context='x'*240000))) for i in range(3)]
        groups=[self.item(i+3,group=f'{i:05d}-'+('g'*194)) for i in range(2000)]
        q=ReviewQueueQuery(100,1);snapshot=self.snapshot(heavy+groups,q);signer=ReviewQueueCursor(b'x'*32)
        first=make_review_queue_page(snapshot,q,index=0,signer=signer)
        self.assertEqual(first['returned_count'],2)
        self.assertLessEqual(len(canonical(first).encode()),1048576)
        sid,index=signer.decode(first['next_cursor'],principal_id='user',query_hash=q.fingerprint)
        self.assertEqual((sid,index),('snapshot',2))
        second=make_review_queue_page(snapshot,q,index=index,signer=signer)
        self.assertEqual(second['items'][0]['item_id'],snapshot.items[2].item_id)
        self.assertEqual((first['total_items'],second['total_items']),(2003,2003))
        self.assertLessEqual(len(canonical(second).encode()),1048576)

    @patch('src.application.review_queue.MAX_PAGE_BYTES',1048576)
    def test_unpageable_group_metadata_rejects_the_entire_capture_instead_of_dropping_groups(self):
        items=[self.item(i,group=f'{i:05d}-'+('g'*194)) for i in range(5000)]
        with self.assertRaisesRegex(TransactionError,'PAGE_METADATA_TOO_LARGE'):
            self.snapshot(items)

    def test_large_admitted_producer_question_is_retained_in_full(self):
        item=replace(self.item(1),details_json=canonical(dict(known_intent='x'*1048576)))
        page=make_review_queue_page(self.snapshot([item]),ReviewQueueQuery(3,5),index=0,signer=ReviewQueueCursor(b'x'*32))
        self.assertEqual(len(page['items'][0]['details']['known_intent']),1048576)
        self.assertLessEqual(len(canonical(page).encode()),MAX_PAGE_BYTES)

    def test_resolved_execution_and_source_blockers_do_not_reask_known_answers(self):
        q=ReviewQueueQuery(3,5)
        awaiting=ReviewQueueItem('CLARIFICATION','resolved',2,'AWAITING_EXECUTION','Known intent',1,None,'pending')
        blocker=ReviewQueueItem('SOURCE_BLOCKER','unavailable',1,'SOURCE_SCOPE_UNCONFIGURED',None,0,None,'pending')
        page=make_review_queue_page(self.snapshot([awaiting,blocker]),q,index=0,signer=ReviewQueueCursor(b'x'*32))
        self.assertTrue(all(i['requires_response'] is False and i['answer'] is None for i in page['items']))
        self.assertEqual(self.codec.admit('review-queue-page',canonical(page).encode()).status,'SUPPORTED_SHAPE')
        bad=page.copy();bad['items']=[awaiting.payload|dict(requires_response=True)]
        self.assertNotEqual(self.codec.admit('review-queue-page',canonical(bad).encode()).status,'SUPPORTED_SHAPE')
