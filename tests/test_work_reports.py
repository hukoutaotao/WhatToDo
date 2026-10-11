from copy import deepcopy
from dataclasses import replace
from datetime import datetime,timedelta,timezone
import json
from pathlib import Path
import unittest

from src.adapters.contract_json import ContractJSONCodec
from src.adapters.extension_contracts import load_supported_schemas
from src.application.command_ledger import validate_audit_fingerprint
from src.application.definitions import canonical
from src.application.ports import AggregateKey,CommitRequest,RecordWrite,RequestContext,TransactionPermit
from src.application.task_storage import admit_storage
from src.application.transactions import TransactionError,prepare_transaction
from src.application.work_reports import WorkReportGrant,admit_work_report,admit_actual_record,prepare_work_report
from src.domain.authorization import CallerIdentity
from tools.check_contract_registry import trusted_schemas

ROOT=Path(__file__).resolve().parents[1];NOW=datetime(2026,1,1,tzinfo=timezone.utc)
CALLER=CallerIdentity('principal','USER_COMMAND',True)


class WorkReportTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.codec=ContractJSONCodec(load_supported_schemas(root=ROOT))
        cls.cases=json.loads((ROOT/'tests/fixtures/task_aggregate/cases.json').read_text(encoding='utf-8'))['cases']

    def values(self,*,name='aggregate-unknown-facts',**fields):
        before=admit_storage(self.codec,canonical(next(c['payload'] for c in self.cases if c['id']==name)).encode())
        v=dict(schema_version='0.1.0-work-report',command_id='report',principal_id='principal',origin='USER_COMMAND',authority_ref='grant',
            observation_id='observation',target_ref=dict(task_id=before.task_id,revision=before.revision),mode='INCREMENT',seconds=300,
            stage_id=None,session_started_at=None,session_ended_at=None);v.update(fields)
        report=admit_work_report(self.codec,canonical(v).encode())
        grant=WorkReportGrant(report,'statement',NOW-timedelta(minutes=2),NOW+timedelta(hours=1))
        return report,grant,before

    def prepare(self,r,g,b,**kwargs):
        options=dict(caller=CALLER,previous_total_seconds=200,source_observed_at=NOW-timedelta(minutes=1),now=NOW);options.update(kwargs)
        return prepare_work_report(self.codec,r,g,b,**options)

    def transaction(self,r,g,b):
        out=self.prepare(r,g,b)
        request=CommitRequest(RequestContext(r.command_id,'correlation'),r.principal_id,1,
            (RecordWrite(AggregateKey('TASK',r.task_id),b.revision,out.task.raw_bytes.decode()),
             RecordWrite(AggregateKey('WORK_REPORT',r.observation_id),None,out.work.raw_bytes.decode())),'audit',g.evidence_ref)
        permit=TransactionPermit('permit',r.principal_id,'USER_COMMAND',request.fingerprint,NOW-timedelta(minutes=1),NOW+timedelta(minutes=5))
        return out,request,permit

    def test_increment_preserves_truthful_unknown_session_and_all_independent_facts(self):
        r,g,b=self.values();out=self.prepare(r,g,b);v=out.work.as_record();a=out.task.aggregate.as_record();old=b.aggregate.as_record()
        self.assertEqual((v['previous_total_seconds'],v['increment_seconds'],v['resulting_total_seconds']),(200,300,500))
        for key in ('timing','work','stage_details','provenance'):self.assertEqual(a[key],old[key])
        self.assertEqual(a['effort']['user_remaining'],old['effort']['user_remaining']);self.assertEqual(out.estimates,())
        self.assertEqual(a['core']['completion'],'INCOMPLETE');self.assertIsNone(v['report']['session_started_at']);self.assertIsNone(v['report']['session_ended_at'])

    def test_cumulative_report_stores_original_total_and_only_effective_increment(self):
        r,g,b=self.values(mode='CUMULATIVE',seconds=900);v=self.prepare(r,g,b).work.as_record()
        self.assertEqual((v['report']['seconds'],v['increment_seconds'],v['resulting_total_seconds']),(900,700,900))

    def test_equal_cumulative_and_explicit_zero_are_real_zero_increments(self):
        for fields in (dict(mode='CUMULATIVE',seconds=200),dict(seconds=0)):
            r,g,b=self.values(**fields);self.assertEqual(self.prepare(r,g,b).work.as_record()['increment_seconds'],0)

    def test_cumulative_below_recorded_total_is_conflict_never_negative_or_counter_reset(self):
        r,g,b=self.values(mode='CUMULATIVE',seconds=199)
        with self.assertRaisesRegex(TransactionError,'CUMULATIVE_BELOW'):self.prepare(r,g,b)

    def test_seconds_are_unbounded_integral_and_booleans_negative_floats_rejected(self):
        r,g,b=self.values(seconds=2**80);self.assertEqual(self.prepare(r,g,b).work.as_record()['increment_seconds'],2**80)
        for seconds in (True,-1,0.5):
            with self.subTest(seconds=seconds),self.assertRaises(TransactionError):self.values(seconds=seconds)

    def test_explicit_u_zero_never_asserts_completion_or_fabricates_time(self):
        r,g,b=self.values(user_remaining_seconds=0);out=self.prepare(r,g,b)
        self.assertEqual(len(out.estimates),1);self.assertEqual(out.estimates[0].seconds,0)
        self.assertEqual(out.task.aggregate.as_record()['core']['completion'],'INCOMPLETE')
        self.assertIsNone(out.task.aggregate.as_record()['timing']['completed_at'])

    def test_explicit_u_unknown_is_distinct_from_omission_and_zero(self):
        r,g,b=self.values(name='aggregate-expired-retains-positive-u',user_remaining_seconds=None);out=self.prepare(r,g,b)
        self.assertIsNone(out.task.aggregate.as_record()['effort']['user_remaining']);self.assertFalse(out.estimates)
        self.assertEqual(out.task.aggregate.as_record()['core']['disposition'],'EXPIRED')
        r,g,b=self.values(name='aggregate-expired-retains-positive-u');out=self.prepare(r,g,b)
        self.assertEqual(out.task.aggregate.as_record()['effort']['user_remaining'],b.aggregate.as_record()['effort']['user_remaining'])

    def test_reports_do_not_restore_cancelled_or_expired_tasks_or_modify_stage_status(self):
        for name in ('aggregate-expired-retains-positive-u','aggregate-stages-retain-historical-completed-stage-u'):
            r,g,b=self.values(name=name);out=self.prepare(r,g,b);old=b.aggregate.as_record();new=out.task.aggregate.as_record()
            self.assertEqual(new['core']['disposition'],old['core']['disposition']);self.assertEqual(new['effort']['stages'],old['effort']['stages'])

    def test_completed_task_historical_work_retains_zero_u_and_cannot_silently_reopen(self):
        r,g,b=self.values(name='aggregate-complete-with-unknown-historical-completion-time');out=self.prepare(r,g,b)
        self.assertEqual(out.task.aggregate.as_record()['core']['completion'],'COMPLETE')
        for u in (None,1):
            r,g,b=self.values(name='aggregate-complete-with-unknown-historical-completion-time',user_remaining_seconds=u)
            with self.assertRaisesRegex(TransactionError,'COMPLETED_U_CONFLICT'):self.prepare(r,g,b)

    def test_one_session_bound_stays_partial_and_microseconds_offset_are_retained(self):
        start='2025-12-31T20:00:00.123456-03:00';r,g,b=self.values(session_started_at=start)
        v=self.prepare(r,g,b).work.as_record()['report'];self.assertEqual(v['session_started_at'],start);self.assertIsNone(v['session_ended_at'])
        r,g,b=self.values(session_ended_at=start);self.assertIsNone(self.prepare(r,g,b).work.as_record()['report']['session_started_at'])

    def test_future_and_reversed_sessions_never_become_actual_work(self):
        r,g,b=self.values(session_ended_at=NOW.isoformat())
        with self.assertRaisesRegex(TransactionError,'FUTURE_SESSION'):self.prepare(r,g,b)
        with self.assertRaises(TransactionError):self.values(session_started_at='2025-12-31T23:00:00Z',session_ended_at='2025-12-31T22:00:00Z')

    def test_reported_source_time_must_be_known_aware_and_not_future(self):
        r,g,b=self.values()
        for time in (None,datetime(2026,1,1),NOW+timedelta(seconds=1)):
            with self.subTest(time=time),self.assertRaisesRegex(TransactionError,'SOURCE_TIME_REQUIRED'):self.prepare(r,g,b,source_observed_at=time)

    def test_fresh_user_authority_and_exact_target_revision_required(self):
        r,g,b=self.values()
        for caller in (CallerIdentity('principal','EXTERNAL',True),CallerIdentity('principal','USER_COMMAND',False),CallerIdentity('other','USER_COMMAND',True)):
            with self.assertRaisesRegex(TransactionError,'UNTRUSTED_CALLER'):self.prepare(r,g,b,caller=caller)
        with self.assertRaisesRegex(TransactionError,'INACTIVE_AUTHORITY'):self.prepare(r,replace(g,active=False),b)
        other,_,_=self.values(seconds=301)
        with self.assertRaisesRegex(TransactionError,'EXACT_SCOPE'):self.prepare(r,replace(g,report=other),b)
        other,grant,_=self.values(target_ref=dict(task_id=b.task_id,revision=2))
        with self.assertRaisesRegex(TransactionError,'STALE_STATE_VERSION'):self.prepare(other,grant,b)

    def test_observation_fact_identity_ignores_transport_and_revision_but_binds_all_reported_facts(self):
        r,_,b=self.values();other,_,_=self.values(command_id='another-command',authority_ref='another-grant',target_ref=dict(task_id=b.task_id,revision=9))
        self.assertNotEqual(r.fingerprint,other.fingerprint);self.assertEqual(r.fact_fingerprint,other.fact_fingerprint)
        for fields in (dict(seconds=301),dict(mode='CUMULATIVE'),dict(user_remaining_seconds=None),dict(stage_id='stage'),dict(principal_id='other')):
            changed,_,_=self.values(**fields);self.assertNotEqual(r.fact_fingerprint,changed.fact_fingerprint)

    def test_planned_blocks_completion_unknown_fields_and_unknown_versions_are_closed(self):
        for fields in (dict(planned_block_ref='block'),dict(completion='COMPLETE'),dict(origin='EXTERNAL'),dict(schema_version='newer'),dict(session_started_at='2025-12-31T20:00:00')):
            with self.subTest(fields=fields),self.assertRaises(TransactionError):self.values(**fields)
        r,_,_=self.values();self.assertNotEqual(ContractJSONCodec(trusted_schemas()).admit('work-report',r.payload_json.encode()).status,'SUPPORTED_SHAPE')

    def test_actual_record_hash_and_settlement_drift_are_rejected(self):
        r,g,b=self.values();record=self.prepare(r,g,b).work
        with self.assertRaisesRegex(TransactionError,'PAYLOAD_HASH'):replace(record,content_hash='0'*64)
        v=record.as_record();v['increment_seconds']+=1
        with self.assertRaisesRegex(TransactionError,'SETTLEMENT'):admit_actual_record(self.codec,canonical(v).encode())

    def test_exact_transaction_audits_both_task_revision_and_work_record(self):
        r,g,b=self.values();out,req,permit=self.transaction(r,g,b)
        prepared=prepare_transaction(self.codec,req,caller=CALLER,permit=permit,at=NOW)
        self.assertEqual([k.kind for k in prepared.receipt.changed_keys],['TASK','WORK_REPORT'])
        changes=(('TASK',b.task_id,b.revision,out.task.revision,b.aggregate.as_record(),out.task.aggregate.as_record()),
            ('WORK_REPORT',r.observation_id,None,1,None,out.work.as_record()))
        validate_audit_fingerprint(prepared.receipt,principal_id=r.principal_id,expected_store_revision=1,source_ref=g.evidence_ref,correlation_ref='other',changes=changes)
        with self.assertRaises(TransactionError):validate_audit_fingerprint(prepared.receipt,principal_id=r.principal_id,expected_store_revision=1,source_ref=g.evidence_ref,correlation_ref='other',changes=changes[:1])

    def test_unpaired_work_or_changed_report_cannot_use_existing_transaction_permit(self):
        r,g,b=self.values();out,req,permit=self.transaction(r,g,b)
        req2=replace(req,writes=req.writes[1:]);permit2=replace(permit,request_fingerprint=req2.fingerprint)
        with self.assertRaisesRegex(TransactionError,'WORK_REPORT_SCOPE'):prepare_transaction(self.codec,req2,caller=CALLER,permit=permit2,at=NOW)
        v=out.work.as_record();v['report']['seconds']=301;v['increment_seconds']=301;v['resulting_total_seconds']=501
        altered=replace(req,writes=(req.writes[0],replace(req.writes[1],body_json=canonical(v))))
        with self.assertRaisesRegex(TransactionError,'EXACT_ACTIVE_PERMIT'):prepare_transaction(self.codec,altered,caller=CALLER,permit=permit,at=NOW)


if __name__=='__main__':unittest.main()
