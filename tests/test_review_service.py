"""Public queue admission rejects untrusted input before opening SQL work."""
from datetime import datetime,timezone
from pathlib import Path
import json,unittest
from unittest.mock import patch
from src.adapters.clocks import FrozenClock
from src.adapters.contract_json import ContractJSONCodec
from src.adapters.extension_contracts import load_supported_schemas
from src.adapters.postgres_review_service import PostgresReviewQueueService
from src.application.definitions import canonical
from src.application.evidence_storage import SourceScope
from src.application.ports import RequestContext
from src.application.review_queue import ReviewQueueQuery,ReviewQueueCursor
from src.application.transactions import TransactionError
from src.domain.authorization import CallerIdentity

ROOT=Path(__file__).resolve().parents[1]
NOW=datetime(2026,1,1,tzinfo=timezone.utc);USER=CallerIdentity('user','USER_COMMAND',True);KEY=b'x'*32


class ForbiddenSQL:
    def __getattr__(self,name):raise AssertionError('SQL must not run during rejected admission')


class ReviewServiceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        schemas=load_supported_schemas(root=ROOT)
        cls.codec=ContractJSONCodec(schemas)
    def service(self,**kw):
        return PostgresReviewQueueService(ForbiddenSQL(),self.codec,None,application_version='0.1.0.dev0',clock=FrozenClock(NOW),cursor_key=KEY,**kw)
    def query(self,raw=None,caller=USER,svc=None):
        return (svc or self.service()).query(raw if raw is not None else canonical(ReviewQueueQuery(3,5).as_record()).encode(),
            RequestContext('request','correlation'),caller=caller)
    def test_non_user_and_unauthenticated_callers_never_query_sql(self):
        for actor in (CallerIdentity('user','EXTERNAL',True),CallerIdentity('user','RELATIONSHIP_RULE',True),
            CallerIdentity('user','USER_COMMAND',False)):
            out=self.query(caller=actor)
            self.assertEqual((out.status,out.code),('PERMANENT','RESOLUTION_AUTHENTICATED_OWNER_REQUIRED'))
    def test_malformed_filters_approvals_and_future_contracts_never_query_sql(self):
        v=ReviewQueueQuery(3,5).as_record()
        for raw in (b'{',canonical(v|dict(filters=dict(importance=5))).encode(),canonical(v|dict(approved=True)).encode(),
            canonical(v|dict(schema_version='future')).encode(),b'x'*8193):
            self.assertEqual(self.query(raw).status,'PERMANENT')
    def test_signed_cursor_cannot_switch_principal_or_query_without_sql(self):
        q=ReviewQueueQuery(3,5)
        token=ReviewQueueCursor(KEY).encode('snapshot',1,'foreign',q.fingerprint)
        out=self.query(canonical(ReviewQueueQuery(3,5,token).as_record()).encode())
        self.assertEqual((out.status,out.code),('CONFLICT','REVIEW_QUEUE_CURSOR_SCOPE_CONFLICT'))
    def test_invalid_signature_never_reads_snapshot(self):
        out=self.query(canonical(ReviewQueueQuery(3,5,'forged.signature').as_record()).encode())
        self.assertEqual((out.status,out.code),('PERMANENT','REVIEW_QUEUE_CURSOR_INVALID'))
    def test_optional_driver_absence_has_explicit_typed_outcome(self):
        with patch.dict('sys.modules',{'psycopg':None}):out=self.query()
        self.assertEqual((out.status,out.code),('PERMANENT','TRANSACTION_DRIVER_UNAVAILABLE'))
    def test_trusted_scope_bindings_must_be_typed_and_unique(self):
        scope=SourceScope('provider','scope','account')
        for scopes in ([scope],(scope,scope),('from-json',)):
            with self.assertRaises(TransactionError):self.service(source_scopes=scopes)
