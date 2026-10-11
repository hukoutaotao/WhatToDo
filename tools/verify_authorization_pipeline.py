"""Synthetic PostgreSQL command scope, references and exact-effect acceptance."""
from copy import deepcopy
from dataclasses import replace
from datetime import datetime,timedelta,timezone
import json
from pathlib import Path
import sys
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:sys.path.insert(0,str(ROOT))
from src import __version__
from src.adapters.clocks import FrozenClock
from src.adapters.contract_json import ContractJSONCodec
from src.adapters.git_definitions import GitDefinitionSource
from src.adapters.migration_files import load_migration_plan
from src.adapters.postgres_authorization import PostgresCommandService,register_grant
from src.adapters.postgres_definitions import PostgresDefinitionRepository
from src.adapters.postgres_migrations import DatabaseRoles,apply_migrations
from src.adapters.postgres_tasks import PostgresTaskRepository
from src.adapters.postgres_transactions import PostgresTransactionCoordinator
from src.application.definitions import DefinitionKey,canonical
from src.application.evidence_storage import SourceScope
from src.application.ports import AggregateKey,CommitRequest,RecordWrite,RequestContext
from src.application.task_storage import admit_storage
from src.domain.authorization import AuthorityGrant,CallerIdentity,Command,NoticeEvidence,RuleScope,change
from tools.check_contract_registry import trusted_schemas
from tools.git_definition_fixture import GitDefinitionFixture
from tools.postgres_harness import HarnessError,PostgresHarness,ROLES,require
from tools.verify_definition_repository import request as definition_request
from tools.verify_toolchain import native_transactions
from tools.verify_transactions import TABLES

NOW=datetime(2026,1,1,tzinfo=timezone.utc);CALLER=CallerIdentity('principal','USER_COMMAND',True)
SCOPES=(SourceScope('spike','scope','synthetic'),)


