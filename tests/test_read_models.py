from copy import deepcopy
from datetime import datetime,timedelta,timezone
from pathlib import Path
import json
import unittest
from src.adapters.extension_contracts import load_supported_schemas
from src.adapters.prototype_codec import PrototypeJSONCodec
from src.application.definitions import canonical
from src.application.read_models import ReadQuery,ReadSnapshot,CursorSigner,admit_query,make_snapshot,make_page,task_view,semantic_changes
from src.application.task_storage import admit_storage
from src.domain.authorization import CallerIdentity
ROOT=Path(__file__).resolve().parents[1]
CODEC=PrototypeJSONCodec(load_supported_schemas(root=ROOT));NOW=datetime(2026,1,1,tzinfo=timezone.utc)
CALLER=CallerIdentity('principal','USER_COMMAND',True);SIGNER=CursorSigner(b'synthetic-read-cursor-key-00000001')
def query(view='TASKS',**kw):
    v=dict(schema_version='0.1.0-read-query',view=view,task_id='task' if view=='HISTORY' else None,filters=dict(completion=None,disposition=None,trust=None,domain=None,context=None),pending_kind=None,include_closed=False,page_size=1,cursor=None);v.update(kw);return v
def ref(key='task',kind='TASK',revision=1,state='CURRENT'):
    return dict(kind=kind,id=key,revision=revision,state=state,actual_seconds=0,transaction_ref='command',store_revision=2,pending_id=None,pending_revision=None)
def snapshot(q=None,refs=None,**kw):
    values=dict(snapshot_id='snapshot',principal_id='principal',scope_hash='a'*64,store_revision=2,last_transaction_ref='command',observed_at=NOW,expires_at=NOW+timedelta(hours=1),references=refs if refs is not None else [ref()],source_scope_state='NOT_APPLICABLE');values.update(kw)
    return make_snapshot(ReadQuery(canonical(q or query())),**values)
