"""Owned native automatic counterpart authority, atomicity and recovery probes."""
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from dataclasses import replace
from datetime import datetime, timezone, timedelta
from pathlib import Path
from threading import Barrier
import json
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path: sys.path.insert(0, str(ROOT))
from src import __version__
from src.adapters.clocks import FrozenClock
from src.adapters.contract_json import ContractJSONCodec
from src.adapters.extension_contracts import load_supported_schemas
from src.adapters.git_definitions import GitDefinitionSource
from src.adapters.migration_files import load_migration_plan
from src.adapters.postgres_migrations import apply_migrations, DatabaseRoles
from src.adapters.postgres_authorization import register_grant, PostgresCommandService
from src.adapters.postgres_definitions import PostgresDefinitionRepository
from src.adapters.postgres_evidence import PostgresEvidenceRepository, register_source_scope
from src.adapters.postgres_generation import PostgresGenerationHandler
from src.adapters.postgres_manual_tasks import PostgresManualTaskHandler
from src.adapters.postgres_lifecycle import PostgresLifecycleHandler
from src.adapters.postgres_fact_patches import PostgresFactPatchHandler, register_fact_patch_grant
from src.adapters.postgres_relationships import PostgresRelationshipRepository
from src.adapters.postgres_tasks import PostgresTaskRepository
from src.application.creation_outbox import event_id_for
from src.application.definitions import canonical, GitDefinitionRequest, DefinitionKey
from src.application.evidence_storage import SourceScope
from src.application.generation_commit import digest
from src.application.generation_runtime import GenerationPolicy
from src.application.manual_tasks import ResolvedManualIntent
from src.application.fact_patches import FactPatch, FactPatchGrant
from src.application.relationship_storage import acceptance_scope
from src.application.ports import RequestContext, AggregateKey, RecordWrite, CommitRequest
from src.domain.authorization import Command, CallerIdentity, AuthorityGrant, change
from src.domain.provenance import capture_source
from src.domain.relationships import literal, FieldMapping
from tools.git_definition_fixture import GitDefinitionFixture
from tools.postgres_harness import PostgresHarness, HarnessError, ROLES, require
from tests import test_generation_evaluator as fixtures

NOW = datetime(2026, 1, 1, tzinfo=timezone.utc); CLOCK = FrozenClock(NOW)
SCOPE = SourceScope('synthetic-generation-runtime', 'scope', 'account')
USER = CallerIdentity('user', 'USER_COMMAND', True); WORKER = CallerIdentity('user', 'RELATIONSHIP_RULE', True)


