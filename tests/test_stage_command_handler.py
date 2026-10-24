"""The stage transport boundary rejects untrusted requests before database I/O."""
from dataclasses import replace
from pathlib import Path
import unittest

from src.adapters.migration_files import load_migration_plan
from src.adapters.postgres_stage_commands import PostgresStageCommandHandler, StageCommandOutcome
from src.application.definitions import canonical
from src.application.evidence_storage import SourceScope
from src.application.ports import RequestContext
from src.application.transactions import TransactionError
from src.domain.authorization import CallerIdentity
from tests import test_stage_commands as fixtures
from src.application.stage_commit import prepare_stage_commit

ROOT=Path(__file__).resolve().parents[1]


class NoDatabase:
    def __getattr__(self,key): raise AssertionError('Untrusted request reached database')


class StageHandlerBoundaryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        fixtures.StageCommandTests.setUpClass();cls.fixture=fixtures.StageCommandTests()
        cls.plan=load_migration_plan(root=ROOT)

    def handler(self,**kwargs):
        return PostgresStageCommandHandler(NoDatabase(),self.fixture.codec,self.plan,
            application_version='0.1.0.dev0',clock=type('Clock',(),{'now':lambda _:fixtures.NOW})(),**kwargs)

    def submit(self,raw,*,caller=fixtures.USER,context=None):
        return self.handler().execute(raw,context or RequestContext('command','trace'),
            expected_store_revision=1,audit_id='audit',caller=caller)

    def test_unknown_schema_extra_approval_and_duplicate_json_are_rejected_before_io(self):
        c,_,_=self.fixture.fixture()
        for value in (c.as_record()|dict(schema_version='future'),c.as_record()|dict(approved=True)):
            result=self.submit(canonical(value).encode())
            self.assertEqual(result.code,'STAGE_COMMAND_SHAPE_UNSUPPORTED')
        raw=canonical(c.as_record()).replace('"operation":"REWORK"','"operation":"REWORK","operation":"COMPLETE"').encode()
        self.assertEqual(self.submit(raw).code,'STAGE_COMMAND_SHAPE_UNSUPPORTED')

    def test_foreign_unauthenticated_or_nonuser_callers_cannot_reach_storage(self):
        c,_,_=self.fixture.fixture();raw=canonical(c.as_record()).encode()
        for caller in (CallerIdentity('foreign','USER_COMMAND',True),CallerIdentity('user','USER_COMMAND',False),
            CallerIdentity('user','EXTERNAL',True),CallerIdentity('user','RELATIONSHIP_RULE',True)):
            result=self.submit(raw,caller=caller)
            self.assertEqual(result.status,'PERMANENT')
            self.assertIn(result.code,('UNTRUSTED_CALLER','STAGE_TRUSTED_USER_CALLER'))

    def test_changed_transport_request_id_does_not_bind_another_command(self):
        c,_,_=self.fixture.fixture()
        self.assertEqual(self.submit(canonical(c.as_record()).encode(),context=RequestContext('other','trace')).code,'STAGE_TRUSTED_USER_CALLER')

    def test_grants_and_source_scopes_are_typed_independent_registries(self):
        _,g,_=self.fixture.fixture();scope=SourceScope('provider','scope','account')
        for kwargs in (dict(grants=[g]),dict(grants=(g,g)),dict(grants=({'approved':True},)),
            dict(source_scopes=[scope]),dict(source_scopes=(scope,scope)),dict(source_scopes=({'account':'guessed'},))):
            with self.assertRaises(TransactionError):self.handler(**kwargs)

    def test_foreign_definition_repository_and_nonpositive_limits_are_not_trusted(self):
        for kwargs in (dict(definitions=object()),dict(limits=None)):
            with self.assertRaises(TransactionError):self.handler(**kwargs)

    def test_outcome_requires_the_original_command_and_a_journal_in_its_receipt(self):
        c,g,b=self.fixture.fixture()
        plan=prepare_stage_commit(self.fixture.codec,canonical(c.as_record()).encode(),g,b,caller=fixtures.USER,
            now=fixtures.NOW,context=RequestContext(c.command_id,'trace'),expected_store_revision=1,audit_id='audit')
        self.assertEqual(StageCommandOutcome(plan.journal,plan.receipt).state,'COMMITTED')
        for receipt in (None,replace(plan.receipt,request_id='other'),replace(plan.receipt,changed_keys=tuple(k for k in plan.receipt.changed_keys if k.kind=='TASK'))):
            with self.assertRaisesRegex(TransactionError,'TYPED_OUTCOME'):StageCommandOutcome(plan.journal,receipt)
