from dataclasses import replace
from datetime import datetime,timezone
import unittest

from src.adapters.clocks import FrozenClock
from src.adapters.contract_json import ContractJSONCodec
from src.adapters.memory_definitions import MemoryDefinitionRepository
from src.application.definitions import DefinitionKey,canonical
from src.application.manual_tasks import ApprovedDefaultUse,ResolvedManualIntent,prepare_manual_task
from src.application.transactions import TransactionError
from src.domain.authorization import Command,change
from tests.test_definitions import artifact
from tools.check_contract_registry import trusted_schemas

NOW=datetime(2026,1,1,tzinfo=timezone.utc)
DIMS=dict(thinking_depth=2,repetitive_volume=2,new_learning_load=3)
DEFAULTS=dict(importance=3,requiredness='OPTIONAL',difficulty=DIMS,minimum_session_seconds=1200,
    fragmentable=True,total_estimate_seconds=1800)


class ManualTaskTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.codec=ContractJSONCodec(trusted_schemas())

    def setup_values(self,fields=None,facts=None):
        repo=MemoryDefinitionRepository(FrozenClock(NOW))
        record,=repo.register_artifacts([artifact('TASKTYPE','work','1',dict(defaults=DEFAULTS))])
        command=Command('create','user','USER_COMMAND','grant',(change('task',None,'CREATE_TASK',fields or {'title':'Explicit new task'}),))
        facts=dict(domain='study',task_type_ref=dict(id='work',version='1')) if facts is None else facts
        intent=ResolvedManualIntent(command.fingerprint,'statement',NOW,canonical(facts),
            (ApprovedDefaultUse(record.key,'approved-defaults','default-statement'),) if facts.get('task_type_ref') else ())
        return command,intent,repo

    def prepare(self,*v):return prepare_manual_task(self.codec,*v)

    def test_approved_defaults_copy_exact_values_with_source_and_version_provenance(self):
        c,i,repo=self.setup_values();out=self.prepare(c,i,repo);v=out.after.aggregate.as_record()
        self.assertTrue(out.ready);self.assertEqual(v['core']['importance'],3)
        self.assertEqual(v['work']['total_estimate']['seconds'],1800)
        self.assertEqual(v['work']['total_estimate']['definition_ref'],dict(kind='TASKTYPE',id='work',version='1'))
        self.assertEqual(out.provenance.details['approved_default_snapshots'][0]['acceptance_ref'],'approved-defaults')
        self.assertIn(dict(field='/core/importance',source_ref='default-statement'),v['provenance'])
        self.assertIsNone(v['effort']['user_remaining']);self.assertEqual(v['core']['completion'],'INCOMPLETE')

    def test_cache_presence_alone_does_not_make_defaults_approved(self):
        c,i,repo=self.setup_values();out=self.prepare(c,replace(i,default_uses=()),repo)
        self.assertFalse(out.ready);self.assertIn('/core/importance',out.missing_fields)
        self.assertIsNone(out.after);self.assertIn('task',out.proposal['command']['changes'][0]['task_id'])

    def test_missing_title_domain_and_ratings_are_explicit_pending_paths(self):
        c,i,repo=self.setup_values({'importance':3},{})
        out=self.prepare(c,i,repo)
        self.assertEqual(out.missing_fields,('/core/difficulty','/core/domain','/core/requiredness','/core/title'))
        self.assertIsNone(out.seed);self.assertNotIn('default-domain',out.proposal_json)

    def test_conflicting_defaults_have_no_implicit_precedence_and_explicit_value_resolves_only_that_field(self):
        c,i,repo=self.setup_values();t,=repo.register_artifacts([artifact('TASK_TEMPLATE','template','1',dict(defaults=dict(importance=5)))])
        facts=i.facts;facts['template_ref']=dict(id='template',version='1')
        i=replace(i,facts_json=canonical(facts),default_uses=i.default_uses+(ApprovedDefaultUse(t.key,'approved-template','template-statement'),))
        out=self.prepare(c,i,repo);self.assertIn('/defaults/importance',out.missing_fields)
        c=replace(c,changes=(change('task',None,'CREATE_TASK',dict(title='Explicit new task',importance=2)),))
        i=replace(i,command_fingerprint=c.fingerprint);out=self.prepare(c,i,repo)
        self.assertTrue(out.ready);self.assertEqual(out.after.aggregate.as_record()['core']['importance'],2)
        self.assertEqual(out.after.aggregate.as_record()['core']['difficulty'],DIMS)

    def test_new_default_version_and_detached_provenance_do_not_rewrite_a_prepared_task(self):
        c,i,repo=self.setup_values();out=self.prepare(c,i,repo)
        repo.register_artifacts([artifact('TASKTYPE','work','2',dict(defaults=dict(DEFAULTS,importance=5)))])
        out.provenance.details['approved_default_snapshots'][0]['values']['importance']=1
        self.assertEqual(out.after.aggregate.as_record()['core']['importance'],3)
        self.assertEqual(out.provenance.details['approved_default_snapshots'][0]['values']['importance'],3)
        self.assertEqual(self.prepare(c,i,repo),out)

    def test_missing_exact_definition_or_course_profile_is_pending_without_using_latest(self):
        c,i,repo=self.setup_values();facts=i.facts;facts['task_type_ref']['version']='2'
        i=replace(i,facts_json=canonical(facts),default_uses=(ApprovedDefaultUse(DefinitionKey('TASKTYPE','work','2'),'approval','statement'),))
        self.assertIn('/references/task_type_ref',self.prepare(c,i,repo).missing_fields)
        c,i,repo=self.setup_values();facts=i.facts;facts['context']=dict(kind='COURSE',id='course')
        i=replace(i,facts_json=canonical(facts));self.assertIn('/references/profile_ref',self.prepare(c,i,repo).missing_fields)

    def test_expiring_creation_needs_a_condition_and_never_a_delivered_notice(self):
        c,i,repo=self.setup_values(dict(title='Preview',requiredness='EXPIRING'))
        self.assertIn('/core/expiration/condition_ref',self.prepare(c,i,repo).missing_fields)
        c=replace(c,changes=(change('task',None,'CREATE_TASK',dict(title='Preview',requiredness='EXPIRING',expiration_condition_ref='class-start')),))
        i=replace(i,command_fingerprint=c.fingerprint);out=self.prepare(c,i,repo)
        self.assertEqual(out.after.aggregate.as_record()['core']['expiration'],dict(condition_ref='class-start',notice_ref=None))

    def test_explicit_initial_u_has_separate_exact_observation_and_never_uses_total_as_u(self):
        c,i,repo=self.setup_values(dict(title='New task',user_remaining_seconds=7200));out=self.prepare(c,i,repo)
        self.assertIsNone(out.seed.aggregate.as_record()['effort']['user_remaining'])
        self.assertEqual(out.after.aggregate.as_record()['effort']['user_remaining']['seconds'],7200)
        self.assertEqual(out.prepared_estimates[0].source_ref,'statement')
        self.assertEqual(out.prepared_estimates[0].observed_at,NOW)
        self.assertEqual(out.after.aggregate.as_record()['work']['total_estimate']['seconds'],1800)

    def test_reported_zero_and_false_session_values_preserve_meaning(self):
        c,i,repo=self.setup_values();facts=i.facts;facts.update(total_estimate_seconds=0,fragmentable=False)
        out=self.prepare(c,replace(i,facts_json=canonical(facts)),repo)
        self.assertEqual(out.after.aggregate.as_record()['work']['total_estimate']['seconds'],0)
        self.assertEqual(out.after.aggregate.as_record()['work']['total_estimate']['basis'],'USER_REPORT')
        self.assertIs(out.after.aggregate.as_record()['work']['fragmentable'],False)
        self.assertIsNone(out.after.aggregate.as_record()['effort']['user_remaining'])

    def test_only_single_registered_user_creation_and_allowlisted_resolved_facts_are_accepted(self):
        c,i,repo=self.setup_values()
        with self.assertRaisesRegex(TransactionError,'MANUAL_INTENT_SCOPE_MISMATCH'):
            self.prepare(c,replace(i,command_fingerprint='a'*64),repo)
        with self.assertRaisesRegex(TransactionError,'MANUAL_RESOLVED_FACTS'):
            replace(i,facts_json=canonical(dict(i.facts,completed_at='invented')))
        with self.assertRaisesRegex(TransactionError,'MANUAL_CREATION_CANNOT_ASSERT_OUTCOME'):
            c=replace(c,changes=(change('task',None,'CREATE_TASK',dict(title='Done',completion='COMPLETE')),));self.prepare(c,i,repo)


if __name__=='__main__':unittest.main()
