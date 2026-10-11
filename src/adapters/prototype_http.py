"""Loopback-only HTTP binding over the shared authenticated command envelope."""
from dataclasses import dataclass,field
from http.server import BaseHTTPRequestHandler,HTTPServer
import socket
from time import monotonic
from src.adapters.prototype_codec import PrototypeJSONCodec
from src.application.command_transport import (CredentialAuthenticator,TransportData,TransportError,admit_request,MAX_REQUEST_BYTES,MAX_RESPONSE_BYTES,need)
from src.application.definitions import canonical,strict_json
from src.application.ports import PortResult


@dataclass(frozen=True)
class TransportResponse:
    http_status: int
    body_bytes: bytes = field(repr=False)
    def as_record(self):return strict_json(self.body_bytes)


class AuthenticatedCommandTransport:
    def __init__(self,codec,*,clock,credentials,backend_factory):
        need(isinstance(codec,PrototypeJSONCodec),'TRANSPORT_ENVELOPE_CODEC_REQUIRED')
        self.codec=codec;self._auth=CredentialAuthenticator(credentials,clock=clock);self._factory=backend_factory
        need(callable(backend_factory),'TRANSPORT_BACKEND_FACTORY_REQUIRED')
        probe=canonical(dict(schema_version='0.1.0-prototype-response',request_id=None,correlation_ref='prototype-startup',status='PERMANENT',code='TRANSPORT_STARTUP',next_action='CORRECT_REQUEST',data=None)).encode()
        need(codec.admit('prototype-response',probe).status=='SUPPORTED_SHAPE','TRANSPORT_RESPONSE_CONTRACT_REQUIRED')

    def _response(self,result,request_id,http_status):
        value=dict(schema_version='0.1.0-prototype-response',request_id=request_id,correlation_ref=result.correlation_ref,status=result.status,code=result.code,
            next_action=result.next_action,data=result.value.as_record() if result.status=='SUCCESS' else None)
        raw=canonical(value).encode();need(len(raw)<=MAX_RESPONSE_BYTES,'TRANSPORT_RESULT_SIZE_LIMIT')
        need(self.codec.admit('prototype-response',raw).status=='SUPPORTED_SHAPE','TRANSPORT_RESULT_SHAPE_UNSUPPORTED')
        return TransportResponse(http_status,raw)

    def reject(self,code,http_status):
        return self._response(PortResult('PERMANENT',code,'prototype-unidentified'),None,http_status)

    def handle(self,raw,*,authorization):
        try:credential=self._auth.authenticate(authorization)
        except TransportError as exc:return self.reject(exc.code,exc.http_status)
        try:request=admit_request(self.codec,raw,credential)
        except TransportError as exc:return self.reject(exc.code,exc.http_status)
        except Exception:return self.reject('TRANSPORT_REQUEST_VALIDATION_FAILED',400)
        context=request.context
        try:
            with self._factory() as backend:result=backend.dispatch(request,caller=credential.caller)
            need(isinstance(result,PortResult) and result.correlation_ref==context.correlation_ref and (result.status!='SUCCESS' or isinstance(result.value,TransportData)),
                'TRANSPORT_RESULT_INVALID')
            if result.status=='SUCCESS':
                kinds={'CREATE_TASK':'MANUAL_CREATION','PATCH_TASK':'RECEIPT','COMPLETE_TASK':'RECEIPT','CANCEL_TASK':'RECEIPT','REPORT_WORK':'WORK_REPORT',
                    'RESOLVE':'RESOLUTION','RESOLVE_CREATION':'RESOLUTION','CLARIFY':'RESOLUTION','RESOLUTION_GET':'RESOLUTION','REFRESH_RESOLUTION':'RESOLUTION',
                    'RESOLUTION_HANDOFF':'RESOLUTION_HANDOFF','LOOKUP_COMMAND':'RECEIPT','QUERY_STATE':'READ_PAGE'}
                need(result.value.as_record()['kind']==kinds[request.operation],'TRANSPORT_RESULT_OPERATION_MISMATCH')
            status={'SUCCESS':200,'PERMANENT':400,'CONFLICT':409,'RETRYABLE':503,'UNKNOWN':202}[result.status]
            return self._response(result,context.request_id,status)
        except Exception:
            # A handler/factory exit or serialization failure may follow commit.
            return self._response(PortResult('UNKNOWN','TRANSPORT_RESULT_UNAVAILABLE',context.correlation_ref),context.request_id,202)


