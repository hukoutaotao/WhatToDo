"""Stage commands on real rule-generated stages and generated Task parents."""
from dataclasses import replace
from pathlib import Path
import json,sys
ROOT=Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:sys.path.insert(0,str(ROOT))
from src import __version__
from src.adapters.git_definitions import GitDefinitionSource
from src.adapters.postgres_definitions import PostgresDefinitionRepository
from src.adapters.postgres_evidence import PostgresEvidenceRepository
from src.adapters.postgres_generation import PostgresGenerationHandler
from src.adapters.postgres_migrations import apply_migrations
from src.adapters.postgres_relationships import PostgresRelationshipRepository,rule_from_payload
from src.adapters.postgres_stage_commands import PostgresStageCommandHandler,register_stage_command_grant
from src.adapters.postgres_tasks import PostgresTaskRepository
from src.application.definitions import DefinitionError,DefinitionKey,GitDefinitionRequest,canonical
from src.application.generation_runtime import GenerationPolicy
from src.application.ports import RequestContext
from src.application.relationship_storage import acceptance_scope
from src.application.stage_commands import StageCommand,StageCommandGrant
from src.application.stage_commit import digest
from src.domain.provenance import capture_source
from tools.postgres_harness import PostgresHarness,HarnessError,require
from tools.verify_stage_commit import candidate_plan
from tools import verify_generation_runtime as fixtures