def verify(h, report, *, post_verify=None):
    import psycopg
    from psycopg.types.json import Jsonb
    checks = report['native_checks']; plan = load_migration_plan(root=ROOT)
    roles = DatabaseRoles(ROLES['migration'], ROLES['application'], ROLES['test'])
    db = h.create_database(initialize_schema=False)
    codec = ContractJSONCodec(load_supported_schemas(root=ROOT)); git = GitDefinitionFixture(h.run_root / 'git-fixture')
    fixtures.GenerationEvaluatorTests.setUpClass(); f = fixtures.GenerationEvaluatorTests()
    _, base, memory = f.setup_values()
    rules = {}; envelopes = {}
    for key in (base.record.source_type, base.record.target_type):
        envelopes[key] = dict(kind=key.kind, id=key.id, version=key.version, body=memory.get(key).body)
    def add(name, version='1', *, kind='SEPARATE_TASK', facts=None, mappings=None, relation=None, active=True, reverse_type=False):
        _, selected, values = f.setup_values(kind=kind, facts=facts, mappings=mappings, relation=relation)
        template = DefinitionKey('TASK_TEMPLATE', name+'-template', version)
        r = replace(selected.record.rule, rule_id=name, version=version, acceptance_ref='accepted-'+name+'-'+version,
            target_template_ref=template.id, target_template_version=version, active=active)
        record = replace(selected.record, rule=r, template=template)
        if reverse_type:
            record = replace(record, source_type=base.record.target_type, target_type=base.record.source_type,
                rule=replace(record.rule, source_type_ref='target-type', target_type_ref='source-type'))
        rules[(name, version)] = record
        for key, body in ((template, values.get(selected.record.template).body), (record.key, record.payload)):
            envelopes[key] = dict(kind=key.kind, id=key.id, version=key.version, body=body)
        return record
    copy_u = base.record.rule.mappings + (FieldMapping('user_remaining_seconds', 'SOURCE', 'user_remaining_seconds', None),)
    normal = add('normal', mappings=copy_u)
    add('normal', '2', active=False)
    add('pending', facts={}); add('pending', '2')
    stage_mappings = base.record.rule.mappings + (literal('user_remaining_seconds', 300),)
    add('stage', kind='STAGE', facts=dict(domain='study', stage_weight=2), mappings=stage_mappings)
    add('stage-two', kind='STAGE', facts=dict(domain='study', stage_weight=2), mappings=stage_mappings)
    add('reverse', relation=dict(kind='COMPLETION_ORDER', direction='TARGET_TO_SOURCE'))
    add('cycle', reverse_type=True)
    add('expired')
    files = {str(i)+'.json': canonical(e).encode() for i,e in enumerate(envelopes.values())}; commit = git.commit_objects(files)
    with h.target(db, 'migration').connect() as owner:
        apply_migrations(owner, plan, roles=roles, application_version=__version__)
        register_source_scope(owner, plan, roles, SCOPE, application_version=__version__, clock=CLOCK)
        PostgresDefinitionRepository(owner, GitDefinitionSource(git.root), plan, roles, application_version=__version__).register(
            tuple(GitDefinitionRequest(commit, n, digest(json.loads(raw))) for n,raw in files.items()))
    def definitions(conn):
        return PostgresDefinitionRepository(conn, GitDefinitionSource(git.root), plan, roles, application_version=__version__)
    def policy(name, version='1', **kw):
        return GenerationPolicy('user', (rules[(name, version)].key,), (SCOPE,), **kw)
    def handler(conn, selected):
        return PostgresGenerationHandler(conn, codec, plan, application_version=__version__, clock=CLOCK,
            policy=selected, definitions=definitions(conn))
    with h.target(db).connect() as conn:
        reader = PostgresTaskRepository(conn, codec, plan, application_version=__version__, clock=CLOCK)
        evidence = PostgresEvidenceRepository(conn, codec, plan, application_version=__version__, clock=CLOCK, scopes=(SCOPE,))
        def source(name, raw):
            s = capture_source(provider=SCOPE.provider, scope_ref=SCOPE.scope_ref, external_id=name, raw_bytes=raw, captured_at=NOW, source_type='USER')
            evidence.observe_source(canonical(s.as_record()).encode(), raw_content=raw, locator_ref='synthetic-'+name)
            return s.record_id
        for record in rules.values():
            ref = source(record.rule.acceptance_ref, canonical(record.payload).encode()); scope = acceptance_scope('RULE', record)
            with h.target(db, 'migration').connect() as owner:
                with owner.transaction():
                    owner.execute('INSERT INTO whattodo.authority_record VALUES(%s,%s,%s,%s,%s,%s,%s,%s)',
                        (record.rule.acceptance_ref, 'user', 'USER_COMMAND', ref, digest(scope), Jsonb(scope), NOW,
                            NOW+timedelta(hours=1) if record.rule.rule_id=='expired' else None))
                PostgresRelationshipRepository(owner, plan, roles, application_version=__version__, caller=USER,
                    source_scopes=(SCOPE,), clock=CLOCK).register_rule(record)
        def manual(name,principal='user'):
            command = Command('create-'+name, principal, 'USER_COMMAND', 'grant-'+name, (change(name, None, 'CREATE_TASK',
                dict(title='Synthetic '+name, importance=3, requiredness='REQUIRED', difficulty=fixtures.DIMS, user_remaining_seconds=600)),))
            raw = canonical(command.as_record()).encode(); ref = source(command.command_id, raw)
            grant = AuthorityGrant(command.authority_ref, principal, 'USER_COMMAND', command.command_id, command.changes, ref, NOW, expires_at=NOW+timedelta(hours=1))
            with h.target(db, 'migration').connect() as owner: register_grant(owner, grant, plan, application_version=__version__)
            intent = ResolvedManualIntent(command.fingerprint, ref, NOW, canonical(dict(domain='study', task_type_ref=dict(id='source-type', version='1'))))
            result = PostgresManualTaskHandler(conn, codec, plan, application_version=__version__, clock=CLOCK, definitions=definitions(conn),
                grants=(grant,), source_scopes=(SCOPE,), intents=(intent,)).create(raw, RequestContext(command.command_id, 'native-create'),
                expected_store_revision=conn.execute('SELECT revision FROM whattodo.store_epoch').fetchone()[0], audit_id='audit-'+command.command_id,
                caller=CallerIdentity(principal,'USER_COMMAND',True))
            require(result.status=='SUCCESS', 'GENERATION_RUNTIME_MANUAL_FIXTURE')
            return event_id_for(name)
        def generate(event, name='normal', selected=None, connection=None, caller=WORKER):
            return handler(connection if connection is not None else conn, selected or policy(name)).generate(
                event, name, correlation_ref='native-'+name, caller=caller)
        tables = ('authority_record','command_transaction','audit_entry','audit_change','task_identity','task_revision','task_head',
            'task_payload_revision','stage_identity','stage_revision','task_stage_revision','task_field_provenance','effort_observation',
            'canonical_creation_event','creation_delivery_head','creation_delivery_revision','task_relation_revision',
            'generation_occurrence','generation_occurrence_revision')
        def counts():
            return tuple(conn.execute('SELECT count(*) FROM whattodo.'+t).fetchone()[0] for t in tables) + conn.execute('SELECT revision FROM whattodo.store_epoch').fetchone()
        def success(out, state='CREATED'):
            require(out.status=='SUCCESS' and out.value.state==state, 'GENERATION_RUNTIME_'+out.code)
        event = manual('source-main'); before = counts(); created = generate(event); success(created)
        target = created.value.occurrence.target_task_ref; actual = reader.get(target)
        require(actual is not None and actual.aggregate.budget(at=NOW).seconds==600 and reader.get('source-main').revision==1
            and created.value.receipt.store_revision==before[-1]+1 and len(created.value.receipt.changed_keys)==2,
            'GENERATION_RUNTIME_ATOMIC_TARGET')
        require(conn.execute('SELECT count(*) FROM whattodo.canonical_creation_event WHERE task_id=%s', (target,)).fetchone()==(1,)
            and conn.execute('SELECT count(*) FROM whattodo.pending_evidence_identity').fetchone()==(0,), 'GENERATION_RUNTIME_CANONICAL_NO_REVIEW')
        checks.append('application_role_resolves_real_rule_authority_and_atomically_creates_target_occurrence_full_audit_epoch_and_next_event')
        checks.append('mapped_remaining_retains_original_user_evidence_and_independent_target_budget_without_confirmation_queue')
        after = counts(); replay = generate(event); success(replay)
        require(replay.code=='GENERATION_REPLAY' and replay.value.receipt==created.value.receipt and counts()==after, 'GENERATION_RUNTIME_REPLAY')
        lookup = handler(conn, policy('normal')).lookup(event, 'normal', correlation_ref='reconcile', caller=WORKER); success(lookup)
        require(lookup.value.receipt==created.value.receipt, 'GENERATION_RUNTIME_LOOKUP')
        changed = generate(event, selected=policy('normal','2')); success(changed)
        require(changed.value.occurrence==created.value.occurrence and counts()==after, 'GENERATION_RUNTIME_RULE_EDIT_RECREATED')
        checks.append('created_retries_lookup_and_inactive_new_rule_version_return_original_receipt_without_writes')
        for caller in (CallerIdentity('other','RELATIONSHIP_RULE',True), USER, CallerIdentity('user','RELATIONSHIP_RULE',False)):
            result = generate(event, caller=caller); require(result.status=='PERMANENT' and counts()==after, 'GENERATION_RUNTIME_FOREIGN_CALLER')
        bad_policy = replace(policy('normal'), source_scopes=(SourceScope(SCOPE.provider,SCOPE.scope_ref,'foreign'),))
        denied = generate(event, selected=bad_policy); require(denied.status=='PERMANENT' and counts()==after, 'GENERATION_RUNTIME_FOREIGN_SCOPE')
        denied = generate('missing-event'); require(denied.code=='GENERATION_CANONICAL_EVENT_REQUIRED' and counts()==after, 'GENERATION_RUNTIME_RAW_EVENT')
        checks.append('foreign_unauthenticated_wrong_origin_wrong_account_and_raw_event_are_rejected_without_effects')
        foreign_event=manual('source-foreign',principal='foreign');n=counts()
        denied=generate(foreign_event);require(denied.code=='GENERATION_SOURCE_PRINCIPAL_OR_TIME' and counts()==n,'GENERATION_RUNTIME_FOREIGN_EVENT')
        checks.append('authenticated_worker_cannot_generate_from_another_principal_canonical_event_even_with_same_source_account')
        inactive_event=manual('source-inactive');n=counts();inactive=generate(inactive_event,selected=policy('normal','2'))
        success(inactive,'NOT_ELIGIBLE');require(counts()==n,'GENERATION_RUNTIME_INACTIVE_CREATED')
        expired_handler=PostgresGenerationHandler(conn,codec,plan,application_version=__version__,clock=FrozenClock(NOW+timedelta(hours=2)),
            policy=policy('expired'),definitions=definitions(conn))
        denied=expired_handler.generate(inactive_event,'expired',correlation_ref='expired',caller=WORKER)
        require(denied.code=='GENERATION_AUTHORITY_INACTIVE' and counts()==n,'GENERATION_RUNTIME_EXPIRED_AUTHORITY')
        checks.append('uncreated_inactive_rule_or_expired_root_authority_cannot_publish_counterpart_or_pending_effects')
        pending_event = manual('source-pending'); pending = generate(pending_event,'pending'); success(pending,'PENDING')
        n = counts(); repeated = generate(pending_event,'pending'); success(repeated,'PENDING'); require(counts()==n, 'GENERATION_RUNTIME_PENDING_REPLAY')
        resolved = generate(pending_event,'pending',selected=policy('pending','2')); success(resolved)
        require(resolved.value.occurrence.revision==2 and resolved.value.occurrence.scope.generation_key==pending.value.occurrence.scope.generation_key
            and conn.execute('SELECT runtime_payload FROM whattodo.generation_occurrence_revision WHERE generation_key=%s AND revision=1',
                (pending.value.occurrence.scope.generation_key,)).fetchone()==(pending.value.occurrence.payload,), 'GENERATION_RUNTIME_PENDING_HISTORY')
        checks.append('missing_facts_publish_only_pending_once_then_accepted_new_version_creates_one_target_retaining_history')
        reverse_event = manual('source-reverse'); reversed_out = generate(reverse_event,'reverse'); success(reversed_out)
        link = conn.execute('SELECT kind,before_task_id,after_task_id FROM whattodo.task_relation_revision WHERE relation_id=%s',
            (reversed_out.value.occurrence.relation_ref,)).fetchone()
        require(link==('COMPLETION_ORDER',reversed_out.value.occurrence.target_task_ref,'source-reverse') and len(reversed_out.value.receipt.changed_keys)==3,
            'GENERATION_RUNTIME_REVERSE_ORDER')
        success(handler(conn,policy('reverse')).lookup(reverse_event,'reverse',correlation_ref='reverse-lookup',caller=WORKER))
        checks.append('explicit_reverse_hard_order_is_atomic_and_independent_of_source_to_target_generation_direction')
        cycle_event = manual('source-cycle'); n = counts()
        cyclic = replace(policy('normal'),rule_keys=(normal.key,rules[('cycle','1')].key))
        rejected = generate(cycle_event,selected=cyclic); require(rejected.code=='GENERATION_GRAPH_REJECTED' and counts()==n,'GENERATION_RUNTIME_CYCLE')
        checks.append('current_selected_generation_cycle_is_rejected_before_any_authority_or_audit_effect')
        # A real epoch lock forces one writer to defer; retry observes the exact original occurrence.
        concurrent_event = manual('source-concurrent'); barrier=Barrier(2)
        def contender(_):
            with h.target(db).connect() as separate:
                service=handler(separate,policy('normal'));barrier.wait(timeout=20)
                return service.generate(concurrent_event,'normal',correlation_ref='concurrent',caller=WORKER)
        with ThreadPoolExecutor(max_workers=2) as pool: outcomes=list(pool.map(contender,range(2)))
        require(any(o.status=='SUCCESS' for o in outcomes) and all(o.status in ('SUCCESS','RETRYABLE') for o in outcomes), 'GENERATION_RUNTIME_CONCURRENT')
        final = generate(concurrent_event); success(final)
        require(conn.execute('SELECT count(*) FROM whattodo.generation_occurrence_revision WHERE generation_key=%s',
            (final.value.occurrence.scope.generation_key,)).fetchone()==(1,), 'GENERATION_RUNTIME_CONCURRENT_DUPLICATE')
        checks.append('two_real_simultaneous_connections_commit_one_counterpart_and_retry_returns_original_receipt')
        stage_event=manual('source-stage');barrier=Barrier(2)
        def stage_contender(name):
            with h.target(db).connect() as separate:
                service=handler(separate,policy(name));barrier.wait(timeout=20)
                return service.generate(stage_event,name,correlation_ref='stage-concurrent',caller=WORKER)
        with ThreadPoolExecutor(max_workers=2) as pool: outcomes=list(pool.map(stage_contender,('stage','stage-two')))
        require(any(o.status=='SUCCESS' for o in outcomes) and all(o.status in ('SUCCESS','RETRYABLE') for o in outcomes),'GENERATION_RUNTIME_STAGE_CAS')
        one=generate(stage_event,'stage');two=generate(stage_event,'stage-two');success(one);success(two)
        parent=reader.get('source-stage')
        require(parent.revision==3 and len(parent.aggregate.as_record()['stage_details'])==2 and parent.aggregate.budget(at=NOW).seconds==600
            and reader.get('source-stage',1).aggregate.as_record()['stage_details']==[],'GENERATION_RUNTIME_SHARED_BUDGET')
        checks.append('concurrent_stage_rules_retry_against_current_parent_preserve_both_stages_and_share_one_budget_with_exact_membership')
        # Cancellation and user-authorized reactivation never recreate an already generated target.
        revision=reader.get('source-main').revision
        cancel=Command('cancel-main','user','USER_COMMAND','cancel-grant',(change('source-main',revision,'UPDATE_TASK',dict(disposition='CANCELLED')),))
        cancel_raw=canonical(cancel.as_record()).encode();ref=source('cancel-main',cancel_raw)
        grant=AuthorityGrant(cancel.authority_ref,'user','USER_COMMAND',cancel.command_id,cancel.changes,ref,NOW,expires_at=NOW+timedelta(hours=1))
        with h.target(db,'migration').connect() as owner:register_grant(owner,grant,plan,application_version=__version__)
        result=PostgresLifecycleHandler(conn,codec,plan,application_version=__version__,clock=CLOCK,grants=(grant,),source_scopes=(SCOPE,)).cancel(
            cancel_raw,RequestContext(cancel.command_id,'cancel'),expected_store_revision=counts()[-1],audit_id='audit-cancel-main',caller=USER)
        require(result.status=='SUCCESS','GENERATION_RUNTIME_CANCEL_FIXTURE');n=counts();success(generate(event));require(counts()==n and reader.get(target)==actual,'GENERATION_RUNTIME_CANCEL_INDEPENDENCE')
        old=reader.get('source-main');reopen=Command('reopen-main','user','USER_COMMAND','reopen-grant',(change('source-main',old.revision,'UPDATE_TASK',dict(disposition='ACTIVE')),))
        raw=canonical(reopen.as_record()).encode();ref=source('reopen-main',raw);grant=AuthorityGrant(reopen.authority_ref,'user','USER_COMMAND',reopen.command_id,reopen.changes,ref,NOW,expires_at=NOW+timedelta(hours=1))
        with h.target(db,'migration').connect() as owner:register_grant(owner,grant,plan,application_version=__version__)
        v=deepcopy(old.aggregate.as_record());v['core']['revision']=v['effort']['task_revision']=old.revision+1;v['core']['disposition']=v['effort']['disposition']='ACTIVE'
        provenance={p['field']:p['source_ref'] for p in v['provenance']};provenance.update({'/core/disposition':ref,'/effort/disposition':ref});v['provenance']=[dict(field=k,source_ref=s) for k,s in sorted(provenance.items())]
        request=CommitRequest(RequestContext(reopen.command_id,'reopen'),'user',counts()[-1],(RecordWrite(AggregateKey('TASK','source-main'),old.revision,canonical(v)),),'audit-reopen',ref)
        result=PostgresCommandService(conn,codec,plan,application_version=__version__,clock=CLOCK,grants=(grant,),source_scopes=(SCOPE,)).commit(raw,request,caller=USER)
        require(result.status=='SUCCESS','GENERATION_RUNTIME_REOPEN_FIXTURE');n=counts();success(generate(event));require(counts()==n and reader.get(target)==actual,'GENERATION_RUNTIME_REOPEN_RECREATED')
        checks.append('actual_user_source_cancellation_and_reactivation_leave_existing_independent_target_and_original_occurrence_unchanged')
        late_event=manual('source-late')
        patch=FactPatch('patch-late','user','patch-late-grant','source-late',1,canonical(dict(user_remaining_seconds=900)))
        raw=canonical(patch.as_record()).encode();ref=source('patch-late',raw);grant=FactPatchGrant(patch,ref,NOW,NOW+timedelta(hours=1),NOW)
        with h.target(db,'migration').connect() as owner:register_fact_patch_grant(owner,grant,plan,application_version=__version__)
        result=PostgresFactPatchHandler(conn,codec,plan,application_version=__version__,clock=CLOCK,grants=(grant,),source_scopes=(SCOPE,)).patch(
            raw,RequestContext('patch-late','late'),expected_store_revision=counts()[-1],audit_id='audit-patch-late',caller=USER)
        require(result.status=='SUCCESS','GENERATION_RUNTIME_LATE_SOURCE_FIXTURE')
        late=generate(late_event);success(late)
        require(reader.get('source-late').aggregate.budget(at=NOW).seconds==900
            and reader.get(late.value.occurrence.target_task_ref).aggregate.budget(at=NOW).seconds==600
            and late.value.occurrence.payload['manifest']['source_current_revision']==2,'GENERATION_RUNTIME_ORIGINAL_NOT_LATEST')
        n=counts();success(generate(late_event));require(counts()==n,'GENERATION_RUNTIME_LATE_REPLAY')
        checks.append('delayed_generation_maps_original_creation_snapshot_and_reconstructs_receipt_with_later_current_source_revision')
        closed_event=manual('source-closed');cancel=Command('cancel-closed','user','USER_COMMAND','cancel-closed-grant',
            (change('source-closed',1,'UPDATE_TASK',dict(disposition='CANCELLED')),))
        raw=canonical(cancel.as_record()).encode();ref=source('cancel-closed',raw)
        grant=AuthorityGrant(cancel.authority_ref,'user','USER_COMMAND',cancel.command_id,cancel.changes,ref,NOW,expires_at=NOW+timedelta(hours=1))
        with h.target(db,'migration').connect() as owner:register_grant(owner,grant,plan,application_version=__version__)
        result=PostgresLifecycleHandler(conn,codec,plan,application_version=__version__,clock=CLOCK,grants=(grant,),source_scopes=(SCOPE,)).cancel(
            raw,RequestContext(cancel.command_id,'closed'),expected_store_revision=counts()[-1],audit_id='audit-cancel-closed',caller=USER)
        require(result.status=='SUCCESS','GENERATION_RUNTIME_CLOSED_PARENT_FIXTURE')
        closed=generate(closed_event,'stage');success(closed,'FAILED');n=counts();success(generate(closed_event,'stage'),'FAILED')
        require(counts()==n and reader.get('source-closed').revision==2 and not reader.get('source-closed').aggregate.as_record()['stage_details'],
            'GENERATION_RUNTIME_CLOSED_PARENT_MUTATED')
        checks.append('closed_current_parent_publishes_only_failed_occurrence_and_retries_without_task_or_stage_effect')
        class Disconnect:
            def __init__(self, connection):self.connection=connection;self.fired=False
            def __getattr__(self,name):return getattr(self.connection,name)
            def execute(self,query,*args,**kw):
                result=self.connection.execute(query,*args,**kw)
                if not self.fired and 'INSERT INTO whattodo.' in str(query) and 'generation_occurrence_revision' in str(query):
                    self.fired=True;self.connection.close();raise psycopg.OperationalError('synthetic precommit disconnect')
                return result
        for name in ('normal','reverse','stage'):
            broken_event=manual('source-disconnect-'+name);n=counts()
            with h.target(db).connect() as separate:
                proxy=Disconnect(separate);result=generate(broken_event,name,connection=proxy)
                require(proxy.fired and result.status=='RETRYABLE','GENERATION_RUNTIME_REAL_DISCONNECT')
            require(counts()==n,'GENERATION_RUNTIME_DISCONNECT_LEAK');success(generate(broken_event,name))
        checks.append('real_precommit_connection_close_rolls_back_task_observation_outbox_relation_occurrence_authority_audit_receipt_and_epoch')
        class LostAck:
            def __init__(self,connection,error_type):self.connection=connection;self.ordinal=0;self.error_type=error_type
            def __getattr__(self,name):return getattr(self.connection,name)
            def transaction(self):
                self.ordinal+=1;outer=self.ordinal==1;wrapped=self.connection.transaction();error_type=self.error_type
                class Transaction:
                    def __enter__(self):return wrapped.__enter__()
                    def __exit__(self,kind,error,traceback):
                        result=wrapped.__exit__(kind,error,traceback)
                        if kind is None and outer:raise error_type('synthetic lost acknowledgement')
                        return result
                return Transaction()
        for i,(name,error_type) in enumerate((('normal',psycopg.OperationalError),('reverse',psycopg.InterfaceError),('stage',psycopg.OperationalError))):
            ack_event=manual('source-ack-'+str(i))
            with h.target(db).connect() as separate:
                proxy=LostAck(separate,error_type);out=generate(ack_event,name,connection=proxy)
                require(out.status=='UNKNOWN' and out.code=='GENERATION_ACKNOWLEDGEMENT_LOST','GENERATION_RUNTIME_ACK_UNKNOWN')
            n=counts();reconciled=handler(conn,policy(name)).lookup(ack_event,name,correlation_ref='ack-reconcile',caller=WORKER);success(reconciled)
            replayed=generate(ack_event,name);success(replayed);require(replayed.value.receipt==reconciled.value.receipt and counts()==n,'GENERATION_RUNTIME_ACK_RECONCILE')
        checks.append('successful_commit_operational_or_interface_ack_loss_is_unknown_and_fresh_lookup_retry_reconciles_without_duplicates')
        retained=created.value.receipt
    with h.target(db).connect() as fresh:
        out=handler(fresh,policy('normal','2')).lookup(event,'normal',correlation_ref='restart',caller=WORKER)
        success(out);require(out.value.receipt==retained,'GENERATION_RUNTIME_RESTART')
        checks.append('fresh_connection_reconstructs_original_full_audited_generation_receipt_after_source_changes_and_rule_edit')
    if post_verify is not None:post_verify(h,db,codec,plan,roles,git)
    report.update(schema_version=plan.schema_version,migration_steps=len(plan.steps),domain_tables=82,domain_foreign_keys=204)


