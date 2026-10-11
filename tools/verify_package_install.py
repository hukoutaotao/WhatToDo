"""Build and install a pinned private wheel in two new project-owned environments.

All pip work after cache preparation is offline. No existing environment is
replaced or deleted, and no global installation or package publication occurs.
"""
from hashlib import sha256
import json
import os
from pathlib import Path
import platform
import subprocess
import sys
from uuid import uuid4
import venv
import zipfile

ROOT=Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:sys.path.insert(0,str(ROOT))
from tools.check_generic_baseline import BASELINE,validate_baseline
from tools.check_import_boundaries import check_tree
from tools.validate_task_core import load_json


def run(argv, *, cwd, env):
    result=subprocess.run([str(a) for a in argv],cwd=cwd,env=env,capture_output=True,text=True,encoding='utf-8',errors='replace',timeout=120,creationflags=subprocess.CREATE_NO_WINDOW if os.name=='nt' else 0)
    if result.returncode:raise RuntimeError('PACKAGE_COMMAND_FAILED:'+Path(str(argv[0])).name+'\n'+result.stderr[-2000:])
    return result.stdout.strip()


def interpreter(root):return root/('Scripts/python.exe' if os.name=='nt' else 'bin/python')


def main():
    if os.name!='nt' or platform.python_version()!='3.13.5' or platform.machine().lower() not in ('amd64','x86_64'):
        print('Package-install acceptance currently targets Windows x64 / Python 3.13.5',file=sys.stderr);return 1
    errors=validate_baseline(load_json(BASELINE));module_count,import_errors=check_tree()
    if errors or import_errors:print('BASELINE_OR_IMPORT_BOUNDARY_FAILED',file=sys.stderr);return 1
    run_root=ROOT/'.dev-tools/package-validation'/uuid4().hex
    run_root.mkdir(parents=True,exist_ok=False)
    env=dict(os.environ)
    for key in list(env):
        if key.startswith(('OPENAI_','ANTHROPIC_','WHATTODO_')) or key in ('PYTHONPATH','PYTHONHOME'):env.pop(key,None)
    env.update(PIP_NO_INDEX='1',PIP_DISABLE_PIP_VERSION_CHECK='1',PYTHONNOUSERSITE='1',PYTHONUTF8='1')
    report=dict(task='M3A-01',status='IN_PROGRESS',scope='PRIVATE_PACKAGE_SYNTHETIC_ACCEPTANCE',python_version=platform.python_version(),import_modules_checked=module_count,optional_credentials='ABSENT_IN_CHILD_ENV',network='DISABLED_FOR_BUILD_AND_INSTALL',global_environment_modified=False)
    try:
        build_env=run_root/'builder';clean_env=run_root/'installed';venv.EnvBuilder(with_pip=True).create(build_env);venv.EnvBuilder(with_pip=True).create(clean_env)
        builder=interpreter(build_env);installed=interpreter(clean_env)
        run([builder,'-m','pip','install','--no-index','--find-links',ROOT/'.dev-tools/wheelhouse/build','--require-hashes','-r',ROOT/'requirements-build.lock'],cwd=run_root,env=env)
        wheel_dir=run_root/'wheels'
        run([builder,'-m','pip','wheel','--no-build-isolation','--no-deps','--wheel-dir',wheel_dir,ROOT],cwd=run_root,env=env)
        wheels=list(wheel_dir.glob('whattodo_core-0.1.0.dev0-*.whl'))
        if len(wheels)!=1:raise RuntimeError('PACKAGE_WHEEL_IDENTITY')
        wheel=wheels[0]
        with zipfile.ZipFile(wheel) as archive:
            names=archive.namelist()
            if any('/intake/' in n or n.startswith(('tests/','tools/','plan/','.')) for n in names):raise RuntimeError('PRIVATE_OR_DEVELOPER_ARTIFACT_PACKAGED')
            schemas=[n for n in names if n.endswith('.schema.json')]
            if len(schemas)!=41:raise RuntimeError('PACKAGED_CONTRACT_COVERAGE')
        run([installed,'-m','pip','install','--no-index','--find-links',ROOT/'.dev-tools/wheelhouse/core','--require-hashes','-r',ROOT/'requirements-runtime.lock'],cwd=run_root,env=env)
        local_lock=run_root/'package.lock'
        digest=sha256(wheel.read_bytes()).hexdigest()
        local_lock.write_text(wheel.as_uri()+' --hash=sha256:'+digest+'\n',encoding='utf-8')
        run([installed,'-m','pip','install','--no-index','--no-deps','--require-hashes','-r',local_lock],cwd=run_root,env=env)
        report['pip_check']=run([installed,'-m','pip','check'],cwd=run_root,env=env)
        code="""import json,pathlib,sys,sysconfig,importlib.util,importlib.metadata
from datetime import datetime,timezone,date,timedelta
import src
from src.application.package_smoke import domain_smoke
from src.adapters.packaged_contracts import load_contract_schemas
from src.adapters.extension_contracts import load_supported_schemas
from src.application.fact_patches import FactPatch,FactPatchGrant,admit_fact_patch,prepare_fact_patch
from src.adapters.postgres_fact_patches import PostgresFactPatchHandler
from src.application.task_lifecycle import admit_lifecycle_command,prepare_lifecycle_task
from src.adapters.postgres_lifecycle import PostgresLifecycleHandler
from src.application.work_reports import WorkReportGrant,admit_work_report,prepare_work_report
from src.adapters.postgres_work_reports import PostgresWorkReportHandler
from src.adapters.postgres_actual_work import PostgresActualWorkRepository
from src.application.direct_creation import DirectCreationNormalizer,UserInputBinding,guided_message
from src.adapters.contract_json import ContractJSONCodec
from src.adapters.clocks import FrozenClock
from src.domain.time_values import UtcInstant,DateOnly
from src.adapters.runtime_config import load_runtime_config
from src.adapters.migration_files import load_migration_plan
from src.adapters.postgres_migrations import DatabaseRoles
from src.adapters.postgres_creation_outbox import PostgresCreationOutbox
from src.application.creation_outbox import CreationEvent,DeliveryLease,DeliveryOutcome,event_id_for
from src.application.task_storage import admit_storage,TaskStorageBindings,project_task
from src.adapters.postgres_tasks import PostgresTaskRepository
from src.application.evidence_storage import SourceScope,admit_source,admit_candidate
from src.adapters.postgres_evidence import PostgresEvidenceRepository
from src.application.ports import AggregateKey,CommitRequest,RecordWrite,RequestContext,TransactionPermit
from src.application.transactions import prepare_transaction
from src.application.command_ledger import receipt_from_row,validate_audit_fingerprint
from src.application.command_validation import admit_command,validate_effects
from src.adapters.postgres_authorization import PostgresCommandService,register_grant
from src.adapters.postgres_manual_tasks import PostgresManualTaskHandler
from src.application.manual_tasks import ResolvedManualIntent,prepare_manual_task
from src.adapters.postgres_transactions import PostgresTransactionCoordinator
from src.domain.authorization import CallerIdentity,AuthorityGrant,Command,change
from src.domain.provenance import capture_source,make_candidate
schemas=load_contract_schemas()
codec=ContractJSONCodec(schemas)
assert pathlib.Path(src.__file__).resolve().is_relative_to(pathlib.Path(sys.prefix).resolve())
assert importlib.util.find_spec('psycopg') is None
assert len(schemas)==30
clock=FrozenClock(datetime(2026,12,31,16,tzinfo=timezone.utc))
assert UtcInstant(clock.now()).beijing_date==date(2027,1,1)
assert DateOnly.parse('2027-01-01').as_due(source_ref='synthetic-source').instant.hour==23
config=load_runtime_config(pathlib.Path(sysconfig.get_path('data'))/'share/whattodo/config/runtime.example.json',env={})
assert config.definitions==()
plan=load_migration_plan()
assert len(plan.steps)==17
assert plan.schema_version=='0.12.0-generation-processing'
outbox_now=datetime(2026,1,1,tzinfo=timezone.utc)
outbox_event=CreationEvent(event_id_for('installed-source-task'),'installed-source-task',1,'a'*64,'creation-tx','principal','authority',outbox_now)
outbox_lease=DeliveryLease(outbox_event,2,1,'installed-worker','b'*32,outbox_now,outbox_now+timedelta(seconds=60))
assert outbox_lease.event==outbox_event and 'b'*32 not in repr(outbox_lease)
outbox_outcome=DeliveryOutcome('RETRY',code='TEMPORARY_UNAVAILABLE',retry_at=outbox_now+timedelta(seconds=30))
assert DeliveryOutcome.from_payload(outbox_outcome.payload)==outbox_outcome
from src.domain.relationships import Endpoint as GraphEndpoint,RelationshipRule as GraphRule,TaskRelation as GraphRelation,literal as graph_literal
from src.application.definitions import DefinitionKey as GraphDefinitionKey
from src.application.relationship_storage import RuleStorageRecord as GraphRuleRecord,RelationStorageRecord as GraphRelationRecord,EndpointBinding as GraphBinding
from src.application.relationship_validation import GraphSnapshot,EndpointFact,GraphLimits,validate_relationship_graph
graph_rule=GraphRuleRecord(GraphRule('installed-rule','1',True,'installed-rule-acceptance','CANONICAL_CREATION','installed-source','installed-target','installed-template','1','counterpart','SEPARATE_TASK',('title','completion','disposition'),(graph_literal('title','Synthetic counterpart'),graph_literal('completion','INCOMPLETE'),graph_literal('disposition','ACTIVE'))),GraphDefinitionKey('TASKTYPE','installed-source','1'),GraphDefinitionKey('TASKTYPE','installed-target','1'),GraphDefinitionKey('TASK_TEMPLATE','installed-template','1'))
graph_a,graph_b=GraphEndpoint('TASK','installed-a'),GraphEndpoint('TASK','installed-b')
graph_facts=(EndpointFact(graph_a),EndpointFact(graph_b))
graph_finish=GraphRelationRecord(GraphRelation('installed-finish',1,'COMPLETION_ORDER',graph_b,graph_a,'installed-link-authority'),GraphBinding(graph_b,graph_b.id,1),GraphBinding(graph_a,graph_a.id,1))
graph_valid=validate_relationship_graph(GraphSnapshot((graph_rule,),(graph_finish,),graph_facts))
assert graph_valid.valid and graph_valid.generation_depth==1 and graph_valid.generated_instances==1
graph_start=GraphRelationRecord(GraphRelation('installed-start',1,'START_PREREQUISITE',graph_a,graph_b,'installed-link-authority'),GraphBinding(graph_a,graph_a.id,1),GraphBinding(graph_b,graph_b.id,1))
graph_invalid=validate_relationship_graph(GraphSnapshot((graph_rule,),(graph_finish,graph_start),graph_facts))
assert graph_invalid.status=='INVALID' and graph_invalid.issues[0].identities==('installed-finish','installed-start')
graph_limited=validate_relationship_graph(GraphSnapshot((graph_rule,),(graph_finish,),graph_facts),limits=GraphLimits(max_traversal_work=1))
assert graph_limited.status=='LIMIT_EXCEEDED' and not graph_limited.complete and not graph_limited.valid
DatabaseRoles('synthetic_migration','synthetic_application')
core=dict(schema_version='0.1.0-draft',task_id='synthetic-installed-task',revision=1,title='Synthetic installed task',domain='other',context=None,task_type_ref=None,acceptance=dict(state='ACCEPTED',authority_ref='synthetic-authority'),completion='INCOMPLETE',disposition='ACTIVE',requiredness='OPTIONAL',importance=3,difficulty=dict(thinking_depth=2,repetitive_volume=2,new_learning_load=2),expiration=None,metadata=dict(trust='UNKNOWN',overdue='UNKNOWN'))
effort=dict(schema_version='0.1.0-draft',task_id=core['task_id'],task_revision=1,completion='INCOMPLETE',disposition='ACTIVE',user_remaining=None,prediction=None,stages=[])
value=dict(schema_version='0.1.0-draft',core=core,effort=effort,timing=dict(created_at=None,release=None,deadline=None,completed_at=None),work=dict(total_estimate=None,minimum_session_seconds=None,fragmentable=None),stage_details=[],provenance=[])
record=admit_storage(codec,json.dumps(value).encode())
assert record.aggregate.as_record()==value
assert project_task(record,TaskStorageBindings()).rows['task_revision']['user_remaining_seconds'] is None
from hashlib import sha1,sha256
from src.adapters.memory_definitions import MemoryDefinitionRepository
from src.application.definitions import DefinitionArtifact,GitDefinitionRequest,canonical as generation_canonical
from src.application.generation_evaluator import GenerationSource,AcceptedGenerationRule,evaluate_generation
def installed_generation_artifact(key,body):
    raw=generation_canonical(dict(kind=key.kind,id=key.id,version=key.version,body=body)).encode()
    return DefinitionArtifact(GitDefinitionRequest('a'*40,key.id+'.json',sha256(raw).hexdigest()),sha1(b'blob '+str(len(raw)).encode()+b'\\0'+raw).hexdigest(),raw)
generation_repo=MemoryDefinitionRepository(clock)
generation_defaults=dict(importance=3,requiredness='OPTIONAL',difficulty=core['difficulty'],total_estimate_seconds=1800)
generation_repo.register_artifacts([installed_generation_artifact(graph_rule.source_type,{}),installed_generation_artifact(graph_rule.target_type,dict(defaults=generation_defaults)),
    installed_generation_artifact(graph_rule.template,dict(creation_facts=dict(domain='other'))),installed_generation_artifact(graph_rule.key,graph_rule.payload)])
generation_value=json.loads(json.dumps(value));generation_value['core']['task_type_ref']=dict(id=graph_rule.source_type.id,version=graph_rule.source_type.version)
generation_task=admit_storage(codec,generation_canonical(generation_value).encode())
generation_source=GenerationSource(CreationEvent(event_id_for(generation_task.task_id),generation_task.task_id,1,generation_task.content_hash,'installed-creation','installed-principal','synthetic-authority',clock.now()),generation_task,'installed-source')
generation_use=AcceptedGenerationRule(graph_rule,'installed-principal','installed-rule-source',clock.now())
generation_draft=evaluate_generation(codec,generation_source,generation_use,generation_repo,target_id='installed-generation-target')
assert generation_draft.ready and generation_draft.target.aggregate.as_record()['work']['total_estimate']['seconds']==1800
assert any(p['key']==vars(graph_rule.template) for p in generation_draft.manifest['definition_snapshots'])
assert generation_draft.target.aggregate.as_record()['effort']['user_remaining'] is None
from src.application.generation_runtime import GenerationPolicy,GenerationOutcome
from src.application.evidence_storage import SourceScope as GenerationSourceScope
from src.adapters.postgres_generation import PostgresGenerationHandler
generation_policy=GenerationPolicy('installed-principal',(graph_rule.key,),(GenerationSourceScope('installed','scope','account'),))
generation_handler=PostgresGenerationHandler(None,codec,plan,application_version='0.1.0.dev0',clock=clock,policy=generation_policy)
generation_worker=CallerIdentity('installed-principal','RELATIONSHIP_RULE',True)
generation_unavailable=generation_handler.generate('installed-event',graph_rule.key.id,correlation_ref='installed-generation-runtime',caller=generation_worker)
assert generation_unavailable.status=='PERMANENT' and generation_unavailable.code=='TRANSACTION_DRIVER_UNAVAILABLE'
assert GenerationOutcome('NOT_ELIGIBLE').receipt is None
from src.application.generation_processing import ProcessingLimits,ProcessingCheckpoint
from src.adapters.postgres_generation_worker import PostgresGenerationWorker
from src.application.creation_outbox import OutboxError
installed_worker=PostgresGenerationWorker(None,codec,plan,application_version='0.1.0.dev0',clock=clock,policy=generation_policy,worker_id='installed-worker',definitions=None)
assert ProcessingCheckpoint.from_payload(ProcessingCheckpoint('a'*64,(graph_rule.key,)).payload).cursor==0
try:installed_worker.run_batch()
except OutboxError as error:assert str(error)=='TRANSACTION_DRIVER_UNAVAILABLE'
else:raise AssertionError('WORKER_OPTIONAL_DRIVER_BOUNDARY')

generation_pending=evaluate_generation(codec,generation_source,generation_use,MemoryDefinitionRepository(clock),target_id='installed-generation-target')
assert not generation_pending.ready and generation_pending.state=='PENDING' and generation_pending.target is None
from src.application.generation_commit import prepare_generation_commit,GenerationOccurrenceRecord
generation_composite=prepare_generation_commit(codec,generation_source,generation_use,generation_repo,expected_store_revision=1,correlation_ref='installed-generation')
assert generation_composite.state=='PREPARED' and generation_composite.plan.occurrence.state=='CREATED'
assert {w.key.kind for w in generation_composite.plan.request.writes}=={'TASK','GENERATION_OCCURRENCE'}
assert GenerationOccurrenceRecord.from_payload(generation_composite.plan.occurrence.payload)==generation_composite.plan.occurrence
validate_audit_fingerprint(generation_composite.plan.receipt,principal_id='installed-principal',expected_store_revision=1,
    source_ref='installed-rule-source',correlation_ref='another-attempt',changes=tuple(a.tuple for a in generation_composite.plan.audits))
assert not hasattr(generation_composite.plan,'permit')
caller=CallerIdentity('synthetic-principal','USER_COMMAND',True)
request=CommitRequest(RequestContext('synthetic-request','synthetic-correlation'),caller.principal_id,1,(RecordWrite(AggregateKey('TASK',record.task_id),None,json.dumps(value)),),'synthetic-audit','synthetic-source')
permit=TransactionPermit('synthetic-permit',caller.principal_id,caller.origin,request.fingerprint,clock.now()-timedelta(minutes=1),clock.now()+timedelta(hours=1))
prepared=prepare_transaction(codec,request,caller=caller,permit=permit,at=clock.now())
assert prepared.receipt.store_revision==2 and prepared.writes[0].record.aggregate.as_record()==value
receipt=receipt_from_row(json.loads(json.dumps(prepared.receipt_body)),request_id=request.context.request_id,request_hash=request.fingerprint,store_revision=2,audit_id=request.audit_id)
assert receipt==prepared.receipt
validate_audit_fingerprint(receipt,principal_id=caller.principal_id,expected_store_revision=1,source_ref=request.source_ref,correlation_ref='another-attempt',changes=(('TASK',record.task_id,None,1,None,value),))
coordinator=PostgresTransactionCoordinator(None,codec,plan,application_version='0.1.0.dev0',clock=clock,permits=(permit,))
driver_absent=coordinator.commit(request,caller=caller,permit_ref=permit.permit_ref)
assert driver_absent.status=='PERMANENT' and driver_absent.code=='TRANSACTION_DRIVER_UNAVAILABLE'
lookup_absent=coordinator.lookup_commit(request.context,caller=caller)
assert lookup_absent.status=='PERMANENT' and lookup_absent.code=='TRANSACTION_DRIVER_UNAVAILABLE'
command=Command('synthetic-edit',caller.principal_id,caller.origin,'synthetic-grant',(change(record.task_id,1,'UPDATE_TASK',dict(title='Authorized installed correction')),))
grant=AuthorityGrant(command.authority_ref,caller.principal_id,caller.origin,command.command_id,command.changes,'synthetic-source',clock.now()-timedelta(minutes=1),expires_at=clock.now()+timedelta(hours=1))
after=json.loads(json.dumps(value));after['core']['revision']=after['effort']['task_revision']=2;after['core']['title']='Authorized installed correction'
edit=CommitRequest(RequestContext(command.command_id,'synthetic-edit-correlation'),caller.principal_id,2,(RecordWrite(AggregateKey('TASK',record.task_id),1,json.dumps(after)),),'synthetic-edit-audit','synthetic-source')
raw_command=json.dumps(command.as_record()).encode()
effects=validate_effects(codec,admit_command(codec,raw_command),edit,caller=caller,grant=grant,records=(record,),now=clock.now())
assert effects.permit.request_fingerprint==edit.fingerprint and effects.context['command_fingerprint']==command.fingerprint
detached=effects.context;detached['grant_ref']='forged';assert effects.context['grant_ref']==grant.grant_id
service=PostgresCommandService(None,codec,plan,application_version='0.1.0.dev0',clock=clock,grants=(grant,))
unavailable=service.commit(raw_command,edit,caller=caller)
assert unavailable.status=='PERMANENT' and unavailable.code=='TRANSACTION_DRIVER_UNAVAILABLE'
manual=Command('synthetic-manual',caller.principal_id,caller.origin,'synthetic-manual-grant',(change('synthetic-new-task',None,'CREATE_TASK',dict(title='Explicit installed task',importance=3,requiredness='OPTIONAL',difficulty=dict(thinking_depth=2,repetitive_volume=2,new_learning_load=3),user_remaining_seconds=7200)),))
intent=ResolvedManualIntent(manual.fingerprint,'synthetic-source',clock.now(),json.dumps(dict(domain='other',total_estimate_seconds=1800)))
class EmptyDefinitions:
    def get(self,key):return None
draft=prepare_manual_task(codec,manual,intent,EmptyDefinitions())
assert draft.ready and draft.seed.aggregate.as_record()['effort']['user_remaining'] is None
assert draft.after.aggregate.as_record()['effort']['user_remaining']['seconds']==7200 and draft.after.aggregate.as_record()['work']['total_estimate']['seconds']==1800
assert draft.prepared_estimates[0].source_ref=='synthetic-source' and draft.provenance.details['kind']=='MANUAL_CREATION'
incomplete=Command('synthetic-pending',caller.principal_id,caller.origin,'synthetic-manual-grant',(change('synthetic-pending-task',None,'CREATE_TASK',dict(importance=3)),))
pending_intent=ResolvedManualIntent(incomplete.fingerprint,'synthetic-source',clock.now(),json.dumps({}))
pending_draft=prepare_manual_task(codec,incomplete,pending_intent,EmptyDefinitions())
assert not pending_draft.ready and pending_draft.after is None and '/core/title' in pending_draft.missing_fields
manual_handler=PostgresManualTaskHandler(None,codec,plan,application_version='0.1.0.dev0',clock=clock,definitions=EmptyDefinitions(),intents=(intent,))
manual_unavailable=manual_handler.create(json.dumps(manual.as_record()).encode(),RequestContext(manual.command_id,'synthetic-manual-correlation'),expected_store_revision=1,audit_id='synthetic-manual-audit',caller=caller)
assert manual_unavailable.status=='PERMANENT' and manual_unavailable.code=='TRANSACTION_DRIVER_UNAVAILABLE'
extended=load_supported_schemas()
assert len(extended)==41 and all(extended[k]==s for k,s in schemas.items())
extended_codec=ContractJSONCodec(extended)
from copy import deepcopy
from src.application.stage_commands import StageCommand,StageCommandGrant,admit_stage_command,prepare_stage_command
installed_stage_value=deepcopy(value)
installed_stage_value['effort']['stages']=[dict(stage_id='installed-rework-stage',completion='COMPLETE',weight=1,user_remaining=None)]
installed_stage_value['stage_details']=[dict(stage_id='installed-rework-stage',revision=1,title='Installed stage')]
installed_stage_before=admit_storage(extended_codec,json.dumps(installed_stage_value).encode())
installed_stage_command=StageCommand('installed-stage-command',caller.principal_id,'installed-stage-grant',record.task_id,1,'installed-rework-stage',1,'REWORK',json.dumps(dict(intent='SAME_OBLIGATION',parent_remaining_seconds=600)))
assert admit_stage_command(extended_codec,json.dumps(installed_stage_command.as_record()).encode())==installed_stage_command
installed_stage_grant=StageCommandGrant(installed_stage_command,'synthetic-source',clock.now(),clock.now())
installed_stage_prepared=prepare_stage_command(extended_codec,installed_stage_command,installed_stage_grant,installed_stage_before,caller=caller,now=clock.now())
assert installed_stage_prepared.state=='PREPARED' and installed_stage_prepared.record.aggregate.as_record()['effort']['stages'][0]['completion']=='INCOMPLETE'
assert installed_stage_prepared.record.aggregate.as_record()['effort']['user_remaining']['seconds']==600 and not hasattr(installed_stage_prepared,'permit')
installed_stage_unknown=StageCommand('installed-pending-stage',caller.principal_id,'installed-pending-stage-grant',record.task_id,1,'installed-rework-stage',1,'REWORK',json.dumps(dict(intent='UNRESOLVED')))
assert prepare_stage_command(extended_codec,installed_stage_unknown,StageCommandGrant(installed_stage_unknown,'synthetic-source',clock.now(),clock.now()),installed_stage_before,caller=caller,now=clock.now()).record is None
patch=FactPatch('installed-fact-patch',caller.principal_id,'installed-fact-grant',core['task_id'],1,json.dumps(dict(deadline='2026-10-13T13:30:00.123456+08:00',importance=4,user_remaining_seconds=1200)))
patch_raw=json.dumps(patch.as_record()).encode()
assert admit_fact_patch(extended_codec,patch_raw)==patch
fact_grant=FactPatchGrant(patch,'synthetic-source',clock.now(),clock.now()+timedelta(minutes=5),clock.now())
fact=prepare_fact_patch(extended_codec,patch,fact_grant,admit_storage(extended_codec,json.dumps(value).encode()),now=clock.now())
assert fact.record.revision==2 and fact.dues[0].value.original_value==patch.fields['deadline'] and fact.estimates[0].seconds==1200
assert codec.admit('task-fact-patch',patch_raw).status!='SUPPORTED_SHAPE'
patch_handler=PostgresFactPatchHandler(None,extended_codec,plan,application_version='0.1.0.dev0',clock=clock,grants=(fact_grant,))
patch_unavailable=patch_handler.patch(patch_raw,RequestContext(patch.command_id,'installed-patch-correlation'),expected_store_revision=1,audit_id='installed-patch-audit',caller=caller)
assert patch_unavailable.status=='PERMANENT' and patch_unavailable.code=='TRANSACTION_DRIVER_UNAVAILABLE'
complete=Command('installed-complete',caller.principal_id,caller.origin,'installed-complete-grant',
    (change(core['task_id'],1,'UPDATE_TASK',dict(completion='COMPLETE')),))
complete_grant=AuthorityGrant(complete.authority_ref,caller.principal_id,caller.origin,complete.command_id,complete.changes,
    'synthetic-source',clock.now(),expires_at=clock.now()+timedelta(minutes=5))
complete_raw=json.dumps(complete.as_record()).encode()
completed=prepare_lifecycle_task(codec,admit_lifecycle_command(codec,complete_raw,'COMPLETE'),complete_grant,
    record,operation='COMPLETE',caller=caller,source_observed_at=clock.now(),now=clock.now())
assert completed.record.aggregate.as_record()['core']['completion']=='COMPLETE'
assert completed.record.aggregate.as_record()['effort']['user_remaining']['seconds']==0 and len(completed.estimates)==1
assert completed.record.aggregate.as_record()['timing']['completed_at'] is None
cancel=Command('installed-cancel',caller.principal_id,caller.origin,'installed-cancel-grant',
    (change(core['task_id'],2,'UPDATE_TASK',dict(disposition='CANCELLED')),))
cancel_grant=AuthorityGrant(cancel.authority_ref,caller.principal_id,caller.origin,cancel.command_id,cancel.changes,
    'synthetic-source',clock.now(),expires_at=clock.now()+timedelta(minutes=5))
cancel_raw=json.dumps(cancel.as_record()).encode()
cancelled=prepare_lifecycle_task(codec,admit_lifecycle_command(codec,cancel_raw,'CANCEL'),cancel_grant,
    completed.record,operation='CANCEL',caller=caller,source_observed_at=clock.now(),now=clock.now())
assert cancelled.record.aggregate.as_record()['core']['completion']=='COMPLETE' and cancelled.record.aggregate.as_record()['core']['disposition']=='CANCELLED'
assert not cancelled.estimates and cancelled.record.aggregate.as_record()['effort']['user_remaining']==completed.record.aggregate.as_record()['effort']['user_remaining']
lifecycle=PostgresLifecycleHandler(None,codec,plan,application_version='0.1.0.dev0',clock=clock,grants=(complete_grant,cancel_grant))
for operation,raw,command in ((lifecycle.complete,complete_raw,complete),(lifecycle.cancel,cancel_raw,cancel)):
    unavailable=operation(raw,RequestContext(command.command_id,'installed-lifecycle-correlation'),expected_store_revision=1,audit_id='installed-lifecycle-audit',caller=caller)
    assert unavailable.status=='PERMANENT' and unavailable.code=='TRANSACTION_DRIVER_UNAVAILABLE'
scope=SourceScope('synthetic-installed-provider','synthetic-scope','synthetic-account')
work_value=dict(schema_version='0.1.0-work-report',command_id='installed-work',principal_id=caller.principal_id,origin='USER_COMMAND',
    authority_ref='installed-work-grant',observation_id='installed-observation',target_ref=dict(task_id=record.task_id,revision=1),
    mode='CUMULATIVE',seconds=900,stage_id=None,session_started_at=None,session_ended_at=None,user_remaining_seconds=1200)
work_raw=json.dumps(work_value).encode();work_report=admit_work_report(extended_codec,work_raw)
work_grant=WorkReportGrant(work_report,'synthetic-source',clock.now(),clock.now()+timedelta(minutes=5))
work_prepared=prepare_work_report(extended_codec,work_report,work_grant,record,caller=caller,previous_total_seconds=300,source_observed_at=clock.now(),now=clock.now())
assert work_prepared.work.as_record()['increment_seconds']==600 and work_prepared.work.as_record()['resulting_total_seconds']==900
assert work_prepared.task.aggregate.as_record()['core']['completion']=='INCOMPLETE' and work_prepared.estimates[0].seconds==1200
assert work_prepared.work.report.as_record()['session_started_at'] is None and work_prepared.work.report.as_record()['session_ended_at'] is None
work_request=CommitRequest(RequestContext(work_report.command_id,'installed-work-correlation'),caller.principal_id,1,
    (RecordWrite(AggregateKey('TASK',record.task_id),1,work_prepared.task.raw_bytes.decode()),RecordWrite(AggregateKey('WORK_REPORT',work_report.observation_id),None,work_prepared.work.raw_bytes.decode())),
    'installed-work-audit','synthetic-source')
work_permit=TransactionPermit('installed-work-permit',caller.principal_id,caller.origin,work_request.fingerprint,clock.now(),clock.now()+timedelta(minutes=5))
work_transaction=prepare_transaction(extended_codec,work_request,caller=caller,permit=work_permit,at=clock.now())
assert len(work_transaction.receipt.changed_keys)==2 and len(work_transaction.writes)==2
assert codec.admit('work-report',work_raw).status!='SUPPORTED_SHAPE'
work_handler=PostgresWorkReportHandler(None,extended_codec,plan,application_version='0.1.0.dev0',clock=clock,grants=(work_grant,))
unavailable=work_handler.report(work_raw,work_request.context,expected_store_revision=1,audit_id=work_request.audit_id,caller=caller)
assert unavailable.status=='PERMANENT' and unavailable.code=='TRANSACTION_DRIVER_UNAVAILABLE'
source=capture_source(provider=scope.provider,scope_ref=scope.scope_ref,external_id='synthetic-item',raw_bytes=b'synthetic installed raw content',captured_at=clock.now())
source_value=admit_source(codec,json.dumps(source.as_record()).encode())
assert source_value.source==source
proposal=make_candidate(source,parser_version='synthetic-parser',action='CREATE_TASK',proposed_fields=dict(title='Synthetic installed proposal'),confidence=1)
candidate=admit_candidate(codec,json.dumps(proposal.as_record()).encode(),pending_only=True)
assert candidate.candidate.review_state=='PENDING' and candidate.candidate.authority_ref is None
normalizer=DirectCreationNormalizer(codec,clock=clock,bindings=(UserInputBinding(caller.principal_id,scope),))
creation_raw=guided_message(dict(title='Installed direct task',importance='4',requiredness='可选',difficulty='3/2/3',remaining='约40分钟',domain='学习'))
creation_source=capture_source(provider=scope.provider,scope_ref=scope.scope_ref,external_id='installed-direct',raw_bytes=creation_raw,captured_at=clock.now(),source_type='USER')
direct=normalizer.guided(creation_raw,creation_source,caller=caller)
assert direct.ready_for_creation and direct.candidate['review']['state']=='PENDING'
handoff=normalizer.manual_handoff(direct,command_id='installed-direct-command',task_id='installed-direct-task',authority_ref='installed-independent-root',caller=caller)
assert handoff.command.changes[0].fields['user_remaining_seconds']==2400 and handoff.statement_bytes==creation_raw
assert prepare_manual_task(codec,handoff.command,handoff.intent,EmptyDefinitions()).ready
incomplete_raw=guided_message(dict(title='Installed partial task'))
incomplete_source=capture_source(provider=scope.provider,scope_ref=scope.scope_ref,external_id='installed-partial',raw_bytes=incomplete_raw,captured_at=clock.now(),source_type='USER')
incomplete=normalizer.guided(incomplete_raw,incomplete_source,caller=caller)
assert incomplete.normalized and not incomplete.ready_for_creation and incomplete.facts=={}
from src.application.task_resolution import ResolutionSnapshot,admit_intent,begin_resolution,resume_resolution,admit_reply,resolution_handoff
from src.adapters.postgres_resolution import PostgresResolutionService
resolution_input=dict(schema_version='0.1.0-resolution-intent',session_id='installed-resolution-session',command_id='installed-resolution-command',principal_id=caller.principal_id,
    action='CREATE_TASK',target=None,creation_task_id='installed-resolved-task',fields=dict(title='Installed resolved task'),creation_facts={})
resolution_raw=json.dumps(resolution_input).encode()
resolution_intent=admit_intent(extended_codec,resolution_raw)
snapshot=ResolutionSnapshot(caller.principal_id,1,(record,))
frame=begin_resolution(extended_codec,resolution_intent,snapshot,source_ref='synthetic-source',source_observed_at=clock.now(),at=clock.now(),caller=caller)
assert frame.as_record()['state']=='NEEDS_DETAILS' and '/core/title' not in frame.as_record()['missing_fields']
reply=dict(schema_version='0.1.0-clarification-reply',reply_id='installed-reply',session_id=frame.session_id,expected_revision=frame.revision,scope_hash=frame.fingerprint,
    selection=None,answers=dict(importance='4',requiredness=json.loads(creation_raw)['answers']['requiredness'],difficulty='3/2/3',domain=json.loads(creation_raw)['answers']['domain']))
resolved=resume_resolution(extended_codec,frame,admit_reply(extended_codec,json.dumps(reply).encode()),snapshot,source_ref='synthetic-reply-source',source_observed_at=clock.now(),at=clock.now(),caller=caller)
assert resolved.as_record()['state']=='RESOLVED' and resolved.revision==2
resolution_out=resolution_handoff(resolved,authority_ref='installed-separate-resolution-root',caller=caller)
assert resolution_out.command.command_id=='installed-resolution-command' and resolution_out.manual_intent.facts==dict(domain='study')
assert resolution_out.source_refs==('synthetic-source','synthetic-reply-source') and 'user_remaining_seconds' not in resolution_out.command.changes[0].fields
resolution_service=PostgresResolutionService(None,extended_codec,plan,application_version='0.1.0.dev0',clock=clock)
resolution_unavailable=resolution_service.begin(resolution_raw,'synthetic-source',RequestContext('installed-resolution-command','installed-correlation'),caller=caller)
assert resolution_unavailable.status=='PERMANENT' and resolution_unavailable.code=='TRANSACTION_DRIVER_UNAVAILABLE'
from contextlib import contextmanager
from src.application.command_transport import TransportCredential,OPERATIONS,token_digest
from src.adapters.prototype_codec import PrototypeJSONCodec
from src.adapters.prototype_http import AuthenticatedCommandTransport
from src.adapters.postgres_transport import PostgresPrototypeBackend
transport_codec=PrototypeJSONCodec(extended)
transport_token='synthetic-installed-prototype-token-0001'
transport_credential=TransportCredential(caller.principal_id,token_digest(transport_token),OPERATIONS,None,clock.now()-timedelta(minutes=1),clock.now()+timedelta(minutes=5))
@contextmanager
def backend_factory():
    yield PostgresPrototypeBackend(None,transport_codec,plan,application_version='0.1.0.dev0',clock=clock)
transport=AuthenticatedCommandTransport(transport_codec,clock=clock,credentials=(transport_credential,),backend_factory=backend_factory)
transport_wire=json.dumps(dict(schema_version='0.1.0-prototype-request',operation='COMPLETE_TASK',request_id=complete.command_id,correlation_ref='installed-transport-correlation',
    payload=complete_raw.decode(),parameters=dict(expected_store_revision=1,audit_id='installed-transport-audit'))).encode()
authenticated=transport.handle(transport_wire,authorization='Bearer '+transport_token)
assert authenticated.http_status==400 and authenticated.as_record()['code']=='TRANSACTION_DRIVER_UNAVAILABLE'
unauthenticated=transport.handle(transport_wire,authorization=None)
assert unauthenticated.http_status==401 and unauthenticated.as_record()['data'] is None
assert transport_token not in authenticated.body_bytes.decode() and transport_token not in unauthenticated.body_bytes.decode()
from src.application.read_models import admit_query,CursorSigner,task_view
from src.adapters.postgres_read_models import PostgresReadService
read_value=dict(schema_version='0.1.0-read-query',view='TASKS',task_id=None,filters=dict(completion=None,disposition=None,trust=None,domain=None,context=None),pending_kind=None,include_closed=False,page_size=10,cursor=None)
read_raw=json.dumps(read_value).encode();read_query=admit_query(transport_codec,read_raw)
read_key=b'synthetic-installed-read-key-0001';signer=CursorSigner(read_key)
read_cursor=signer.encode('installed-snapshot',1,caller.principal_id,read_query.fingerprint)
assert CursorSigner(read_key).decode(read_cursor,principal_id=caller.principal_id,query_hash=read_query.fingerprint)==('installed-snapshot',1)
assert task_view(record,0)['user_remaining'] is None
read_service=PostgresReadService(None,transport_codec,plan,application_version='0.1.0.dev0',clock=clock,cursor_key=read_key)
read_unavailable=read_service.query(read_raw,RequestContext('installed-read','installed-read-correlation'),caller=caller)
assert read_unavailable.code=='TRANSACTION_DRIVER_UNAVAILABLE' and read_unavailable.status=='PERMANENT'
@contextmanager
def read_backend_factory():
    yield PostgresPrototypeBackend(None,transport_codec,plan,application_version='0.1.0.dev0',clock=clock,read_cursor_key=read_key)
read_transport=AuthenticatedCommandTransport(transport_codec,clock=clock,credentials=(transport_credential,),backend_factory=read_backend_factory)
read_wire=json.dumps(dict(schema_version='0.1.0-prototype-request',operation='QUERY_STATE',request_id='installed-read',correlation_ref='installed-read-correlation',payload=read_raw.decode(),parameters={})).encode()
assert read_transport.handle(read_wire,authorization='Bearer '+transport_token).as_record()['code']=='TRANSACTION_DRIVER_UNAVAILABLE'
print(json.dumps(dict(stage_commands='INSTALLED_EXACT_STAGE_REWORK_AND_EFFECT_FREE_PENDING_WITHOUT_PERMIT',generation_processing='INSTALLED_TYPED_CHECKPOINT_AND_EXPLICIT_OPTIONAL_DRIVER_RESULT',generation_runtime='INSTALLED_POLICY_SCOPED_HANDLER_EXPLICIT_OPTIONAL_DRIVER_RESULT',generation_commit='INSTALLED_COMPOSITE_RECEIPT_AUDIT_AND_OCCURRENCE_NOT_AUTHORIZED',generation_evaluator='INSTALLED_EXACT_CANONICAL_MAPPING_AND_PENDING_WITHOUT_OPTIONAL_DRIVER',read_models='INSTALLED_QUERY_CURSOR_PROJECTION_AND_AUTHENTICATED_ROUTE_WITH_EXPLICIT_OPTIONAL_DRIVER_RESULT',command_transport='INSTALLED_AUTHENTICATED_HANDLER_ROUTE_UNAUTHENTICATED_REJECTION_AND_OPTIONAL_DRIVER_RESULT',task_resolution='INSTALLED_VERSIONED_FOLLOWUP_SAME_COMMAND_HANDOFF_AND_OPTIONAL_DRIVER_RESULT',direct_creation='INSTALLED_GUIDED_FROZEN_PROPOSAL_EXACT_RAW_MANUAL_HANDOFF_AND_PARTIAL_UNKNOWN_FACTS',work_reports='INSTALLED_CUMULATIVE_SETTLEMENT_U_TWO_RECORD_AUDIT_AND_OPTIONAL_DRIVER_RESULT',task_lifecycle='INSTALLED_COMPLETE_ZERO_OBSERVATION_CANCEL_TRUTHFUL_TIME_AND_OPTIONAL_DRIVER_RESULT',extension_contracts=len(extended)-len(schemas),task_fact_patches='INSTALLED_OPT_IN_EXACT_PATCH_SOURCE_TIME_U_AND_OPTIONAL_DRIVER_RESULT',version=importlib.metadata.version('whattodo-core'),installed_source=src.__file__,contracts=len(schemas),postgres_driver='ABSENT_OPTIONAL',domain=domain_smoke(),clock_check='BEIJING_YEAR_ROLLOVER',configuration=config.safe_summary(),migration_steps=len(plan.steps),schema_version=plan.schema_version,migration_module='IMPORTS_WITHOUT_OPTIONAL_DRIVER',task_storage='INSTALLED_ADMISSION_AND_PROJECTION_WITHOUT_OPTIONAL_DRIVER',evidence_storage='INSTALLED_SOURCE_AND_PENDING_CANDIDATE_WITHOUT_OPTIONAL_DRIVER',transactions='INSTALLED_EXACT_PERMIT_PREPARATION_AND_EXPLICIT_OPTIONAL_DRIVER_RESULT',command_ledger='INSTALLED_RECEIPT_AUDIT_CHECK_AND_EXPLICIT_OPTIONAL_LOOKUP_DRIVER_RESULT',command_validation='INSTALLED_STRICT_COMMAND_EFFECT_SCOPE_AND_EXPLICIT_OPTIONAL_DRIVER_RESULT',manual_creation='INSTALLED_READY_PENDING_OBSERVATION_AND_EXPLICIT_OPTIONAL_DRIVER_RESULT')))
"""
        smoke_script=run_root/'installed-smoke.py'
        smoke_script.write_text(code,encoding='utf-8')
        observed=json.loads(run([installed,'-I',smoke_script],cwd=run_root,env=env))
        script=clean_env/'Scripts/whattodo-smoke.exe'
        entry=json.loads(run([script],cwd=run_root,env=env))
        if entry!=observed['domain']:raise RuntimeError('INSTALLED_ENTRYPOINT_MISMATCH')
        report.update(status='PASS',wheel=wheel.relative_to(ROOT).as_posix(),wheel_sha256=digest,packaged_schema_count=len(schemas),installed_checks=observed,entrypoint=entry,clean_install=True,source_checkout_import='EXCLUDED_BY_ISOLATED_INTERPRETER',build_lock='requirements-build.lock',runtime_lock='requirements-runtime.lock',limitations=['Private Windows/Python development package only','Not a deployed command transport, persistence adapter or authenticated user channel','Real provider/profile activation remains deferred'])
    except (RuntimeError,OSError,subprocess.SubprocessError,ValueError) as exc:
        report.update(status='FAIL',diagnostic=str(exc)[-2500:]);print(report['diagnostic'],file=sys.stderr)
    target=run_root/'report.json';target.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print('Package acceptance report: '+str(target))
    return 0 if report['status']=='PASS' else 1


if __name__=='__main__':raise SystemExit(main())
