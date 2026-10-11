"""Versioned prototype transport values; authentication never comes from JSON."""
from dataclasses import dataclass,field
from datetime import datetime
from hashlib import sha256
from hmac import compare_digest
import re
from typing import Protocol
from src.application.command_validation import admit_command
from src.application.definitions import canonical,identity,strict_json
from src.application.fact_patches import admit_fact_patch
from src.application.manual_tasks import manual_command
from src.application.ports import PortResult,RequestContext
from src.application.task_lifecycle import admit_lifecycle_command
from src.application.task_resolution import admit_intent,admit_reply
from src.application.read_models import admit_query
from src.application.work_reports import admit_work_report
from src.domain.authorization import CallerIdentity

MAX_REQUEST_BYTES=2097152;MAX_PAYLOAD_BYTES=262144;MAX_RESPONSE_BYTES=2097152
OPERATIONS=frozenset(('CREATE_TASK','PATCH_TASK','COMPLETE_TASK','CANCEL_TASK','REPORT_WORK','RESOLVE','RESOLVE_CREATION','CLARIFY','RESOLUTION_GET','REFRESH_RESOLUTION','RESOLUTION_HANDOFF','LOOKUP_COMMAND','QUERY_STATE'))
FULL_SCOPE_OPERATIONS=OPERATIONS-{'CREATE_TASK','PATCH_TASK','COMPLETE_TASK','CANCEL_TASK','REPORT_WORK'}
KINDS=frozenset(('RECEIPT','MANUAL_CREATION','RESOLUTION','RESOLUTION_HANDOFF','WORK_REPORT','READ_PAGE'))


class TransportError(RuntimeError):
    def __init__(self,code,http_status=400):super().__init__(code);self.code=code;self.http_status=http_status


def need(value,code,http_status=400):
    if not value:raise TransportError(code,http_status)


def token_digest(token):
    need(isinstance(token,str) and re.fullmatch('[A-Za-z0-9_-]{32,256}',token) is not None,'TRANSPORT_AUTHENTICATION_REQUIRED',401)
    return sha256(token.encode('ascii')).hexdigest()


@dataclass(frozen=True)
class TransportCredential:
    principal_id: str
    token_hash: str = field(repr=False)
    operations: frozenset[str]
    task_ids: frozenset[str] | None
    issued_at: datetime
    expires_at: datetime
    active: bool = True

    def __post_init__(self):
        need(identity(self.principal_id) and isinstance(self.token_hash,str) and re.fullmatch('[a-f0-9]{64}',self.token_hash) is not None,'TRANSPORT_CREDENTIAL_INVALID')
        need(isinstance(self.operations,frozenset) and bool(self.operations) and self.operations<=OPERATIONS,'TRANSPORT_CREDENTIAL_INVALID')
        need(self.task_ids is None or isinstance(self.task_ids,frozenset) and all(identity(x) for x in self.task_ids),'TRANSPORT_CREDENTIAL_INVALID')
        need(isinstance(self.issued_at,datetime) and self.issued_at.utcoffset() is not None and isinstance(self.expires_at,datetime) and self.expires_at.utcoffset() is not None
            and self.expires_at>self.issued_at and type(self.active) is bool,'TRANSPORT_CREDENTIAL_INVALID')

    @property
    def caller(self):return CallerIdentity(self.principal_id,'USER_COMMAND',True)


class CredentialAuthenticator:
    def __init__(self,credentials,*,clock):
        need(isinstance(credentials,tuple) and 1<=len(credentials)<=128 and all(isinstance(c,TransportCredential) for c in credentials)
            and len({c.token_hash for c in credentials})==len(credentials),'TRANSPORT_CREDENTIAL_REGISTRY_INVALID')
        self._credentials=credentials;self.clock=clock

    def authenticate(self,authorization):
        need(isinstance(authorization,str) and authorization.startswith('Bearer '),'TRANSPORT_AUTHENTICATION_REQUIRED',401)
        digest=token_digest(authorization[7:]);matches=[c for c in self._credentials if compare_digest(c.token_hash,digest)]
        now=self.clock.now()
        need(len(matches)==1 and matches[0].active and matches[0].issued_at<=now<matches[0].expires_at,'TRANSPORT_AUTHENTICATION_REQUIRED',401)
        return matches[0]


