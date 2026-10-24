"""Native owned read snapshots and loopback query handoff; synthetic data only."""
from contextlib import contextmanager
from copy import deepcopy
from dataclasses import replace
from datetime import timedelta
from hashlib import sha256
from http.client import HTTPConnection
from pathlib import Path
from threading import Thread
import json
import sys
ROOT=Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:sys.path.insert(0,str(ROOT))
from tools.verify_command_transport import NOW,CLOCK,SCOPE,OTHER_SCOPE,TOKEN,OTHER_TOKEN,NARROW_TOKEN,DIMS
from src import __version__
from src.adapters.clocks import FrozenClock
from src.adapters.extension_contracts import load_supported_schemas
from src.adapters.migration_files import load_migration_plan
from src.adapters.memory_definitions import MemoryDefinitionRepository
from src.adapters.postgres_authorization import register_grant
from src.adapters.postgres_evidence import PostgresEvidenceRepository,register_source_scope
from src.adapters.postgres_migrations import DatabaseRoles,apply_migrations
from src.adapters.postgres_read_models import PostgresReadService
from src.adapters.postgres_tasks import PostgresTaskRepository
from src.adapters.postgres_transactions import PostgresTransactionCoordinator
from src.adapters.postgres_transport import PostgresPrototypeBackend
from src.adapters.postgres_work_reports import register_work_report_grant
from src.adapters.prototype_codec import PrototypeJSONCodec
from src.adapters.prototype_http import AuthenticatedCommandTransport,make_http_server
from src.application.command_transport import TransportCredential,OPERATIONS,token_digest
from src.application.definitions import canonical
from src.application.direct_creation import UserInputBinding,guided_message
from src.application.evidence_storage import pending_id
from src.application.manual_tasks import ResolvedManualIntent
from src.application.ports import AggregateKey,CommitRequest,RecordWrite,RequestContext,TransactionPermit
from src.application.task_storage import TaskStorageBindings
from src.application.work_reports import admit_work_report,WorkReportGrant
from src.domain.authorization import AuthorityGrant,CallerIdentity,Command,change
from src.domain.provenance import capture_source,make_candidate
from tools.postgres_harness import HarnessError,PostgresHarness,ROLES,require
from tools.verify_transactions import TABLES
KEY=b'synthetic-native-read-cursor-key-0001';CALLER=CallerIdentity('principal','USER_COMMAND',True)
def query(view='TASKS',**kw):
    v=dict(schema_version='0.1.0-read-query',view=view,task_id='a' if view=='HISTORY' else None,filters=dict(completion=None,disposition=None,trust=None,domain=None,context=None),pending_kind=None,include_closed=False,page_size=1,cursor=None);v.update(kw);return v

