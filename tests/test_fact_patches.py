from copy import deepcopy
from dataclasses import replace
from datetime import datetime,timedelta,timezone
import json
from pathlib import Path
import tempfile
import unittest

from src.adapters.contract_json import ContractJSONCodec
from src.adapters.extension_contracts import load_supported_schemas,load_extension_schemas
from src.adapters.packaged_contracts import ContractResourceError,load_contract_schemas
from src.application.definitions import canonical
from src.application.fact_patches import FactPatch,FactPatchGrant,admit_fact_patch,prepare_fact_patch
from src.application.task_storage import admit_storage
from src.application.transactions import TransactionError

ROOT=Path(__file__).resolve().parents[1]
NOW=datetime(2026,1,1,tzinfo=timezone.utc)


class FactPatchTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.codec=ContractJSONCodec(load_supported_schemas(root=ROOT))
        cls.base=json.loads((ROOT/'tests/fixtures/task_aggregate/cases.json').read_text(encoding='utf-8'))['cases'][0]['payload']

    def values(self,fields=None,value=None):
        before=admit_storage(self.codec,canonical(value or deepcopy(self.base)).encode())
        patch=FactPatch('patch','principal','grant',before.task_id,before.revision,canonical(fields or dict(importance=4)))
        grant=FactPatchGrant(patch,'statement',NOW-timedelta(minutes=1),NOW+timedelta(hours=1),NOW)
        return patch,grant,before

    def prepare(self,p,g,b):return prepare_fact_patch(self.codec,p,g,b,now=NOW)

    def test_opt_in_does_not_replace_or_change_any_base_schema(self):
        base=load_contract_schemas(root=ROOT);all_schemas=load_supported_schemas(root=ROOT)
        self.assertEqual(len(base),30);self.assertEqual(len(all_schemas),44)
        self.assertEqual({k:all_schemas[k] for k in base},base)
        p,_,_=self.values();raw=canonical(p.as_record()).encode()
        self.assertNotEqual(ContractJSONCodec(base).admit('task-fact-patch',raw).status,'SUPPORTED_SHAPE')
        self.assertEqual(admit_fact_patch(self.codec,raw),p)
        self.assertEqual(admit_fact_patch(self.codec,json.dumps(p.as_record(),indent=2).encode()),p)

    def test_shape_rejects_lifecycle_total_actual_stage_approval_and_unknown_version(self):
        p,_,_=self.values()
        for name in ('completion','disposition','total_estimate_seconds','actual_seconds','stages','approved'):
            v=p.as_record();v['fields'][name]=True
            with self.subTest(name=name),self.assertRaises(TransactionError):admit_fact_patch(self.codec,canonical(v).encode())
        v=p.as_record();v['schema_version']='future'
        with self.assertRaises(TransactionError):admit_fact_patch(self.codec,canonical(v).encode())

    def test_rejects_duplicate_fields_bad_dates_missing_timezone_and_excess_precision(self):
        p,_,_=self.values();raw=canonical(p.as_record()).encode().replace(b'"importance":4',b'"importance":4,"importance":5')
        with self.assertRaises(TransactionError):admit_fact_patch(self.codec,raw)
        for time in ('2026-02-30','2026-01-01T12:00:00','2026-01-01T12:00:00.1234567Z','tomorrow'):
            with self.subTest(time=time),self.assertRaises(TransactionError):self.values(dict(deadline=time))

    def test_exact_scope_active_time_and_current_revision_are_required(self):
        p,g,b=self.values()
        for grant,code in ((replace(g,active=False),'INACTIVE'),(replace(g,issued_at=NOW+timedelta(minutes=1)),'INACTIVE'),
            (replace(g,source_observed_at=NOW+timedelta(seconds=1)),'FUTURE'),
            (replace(g,patch=replace(p,fields_json=canonical(dict(importance=5)))),'EXACT_SCOPE')):
            with self.subTest(code=code),self.assertRaisesRegex(TransactionError,code):self.prepare(p,grant,b)
        p=replace(p,expected_revision=p.expected_revision+1);g=replace(g,patch=p)
        with self.assertRaisesRegex(TransactionError,'STALE_STATE_VERSION'):self.prepare(p,g,b)

    def test_only_requested_facts_change_and_prior_record_remains_detached(self):
        p,g,b=self.values(dict(title='New title',importance=5,difficulty=dict(thinking_depth=4,repetitive_volume=2,new_learning_load=1)))
        original=b.aggregate.as_record();after=self.prepare(p,g,b).record.aggregate.as_record()
        self.assertEqual(after['work'],original['work']);self.assertEqual(after['timing'],original['timing'])
        self.assertEqual(after['stage_details'],original['stage_details']);self.assertEqual(after['core']['completion'],original['core']['completion'])
        self.assertEqual(b.aggregate.as_record(),original);self.assertEqual(after['core']['revision'],b.revision+1)
        provenance={v['field']:v['source_ref'] for v in after['provenance']}
        self.assertEqual(provenance['/core/importance'],'statement');self.assertEqual(provenance['/core/title'],'statement')

    def test_date_only_is_beijing_2359_with_declared_policy(self):
        p,g,b=self.values(dict(deadline='2026-10-13'));out=self.prepare(p,g,b);due=out.dues[0].value
        self.assertEqual(due.instant.isoformat(),'2026-10-13T23:59:00+08:00');self.assertEqual(due.default_policy_ref,'D-075-date-only-2359')
        self.assertEqual(out.record.aggregate.as_record()['timing']['deadline']['value'],due.as_record())

    def test_explicit_time_offset_and_microseconds_preserved_and_clear_does_not_erase_history(self):
        for time in ('2026-10-13T13:30:00+08:00','2026-10-13T05:30:00.123456Z','2026-10-13T01:30:00-04:00'):
            p,g,b=self.values(dict(deadline=time));out=self.prepare(p,g,b);due=out.dues[0].value
            self.assertEqual(due.original_value,time);self.assertIsNone(due.default_policy_ref)
            p=replace(p,command_id='clear',expected_revision=out.record.revision,fields_json=canonical(dict(deadline=None)))
            cleared=self.prepare(p,replace(g,patch=p),out.record)
            self.assertIsNone(cleared.record.aggregate.as_record()['timing']['deadline']);self.assertEqual(cleared.dues,())
            self.assertIsNotNone(out.record.aggregate.as_record()['timing']['deadline'])

    def test_known_u_zero_and_unknown_are_distinct_and_do_not_complete_task(self):
        for seconds in (0,3600,None):
            p,g,b=self.values(dict(user_remaining_seconds=seconds));out=self.prepare(p,g,b);v=out.record.aggregate.as_record()
            self.assertEqual(v['core']['completion'],'INCOMPLETE')
            if seconds is None:self.assertIsNone(v['effort']['user_remaining']);self.assertEqual(out.estimates,())
            else:self.assertEqual(v['effort']['user_remaining']['seconds'],seconds);self.assertEqual(out.estimates[0].observed_at,NOW)
        p,g,b=self.values(dict(user_remaining_seconds=10))
        with self.assertRaisesRegex(TransactionError,'OBSERVATION_TIME_REQUIRED'):self.prepare(p,replace(g,source_observed_at=None),b)

    def test_expiration_condition_required_and_expired_identity_not_rewritten(self):
        p,g,b=self.values(dict(requiredness='EXPIRING'))
        with self.assertRaisesRegex(TransactionError,'CONDITION_REQUIRED'):self.prepare(p,g,b)
        p=replace(p,fields_json=canonical(dict(requiredness='EXPIRING',expiration_condition_ref='class-start')))
        out=self.prepare(p,replace(g,patch=p),b);self.assertEqual(out.record.aggregate.as_record()['core']['expiration']['condition_ref'],'class-start')
        v=out.record.aggregate.as_record();v['provenance'].append(dict(field='/core/expiration/condition_ref',source_ref='old-condition'))
        before=admit_storage(self.codec,canonical(v).encode())
        p=replace(p,command_id='non-expiring',expected_revision=before.revision,fields_json=canonical(dict(requiredness='OPTIONAL')))
        after=self.prepare(p,replace(g,patch=p),before).record.aggregate.as_record()
        self.assertIsNone(after['core']['expiration'])
        self.assertNotIn('/core/expiration/condition_ref',{v['field'] for v in after['provenance']})

    def test_bad_values_and_typed_grant_cannot_come_from_approval_flag(self):
        for fields in (dict(user_remaining_seconds=True),dict(importance=0),dict(difficulty=dict(thinking_depth=2)),dict(title='  ')):
            with self.subTest(fields=fields),self.assertRaises(TransactionError):self.values(fields)
        p,g,b=self.values()
        with self.assertRaisesRegex(TransactionError,'UNREGISTERED_AUTHORITY'):self.prepare(p,{'approved':True},b)

    def test_extension_loader_rejects_traversal_schema_drift_and_version_drift(self):
        registry=json.loads((ROOT/'formats/extension-registry.json').read_text(encoding='utf-8'))
        raw=(ROOT/'formats/extensions/task-fact-patch.schema.json').read_bytes()
        with tempfile.TemporaryDirectory(dir=ROOT/'.local-state') as temp:
            root=Path(temp);(root/'formats/extensions').mkdir(parents=True)
            (root/'formats/extensions/task-fact-patch.schema.json').write_bytes(raw)
            for mutation in ('path','schema_hash','supported_versions'):
                v=deepcopy(registry);v['contracts'][0][mutation]={'path':'../outside','schema_hash':'0'*64,'supported_versions':['future']}[mutation]
                (root/'formats/extension-registry.json').write_text(json.dumps(v),encoding='utf-8')
                with self.subTest(mutation=mutation),self.assertRaises(ContractResourceError):load_extension_schemas(root=root)

    def test_cleared_object_child_provenance_stays_in_history_and_current_null_has_new_source(self):
        p,g,b=self.values(dict(deadline='2026-10-13',user_remaining_seconds=100))
        initial=self.prepare(p,g,b).record.aggregate.as_record()
        initial['provenance'] += [dict(field='/timing/deadline/value/original_value',source_ref='old-deadline-source'),
            dict(field='/effort/user_remaining/seconds',source_ref='old-estimate-source')]
        b=admit_storage(self.codec,canonical(initial).encode())
        p=replace(p,command_id='clear-child',expected_revision=b.revision,fields_json=canonical(dict(deadline=None,user_remaining_seconds=None)))
        out=self.prepare(p,replace(g,patch=p),b).record.aggregate.as_record()
        sources={v['field']:v['source_ref'] for v in out['provenance']}
        self.assertNotIn('/timing/deadline/value/original_value',sources);self.assertNotIn('/effort/user_remaining/seconds',sources)
        self.assertEqual(sources['/timing/deadline'],'statement');self.assertEqual(b.aggregate.as_record(),initial)

    def test_existing_prediction_retained_but_invalidated_for_new_revision(self):
        v=deepcopy(self.base)
        prediction=dict(seconds=300,prediction_id='prediction',model_ref=dict(id='model',version='1'),
            task_revision=v['core']['revision'],computed_at=NOW.isoformat(),valid_until=(NOW+timedelta(hours=1)).isoformat(),valid=True,applicable=True)
        v['effort']['prediction']=prediction;p,g,b=self.values(value=v)
        after=self.prepare(p,g,b).record.aggregate.as_record()['effort']['prediction']
        self.assertEqual(after,dict(prediction,valid=False,applicable=False));self.assertEqual(b.aggregate.as_record()['effort']['prediction'],prediction)

    def test_complete_task_cannot_acquire_unknown_or_positive_u_without_reopening(self):
        cases=json.loads((ROOT/'tests/fixtures/task_aggregate/cases.json').read_text(encoding='utf-8'))['cases']
        v=deepcopy(next(c['payload'] for c in cases if c['id']=='aggregate-complete-with-unknown-historical-completion-time'))
        for seconds in (None,10):
            p,g,b=self.values(dict(user_remaining_seconds=seconds),v)
            with self.subTest(seconds=seconds),self.assertRaisesRegex(TransactionError,'COMPLETED_REMAINING_CONFLICT'):self.prepare(p,g,b)
        p,g,b=self.values(dict(user_remaining_seconds=0),v)
        self.assertEqual(self.prepare(p,g,b).record.aggregate.as_record()['core']['completion'],'COMPLETE')

    def test_stage_facts_are_unchanged_when_parent_ratings_are_corrected(self):
        cases=json.loads((ROOT/'tests/fixtures/task_aggregate/cases.json').read_text(encoding='utf-8'))['cases']
        v=deepcopy(next(c['payload'] for c in cases if c['id']=='aggregate-stages-retain-historical-completed-stage-u'))
        p,g,b=self.values(dict(importance=2),v);out=self.prepare(p,g,b).record.aggregate.as_record()
        self.assertEqual(out['effort']['stages'],v['effort']['stages']);self.assertEqual(out['stage_details'],v['stage_details'])


if __name__=='__main__':unittest.main()
