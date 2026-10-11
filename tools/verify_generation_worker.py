"""Native finite cascades, durable checkpoints, fencing and changed-input wake."""
from dataclasses import replace
from datetime import timedelta
from pathlib import Path
import json,sys
ROOT=Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:sys.path.insert(0,str(ROOT))
from src import __version__
from src.adapters.git_definitions import GitDefinitionSource
from src.adapters.postgres_definitions import PostgresDefinitionRepository
from src.adapters.postgres_evidence import PostgresEvidenceRepository
from src.adapters.postgres_authorization import register_grant
from src.adapters.postgres_manual_tasks import PostgresManualTaskHandler
from src.adapters.postgres_relationships import PostgresRelationshipRepository
from src.adapters.postgres_generation_worker import PostgresGenerationWorker
from src.adapters.postgres_generation import PostgresGenerationHandler
from src.adapters.postgres_tasks import PostgresTaskRepository
from src.application.definitions import canonical,DefinitionKey,GitDefinitionRequest
from src.application.generation_commit import digest
from src.application.generation_processing import ProcessingLimits
from src.application.generation_runtime import GenerationPolicy
from src.application.relationship_storage import RuleStorageRecord,acceptance_scope
from src.application.relationship_validation import GraphLimits
from src.application.manual_tasks import ResolvedManualIntent
from src.application.creation_outbox import event_id_for
from src.application.ports import RequestContext,PortResult
from src.domain.authorization import Command,AuthorityGrant,CallerIdentity,change
from src.domain.relationships import RelationshipRule,literal
from src.domain.provenance import capture_source
from tools.postgres_harness import PostgresHarness,HarnessError,require
from tools.verify_generation_runtime import verify as verify_runtime,SCOPE,NOW,USER


class MovingClock:
    def __init__(self):self.value=NOW
    def now(self):return self.value
    def advance(self,seconds):self.value+=timedelta(seconds=seconds)