def verify(harness,report):
    import psycopg
    plan=load_migration_plan(root=ROOT);old=load_migration_plan(root=ROOT,manifest_path=ROOT/'reports/acceptance/M3A-16-migration-plan.json');codec=PrototypeJSONCodec(load_supported_schemas(root=ROOT));checks=report['native_checks']
    database=harness.create_database(initialize_schema=False);roles=DatabaseRoles(ROLES['migration'],ROLES['application'],ROLES['test'])
    with harness.target(database,'migration').connect() as owner:
        apply_migrations(owner,old,roles=roles,application_version=__version__);before=owner.execute('SELECT * FROM whattodo_meta.migration_history ORDER BY position').fetchall()
        out=apply_migrations(owner,plan,roles=roles,application_version=__version__);require(out.applied==('012_read_snapshots','013_relationship_storage','014_creation_outbox','015_generation_occurrences','016_generation_processing','017_stage_commands','018_review_queue'),'READ_UPGRADE_SUFFIX')
        require(owner.execute('SELECT * FROM whattodo_meta.migration_history WHERE position<=12 ORDER BY position').fetchall()==before,'READ_UPGRADE_PREFIX')
        for scope in (SCOPE,OTHER_SCOPE):register_source_scope(owner,plan,roles,scope,application_version=__version__,clock=CLOCK)
    checks.append('thirteenth_metadata_migration_preserves_all_twelve_prior_migration_receipts')
    config=dict(definitions=MemoryDefinitionRepository(CLOCK),grants=(),work_grants=(),intents=(),input_bindings=(UserInputBinding('principal',SCOPE),UserInputBinding('other',OTHER_SCOPE)),read_cursor_key=KEY)
    counts=dict(backend_opens=0)
    @contextmanager
    def factory():
        counts['backend_opens']+=1
        with harness.target(database).connect() as conn:yield PostgresPrototypeBackend(conn,codec,plan,application_version=__version__,clock=CLOCK,**config)
    def credential(token,principal='principal',tasks=None):return TransportCredential(principal,token_digest(token),OPERATIONS,tasks,NOW-timedelta(minutes=1),NOW+timedelta(hours=1))
    transport=AuthenticatedCommandTransport(codec,clock=CLOCK,credentials=(credential(TOKEN),credential(OTHER_TOKEN,'other'),credential(NARROW_TOKEN,tasks=frozenset({'a'}))),backend_factory=factory)
    server=make_http_server(transport);thread=Thread(target=server.serve_forever,kwargs=dict(poll_interval=.02));thread.start()
    def wire(op,request,payload=None,parameters=None):return canonical(dict(schema_version='0.1.0-prototype-request',operation=op,request_id=request,correlation_ref='read-correlation',payload=canonical(payload) if payload is not None else None,parameters=parameters or {})).encode()
    def http(raw,token=TOKEN):
        client=HTTPConnection('127.0.0.1',server.server_port,timeout=10)
        try:
            headers={'Content-Type':'application/json'}
            if token:headers['Authorization']='Bearer '+token
            client.request('POST','/v1/commands',raw,headers);response=client.getresponse();body=response.read();require(response.getheader('Cache-Control')=='no-store','READ_HTTP_CACHE');return response.status,json.loads(body)
        finally:client.close()
    try:
        with harness.target(database).connect() as conn:
            options=dict(application_version=__version__,clock=CLOCK)
            reader=PostgresTaskRepository(conn,codec,plan,**options);repo=PostgresEvidenceRepository(conn,codec,plan,**options,scopes=(SCOPE,OTHER_SCOPE))
            service=PostgresReadService(conn,codec,plan,**options,cursor_key=KEY,scopes=(SCOPE,))
            def epoch():return conn.execute('SELECT revision FROM whattodo.store_epoch').fetchone()[0]
            def canonical_state():return tuple(conn.execute('SELECT * FROM whattodo.'+t+' ORDER BY 1,2').fetchall() for t in TABLES+('effort_observation','normalized_due','manual_creation_pending','command_resolution_revision','command_resolution_head','command_resolution_reply'))
            def source(name,raw,scope=SCOPE):
                s=capture_source(provider=scope.provider,scope_ref=scope.scope_ref,external_id=name,raw_bytes=raw,captured_at=NOW,source_type='USER');repo.observe_source(canonical(s.as_record()).encode(),raw_content=raw,locator_ref='private-locator-'+name);return s
            def grant(c,ref):
                g=AuthorityGrant(c.authority_ref,c.principal_id,c.origin,c.command_id,c.changes,ref,NOW-timedelta(minutes=1),expires_at=NOW+timedelta(hours=1))
                with harness.target(database,'migration').connect() as owner:register_grant(owner,g,plan,application_version=__version__)
                config['grants']+=(g,)
            def mutation(op,c,token=TOKEN):
                status,out=http(wire(op,c.command_id,c.as_record(),dict(expected_store_revision=epoch(),audit_id='audit-'+c.command_id)),token);require(status==200,'READ_FIXTURE_'+op+'_'+out['code']);return out
            def create(name,*,principal='principal',partial=False,unknown=False,expiring=False):
                fields=dict(title='Synthetic '+name,importance=3,requiredness='EXPIRING' if expiring else 'REQUIRED',difficulty=DIMS)
                if not unknown:fields['user_remaining_seconds']=600
                if expiring:fields['expiration_condition_ref']='class-start'
                if partial:fields=dict(title='Synthetic '+name)
                c=Command('create-'+name,principal,'USER_COMMAND','root-'+name,(change(name,None,'CREATE_TASK',fields),));ref=source(c.command_id,canonical(c.as_record()).encode(),SCOPE if principal=='principal' else OTHER_SCOPE).record_id;grant(c,ref)
                config['intents']+=(ResolvedManualIntent(c.fingerprint,ref,NOW,canonical({} if partial else dict(domain='study'))),)
                out=mutation('CREATE_TASK',c,TOKEN if principal=='principal' else OTHER_TOKEN);require(out['code']==('PENDING_DETAILS' if partial else 'COMMITTED'),'READ_FIXTURE_CREATE_'+out['code']);return c
            def read(v,svc=service,caller=CALLER):return svc.query(canonical(v).encode(),RequestContext('read','read-correlation'),caller=caller)
            def page(v,svc=service,caller=CALLER):
                out=read(v,svc,caller);require(out.status=='SUCCESS','READ_QUERY_'+out.code);return out.value.as_record()
            def all_pages(v,svc=service):
                items=[];pages=[]
                while True:
                    p=page(v,svc);items.extend(p['items']);pages.append(p)
                    if not p['has_more']:return items,pages
                    v=dict(v,cursor=p['next_cursor'])
            create('a');create('b',unknown=True);create('z');create('foreign',principal='other');create('partial',partial=True)
            before=canonical_state();p=page(query());require(p['items'][0]['id']=='a' and p['has_more'],'READ_FIRST_PAGE');require(canonical_state()==before,'READ_MUTATED_CANONICAL')
            checks.append('fresh_query_caches_immutable_version_references_without_changing_tasks_audits_receipts_or_store_epoch')
            frozen=p['next_cursor'];snapshot_id=p['snapshot_id'];create('c')
            complete=Command('complete-b','principal','USER_COMMAND','root-complete-b',(change('b',1,'UPDATE_TASK',dict(completion='COMPLETE')),));grant(complete,source(complete.command_id,canonical(complete.as_record()).encode()).record_id);mutation('COMPLETE_TASK',complete)
            rest=page(query(cursor=frozen));require(rest['snapshot_id']==snapshot_id and rest['items'][0]['id']=='b' and rest['items'][0]['revision']==1 and rest['items'][0]['data']['user_remaining'] is None,'READ_VERSION_DRIFT')
            restart=PostgresReadService(conn,codec,plan,**options,cursor_key=KEY,scopes=(SCOPE,));require(page(query(cursor=frozen),restart)==rest,'READ_RESTART_DRIFT')
            final=page(query(cursor=rest['next_cursor']));require([i['id'] for i in final['items']]==['z'] and not final['has_more'],'READ_INSERT_PAGINATION_DRIFT')
            checks.append('restart_safe_signed_cursor_keeps_original_task_versions_order_and_membership_across_insert_and_completion')
            fresh=page(query(page_size=100));require([i['id'] for i in fresh['items']]==['a','b','c','z'] and next(i for i in fresh['items'] if i['id']=='b')['data']['user_remaining']['seconds']==0,'READ_FRESH_STATE')
            require('foreign' not in canonical(fresh) and 'partial' not in canonical(fresh),'READ_FOREIGN_OR_PENDING_AS_TASK')
            checks.append('fresh_owned_task_view_distinguishes_unknown_remaining_from_completed_zero_and_excludes_foreign_tasks_and_uncreated_proposals')
            h=page(query('HISTORY',task_id='b'));cancel=Command('cancel-b','principal','USER_COMMAND','root-cancel-b',(change('b',2,'UPDATE_TASK',dict(disposition='CANCELLED')),));grant(cancel,source(cancel.command_id,canonical(cancel.as_record()).encode()).record_id);mutation('CANCEL_TASK',cancel)
            oldh=page(query('HISTORY',task_id='b',cursor=h['next_cursor']));require(oldh['items'][0]['revision']==2 and not oldh['has_more'],'READ_HISTORY_DRIFT')
            history,_=all_pages(query('HISTORY',task_id='b'));require([i['revision'] for i in history]==[1,2,3] and history[-1]['data']['task']['completion']=='COMPLETE' and history[-1]['data']['task']['disposition']=='CANCELLED','READ_RETAINED_OUTCOMES')
            require('/completion' in history[1]['data']['event']['changed_fields'] and '/disposition' in history[2]['data']['event']['changed_fields'] and all('/revision' not in i['data']['event']['changed_fields'] for i in history),'READ_SEMANTIC_HISTORY')
            checks.append('history_matches_exact_immutable_audit_versions_and_retains_separate_completion_and_cancellation_events_with_semantic_differences')
            w=dict(schema_version='0.1.0-work-report',command_id='work-a',principal_id='principal',origin='USER_COMMAND',authority_ref='root-work-a',observation_id='actual-a',target_ref=dict(task_id='a',revision=1),mode='INCREMENT',seconds=900,stage_id=None,session_started_at=None,session_ended_at=None)
            wr=admit_work_report(codec,canonical(w).encode());ref=source(wr.command_id,canonical(w).encode()).record_id;wg=WorkReportGrant(wr,ref,NOW,NOW+timedelta(hours=1))
            with harness.target(database,'migration').connect() as owner:register_work_report_grant(owner,wg,plan,application_version=__version__)
            config['work_grants']+=(wg,);status,out=http(wire('REPORT_WORK',wr.command_id,w,dict(expected_store_revision=epoch(),audit_id='audit-work-a')));require(status==200 and out['code']=='COMMITTED','READ_WORK_FIXTURE')
            hist,_=all_pages(query('HISTORY',task_id='a'));require([i['data']['task']['actual_seconds'] for i in hist]==[0,900] and hist[-1]['data']['task']['user_remaining']['seconds']==600 and '/actual_seconds' in hist[-1]['data']['event']['changed_fields'],'READ_ACTUAL_HISTORY')
            require(page(query(cursor=frozen))==rest,'READ_OLD_ACTUAL_SNAPSHOT_DRIFT')
            checks.append('historical_actual_work_is_frozen_per_version_and_reported_work_does_not_decrement_user_remaining')
            create('expired',expiring=True);preview=reader.get('expired');ref=source('expiry-fixture',b'synthetic expiry fact').record_id
            with harness.target(database,'migration').connect() as owner:owner.execute('INSERT INTO whattodo.expiration_notice VALUES(%s,%s,%s,%s,%s,%s,%s)',('notice-expired','expired',1,'class-start',ref,NOW,'create-expired'))
            v=preview.aggregate.as_record();v['core']['revision']=v['effort']['task_revision']=2;v['core']['disposition']=v['effort']['disposition']='EXPIRED';v['core']['expiration']['notice_ref']='notice-expired'
            req=CommitRequest(RequestContext('expiry-fixture','read-correlation'),CALLER.principal_id,epoch(),(RecordWrite(AggregateKey('TASK','expired'),1,canonical(v)),),'audit-expiry-fixture',ref);permit=TransactionPermit('permit-expiry-fixture',CALLER.principal_id,CALLER.origin,req.fingerprint,NOW,NOW+timedelta(minutes=5))
            out=PostgresTransactionCoordinator(conn,codec,plan,**options,permits=(permit,),bindings=(('expired',TaskStorageBindings(notice_task_revision=1)),)).commit(req,caller=CALLER,permit_ref=permit.permit_ref);require(out.code=='COMMITTED','READ_EXPIRY_FIXTURE_'+out.code)
            expired,_=all_pages(query('HISTORY',task_id='expired'));require(expired[-1]['data']['task']['disposition']=='EXPIRED' and expired[-1]['data']['task']['user_remaining']['seconds']==600,'READ_EXPIRED_HISTORY')
            checks.append('expired_outcomes_remain_queryable_with_positive_remaining_and_notice_backed_immutable_history')
            for name,value,expected in [('completion','COMPLETE',['b']),('disposition','EXPIRED',['expired']),('domain','study',['a','b','c','expired','z'])]:
                q=query(page_size=100);q['filters'][name]=value;require([i['id'] for i in page(q)['items']]==expected,'READ_FILTER_'+name)
            q=query(page_size=100);q['filters']['context']=dict(kind='COURSE',id='not-bound');require(page(q)['items']==[],'READ_CONTEXT_FILTER')
            checks.append('typed_exact_completion_disposition_domain_and_context_filters_preserve_owned_retained_records')
            raw=b'private-source-body-never-returned';s=source('candidate',raw);candidate=make_candidate(s,parser_version='synthetic-parser',action='CREATE_TASK',proposed_fields=dict(title='Candidate title'),confidence='0.8');repo.observe_candidate(canonical(candidate.as_record()).encode())
            conflict=repo.observe_source(canonical(replace(s,source_timestamp=NOW).as_record()).encode(),raw_content=raw,locator_ref='private-conflict-locator');require(conflict.outcome=='CONFLICT','READ_SOURCE_CONFLICT_FIXTURE')
            other=source('foreign-candidate',b'foreign body',OTHER_SCOPE);foreign_candidate=make_candidate(other,parser_version='foreign-parser',action='CREATE_TASK',proposed_fields=dict(title='Foreign candidate'),confidence='0.8');repo.observe_candidate(canonical(foreign_candidate.as_record()).encode())
            pending,pending_pages=all_pages(query('PENDING'));kinds={i['kind'] for i in pending};require(kinds=={'MANUAL_CREATION','EVIDENCE_CANDIDATE','EVIDENCE_CONFLICT'} and all(i['state']=='OPEN' for i in pending) and 'Foreign candidate' not in canonical(pending),'READ_PENDING_OWNERSHIP')
            require(all(p['source_scope_state']=='CONFIGURED' for p in pending_pages) and 'private-source-body' not in canonical(pending) and 'observed_wire' not in canonical(pending) and 'proposal_json' not in canonical(pending),'READ_PENDING_RAW_LEAK')
            checks.append('pending_manual_candidate_and_source_conflict_views_are_versioned_account_scoped_and_exclude_raw_proposals_sources_and_observed_conflict_wire')
            candidate_q=query('PENDING',pending_kind='EVIDENCE_CANDIDATE');candidate_page=page(candidate_q);require(len(candidate_page['items'])==1,'READ_CANDIDATE_COUNT')
            saved_candidate=conn.execute('SELECT payload_bytes FROM whattodo.read_snapshot WHERE snapshot_id=%s',(candidate_page['snapshot_id'],)).fetchone()
            with conn.transaction():
                pid=pending_id('CANDIDATE',candidate.candidate_id)
                repo._insert('pending_evidence_revision',dict(pending_id=pid,revision=2,state='RESOLVED',authority_ref='root-a',resolved_at=NOW,transaction_ref='create-a'))
                conn.execute('UPDATE whattodo.pending_evidence_head SET revision=2 WHERE pending_id=%s AND revision=1',(pid,))
            require(page(candidate_q)['items']==[],'READ_CANDIDATE_CLOSED_OPEN_QUERY')
            closed_candidate=page(dict(candidate_q,include_closed=True))['items'][0];require(closed_candidate['state']=='RESOLVED' and closed_candidate['revision']==1 and closed_candidate['data']['pending_ref']['revision']==2,'READ_PENDING_AND_CANDIDATE_DISTINCT_VERSIONS')
            from src.application.read_models import ReadQuery,ReadSnapshot
            saved_snapshot=ReadSnapshot(bytes(saved_candidate[0]),canonical(json.loads(bytes(saved_candidate[0]))))
            with service._transaction():old_candidate=service._page(saved_snapshot,ReadQuery(canonical(candidate_q)),0,CALLER).as_record()
            require(old_candidate==candidate_page,'READ_CANDIDATE_OLD_STATE_DRIFT')
            checks.append('candidate_and_pending_review_have_distinct_version_refs_and_old_snapshot_keeps_open_state_after_review_closure')
            raw=guided_message(dict(title='Followup'));ref=source('followup-source',raw).record_id
            # Raw input is already a JSON string, not a JSON value for the envelope helper.
            raw_wire=canonical(dict(schema_version='0.1.0-prototype-request',operation='RESOLVE_CREATION',request_id='followup-command',correlation_ref='read-correlation',payload=raw.decode(),parameters=dict(source_ref=ref,session_id='followup-session',desired_task_id='followup-task',input_mode='GUIDED'))).encode()
            status,out=http(raw_wire);require(status==200,'READ_FOLLOWUP_FIXTURE_'+out['code']);f=out['data']['result']
            earlier_wire=json.loads(raw_wire);earlier_wire['request_id']='earlier-command';earlier_wire['parameters'].update(session_id='a-earlier-session',desired_task_id='earlier-task')
            require(http(canonical(earlier_wire).encode())[0]==200,'READ_EARLIER_CLARIF_FIXTURE')
            clarif_first=page(query('PENDING',pending_kind='CLARIFICATION'));require(clarif_first['items'][0]['id']=='a-earlier-session' and clarif_first['has_more'],'READ_CLARIF_SNAPSHOT_FIXTURE')
            clarif_cursor=clarif_first['next_cursor'];old_followup=page(query('PENDING',pending_kind='CLARIFICATION',cursor=clarif_cursor))
            q=query('PENDING',pending_kind='CLARIFICATION');clarif=page(q);require(clarif['items'][0]['state']=='OPEN','READ_CLARIF_OPEN')
            reply=dict(schema_version='0.1.0-clarification-reply',reply_id='followup-answer',session_id=f['session_id'],expected_revision=f['revision'],scope_hash=f['scope_hash'],selection=None,answers=dict(importance='4',requiredness='\u5fc5\u987b\u5b8c\u6210',difficulty='3/2/3',domain='\u5b66\u4e60'));ref=source('followup-answer',canonical(reply).encode()).record_id
            status,out=http(wire('CLARIFY',reply['reply_id'],reply,dict(source_ref=ref)));require(status==200 and out['code']=='RESOLVED','READ_CLARIF_REPLY_'+out['code']);f=out['data']['result'];require(page(q)['items'][0]['state']=='OPEN','READ_RESOLVED_NOT_COMMITTED')
            checks.append('answered_clarification_remains_pending_until_canonical_command_commit_instead_of_disappearing_when_question_is_resolved')
            status,out=http(wire('RESOLUTION_HANDOFF','handoff-view',parameters=dict(session_id=f['session_id'],revision=f['revision'],scope_hash=f['scope_hash'],authority_ref='followup-root')));require(status==200,'READ_HANDOFF');h=out['data']['result'];c=Command('followup-command','principal','USER_COMMAND','followup-root',tuple(change(**v) for v in h['command']['changes']));grant(c,ref);config['intents']+=(ResolvedManualIntent(c.fingerprint,ref,NOW,canonical(dict(domain='study'))),);mutation('CREATE_TASK',c)
            require([i['id'] for i in page(q)['items']]==['a-earlier-session'],'READ_CLARIF_COMMIT_OPEN');closed=page(dict(q,include_closed=True,page_size=100));closed_followup=next(i for i in closed['items'] if i['id']=='followup-session');require(closed_followup['state']=='RESOLVED' and closed_followup['revision']==f['revision'],'READ_CLARIF_COMMIT_STATE')
            require(page(query('PENDING',pending_kind='CLARIFICATION',cursor=clarif_cursor))==old_followup and old_followup['items'][0]['state']=='OPEN','READ_OLD_CLARIF_STATE_DRIFT')
            checks.append('matching_audited_same_command_commit_closes_pending_clarification_while_retaining_its_last_version_and_minimal_summary')
            unconfigured=PostgresReadService(conn,codec,plan,**options,cursor_key=KEY)
            empty=page(query('PENDING',pending_kind='EVIDENCE_CANDIDATE'),unconfigured);require(empty['items']==[] and empty['source_scope_state']=='UNCONFIGURED','READ_UNCONFIGURED_EMPTY')
            manual=page(query('PENDING',pending_kind='MANUAL_CREATION'),unconfigured);require(manual['items'] and manual['source_scope_state']=='NOT_APPLICABLE','READ_MANUAL_OWNER_SCOPE')
            checks.append('unconfigured_evidence_access_is_explicit_and_does_not_masquerade_as_known_empty_while_owned_manual_pending_remains_readable')
            q=query('PENDING',page_size=1);saved=page(q);require(saved['has_more'],'READ_PENDING_CURSOR_FIXTURE');before_next=page(dict(q,cursor=saved['next_cursor']));new=source('new-candidate',b'later');repo.observe_candidate(canonical(make_candidate(new,parser_version='later-parser',action='CREATE_TASK',proposed_fields=dict(title='Later candidate'),confidence='0.8').as_record()).encode());require(page(dict(q,cursor=saved['next_cursor']))==before_next,'READ_PENDING_SNAPSHOT_DRIFT')
            malformed=source('malformed-candidate',b'external parser output')
            bad=make_candidate(malformed,parser_version='malformed-parser',action='CREATE_TASK',proposed_fields=dict(title='x'*501),confidence='0.8');repo.observe_candidate(canonical(bad.as_record()).encode())
            malformed_page=page(query('PENDING',pending_kind='EVIDENCE_CANDIDATE',page_size=100));bad_item=next(i for i in malformed_page['items'] if i['id']==bad.candidate_id);require(bad_item['data']['title'] is None and bad_item['state']=='OPEN','READ_MALFORMED_CANDIDATE_TITLE')
            checks.append('oversized_candidate_title_does_not_block_pending_page_or_truncate_original_evidence_into_task_facts')
            changed=PostgresReadService(conn,codec,plan,**options,cursor_key=KEY,scopes=(SCOPE,OTHER_SCOPE));require(read(dict(q,cursor=saved['next_cursor']),changed).code=='READ_SOURCE_SCOPE_CHANGED','READ_CHANGED_SOURCE_SCOPE')
            checks.append('pending_cursor_keeps_original_candidate_membership_versions_and_states_and_rejects_changed_account_scope_bindings')
            for changed_q in (query(cursor=frozen,page_size=2),dict(query(cursor=frozen),filters=dict(completion='COMPLETE',disposition=None,trust=None,domain=None,context=None))):require(read(changed_q).code=='READ_CURSOR_SCOPE_CONFLICT','READ_CHANGED_QUERY')
            require(read(query(cursor=frozen),caller=CallerIdentity('other','USER_COMMAND',True)).code=='READ_CURSOR_SCOPE_CONFLICT','READ_CURSOR_FOREIGN')
            require(read(query(cursor=frozen+'a')).code=='READ_CURSOR_INVALID','READ_CURSOR_TAMPER')
            later=PostgresReadService(conn,codec,plan,application_version=__version__,clock=FrozenClock(NOW+timedelta(days=2)),cursor_key=KEY,scopes=(SCOPE,));require(read(query(cursor=frozen),later).code=='READ_SNAPSHOT_EXPIRED','READ_EXPIRED_CURSOR')
            require(read(query('HISTORY',task_id='foreign')).code=='READ_TASK_NOT_AVAILABLE','READ_FOREIGN_HISTORY')
            require(read(query(),caller=CallerIdentity('principal','EXTERNAL',True)).status=='PERMANENT','READ_EXTERNAL_CALLER')
            checks.append('tampered_expired_cross_principal_changed_query_and_foreign_history_requests_fail_without_leaking_records_or_refreshing_the_snapshot')
            before=canonical_state();status,out=http(wire('QUERY_STATE','api-read',query(page_size=100)));require(status==200 and out['data']['kind']=='READ_PAGE' and codec.admit('read-page',canonical(out['data']['result']).encode()).status=='SUPPORTED_SHAPE' and canonical_state()==before,'READ_HTTP_HANDOFF_'+out['code'])
            opens=counts['backend_opens'];require(http(wire('QUERY_STATE','denied',query()),NARROW_TOKEN)[0]==403 and counts['backend_opens']==opens,'READ_HTTP_TASK_SCOPE');require(http(b'invalid',None)[0]==401 and counts['backend_opens']==opens,'READ_HTTP_AUTH')
            checks.append('actual_loopback_query_returns_closed_read_page_envelope_and_authentication_or_narrow_scope_rejects_before_backend_open')
            for text in ('raw_content','raw_bytes','observed_wire','proposal_json','acceptance_ref',TOKEN,'private-locator'):
                require(text not in canonical(out),'READ_HTTP_SECRET_LEAK')
            checks.append('default_http_task_projection_contains_minimal_field_source_refs_without_source_content_internal_authorities_credentials_or_locators')
            try:conn.execute('UPDATE whattodo.read_snapshot SET expires_at=expires_at WHERE snapshot_id=%s',(snapshot_id,))
            except psycopg.Error as exc:require(exc.sqlstate=='23514','READ_IMMUTABILITY_CODE')
            else:raise HarnessError('READ_MUTABLE_SNAPSHOT')
            checks.append('application_role_cannot_mutate_immutable_snapshot_bytes_or_projections')
            class Fault:
                def __getattr__(self,name):return getattr(conn,name)
                def execute(self,sql,*args,**kw):
                    result=conn.execute(sql,*args,**kw)
                    if isinstance(sql,str) and sql.startswith('INSERT INTO whattodo.read_snapshot'):raise psycopg.OperationalError('synthetic cache interruption')
                    return result
            faulty=PostgresReadService(Fault(),codec,plan,**options,cursor_key=KEY,scopes=(SCOPE,));n=conn.execute('SELECT count(*) FROM whattodo.read_snapshot').fetchone()[0];before=canonical_state();out=read(query(),faulty);require(out.status=='RETRYABLE' and conn.execute('SELECT count(*) FROM whattodo.read_snapshot').fetchone()[0]==n and canonical_state()==before,'READ_CACHE_ROLLBACK')
            checks.append('precommit_snapshot_cache_fault_rolls_back_metadata_and_preserves_all_canonical_state_with_typed_retry')
            report.update(migration_steps=len(plan.steps),schema_version=plan.schema_version,domain_tables=conn.execute("SELECT count(*) FROM pg_tables WHERE schemaname='whattodo'").fetchone()[0],domain_foreign_keys=conn.execute("SELECT count(*) FROM pg_constraint c JOIN pg_namespace n ON n.oid=c.connamespace WHERE n.nspname='whattodo' AND c.contype='f'").fetchone()[0],**counts)
            require((report['domain_tables'],report['domain_foreign_keys'])==(87,221),'READ_SCHEMA_COUNT')
    finally:
        server.shutdown();server.server_close();thread.join(timeout=5);require(not thread.is_alive(),'READ_HTTP_SERVER_NOT_STOPPED');report['http_server_stopped']=True