def main():
    h=PostgresHarness();report=dict(task='M3B-05.b',status='IN_PROGRESS',scope='SYNTHETIC_SCOPED_AUTOMATIC_COUNTERPART_RUNTIME',native_checks=[])
    try:
        with h:verify(h,report)
        report.update(status='PASS',native_check_count=len(report['native_checks']),limitations=['Isolated synthetic native runtime; no live worker or personal activation','Policy selects exact independently configured rule versions; no inferred latest version','Delivery leasing and bounded cascade orchestration remain M3B-06'])
    except Exception as exc:
        report.update(status='FAIL',failure_type=type(exc).__name__,failure_code=str(exc) if isinstance(exc,HarnessError) else 'GENERATION_RUNTIME_NATIVE_FAILED',failure_sqlstate=getattr(exc,'sqlstate',None))
        import traceback
        report['failure_frames']=[dict(file=Path(f.filename).name,function=f.name,line=f.lineno) for f in traceback.extract_tb(exc.__traceback__)]
    report['harness']=h.safe_summary();target=h.run_root/'generation-runtime-report.json'
    if h.run_root.exists():target.write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(dict(status=report['status'],report=str(target),checks=len(report['native_checks']),server_stopped=report['harness']['server_stopped'])))
    return 0 if report['status']=='PASS' else 1


if __name__=='__main__':raise SystemExit(main())
