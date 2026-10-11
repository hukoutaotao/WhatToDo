import unittest
from dataclasses import replace
from unittest.mock import patch

from src.adapters.postgres_generation import PostgresGenerationHandler
from src.application.definitions import DefinitionKey
from src.application.evidence_storage import SourceScope
from src.application.generation_evaluator import GenerationError
from src.application.generation_runtime import GenerationPolicy, GenerationOutcome
from src.application.relationship_validation import GraphLimits
from src.domain.authorization import CallerIdentity


class NoDatabase:
    def __getattr__(self, name): raise AssertionError('Unauthorized path touched database: '+name)


class GenerationRuntimeTests(unittest.TestCase):
    def setUp(self):
        self.policy=GenerationPolicy('user',(DefinitionKey('RELATIONSHIP_RULE','rule','1'),),
            (SourceScope('synthetic','scope','account'),))

    def service(self):
        return PostgresGenerationHandler(NoDatabase(),None,None,application_version='0.1.0.dev0',
            clock=None,policy=self.policy)

    def test_policy_requires_one_exact_independent_version_per_stable_rule(self):
        for keys in ((),list(self.policy.rule_keys),self.policy.rule_keys+(DefinitionKey('RELATIONSHIP_RULE','rule','2'),),
                     (DefinitionKey('TASKTYPE','rule','1'),)):
            with self.assertRaisesRegex(GenerationError,'POLICY_RULE_VERSIONS'):replace(self.policy,rule_keys=keys)

    def test_policy_rejects_untyped_empty_or_ambiguous_account_scopes(self):
        for scopes in ((),list(self.policy.source_scopes),({'provider':'synthetic'},),
                       self.policy.source_scopes+(SourceScope('synthetic','scope','foreign'),)):
            with self.assertRaisesRegex(GenerationError,'POLICY_SOURCE_SCOPES'):replace(self.policy,source_scopes=scopes)

    def test_resource_limit_is_applied_before_loading_a_graph(self):
        with self.assertRaisesRegex(GenerationError,'POLICY_RULE_VERSIONS'):
            replace(self.policy,limits=GraphLimits(max_rules=1),rule_keys=self.policy.rule_keys+(DefinitionKey('RELATIONSHIP_RULE','other','1'),))

    def test_caller_principal_authentication_and_origin_are_checked_before_database(self):
        for caller in (CallerIdentity('foreign','RELATIONSHIP_RULE',True),CallerIdentity('user','USER_COMMAND',True),
                       CallerIdentity('user','RELATIONSHIP_RULE',False),CallerIdentity('user','EXTERNAL',True)):
            for method in (self.service().generate,self.service().lookup):
                out=method('event','rule',correlation_ref='scope',caller=caller)
                self.assertEqual(out.status,'PERMANENT');self.assertIsNone(out.value)

    def test_input_cannot_select_an_unregistered_rule_version_or_inject_a_draft(self):
        worker=CallerIdentity('user','RELATIONSHIP_RULE',True)
        out=self.service().generate('event','unselected',correlation_ref='selection',caller=worker)
        self.assertEqual((out.status,out.code),('PERMANENT','GENERATION_RULE_NOT_SELECTED'))
        with self.assertRaises(TypeError):self.service().generate('event','rule',correlation_ref='draft',caller=worker,draft=dict(approved=True))

    def test_fake_definition_repository_cannot_replace_the_independent_sql_reader(self):
        with self.assertRaisesRegex(GenerationError,'TRUSTED_DEFINITION_REPOSITORY'):
            PostgresGenerationHandler(NoDatabase(),None,None,application_version='0.1.0.dev0',clock=None,policy=self.policy,definitions=dict(approved=True))

    def test_optional_driver_absence_is_explicit_without_database_access(self):
        with patch.dict('sys.modules',{'psycopg':None}):
            out=self.service().generate('event','rule',correlation_ref='driver',caller=CallerIdentity('user','RELATIONSHIP_RULE',True))
        self.assertEqual((out.status,out.code),('PERMANENT','TRANSACTION_DRIVER_UNAVAILABLE'))

    def test_outcome_does_not_treat_missing_receipt_as_committed_generation(self):
        self.assertEqual(GenerationOutcome('NOT_ELIGIBLE').state,'NOT_ELIGIBLE')
        for state in ('CREATED','PENDING','FAILED','UNKNOWN'):
            with self.assertRaisesRegex(GenerationError,'GENERATION_OUTCOME'):GenerationOutcome(state)


if __name__=='__main__':unittest.main()
