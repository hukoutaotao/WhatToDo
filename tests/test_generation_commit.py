"""Composite Task/link/occurrence plans and stable replay identities."""
from dataclasses import replace
import unittest

from src.application.definitions import canonical
from src.application.generation_evaluator import GenerationError,GenerationSource
from src.application.generation_commit import (prepare_generation_commit,target_identity,
    generation_scope,GenerationOccurrenceRecord)
from src.application.command_ledger import validate_audit_fingerprint
from src.application.ports import CommitRequest,RequestContext
from tests import test_generation_evaluator as fixtures


class GenerationCommitTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):fixtures.GenerationEvaluatorTests.setUpClass();cls.fixture=fixtures.GenerationEvaluatorTests();cls.codec=cls.fixture.codec

    def setup_values(self,**kw):return self.fixture.setup_values(**kw)

    def prepare(self,*values,**kw):
        return prepare_generation_commit(self.codec,*values,expected_store_revision=kw.pop('expected_store_revision',1),
            correlation_ref=kw.pop('correlation_ref','correlation'),**kw)

    def test_separate_without_declared_order_links_only_through_occurrence(self):
        source,use,repo=self.setup_values();p=self.prepare(source,use,repo).plan
        self.assertEqual({w.key.kind for w in p.request.writes},{'TASK','GENERATION_OCCURRENCE'})
        self.assertIsNone(p.relation);self.assertEqual(p.occurrence.target_task_ref,p.draft.target.task_id)
        self.assertIsNone(p.occurrence.relation_ref);self.assertEqual(p.occurrence.state,'CREATED')
        self.assertEqual(p.request.source_ref,'accepted-rule-statement')

    def test_explicit_reverse_completion_link_does_not_reverse_generation(self):
        source,use,repo=self.setup_values(relation=dict(kind='COMPLETION_ORDER',direction='TARGET_TO_SOURCE'))
        p=self.prepare(source,use,repo).plan;r=p.relation
        self.assertEqual((r.relation.before.id,r.relation.after.id),(p.draft.target_id,'source'))
        self.assertEqual((r.relation.origin_rule_id,r.relation.origin_rule_version),('rule','1'))
        self.assertEqual(r.relation.authority_ref,p.permit_ref)
        self.assertEqual(p.occurrence.scope.source_task_id,'source');self.assertEqual(len(p.request.writes),3)

    def test_stage_plan_updates_one_parent_and_adds_explicit_membership(self):
        source,use,repo=self.setup_values(kind='STAGE',facts=dict(stage_weight=1))
        p=self.prepare(source,use,repo,current_source=source.task).plan
        self.assertEqual(p.relation.relation.kind,'STAGE_MEMBERSHIP')
        self.assertEqual((p.relation.before.task_revision,p.relation.after.task_revision),(2,2))
        task_write=next(w for w in p.request.writes if w.key.kind=='TASK')
        self.assertEqual((task_write.key.id,task_write.expected_revision),('source',1))
        self.assertEqual(p.occurrence.target_stage_revision,1);self.assertIsNone(p.occurrence.target_task_ref)

    def test_missing_essential_facts_compose_only_pending_history_effect(self):
        source,use,repo=self.setup_values(facts={});p=self.prepare(source,use,repo).plan
        self.assertEqual([w.key.kind for w in p.request.writes],['GENERATION_OCCURRENCE'])
        self.assertEqual(p.occurrence.state,'PENDING');self.assertIn('/core/domain',p.occurrence.missing_fields)
        self.assertIsNone(p.relation);self.assertEqual(p.observations,())

    def test_new_rule_version_retains_occurrence_and_target_identity(self):
        a=self.prepare(*self.setup_values(version='1')).plan;b=self.prepare(*self.setup_values(version='2')).plan
        self.assertEqual(a.occurrence.scope.generation_key,b.occurrence.scope.generation_key)
        self.assertEqual(a.draft.target_id,b.draft.target_id)
        self.assertNotEqual(a.request.fingerprint,b.request.fingerprint)

    def test_created_replay_returns_original_even_when_new_version_inactive(self):
        created=self.prepare(*self.setup_values()).plan.occurrence
        source,use,repo=self.setup_values(version='2');use=replace(use,record=replace(use.record,rule=replace(use.record.rule,active=False)))
        out=self.prepare(source,use,repo,previous=created)
        self.assertIsNone(out.plan);self.assertEqual(out.recorded,created);self.assertEqual(out.state,'ALREADY_RECORDED')

    def test_pending_can_advance_under_new_accepted_version_without_losing_original_source(self):
        pending=self.prepare(*self.setup_values(facts={})).plan.occurrence
        source,use,repo=self.setup_values(version='2');p=self.prepare(source,use,repo,previous=pending).plan
        self.assertEqual((p.occurrence.state,p.occurrence.revision,p.occurrence.scope.version),('CREATED',2,'2'))
        audit=next(a for a in p.audits if a.key.kind=='GENERATION_OCCURRENCE')
        self.assertEqual(audit.before_revision,1);self.assertEqual(audit.tuple[4],pending.payload)
        self.assertEqual(p.occurrence.creation_transaction_ref,pending.creation_transaction_ref)

    def test_foreign_previous_or_changed_obligation_cannot_be_adopted(self):
        pending=self.prepare(*self.setup_values(facts={})).plan.occurrence
        source,use,repo=self.setup_values();foreign=replace(pending,manifest_json=canonical(dict(principal_id='foreign')))
        with self.assertRaisesRegex(GenerationError,'PREVIOUS_PRINCIPAL'):self.prepare(source,use,repo,previous=foreign)
        source,use,repo=self.setup_values(kind='STAGE')
        with self.assertRaisesRegex(GenerationError,'OBLIGATION_CONFLICT'):self.prepare(source,use,repo,previous=pending)

    def test_every_receipt_key_has_one_exact_audit_and_rebuilds_same_fingerprint(self):
        p=self.prepare(*self.setup_values(relation=dict(kind='SOFT_SEQUENCE',direction='SOURCE_TO_TARGET'))).plan
        changes=tuple(a.tuple for a in p.audits)
        validate_audit_fingerprint(p.receipt,principal_id=p.request.principal_id,expected_store_revision=1,
            source_ref=p.request.source_ref,correlation_ref='other',changes=changes)
        self.assertEqual(len(p.audits),len(p.receipt.changed_keys));self.assertEqual(len({a.change_ref for a in p.audits}),len(p.audits))

    def test_correlation_is_attempt_metadata_and_epoch_changes_commit_not_occurrence_identity(self):
        values=self.setup_values();a=self.prepare(*values).plan;b=self.prepare(*values,correlation_ref='another').plan
        self.assertEqual(a.request.fingerprint,b.request.fingerprint);self.assertEqual(a.request.context.request_id,b.request.context.request_id)
        c=self.prepare(*values,expected_store_revision=2).plan
        self.assertNotEqual(a.request.fingerprint,c.request.fingerprint);self.assertNotEqual(a.request.context.request_id,c.request.context.request_id)
        self.assertEqual(a.occurrence.scope.generation_key,c.occurrence.scope.generation_key)

    def test_pending_stage_can_move_to_closed_parent_failure_without_task_effect(self):
        source,use,repo=self.setup_values(kind='STAGE');pending=self.prepare(source,use,repo).plan.occurrence
        from src.application.task_storage import admit_storage
        v=source.task.aggregate.as_record();v['core']['disposition']=v['effort']['disposition']='CANCELLED'
        parent=admit_storage(self.codec,canonical(v).encode());p=self.prepare(source,use,repo,previous=pending,current_source=parent).plan
        self.assertEqual(p.occurrence.state,'FAILED');self.assertEqual(p.occurrence.failure_code,'GENERATION_PARENT_CLOSED')
        self.assertEqual([w.key.kind for w in p.request.writes],['GENERATION_OCCURRENCE'])

    def test_malformed_or_unapproved_order_spec_cannot_be_inferred(self):
        for spec in (dict(kind='GENERATION',direction='SOURCE_TO_TARGET'),dict(kind='COMPLETION_ORDER',direction='guess'),dict(kind='STAGE_MEMBERSHIP',direction='SOURCE_TO_TARGET')):
            with self.assertRaisesRegex(GenerationError,'RELATION_SPEC'):self.prepare(*self.setup_values(relation=spec))
        source,use,repo=self.setup_values(kind='STAGE',relation=dict(kind='COMPLETION_ORDER',direction='SOURCE_TO_TARGET'))
        with self.assertRaisesRegex(GenerationError,'RELATION_SPEC'):self.prepare(source,use,repo,current_source=source.task)

    def test_occurrence_roundtrip_and_sql_projection_preserve_all_provenance(self):
        p=self.prepare(*self.setup_values()).plan;record=p.occurrence
        self.assertEqual(GenerationOccurrenceRecord.from_payload(record.payload),record)
        row=record.sql_row(p.request.context.request_id,next(a.change_ref for a in p.audits if a.key.kind=='GENERATION_OCCURRENCE'))
        self.assertEqual(row['runtime_payload'],record.payload);self.assertEqual(row['missing_facts'],dict(fields=[]))
        broken=record.payload;broken['generation_key']='changed'
        with self.assertRaisesRegex(GenerationError,'OCCURRENCE_PAYLOAD'):GenerationOccurrenceRecord.from_payload(broken)
        broken=record.payload;broken['extra']='unrecognized'
        with self.assertRaisesRegex(GenerationError,'OCCURRENCE_PAYLOAD'):GenerationOccurrenceRecord.from_payload(broken)
        staged=self.prepare(*self.setup_values(kind='STAGE'),current_source=self.setup_values(kind='STAGE')[0].task).plan.occurrence
        for field in ('revision','source_task_revision','target_stage_revision','relation_revision'):
            broken=staged.payload;broken[field]=True
            with self.assertRaises(GenerationError):GenerationOccurrenceRecord.from_payload(broken)

    def test_preparation_creates_identifiers_but_never_a_permit_or_writes(self):
        p=self.prepare(*self.setup_values()).plan
        self.assertIsInstance(p.permit_ref,str);self.assertFalse(hasattr(p,'permit'))
        self.assertEqual(p.draft.code,'GENERATION_VALIDATED_NOT_AUTHORIZED')
        for epoch in (False,0,-1,9223372036854775807):
            with self.assertRaisesRegex(GenerationError,'COMMIT_CONTEXT'):self.prepare(*self.setup_values(),expected_store_revision=epoch)

    def test_existing_source_budget_is_not_modified_by_generated_observation(self):
        source,use,repo=self.setup_values();bindings=use.record.rule.mappings+(fixtures.literal('user_remaining_seconds',300),)
        source,use,repo=self.setup_values(mappings=bindings);p=self.prepare(source,use,repo).plan
        self.assertEqual(p.observations[0].authority_ref,p.permit_ref);self.assertEqual(p.observations[0].task_id,p.draft.target_id)
        self.assertEqual(source.task.aggregate.budget(at=fixtures.NOW).seconds,600)
        self.assertEqual(p.draft.target.aggregate.budget(at=fixtures.NOW).seconds,300)

    def test_derivative_manual_authority_chain_is_distinct_from_original_acceptance(self):
        source,use,repo=self.setup_values();event=replace(source.event,authority_ref='exact-transaction-permit')
        annotation=dict(grant_ref='source-authority',command=dict(principal_id='user',changes=[dict(task_id='source',action='CREATE_TASK',expected_revision=None)]))
        bound=replace(source,event=event,creation_authorization_json=canonical(annotation))
        self.assertEqual(self.prepare(bound,use,repo).plan.occurrence.creation_transaction_ref,'creation')
        for bad in ({},dict(command=[]),dict(grant_ref='foreign',command=annotation['command'])):
            with self.assertRaisesRegex(GenerationError,'SOURCE_ACCEPTANCE_MISMATCH'):
                replace(source,event=event,creation_authorization_json=canonical(bad))


if __name__=='__main__':unittest.main()