def main():
    harness=PostgresHarness();report=dict(task='M3A-17',status='IN_PROGRESS',scope='SYNTHETIC_OWNED_TASK_HISTORY_PENDING_READ_MODELS',verified_on='2026-10-10',native_checks=[])
    try:
        with harness:verify(harness,report)
        report.update(status='PASS',native_check_count=len(report['native_checks']),limitations=['Versioned read lists are not a feasibility-verified Daily Brief','Independent cursor key and source-account bindings must be supplied by a trusted runtime; no live activation','Durable metadata snapshots have an explicit bounded lifetime and query-size limits; expiry returns conflict, not an implicit refresh'])
    except Exception as exc:report.update(status='FAIL',failure_type=type(exc).__name__,failure_code=str(exc) if isinstance(exc,HarnessError) else 'READ_NATIVE_FAILED',failure_sqlstate=getattr(exc,'sqlstate',None))
    report['harness']=harness.safe_summary();target=harness.run_root/'read-models-report.json'
    if harness.run_root.exists():target.write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(dict(status=report['status'],report=str(target),checks=len(report['native_checks']),http_server_stopped=report.get('http_server_stopped'),server_stopped=report['harness']['server_stopped'])))
    return 0 if report['status']=='PASS' else 1
if __name__=='__main__':raise SystemExit(main())