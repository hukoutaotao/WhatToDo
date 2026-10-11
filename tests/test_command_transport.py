from contextlib import contextmanager
from datetime import datetime,timedelta,timezone
from http.client import HTTPConnection
from pathlib import Path
from threading import Thread
import json
import unittest
from src.adapters.clocks import FrozenClock
from src.adapters.contract_json import ContractJSONCodec
from src.adapters.prototype_codec import PrototypeJSONCodec
from src.adapters.extension_contracts import load_supported_schemas
from src.adapters.packaged_contracts import load_contract_schemas
from src.adapters.prototype_http import AuthenticatedCommandTransport,make_http_server
from src.application.command_transport import (CredentialAuthenticator,TransportCredential,TransportData,TransportError,OPERATIONS,MAX_REQUEST_BYTES,token_digest)
from src.application.definitions import canonical
from src.application.ports import PortResult
from src.domain.authorization import Command,change
NOW=datetime(2026,1,1,tzinfo=timezone.utc);TOKEN='synthetic-prototype-token-for-tests-0001';ROOT=Path(__file__).resolve().parents[1]
CODEC=PrototypeJSONCodec(load_supported_schemas(root=ROOT))


def credential(token=TOKEN,principal='principal',operations=OPERATIONS,tasks=None,**kw):
    values=dict(principal_id=principal,token_hash=token_digest(token),operations=operations,task_ids=tasks,issued_at=NOW-timedelta(minutes=1),expires_at=NOW+timedelta(hours=1));values.update(kw)
    return TransportCredential(**values)


def command(principal='principal',command_id='command',task='a'):
    return Command(command_id,principal,'USER_COMMAND','synthetic-root',(change(task,1,'UPDATE_TASK',dict(completion='COMPLETE')),)).as_record()


def envelope(operation='COMPLETE_TASK',payload=None,parameters=None,request_id='command'):
    return dict(schema_version='0.1.0-prototype-request',operation=operation,request_id=request_id,correlation_ref='correlation',payload=canonical(payload if payload is not None else command()),
        parameters=parameters if parameters is not None else dict(expected_store_revision=1,audit_id='audit'))


def data(request_id='command'):
    return TransportData(canonical(dict(kind='RECEIPT',result=dict(request_id=request_id,request_fingerprint='a'*64,store_revision=2,audit_id='audit',changed_keys=[dict(kind='TASK',id='a')]))))


