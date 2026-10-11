"""Mapped canonical targets, exact provenance and independent/shared budgets."""
from dataclasses import replace
from datetime import datetime,timezone
import unittest

from src.adapters.clocks import FrozenClock
from src.adapters.contract_json import ContractJSONCodec
from src.adapters.memory_definitions import MemoryDefinitionRepository
from src.application.definitions import DefinitionKey,canonical
from src.application.creation_outbox import CreationEvent,event_id_for
from src.application.generation_evaluator import (GenerationSource,AcceptedGenerationRule,
    GenerationError,evaluate_generation)
from src.application.manual_tasks import ResolvedManualIntent,prepare_manual_task
from src.application.relationship_storage import RuleStorageRecord
from src.application.task_storage import admit_storage,TaskStorageBindings
from src.domain.authorization import Command,CreationRecord,change
from src.domain.relationships import RelationshipRule,FieldMapping,literal
from src.domain.effort import sum_obligations
from tests.test_definitions import artifact
from tools.check_contract_registry import trusted_schemas

NOW=datetime(2026,1,1,tzinfo=timezone.utc)
DIMS=dict(thinking_depth=2,repetitive_volume=3,new_learning_load=2)
DEFAULTS=dict(importance=4,requiredness='REQUIRED',difficulty=DIMS,minimum_session_seconds=1200,
    fragmentable=True,total_estimate_seconds=1800)


class GenerationEvaluatorTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.codec=ContractJSONCodec(trusted_schemas())

    def setup_values(self,*,kind='SEPARATE_TASK',mappings=None,facts=None,copied=None,defaults=DEFAULTS,template_defaults=None,version='1',relation=None):
        repo=MemoryDefinitionRepository(FrozenClock(NOW))
        repo.register_artifacts([artifact('TASKTYPE','source-type','1',{}),artifact('TASKTYPE','target-type','1',dict(defaults=defaults))])
        command=Command('creation','user','USER_COMMAND','source-authority',
            (change('source',None,'CREATE_TASK',dict(title='Source title',importance=3,requiredness='REQUIRED',difficulty=DIMS,user_remaining_seconds=600)),))
        intent=ResolvedManualIntent(command.fingerprint,'original-user-statement',NOW,
            canonical(dict(domain='study',task_type_ref=dict(id='source-type',version='1'))))
        src=prepare_manual_task(self.codec,command,intent,repo).after
        source=GenerationSource(CreationEvent(event_id_for('source'),'source',1,src.content_hash,'creation','user','source-authority',NOW),src,'original-user-statement')
        bindings=(literal('title','Preparation'),literal('completion','INCOMPLETE'),literal('disposition','ACTIVE'))
        rule=RelationshipRule('rule',version,True,'rule-authority','CANONICAL_CREATION','source-type','target-type','template','1','preparation',kind,
            ('title','completion','disposition'),bindings if mappings is None else mappings)
        record=RuleStorageRecord(rule,DefinitionKey('TASKTYPE','source-type','1'),DefinitionKey('TASKTYPE','target-type','1'),DefinitionKey('TASK_TEMPLATE','template','1'))
        body=dict(creation_facts=dict(domain='study') if facts is None else facts,source_facts=copied or {})
        if template_defaults is not None:body['defaults']=template_defaults
        if relation is not None:body['relation']=relation
        repo.register_artifacts([artifact('TASK_TEMPLATE','template','1',body),artifact('RELATIONSHIP_RULE','rule',version,record.payload)])
        return source,AcceptedGenerationRule(record,'user','accepted-rule-statement',NOW),repo

    def run_mapping(self,*v,**kw):return evaluate_generation(self.codec,*v,target_id='target',**kw)

    def test_exact_defaults_preserve_provenance_and_never_become_remaining_or_model(self):
        src,use,repo=self.setup_values();out=self.run_mapping(src,use,repo);v=out.target.aggregate.as_record()
        self.assertTrue(out.ready);self.assertEqual(v['core']['importance'],4)
        self.assertEqual(v['work']['total_estimate']['definition_ref'],dict(kind='TASKTYPE',id='target-type',version='1'))
        self.assertEqual(v['work']['total_estimate']['seconds'],1800);self.assertIsNone(v['effort']['user_remaining']);self.assertIsNone(v['effort']['prediction'])
        self.assertIsNone(out.target.aggregate.budget(at=NOW).seconds)
        self.assertEqual(out.manifest['defaults'][0]['content_hash'],repo.get(use.record.target_type).artifact.request.content_hash)
        template_pin=next(p for p in out.manifest['definition_snapshots'] if p['key']==vars(use.record.template))
        self.assertEqual(template_pin['content_hash'],repo.get(use.record.template).artifact.request.content_hash)
        self.assertEqual(template_pin['git_blob'],repo.get(use.record.template).artifact.blob_oid)
        self.assertEqual(out.manifest['source_event']['content_hash'],src.task.content_hash)
        self.assertEqual(v['core']['acceptance']['authority_ref'],'rule-authority')
        self.assertIsNone(out.parent_after)

    def test_source_only_copies_named_fields_with_original_user_provenance(self):
        bindings=(FieldMapping('title','SOURCE','title',None),literal('completion','INCOMPLETE'),literal('disposition','ACTIVE'),FieldMapping('user_remaining_seconds','SOURCE','user_remaining_seconds',None))
        src,use,repo=self.setup_values(mappings=bindings);out=self.run_mapping(src,use,repo);v=out.target.aggregate.as_record()
        self.assertEqual((v['core']['title'],v['core']['importance']),('Source title',4))
        self.assertEqual(v['effort']['user_remaining']['seconds'],600)
        self.assertEqual(out.observations[0].source_ref,'original-user-statement')
        self.assertIn(dict(field='/core/title',source_ref='original-user-statement'),v['provenance'])

    def test_explicit_default_mapping_is_version_bound_and_missing_lookup_is_pending(self):
        bindings=(FieldMapping('title','DEFAULT','workload_unit',None),literal('completion','INCOMPLETE'),literal('disposition','ACTIVE'),
            FieldMapping('importance','DEFAULT','importance',None))
        src,use,repo=self.setup_values(defaults=dict(DEFAULTS,workload_unit='Weekly preparation'),mappings=bindings)
        out=self.run_mapping(src,use,repo)
        self.assertEqual(out.target.aggregate.as_record()['core']['title'],'Weekly preparation')
        self.assertEqual(out.manifest['field_sources']['title'],'accepted-rule-statement')
        src,use,repo=self.setup_values(mappings=bindings)
        self.assertIn('/mapping/title',self.run_mapping(src,use,repo).missing_fields)

    def test_separate_targets_own_independent_budget_and_stages_share_parent_once(self):
        src,use,repo=self.setup_values();rule=use.record.rule
        src,use,repo=self.setup_values(mappings=rule.mappings+(literal('user_remaining_seconds',300),))
        out=self.run_mapping(src,use,repo)
        self.assertEqual(sum_obligations([src.task.aggregate.budget(at=NOW),out.target.aggregate.budget(at=NOW)]).seconds,900)
        src,use,repo=self.setup_values(kind='STAGE',facts=dict(domain='study',stage_weight=2))
        staged=self.run_mapping(src,use,repo,parent=src.task);after=staged.parent_after
        self.assertTrue(staged.ready);self.assertIsNone(staged.target)
        self.assertEqual(after.aggregate.budget(at=NOW).seconds,600)
        self.assertEqual(after.aggregate.stage_partition(at=NOW).allocations[0].seconds,600)
        self.assertEqual(after.aggregate.as_record()['core']['importance'],3)
        self.assertEqual(src.task.revision,1);self.assertEqual(after.revision,2)

    def test_raw_discovery_and_unpinned_snapshot_cannot_enter(self):
        src,use,repo=self.setup_values()
        for raw in (dict(raw='external'),CreationRecord('raw','source','raw',False),src.task):
            with self.assertRaisesRegex(GenerationError,'CANONICAL_SOURCE_REQUIRED'):self.run_mapping(raw,use,repo)
        with self.assertRaisesRegex(GenerationError,'SOURCE_SNAPSHOT_MISMATCH'):
            replace(src,event=replace(src.event,content_hash='a'*64))

    def test_foreign_principal_and_modified_accepted_rule_fail_closed(self):
        src,use,repo=self.setup_values()
        with self.assertRaisesRegex(GenerationError,'PRINCIPAL_MISMATCH'):self.run_mapping(src,replace(use,principal_id='other'),repo)
        changed=replace(use.record,rule=replace(use.record.rule,mappings=(literal('title','Changed'),)+use.record.rule.mappings[1:]))
        with self.assertRaisesRegex(GenerationError,'RULE_PAYLOAD_MISMATCH'):self.run_mapping(src,replace(use,record=changed),repo)

    def test_missing_essential_source_fact_stays_pending(self):
        src,use,repo=self.setup_values(mappings=(FieldMapping('title','SOURCE','absent',None),literal('completion','INCOMPLETE'),literal('disposition','ACTIVE')))
        out=self.run_mapping(src,use,repo);self.assertFalse(out.ready);self.assertIsNone(out.target)
        self.assertIn('/mapping/title',out.missing_fields);self.assertNotIn('invented',out.manifest_json)

    def test_unknown_domain_or_default_ratings_stay_pending(self):
        for kwargs,path in ((dict(facts={}),'/core/domain'),(dict(defaults={}),'/core/importance')):
            src,use,repo=self.setup_values(**kwargs);out=self.run_mapping(src,use,repo)
            self.assertIn(path,out.missing_fields);self.assertIsNone(out.target)

    def test_template_default_conflicts_are_pending_until_explicitly_resolved(self):
        src,use,repo=self.setup_values(template_defaults=dict(importance=1));out=self.run_mapping(src,use,repo)
        self.assertIn('/defaults/importance',out.missing_fields)
        src,use,repo=self.setup_values(template_defaults=dict(importance=1),mappings=use.record.rule.mappings+(literal('importance',2),))
        self.assertEqual(self.run_mapping(src,use,repo).target.aggregate.as_record()['core']['importance'],2)

    def test_missing_exact_definition_does_not_select_newer_version(self):
        src,use,repo=self.setup_values();repo.register_artifacts([artifact('TASKTYPE','target-type','2',dict(defaults=DEFAULTS))])
        repo._records.pop(use.record.target_type)
        self.assertIn('/references/TASKTYPE/target-type/1',self.run_mapping(src,use,repo).missing_fields)

    def test_inactive_and_source_type_mismatch_are_not_eligible(self):
        src,use,repo=self.setup_values();inactive=replace(use.record,rule=replace(use.record.rule,active=False))
        self.assertEqual(self.run_mapping(src,replace(use,record=inactive),repo).state,'NOT_ELIGIBLE')
        altered=replace(use.record,source_type=DefinitionKey('TASKTYPE','source-type','2'))
        self.assertEqual(self.run_mapping(src,replace(use,record=altered),repo).code,'GENERATION_SOURCE_TYPE_MISMATCH')

    def test_rule_version_is_audit_not_new_occurrence_identity(self):
        a=self.run_mapping(*self.setup_values(version='1'));b=self.run_mapping(*self.setup_values(version='2'))
        self.assertEqual(a.scope.generation_key,b.scope.generation_key);self.assertNotEqual(a.manifest['rule'],b.manifest['rule'])

    def test_complete_cancelled_notice_and_invalid_mapping_are_rejected(self):
        for value in ('COMPLETE',False):
            src,use,repo=self.setup_values(mappings=(literal('title','Title'),literal('completion',value),literal('disposition','ACTIVE')))
            self.assertFalse(self.run_mapping(src,use,repo).ready)
        src,use,repo=self.setup_values();bindings=use.record.rule.mappings+(literal('expiration_notice_ref','notice'),)
        self.assertEqual(self.run_mapping(*self.setup_values(mappings=bindings)).code,'GENERATION_CANNOT_INFER_OUTCOME')
        bindings=use.record.rule.mappings+(literal('importance',False),)
        self.assertEqual(self.run_mapping(*self.setup_values(mappings=bindings)).code,'GENERATION_INVALID_MAPPING')

    def test_expiring_without_condition_is_pending_and_condition_is_preserved(self):
        defs=dict(DEFAULTS,requiredness='EXPIRING');src,use,repo=self.setup_values(defaults=defs)
        self.assertIn('/core/expiration/condition_ref',self.run_mapping(src,use,repo).missing_fields)
        out=self.run_mapping(*self.setup_values(defaults=defs,mappings=use.record.rule.mappings+(literal('expiration_condition_ref','condition'),)))
        self.assertEqual(out.target.aggregate.as_record()['core']['expiration'],dict(condition_ref='condition',notice_ref=None))

    def test_profile_context_requires_exact_version_without_inheriting_source_context(self):
        src,use,repo=self.setup_values(facts=dict(domain='study',context=dict(kind='COURSE',id='course')))
        self.assertIn('/references/profile_ref',self.run_mapping(src,use,repo).missing_fields)
        ref=dict(kind='COURSE_PROFILE',id='course',version='1')
        src,use,repo=self.setup_values(facts=dict(domain='study',context=dict(kind='COURSE',id='course'),profile_ref=ref))
        repo.register_artifacts([artifact('COURSE_PROFILE','course','1',{})]);out=self.run_mapping(src,use,repo)
        self.assertEqual(out.bindings.profile_key,DefinitionKey(**ref));self.assertEqual(out.target.aggregate.as_record()['core']['context']['id'],'course')

    def test_stage_requires_current_parent_and_cannot_mutate_parent_task_fields(self):
        src,use,repo=self.setup_values(kind='STAGE')
        self.assertIn('/references/current_parent',self.run_mapping(src,use,repo).missing_fields)
        bindings=use.record.rule.mappings+(literal('importance',1),)
        src,use,repo=self.setup_values(kind='STAGE',mappings=bindings)
        self.assertEqual(self.run_mapping(src,use,repo,parent=src.task).code,'GENERATION_STAGE_TASK_FIELDS')

    def test_stage_uses_current_parent_preserves_existing_stages_and_rejects_duplicate(self):
        src,use,repo=self.setup_values(kind='STAGE',facts=dict(stage_weight=1));first=self.run_mapping(src,use,repo,parent=src.task)
        second=evaluate_generation(self.codec,src,use,repo,target_id='another',parent=first.parent_after)
        self.assertEqual(second.parent_after.revision,3);self.assertEqual(len(second.parent_after.aggregate.as_record()['stage_details']),2)
        self.assertEqual(self.run_mapping(src,use,repo,parent=first.parent_after).state,'CONFLICT')
        self.assertEqual(sum(x.seconds for x in second.parent_after.aggregate.stage_partition(at=NOW).allocations),600)

    def test_invalid_pointer_weight_and_context_are_pending_without_writes(self):
        for pointer in ('/stage_details/-1/title','/core/~2title','/core/nope'):
            src,use,repo=self.setup_values(facts={},copied=dict(domain=pointer));self.assertFalse(self.run_mapping(src,use,repo).ready)
        src,use,repo=self.setup_values(kind='STAGE',facts=dict(stage_weight=-1));self.assertEqual(self.run_mapping(src,use,repo,parent=src.task).code,'GENERATION_INVALID_TARGET')
        src,use,repo=self.setup_values(facts=dict(domain='invalid'));self.assertEqual(self.run_mapping(src,use,repo).code,'GENERATION_INVALID_TARGET')

    def test_explicit_null_source_context_and_detached_results_are_preserved(self):
        src,use,repo=self.setup_values(copied=dict(context='/core/context'));out=self.run_mapping(src,use,repo)
        self.assertTrue(out.ready);self.assertIsNone(out.target.aggregate.as_record()['core']['context'])
        out.manifest['defaults'][0]['values']['importance']=1
        out.target.aggregate.as_record()['core']['title']='Mutated'
        self.assertEqual(out.manifest['defaults'][0]['values']['importance'],4)
        self.assertEqual(out.target.aggregate.as_record()['core']['title'],'Preparation')

    def test_stage_remaining_retains_parent_owned_observation_without_second_budget(self):
        src,use,repo=self.setup_values(kind='STAGE',facts=dict(stage_weight=1))
        bindings=use.record.rule.mappings+(literal('user_remaining_seconds',300),)
        src,use,repo=self.setup_values(kind='STAGE',facts=dict(stage_weight=1),mappings=bindings)
        out=self.run_mapping(src,use,repo,parent=src.task)
        self.assertEqual(out.observations[0].task_id,'source')
        self.assertEqual(out.parent_after.aggregate.budget(at=NOW).seconds,600)
        partition=out.parent_after.aggregate.stage_partition(at=NOW)
        self.assertEqual(partition.canonical_stage_sum,300);self.assertTrue(partition.canonical_disagreement)
        self.assertEqual(partition.allocations[0].seconds,600)

    def test_source_acceptance_mismatch_and_closed_or_wrong_parent_are_rejected(self):
        src,use,repo=self.setup_values(kind='STAGE')
        with self.assertRaisesRegex(GenerationError,'SOURCE_ACCEPTANCE_MISMATCH'):
            replace(src,event=replace(src.event,authority_ref='different-authority'))
        v=src.task.aggregate.as_record();v['core']['disposition']='CANCELLED';v['effort']['disposition']='CANCELLED'
        parent=admit_storage(self.codec,canonical(v).encode())
        self.assertEqual(self.run_mapping(src,use,repo,parent=parent).code,'GENERATION_PARENT_CLOSED')
        v=src.task.aggregate.as_record();v['core']['task_id']='different';v['effort']['task_id']='different'
        with self.assertRaisesRegex(GenerationError,'PARENT_SCOPE'):
            self.run_mapping(src,use,repo,parent=admit_storage(self.codec,canonical(v).encode()))

    def test_stage_preserves_exact_current_parent_profile_binding(self):
        src,use,repo=self.setup_values(kind='STAGE');v=src.task.aggregate.as_record()
        v['core']['context']=dict(kind='COURSE',id='course');v['core']['revision']=v['effort']['task_revision']=2
        parent=admit_storage(self.codec,canonical(v).encode());key=DefinitionKey('COURSE_PROFILE','course','1')
        self.assertIn('/references/parent_profile',self.run_mapping(src,use,repo,parent=parent).missing_fields)
        bindings=TaskStorageBindings(key)
        self.assertIn('/references/parent_profile',self.run_mapping(src,use,repo,parent=parent,parent_bindings=bindings).missing_fields)
        repo.register_artifacts([artifact('COURSE_PROFILE','course','1',{})])
        out=self.run_mapping(src,use,repo,parent=parent,parent_bindings=bindings)
        self.assertTrue(out.ready);self.assertEqual(out.bindings,bindings)
        self.assertEqual(out.parent_after.aggregate.as_record()['core']['context'],v['core']['context'])

    def test_task_and_stage_may_share_text_id_without_sharing_identity(self):
        src,use,repo=self.setup_values(kind='STAGE')
        out=evaluate_generation(self.codec,src,use,repo,target_id=src.task.task_id,parent=src.task)
        self.assertTrue(out.ready);self.assertEqual(out.parent_after.aggregate.as_record()['stage_details'][0]['stage_id'],'source')
        self.assertEqual(out.parent_after.aggregate.stage_partition(at=NOW).reason,'WEIGHTS_UNKNOWN')
        src,use,repo=self.setup_values()
        with self.assertRaisesRegex(GenerationError,'TARGET_IDENTITY'):
            evaluate_generation(self.codec,src,use,repo,target_id=src.task.task_id)


if __name__=='__main__':unittest.main()
