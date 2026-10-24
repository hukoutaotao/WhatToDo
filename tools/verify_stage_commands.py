"""Native scoped stage-command entrypoint on the activated pinned test schema."""
from contextlib import contextmanager
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from datetime import timedelta
import json
from pathlib import Path
import sys
from threading import Barrier

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path: sys.path.insert(0,str(ROOT))
from src import __version__
from src.adapters.clocks import FrozenClock
from src.adapters.contract_json import ContractJSONCodec
from src.adapters.extension_contracts import load_supported_schemas
from src.adapters.postgres_evidence import PostgresEvidenceRepository, register_source_scope
from src.adapters.postgres_migrations import DatabaseRoles, schema_checked_transaction
from src.adapters.postgres_relationships import PostgresRelationshipRepository
from src.adapters.postgres_stage_commands import PostgresStageCommandHandler, register_stage_command_grant
from src.adapters.postgres_tasks import PostgresTaskRepository
from src.application.definitions import canonical
from src.application.evidence_storage import SourceScope
from src.application.ports import RequestContext, AggregateKey, CommitRequest, CommitReceipt, RecordWrite
from src.application.relationship_storage import EndpointBinding, RelationStorageRecord, acceptance_scope
from src.application.stage_commands import StageCommand, StageCommandGrant
from src.application.stage_commit import digest
from src.domain.authorization import CallerIdentity
from src.domain.provenance import capture_source
from src.domain.relationships import Endpoint, TaskRelation
from tools.postgres_harness import PostgresHarness, HarnessError, ROLES, require
from tools import verify_stage_commit as foundation

NOW=foundation.NOW; CLOCK=foundation.CLOCK; CALLER=foundation.CALLER; SCOPE=foundation.SCOPE


