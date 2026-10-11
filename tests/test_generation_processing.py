import unittest
from dataclasses import replace
from datetime import datetime,timezone
from src.application.definitions import DefinitionKey,canonical
from src.application.generation_commit import digest
from src.application.generation_evaluator import GenerationError
from src.application.generation_processing import ProcessingLimits,ProcessingCheckpoint


class GenerationProcessingTests(unittest.TestCase):
    def setUp(self):
        self.key=DefinitionKey('RELATIONSHIP_RULE','rule','1')
        self.checkpoint=ProcessingCheckpoint(digest({'synthetic':True}),(self.key,))

    def test_limits_are_finite_positive_integer_values_with_hard_ceilings(self):
        for name in ('max_events','max_rules_per_lease','max_attempts','lease_seconds','retry_seconds'):
            for value in (True,0,-1,1000000):
                with self.assertRaisesRegex(GenerationError,'BOUNDED_LIMITS'):replace(ProcessingLimits(),**{name:value})

    def test_checkpoint_round_trip_preserves_rule_versions_progress_and_attempts(self):
        self.assertEqual(ProcessingCheckpoint.from_payload(self.checkpoint.payload),self.checkpoint)
        value=self.checkpoint.payload;value['extra']='approval'
        with self.assertRaisesRegex(GenerationError,'CHECKPOINT_PAYLOAD'):ProcessingCheckpoint.from_payload(value)

    def test_cursor_cannot_skip_or_duplicate_unrecorded_rule_results(self):
        for cursor in (True,-1,1,2):
            with self.assertRaises(GenerationError):replace(self.checkpoint,cursor=cursor)
        with self.assertRaisesRegex(GenerationError,'CHECKPOINT_SCOPE'):
            replace(self.checkpoint,rule_keys=(self.key,DefinitionKey('RELATIONSHIP_RULE','rule','2')))

    def test_result_requires_exact_selected_rule_and_an_honest_outcome(self):
        result=dict(rule={'kind':'RELATIONSHIP_RULE','id':'rule','version':'1'},state='PENDING',occurrence_ref='generation',receipt_ref='receipt')
        value=replace(self.checkpoint,cursor=1,results_json=canonical([result]))
        self.assertEqual(value.payload['results'][0]['state'],'PENDING')
        for patch in ({'state':'APPROVED'},{'occurrence_ref':True},{'receipt_ref':None},{'rule':{'kind':'RELATIONSHIP_RULE','id':'foreign','version':'1'}}):
            with self.assertRaises(GenerationError):replace(value,results_json=canonical([result|patch]))

    def test_continuation_is_retry_and_pending_facts_are_not_done(self):
        now=datetime(2026,1,1,tzinfo=timezone.utc)
        retry=self.checkpoint.outcome(now=now,limits=ProcessingLimits())
        self.assertEqual(retry.kind,'RETRY');self.assertGreater(retry.retry_at,now)
        with self.assertRaisesRegex(GenerationError,'INCOMPLETE_TERMINAL'):replace(self.checkpoint,state='DONE')
        result=dict(rule=vars(self.key),state='PENDING',occurrence_ref='generation',receipt_ref='receipt')
        pending=replace(self.checkpoint,cursor=1,results_json=canonical([result]),state='WAITING_FACTS')
        self.assertEqual(pending.outcome(now=now,limits=ProcessingLimits()).kind,'WAITING_FACTS')
        with self.assertRaisesRegex(GenerationError,'FALSE_DONE'):replace(pending,state='DONE')

    def test_permanent_failure_has_closed_code_and_explicit_result_reference(self):
        now=datetime(2026,1,1,tzinfo=timezone.utc)
        out=replace(self.checkpoint,state='FAILED',code='PROCESSING_INSTANCE_LIMIT').outcome(now=now,limits=ProcessingLimits())
        self.assertEqual(out.code,'PROCESSING_INSTANCE_LIMIT');self.assertIsNotNone(out.result_ref)
        with self.assertRaisesRegex(GenerationError,'CLOSED_CODE'):replace(self.checkpoint,code='raw private diagnostic')


if __name__=='__main__':unittest.main()