def verify(harness,report):
    import psycopg
    from psycopg.types.json import Jsonb
    codec=ContractJSONCodec(trusted_schemas());plan=load_migration_plan(root=ROOT);clock=FrozenClock(NOW)
    roles=DatabaseRoles(ROLES['migration'],ROLES['application'],ROLES['test'])
    checks=report['native_checks'];database=harness.create_database(initialize_schema=False)
    example=json.loads((ROOT/'tests/fixtures/task_aggregate/cases.json').read_text(encoding='utf-8'))['cases'][0]['payload']
    with harness.target(database,'migration').connect() as owner:
        apply_migrations(owner,plan,roles=roles,application_version=__version__);native_transactions(owner)

    def base(task_id,grant_id):
        v=deepcopy(example);v['core']['task_id']=v['effort']['task_id']=task_id
        v['core']['acceptance']['authority_ref']=grant_id;v['core']['title']='Trusted seed title'
        v['effort']['user_remaining']=None
        return v
    def command(command_id,task_id,expected,fields,*,origin='USER_COMMAND',scope=None):
        caller=CALLER if origin=='USER_COMMAND' else CallerIdentity('process',origin,True)
        c=Command(command_id,caller.principal_id,origin,'grant-'+command_id,
            (change(task_id,expected,'CREATE_TASK' if expected is None else
                'EXPIRE_TASK' if fields.get('disposition')=='EXPIRED' else 'UPDATE_TASK',fields),),scope)
        grant=AuthorityGrant(c.authority_ref,c.principal_id,c.origin,c.command_id,c.changes,'record',
            NOW-timedelta(minutes=1),expires_at=NOW+timedelta(hours=1),rule_scope=scope,
            essential_fields=frozenset({'title'}) if scope else frozenset())
        with harness.target(database,'migration').connect() as owner:register_grant(owner,grant,plan,application_version=__version__)
        return c,grant,caller
    def req(conn,c,v,expected):
        epoch=conn.execute('SELECT revision FROM whattodo.store_epoch').fetchone()[0]
        return CommitRequest(RequestContext(c.command_id,'correlation-'+c.command_id),c.principal_id,epoch,
            (RecordWrite(AggregateKey('TASK',v['core']['task_id']),expected,json.dumps(v)),),'audit-'+c.command_id,'record')
    def service(conn,g=None,seed=None,**kw):
        options=dict(application_version=__version__,clock=clock,grants=(g,) if g else (),
            seeds=(admit_storage(codec,json.dumps(seed).encode()),) if seed else (),source_scopes=SCOPES)
        options.update(kw);return PostgresCommandService(conn,codec,plan,**options)
    def submit(owner,c,r,caller=CALLER):return owner.commit(json.dumps(c.as_record()).encode(),r,caller=caller)
    def state(conn):return tuple(conn.execute('SELECT * FROM whattodo.'+t+' ORDER BY 1,2').fetchall() for t in TABLES+('effort_observation',))
    def deny(conn,owner,c,r,code,*,caller=CALLER,raw=None):
        before=state(conn);out=owner.commit(raw or json.dumps(c.as_record()).encode(),r,caller=caller)
        require(out.status in ('PERMANENT','CONFLICT') and out.code==code,'AUTHORITY_NEGATIVE_DIAGNOSTIC_'+out.code)
        require(state(conn)==before,'AUTHORITY_NEGATIVE_STATE_AUDIT_MUTATION');return out

    with harness.target(database).connect() as conn:
        reader=PostgresTaskRepository(conn,codec,plan,application_version=__version__,clock=clock)
        c,g,_=command('create-base','task',None,{'title':'Approved task'})
        seed=base('task',g.grant_id);value=deepcopy(seed);value['core']['title']='Approved task'
        r=req(conn,c,value,None);out=submit(service(conn,g,seed),c,r)
        require(out.status=='SUCCESS' and reader.get('task').aggregate.as_record()==value,'AUTHORITY_CREATE_WITHOUT_SECOND_APPROVAL')
        annotation=conn.execute('''SELECT a.resolved_scope->'authorization' FROM whattodo.authority_record a
            JOIN whattodo.command_transaction t ON t.authority_ref=a.authority_ref WHERE t.request_id='create-base' ''').fetchone()[0]
        require(annotation['command_fingerprint']==c.fingerprint and annotation['grant_ref']==g.grant_id,'AUTHORITY_ATOMIC_SCOPE_AUDIT')
        checks.append('resolved_explicit_creation_uses_registered_scope_trusted_seed_and_one_atomic_publication')
        before=state(conn);out=submit(service(conn,clock=FrozenClock(NOW+timedelta(days=5))),c,r)
        require(out.status=='SUCCESS' and out.code=='REPLAY' and state(conn)==before,'AUTHORITY_REPLAY_REQUIRES_NEW_APPROVAL')
        checks.append('owned_authorized_replay_survives_empty_registry_expired_grant_without_second_approval')
        changed=replace(c,changes=(change('task',None,'CREATE_TASK',{'title':'Other command meaning'}),))
        deny(conn,service(conn),changed,r,'COMMAND_AUTHORITY_REPLAY_CONFLICT')
        checks.append('changed_domain_command_cannot_borrow_receipt_of_same_concrete_request')

        c,g,_=command('patch','task',1,{'title':'Explicit correction'})
        value=reader.get('task').aggregate.as_record();value['core']['revision']=value['effort']['task_revision']=2;value['core']['title']='Explicit correction'
        r=req(conn,c,value,1);out=submit(service(conn,g),c,r)
        require(out.status=='SUCCESS' and reader.get('task').revision==2,'AUTHORITY_EXPLICIT_PATCH')
        require(reader.get('task',1).aggregate.as_record()['core']['title']=='Approved task','AUTHORITY_HISTORY_OVERWRITE')
        checks.append('explicit_title_scope_updates_exact_field_and_preserves_history')
        for origin in ('EXTERNAL',):
            deny(conn,service(conn,g),c,r,'UNTRUSTED_CALLER',caller=CallerIdentity('principal',origin,True))
        deny(conn,service(conn,g),c,r,'UNTRUSTED_CALLER',caller=CallerIdentity('principal','USER_COMMAND',False))
        checks.append('external_claimed_user_and_unauthenticated_callers_cannot_write_or_replay')

        c,g,_=command('extra-scope','task',2,{'title':'Next title'})
        value=reader.get('task').aggregate.as_record();value['core']['revision']=value['effort']['task_revision']=3;value['core']['title']='Next title'
        r=req(conn,c,value,2)
        forged=replace(c,authority_ref='authority')
        deny(conn,service(conn),forged,r,'UNREGISTERED_AUTHORITY')
        checks.append('known_database_approval_id_cannot_populate_independent_grant_registry')
        extra=replace(c,changes=(change('task',2,'UPDATE_TASK',{'title':'Next title','importance':5}),))
        deny(conn,service(conn,g),extra,r,'EXACT_CHANGE_SCOPE_MISMATCH')
        checks.append('extra_declared_field_is_rejected_against_exact_registered_changes')
        bad=deepcopy(value);bad['core']['importance']=5
        bad_request=replace(r,writes=(replace(r.writes[0],body_json=json.dumps(bad)),))
        deny(conn,service(conn,g),c,bad_request,'COMMAND_UNAUTHORIZED_EFFECT')
        bad=deepcopy(value);bad['work']['minimum_session_seconds']=1200
        bad_request=replace(r,writes=(replace(r.writes[0],body_json=json.dumps(bad)),))
        deny(conn,service(conn,g),c,bad_request,'COMMAND_UNAUTHORIZED_EFFECT')
        checks.append('complete_write_cannot_smuggle_importance_or_workload_under_title_permission')
        bad=deepcopy(value);bad['provenance']=[dict(field='/core/importance',source_ref='record')]
        deny(conn,service(conn,g),c,replace(r,writes=(replace(r.writes[0],body_json=json.dumps(bad)),)),'COMMAND_UNAUTHORIZED_PROVENANCE')
        checks.append('undeclared_provenance_change_cannot_expand_authorized_field_scope')
        deny(conn,service(conn,g,source_scopes=(SourceScope('spike','scope','different-account'),)),c,r,'AUTHORITY_SOURCE_SCOPE_REQUIRED')
        checks.append('independent_source_account_scope_must_match_registered_user_statement')
        expired=replace(g,grant_id='expired-grant',expires_at=NOW)
        expired_command=replace(c,authority_ref=expired.grant_id)
        with harness.target(database,'migration').connect() as owner:register_grant(owner,expired,plan,application_version=__version__)
        deny(conn,service(conn,expired),expired_command,r,'INACTIVE_AUTHORITY')
        checks.append('expired_registered_grant_cannot_issue_a_fresh_transaction_permit')
        unsupported=json.dumps(dict(c.as_record(),approved=True)).encode()
        deny(conn,service(conn,g),c,r,'COMMAND_SHAPE_UNSUPPORTED',raw=unsupported)
        checks.append('serialized_approval_flags_fail_strict_command_shape_before_any_authority_write')
        c,g,_=command('unknown','missing',1,{'title':'No inferred target'})
        missing=base('missing','authority');missing['core']['revision']=missing['effort']['task_revision']=2;missing['core']['title']='No inferred target'
        deny(conn,service(conn,g),c,req(conn,c,missing,1),'UNKNOWN_TARGET')
        checks.append('unknown_target_fails_without_new_task_authority_receipt_or_audit')
        c,g,_=command('stale','task',1,{'title':'Stale correction'})
        old=reader.get('task',1).aggregate.as_record();old['core']['revision']=old['effort']['task_revision']=2;old['core']['title']='Stale correction'
        deny(conn,service(conn,g),c,req(conn,c,old,1),'STALE_STATE_VERSION')
        checks.append('current_canonical_task_version_is_rechecked_before_permit_issuance')

        # Complete a real staged aggregate with exact supporting zero-U records.
        c,g,_=command('create-stage','staged',None,{'title':'Staged task'})
        seed=base('staged',g.grant_id);seed['effort']['stages']=[dict(stage_id='stage',completion='INCOMPLETE',weight=1,user_remaining=None)]
        seed['stage_details']=[dict(stage_id='stage',revision=1,title='One stage')]
        staged=deepcopy(seed);staged['core']['title']='Staged task'
        require(submit(service(conn,g,seed),c,req(conn,c,staged,None)).status=='SUCCESS','AUTHORITY_STAGED_CREATE')
        c,g,_=command('complete-stage','staged',1,{'completion':'COMPLETE'})
        with harness.target(database,'migration').connect() as owner:
            with owner.transaction():
                for oid in ('zero-parent','zero-stage'):
                    owner.execute('INSERT INTO whattodo.effort_observation VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)',
                        (oid,'staged','USER_REMAINING',0,NOW,NOW,'record',g.grant_id,None,'create-stage'))
        completed=reader.get('staged').aggregate.as_record();completed['core']['revision']=completed['effort']['task_revision']=2
        completed['core']['completion']=completed['effort']['completion']='COMPLETE'
        completed['effort']['user_remaining']=dict(seconds=0,observation_id='zero-parent',observed_at=NOW.isoformat(),verified_at=NOW.isoformat())
        completed['effort']['stages'][0]['completion']='COMPLETE';completed['effort']['stages'][0]['user_remaining']=dict(seconds=0,observation_id='zero-stage',observed_at=NOW.isoformat(),verified_at=NOW.isoformat())
        completed['stage_details'][0]['revision']=2
        require(submit(service(conn,g),c,req(conn,c,completed,1)).status=='SUCCESS','AUTHORITY_COMPLETION_CASCADE')
        require(reader.get('staged').aggregate.budget(at=NOW).seconds==0,'AUTHORITY_COMPLETION_NOT_ZERO')
        checks.append('explicit_parent_completion_binds_zero_u_and_owned_stage_effects_to_exact_observations')

        c,g,_=command('create-preview','preview',None,{'title':'Preview','requiredness':'EXPIRING','expiration_condition_ref':'class-start'})
        seed=base('preview',g.grant_id);preview=deepcopy(seed);preview['core']['title']='Preview';preview['core']['requiredness']='EXPIRING'
        preview['core']['expiration']=dict(condition_ref='class-start',notice_ref=None)
        require(submit(service(conn,g,seed),c,req(conn,c,preview,None)).status=='SUCCESS','AUTHORITY_PREVIEW_CREATE')
        detected=NOW-timedelta(seconds=10);started=NOW-timedelta(seconds=9);delivered=NOW-timedelta(seconds=5)
        with harness.target(database,'migration').connect() as owner:
            with owner.transaction():
                owner.execute('INSERT INTO whattodo.expiration_notice VALUES(%s,%s,%s,%s,%s,%s,%s)',
                    ('notice','preview',1,'class-start','record',detected,'create-preview'))
                owner.execute('INSERT INTO whattodo.dispatch_attempt VALUES(%s,%s,%s,%s,%s,%s,%s)',
                    ('notice','attempt','synthetic-channel','synthetic-content','correlation',started,'create-preview'))
        confirmation=NoticeEvidence('notice','preview',1,'class-start',True,detected,'DELIVERED',delivered)
        c,g,process=command('expire','preview',1,{'disposition':'EXPIRED','expiration_notice_ref':'notice'},origin='EXPIRATION_PROCESS')
        expired=reader.get('preview').aggregate.as_record();expired['core']['revision']=expired['effort']['task_revision']=2
        expired['core']['disposition']=expired['effort']['disposition']='EXPIRED';expired['core']['expiration']['notice_ref']='notice'
        r=req(conn,c,expired,1)
        deny(conn,service(conn,g,conditions=(confirmation,)),c,r,'CONFIRMED_NOTICE_REQUIRED',caller=process)
        checks.append('claimed_delivered_condition_cannot_replace_actual_persisted_dispatch_result')
        with harness.target(database,'migration').connect() as owner:
            owner.execute('INSERT INTO whattodo.dispatch_result VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)',
                ('result','notice','attempt',started,'DELIVERED',delivered,delivered,'record','correlation','a'*64))
        deny(conn,service(conn,g),c,r,'AUTHORITY_CONFIRMED_CONDITION_REQUIRED',caller=process)
        checks.append('delivered_database_notice_alone_cannot_confirm_an_unknown_expiration_condition')
        require(submit(service(conn,g,conditions=(confirmation,)),c,r,process).status=='SUCCESS','AUTHORITY_EXPIRE_WITH_DELIVERED_NOTICE')
        require(reader.get('preview').aggregate.as_record()['core']['disposition']=='EXPIRED' and
            reader.get('preview').aggregate.as_record()['effort']['user_remaining'] is None,'AUTHORITY_EXPIRY_REWROTE_U')
        checks.append('confirmed_condition_delivered_notice_and_current_version_authorize_expiry_without_resetting_u')

        # Rule data comes from an actual immutable Git cache; approval is separate.
        fixture=GitDefinitionFixture(harness.run_root/'git-fixture')
        values=[dict(kind='TASKTYPE',id='work',version='1',body={}),dict(kind='TASK_TEMPLATE',id='template',version='1',body={}),
            dict(kind='RELATIONSHIP_RULE',id='rule',version='1',body=dict(references=[dict(kind='TASKTYPE',id='work',version='1'),dict(kind='TASK_TEMPLATE',id='template',version='1')]))]
        files={f'{i}.json':canonical(v).encode() for i,v in enumerate(values)};commit=fixture.commit_objects(files)
        with harness.target(database,'migration').connect() as owner:
            definitions=PostgresDefinitionRepository(owner,GitDefinitionSource(fixture.root),plan,roles,application_version=__version__)
            definitions.register(tuple(definition_request(commit,f'{i}.json',v) for i,v in enumerate(values)))
            owner.execute('INSERT INTO whattodo.relationship_rule_revision(rule_id,version,active,acceptance_ref,configuration_ref,trigger_kind,source_type_ref,target_type_ref,template_ref,template_version,target_role,obligation_kind,mappings) VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)',
                ('rule','1',True,'authority',DefinitionKey('RELATIONSHIP_RULE','rule','1').configuration_ref,'CANONICAL_CREATION',
                DefinitionKey('TASKTYPE','work','1').configuration_ref,DefinitionKey('TASKTYPE','work','1').configuration_ref,
                DefinitionKey('TASK_TEMPLATE','template','1').configuration_ref,'1','counterpart','SEPARATE_TASK',Jsonb(dict(synthetic=True))))
        c,g,_=command('create-source','rule-source',None,{'title':'Rule source'})
        seed=base('rule-source',g.grant_id);seed['core']['task_type_ref']=dict(id='work',version='1')
        source=deepcopy(seed);source['core']['title']='Rule source'
        require(submit(service(conn,g,seed),c,req(conn,c,source,None)).status=='SUCCESS','AUTHORITY_RULE_SOURCE_CREATE')
        scope=RuleScope('rule','1','rule-source','create-source','occurrence','counterpart')
        c,g,process=command('rule-target','rule-target',None,{'title':'Mapped counterpart'},origin='RELATIONSHIP_RULE',scope=scope)
        seed=base('rule-target',g.grant_id);seed['core']['task_type_ref']=dict(id='work',version='1')
        target=deepcopy(seed);target['core']['title']='Mapped counterpart';r=req(conn,c,target,None)
        require(submit(service(conn,g,seed),c,r,process).status=='SUCCESS','AUTHORITY_ACCEPTED_RULE_CREATE')
        checks.append('accepted_exact_rule_git_version_type_scope_and_canonical_creation_bind_mapped_creation')
        wrong_scope=replace(scope,creation_event_ref='record')
        c,g,process=command('bad-event','bad-event',None,{'title':'Not a canonical event'},origin='RELATIONSHIP_RULE',scope=wrong_scope)
        seed=base('bad-event',g.grant_id);seed['core']['task_type_ref']=dict(id='work',version='1')
        target=deepcopy(seed);target['core']['title']='Not a canonical event'
        deny(conn,service(conn,g,seed),c,req(conn,c,target,None),'CANONICAL_CREATION_REQUIRED',caller=process)
        checks.append('raw_source_record_reference_cannot_impersonate_a_canonical_rule_creation_event')
        c,g,process=command('bad-type','bad-type',None,{'title':'Wrong mapped type'},origin='RELATIONSHIP_RULE',scope=scope)
        seed=base('bad-type',g.grant_id);target=deepcopy(seed);target['core']['title']='Wrong mapped type'
        deny(conn,service(conn,g,seed),c,req(conn,c,target,None),'AUTHORITY_RULE_TYPE_SCOPE_MISMATCH',caller=process)
        checks.append('accepted_rule_does_not_authorize_an_unrelated_target_task_type')
        unknown_version=replace(scope,version='2')
        c,g,process=command('bad-version','bad-version',None,{'title':'Unaccepted rule version'},origin='RELATIONSHIP_RULE',scope=unknown_version)
        seed=base('bad-version',g.grant_id);seed['core']['task_type_ref']=dict(id='work',version='1')
        target=deepcopy(seed);target['core']['title']='Unaccepted rule version'
        deny(conn,service(conn,g,seed),c,req(conn,c,target,None),'AUTHORITY_ACCEPTED_RULE_REQUIRED',caller=process)
        checks.append('accepted_rule_version_is_exact_and_never_substituted_with_latest_cached_version')

        c,g,_=command('read-failure','task',2,{'title':'Must not commit on read failure'})
        value=reader.get('task').aggregate.as_record();value['core']['revision']=value['effort']['task_revision']=3
        value['core']['title']='Must not commit on read failure';r=req(conn,c,value,2)
        class BrokenReference:
            def __getattr__(self,name):return getattr(conn,name)
            def execute(self,query,*args,**kw):
                if isinstance(query,str) and 'resolved_scope,issued_at,expires_at FROM whattodo.authority_record WHERE authority_ref=' in query:
                    raise psycopg.OperationalError('synthetic read-only reference disconnect')
                return conn.execute(query,*args,**kw)
        before=state(conn);out=submit(service(BrokenReference(),g),c,r)
        require(out.status=='RETRYABLE' and out.code=='COMMAND_REFERENCES_UNAVAILABLE'
            and state(conn)==before,'AUTHORITY_READ_FAILURE_RETRY_WITHOUT_MUTATION')
        checks.append('read_only_reference_connection_failure_is_retryable_without_a_false_committed_result')

        c,g,_=command('race-loser','task',2,{'title':'Must not overwrite concurrent winner'})
        value=reader.get('task').aggregate.as_record();value['core']['revision']=value['effort']['task_revision']=3
        value['core']['title']='Must not overwrite concurrent winner';r=req(conn,c,value,2)
        winner,winner_grant,_=command('race-winner','task',2,{'title':'Concurrent winner'})
        winner_value=deepcopy(value);winner_value['core']['title']='Concurrent winner'
        winner_request=req(conn,winner,winner_value,2);after_winner=[]
        class AdvanceAfterValidation(PostgresTransactionCoordinator):
            def commit(self,request,**kw):
                if request.context.request_id=='race-loser':
                    with harness.target(database).connect() as other:
                        require(submit(service(other,winner_grant),winner,winner_request).status=='SUCCESS',
                            'AUTHORITY_RACE_WINNER_COMMIT')
                    after_winner.append(state(conn))
                return super().commit(request,**kw)
        with patch('src.adapters.postgres_authorization.PostgresTransactionCoordinator',AdvanceAfterValidation):
            out=submit(service(conn,g),c,r)
        require(out.status=='CONFLICT' and out.code=='STALE_STORE_REVISION' and
            state(conn)==after_winner[0] and reader.get('task').aggregate.as_record()['core']['title']=='Concurrent winner',
            'AUTHORITY_REFERENCE_TO_PUBLICATION_RACE')
        require(conn.execute("SELECT 1 FROM whattodo.command_transaction WHERE request_id='race-loser'").fetchone() is None,
            'AUTHORITY_RACE_LOSER_LEFT_RECEIPT')
        checks.append('concurrent_change_after_scope_validation_rejects_stale_publication_without_audit_or_receipt')
        expected=reader.get('task')
    with harness.target(database).connect() as fresh:
        read=PostgresTaskRepository(fresh,codec,plan,application_version=__version__,clock=clock)
        require(read.get('task')==expected,'AUTHORITY_FRESH_HISTORY')
        checks.append('fresh_connection_retains_authorized_task_and_complete_scope_audit_history')


