"""Actual loopback HTTP -> authenticated caller -> existing PostgreSQL handlers."""
from contextlib import contextmanager
from datetime import datetime,timedelta,timezone
from http.client import HTTPConnection
from pathlib import Path
from threading import Thread
import json
import sys
ROOT=Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:sys.path.insert(0,str(ROOT))
from src import __version__
from src.adapters.clocks import FrozenClock
from src.adapters.extension_contracts import load_supported_schemas
from src.adapters.memory_definitions import MemoryDefinitionRepository
from src.adapters.migration_files import load_migration_plan
from src.adapters.postgres_authorization import register_grant
from src.adapters.postgres_evidence import PostgresEvidenceRepository,register_source_scope
from src.adapters.postgres_fact_patches import register_fact_patch_grant
from src.adapters.postgres_migrations import DatabaseRoles,apply_migrations
from src.adapters.postgres_tasks import PostgresTaskRepository
from src.adapters.postgres_transport import PostgresPrototypeBackend
from src.adapters.postgres_work_reports import register_work_report_grant
from src.adapters.prototype_codec import PrototypeJSONCodec
from src.adapters.prototype_http import AuthenticatedCommandTransport,make_http_server
from src.application.command_transport import TransportCredential,OPERATIONS,token_digest,MAX_REQUEST_BYTES
from src.application.definitions import canonical
from src.application.direct_creation import UserInputBinding,guided_message
from src.application.evidence_storage import SourceScope
from src.application.fact_patches import FactPatch,FactPatchGrant
from src.application.manual_tasks import ResolvedManualIntent
from src.application.work_reports import admit_work_report,WorkReportGrant
from src.domain.authorization import AuthorityGrant,Command,change
from src.domain.provenance import capture_source
from tools.postgres_harness import HarnessError,PostgresHarness,ROLES,require
from tools.verify_transactions import TABLES
NOW=datetime(2026,1,1,tzinfo=timezone.utc);CLOCK=FrozenClock(NOW)
TOKEN='synthetic-prototype-native-token-0001';OTHER_TOKEN='synthetic-prototype-native-other-0002';NARROW_TOKEN='synthetic-prototype-native-narrow-0003';READ_TOKEN='synthetic-prototype-native-read-0004'
SCOPE=SourceScope('synthetic-prototype-user','scope','account');OTHER_SCOPE=SourceScope('synthetic-prototype-other','scope-other','account-other')
DIMS=dict(thinking_depth=2,repetitive_volume=2,new_learning_load=3)


