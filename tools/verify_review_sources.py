"""Native complete source-query checks over actual admitted runtime fixtures."""
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from datetime import timedelta
from pathlib import Path
from threading import Barrier
import json,sys,traceback
ROOT=Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:sys.path.insert(0,str(ROOT))
from src import __version__
from src.adapters.contract_json import ContractJSONCodec
from src.adapters.extension_contracts import load_supported_schemas
from src.adapters.git_definitions import GitDefinitionSource
from src.adapters.memory_definitions import MemoryDefinitionRepository
from src.adapters.postgres_authorization import register_grant
from src.adapters.postgres_definitions import PostgresDefinitionRepository
from src.adapters.postgres_evidence import PostgresEvidenceRepository
from src.adapters.postgres_fact_patches import PostgresFactPatchHandler,register_fact_patch_grant
from src.adapters.postgres_manual_tasks import PostgresManualTaskHandler
from src.adapters.postgres_resolution import PostgresResolutionService
from src.adapters.postgres_migrations import apply_migrations,DatabaseRoles
from src.adapters.postgres_review_service import PostgresReviewQueueService
from src.application.definitions import canonical
from src.application.direct_creation import UserInputBinding
from src.application.fact_patches import FactPatch,FactPatchGrant
from src.application.manual_tasks import ResolvedManualIntent
from src.application.ports import RequestContext
from src.application.review_queue import ReviewQueueQuery
from src.domain.authorization import AuthorityGrant,CallerIdentity,Command,change
from src.domain.provenance import capture_source
from tools.postgres_harness import PostgresHarness,HarnessError,ROLES,require
from tools.verify_review_queue_storage import review_plan
from tools import verify_read_models as reads
from tools import verify_stage_commands as stages
from tools import verify_generation_runtime as generation

KEY=b'synthetic-full-review-source-key-0001'


def codec():
    return ContractJSONCodec(load_supported_schemas(root=ROOT))


