"""Internal prototype backend: route admitted requests to existing handlers."""
from src.adapters.postgres_fact_patches import PostgresFactPatchHandler
from src.adapters.postgres_lifecycle import PostgresLifecycleHandler
from src.adapters.postgres_manual_tasks import PostgresManualTaskHandler
from src.adapters.postgres_read_models import PostgresReadService
from src.application.read_models import ReadPage
from src.adapters.postgres_resolution import PostgresResolutionService
from src.adapters.postgres_transactions import PostgresTransactionCoordinator
from src.adapters.postgres_work_reports import PostgresWorkReportHandler,WorkReportOutcome
from src.application.command_transport import TransportData,TransportRequest,need
from src.application.definitions import canonical
from src.application.direct_creation import UserInputBinding
from src.application.manual_tasks import ManualCreationOutcome
from src.application.ports import CommitReceipt,PortResult
from src.application.task_resolution import ResolutionFrame,ResolutionHandoff,user


def receipt_value(value):
    return dict(request_id=value.request_id,request_fingerprint=value.request_fingerprint,store_revision=value.store_revision,audit_id=value.audit_id,
        changed_keys=[dict(kind=k.kind,id=k.id) for k in value.changed_keys])


def transport_data(value):
    if isinstance(value,ReadPage):kind='READ_PAGE';result=value.as_record()
    elif isinstance(value,CommitReceipt):kind='RECEIPT';result=receipt_value(value)
    elif isinstance(value,ManualCreationOutcome):
        kind='MANUAL_CREATION';result=dict(state=value.state,task_id=value.task_id,creation_event_ref=value.creation_event_ref,receipt=receipt_value(value.receipt) if value.receipt else None,
            pending_id=value.pending_id,missing_fields=list(value.missing_fields))
    elif isinstance(value,WorkReportOutcome):
        kind='WORK_REPORT';v=value.record.as_record();result=dict(receipt=receipt_value(value.receipt),observation_id=v['observation_id'],task_id=v['task_id'],
            increment_seconds=v['increment_seconds'],resulting_total_seconds=v['resulting_total_seconds'])
    elif isinstance(value,ResolutionFrame):
        kind='RESOLUTION';v=value.as_record();result={k:v[k] for k in ('session_id','revision','command_id','state','question','choices','selected_task_ref','fields','creation_facts','missing_fields','store_revision','course_id')}
        result['scope_hash']=value.fingerprint
    elif isinstance(value,ResolutionHandoff):
        kind='RESOLUTION_HANDOFF';i=value.manual_intent
        result=dict(command=value.command.as_record(),session_id=value.session_id,session_revision=value.session_revision,scope_hash=value.scope_hash,
            expected_store_revision=value.expected_store_revision,source_refs=list(value.source_refs),manual_intent=dict(command_fingerprint=i.command_fingerprint,
                source_ref=i.source_ref,source_observed_at=i.source_observed_at.isoformat(),facts=i.facts) if i else None)
    else:need(False,'TRANSPORT_RESULT_TYPE_UNSUPPORTED')
    return TransportData(canonical(dict(kind=kind,result=result)))


class PostgresPrototypeBackend:
    def __init__(self,connection,codec,plan,*,application_version,clock,definitions=None,grants=(),patch_grants=(),work_grants=(),intents=(),input_bindings=(),course_bindings=(),read_cursor_key=None):
        need(isinstance(input_bindings,tuple) and all(isinstance(b,UserInputBinding) for b in input_bindings),'TRANSPORT_INPUT_BINDINGS_INVALID')
        self.connection=connection;self.codec=codec;self.plan=plan;self.application_version=application_version;self.clock=clock;self.definitions=definitions
        self._read_cursor_key=read_cursor_key
        self._grants=grants;self._patch_grants=patch_grants;self._work_grants=work_grants;self._intents=intents;self._bindings=input_bindings;self._courses=course_bindings

    def dispatch(self,request,*,caller):
        need(isinstance(request,TransportRequest),'TRANSPORT_REQUEST_TYPE_REQUIRED');user(caller)
        op=request.operation;p=request.parameters;raw=request.payload_bytes;context=request.context
        options=dict(application_version=self.application_version,clock=self.clock)
        scopes=tuple(b.scope for b in self._bindings if b.principal_id==caller.principal_id)
        if op=='QUERY_STATE':
            if self._read_cursor_key is None:out=PortResult('PERMANENT','READ_SERVICE_UNCONFIGURED',context.correlation_ref)
            else:out=PostgresReadService(self.connection,self.codec,self.plan,**options,cursor_key=self._read_cursor_key,scopes=scopes).query(raw,context,caller=caller)
        elif op=='CREATE_TASK':
            out=PostgresManualTaskHandler(self.connection,self.codec,self.plan,**options,definitions=self.definitions,grants=self._grants,source_scopes=scopes,intents=self._intents).create(
                raw,context,**p,caller=caller)
        elif op=='PATCH_TASK':out=PostgresFactPatchHandler(self.connection,self.codec,self.plan,**options,grants=self._patch_grants,source_scopes=scopes).patch(raw,context,**p,caller=caller)
        elif op in ('COMPLETE_TASK','CANCEL_TASK'):
            handler=PostgresLifecycleHandler(self.connection,self.codec,self.plan,**options,grants=self._grants,source_scopes=scopes)
            out=(handler.complete if op=='COMPLETE_TASK' else handler.cancel)(raw,context,**p,caller=caller)
        elif op=='REPORT_WORK':out=PostgresWorkReportHandler(self.connection,self.codec,self.plan,**options,grants=self._work_grants,source_scopes=scopes).report(raw,context,**p,caller=caller)
        elif op=='LOOKUP_COMMAND':out=PostgresTransactionCoordinator(self.connection,self.codec,self.plan,**options).lookup_commit(context,caller=caller)
        else:
            service=PostgresResolutionService(self.connection,self.codec,self.plan,**options,input_bindings=self._bindings,course_bindings=self._courses)
            if op=='RESOLVE':out=service.begin(raw,p['source_ref'],context,caller=caller)
            elif op=='CLARIFY':out=service.reply(raw,p['source_ref'],context,caller=caller)
            elif op=='RESOLUTION_GET':out=service.get(p['session_id'],context,revision=p['revision'],caller=caller)
            elif op=='REFRESH_RESOLUTION':out=service.refresh(p['session_id'],p['expected_revision'],p['scope_hash'],context,caller=caller)
            elif op=='RESOLUTION_HANDOFF':out=service.handoff(p['session_id'],p['revision'],p['scope_hash'],p['authority_ref'],context,caller=caller)
            elif op=='RESOLVE_CREATION':
                def prepare():
                    service._driver();source=service._source(p['source_ref'],raw,caller)
                    proposal=(service._normalizer.natural if p['input_mode']=='NATURAL' else service._normalizer.guided)(raw,source,caller=caller)
                    return PortResult('SUCCESS','NORMALIZED',context.correlation_ref,proposal)
                normalized=service._result(prepare,context.correlation_ref)
                out=service.begin_creation(normalized.value,context,session_id=p['session_id'],desired_task_id=p['desired_task_id'],caller=caller) if normalized.status=='SUCCESS' else normalized
            else:need(False,'TRANSPORT_OPERATION_UNSUPPORTED')
        return PortResult(out.status,out.code,out.correlation_ref,transport_data(out.value) if out.status=='SUCCESS' else None)