def verify(h,report):
    def processing(h,db,codec,plan,roles,git):
        from psycopg.types.json import Jsonb
        clock=MovingClock();checks=report['native_checks'];worker_caller=CallerIdentity('user','RELATIONSHIP_RULE',True)
        with h.target(db).connect() as conn:
            def definitions(connection):return PostgresDefinitionRepository(connection,GitDefinitionSource(git.root),plan,roles,application_version=__version__)
            def policy(keys,**limits):return GenerationPolicy('user',tuple(keys),(SCOPE,),GraphLimits(**limits))
            def worker(connection,selected,identifier='worker',**limits):
                return PostgresGenerationWorker(connection,codec,plan,application_version=__version__,clock=clock,policy=selected,
                    worker_id=identifier,definitions=definitions(connection),limits=ProcessingLimits(**limits))
            old_policy=policy((DefinitionKey('RELATIONSHIP_RULE','normal','1'),))
            drained=worker(conn,old_policy,max_events=1000).run_batch()
            require(drained.idle and drained.processed_events>0,'WORKER_LEGACY_EVENTS_DRAIN')
            checks.append('worker_consumes_scoped_existing_canonical_events_including_generated_sources_and_terminal_leaves')
            evidence=PostgresEvidenceRepository(conn,codec,plan,application_version=__version__,clock=clock,scopes=(SCOPE,))
            def source(name,raw):
                s=capture_source(provider=SCOPE.provider,scope_ref=SCOPE.scope_ref,external_id=name,raw_bytes=raw,captured_at=clock.now(),source_type='USER')
                evidence.observe_source(canonical(s.as_record()).encode(),raw_content=raw,locator_ref='synthetic-'+name);return s.record_id
            types={name:DefinitionKey('TASKTYPE','worker-'+name,'1') for name in ('a','b','c')}
            dims=dict(thinking_depth=2,repetitive_volume=2,new_learning_load=2)
            defaults=dict(importance=3,requiredness='REQUIRED',difficulty=dims)
            records={};envelopes={k:dict(kind=k.kind,id=k.id,version=k.version,body=dict(defaults=defaults)) for k in types.values()}
            def rule(name,before,after,version='1',*,facts=None,role='child'):
                template=DefinitionKey('TASK_TEMPLATE',name+'-template',version)
                r=RelationshipRule(name,version,True,'accepted-'+name+'-'+version,'CANONICAL_CREATION',types[before].id,types[after].id,
                    template.id,template.version,role,'SEPARATE_TASK',('title','completion','disposition'),
                    (literal('title','Synthetic '+name),literal('completion','INCOMPLETE'),literal('disposition','ACTIVE')))
                record=RuleStorageRecord(r,types[before],types[after],template);records[(name,version)]=record
                for key,body in ((template,dict(creation_facts=dict(domain='study') if facts is None else facts)),(record.key,record.payload)):
                    envelopes[key]=dict(kind=key.kind,id=key.id,version=key.version,body=body)
                return record
            ab=rule('chain-ab','a','b');bc=rule('chain-bc','b','c');pending=rule('waiting-ab','a','b',facts={});pending2=rule('waiting-ab','a','b','2')
            first=rule('quota-first','a','b');second=rule('quota-second','a','c');changed=rule('quota-first','a','b','2',role='new-child')
            reverse=rule('cycle-ba','b','a')
            files={str(i)+'.json':canonical(e).encode() for i,e in enumerate(envelopes.values())};commit=git.commit_objects(files)
            with h.target(db,'migration').connect() as owner:
                definitions(owner).register(tuple(GitDefinitionRequest(commit,name,digest(json.loads(raw))) for name,raw in files.items()))
            for record in records.values():
                ref=source(record.rule.acceptance_ref,canonical(record.payload).encode());scope=acceptance_scope('RULE',record)
                with h.target(db,'migration').connect() as owner:
                    with owner.transaction():owner.execute('INSERT INTO whattodo.authority_record VALUES(%s,%s,%s,%s,%s,%s,%s,%s)',
                        (record.rule.acceptance_ref,'user','USER_COMMAND',ref,digest(scope),Jsonb(scope),clock.now(),None))
                    PostgresRelationshipRepository(owner,plan,roles,application_version=__version__,caller=USER,source_scopes=(SCOPE,),clock=clock).register_rule(record)
            def manual(name):
                command=Command('create-'+name,'user','USER_COMMAND','grant-'+name,(change(name,None,'CREATE_TASK',dict(title='Synthetic '+name,
                    importance=3,requiredness='REQUIRED',difficulty=dims,user_remaining_seconds=600)),))
                raw=canonical(command.as_record()).encode();ref=source(command.command_id,raw)
                grant=AuthorityGrant(command.authority_ref,'user','USER_COMMAND',command.command_id,command.changes,ref,clock.now(),expires_at=clock.now()+timedelta(hours=1))
                with h.target(db,'migration').connect() as owner:register_grant(owner,grant,plan,application_version=__version__)
                intent=ResolvedManualIntent(command.fingerprint,ref,clock.now(),canonical(dict(domain='study',task_type_ref=dict(id=types['a'].id,version='1'))))
                out=PostgresManualTaskHandler(conn,codec,plan,application_version=__version__,clock=clock,definitions=definitions(conn),grants=(grant,),source_scopes=(SCOPE,),intents=(intent,)).create(
                    raw,RequestContext(command.command_id,'worker-fixture'),expected_store_revision=conn.execute('SELECT revision FROM whattodo.store_epoch').fetchone()[0],audit_id='audit-'+name,caller=USER)
                require(out.status=='SUCCESS','WORKER_MANUAL_FIXTURE');return event_id_for(name)
            reader=PostgresTaskRepository(conn,codec,plan,application_version=__version__,clock=clock)
            chain=policy((ab.key,bc.key));root=manual('worker-chain')
            result=worker(conn,chain,max_events=1).run_batch();require(result.processed_events==1 and not result.idle,'WORKER_FINITE_BATCH')
            with h.target(db).connect() as fresh:result=worker(fresh,chain,max_events=10).run_batch()
            require(result.idle and conn.execute('SELECT count(*) FROM whattodo.generation_occurrence WHERE source_event_ref=%s AND state=\'CREATED\'',(root,)).fetchone()==(1,),'WORKER_CHAIN_ROOT')
            descendants=conn.execute('SELECT depth FROM whattodo.generation_chain_event WHERE root_event_id=%s ORDER BY depth',(root,)).fetchall()
            require(descendants==[(0,),(1,),(2,)],'WORKER_CHAIN_DEPTH')
            checks.append('finite_first_batch_and_fresh_connection_complete_real_two_step_cascade_with_persistent_lineage_and_leaf_settlement')
            clock.advance(2);root=manual('worker-checkpoint');two=policy((first.key,second.key))
            w=worker(conn,two,max_events=1,max_rules_per_lease=1,retry_seconds=1);w.run_batch()
            old=w.outbox.get(root);require(old.state=='READY','WORKER_CHECKPOINT_CONTINUATION')
            checkpoint=conn.execute('SELECT progress FROM whattodo.generation_processing_revision r JOIN whattodo.generation_processing_head h USING(event_id,revision) WHERE event_id=%s',(root,)).fetchone()[0]
            require(checkpoint['cursor']==1,'WORKER_RULE_CHECKPOINT')
            count=conn.execute('SELECT count(*) FROM whattodo.generation_occurrence WHERE source_event_ref=%s',(root,)).fetchone()[0]
            for _ in range(5):
                clock.advance(2)
                with h.target(db).connect() as fresh:worker(fresh,two,max_events=1,max_rules_per_lease=1,retry_seconds=1).run_batch()
                if w.outbox.get(root).state=='DONE':break
            require(w.outbox.get(root).state=='DONE' and conn.execute('SELECT count(*) FROM whattodo.generation_occurrence WHERE source_event_ref=%s',(root,)).fetchone()[0]==count+1,'WORKER_CHECKPOINT_RESUME')
            worker(conn,two,max_events=20).run_batch()
            checks.append('partial_rule_checkpoint_resumes_after_new_connection_without_recreating_first_counterpart')
            clock.advance(2);root=manual('worker-waiting');p=policy((pending.key,));w=worker(conn,p,max_events=5);w.run_batch()
            require(w.outbox.get(root).state=='WAITING_FACTS' and w.wake(root) is None,'WORKER_NO_UNCHANGED_WAKE')
            w2=worker(conn,policy((pending2.key,)),identifier='facts-worker',max_events=5)
            resumed=w2.wake(root);require(resumed is not None and resumed.state=='DONE','WORKER_FACT_WAKE')
            require(conn.execute('SELECT state,revision FROM whattodo.generation_occurrence WHERE source_event_ref=%s',(root,)).fetchone()==('CREATED',2),'WORKER_FACT_HISTORY')
            w2.run_batch();checks.append('unchanged_pending_facts_stay_waiting_and_new_accepted_inputs_wake_once_preserving_occurrence_history')
            # Replayed settlement still names exactly the original token after a wake.
            require(conn.execute('SELECT count(*) FROM whattodo.creation_delivery_revision WHERE event_id=%s AND state=\'WAITING_FACTS\'',(root,)).fetchone()==(1,),'WORKER_WAKE_HISTORY')
            checks.append('changed_input_wake_takes_new_fenced_claim_without_rewriting_prior_delivery_history')
            clock.advance(2);root=manual('worker-quota');quota=policy((first.key,second.key),max_generated_instances=2)
            w=worker(conn,quota,max_events=1,max_rules_per_lease=1,retry_seconds=1);w.run_batch()
            next_policy=policy((changed.key,second.key),max_generated_instances=2)
            for _ in range(8):
                clock.advance(2)
                with h.target(db).connect() as fresh:worker(fresh,next_policy,max_events=1,max_rules_per_lease=1,retry_seconds=1).run_batch()
                if w.outbox.get(root).state=='FAILED':break
            state=w.outbox.get(root)
            require(state.state=='FAILED' and state.outcome.code=='PROCESSING_INSTANCE_LIMIT'
                and conn.execute('SELECT count(*) FROM whattodo.generation_occurrence WHERE source_event_ref=%s AND state=\'CREATED\'',(root,)).fetchone()==(2,),'WORKER_ROOT_QUOTA')
            checks.append('chain_instance_cap_survives_batches_restarts_and_changed_role_policy_without_counting_from_zero')
            worker(conn,next_policy,max_events=20).run_batch()
            clock.advance(2);root=manual('worker-cycle');cycle=policy((ab.key,reverse.key));w=worker(conn,cycle,max_events=1);w.run_batch()
            require(w.outbox.get(root).state=='FAILED' and w.outbox.get(root).outcome.code=='GENERATION_GRAPH_REJECTED'
                and conn.execute('SELECT count(*) FROM whattodo.generation_occurrence WHERE source_event_ref=%s',(root,)).fetchone()==(0,),'WORKER_VISIBLE_CYCLE')
            checks.append('recursive_selected_graph_stops_as_visible_permanent_delivery_failure_without_counterparts')
            # Existing descendants are measured from their canonical birth,
            # including counterparts created before this worker's checkpoint.
            clock.advance(2);root=manual('worker-depth')
            direct=PostgresGenerationHandler(conn,codec,plan,application_version=__version__,clock=clock,policy=policy((ab.key,)),definitions=definitions(conn))
            generated=direct.generate(root,ab.key.id,correlation_ref='depth-fixture',caller=worker_caller)
            require(generated.status=='SUCCESS','WORKER_DEPTH_FIXTURE')
            child=event_id_for(generated.value.occurrence.target_task_ref)
            bounded=worker(conn,policy((bc.key,),max_generation_depth=1),max_events=10)
            bounded.run_batch()
            require(bounded.outbox.get(child).state=='FAILED' and bounded.outbox.get(child).outcome.code=='PROCESSING_DEPTH_LIMIT'
                and conn.execute('SELECT count(*) FROM whattodo.generation_occurrence WHERE source_event_ref=%s',(child,)).fetchone()==(0,),'WORKER_ACTUAL_DEPTH_CAP')
            checks.append('actual_ancestry_depth_cap_stops_preexisting_generated_descendant_without_resetting_root_depth')
            clock.advance(2);root=manual('worker-renew');renewed=worker(conn,two,max_events=1,lease_seconds=10)
            original_generate=renewed.generator.generate;calls=[]
            def advancing_generate(*args,**kw):
                result=original_generate(*args,**kw);calls.append(result)
                if len(calls)==1:clock.advance(6)
                return result
            renewed.generator.generate=advancing_generate;renewed.run_batch()
            require(renewed.outbox.get(root).state=='DONE' and len(calls)==2
                and conn.execute("SELECT count(*) FROM whattodo.creation_delivery_revision WHERE event_id=%s AND state='CLAIMED'",(root,)).fetchone()==(2,),'WORKER_LEASE_RENEWAL')
            worker(conn,two,max_events=10).run_batch()
            checks.append('long_event_renews_real_delivery_lease_between_rules_and_commits_under_current_fencing_revision')
            clock.advance(2);root=manual('worker-checkpoint-disconnect')
            with h.target(db).connect() as interrupted:
                class ClosingCheckpoint:
                    def __getattr__(self,name):return getattr(interrupted,name)
                    def execute(self,query,*args,**kw):
                        result=interrupted.execute(query,*args,**kw)
                        if 'INSERT INTO whattodo.generation_processing_revision' in str(query):
                            interrupted.close()
                            import psycopg
                            raise psycopg.OperationalError('synthetic checkpoint disconnect')
                        return result
                broken=worker(ClosingCheckpoint(),chain,identifier='checkpoint-disconnect',lease_seconds=10)
                try:broken.run_batch()
                except Exception as exc:require(str(exc)=='PROCESSING_STORAGE_RETRY','WORKER_CHECKPOINT_DISCONNECT_CODE')
                else:require(False,'WORKER_CHECKPOINT_DISCONNECT_MISSING')
            require(conn.execute('SELECT count(*) FROM whattodo.generation_processing_revision WHERE event_id=%s',(root,)).fetchone()==(0,),'WORKER_CHECKPOINT_ROLLBACK')
            clock.advance(11)
            with h.target(db).connect() as fresh:worker(fresh,chain,identifier='checkpoint-restart',max_events=10,lease_seconds=10).run_batch()
            require(worker(conn,chain).outbox.get(root).state=='DONE','WORKER_CHECKPOINT_RECOVERY')
            checks.append('real_precommit_checkpoint_connection_close_rolls_back_partial_metadata_and_fresh_worker_recovers_expired_lease')
            clock.advance(2);root=manual('worker-stale');w=worker(conn,chain,identifier='old-worker',max_events=1,lease_seconds=10)
            lease=w.outbox.claim(lease_seconds=10);require(lease is not None and lease.event.event_id==root,'WORKER_STALE_FIXTURE');checkpoint=w._start(lease);w._reserve(lease,ab.key)
            clock.advance(11)
            new=worker(conn,chain,identifier='new-worker',max_events=1,lease_seconds=10);new_lease=new.outbox.claim(lease_seconds=10)
            require(new_lease is not None and new_lease.event.event_id==root,'WORKER_RECLAIM')
            epoch=conn.execute('SELECT revision FROM whattodo.store_epoch').fetchone()[0]
            rejected=w.generator.generate(root,ab.key.id,correlation_ref='stale',caller=worker_caller,lease=lease)
            require(rejected.status=='PERMANENT' and rejected.code=='OUTBOX_STALE_LEASE' and conn.execute('SELECT revision FROM whattodo.store_epoch').fetchone()==(epoch,),'WORKER_STALE_COMMITTED')
            new._process(new_lease);worker(conn,chain,max_events=10).run_batch()
            require(conn.execute('SELECT count(*) FROM whattodo.generation_occurrence WHERE source_event_ref=%s',(root,)).fetchone()==(1,),'WORKER_STALE_DUPLICATE')
            checks.append('expired_stolen_lease_cannot_commit_canonical_effects_and_new_owner_reuses_reservation_safely')
            clock.advance(2);root=manual('worker-commit-restart');w=worker(conn,chain,identifier='interrupted',max_events=1,lease_seconds=10)
            lease=w.outbox.claim(lease_seconds=10);checkpoint=w._start(lease);w._reserve(lease,ab.key)
            committed=w.generator.generate(root,ab.key.id,correlation_ref='before-checkpoint',caller=worker_caller,lease=lease)
            require(committed.status=='SUCCESS','WORKER_PRECHECKPOINT_COMMIT_'+committed.status+'_'+str(committed.code));clock.advance(11)
            with h.target(db).connect() as fresh:worker(fresh,chain,identifier='restart',max_events=10,lease_seconds=10).run_batch()
            require(w.outbox.get(root).state=='DONE' and conn.execute('SELECT count(*) FROM whattodo.generation_occurrence_revision WHERE generation_key=%s',
                (committed.value.occurrence.scope.generation_key,)).fetchone()==(1,),'WORKER_COMMIT_RESTART_DUPLICATE')
            checks.append('commit_before_checkpoint_process_loss_replays_original_receipt_after_lease_expiry_and_completes_descendants')
            clock.advance(2);root=manual('worker-unobserved-commit');uncertain=worker(conn,chain,max_events=1,retry_seconds=1)
            original=uncertain.generator.generate;original_lookup=uncertain.generator.lookup
            uncertain.generator.generate=lambda *a,**kw:PortResult('UNKNOWN','GENERATION_ACKNOWLEDGEMENT_LOST',kw['correlation_ref'])
            uncertain.generator.lookup=lambda *a,**kw:PortResult('UNKNOWN','GENERATION_NOT_OBSERVED',kw['correlation_ref'])
            uncertain.run_batch()
            require(uncertain.outbox.get(root).state=='READY' and uncertain.outbox.get(root).outcome.code=='GENERATION_NOT_OBSERVED','WORKER_UNKNOWN_NOT_PERMANENT')
            uncertain.generator.generate=original;uncertain.generator.lookup=original_lookup;clock.advance(2)
            worker(conn,chain,max_events=10,retry_seconds=1).run_batch()
            require(uncertain.outbox.get(root).state=='DONE' and conn.execute('SELECT count(*) FROM whattodo.generation_occurrence WHERE source_event_ref=%s',(root,)).fetchone()==(1,),'WORKER_UNKNOWN_RETRY')
            checks.append('typed_unknown_unobserved_commit_remains_retryable_and_recovers_once_instead_of_permanent_failure')
            clock.advance(2);root=manual('worker-contention');blocked=worker(conn,chain,max_events=1,max_attempts=2,retry_seconds=1)
            lease=blocked.outbox.claim();blocked._start(lease)
            with h.target(db).connect() as contender:
                with contender.transaction():
                    contender.execute('SELECT event_id FROM whattodo.generation_chain_event WHERE event_id=%s FOR UPDATE',(root,)).fetchone()
                    checkpoint=blocked._process(lease)
                    require(checkpoint.state=='RUNNING' and checkpoint.code=='PROCESSING_STORAGE_RETRY','WORKER_LOCK_RETRY')
                    clock.advance(2);blocked.run_batch()
                    require(blocked.outbox.get(root).state=='FAILED' and blocked.outbox.get(root).outcome.code=='PROCESSING_RETRY_LIMIT','WORKER_LOCK_RETRY_LIMIT')
            require(conn.execute('SELECT count(*) FROM whattodo.generation_occurrence WHERE source_event_ref=%s',(root,)).fetchone()==(0,),'WORKER_LOCK_COUNTERPART_LEAK')
            checks.append('real_concurrent_root_row_lock_is_typed_retry_with_backoff_and_finite_failure_instead_of_false_completion')
            clock.advance(2);root=manual('worker-retry');w=worker(conn,chain,max_events=1,max_attempts=2,retry_seconds=1)
            original=w.generator.generate
            w.generator.generate=lambda *a,**kw:PortResult('RETRYABLE','GENERATION_STORAGE_UNAVAILABLE',kw['correlation_ref'])
            w.run_batch();require(w.outbox.get(root).state=='READY','WORKER_RETRY_BACKOFF');clock.advance(2);w.run_batch()
            require(w.outbox.get(root).state=='FAILED' and w.outbox.get(root).outcome.code=='PROCESSING_RETRY_LIMIT','WORKER_RETRY_LIMIT')
            checks.append('typed_transient_failure_retries_with_backoff_then_stops_visibly_at_configured_attempt_limit')
            # Histories are immutable under the real application role.
            for table in ('generation_chain_event','generation_processing_revision','generation_chain_slot_revision'):
                try:
                    with conn.transaction():conn.execute('DELETE FROM whattodo.'+table)
                except Exception as exc:require(getattr(exc,'sqlstate',None)=='23514','WORKER_HISTORY_SQLSTATE')
                else:require(False,'WORKER_HISTORY_MUTATED')
            checks.append('application_cannot_delete_persistent_lineage_checkpoint_or_reservation_history')
            report.update(domain_tables=82,domain_foreign_keys=204,migration_steps=17,schema_version=plan.schema_version)
    fixture_report=dict(native_checks=[]);verify_runtime(h,fixture_report,post_verify=processing)
    report['prerequisite_runtime_checks']=len(fixture_report['native_checks'])


def main():
    h=PostgresHarness();r=dict(task='M3B-06',status='IN_PROGRESS',scope='SYNTHETIC_BOUNDED_FENCED_CASCADE_WORKER',native_checks=[])
    try:
        with h:verify(h,r)
        r.update(status='PASS',native_check_count=len(r['native_checks']),limitations=['Explicit finite worker calls only; no live scheduling or personal activation'])
    except Exception as exc:
        import traceback
        r.update(status='FAIL',failure_type=type(exc).__name__,failure_code=str(exc) if isinstance(exc,HarnessError) else 'PROCESSING_NATIVE_FAILED',failure_sqlstate=getattr(exc,'sqlstate',None),failure_frames=[dict(file=Path(f.filename).name,line=f.lineno,function=f.name) for f in traceback.extract_tb(exc.__traceback__)])
    r['harness']=h.safe_summary();p=h.run_root/'generation-worker-report.json'
    if h.run_root.exists():p.write_text(json.dumps(r,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(dict(status=r['status'],report=str(p),checks=len(r['native_checks']),server_stopped=r['harness']['server_stopped'])))
    return 0 if r['status']=='PASS' else 1
if __name__=='__main__':raise SystemExit(main())