def verify(h,report):
    support=dict(native_checks=[]);checks=report['native_checks']
    def stage_checks(h,db,codec,base,roles,git):
        from psycopg.types.json import Jsonb
        plan=candidate_plan();now=fixtures.NOW;clock=fixtures.CLOCK;caller=fixtures.USER;scope=fixtures.SCOPE
        with h.target(db,'migration').connect() as owner:apply_migrations(owner,plan,roles=roles,application_version=__version__)
        with h.target(db).connect() as conn:
            defs=PostgresDefinitionRepository(conn,GitDefinitionSource(git.root),plan,roles,application_version=__version__)
            reader=PostgresTaskRepository(conn,codec,plan,application_version=__version__,clock=clock)
            def source(name,raw):
                s=capture_source(provider=scope.provider,scope_ref=scope.scope_ref,external_id=name,raw_bytes=raw,captured_at=now,source_type='USER')
                PostgresEvidenceRepository(conn,codec,plan,application_version=__version__,clock=clock,scopes=(scope,)).observe_source(
                    canonical(s.as_record()).encode(),raw_content=raw,locator_ref='synthetic-'+name)
                return s
            def stage_cycle(name,task_id,stage_id):
                for operation in ('COMPLETE','REWORK'):
                    before=reader.get(task_id);detail=next(d for d in before.aggregate.as_record()['stage_details'] if d['stage_id']==stage_id)
                    fields=dict(intent='SAME_OBLIGATION',completed_at=now.isoformat()) if operation=='COMPLETE' else dict(intent='SAME_OBLIGATION',parent_remaining_seconds=450)
                    c=StageCommand(name+'-'+operation,caller.principal_id,name+'-root-'+operation,task_id,before.revision,stage_id,detail['revision'],operation,canonical(fields))
                    raw=canonical(c.as_record()).encode();s=source(c.command_id,raw);grant=StageCommandGrant(c,s.record_id,now,s.captured_at)
                    with h.target(db,'migration').connect() as owner:register_stage_command_grant(owner,grant,plan,application_version=__version__)
                    service=PostgresStageCommandHandler(conn,codec,plan,application_version=__version__,clock=clock,grants=(grant,),source_scopes=(scope,),definitions=defs)
                    result=service.execute(raw,RequestContext(c.command_id,'generated-stage'),
                        expected_store_revision=conn.execute('SELECT revision FROM whattodo.store_epoch').fetchone()[0],audit_id='audit-'+c.command_id,caller=caller)
                    require(result.code=='STAGE_COMMAND_COMMITTED','STAGE_GENERATED_'+operation+'_'+result.code)
                    require(reader.get(task_id,before.revision)==before,'STAGE_GENERATED_HISTORY')
                    after=reader.get(task_id).aggregate.as_record()
                    require(after['work']==before.aggregate.as_record()['work'],'STAGE_GENERATED_CHANGED_ACTUAL_WORK')
                    if operation=='REWORK':
                        require(after['core']['completion']=='INCOMPLETE' and after['effort']['user_remaining']['seconds']==450
                            and next(s for s in after['effort']['stages'] if s['stage_id']==stage_id)['user_remaining'] is None
                            and conn.execute('SELECT task_id,seconds FROM whattodo.effort_observation WHERE transaction_ref=%s',
                                (c.command_id,)).fetchall()==[(task_id,450)],'STAGE_GENERATED_BUDGET_OWNER')
                    replay=PostgresStageCommandHandler(conn,codec,plan,application_version=__version__,clock=clock,source_scopes=(scope,),definitions=defs).lookup(
                        raw,RequestContext(c.command_id,'generated-stage-replay'),caller=caller)
                    require(replay.code=='STAGE_COMMAND_REPLAYED' and replay.value.receipt==result.value.receipt,'STAGE_GENERATED_REPLAY_'+replay.code)

            chosen=conn.execute('''SELECT s.task_id,s.stage_id FROM whattodo.stage_identity s JOIN whattodo.command_transaction c ON c.request_id=s.transaction_ref
                JOIN whattodo.task_head h ON h.task_id=s.task_id JOIN whattodo.task_revision t ON(t.task_id,t.revision)=(h.task_id,h.revision)
                JOIN whattodo.task_identity i ON i.task_id=s.task_id JOIN whattodo.command_transaction birth ON birth.request_id=i.transaction_ref
                WHERE c.origin='RELATIONSHIP_RULE' AND birth.origin='USER_COMMAND' AND t.disposition='ACTIVE' AND t.completion='INCOMPLETE'
                ORDER BY s.stage_id LIMIT 1''').fetchone()
            require(chosen is not None,'STAGE_GENERATED_STAGE_FIXTURE')
            stage_cycle('real-generated-stage',*chosen)
            checks.append('actual_rule_generated_stage_under_manual_parent_completes_reopens_and_replays_with_original_parent_budget_ownership')

            stored=conn.execute("SELECT runtime_payload FROM whattodo.relationship_rule_revision WHERE rule_id='stage' AND version='1'").fetchone()[0]
            base_rule=rule_from_payload(stored)
            rule=replace(base_rule,source_type=DefinitionKey('TASKTYPE','target-type','1'),target_type=DefinitionKey('TASKTYPE','source-type','1'),rule=replace(base_rule.rule,
                rule_id='stage-on-generated',acceptance_ref='stage-on-generated-root',source_type_ref='target-type',target_type_ref='source-type'))
            envelope=dict(kind=rule.key.kind,id=rule.key.id,version=rule.key.version,body=rule.payload)
            raw=canonical(envelope).encode();commit=git.commit_objects({'stage-on-generated.json':raw})
            s=source('accept-stage-on-generated',canonical(rule.payload).encode());accept=acceptance_scope('RULE',rule)
            with h.target(db,'migration').connect() as owner:
                PostgresDefinitionRepository(owner,GitDefinitionSource(git.root),plan,roles,application_version=__version__).register(
                    (GitDefinitionRequest(commit,'stage-on-generated.json',digest(envelope)),))
                owner.execute('INSERT INTO whattodo.authority_record VALUES(%s,%s,%s,%s,%s,%s,%s,%s)',
                    (rule.rule.acceptance_ref,caller.principal_id,'USER_COMMAND',s.record_id,digest(accept),Jsonb(accept),now,None))
                PostgresRelationshipRepository(owner,plan,roles,application_version=__version__,caller=caller,source_scopes=(scope,),clock=clock).register_rule(rule)
            target=conn.execute('''SELECT e.event_id,h.task_id FROM whattodo.task_head h JOIN whattodo.task_revision t ON(t.task_id,t.revision)=(h.task_id,h.revision)
                JOIN whattodo.task_identity i ON i.task_id=h.task_id JOIN whattodo.command_transaction c ON c.request_id=i.transaction_ref
                JOIN whattodo.canonical_creation_event e ON e.task_id=h.task_id
                JOIN whattodo.task_payload_revision p ON(p.task_id,p.task_revision)=(h.task_id,h.revision)
                WHERE c.origin='RELATIONSHIP_RULE' AND t.disposition='ACTIVE' AND t.completion='INCOMPLETE'
                AND convert_from(p.raw_bytes,'UTF8')::jsonb#>>'{core,task_type_ref,id}'='target-type' ORDER BY h.task_id LIMIT 1''').fetchone()
            require(target is not None,'STAGE_GENERATED_PARENT_FIXTURE')
            result=PostgresGenerationHandler(conn,codec,plan,application_version=__version__,clock=clock,
                policy=GenerationPolicy(caller.principal_id,(rule.key,),(scope,)),definitions=defs).generate(
                    target[0],rule.rule.rule_id,correlation_ref='stage-on-generated',caller=fixtures.WORKER)
            require(result.code=='GENERATION_COMMITTED' and result.value.state=='CREATED','STAGE_GENERATED_PARENT_STAGE_'+result.code)
            stage_cycle('real-generated-parent',target[1],result.value.occurrence.target_stage_ref)
            checks.append('generated_task_birth_receipt_and_exact_rule_definition_ancestry_are_verified_before_stage_mutation_and_replay')
    fixtures.verify(h,support,post_verify=stage_checks)
    report['generation_fixture_checks_not_counted']=len(support['native_checks'])
    report['generation_fixture_checks']=support['native_checks']


def main():
    h=PostgresHarness();report=dict(task='M3B-07.b',status='IN_PROGRESS',scope='SYNTHETIC_ACTUAL_GENERATED_TASK_AND_STAGE_ENDPOINTS',native_checks=[])
    try:
        with h:verify(h,report)
        report.update(status='PASS',native_check_count=len(report['native_checks']),limitations=['Isolated pinned-schema runtime; unified acceptance is recorded separately','No live generation or personal activation'])
    except Exception as exc:
        report.update(status='FAIL',failure_type=type(exc).__name__,failure_code=str(exc) if isinstance(exc,(HarnessError,DefinitionError)) else 'STAGE_GENERATED_NATIVE_FAILED',failure_sqlstate=getattr(exc,'sqlstate',None))
    report['harness']=h.safe_summary();path=h.run_root/'stage-generated-report.json'
    if h.run_root.exists():path.write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(dict(status=report['status'],report=str(path),checks=len(report['native_checks']),server_stopped=report['harness']['server_stopped'])))
    return 0 if report['status']=='PASS' else 1
if __name__=='__main__':raise SystemExit(main())