@dataclass(frozen=True)
class TransportRequest:
    raw_bytes: bytes = field(repr=False)
    payload_json: str = field(repr=False)

    def as_record(self):return strict_json(self.payload_json)
    @property
    def operation(self):return self.as_record()['operation']
    @property
    def context(self):
        v=self.as_record();return RequestContext(v['request_id'],v['correlation_ref'])
    @property
    def parameters(self):return self.as_record()['parameters']
    @property
    def payload_bytes(self):
        payload=self.as_record()['payload'];return payload.encode('utf-8') if payload is not None else None


def admit_request(codec,raw,credential):
    need(isinstance(raw,bytes) and 0<len(raw)<=MAX_REQUEST_BYTES,'TRANSPORT_REQUEST_SIZE_LIMIT',413)
    admitted=codec.admit('prototype-request',raw);need(admitted.status=='SUPPORTED_SHAPE','TRANSPORT_REQUEST_SHAPE_UNSUPPORTED')
    v=admitted.payload;op=v['operation'];need(op in credential.operations,'TRANSPORT_OPERATION_SCOPE_DENIED',403)
    need(all(identity(v[k]) for k in ('request_id','correlation_ref')),'TRANSPORT_REQUEST_IDENTITY')
    for name,value in v['parameters'].items():
        if name in ('expected_store_revision','expected_revision','revision') and value is not None:
            need(type(value) is int and 0<value<2**63,'TRANSPORT_PARAMETER_REVISION')
        if name in ('audit_id','source_ref','session_id','desired_task_id','authority_ref'):
            need(identity(value),'TRANSPORT_PARAMETER_IDENTITY')
    request=TransportRequest(raw,canonical(v));payload=request.payload_bytes
    need(payload is None or len(payload)<=MAX_PAYLOAD_BYTES,'TRANSPORT_PAYLOAD_SIZE_LIMIT',413)
    if op in FULL_SCOPE_OPERATIONS:need(credential.task_ids is None,'TRANSPORT_REFERENCE_SCOPE_DENIED',403)
    owner=None;command_id=None;tasks=()
    if op=='CREATE_TASK':
        command=admit_command(codec,payload).command;manual_command(command);owner=command.principal_id;command_id=command.command_id;tasks=tuple(c.task_id for c in command.changes)
    elif op in ('COMPLETE_TASK','CANCEL_TASK'):
        command=admit_lifecycle_command(codec,payload,'COMPLETE' if op=='COMPLETE_TASK' else 'CANCEL').command
        owner=command.principal_id;command_id=command.command_id;tasks=tuple(c.task_id for c in command.changes)
    elif op=='PATCH_TASK':
        p=admit_fact_patch(codec,payload);owner=p.principal_id;command_id=p.command_id;tasks=(p.task_id,)
    elif op=='REPORT_WORK':
        p=admit_work_report(codec,payload);owner=p.principal_id;command_id=p.command_id;tasks=(p.task_id,)
    elif op=='RESOLVE':
        p=admit_intent(codec,payload).as_record();owner=p['principal_id'];command_id=p['command_id']
    elif op=='CLARIFY':command_id=admit_reply(codec,payload)['reply_id']
    elif op=='QUERY_STATE':admit_query(codec,payload)
    elif op=='RESOLVE_CREATION':need(len(payload)<=8192,'TRANSPORT_PAYLOAD_SIZE_LIMIT',413)
    if owner is not None:need(owner==credential.principal_id,'TRANSPORT_PRINCIPAL_SCOPE_DENIED',403)
    if command_id is not None:need(command_id==v['request_id'],'TRANSPORT_REQUEST_ID_MISMATCH')
    need(credential.task_ids is None or set(tasks)<=credential.task_ids,'TRANSPORT_TASK_SCOPE_DENIED',403)
    return request


@dataclass(frozen=True)
class TransportData:
    payload_json: str = field(repr=False)

    def __post_init__(self):
        v=self.as_record();need(isinstance(v,dict) and set(v)=={'kind','result'} and v['kind'] in KINDS and isinstance(v['result'],dict),'TRANSPORT_DATA_INVALID')
        object.__setattr__(self,'payload_json',canonical(v))
    def as_record(self):return strict_json(self.payload_json)


class CommandBackend(Protocol):
    def dispatch(self,request:TransportRequest,*,caller:CallerIdentity)->PortResult[TransportData]:...
