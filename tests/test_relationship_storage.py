"""Storage bindings cannot conflate a parent stage with a separate obligation."""
from dataclasses import replace
import unittest

from src.application.definitions import DefinitionKey
from src.application.relationship_storage import (EndpointBinding, RelationStorageRecord,
    RuleStorageRecord, RelationshipStorageError, acceptance_scope)
from src.adapters.postgres_relationships import rule_from_payload, relation_from_payload
from src.domain.relationships import Endpoint, RelationshipRule, TaskRelation, literal


def rule_record(version='1', active=True):
    rule = RelationshipRule('prepare',version,active,'rule-authority-'+version,'CANONICAL_CREATION',
        'lab','preparation','prepare-template','1','preparation','SEPARATE_TASK',
        ('title','completion','disposition'),(literal('title','Prepare'),literal('completion','INCOMPLETE'),literal('disposition','ACTIVE')))
    return RuleStorageRecord(rule,DefinitionKey('TASKTYPE','lab','1'),
        DefinitionKey('TASKTYPE','preparation','1'),DefinitionKey('TASK_TEMPLATE','prepare-template','1'))


def relation_record(revision=1, kind='COMPLETION_ORDER', origin_version='1'):
    before,after=Endpoint('TASK','preparation-task'),Endpoint('TASK','lab-task')
    link=TaskRelation('prepare-before-lab',revision,kind,before,after,'link-authority',
                      'prepare' if origin_version else None,origin_version)
    return RelationStorageRecord(link,EndpointBinding(before,before.id,1),EndpointBinding(after,after.id,1))


class RelationshipStorageTests(unittest.TestCase):
    def test_rule_round_trip_keeps_mapping_and_exact_versions(self):
        value=rule_record();self.assertEqual(rule_from_payload(value.payload),value)

    def test_relation_round_trip_keeps_reverse_direction_and_origin(self):
        value=relation_record();self.assertEqual(relation_from_payload(value.payload),value)
        self.assertEqual(value.relation.before.id,'preparation-task')

    def test_new_rule_version_does_not_change_link_origin(self):
        old=rule_record();new=rule_record('2');link=relation_record()
        self.assertNotEqual(old.content_hash,new.content_hash)
        self.assertEqual(link.relation.origin_rule_version,'1')

    def test_bindings_are_part_of_authorized_scope(self):
        old=relation_record();new=replace(old,after=replace(old.after,task_revision=2))
        self.assertNotEqual(acceptance_scope('RELATION',old),acceptance_scope('RELATION',new))

    def test_payload_mutation_cannot_mutate_record(self):
        value=rule_record();raw=value.payload;raw['rule']['mappings'][0]['literal_json']='"Altered"'
        self.assertEqual(rule_from_payload(value.payload),value)

    def test_template_version_mismatch_is_rejected(self):
        with self.assertRaises(RelationshipStorageError):replace(rule_record(),template=DefinitionKey('TASK_TEMPLATE','prepare-template','2'))

    def test_wrong_definition_kind_is_rejected(self):
        with self.assertRaises(RelationshipStorageError):replace(rule_record(),source_type=DefinitionKey('PREFERENCE','lab','1'))

    def test_unaccepted_rule_cannot_enter_storage(self):
        r=rule_record();draft=replace(r.rule,active=False,acceptance_ref=None)
        with self.assertRaises(RelationshipStorageError):replace(r,rule=draft)

    def test_task_endpoint_cannot_bind_another_id(self):
        with self.assertRaises(RelationshipStorageError):EndpointBinding(Endpoint('TASK','a'),'b',1)

    def test_stage_needs_explicit_revision(self):
        with self.assertRaises(RelationshipStorageError):EndpointBinding(Endpoint('STAGE','stage'),'parent',1)

    def test_boolean_and_nonpositive_revisions_are_rejected(self):
        for n in (True,0,-1):
            with self.subTest(n=n),self.assertRaises(RelationshipStorageError):EndpointBinding(Endpoint('TASK','a'),'a',n)

    def test_membership_requires_the_same_parent_snapshot(self):
        parent,stage=Endpoint('TASK','parent'),Endpoint('STAGE','stage')
        r=TaskRelation('membership',1,'STAGE_MEMBERSHIP',parent,stage,'authority')
        good=RelationStorageRecord(r,EndpointBinding(parent,'parent',1),EndpointBinding(stage,'parent',1,1))
        self.assertEqual(relation_from_payload(good.payload),good)
        with self.assertRaises(RelationshipStorageError):replace(good,after=EndpointBinding(stage,'other',1,1))
        with self.assertRaises(RelationshipStorageError):replace(good,after=EndpointBinding(stage,'parent',2,1))

    def test_soft_sequence_is_not_converted_to_a_hard_link(self):
        value=relation_record(kind='SOFT_SEQUENCE',origin_version=None)
        self.assertEqual(relation_from_payload(value.payload).relation.kind,'SOFT_SEQUENCE')

    def test_mismatched_endpoint_payload_is_rejected(self):
        with self.assertRaises(RelationshipStorageError):replace(relation_record(),after=EndpointBinding(Endpoint('TASK','another'),'another',1))

    def test_scope_kind_cannot_be_swapped(self):
        with self.assertRaises(RelationshipStorageError):acceptance_scope('RULE',relation_record())


if __name__=='__main__':unittest.main()