def verify(h,report):
    import psycopg
    roles=DatabaseRoles(ROLES['migration'],ROLES['application'],ROLES['test']);plan=review_plan();wire=codec();checks=report['native_checks']
    support=dict(native_checks=[]);reads.verify(h,support);db=h._created[-1]
    report['read_fixture_checks_not_counted']=len(support['native_checks']);report['http_server_stopped']=support['http_server_stopped']
    with h.target(db,'migration').connect() as owner:apply_migrations(owner,plan,roles=roles,application_version=__version__)
    clock=reads.CLOCK;caller=reads.CALLER;scope=reads.SCOPE;now=reads.NOW;q=ReviewQueueQuery(1,1)
    with h.target(db).connect() as conn:
        def service(c=conn,scopes=(scope,),**kw):
            return PostgresReviewQueueService(c,wire,plan,application_version=__version__,clock=clock,
                cursor_key=KEY,source_scopes=scopes,**kw)
        def query(name,query=q,svc=None,actor=caller):
            return (svc or service()).query(canonical(query.as_record()).encode(),RequestContext(name,'review-native'),caller=actor)
        def success(out):require(out.status=='SUCCESS','REVIEW_SOURCE_QUERY_'+out.status+'_'+out.code);return out.value
        def canonical_state():return tuple(conn.execute('SELECT * FROM whattodo.'+t+' ORDER BY 1,2').fetchall() for t in
            ('task_revision','task_head','stage_revision','effort_observation','authority_record','audit_entry','audit_change','command_transaction','store_epoch',
             'manual_creation_pending','command_resolution_head','command_resolution_revision','pending_evidence_head','pending_evidence_revision'))
        def observe(name,raw):
            s=capture_source(provider=scope.provider,scope_ref=scope.scope_ref,external_id=name,raw_bytes=raw,captured_at=now,source_type='USER')
            PostgresEvidenceRepository(conn,wire,plan,application_version=__version__,clock=clock,scopes=(scope,)).observe_source(
                canonical(s.as_record()).encode(),raw_content=raw,locator_ref='synthetic-'+name)
            return s
        def create(name,*,requiredness='OPTIONAL',importance=1,unknown=False):
            fields=dict(title='Synthetic '+name,importance=importance,requiredness=requiredness,
                difficulty=dict(thinking_depth=1,repetitive_volume=1,new_learning_load=1))
            if not unknown:fields['user_remaining_seconds']=600
            c=Command('review-create-'+name,caller.principal_id,'USER_COMMAND','review-root-'+name,
                (change(name,None,'CREATE_TASK',fields),))
            raw=canonical(c.as_record()).encode();s=capture_source(provider=scope.provider,scope_ref=scope.scope_ref,
                external_id=c.command_id,raw_bytes=raw,captured_at=now,source_type='USER')
            PostgresEvidenceRepository(conn,wire,plan,application_version=__version__,clock=clock,scopes=(scope,)).observe_source(
                canonical(s.as_record()).encode(),raw_content=raw,locator_ref='synthetic-'+name)
            g=AuthorityGrant(c.authority_ref,c.principal_id,c.origin,c.command_id,c.changes,s.record_id,now-timedelta(minutes=1),expires_at=now+timedelta(hours=1))
            with h.target(db,'migration').connect() as owner:register_grant(owner,g,plan,application_version=__version__)
            intent=ResolvedManualIntent(c.fingerprint,s.record_id,now,canonical(dict(domain='study',total_estimate_seconds=2400)))
            out=PostgresManualTaskHandler(conn,wire,plan,application_version=__version__,clock=clock,definitions=MemoryDefinitionRepository(clock),
                grants=(g,),source_scopes=(scope,),intents=(intent,)).create(raw,RequestContext(c.command_id,'native-create'),
                expected_store_revision=conn.execute('SELECT revision FROM whattodo.store_epoch').fetchone()[0],audit_id='audit-'+c.command_id,caller=caller)
            require(out.code=='COMMITTED','REVIEW_SOURCE_CREATE_'+out.code)
        def walk(first,query=q):
            all_items=list(first['items']);page=first
            while page['next_cursor']:
                with h.target(db).connect() as fresh:
                    page=success(query_page(page['next_cursor'],fresh,query))
                require(page['snapshot_id']==first['snapshot_id'] and page['groups']==first['groups'],'REVIEW_SOURCE_FROZEN_PAGE')
                all_items.extend(page['items'])
            require(len(all_items)==first['total_items'] and len({i['item_id'] for i in all_items})==len(all_items),'REVIEW_SOURCE_MISSING_PAGE')
            return all_items
        def query_page(cursor,c,query=q):return query_fn('next',replace(query,cursor=cursor),service(c))
        query_fn=query
        create('optional-low')
        create('missing-user-estimate',unknown=True)
        patch=FactPatch('review-future-due',caller.principal_id,'review-future-due-root','optional-low',1,
            canonical(dict(deadline='2099-01-01T00:00:00+08:00')))
        raw=canonical(patch.as_record()).encode();s=observe('future-due-input',raw)
        grant=FactPatchGrant(patch,s.record_id,now-timedelta(minutes=1),now+timedelta(hours=1),now)
        with h.target(db,'migration').connect() as owner:register_fact_patch_grant(owner,grant,plan,application_version=__version__)
        patched=PostgresFactPatchHandler(conn,wire,plan,application_version=__version__,clock=clock,grants=(grant,),source_scopes=(scope,)).patch(
            raw,RequestContext(patch.command_id,'future-due'),expected_store_revision=conn.execute('SELECT revision FROM whattodo.store_epoch').fetchone()[0],
            audit_id='audit-future-due',caller=caller)
        require(patched.code=='COMMITTED','REVIEW_SOURCE_FUTURE_DUE_'+patched.code)
        raw=canonical(dict(schema_version='0.1.0-resolution-intent',session_id='awaiting-session',command_id='awaiting-command',
            principal_id=caller.principal_id,action='CREATE_TASK',target=None,creation_task_id='awaiting-task',
            fields=dict(title='Known waiting task',importance=3,requiredness='REQUIRED',difficulty=reads.DIMS,user_remaining_seconds=600),
            creation_facts=dict(domain='study'))).encode()
        s=observe('awaiting-input',raw)
        resolved=PostgresResolutionService(conn,wire,plan,application_version=__version__,clock=clock,
            input_bindings=(UserInputBinding(caller.principal_id,scope),)).begin(raw,s.record_id,RequestContext('awaiting-command','awaiting'),caller=caller)
        require(resolved.code=='RESOLVED','REVIEW_SOURCE_AWAITING_SETUP_'+resolved.code)
        original=canonical_state();first=success(query('initial'));items=walk(first)
        kinds={i['kind'] for i in items}
        require({'TASK_ESTIMATE','MANUAL_CREATION','CLARIFICATION','EVIDENCE_CANDIDATE','EVIDENCE_CONFLICT'}<=kinds,'REVIEW_SOURCE_FAMILIES')
        require(first['enumeration_complete'] and all(i['answer'] is None for i in items)
            and not first['personal_reconciliation_complete'],'REVIEW_SOURCE_FALSE_RECONCILIATION')
        awaiting=next(i for i in items if i['kind']=='CLARIFICATION' and i['source_ref']['id']=='awaiting-session')
        require(awaiting['reason']=='AWAITING_EXECUTION' and awaiting['requires_response'] is False
            and awaiting['details']['question']=='','REVIEW_SOURCE_REASK_KNOWN_FACTS')
        tasks={i['task_ref']['task_id']:i for i in items if i['kind']=='TASK_ESTIMATE'}
        require('optional-low' in tasks and tasks['optional-low']['importance']==1 and tasks['optional-low']['details']['requiredness']=='OPTIONAL',
            'REVIEW_SOURCE_LOW_PRIORITY_DROPPED')
        require(tasks['missing-user-estimate']['details']['user_remaining'] is None
            and tasks['missing-user-estimate']['details']['estimate_status']=='MISSING','REVIEW_SOURCE_BASE_ESTIMATE_REPLACED_USER')
        require('b' not in tasks and 'expired' not in tasks and 'foreign' not in canonical(items) and 'Foreign candidate' not in canonical(items),
            'REVIEW_SOURCE_FOREIGN_OR_INACTIVE')
        require(all(i['details']['work_status']=='UNKNOWN' for i in tasks.values()) and canonical_state()==original,'REVIEW_SOURCE_INFERRED_NO_WORK')
        checks.append('actual_owned_tasks_and_four_pending_families_retain_far_future_low_optional_and_missing_user_estimates_without_reasking_ready_intents_or_mutating_canonical_state')
        create('later-task');retry=success(query('initial'))
        require(retry==first and walk(retry)==items,'REVIEW_SOURCE_REQUEST_REPLAY_CHANGED')
        fresh=success(query('fresh'));fresh_items=walk(fresh)
        require(any(i['task_ref'] and i['task_ref']['task_id']=='later-task' for i in fresh_items),'REVIEW_SOURCE_FRESH_TASK_OMITTED')
        checks.append('original_initial_request_and_all_frozen_pages_survive_new_canonical_tasks_while_a_fresh_request_sees_them')
        require(query('changed',replace(q,cursor=first['next_cursor']),service(scopes=(scope,reads.OTHER_SCOPE))).status=='CONFLICT','REVIEW_SOURCE_CHANGED_ACCOUNT')
        require(query('foreign',replace(q,cursor=first['next_cursor']),actor=CallerIdentity('other','USER_COMMAND',True)).status=='CONFLICT','REVIEW_SOURCE_FOREIGN_CURSOR')
        require(query('bad',replace(q,cursor=first['next_cursor']+'!')).status=='PERMANENT','REVIEW_SOURCE_BAD_CURSOR')
        require(query('initial',ReviewQueueQuery(2,1)).status=='CONFLICT','REVIEW_SOURCE_CHANGED_REQUEST')
        blocked=success(query('unconfigured',svc=service(scopes=())))
        require(not blocked['enumeration_complete'] and blocked['coverage_blockers']==['SOURCE_SCOPE_UNCONFIGURED']
            and blocked['items'][0]['requires_response'] is False,'REVIEW_SOURCE_FALSE_EMPTY')
        checks.append('changed_account_query_owner_and_signed_cursor_fail_and_unconfigured_scope_is_a_visible_coverage_gap')
        with h.target(db,'migration').connect() as owner:
            owner.execute('INSERT INTO whattodo.review_frame VALUES(%s,%s,%s,%s,%s)',
                ('unowned-legacy-review',1,'unowned-snapshot',now,psycopg.types.json.Jsonb(dict(secret='foreign-legacy-secret'))))
        gap=success(query('legacy-gap'));gap_items=walk(gap)
        require('LEGACY_REVIEW_SOURCE_UNADMITTED' in gap['coverage_blockers'] and 'foreign-legacy-secret' not in canonical(gap_items),
            'REVIEW_SOURCE_LEGACY_LEAK')
        checks.append('unowned_legacy_review_presence_blocks_complete_enumeration_without_revealing_its_contents')
        class LostAck:
            def __init__(self,actual,error):self.actual=actual;self.error=error
            def __getattr__(self,name):return getattr(self.actual,name)
            def transaction(self,*args,**kw):
                outer=self.actual.info.transaction_status==psycopg.pq.TransactionStatus.IDLE
                wrapped=self.actual.transaction(*args,**kw);error=self.error
                class Transaction:
                    def __enter__(self):return wrapped.__enter__()
                    def __exit__(self,kind,exc,tb):
                        result=wrapped.__exit__(kind,exc,tb)
                        if kind is None and outer:raise error('synthetic lost capture acknowledgement')
                        return result
                return Transaction()
        for n,error in enumerate((psycopg.OperationalError,psycopg.InterfaceError)):
            name='lost-ack-'+str(n)
            with h.target(db).connect() as victim:out=query(name,svc=service(LostAck(victim,error)))
            require(out.status=='UNKNOWN' and out.code=='REVIEW_QUEUE_CAPTURE_UNKNOWN','REVIEW_SOURCE_LOST_ACK')
            a=success(query(name));b=success(query(name));require(a==b,'REVIEW_SOURCE_ACK_REPLAY')
            require(conn.execute('SELECT count(*) FROM whattodo.review_queue_snapshot WHERE request_id=%s AND principal_id=%s',
                (name,caller.principal_id)).fetchone()==(1,),'REVIEW_SOURCE_ACK_DUPLICATE')
        checks.append('real_outer_commit_then_operational_or_interface_ack_loss_is_unknown_and_original_request_recovers_one_capture')
        barrier=Barrier(2)
        def concurrent(_):
            with h.target(db).connect() as fresh:
                barrier.wait(timeout=30);return query('simultaneous',svc=service(fresh))
        with ThreadPoolExecutor(max_workers=2) as pool:outcomes=tuple(pool.map(concurrent,range(2)))
        require(all(o.status in ('SUCCESS','RETRYABLE') for o in outcomes),'REVIEW_SOURCE_CONCURRENT_STATUS')
        replay=success(query('simultaneous'))
        require(all(o.status!='SUCCESS' or o.value==replay for o in outcomes)
            and conn.execute("SELECT count(*) FROM whattodo.review_queue_snapshot WHERE request_id='simultaneous'").fetchone()==(1,),
            'REVIEW_SOURCE_CONCURRENT_DUPLICATE')
        checks.append('simultaneous_initial_request_has_one_frozen_capture_with_safe_busy_or_serialization_retry')

    stage_support=dict(native_checks=[]);stages.verify(h,stage_support);stage_db=h._created[-1]
    report['stage_fixture_checks_not_counted']=len(stage_support['native_checks'])+len(stage_support['foundation_checks'])
    report['lifecycle_fixture_checks_not_counted']=stage_support['lifecycle_fixture_checks_not_counted']
    with h.target(stage_db,'migration').connect() as owner:apply_migrations(owner,plan,roles=roles,application_version=__version__)
    with h.target(stage_db).connect() as conn:
        svc=PostgresReviewQueueService(conn,wire,plan,application_version=__version__,clock=stages.CLOCK,cursor_key=KEY,source_scopes=(stages.SCOPE,))
        out=svc.query(canonical(ReviewQueueQuery(100,1).as_record()).encode(),RequestContext('stages','stages'),caller=stages.CALLER)
        require(out.status=='SUCCESS','REVIEW_SOURCE_STAGES_'+out.code)
        actual={i['source_ref']['id'] for i in out.value['items'] if i['kind']=='STAGE_PENDING'}
        expected={r[0] for r in conn.execute('''SELECT j.record_id FROM whattodo.stage_command_journal j WHERE j.state='PENDING'
            AND j.runtime_payload#>>'{command,principal_id}'=%s AND NOT EXISTS
            (SELECT 1 FROM whattodo.stage_pending_resolution r WHERE r.pending_ref=j.record_id)''',(stages.CALLER.principal_id,)).fetchall()}
        require(actual==expected and len(actual)>0,'REVIEW_SOURCE_STAGE_PENDING_OMITTED')
        checks.append('actual_retained_stage_intents_include_correction_and_new_obligation_without_consuming_resolved_journals')

    def generated(h,db,old_codec,base,roles,git):
        with h.target(db,'migration').connect() as owner:apply_migrations(owner,plan,roles=roles,application_version=__version__)
        with h.target(db).connect() as conn:
            defs=PostgresDefinitionRepository(conn,GitDefinitionSource(git.root),plan,roles,application_version=__version__)
            svc=PostgresReviewQueueService(conn,wire,plan,application_version=__version__,clock=generation.CLOCK,cursor_key=KEY,
                source_scopes=(generation.SCOPE,),definitions=defs)
            out=svc.query(canonical(ReviewQueueQuery(100,1).as_record()).encode(),RequestContext('generated','generated'),caller=generation.USER)
            require(out.status=='SUCCESS','REVIEW_SOURCE_GENERATION_'+out.code)
            items=out.value['items'];actual={(i['source_ref']['id'],i['source_ref']['revision']) for i in items if i['kind'] in ('GENERATION_PENDING','GENERATION_FAILED')}
            expected=set(conn.execute("SELECT generation_key,revision FROM whattodo.generation_occurrence WHERE state IN('PENDING','FAILED') AND runtime_payload IS NOT NULL").fetchall())
            require(actual==expected and len(actual)>0,'REVIEW_SOURCE_GENERATION_PENDING_OMITTED')
            require(any(i['kind']=='TASK_ESTIMATE' and i['source_ref']['id'].startswith('generated-task-') for i in items),'REVIEW_SOURCE_GENERATED_TASK_OMITTED')
            checks.append('current_pending_and_failed_generation_heads_and_generated_task_births_are_verified_against_actual_cached_rule_receipts')
    generation_support=dict(native_checks=[]);generation.verify(h,generation_support,post_verify=generated)
    report['generation_fixture_checks_not_counted']=len(generation_support['native_checks'])


def main():
    h=PostgresHarness();report=dict(task='M3B-08',status='IN_PROGRESS',scope='COMPLETE_ADMITTED_SOURCE_QUERY_PINNED_RUNTIME',native_checks=[])
    try:
        with h:verify(h,report)
        report.update(status='PASS',native_check_count=len(report['native_checks']))
    except Exception as exc:
        report.update(status='FAIL',failure_type=type(exc).__name__,failure_code=str(exc) if isinstance(exc,HarnessError) else 'REVIEW_SOURCE_NATIVE_FAILED',
            failure_sqlstate=getattr(exc,'sqlstate',None),failure_frames=[dict(file=Path(f.filename).name,function=f.name,line=f.lineno) for f in traceback.extract_tb(exc.__traceback__)])
    report['harness']=h.safe_summary();target=h.run_root/'review-sources-report.json'
    if h.run_root.exists():target.write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(dict(status=report['status'],report=str(target),checks=len(report['native_checks']),server_stopped=report['harness']['server_stopped'])))
    return 0 if report['status']=='PASS' else 1
if __name__=='__main__':raise SystemExit(main())