def verify(harness,report):
    import psycopg
    plan=load_migration_plan(root=ROOT);codec=PrototypeJSONCodec(load_supported_schemas(root=ROOT));checks=report['native_checks']
    database=harness.create_database(initialize_schema=False);roles=DatabaseRoles(ROLES['migration'],ROLES['application'],ROLES['test'])
    with harness.target(database,'migration').connect() as owner:
        apply_migrations(owner,plan,roles=roles,application_version=__version__)
        for scope in (SCOPE,OTHER_SCOPE):register_source_scope(owner,plan,roles,scope,application_version=__version__,clock=CLOCK)
    config=dict(grants=(),patch_grants=(),work_grants=(),intents=(),input_bindings=(UserInputBinding('principal',SCOPE),UserInputBinding('other',OTHER_SCOPE)))
    counts=dict(backend_opens=0,handler_calls=0);fault=dict(before_commit=False,after_commit=False)
    class ExecuteFault:
        def __init__(self,conn):self.conn=conn;self.fired=False
        def __getattr__(self,n):return getattr(self.conn,n)
        def execute(self,query,*a,**kw):
            out=self.conn.execute(query,*a,**kw)
            text=query if isinstance(query,str) else query.as_string(self.conn)
            if text.startswith('INSERT INTO whattodo.') and '"task_revision"' in text and not self.fired:
                self.fired=True;raise psycopg.OperationalError('synthetic precommit interruption')
            return out
    @contextmanager
    def factory():
        counts['backend_opens']+=1
        with harness.target(database).connect() as conn:
            actual=ExecuteFault(conn) if fault['before_commit'] else conn
            backend=PostgresPrototypeBackend(actual,codec,plan,application_version=__version__,clock=CLOCK,definitions=MemoryDefinitionRepository(CLOCK),**config)
            class Counted:
                def dispatch(self,request,*,caller):
                    counts['handler_calls']+=1;return backend.dispatch(request,caller=caller)
            yield Counted()
        if fault['after_commit']:raise psycopg.OperationalError('synthetic transport exit after commit')
    def credential(token,principal='principal',operations=OPERATIONS,tasks=None):
        return TransportCredential(principal,token_digest(token),operations,tasks,NOW-timedelta(minutes=1),NOW+timedelta(hours=1))
    credentials=(credential(TOKEN),credential(OTHER_TOKEN,'other'),credential(NARROW_TOKEN,tasks=frozenset({'api-task'})),credential(READ_TOKEN,operations=frozenset({'LOOKUP_COMMAND'})))
    transport=AuthenticatedCommandTransport(codec,clock=CLOCK,credentials=credentials,backend_factory=factory)
    server=make_http_server(transport);thread=Thread(target=server.serve_forever,kwargs=dict(poll_interval=.02));thread.start()
    try:
        with harness.target(database).connect() as conn:
            reader=PostgresTaskRepository(conn,codec,plan,application_version=__version__,clock=CLOCK)
            evidence=PostgresEvidenceRepository(conn,codec,plan,application_version=__version__,clock=CLOCK,scopes=(SCOPE,OTHER_SCOPE))
            def epoch():return conn.execute('SELECT revision FROM whattodo.store_epoch').fetchone()[0]
            def state():return tuple(conn.execute('SELECT * FROM whattodo.'+t+' ORDER BY 1,2').fetchall() for t in TABLES+('effort_observation','normalized_due','manual_creation_pending','command_resolution_revision','command_resolution_head','command_resolution_reply'))
            def source(name,raw,kind='USER',scope=SCOPE):
                s=capture_source(provider=scope.provider,scope_ref=scope.scope_ref,external_id=name,raw_bytes=raw,captured_at=NOW,source_type=kind)
                evidence.observe_source(canonical(s.as_record()).encode(),raw_content=raw,locator_ref='synthetic-'+name);return s.record_id
            def grant(command,ref):
                g=AuthorityGrant(command.authority_ref,command.principal_id,command.origin,command.command_id,command.changes,ref,NOW-timedelta(minutes=1),expires_at=NOW+timedelta(hours=1))
                with harness.target(database,'migration').connect() as owner:register_grant(owner,g,plan,application_version=__version__)
                config['grants']+=(g,);return g
            def create_command(name,title='Homework',fields=None,facts=None):
                c=Command('create-'+name,'principal','USER_COMMAND','root-create-'+name,(change(name,None,'CREATE_TASK',fields or dict(title=title,importance=3,requiredness='REQUIRED',difficulty=DIMS,user_remaining_seconds=600)),))
                ref=source(c.command_id,canonical(c.as_record()).encode());grant(c,ref)
                config['intents']+=(ResolvedManualIntent(c.fingerprint,ref,NOW,canonical(facts if facts is not None else dict(domain='study'))),);return c
            def wire(op,request_id,payload=None,parameters=None):return canonical(dict(schema_version='0.1.0-prototype-request',operation=op,request_id=request_id,correlation_ref='synthetic-correlation',payload=payload,parameters=parameters or {})).encode()
            def http(raw,token=TOKEN,headers=None,path='/v1/commands',method='POST'):
                client=HTTPConnection('127.0.0.1',server.server_port,timeout=10)
                h={'Content-Type':'application/json'}
                if token:h['Authorization']='Bearer '+token
                h.update(headers or {})
                try:
                    client.request(method,path,body=raw,headers=h);out=client.getresponse();body=out.read();require(out.getheader('Cache-Control')=='no-store','TRANSPORT_HTTP_CACHE')
                    v=json.loads(body);require(codec.admit('prototype-response',body).status=='SUPPORTED_SHAPE','TRANSPORT_HTTP_RESPONSE_SHAPE');return out.status,v
                finally:client.close()
            def mutation(op,c,e=None,token=TOKEN,payload=None):
                raw=wire(op,c.command_id,payload if payload is not None else canonical(c.as_record()),dict(expected_store_revision=epoch() if e is None else e,audit_id='audit-'+c.command_id))
                return http(raw,token),raw
            def deny(raw,token=TOKEN,status=None):
                before=state();opened=counts['backend_opens'];result=http(raw,token)
                require(result[0]==status if status else result[1]['status']!='SUCCESS','TRANSPORT_NEGATIVE_STATUS')
                require(state()==before and counts['backend_opens']==opened,'TRANSPORT_NEGATIVE_ENTERED_HANDLER');return result
            c=create_command('api-task');e=epoch();raw=wire('CREATE_TASK',c.command_id,canonical(c.as_record()),dict(expected_store_revision=e,audit_id='audit-'+c.command_id))
            deny(raw,token=None,status=401);deny(raw,token='synthetic-unknown-native-token-9999',status=401);deny(raw,token=READ_TOKEN,status=403)
            checks.append('missing_unknown_and_wrong_operation_credentials_reject_before_backend_connection_or_handler')
            foreign=c.as_record();foreign['principal_id']='other';deny(wire('CREATE_TASK',c.command_id,canonical(foreign),dict(expected_store_revision=e,audit_id='audit')),status=403)
            denied=c.as_record();denied['changes'][0]['task_id']='not-in-token-scope';deny(wire('CREATE_TASK',c.command_id,canonical(denied),dict(expected_store_revision=e,audit_id='audit')),token=NARROW_TOKEN,status=403)
            checks.append('payload_principal_and_task_scope_forgery_fail_before_existing_handler_invocation')
            for extra in ('caller','grant','sql','credentials'):
                forged=json.loads(raw);forged[extra]={'synthetic':True};deny(canonical(forged).encode(),status=400)
            deny(b'x'*(MAX_REQUEST_BYTES+1),status=413)
            checks.append('closed_envelope_rejects_arbitrary_sql_authority_credentials_and_oversized_requests_without_state_changes')
            (status,out),_=mutation('CREATE_TASK',c,e,token=NARROW_TOKEN)
            require(status==200 and out['code']=='COMMITTED' and out['data']['result']['state']=='CREATED' and reader.get('api-task').revision==1 and epoch()==e+1,'TRANSPORT_HTTP_CREATE_'+out['code'])
            checks.append('actual_http_create_uses_independent_principal_grant_intent_source_and_existing_atomic_task_audit_receipt_path')
            task=reader.get('api-task').aggregate.as_record();require(task['timing']['created_at'] is None and task['work']['total_estimate'] is None,'TRANSPORT_INFERRED_FACTS')
            require(TOKEN not in canonical(out) and 'proposal_json' not in canonical(out) and 'raw_bytes' not in canonical(out),'TRANSPORT_RESPONSE_MINIMIZATION')
            checks.append('allowlisted_creation_result_excludes_raw_evidence_secrets_and_fabricated_work_or_creation_times')
            before=state();replay=http(raw);require(replay[1]['code']=='REPLAY' and replay[1]['data']['result']['receipt']==out['data']['result']['receipt'] and state()==before,'TRANSPORT_HTTP_REPLAY')
            padded=wire('CREATE_TASK',c.command_id,' \n'*110000+canonical(c.as_record()),dict(expected_store_revision=e,audit_id='audit-'+c.command_id))
            require(len(padded)>262144 and http(padded)[1]['code']=='REPLAY' and state()==before,'TRANSPORT_ENVELOPE_LIMIT_COMPOSITION')
            checks.append('same_request_replays_original_receipt_and_larger_transport_envelope_preserves_frozen_inner_contract_limit')
            partial=create_command('partial',fields=dict(title='Partial task'),facts={});(status,pending),_=mutation('CREATE_TASK',partial)
            require(status==200 and pending['code']=='PENDING_DETAILS' and reader.get('partial') is None and pending['data']['result']['missing_fields'],'TRANSPORT_PENDING')
            require('proposal_json' not in canonical(pending),'TRANSPORT_PENDING_RAW_LEAK')
            checks.append('partial_creation_remains_durable_pending_with_readable_missing_fields_and_no_raw_proposal_exposure')
            p=FactPatch('patch-api','principal','root-patch-api','api-task',1,canonical(dict(title='Updated homework',user_remaining_seconds=1200)))
            ref=source(p.command_id,canonical(p.as_record()).encode());pg=FactPatchGrant(p,ref,NOW,NOW+timedelta(hours=1),NOW)
            with harness.target(database,'migration').connect() as owner:register_fact_patch_grant(owner,pg,plan,application_version=__version__)
            config['patch_grants']+=(pg,);(status,patched),_=mutation('PATCH_TASK',p,token=NARROW_TOKEN)
            require(status==200 and patched['code']=='COMMITTED' and reader.get('api-task').aggregate.as_record()['core']['title']=='Updated homework','TRANSPORT_PATCH_'+patched['code'])
            checks.append('fact_patch_route_preserves_opt_in_exact_grant_source_provenance_and_explicit_u')
            work_value=dict(schema_version='0.1.0-work-report',command_id='work-api',principal_id='principal',origin='USER_COMMAND',authority_ref='root-work-api',observation_id='actual-api',target_ref=dict(task_id='api-task',revision=2),mode='INCREMENT',seconds=900,stage_id=None,session_started_at=None,session_ended_at=None)
            wr=admit_work_report(codec,canonical(work_value).encode());ref=source(wr.command_id,canonical(work_value).encode());wg=WorkReportGrant(wr,ref,NOW,NOW+timedelta(hours=1))
            with harness.target(database,'migration').connect() as owner:register_work_report_grant(owner,wg,plan,application_version=__version__)
            config['work_grants']+=(wg,);(status,worked),work_wire=mutation('REPORT_WORK',wr)
            require(status==200 and worked['data']['result']['increment_seconds']==900 and reader.get('api-task').aggregate.as_record()['effort']['user_remaining']['seconds']==1200,'TRANSPORT_WORK')
            before=state();require(http(work_wire)[1]['code']=='REPLAY' and state()==before,'TRANSPORT_WORK_REPLAY')
            checks.append('reported_work_route_deduplicates_actual_observation_and_does_not_decrement_u_or_invent_session_bounds')
            cc=Command('complete-api','principal','USER_COMMAND','root-complete-api',(change('api-task',3,'UPDATE_TASK',dict(completion='COMPLETE')),));grant(cc,source(cc.command_id,canonical(cc.as_record()).encode()))
            (status,completed),complete_wire=mutation('COMPLETE_TASK',cc);require(status==200 and completed['code']=='COMMITTED','TRANSPORT_COMPLETE')
            cancel=Command('cancel-api','principal','USER_COMMAND','root-cancel-api',(change('api-task',4,'UPDATE_TASK',dict(disposition='CANCELLED')),));grant(cancel,source(cancel.command_id,canonical(cancel.as_record()).encode()))
            (status,cancelled),_=mutation('CANCEL_TASK',cancel);v=reader.get('api-task').aggregate.as_record()
            require(status==200 and v['core']['completion']=='COMPLETE' and v['core']['disposition']=='CANCELLED' and v['effort']['user_remaining']['seconds']==0 and conn.execute("SELECT sum(seconds) FROM whattodo.effort_observation WHERE kind='ACTUAL_WORK'").fetchone()==(900,),'TRANSPORT_LIFECYCLE')
            checks.append('complete_and_cancel_routes_keep_separate_lifecycle_history_zero_u_and_original_actual_work')
            saved=dict(config);config.update(grants=(),patch_grants=(),work_grants=(),intents=(),input_bindings=())
            before=state();lookup=wire('LOOKUP_COMMAND',cc.command_id)
            require(http(complete_wire)[1]['code']=='REPLAY' and http(lookup,READ_TOKEN)[1]['status']=='SUCCESS' and state()==before,'TRANSPORT_RESTART_REPLAY')
            foreign_receipt=http(lookup,OTHER_TOKEN);require(foreign_receipt[1]['status']=='PERMANENT' and foreign_receipt[1]['data'] is None,'TRANSPORT_FOREIGN_RECEIPT')
            config.update(saved)
            checks.append('authenticated_restart_replay_and_lookup_recover_owned_receipts_without_live_grants_or_accounts_and_hide_foreign_receipts')
            creation_raw=guided_message(dict(title='Created through API followup'));ref=source('followup-source',creation_raw)
            resolution_wire=wire('RESOLVE_CREATION','followup-command',creation_raw.decode(),dict(source_ref=ref,session_id='api-followup-session',desired_task_id='api-followup-task',input_mode='GUIDED'))
            before=epoch();resolved=http(resolution_wire)[1];f=resolved['data']['result']
            require(resolved['code']=='NEEDS_CLARIFICATION' and f['missing_fields'] and epoch()==before,'TRANSPORT_NORMALIZATION')
            reply=dict(schema_version='0.1.0-clarification-reply',reply_id='api-answer',session_id=f['session_id'],expected_revision=f['revision'],scope_hash=f['scope_hash'],selection=None,answers=dict(importance='4',requiredness='\u5fc5\u987b\u5b8c\u6210',difficulty='3/2/3',domain='\u5b66\u4e60'))
            reply_raw=canonical(reply).encode();reply_ref=source('api-answer-source',reply_raw);answer_wire=wire('CLARIFY','api-answer',reply_raw.decode(),dict(source_ref=reply_ref))
            answer=http(answer_wire)[1];frame=answer['data']['result'];require(answer['code']=='RESOLVED' and frame['command_id']=='followup-command' and epoch()==before,'TRANSPORT_SAME_COMMAND')
            hf=http(wire('RESOLUTION_HANDOFF','handoff-view',parameters=dict(session_id=frame['session_id'],revision=frame['revision'],scope_hash=frame['scope_hash'],authority_ref='api-followup-root')))[1]
            h=hf['data']['result'];require(hf['code']=='HANDOFF_READY' and h['command']['command_id']=='followup-command' and h['source_refs']==[ref,reply_ref],'TRANSPORT_SOURCE_CHAIN')
            checks.append('normalization_clarification_and_handoff_routes_preserve_original_user_bytes_frame_scope_and_same_command_identity_without_task_publication')
            made=Command(h['command']['command_id'],'principal','USER_COMMAND','api-followup-root',tuple(change(**v) for v in h['command']['changes']));grant(made,reply_ref)
            config['intents']+=(ResolvedManualIntent(made.fingerprint,reply_ref,NOW,canonical(dict(domain='study'))),)
            (status,created),_=mutation('CREATE_TASK',made,h['expected_store_revision']);require(status==200 and created['code']=='COMMITTED' and reader.get('api-followup-task').aggregate.as_record()['effort']['user_remaining'] is None,'TRANSPORT_FOLLOWUP_CREATE')
            before=state();require(http(answer_wire)[1]['code']=='CLARIFICATION_REPLAY' and state()==before,'TRANSPORT_FOLLOWUP_REPLAY')
            checks.append('resolved_followup_reaches_existing_creation_only_after_independent_grant_and_reply_replays_without_duplicate_task')
            current=http(wire('RESOLUTION_GET','get-followup',parameters=dict(session_id=frame['session_id'],revision=None)))[1]
            require(current['data']['result']==frame,'TRANSPORT_FRAME_READ')
            checks.append('owned_resolution_get_returns_minimized_versioned_view_without_raw_source_or_internal_pending_json')
            # The normalized structured intent uses the same shared wire as n8n.
            ri=dict(schema_version='0.1.0-resolution-intent',session_id='api-resolve-session',command_id='api-resolve-command',principal_id='principal',action='CANCEL_TASK',target=dict(mode='NAME',value='Updated homework',course=None),creation_task_id=None,fields=dict(disposition='CANCELLED'),creation_facts={})
            ri_raw=canonical(ri).encode();ri_ref=source('api-resolve-source',ri_raw);clear=http(wire('RESOLVE',ri['command_id'],ri_raw.decode(),dict(source_ref=ri_ref)))[1]
            require(clear['code']=='RESOLVED' and not clear['data']['result']['question'],'TRANSPORT_EXACT_NAME')
            checks.append('structured_n8n_reference_intent_resolves_exact_unique_name_without_duplicate_approval')
            fuzzy=dict(ri,session_id='api-fuzzy-session',command_id='api-fuzzy-command',target=dict(mode='NAME',value='Updated homewor',course=None))
            fuzzy_raw=canonical(fuzzy).encode();fuzzy_ref=source('api-fuzzy-source',fuzzy_raw)
            question=http(wire('RESOLVE',fuzzy['command_id'],fuzzy_raw.decode(),dict(source_ref=fuzzy_ref)))[1]['data']['result']
            require(question['state']=='NEEDS_TASK','TRANSPORT_FUZZY_PENDING')
            refreshed=http(wire('REFRESH_RESOLUTION','api-refresh',parameters=dict(session_id=question['session_id'],expected_revision=question['revision'],scope_hash=question['scope_hash'])))[1]
            require(refreshed['data']['result']['revision']==2,'TRANSPORT_REFRESH')
            stale_reply=dict(reply,reply_id='api-stale-answer',session_id=question['session_id'],expected_revision=1,scope_hash=question['scope_hash'],selection='1',answers={})
            stale_raw=canonical(stale_reply).encode();stale_ref=source('api-stale-answer-source',stale_raw)
            before=state();stale=http(wire('CLARIFY',stale_reply['reply_id'],stale_raw.decode(),dict(source_ref=stale_ref)))
            require(stale[0]==409 and stale[1]['code']=='RESOLUTION_STALE_SESSION' and state()==before,'TRANSPORT_REFRESH_STALE_REPLY')
            checks.append('refresh_route_advances_only_question_version_and_old_scoped_answer_returns_conflict_without_state_changes')
            external_ref=source('external-normalization',creation_raw,kind='EMAIL')
            before=state();external=http(wire('RESOLVE_CREATION','external-command',creation_raw.decode(),dict(source_ref=external_ref,session_id='external-session',desired_task_id='external-task',input_mode='GUIDED')))
            require(external[0]==400 and external[1]['code']=='RESOLUTION_USER_SOURCE_REQUIRED' and state()==before,'TRANSPORT_EXTERNAL_NORMALIZATION')
            checks.append('raw_creation_route_preserves_typed_source_validation_errors_and_cannot_use_external_content_as_user_input')
            foreign_source_command=Command('foreign-account-command','other','USER_COMMAND','foreign-account-root',(change('foreign-account-task',None,'CREATE_TASK',dict(title='Foreign account task',importance=3,requiredness='OPTIONAL',difficulty=DIMS)),))
            foreign_ref=source('foreign-account-source',canonical(foreign_source_command.as_record()).encode());grant(foreign_source_command,foreign_ref)
            config['intents']+=(ResolvedManualIntent(foreign_source_command.fingerprint,foreign_ref,NOW,canonical(dict(domain='study'))),)
            before=state();(status,blocked),_=mutation('CREATE_TASK',foreign_source_command,token=OTHER_TOKEN)
            require(status==400 and blocked['status']=='PERMANENT' and state()==before and reader.get('foreign-account-task') is None,'TRANSPORT_CROSS_ACCOUNT_SOURCE')
            checks.append('backend_filters_registered_source_scopes_by_authenticated_principal_instead_of_sharing_other_account_bindings')
            missing=create_command('not-granted');config['grants']=tuple(g for g in config['grants'] if g.command_id!=missing.command_id)
            before=state();(status,rejected),_=mutation('CREATE_TASK',missing)
            require(rejected['code']=='UNREGISTERED_AUTHORITY' and state()==before,'TRANSPORT_AUTH_IS_NOT_GRANT')
            checks.append('valid_transport_authentication_cannot_replace_missing_exact_domain_authority')
            interrupted=create_command('interrupted');before=state();fault['before_commit']=True
            (status,retry),retry_wire=mutation('CREATE_TASK',interrupted);fault['before_commit']=False
            require(retry['status']=='RETRYABLE' and state()==before,'TRANSPORT_PRECOMMIT_'+retry['code'])
            require(http(retry_wire)[1]['code']=='COMMITTED','TRANSPORT_PRECOMMIT_RETRY')
            checks.append('native_precommit_failure_rolls_back_all_task_audit_receipt_epoch_state_then_same_wire_retry_commits_once')
            unknown_command=create_command('lost-response');before=epoch();fault['after_commit']=True
            (status,unknown),unknown_wire=mutation('CREATE_TASK',unknown_command);fault['after_commit']=False
            require(status==202 and unknown['status']=='UNKNOWN' and reader.get('lost-response') is not None and epoch()==before+1,'TRANSPORT_UNKNOWN_COMMIT')
            original=http(wire('LOOKUP_COMMAND',unknown_command.command_id))[1];require(original['status']=='SUCCESS' and http(unknown_wire)[1]['code']=='REPLAY' and epoch()==before+1,'TRANSPORT_UNKNOWN_RECOVERY')
            checks.append('lost_transport_result_after_real_commit_stays_unknown_and_lookup_or_same_id_retry_recovers_one_original_receipt')
            # Typed HTTP framing rejects never reach the backend.
            before=state();opens=counts['backend_opens']
            for headers,status in (({'Content-Type':'text/plain'},415),({'Transfer-Encoding':'chunked'},411),({'Content-Length':str(MAX_REQUEST_BYTES+1)},413)):
                require(http(b'{}',headers=headers)[0]==status,'TRANSPORT_HTTP_FRAMING')
            require(counts['backend_opens']==opens and state()==before,'TRANSPORT_HTTP_FRAMING_OPENED')
            checks.append('actual_http_invalid_content_type_chunked_input_and_declared_oversize_return_typed_errors_without_database_access')
            report.update(migration_steps=len(plan.steps),schema_version=plan.schema_version,domain_tables=conn.execute("SELECT count(*) FROM pg_tables WHERE schemaname='whattodo'").fetchone()[0],domain_foreign_keys=conn.execute("SELECT count(*) FROM pg_constraint c JOIN pg_namespace n ON n.oid=c.connamespace WHERE n.nspname='whattodo' AND c.contype='f'").fetchone()[0],**counts)
            require((report['domain_tables'],report['domain_foreign_keys'])==(87,221),'TRANSPORT_SCHEMA_CHANGED')
            checks.append('current_runtime_schema_and_canonical_ownership_remain_unchanged')
    finally:
        server.shutdown();server.server_close();thread.join(timeout=5);require(not thread.is_alive(),'TRANSPORT_HTTP_SERVER_NOT_STOPPED')
        report['http_server_stopped']=not thread.is_alive()