class ReadModelTests(unittest.TestCase):
    def admit(self,value):return admit_query(CODEC,canonical(value).encode())
    def record(self,name='aggregate-unknown-facts'):
        cases=json.loads((ROOT/'tests/fixtures/task_aggregate/cases.json').read_text(encoding='utf-8'))['cases'];v=deepcopy(next(c['payload'] for c in cases if c['id']==name));return admit_storage(CODEC,canonical(v).encode())
    def test_supported_query_views(self):
        for view in ('TASKS','HISTORY','PENDING'):self.assertEqual(self.admit(query(view)).view,view)
    def test_query_rejects_unknown_keys(self):
        with self.assertRaisesRegex(Exception,'SHAPE'):self.admit(query(secret='x'))
    def test_page_size_rejects_coercion(self):
        for value in (True,1.0,'1',0,101):
            with self.subTest(value=value),self.assertRaises(Exception):self.admit(query(page_size=value))
    def test_history_requires_task_identity(self):
        with self.assertRaises(Exception):self.admit(query('HISTORY',task_id=None))
    def test_other_views_reject_target(self):
        for view in ('TASKS','PENDING'):
            with self.assertRaises(Exception):self.admit(query(view,task_id='foreign'))
    def test_non_task_views_reject_filters(self):
        for view in ('HISTORY','PENDING'):
            v=query(view);v['filters']['domain']='study'
            with self.assertRaises(Exception):self.admit(v)
    def test_non_pending_views_reject_pending_scope(self):
        for kw in (dict(pending_kind='CLARIFICATION'),dict(include_closed=True)):
            with self.assertRaises(Exception):self.admit(query(**kw))
    def test_query_bounded_before_schema(self):
        with self.assertRaisesRegex(Exception,'SIZE_LIMIT'):admit_query(CODEC,b'x'*8193)
    def test_fingerprint_retains_filters_and_page_size_excludes_cursor(self):
        q=self.admit(query());self.assertEqual(q.fingerprint,self.admit(query(cursor='opaque')).fingerprint)
        self.assertNotEqual(q.fingerprint,self.admit(query(page_size=2)).fingerprint)
        v=query();v['filters']['trust']='UNKNOWN';self.assertNotEqual(q.fingerprint,self.admit(v).fingerprint)
    def test_query_records_detached(self):
        q=self.admit(query());v=q.as_record();v['filters']['domain']='other';self.assertIsNone(q.as_record()['filters']['domain'])
    def test_cursor_roundtrip_and_restart(self):
        q=self.admit(query());token=SIGNER.encode('snapshot',1,'principal',q.fingerprint);self.assertEqual(CursorSigner(b'synthetic-read-cursor-key-00000001').decode(token,principal_id='principal',query_hash=q.fingerprint),('snapshot',1))
    def test_cursor_binds_actor_and_query(self):
        q=self.admit(query());token=SIGNER.encode('snapshot',1,'principal',q.fingerprint)
        for principal,digest in (('other',q.fingerprint),('principal','b'*64)):
            with self.assertRaisesRegex(Exception,'SCOPE_CONFLICT'):SIGNER.decode(token,principal_id=principal,query_hash=digest)
    def test_cursor_rejects_tampering_and_changed_key(self):
        q=self.admit(query());token=SIGNER.encode('snapshot',1,'principal',q.fingerprint)
        for changed in (token+'a','!'+token,token.replace('.', '..'),token+'=',token+'\n'):
            with self.assertRaisesRegex(Exception,'CURSOR_INVALID'):SIGNER.decode(changed,principal_id='principal',query_hash=q.fingerprint)
        with self.assertRaises(Exception):CursorSigner(b'different-key-0000000000000000000').decode(token,principal_id='principal',query_hash=q.fingerprint)
    def test_cursor_key_not_implicit(self):
        for key in (None,'x'*32,b'short'):
            with self.assertRaisesRegex(Exception,'KEY_REQUIRED'):CursorSigner(key)
    def test_snapshot_owns_sorted_detached_references(self):
        refs=[ref('z'),ref('a')];snap=snapshot(refs=refs);refs[1]['id']='changed';self.assertEqual([r['id'] for r in snap.as_record()['references']],['a','z'])
    def test_snapshot_duplicate_references_rejected(self):
        with self.assertRaisesRegex(Exception,'REFERENCE_ORDER'):snapshot(refs=[ref(),ref()])
    def test_snapshot_bytes_match_record(self):
        s=snapshot();v=s.as_record();v['principal_id']='other'
        with self.assertRaisesRegex(Exception,'BYTES_DRIFT'):ReadSnapshot(s.raw_bytes,canonical(v))
    def test_snapshot_exact_lifetime_and_scope(self):
        with self.assertRaisesRegex(Exception,'TIME'):snapshot(expires_at=NOW)
        with self.assertRaisesRegex(Exception,'SCOPE_STATE'):snapshot(source_scope_state='UNKNOWN')
    def test_snapshot_references_must_match_view(self):
        with self.assertRaisesRegex(Exception,'KIND'):snapshot(refs=[ref(kind='CLARIFICATION')])
    def test_task_unknown_zero_actual_separate(self):
        unknown=self.record().aggregate.as_record();unknown['effort']['user_remaining']=None;unknown['work']['total_estimate']=None;view=task_view(admit_storage(CODEC,canonical(unknown).encode()),0);self.assertIsNone(view['user_remaining']);self.assertEqual(view['actual_seconds'],0);self.assertIsNone(view['total_estimate_seconds'])
        complete=task_view(self.record('aggregate-complete-with-unknown-historical-completion-time'),900);self.assertEqual(complete['user_remaining']['seconds'],0);self.assertEqual(complete['actual_seconds'],900);self.assertIsNone(complete['timing']['completed_at'])
    def test_task_lifecycle_trust_and_difficulty_preserved(self):
        r=self.record('aggregate-cancelled-retains-effort');v=task_view(r,900);self.assertEqual(v['disposition'],'CANCELLED');self.assertEqual(v['difficulty'],r.aggregate.as_record()['core']['difficulty']);self.assertEqual(v['trust'],r.aggregate.as_record()['core']['metadata']['trust'])
    def test_task_view_excludes_internal_payloads(self):
        view=task_view(self.record(),0);self.assertNotIn('metadata',view);self.assertNotIn('details',view);self.assertNotIn('prediction',view);self.assertNotIn('acceptance',view)
    def test_semantic_changes_exclude_revision_and_provenance_only(self):
        before=task_view(self.record(),0);after=deepcopy(before);after.update(revision=2,field_sources=[]);self.assertEqual(semantic_changes(before,after),[])
        after.update(completion='COMPLETE',actual_seconds=600);self.assertEqual(semantic_changes(before,after),['/actual_seconds','/completion'])
    def test_page_empty_has_explicit_source_coverage(self):
        for scope in ('CONFIGURED','UNCONFIGURED'):
            s=snapshot(q=query('PENDING'),refs=[],source_scope_state=scope);p=make_page(CODEC,s,[],start_index=0,signer=SIGNER,caller=CALLER).as_record();self.assertEqual(p['source_scope_state'],scope);self.assertEqual(p['items'],[]);self.assertFalse(p['has_more']);self.assertIsNone(p['next_cursor'])
    def test_page_signed_continuation_and_terminal(self):
        s=snapshot(refs=[ref('a'),ref('b')]);item=dict(kind='TASK',id='a',revision=1,state='CURRENT',data=task_view(self.record(),0)|dict(task_id='a',revision=1));p=make_page(CODEC,s,[item],start_index=0,signer=SIGNER,caller=CALLER).as_record();self.assertTrue(p['has_more']);self.assertEqual(SIGNER.decode(p['next_cursor'],principal_id='principal',query_hash=p['query_hash']),('snapshot',1))
        item=deepcopy(item);item['id']='b';item['data']['task_id']='b'
        end=make_page(CODEC,s,[item],start_index=1,signer=SIGNER,caller=CALLER).as_record();self.assertFalse(end['has_more']);self.assertIsNone(end['next_cursor'])
    def test_page_rejects_foreign_actor_and_empty_nonterminal(self):
        s=snapshot(refs=[ref('a'),ref('b')])
        with self.assertRaises(Exception):make_page(CODEC,s,[],start_index=0,signer=SIGNER,caller=CALLER)
        with self.assertRaises(Exception):make_page(CODEC,s,[],start_index=2,signer=SIGNER,caller=CallerIdentity('other','USER_COMMAND',True))
    def test_page_reference_and_task_projection_must_match(self):
        s=snapshot();item=dict(kind='TASK',id='other',revision=1,state='CURRENT',data=task_view(self.record(),0))
        with self.assertRaisesRegex(Exception,'REFERENCE_DRIFT'):make_page(CODEC,s,[item],start_index=0,signer=SIGNER,caller=CALLER)
        item['id']='task'
        with self.assertRaisesRegex(Exception,'TASK_DRIFT'):make_page(CODEC,s,[item],start_index=0,signer=SIGNER,caller=CALLER)
    def test_http_success_read_page_schema_and_dispatch(self):
        from contextlib import contextmanager
        from src.adapters.clocks import FrozenClock
        from src.adapters.prototype_http import AuthenticatedCommandTransport
        from src.adapters.postgres_transport import transport_data
        from src.application.command_transport import TransportCredential,token_digest,OPERATIONS
        from src.application.ports import PortResult
        token='synthetic-query-token-00000000001';c=TransportCredential('principal',token_digest(token),OPERATIONS,None,NOW-timedelta(minutes=1),NOW+timedelta(hours=1))
        p=make_page(CODEC,snapshot(refs=[]),[],start_index=0,signer=SIGNER,caller=CALLER)
        calls=[]
        class Backend:
            def dispatch(self,request,*,caller):calls.append(request.operation);return PortResult('SUCCESS','READ_PAGE',request.context.correlation_ref,transport_data(p))
        @contextmanager
        def factory():yield Backend()
        t=AuthenticatedCommandTransport(CODEC,clock=FrozenClock(NOW),credentials=(c,),backend_factory=factory)
        envelope=dict(schema_version='0.1.0-prototype-request',request_id='read',correlation_ref='corr',operation='QUERY_STATE',payload=canonical(query()),parameters={})
        out=t.handle(canonical(envelope).encode(),authorization='Bearer '+token);self.assertEqual(out.http_status,200);self.assertEqual(out.as_record()['data']['result'],p.as_record());self.assertEqual(calls,['QUERY_STATE'])
        envelope['payload']=canonical(query(page_size=True));self.assertEqual(t.handle(canonical(envelope).encode(),authorization='Bearer '+token).http_status,400);self.assertEqual(calls,['QUERY_STATE'])
    def test_unknown_query_version_rejected(self):
        with self.assertRaisesRegex(Exception,'SHAPE_UNSUPPORTED'):self.admit(query(schema_version='future-version'))
    def test_snapshot_reference_transaction_and_state_consistency(self):
        for change in (dict(transaction_ref=None),dict(state='OPEN'),dict(store_revision=3)):
            r=ref();r.update(change)
            with self.assertRaisesRegex(Exception,'REFERENCE'):snapshot(refs=[r])

    def test_public_provenance_accepts_full_base_pointer_length_and_unbounded_item_count_within_byte_limit(self):
        task=task_view(self.record(),0);task.update(task_id='task',revision=1,field_sources=[dict(field='/'+str(i)+'x'*490,source_ref='source') for i in range(1001)])
        # Pointer width itself must not be narrowed by the read DTO. The full
        # page still obeys the byte budget independently of array item counts.
        task['field_sources']=task['field_sources'][:1]
        item=dict(kind='TASK',id='task',revision=1,state='CURRENT',data=task)
        self.assertEqual(make_page(CODEC,snapshot(),[item],start_index=0,signer=SIGNER,caller=CALLER).as_record()['items'][0]['data']['field_sources'],task['field_sources'])
        task['field_sources']=[dict(field='/'+str(i),source_ref='source') for i in range(1001)]
        self.assertEqual(len(make_page(CODEC,snapshot(),[item],start_index=0,signer=SIGNER,caller=CALLER).as_record()['items'][0]['data']['field_sources']),1001)