def make_http_server(transport,*,host='127.0.0.1',port=0):
    need(isinstance(transport,AuthenticatedCommandTransport) and host=='127.0.0.1' and type(port) is int and 0<=port<=65535,'TRANSPORT_LOOPBACK_BINDING_REQUIRED')
    class Handler(BaseHTTPRequestHandler):
        protocol_version='HTTP/1.0';server_version='WhatToDoPrototype';sys_version=''
        def log_message(self,*args):pass
        def _send(self,result):
            self.send_response(result.http_status);self.send_header('Content-Type','application/json; charset=utf-8')
            self.send_header('Content-Length',str(len(result.body_bytes)));self.send_header('Cache-Control','no-store')
            self.send_header('Connection','close');self.end_headers();self.close_connection=True
            try:
                if getattr(self,'command',None)!='HEAD':self.wfile.write(result.body_bytes)
                self.wfile.flush()
                self.connection.shutdown(socket.SHUT_WR)
            except (BrokenPipeError,ConnectionResetError):pass
            # Windows may reset an early rejection with unread request bytes.
            # After sending the response, discard bounded bytes without parsing
            # or opening a backend, then finish the half-closed connection.
            if not getattr(self,'_body_consumed',False):
                try:
                    self.connection.settimeout(.02);discarded=0;deadline=monotonic()+.1
                    while discarded<MAX_REQUEST_BYTES and monotonic()<deadline:
                        block=self.rfile.read1(min(65536,MAX_REQUEST_BYTES-discarded))
                        if not block:break
                        discarded+=len(block)
                except OSError:pass
        def send_error(self,code,message=None,explain=None):
            self._send(transport.reject('TRANSPORT_HTTP_REQUEST_INVALID',code))
        def do_POST(self):
            if self.path!='/v1/commands':return self._send(transport.reject('TRANSPORT_ROUTE_UNSUPPORTED',404))
            authorization=self.headers.get_all('Authorization') or []
            if len(authorization)!=1:return self._send(transport.reject('TRANSPORT_AUTHENTICATION_REQUIRED',401))
            # Reject auth before reading a potentially large body or opening DB.
            try:transport._auth.authenticate(authorization[0])
            except TransportError as exc:return self._send(transport.reject(exc.code,exc.http_status))
            lengths=self.headers.get_all('Content-Length') or []
            if len(lengths)!=1 or self.headers.get('Transfer-Encoding') is not None:return self._send(transport.reject('TRANSPORT_CONTENT_LENGTH_REQUIRED',411))
            if not lengths[0].isascii() or not lengths[0].isdigit() or len(lengths[0])>9:return self._send(transport.reject('TRANSPORT_CONTENT_LENGTH_INVALID',400))
            length=int(lengths[0])
            if not 0<length<=MAX_REQUEST_BYTES:return self._send(transport.reject('TRANSPORT_REQUEST_SIZE_LIMIT',413))
            content_types=self.headers.get_all('Content-Type') or []
            if len(content_types)!=1 or content_types[0].lower() not in ('application/json','application/json; charset=utf-8'):
                return self._send(transport.reject('TRANSPORT_CONTENT_TYPE_REQUIRED',415))
            try:
                deadline=monotonic()+5;parts=[];remaining=length
                while remaining:
                    timeout=deadline-monotonic()
                    if timeout<=0:raise socket.timeout()
                    self.connection.settimeout(timeout);block=self.rfile.read1(min(65536,remaining))
                    if not block:break
                    parts.append(block);remaining-=len(block)
                raw=b''.join(parts);self._body_consumed=not remaining
            except (socket.timeout,OSError):return self._send(transport.reject('TRANSPORT_REQUEST_INCOMPLETE',408))
            if len(raw)!=length:return self._send(transport.reject('TRANSPORT_REQUEST_INCOMPLETE',400))
            self._send(transport.handle(raw,authorization=authorization[0]))
        def do_GET(self):self._send(transport.reject('TRANSPORT_METHOD_UNSUPPORTED',405))
        do_PUT=do_GET;do_DELETE=do_GET;do_PATCH=do_GET;do_OPTIONS=do_GET;do_HEAD=do_GET;do_TRACE=do_GET;do_CONNECT=do_GET
    return HTTPServer((host,port),Handler)