def main():
    harness=PostgresHarness();report=dict(task='M3A-16',status='IN_PROGRESS',scope='SYNTHETIC_AUTHENTICATED_LOOPBACK_HTTP_HANDOFF',verified_on='2026-10-10',native_checks=[])
    try:
        with harness:verify(harness,report)
        report.update(status='PASS',native_check_count=len(report['native_checks']),limitations=['Loopback prototype with independent synthetic credentials/grants/accounts; not deployed or connected to live n8n','Already-normalized handler contracts and first freeform creation instance only; other normalization classes remain separate work','Transport authentication grants no Task authority and does not provision user credentials or provider access'])
    except Exception as exc:report.update(status='FAIL',failure_type=type(exc).__name__,failure_code=str(exc) if isinstance(exc,HarnessError) else 'TRANSPORT_NATIVE_FAILED',failure_sqlstate=getattr(exc,'sqlstate',None))
    report['harness']=harness.safe_summary();target=harness.run_root/'command-transport-report.json'
    if harness.run_root.exists():target.write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(dict(status=report['status'],report=str(target),checks=len(report['native_checks']),http_server_stopped=report.get('http_server_stopped'),server_stopped=report['harness']['server_stopped'])))
    return 0 if report['status']=='PASS' else 1

if __name__=='__main__':raise SystemExit(main())
