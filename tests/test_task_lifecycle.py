from copy import deepcopy
from dataclasses import replace
from datetime import datetime,timedelta,timezone
import json
from pathlib import Path
import unittest

from src.adapters.contract_json import ContractJSONCodec
from src.application.command_validation import validate_effects
from src.application.definitions import canonical
from src.application.ports import AggregateKey,CommitRequest,RecordWrite,RequestContext
from src.application.task_lifecycle import admit_lifecycle_command,prepare_lifecycle_task
from src.application.task_storage import admit_storage
from src.application.transactions import TransactionError
from src.domain.authorization import AuthorityGrant,CallerIdentity,Command,change
from tools.check_contract_registry import trusted_schemas

ROOT=Path(__file__).resolve().parents[1];NOW=datetime(2026,1,1,tzinfo=timezone.utc)
CALLER=CallerIdentity('principal','USER_COMMAND',True)


class LifecycleTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.codec=ContractJSONCodec(trusted_schemas())
        cls.cases=json.loads((ROOT/'tests/fixtures/task_aggregate/cases.json').read_text(encoding='utf-8'))['cases']

    def setup_values(self,operation='COMPLETE',name='aggregate-unknown-facts',*,value=None,fields=None):
        v=deepcopy(value or next(c['payload'] for c in self.cases if c['id']==name))
        before=admit_storage(self.codec,canonical(v).encode())
        c=Command('command','principal','USER_COMMAND','grant',(change(before.task_id,before.revision,'UPDATE_TASK',
            fields or (dict(completion='COMPLETE') if operation=='COMPLETE' else dict(disposition='CANCELLED'))),))
        g=AuthorityGrant('grant','principal','USER_COMMAND',c.command_id,c.changes,'statement',NOW-timedelta(minutes=1),expires_at=NOW+timedelta(hours=1))
        return admit_lifecycle_command(self.codec,canonical(c.as_record()).encode(),operation),g,before

    def prepare(self,a,g,b,operation='COMPLETE',**kw):
        options=dict(operation=operation,caller=CALLER,source_observed_at=NOW-timedelta(seconds=10),now=NOW);options.update(kw)
        out=prepare_lifecycle_task(self.codec,a,g,b,**options)
        request=CommitRequest(RequestContext(a.command.command_id,'correlation'),a.command.principal_id,1,
            (RecordWrite(AggregateKey('TASK',b.task_id),b.revision,out.record.raw_bytes.decode()),),'audit',g.evidence_ref)
        validate_effects(self.codec,a,request,caller=CALLER,grant=g,records=(b,),observations=tuple(o.row for o in out.estimates),now=NOW)
        return out

    def test_completion_is_exact_user_confirmation_zero_u_and_truthful_unknown_work_time(self):
        a,g,b=self.setup_values();out=self.prepare(a,g,b);v=out.record.aggregate.as_record()
        self.assertEqual(v['core']['completion'],'COMPLETE');self.assertEqual(v['effort']['completion'],'COMPLETE')
        self.assertEqual(v['effort']['user_remaining']['seconds'],0);self.assertEqual(len(out.estimates),1)
        self.assertIsNone(v['timing']['completed_at']);self.assertEqual(out.estimates[0].observed_at,NOW-timedelta(seconds=10))
        self.assertEqual(v['work'],b.aggregate.as_record()['work']);self.assertEqual(b.revision,1)

    def test_parent_completion_completes_only_incomplete_stages_with_zero_observations(self):
        a,g,b=self.setup_values(name='aggregate-stages-retain-historical-completed-stage-u');before=b.aggregate.as_record();out=self.prepare(a,g,b)
        after=out.record.aggregate.as_record();old_details={s['stage_id']:s for s in before['stage_details']}
        self.assertEqual(len(out.estimates),1+sum(s['completion']=='INCOMPLETE' for s in before['effort']['stages']))
        for old,new in zip(before['effort']['stages'],after['effort']['stages']):
            d=next(s for s in after['stage_details'] if s['stage_id']==old['stage_id'])
            if old['completion']=='COMPLETE':self.assertEqual(new,old);self.assertEqual(d,old_details[old['stage_id']])
            else:
                self.assertEqual(new['completion'],'COMPLETE');self.assertEqual(new['user_remaining']['seconds'],0)
                self.assertEqual(d['revision'],old_details[old['stage_id']]['revision']+1)
        self.assertEqual(out.record.aggregate.budget(at=NOW).seconds,0)

    def test_already_completed_parent_is_harmless_and_creates_no_new_zero_observations(self):
        a,g,b=self.setup_values(name='aggregate-complete-with-unknown-historical-completion-time');out=self.prepare(a,g,b)
        self.assertEqual(out.estimates,());self.assertEqual(out.record.aggregate.as_record()['effort']['user_remaining'],b.aggregate.as_record()['effort']['user_remaining'])
        self.assertEqual(out.record.aggregate.as_record()['timing'],b.aggregate.as_record()['timing'])

    def test_explicit_reconfirmed_zero_may_create_an_observation_without_actual_effort(self):
        a,g,b=self.setup_values(name='aggregate-complete-with-unknown-historical-completion-time',fields=dict(completion='COMPLETE',user_remaining_seconds=0))
        out=self.prepare(a,g,b);self.assertEqual(len(out.estimates),1);self.assertEqual(out.estimates[0].row[2],'USER_REMAINING')

    def test_cancellation_retains_completion_effort_stages_dates_and_known_positive_u(self):
        a,g,b=self.setup_values('CANCEL',name='aggregate-stages-retain-historical-completed-stage-u');out=self.prepare(a,g,b,'CANCEL')
        old=b.aggregate.as_record();v=out.record.aggregate.as_record()
        self.assertEqual(v['core']['completion'],old['core']['completion']);self.assertEqual(v['core']['disposition'],'CANCELLED')
        self.assertEqual(v['effort']['user_remaining'],old['effort']['user_remaining']);self.assertEqual(v['effort']['stages'],old['effort']['stages'])
        self.assertEqual(v['stage_details'],old['stage_details']);self.assertEqual(v['timing'],old['timing']);self.assertEqual(out.estimates,())

    def test_cancelling_a_previously_completed_task_preserves_orthogonal_completion(self):
        a,g,b=self.setup_values('CANCEL',name='aggregate-complete-with-unknown-historical-completion-time');out=self.prepare(a,g,b,'CANCEL')
        self.assertEqual(out.record.aggregate.as_record()['core']['completion'],'COMPLETE')
        self.assertEqual(out.record.aggregate.as_record()['core']['disposition'],'CANCELLED');self.assertEqual(out.estimates,())

    def test_submission_external_caller_and_unrelated_fields_are_rejected(self):
        a,g,b=self.setup_values()
        with self.assertRaisesRegex(TransactionError,'EXTERNAL|CALLER_SCOPE'):self.prepare(a,g,b,caller=CallerIdentity('principal','EXTERNAL',True))
        for fields in (dict(completion='COMPLETE',title='Smuggled'),dict(completion='COMPLETE',user_remaining_seconds=10),dict(completion='INCOMPLETE')):
            with self.subTest(fields=fields),self.assertRaises(TransactionError):self.setup_values(fields=fields)
        with self.assertRaisesRegex(TransactionError,'CANCELLATION_SCOPE'):self.setup_values('CANCEL',fields=dict(disposition='CANCELLED',user_remaining_seconds=0))

    def test_stale_task_inactive_or_changed_exact_grant_cannot_assert_completion(self):
        a,g,b=self.setup_values();c=replace(a.command,changes=(change(b.task_id,2,'UPDATE_TASK',dict(completion='COMPLETE')),))
        admitted=admit_lifecycle_command(self.codec,canonical(c.as_record()).encode(),'COMPLETE')
        with self.assertRaisesRegex(TransactionError,'STALE_STATE_VERSION'):self.prepare(admitted,replace(g,changes=c.changes),b)
        with self.assertRaisesRegex(TransactionError,'INACTIVE_AUTHORITY'):self.prepare(a,replace(g,active=False),b)
        with self.assertRaisesRegex(TransactionError,'EXACT_CHANGE_SCOPE'):self.prepare(a,replace(g,changes=(change(b.task_id,1,'UPDATE_TASK',dict(completion='COMPLETE',user_remaining_seconds=0)),)),b)

    def test_cancelled_or_expired_completion_requires_explicit_reactivation(self):
        v=deepcopy(self.cases[0]['payload']);v['core']['disposition']=v['effort']['disposition']='CANCELLED'
        a,g,b=self.setup_values(value=v)
        with self.assertRaisesRegex(TransactionError,'REACTIVATION_REQUIRED'):self.prepare(a,g,b)
        a,g,b=self.setup_values(value=v,fields=dict(completion='COMPLETE',disposition='ACTIVE'))
        self.assertEqual(self.prepare(a,g,b).record.aggregate.as_record()['core']['disposition'],'ACTIVE')
        a,g,b=self.setup_values(name='aggregate-expired-retains-positive-u',fields=dict(completion='COMPLETE',disposition='ACTIVE'))
        out=self.prepare(a,g,b);self.assertIsNone(out.record.aggregate.as_record()['core']['expiration']['notice_ref'])
        self.assertIsNotNone(b.aggregate.as_record()['core']['expiration']['notice_ref'])

    def test_expired_cancellation_preserves_notice_history_and_keeps_condition(self):
        a,g,b=self.setup_values('CANCEL',name='aggregate-expired-retains-positive-u');out=self.prepare(a,g,b,'CANCEL')
        old=b.aggregate.as_record();v=out.record.aggregate.as_record()
        self.assertEqual(v['core']['disposition'],'CANCELLED');self.assertEqual(v['core']['expiration']['condition_ref'],old['core']['expiration']['condition_ref'])
        self.assertIsNone(v['core']['expiration']['notice_ref']);self.assertEqual(v['effort']['user_remaining'],old['effort']['user_remaining'])

    def test_current_actual_completion_time_is_retained_not_replaced_by_confirmation(self):
        a,g,b=self.setup_values(name='aggregate-complete-with-unknown-historical-completion-time')
        v=b.aggregate.as_record();v['timing']['completed_at']='2025-12-29T13:00:00+08:00'
        a,g,b=self.setup_values(value=v);out=self.prepare(a,g,b)
        self.assertEqual(out.record.aggregate.as_record()['timing']['completed_at'],v['timing']['completed_at'])

    def test_known_zero_observation_requires_nonfuture_aware_time(self):
        a,g,b=self.setup_values()
        for timestamp in (None,NOW+timedelta(seconds=1),datetime(2026,1,1)):
            with self.subTest(timestamp=timestamp),self.assertRaisesRegex(TransactionError,'SOURCE_OBSERVATION_TIME_REQUIRED'):
                self.prepare(a,g,b,source_observed_at=timestamp)

    def test_prediction_retained_but_no_longer_eligible_for_new_task_revision(self):
        v=deepcopy(self.cases[0]['payload']);v['effort']['prediction']=dict(seconds=300,prediction_id='prediction',model_ref=dict(id='model',version='1'),
            task_revision=1,computed_at=NOW.isoformat(),valid_until=(NOW+timedelta(hours=1)).isoformat(),valid=True,applicable=True)
        a,g,b=self.setup_values(value=v);out=self.prepare(a,g,b)
        self.assertEqual(out.record.aggregate.as_record()['effort']['prediction'],dict(v['effort']['prediction'],valid=False,applicable=False))

    def test_whole_effect_validator_rejects_unrelated_metadata_even_on_valid_complete(self):
        a,g,b=self.setup_values();out=self.prepare(a,g,b);v=out.record.aggregate.as_record();v['core']['importance']=1
        request=CommitRequest(RequestContext(a.command.command_id,'correlation'),a.command.principal_id,1,
            (RecordWrite(AggregateKey('TASK',b.task_id),b.revision,canonical(v)),),'audit',g.evidence_ref)
        with self.assertRaisesRegex(TransactionError,'UNAUTHORIZED_EFFECT'):
            validate_effects(self.codec,a,request,caller=CALLER,grant=g,records=(b,),observations=tuple(o.row for o in out.estimates),now=NOW)


if __name__=='__main__':unittest.main()