def verify(h,report):
    import psycopg
    from psycopg import sql
    from psycopg.types.json import Jsonb
    support=dict(native_checks=[]); foundation.verify(h,support)
    report['foundation_checks_not_counted']=len(support['native_checks'])
    report['foundation_checks']=support['native_checks']
    report['lifecycle_fixture_checks_not_counted']=support['fixture_native_check_count']
    database=h._created[-1]; full=foundation.candidate_plan(); plan=replace(full,steps=full.steps[:19]); roles=DatabaseRoles(ROLES['migration'],ROLES['application'],ROLES['test'])
    codec=ContractJSONCodec(load_supported_schemas(root=ROOT)); checks=report['native_checks']
    foreign_scope=SourceScope('synthetic-stage-foreign','scope','foreign-account')
    with h.target(database,'migration').connect() as owner:
        register_source_scope(owner,plan,roles,foreign_scope,application_version=__version__,clock=CLOCK)
    with h.target(database).connect() as conn:
        reader=PostgresTaskRepository(conn,codec,plan,application_version=__version__,clock=CLOCK)
        def epoch():return conn.execute('SELECT revision FROM whattodo.store_epoch').fetchone()[0]
        def state():
            return tuple(conn.execute(sql.SQL('SELECT * FROM whattodo.{} ORDER BY 1,2').format(sql.Identifier(t))).fetchall()
                for t in ('task_revision','stage_revision','task_head','task_payload_revision','stage_command_journal','stage_relationship_issue',
                    'stage_pending_resolution','effort_observation','authority_record','command_transaction','audit_entry','audit_change','store_epoch'))
        def source(name,raw,scope=SCOPE):
            s=capture_source(provider=scope.provider,scope_ref=scope.scope_ref,external_id=name,raw_bytes=raw,
                captured_at=NOW-timedelta(minutes=1),source_type='USER')
            PostgresEvidenceRepository(conn,codec,plan,application_version=__version__,clock=CLOCK,scopes=(scope,)).observe_source(
                canonical(s.as_record()).encode(),raw_content=raw,locator_ref='synthetic-'+name)
            return s
        def setup(name,*,operation='REWORK',fields=None,principal=CALLER.principal_id,scope=SCOPE):
            before=reader.get('staged');value=before.aggregate.as_record()
            revision=next(d['revision'] for d in value['stage_details'] if d['stage_id']=='staged-stage-0')
            c=StageCommand(name,principal,'stage-root-'+name,'staged',before.revision,'staged-stage-0',revision,
                operation,canonical(fields or dict(intent='SAME_OBLIGATION',parent_remaining_seconds=900)))
            raw=canonical(c.as_record()).encode();s=source(name,raw,scope)
            grant=StageCommandGrant(c,s.record_id,NOW-timedelta(minutes=2),s.captured_at,NOW+timedelta(hours=1))
            with h.target(database,'migration').connect() as owner:
                register_stage_command_grant(owner,grant,plan,application_version=__version__)
            return c,grant,raw,epoch()
        def handler(grants=(),*,connection=conn,scopes=(SCOPE,),clock=CLOCK):
            return PostgresStageCommandHandler(connection,codec,plan,application_version=__version__,clock=clock,grants=grants,source_scopes=scopes)
        def execute(setup_value,*,service=None,caller=CALLER):
            c,g,raw,store=setup_value
            return (service or handler((g,))).execute(raw,RequestContext(c.command_id,'native-stage-entry'),
                expected_store_revision=store,audit_id='audit-'+c.command_id,caller=caller)
        def reject(value,expected,**kwargs):
            baseline=state();result=execute(value,**kwargs)
            require(result.status in ('PERMANENT','CONFLICT','RETRYABLE') and result.code==expected,'STAGE_ENTRY_REJECT_'+result.code)
            require(state()==baseline,'STAGE_ENTRY_REJECTION_MUTATED')

        complete=setup('entry-first-complete',operation='COMPLETE',fields=dict(intent='SAME_OBLIGATION',completed_at=NOW.isoformat()))
        result=execute(complete)
        require(result.code=='STAGE_COMMAND_COMMITTED','STAGE_ENTRY_COMPLETE_'+result.code)
        require(result.value.state=='COMMITTED' and reader.get('staged').aggregate.as_record()['core']['completion']=='INCOMPLETE',
            'STAGE_ENTRY_COMPLETION_PARENT')
        checks.append('real_entrypoint_resolves_actual_parent_and_stage_and_commits_truthful_stage_completion')

        ambiguous=setup('entry-ambiguous',fields=dict(intent='UNRESOLVED'))
        before=reader.get('staged');pending=execute(ambiguous)
        require(pending.code=='STAGE_COMMAND_PENDING' and pending.value.journal.code=='STAGE_INTENT_UNRESOLVED'
            and reader.get('staged')==before,'STAGE_ENTRY_PENDING_'+pending.code)
        checks.append('independently_registered_ambiguous_instruction_commits_only_lossless_pending_metadata')
        deferred=[]
        for name,intent in (('entry-correction','CORRECTION'),('entry-new-obligation','NEW_OBLIGATION')):
            value=setup(name,fields=dict(intent=intent));out=execute(value)
            require(out.code=='STAGE_COMMAND_PENDING','STAGE_ENTRY_KNOWN_INTENT_'+out.code)
            deferred.append(out.value.journal.record_id)
        unauthorized=setup('entry-no-injected-grant')
        reject(unauthorized,'STAGE_INDEPENDENT_GRANT_REQUIRED',service=handler())
        wrong=replace(unauthorized[1],command=replace(unauthorized[0],stage_id='foreign-stage'))
        reject(unauthorized,'STAGE_INDEPENDENT_GRANT_REQUIRED',service=handler((wrong,)))
        checks.append('stored_row_or_supplied_command_cannot_replace_independently_injected_exact_grant')
        intruder=CallerIdentity('intruder','USER_COMMAND',True)
        foreign=setup('entry-foreign-principal',principal=intruder.principal_id)
        reject(foreign,'STAGE_PARENT_NOT_OWNED',caller=intruder)
        checks.append('fresh_accepted_intruder_grant_cannot_modify_a_task_owned_by_another_birth_principal')
        foreign=setup('entry-foreign-source',scope=foreign_scope)
        reject(foreign,'EVIDENCE_SOURCE_SCOPE_NOT_AUTHORIZED')
        reject(foreign,'EVIDENCE_SOURCE_SCOPE_NOT_AUTHORIZED',service=handler((foreign[1],),scopes=(foreign_scope,)))
        checks.append('foreign_grant_source_and_owned_grant_targeting_an_unregistered_task_birth_account_both_fail_without_effects')

        reopen=setup('entry-reopen');before=reader.get('staged');result=execute(reopen)
        require(result.code=='STAGE_COMMAND_COMMITTED' and result.value.journal.transition['previous_stage_completed_at']==NOW.isoformat()
            and reader.get('staged',before.revision)==before,'STAGE_ENTRY_REOPEN_'+result.code)
        checks.append('rework_uses_current_historical_execution_pins_and_preserves_original_completion_history')
        require(conn.execute('SELECT pending_ref FROM whattodo.stage_pending_resolution WHERE transition_ref=%s',
            (result.value.journal.record_id,)).fetchall()==[(pending.value.journal.record_id,)]
            and conn.execute('SELECT count(*) FROM whattodo.stage_pending_resolution WHERE pending_ref=ANY(%s)',(deferred,)).fetchone()==(0,),
            'STAGE_ENTRY_PENDING_RESOLUTION')
        checks.append('fresh_same_obligation_instruction_resolves_matching_pending_but_preserves_correction_and_new_obligation_routes')
        baseline=state();c,g,raw,store=reopen
        expired=handler(clock=FrozenClock(NOW+timedelta(days=2)))
        replay=expired.execute(json.dumps(c.as_record(),indent=2).encode(),RequestContext(c.command_id,'different-trace'),
            expected_store_revision=store,audit_id='audit-'+c.command_id,caller=CALLER)
        require(replay.code=='STAGE_COMMAND_REPLAYED' and replay.value.receipt==result.value.receipt and state()==baseline,
            'STAGE_ENTRY_EXPIRED_REPLAY_'+replay.code)
        altered=replace(c,fields_json=canonical(dict(intent='SAME_OBLIGATION',parent_remaining_seconds=1800)))
        denied=handler().lookup(canonical(altered.as_record()).encode(),RequestContext(c.command_id,'changed'),caller=CALLER)
        require(denied.code=='STAGE_REPLAY_SCOPE_CONFLICT' and state()==baseline,'STAGE_ENTRY_CHANGED_REPLAY')
        checks.append('original_receipt_replays_after_expired_grants_new_trace_and_wire_whitespace_but_changed_content_conflicts')

        # One accepted actual hard relation, with full audit/receipt fingerprint.
        before=reader.get('staged');prereq=reader.get('cancel-task');sid=next(d['revision'] for d in before.aggregate.as_record()['stage_details'] if d['stage_id']=='staged-stage-0')
        require(prereq.aggregate.as_record()['core']['completion']=='INCOMPLETE','STAGE_PREREQUISITE_FIXTURE_MUST_BE_INCOMPLETE')
        rel=RelationStorageRecord(TaskRelation('entry-hard-order',1,'COMPLETION_ORDER',Endpoint('TASK',prereq.task_id),
            Endpoint('STAGE','staged-stage-0'),'entry-relation-root'),EndpointBinding(Endpoint('TASK',prereq.task_id),prereq.task_id,prereq.revision),
            EndpointBinding(Endpoint('STAGE','staged-stage-0'),'staged',before.revision,sid))
        evidence=source('entry-hard-order',canonical(rel.payload).encode());scope=acceptance_scope('RELATION',rel)
        with h.target(database,'migration').connect() as owner:
            owner.execute('INSERT INTO whattodo.authority_record VALUES(%s,%s,%s,%s,%s,%s,%s,%s)',
                (rel.relation.authority_ref,CALLER.principal_id,'USER_COMMAND',evidence.record_id,digest(scope),Jsonb(scope),NOW-timedelta(minutes=2),NOW+timedelta(hours=1)))
        request=CommitRequest(RequestContext('entry-create-order','native-order'),CALLER.principal_id,epoch(),
            (RecordWrite(AggregateKey('TASK_RELATION',rel.relation.relation_id),None,canonical(rel.payload)),),'audit-entry-create-order',evidence.record_id)
        from dataclasses import asdict
        receipt=CommitReceipt(request.context.request_id,request.fingerprint,request.expected_store_revision+1,request.audit_id,(request.writes[0].key,))
        with h.target(database,'migration').connect() as relation_owner, schema_checked_transaction(
                relation_owner,plan,application_version=__version__,read_only=False):
            relation_owner.execute('INSERT INTO whattodo.command_transaction VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)',
                (request.context.request_id,request.fingerprint,CALLER.principal_id,'USER_COMMAND',rel.relation.authority_ref,
                    request.expected_store_revision,receipt.store_revision,request.audit_id,NOW,Jsonb(asdict(receipt))))
            relation_owner.execute('INSERT INTO whattodo.audit_entry VALUES(%s,%s,%s,%s,%s)',(request.audit_id,request.context.request_id,evidence.record_id,'native-order',NOW))
            relation_owner.execute('INSERT INTO whattodo.audit_change VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s)',
                ('change-entry-create-order',request.audit_id,'TASK_RELATION',rel.relation.relation_id,None,1,None,Jsonb(rel.payload),request.context.request_id))
            PostgresRelationshipRepository(relation_owner,plan,roles,application_version=__version__,caller=CALLER,source_scopes=(SCOPE,),clock=CLOCK).append_relation_in_transaction(rel,request.context.request_id)
            relation_owner.execute('UPDATE whattodo.store_epoch SET revision=%s,last_transaction_ref=%s WHERE singleton=TRUE',(receipt.store_revision,receipt.request_id))
        complete2=setup('entry-out-of-order',operation='COMPLETE',fields=dict(intent='SAME_OBLIGATION',completed_at=NOW.isoformat()))
        result=execute(complete2)
        require(result.code=='STAGE_COMMAND_COMMITTED','STAGE_ENTRY_ORDER_'+result.code)
        require(reader.get(prereq.task_id)==prereq and result.value.journal.transition['issues']==[
            dict(code='PREREQUISITE_INCOMPLETE',relation_id=rel.relation.relation_id,relation_revision=1,kind='COMPLETION_ORDER')]
            and conn.execute('SELECT code FROM whattodo.stage_relationship_issue WHERE transition_ref=%s',(result.value.journal.record_id,)).fetchall()==[('PREREQUISITE_INCOMPLETE',)],
            'STAGE_ENTRY_TRUTHFUL_ORDER')
        checks.append('independently_resolved_current_accepted_hard_relation_publishes_truth_and_audited_issue_without_completing_prerequisite')
        require(handler().lookup(complete2[2],RequestContext(complete2[0].command_id,'lookup-order'),caller=CALLER).code=='STAGE_COMMAND_REPLAYED',
            'STAGE_ENTRY_ORDER_REPLAY')
        checks.append('order_receipt_reconstructs_historical_task_relation_execution_and_issue_effects')
        require(handler().lookup(reopen[2],RequestContext(reopen[0].command_id,'after-new-order'),caller=CALLER).code=='STAGE_COMMAND_REPLAYED',
            'STAGE_ENTRY_REPLAY_CHANGED_GRAPH')
        checks.append('newly_added_relationships_and_later_completion_do_not_rewrite_an_original_rework_receipt')

        class Proxy:
            def __init__(self,actual):self.actual=actual
            def __getattr__(self,k):return getattr(self.actual,k)
        class LostAcknowledgement(Proxy):
            def __init__(self,actual,error_type=psycopg.OperationalError):super().__init__(actual);self.ordinal=0;self.reached=False;self.error_type=error_type
            @contextmanager
            def transaction(self,*args,**kwargs):
                self.ordinal+=1;outer=self.ordinal==1
                with self.actual.transaction(*args,**kwargs) as tx:yield tx
                if outer:
                    self.reached=True
                    raise self.error_type('synthetic acknowledged connection loss after real COMMIT')
        class DisconnectAfterJournal(Proxy):
            reached=False
            def execute(self,statement,*args,**kwargs):
                text=statement.as_string(self.actual) if hasattr(statement,'as_string') else statement
                result=self.actual.execute(statement,*args,**kwargs)
                if text.startswith('INSERT INTO whattodo.stage_command_journal'):
                    self.reached=True;self.actual.close()
                return result
        broken=setup('entry-real-close');baseline=state()
        with h.target(database).connect() as victim:
            proxy=DisconnectAfterJournal(victim)
            retry=execute(broken,service=handler((broken[1],),connection=proxy))
            require(proxy.reached and victim.closed and retry.status=='RETRYABLE','STAGE_ENTRY_REAL_CLOSE_'+retry.code)
        require(state()==baseline,'STAGE_ENTRY_REAL_CLOSE_LEAKED')
        require(execute(broken).code=='STAGE_COMMAND_COMMITTED','STAGE_ENTRY_REAL_CLOSE_RETRY')
        checks.append('real_precommit_connection_close_rolls_back_every_effect_and_original_command_retries_once')
        require(execute(setup('entry-after-close-complete',operation='COMPLETE',fields=dict(intent='SAME_OBLIGATION',completed_at=NOW.isoformat()))).code=='STAGE_COMMAND_COMMITTED',
            'STAGE_ENTRY_RACE_FIXTURE')
        rivals=[setup('entry-race-'+name) for name in ('one','two')];before_race=reader.get('staged');before_epoch=epoch();barrier=Barrier(2)
        targets=[h.target(database),h.target(database)]
        class RaceConnection(Proxy):
            def execute(self,statement,*args,**kwargs):
                text=statement.as_string(self.actual) if hasattr(statement,'as_string') else statement
                if text.startswith('SELECT revision FROM whattodo.store_epoch WHERE singleton=TRUE FOR UPDATE NOWAIT'):barrier.wait(timeout=20)
                return self.actual.execute(statement,*args,**kwargs)
        def race(index):
            with targets[index].connect() as separate:
                return execute(rivals[index],service=handler((rivals[index][1],),connection=RaceConnection(separate)))
        with ThreadPoolExecutor(max_workers=2) as pool:results=tuple(pool.map(race,range(2)))
        require(sum(r.code=='STAGE_COMMAND_COMMITTED' for r in results)==1 and sum(r.status=='RETRYABLE' for r in results)==1
            and epoch()==before_epoch+1 and reader.get('staged').revision==before_race.revision+1,'STAGE_ENTRY_CONCURRENT_CAS')
        checks.append('two_real_entrypoints_publish_one_parent_stage_change_and_return_retryable_for_the_concurrent_loser')
        require(execute(setup('entry-after-race-complete',operation='COMPLETE',fields=dict(intent='SAME_OBLIGATION',completed_at=NOW.isoformat()))).code=='STAGE_COMMAND_COMMITTED',
            'STAGE_ENTRY_LOST_ACK_FIXTURE')
        lost=setup('entry-lost-ack')
        with h.target(database).connect() as victim:
            proxy=LostAcknowledgement(victim)
            unknown=execute(lost,service=handler((lost[1],),connection=proxy))
            require(proxy.reached and unknown.status=='UNKNOWN' and unknown.code=='STAGE_ACKNOWLEDGEMENT_LOST',
                'STAGE_ENTRY_LOST_ACK_'+unknown.code)
        with h.target(database).connect() as fresh:
            found=handler(connection=fresh).lookup(lost[2],RequestContext(lost[0].command_id,'fresh-reconcile'),caller=CALLER)
            require(found.code=='STAGE_COMMAND_REPLAYED' and found.value.state=='COMMITTED','STAGE_ENTRY_LOST_ACK_LOOKUP_'+found.code)
        require(conn.execute('SELECT count(*) FROM whattodo.command_transaction WHERE request_id=%s',(lost[0].command_id,)).fetchone()==(1,),
            'STAGE_ENTRY_LOST_ACK_DUPLICATE')
        checks.append('real_successful_commit_with_lost_ack_returns_unknown_and_fresh_lookup_recovers_original_effect_once')
        require(execute(setup('entry-before-interface-complete',operation='COMPLETE',fields=dict(intent='SAME_OBLIGATION',completed_at=NOW.isoformat()))).code=='STAGE_COMMAND_COMMITTED',
            'STAGE_ENTRY_INTERFACE_FIXTURE')
        interface=setup('entry-interface-ack')
        with h.target(database).connect() as victim:
            proxy=LostAcknowledgement(victim,psycopg.InterfaceError)
            unknown=execute(interface,service=handler((interface[1],),connection=proxy))
            require(proxy.reached and unknown.status=='UNKNOWN','STAGE_ENTRY_INTERFACE_ACK_'+unknown.code)
        baseline=state();replayed=execute(interface,service=handler())
        require(replayed.code=='STAGE_COMMAND_REPLAYED' and state()==baseline,'STAGE_ENTRY_INTERFACE_REPLAY_'+replayed.code)
        checks.append('interface_commit_ack_loss_is_unknown_and_original_execute_replays_without_current_grants_or_duplicate_effects')
        report.update(schema_version=plan.schema_version,migration_steps=len(plan.steps),
            domain_tables=conn.execute("SELECT count(*) FROM pg_tables WHERE schemaname='whattodo'").fetchone()[0],
            domain_foreign_keys=conn.execute("SELECT count(*) FROM pg_constraint c JOIN pg_namespace n ON n.oid=c.connamespace WHERE n.nspname='whattodo' AND c.contype='f'").fetchone()[0])


def main():
    h=PostgresHarness();report=dict(task='M3B-07.b',status='IN_PROGRESS',scope='SYNTHETIC_SCOPED_STAGE_COMMAND_RUNTIME',native_checks=[])
    try:
        with h:verify(h,report)
        report.update(status='PASS',native_check_count=len(report['native_checks']),limitations=[
            'Unified CI and parent acceptance are recorded separately; generated endpoints have a separate native verifier',
            'No personal/provider/model/n8n/deployment activation'])
    except Exception as exc:
        report.update(status='FAIL',failure_type=type(exc).__name__,failure_code=str(exc) if isinstance(exc,HarnessError) else 'STAGE_ENTRY_NATIVE_FAILED',
            failure_sqlstate=getattr(exc,'sqlstate',None))
    report['harness']=h.safe_summary();path=h.run_root/'stage-commands-report.json'
    if h.run_root.exists():path.write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(dict(status=report['status'],report=str(path),checks=len(report['native_checks']),server_stopped=report['harness']['server_stopped'])))
    return 0 if report['status']=='PASS' else 1


if __name__=='__main__':raise SystemExit(main())