def main():
    harness=PostgresHarness();report=dict(task='M3A-11',status='IN_PROGRESS',scope='SYNTHETIC_COMMAND_AUTHORITY_PIPELINE',verified_on='2026-10-10',native_checks=[])
    try:
        with harness:verify(harness,report)
        report.update(status='PASS',native_check_count=len(report['native_checks']),limitations=[
            'Independent grants/seeds/condition confirmations supplied by trusted synthetic resolvers',
            'Synthetic dispatch rows only; no user message was delivered',
            'Manual intent parser/handlers and full lifecycle/generation services remain their separate cards',
            'Current frozen command fields only; no live course/account/transport or deployment activation'])
    except Exception as exc:
        report.update(status='FAIL',failure_type=type(exc).__name__,failure_code=str(exc) if isinstance(exc,HarnessError) else 'AUTHORITY_NATIVE_CHECK_FAILED',failure_sqlstate=getattr(exc,'sqlstate',None))
    report['harness']=harness.safe_summary();target=harness.run_root/'authorization-report.json'
    if harness.run_root.exists():target.write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(dict(status=report['status'],report=str(target),checks=len(report['native_checks']),server_stopped=report['harness']['server_stopped'])))
    return 0 if report['status']=='PASS' else 1


if __name__=='__main__':raise SystemExit(main())