class TransportTests(unittest.TestCase):
    def setUp(self):
        self.calls=[];self.opens=0;self.clock=FrozenClock(NOW);self.result=None
        test=self
        class Backend:
            def dispatch(self,request,*,caller):
                test.calls.append((request,caller))
                if isinstance(test.result,Exception):raise test.result
                return test.result if test.result is not None else PortResult('SUCCESS','COMMITTED',request.context.correlation_ref,data(request.context.request_id))
        @contextmanager
        def factory():
            self.opens+=1;yield Backend()
        self.factory=factory;self.transport=self.make()
    def make(self,credentials=None):return AuthenticatedCommandTransport(CODEC,clock=self.clock,credentials=credentials or (credential(),),backend_factory=self.factory)
    def send(self,value=None,raw=None,token=TOKEN,transport=None):return (transport or self.transport).handle(raw if raw is not None else canonical(value or envelope()).encode(),authorization='Bearer '+token if token else None)
    def denied(self,**kw):
        out=self.send(**kw);self.assertEqual(self.opens,0);self.assertEqual(self.calls,[]);self.assertNotEqual(out.as_record()['status'],'SUCCESS');return out

    def test_valid_context_uses_authenticated_principal(self):
        out=self.send();self.assertEqual(out.http_status,200);self.assertEqual(self.calls[0][1].principal_id,'principal');self.assertTrue(self.calls[0][1].authenticated)
        self.assertEqual(self.calls[0][1].origin,'USER_COMMAND');self.assertEqual(out.as_record()['next_action'],'NONE')
    def test_unauthenticated_invalid_bytes_fail_before_validation_or_factory(self):
        self.assertEqual(self.denied(raw=b'invalid',token=None).http_status,401)
    def test_wrong_token_fails_before_factory(self):self.assertEqual(self.denied(token='synthetic-unknown-token-for-tests-9999').http_status,401)
    def test_short_non_ascii_or_header_injection_token_rejected(self):
        for token in ('short','x'*32+'\r\n','\u6d4b'*32):self.assertEqual(self.denied(token=token).http_status,401)
    def test_expired_inactive_future_credentials_fail(self):
        for c in (credential(expires_at=NOW),credential(active=False),credential(issued_at=NOW+timedelta(minutes=1))):
            self.assertEqual(self.denied(transport=self.make((c,))).http_status,401)
    def test_operation_capability_precedes_handler(self):
        self.assertEqual(self.denied(transport=self.make((credential(operations=frozenset({'CREATE_TASK'})),))).http_status,403)
    def test_task_scope_and_empty_scope_precede_handler(self):
        for tasks in (frozenset({'b'}),frozenset()):self.assertEqual(self.denied(transport=self.make((credential(tasks=tasks),))).http_status,403)
    def test_matching_narrow_task_scope_is_allowed(self):self.assertEqual(self.send(transport=self.make((credential(tasks=frozenset({'a'})),))).http_status,200)
    def test_foreign_principal_payload_cannot_become_caller(self):self.assertEqual(self.denied(value=envelope(payload=command('other'))).http_status,403)
    def test_request_id_must_equal_original_command(self):self.assertEqual(self.denied(value=envelope(request_id='another')).as_record()['code'],'TRANSPORT_REQUEST_ID_MISMATCH')
    def test_payload_cannot_add_caller_credential_or_arbitrary_sql(self):
        for name,value in (('caller',dict(principal_id='principal',authenticated=True)),('authorization','Bearer '+TOKEN),('sql','DROP TABLE task'),('grant',dict(active=True))):
            v=envelope();v[name]=value;self.assertEqual(self.denied(value=v).http_status,400)
    def test_unknown_versions_operations_and_parameter_keys_rejected(self):
        for v in (envelope()|dict(schema_version='future'),envelope()|dict(operation='RUN_SQL'),envelope(parameters=dict(expected_store_revision=1,audit_id='audit',grants=[]))):
            self.assertEqual(self.denied(value=v).http_status,400)
    def test_duplicate_keys_and_nonfinite_json_rejected(self):
        raw=canonical(envelope()).encode()
        for bad in (raw[:-1]+b',"operation":"COMPLETE_TASK"}',b'{"value":NaN}',b'{"value":1e9999}',b'\xff'):
            self.assertEqual(self.denied(raw=bad).http_status,400)
    def test_nested_duplicate_keys_do_not_reach_handler(self):
        v=envelope();v['payload']=canonical(command())[:-1]+',"principal_id":"principal"}'
        self.assertEqual(self.denied(value=v).http_status,400)
    def test_wrong_action_and_extra_lifecycle_effects_do_not_reach_handler(self):
        for payload in (command()|dict(origin='EXTERNAL'),command()|dict(origin='RELATIONSHIP_RULE')):
            self.assertEqual(self.denied(value=envelope(payload=payload)).http_status,400)
        payload=command();payload['changes'][0]['fields']['importance']=5
        self.assertEqual(self.denied(value=envelope(payload=payload)).http_status,400)
    def test_outer_and_inner_byte_limits(self):
        self.assertEqual(self.denied(raw=b'x'*(MAX_REQUEST_BYTES+1)).http_status,413)
        v=envelope(operation='RESOLVE_CREATION',parameters=dict(source_ref='source',session_id='session',desired_task_id='new',input_mode='NATURAL'));v['payload']='\u6d4b'*400000
        self.assertEqual(self.denied(value=v).http_status,413)
    def test_reference_operations_require_full_task_scope(self):
        v=envelope(operation='LOOKUP_COMMAND',parameters={});v['payload']=None
        self.assertEqual(self.denied(value=v,transport=self.make((credential(tasks=frozenset({'a'})),))).as_record()['code'],'TRANSPORT_REFERENCE_SCOPE_DENIED')
    def test_integer_and_null_parameter_meaning_not_coerced(self):
        for value in (True,0,1.0,None,'1'):
            v=envelope(parameters=dict(expected_store_revision=value,audit_id='audit'));self.assertEqual(self.denied(value=v).http_status,400)
    def test_original_inner_payload_bytes_preserved(self):
        v=envelope();v['payload']=json.dumps(command(),indent=2);self.send(value=v)
        self.assertEqual(self.calls[0][0].payload_bytes,v['payload'].encode());self.assertEqual(self.calls[0][0].raw_bytes,canonical(v).encode())
    def test_detached_parameters_cannot_change_admitted_request(self):
        self.send();r=self.calls[0][0];p=r.parameters;p['audit_id']='changed';self.assertEqual(r.parameters['audit_id'],'audit')
    def test_all_typed_outcomes_preserve_meaning(self):
        for status,http_status,action in (('UNKNOWN',202,'RECONCILE'),('RETRYABLE',503,'RETRY_LATER'),('CONFLICT',409,'RESOLVE_CONFLICT'),('PERMANENT',400,'CORRECT_REQUEST')):
            self.result=PortResult(status,'SYNTHETIC_RESULT','correlation');out=self.send();self.assertEqual(out.http_status,http_status);self.assertEqual(out.as_record()['next_action'],action);self.assertIsNone(out.as_record()['data'])
    def test_exception_after_handler_does_not_claim_no_commit(self):
        self.result=RuntimeError('secret '+TOKEN);out=self.send();self.assertEqual(out.as_record()['status'],'UNKNOWN');self.assertNotIn(TOKEN,out.body_bytes.decode())
    def test_failed_result_serialization_is_unknown_and_redacted(self):
        self.result=PortResult('SUCCESS','COMMITTED','correlation',TransportData(canonical(dict(kind='RECEIPT',result=dict(raw_content=TOKEN)))))
        out=self.send();self.assertEqual(out.http_status,202);self.assertNotIn(TOKEN,out.body_bytes.decode())
    def test_wrong_result_correlation_is_unknown(self):
        self.result=PortResult('SUCCESS','COMMITTED','wrong',data());self.assertEqual(self.send().as_record()['status'],'UNKNOWN')
    def test_factory_exit_failure_is_unknown_after_dispatch(self):
        @contextmanager
        def factory():
            class Backend:
                def dispatch(self,request,*,caller):return PortResult('SUCCESS','COMMITTED','correlation',data())
            yield Backend();raise RuntimeError(TOKEN)
        t=AuthenticatedCommandTransport(CODEC,clock=self.clock,credentials=(credential(),),backend_factory=factory)
        self.assertEqual(self.send(transport=t).as_record()['status'],'UNKNOWN')
    def test_credential_registry_rejects_aliasing_identity_or_bad_definition(self):
        for values in ((credential(),credential(principal='other')),()):
            with self.assertRaises(TransportError):CredentialAuthenticator(values,clock=self.clock)
        with self.assertRaises(TransportError):credential(operations=frozenset({'RUN_SQL'}))
        self.assertNotIn(TOKEN,repr(credential()));self.assertNotIn(credential().token_hash,repr(credential()))
    def test_default_base_codec_cannot_start_transport(self):
        with self.assertRaises(TransportError):AuthenticatedCommandTransport(ContractJSONCodec(load_contract_schemas(root=ROOT)),clock=self.clock,credentials=(credential(),),backend_factory=self.factory)
    def test_non_loopback_binding_is_rejected_before_listening(self):
        for host in ('0.0.0.0','localhost','example.com'):
            with self.assertRaises(TransportError):make_http_server(self.transport,host=host)
    def test_http_wire_matches_direct_n8n_contract_and_typed_rejections(self):
        server=make_http_server(self.transport);thread=Thread(target=server.serve_forever,kwargs=dict(poll_interval=.02));thread.start()
        def call(method,path,body,headers):
            c=HTTPConnection('127.0.0.1',server.server_port,timeout=3)
            try:
                c.request(method,path,body=body,headers=headers);r=c.getresponse();return r.status,r.read(),r.getheader('Cache-Control')
            finally:c.close()
        headers=dict(Authorization='Bearer '+TOKEN);headers['Content-Type']='application/json'
        try:
            raw=canonical(envelope()).encode();status,body,cache=call('POST','/v1/commands',raw,headers)
            self.assertEqual(status,200);self.assertEqual(json.loads(body),self.send(raw=raw).as_record());self.assertEqual(cache,'no-store')
            initial=self.opens
            for method,path,body,h,status in (('GET','/v1/commands',None,{},405),('POST','/wrong',raw,headers,404),('POST','/v1/commands',raw,{},401),('POST','/v1/commands',raw,headers|{'Content-Type':'text/plain'},415),('POST','/v1/commands',None,headers|{'Content-Length':str(MAX_REQUEST_BYTES+1)},413),('POST','/v1/commands',raw,headers|{'Transfer-Encoding':'chunked'},411)):
                observed,body,_=call(method,path,body,h);self.assertEqual(observed,status);self.assertEqual(json.loads(body)['status'],'PERMANENT')
            self.assertEqual(self.opens,initial)
        finally:server.shutdown();server.server_close();thread.join(timeout=3);self.assertFalse(thread.is_alive())

if __name__=='__main__':unittest.main()
