from copy import deepcopy
from dataclasses import replace
from datetime import datetime,timedelta,timezone
import json
from pathlib import Path
import unittest

from src.adapters.contract_json import ContractJSONCodec
from src.adapters.extension_contracts import load_supported_schemas
from src.adapters.packaged_contracts import load_contract_schemas
from src.application.definitions import canonical
from src.application.relationship_storage import EndpointBinding,RelationStorageRecord
from src.application.relationship_validation import GraphLimits
from src.application.stage_commands import StageCommand,StageCommandGrant,StageExecutionEvidence,StageOrderSnapshot,admit_stage_command,prepare_stage_command
from src.application.task_storage import admit_storage
from src.application.transactions import TransactionError
from src.domain.authorization import CallerIdentity
from src.domain.relationships import Endpoint,TaskRelation

ROOT=Path(__file__).resolve().parents[1]
NOW=datetime(2026,1,1,tzinfo=timezone.utc)
USER=CallerIdentity('user','USER_COMMAND',True)


class StageCommandTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.codec=ContractJSONCodec(load_supported_schemas(root=ROOT))
        cases=json.loads((ROOT/'tests/fixtures/task_aggregate/cases.json').read_text(encoding='utf-8'))['cases']
        cls.value=next(c['payload'] for c in cases if c['id']=='aggregate-stages-retain-historical-completed-stage-u')

    def fixture(self,*,operation='REWORK',stage='stage-2',fields=None,value=None):
        b=admit_storage(self.codec,canonical(deepcopy(value or self.value)).encode())
        revision=next(d['revision'] for d in b.aggregate.as_record()['stage_details'] if d['stage_id']==stage)
        c=StageCommand('command','user','grant',b.task_id,b.revision,stage,revision,operation,canonical(fields or dict(intent='SAME_OBLIGATION')))
        g=StageCommandGrant(c,'source',NOW-timedelta(minutes=2),NOW-timedelta(minutes=1),NOW+timedelta(hours=1))
        return c,g,b

    def prepare(self,c,g,b,**kw):return prepare_stage_command(self.codec,c,g,b,caller=USER,now=NOW,**kw)

    def order(self,before,*,kind='COMPLETION_ORDER',prior_complete='INCOMPLETE',completed_at=None,started_at=None):
        target=Endpoint('STAGE','stage-1');prereq=Endpoint('TASK','prerequisite')
        relation=TaskRelation('order',1,kind,prereq,target,'relation-grant')
        stored=RelationStorageRecord(relation,EndpointBinding(prereq,prereq.id,1),EndpointBinding(target,before.task_id,before.revision,1))
        facts=(StageExecutionEvidence(prereq,prereq.id,1,prior_complete,completed_at=completed_at),
            StageExecutionEvidence(target,before.task_id,before.revision,'INCOMPLETE',1,started_at=started_at))
        return StageOrderSnapshot((stored,),facts)

    def test_opt_in_roundtrip_preserves_exact_revisions_and_base_contracts(self):
        c,_,_=self.fixture();raw=canonical(c.as_record()).encode()
        self.assertEqual(admit_stage_command(self.codec,raw),c)
        self.assertEqual(admit_stage_command(self.codec,json.dumps(c.as_record(),indent=2).encode()).fingerprint,c.fingerprint)
        base=load_contract_schemas(root=ROOT);self.assertEqual(len(base),30)
        self.assertNotEqual(ContractJSONCodec(base).admit('stage-command',raw).status,'SUPPORTED_SHAPE')
        supported=load_supported_schemas(root=ROOT)
        self.assertEqual({k:supported[k] for k in base},base)

    def test_extra_approval_new_version_duplicate_keys_and_bad_origin_cannot_authorize(self):
        c,_,_=self.fixture()
        for patch in ({'approved':True},{'schema_version':'new'},{'origin':'EXTERNAL'}):
            with self.assertRaises(TransactionError):admit_stage_command(self.codec,canonical(c.as_record()|patch).encode())
        raw=canonical(c.as_record()).encode().replace(b'"operation":"REWORK"',b'"operation":"REWORK","operation":"COMPLETE"')
        with self.assertRaises(TransactionError):admit_stage_command(self.codec,raw)

    def test_constructor_rejects_boolean_revision_unbounded_effort_and_unrelated_fields(self):
        c,_,_=self.fixture()
        for options in (dict(expected_revision=True),dict(expected_stage_revision=0),dict(expected_stage_revision=2**63),dict(fields_json=canonical(dict(title='other'))),dict(fields_json=canonical(dict(parent_remaining_seconds=True))),dict(fields_json=canonical(dict(stage_remaining_seconds=2**63)))):
            with self.assertRaises(TransactionError):replace(c,**options)

    def test_exact_independent_user_authority_is_required(self):
        c,g,b=self.fixture()
        with self.assertRaisesRegex(TransactionError,'INDEPENDENT_GRANT'):self.prepare(c,None,b)
        with self.assertRaisesRegex(TransactionError,'EXACT_SCOPE'):self.prepare(c,replace(g,command=replace(c,stage_id='stage-1')),b)
        for caller in (CallerIdentity('foreign','USER_COMMAND',True),CallerIdentity('user','EXTERNAL',True),CallerIdentity('user','USER_COMMAND',False),CallerIdentity('user','RELATIONSHIP_RULE',True)):
            with self.assertRaisesRegex(TransactionError,'TRUSTED_USER'):prepare_stage_command(self.codec,c,g,b,caller=caller,now=NOW)

    def test_inactive_expired_future_grant_and_future_source_fail_without_effects(self):
        c,g,b=self.fixture()
        for grant in (replace(g,active=False),replace(g,expires_at=NOW),replace(g,issued_at=NOW+timedelta(seconds=1))):
            with self.assertRaises(TransactionError):self.prepare(c,grant,b)
        with self.assertRaisesRegex(TransactionError,'FUTURE_OBSERVATION'):self.prepare(c,replace(g,source_observed_at=NOW+timedelta(seconds=1)),b)

    def test_parent_and_stage_versions_are_separately_checked(self):
        c,g,b=self.fixture()
        for changed,code in ((replace(c,expected_revision=2),'STALE_PARENT'),(replace(c,expected_stage_revision=1),'STALE_TARGET'),(replace(c,stage_id='absent'),'UNKNOWN_TARGET'),(replace(c,task_id='foreign'),'UNKNOWN_PARENT')):
            with self.assertRaisesRegex(TransactionError,code):self.prepare(changed,replace(g,command=changed),b)

    def test_ambiguous_correction_and_new_obligation_are_effect_free_pending(self):
        for intent in ('UNRESOLVED','CORRECTION','NEW_OBLIGATION'):
            c,g,b=self.fixture(fields=dict(intent=intent));p=self.prepare(c,g,b)
            self.assertEqual(p.state,'PENDING');self.assertIsNone(p.record);self.assertIsNone(p.transition);self.assertEqual(p.estimates,())
        self.assertEqual(p.code,'STAGE_NEW_OBLIGATION_REQUIRES_CREATION')

    def test_cancelled_parent_requires_explicit_reactivation_instead_of_implicit_change(self):
        value=deepcopy(self.value);value['core']['disposition']=value['effort']['disposition']='CANCELLED'
        c,g,b=self.fixture(value=value);out=self.prepare(c,g,b)
        self.assertEqual(out.code,'STAGE_PARENT_INACTIVE');self.assertIsNone(out.record)

    def test_genuine_rework_keeps_identity_positive_parent_u_and_other_stages(self):
        c,g,b=self.fixture();old=b.aggregate.as_record();p=self.prepare(c,g,b);v=p.record.aggregate.as_record()
        self.assertEqual(v['core']['completion'],'INCOMPLETE');self.assertEqual(v['effort']['user_remaining'],old['effort']['user_remaining'])
        self.assertEqual(v['effort']['stages'][1]['stage_id'],'stage-2');self.assertEqual(v['effort']['stages'][1]['completion'],'INCOMPLETE')
        self.assertIsNone(v['effort']['stages'][1]['user_remaining']);self.assertEqual(v['effort']['stages'][0],old['effort']['stages'][0])
        self.assertEqual(v['stage_details'][1]['revision'],old['stage_details'][1]['revision']+1)
        self.assertEqual(v['work'],old['work']);self.assertEqual(p.estimates,());self.assertFalse(hasattr(p,'permit'));self.assertEqual(b.aggregate.as_record(),old)

    def test_complete_parent_reopens_with_confirmed_remaining_and_retains_old_time_in_transition(self):
        value=deepcopy(self.value);value['core']['completion']=value['effort']['completion']='COMPLETE';value['effort']['user_remaining']['seconds']=0
        value['effort']['stages'][0]['completion']='COMPLETE';value['timing']['completed_at']='2025-12-31T12:00:00+08:00'
        c,g,b=self.fixture(value=value,fields=dict(intent='SAME_OBLIGATION',parent_remaining_seconds=900,stage_remaining_seconds=600))
        p=self.prepare(c,g,b);v=p.record.aggregate.as_record()
        self.assertEqual(v['core']['completion'],'INCOMPLETE');self.assertIsNone(v['timing']['completed_at'])
        self.assertEqual(p.transition['previous_parent_completed_at'],value['timing']['completed_at'])
        self.assertEqual(v['effort']['user_remaining']['seconds'],900);self.assertEqual(v['effort']['stages'][1]['user_remaining']['seconds'],600)
        self.assertEqual([o.seconds for o in p.estimates],[900,600]);self.assertEqual(p.record.aggregate.budget(at=NOW).seconds,900)

    def test_unknown_zero_or_completed_parent_needs_new_estimate_without_invented_u(self):
        for remaining in (None,0):
            value=deepcopy(self.value)
            value['effort']['user_remaining']=None if remaining is None else dict(value['effort']['user_remaining'],seconds=0)
            c,g,b=self.fixture(value=value);out=self.prepare(c,g,b)
            self.assertEqual(out.code,'STAGE_REWORK_REMAINING_REQUIRED');self.assertIsNone(out.record)
        for supplied in (None,0):
            c,g,b=self.fixture(fields=dict(intent='SAME_OBLIGATION',parent_remaining_seconds=supplied))
            self.assertEqual(self.prepare(c,g,b).state,'PENDING')

    def test_rework_invalidates_prediction_and_replaces_only_affected_provenance(self):
        value=deepcopy(self.value);value['effort']['prediction']=dict(seconds=100,prediction_id='model-estimate',model_ref=dict(id='m',version='1'),task_revision=1,computed_at=NOW.isoformat(),valid_until=(NOW+timedelta(hours=1)).isoformat(),valid=True,applicable=True)
        value['provenance']=[dict(field='/effort/stages/1/user_remaining/seconds',source_ref='old-u'),dict(field='/core/title',source_ref='old-title')]
        c,g,b=self.fixture(value=value);v=self.prepare(c,g,b).record.aggregate.as_record()
        self.assertFalse(v['effort']['prediction']['valid']);self.assertEqual(v['effort']['prediction']['seconds'],100)
        prov={p['field']:p['source_ref'] for p in v['provenance']};self.assertEqual(prov['/core/title'],'old-title');self.assertNotIn('/effort/stages/1/user_remaining/seconds',prov)
        self.assertEqual(prov['/effort/stages/1/user_remaining'],'source')

    def test_stage_completion_zeroes_only_stage_and_does_not_complete_parent(self):
        c,g,b=self.fixture(operation='COMPLETE',stage='stage-1');old=b.aggregate.as_record();p=self.prepare(c,g,b);v=p.record.aggregate.as_record()
        self.assertEqual(v['effort']['stages'][0]['completion'],'COMPLETE');self.assertEqual(v['effort']['stages'][0]['user_remaining']['seconds'],0)
        self.assertEqual(v['core']['completion'],'INCOMPLETE');self.assertEqual(v['effort']['user_remaining'],old['effort']['user_remaining']);self.assertEqual(v['timing'],old['timing'])
        self.assertEqual(len(p.estimates),1);self.assertEqual(p.estimates[0].observed_at,g.source_observed_at);self.assertIsNone(p.transition['reported_completed_at'])

    def test_reported_completion_time_keeps_offset_microseconds_and_stays_out_of_parent_time(self):
        stamp='2025-12-31T23:59:59.123456+08:00';c,g,b=self.fixture(operation='COMPLETE',stage='stage-1',fields=dict(intent='SAME_OBLIGATION',completed_at=stamp))
        p=self.prepare(c,g,b);self.assertEqual(p.transition['reported_completed_at'],stamp);self.assertIsNone(p.record.aggregate.as_record()['timing']['completed_at'])
        changed=replace(c,fields_json=canonical(dict(intent='SAME_OBLIGATION',completed_at='2026-01-02T00:00:00Z')))
        with self.assertRaisesRegex(TransactionError,'REPORTED_TIME_CONFLICT'):self.prepare(changed,replace(g,command=changed),b)

    def test_out_of_order_completion_records_truth_and_incomplete_prerequisite_without_rewriting_it(self):
        c,g,b=self.fixture(operation='COMPLETE',stage='stage-1',fields=dict(intent='SAME_OBLIGATION',completed_at='2025-12-31T23:59:00Z'))
        order=self.order(b);p=self.prepare(c,g,b,order=order)
        self.assertEqual(p.record.aggregate.as_record()['effort']['stages'][0]['completion'],'COMPLETE')
        self.assertEqual(p.transition['issues'][0]['code'],'PREREQUISITE_INCOMPLETE');self.assertEqual(order.executions[0].completion,'INCOMPLETE')
        self.assertEqual(p.transition['order_snapshot'][0]['execution']['task_id'],'prerequisite')

    def test_exact_times_distinguish_order_violation_missing_evidence_and_satisfied_order(self):
        c,g,b=self.fixture(operation='COMPLETE',stage='stage-1',fields=dict(intent='SAME_OBLIGATION',completed_at='2025-12-31T23:59:00Z'))
        for prior,code in ((NOW,'ORDER_VIOLATION'),(None,'ORDER_EVIDENCE_MISSING'),(NOW-timedelta(minutes=2),None)):
            p=self.prepare(c,g,b,order=self.order(b,prior_complete='COMPLETE',completed_at=prior))
            self.assertEqual(p.transition['issues'][0]['code'] if p.transition['issues'] else None,code)

    def test_start_prerequisite_uses_actual_start_while_soft_sequence_never_blocks_truth(self):
        c,g,b=self.fixture(operation='COMPLETE',stage='stage-1')
        order=self.order(b,kind='START_PREREQUISITE',prior_complete='COMPLETE',completed_at=NOW-timedelta(minutes=1),started_at=NOW-timedelta(minutes=2))
        self.assertEqual(self.prepare(c,g,b,order=order).transition['issues'][0]['code'],'ORDER_VIOLATION')
        order=self.order(b,kind='SOFT_SEQUENCE');self.assertEqual(self.prepare(c,g,b,order=order).transition['issues'],[])

    def test_unresolved_order_evidence_is_effect_free_and_drift_is_rejected(self):
        c,g,b=self.fixture(operation='COMPLETE',stage='stage-1');order=self.order(b)
        pending=self.prepare(c,g,b,order=replace(order,executions=order.executions[1:]));self.assertEqual(pending.code,'STAGE_ORDER_EVIDENCE_UNRESOLVED');self.assertIsNone(pending.record)
        changed=replace(order.executions[1],task_revision=2)
        with self.assertRaisesRegex(TransactionError,'TARGET_DRIFT'):self.prepare(c,g,b,order=replace(order,executions=(order.executions[0],changed)))

    def test_snapshot_duplicate_ids_and_resource_limits_are_explicit(self):
        _,_,b=self.fixture();order=self.order(b)
        for options in (dict(relations=order.relations*2),dict(executions=order.executions*2)):
            with self.assertRaisesRegex(TransactionError,'DUPLICATE_IDENTITY'):replace(order,**options)
        with self.assertRaisesRegex(TransactionError,'RESOURCE_LIMIT'):replace(order,limits=GraphLimits(max_endpoints=1))
        with self.assertRaisesRegex(TransactionError,'PAYLOAD_LIMIT'):replace(order,limits=GraphLimits(max_payload_bytes=1))

    def test_same_command_repeated_preparation_is_immutable_and_deterministic(self):
        c,g,b=self.fixture();one=self.prepare(c,g,b);two=self.prepare(c,g,b)
        self.assertEqual(one,two);transition=one.transition;transition['command']['fields']['intent']='NEW_OBLIGATION';self.assertEqual(one.transition['command']['fields']['intent'],'SAME_OBLIGATION')
        with self.assertRaisesRegex(TransactionError,'REQUIRES_COMPLETED'):self.prepare(replace(c,stage_id='stage-1',expected_stage_revision=1),replace(g,command=replace(c,stage_id='stage-1',expected_stage_revision=1)),b)


if __name__=='__main__':unittest.main()
