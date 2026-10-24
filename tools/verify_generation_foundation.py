"""Owned composite-plan/SQL guard probes, not a generation runtime acceptance."""
from dataclasses import replace
from datetime import datetime,timezone,timedelta
import json
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:sys.path.insert(0,str(ROOT))
from src import __version__
from src.adapters.clocks import FrozenClock
from src.adapters.contract_json import ContractJSONCodec
from src.adapters.extension_contracts import load_supported_schemas
from src.adapters.git_definitions import GitDefinitionSource
from src.adapters.migration_files import load_migration_plan
from src.adapters.postgres_migrations import apply_migrations,DatabaseRoles
from src.adapters.postgres_authorization import register_grant
from src.adapters.postgres_definitions import PostgresDefinitionRepository
from src.adapters.postgres_evidence import PostgresEvidenceRepository,register_source_scope
from src.adapters.postgres_manual_tasks import PostgresManualTaskHandler
from src.adapters.postgres_fact_patches import PostgresFactPatchHandler,register_fact_patch_grant
from src.adapters.postgres_relationships import PostgresRelationshipRepository
from src.adapters.postgres_tasks import PostgresTaskRepository
from src.adapters.postgres_creation_outbox import EVENT_COLUMNS
from src.application.creation_outbox import CreationEvent
from src.application.definitions import canonical,GitDefinitionRequest
from src.application.evidence_storage import SourceScope
from src.application.generation_evaluator import GenerationSource,AcceptedGenerationRule
from src.application.generation_commit import (prepare_generation_commit,GenerationOccurrenceRecord,digest)
from src.application.manual_tasks import ResolvedManualIntent
from src.application.fact_patches import FactPatch,FactPatchGrant
from src.application.relationship_storage import acceptance_scope
from src.application.ports import RequestContext,AggregateKey,RecordWrite,CommitRequest,CommitReceipt
from src.domain.authorization import Command,CallerIdentity,AuthorityGrant,change
from src.domain.provenance import capture_source
from tools.git_definition_fixture import GitDefinitionFixture
from tools.postgres_harness import PostgresHarness,HarnessError,ROLES,require
from tests import test_generation_evaluator as fixtures

NOW=datetime(2026,1,1,tzinfo=timezone.utc);CLOCK=FrozenClock(NOW)
SCOPE=SourceScope('synthetic-generation-foundation','scope','account');CALLER=CallerIdentity('user','USER_COMMAND',True)


def verify(h,r):
    import psycopg
    from psycopg.types.json import Jsonb
    from psycopg import sql
    plan=load_migration_plan(root=ROOT);old=replace(plan,steps=plan.steps[:15])
    roles=DatabaseRoles(ROLES['migration'],ROLES['application'],ROLES['test']);db=h.create_database(initialize_schema=False)
    git=GitDefinitionFixture(h.run_root/'git-fixture');codec=ContractJSONCodec(load_supported_schemas(root=ROOT));checks=r['native_checks']
    fixtures.GenerationEvaluatorTests.setUpClass();f=fixtures.GenerationEvaluatorTests()
    _,use,memory=f.setup_values(facts={});first=use.record
    _,use2,memory2=f.setup_values(version='2');second=replace(use2.record,rule=replace(use2.record.rule,acceptance_ref='rule-authority-v2'))
    # Version two resolves the missing domain in a distinct immutable template.
    template2=replace(first.template,version='2');second=replace(second,template=template2,rule=replace(second.rule,target_template_version='2'))
    envelopes=[dict(kind=k.kind,id=k.id,version=k.version,body=memory.get(k).body) for k in (first.source_type,first.target_type,first.template)]
    envelopes.extend([dict(kind=template2.kind,id=template2.id,version=template2.version,body=dict(creation_facts=dict(domain='study')))]
        +[dict(kind=x.key.kind,id=x.key.id,version=x.key.version,body=x.payload) for x in (first,second)])
    files={str(i)+'.json':canonical(e).encode() for i,e in enumerate(envelopes)};commit=git.commit_objects(files)
    with h.target(db,'migration').connect() as owner:
        apply_migrations(owner,old,roles=roles,application_version=__version__)
        register_source_scope(owner,old,roles,SCOPE,application_version=__version__,clock=CLOCK)
        defs=PostgresDefinitionRepository(owner,GitDefinitionSource(git.root),old,roles,application_version=__version__)
        defs.register(tuple(GitDefinitionRequest(commit,name,digest(json.loads(raw))) for name,raw in files.items()))
    with h.target(db).connect() as conn:
        def evidence(name,raw,active):
            s=capture_source(provider=SCOPE.provider,scope_ref=SCOPE.scope_ref,external_id=name,raw_bytes=raw,captured_at=NOW,source_type='USER')
            PostgresEvidenceRepository(conn,codec,active,application_version=__version__,clock=CLOCK,scopes=(SCOPE,)).observe_source(
                canonical(s.as_record()).encode(),raw_content=raw,locator_ref='synthetic-'+name)
            return s.record_id
        def manual(name,active):
            c=Command('create-'+name,'user','USER_COMMAND','root-'+name,(change(name,None,'CREATE_TASK',dict(title='Synthetic '+name,
                importance=3,requiredness='REQUIRED',difficulty=fixtures.DIMS,user_remaining_seconds=600)),))
            raw=canonical(c.as_record()).encode();ref=evidence(c.command_id,raw,active)
            g=AuthorityGrant(c.authority_ref,'user',c.origin,c.command_id,c.changes,ref,NOW,expires_at=NOW+timedelta(hours=1))
            with h.target(db,'migration').connect() as owner:register_grant(owner,g,active,application_version=__version__)
            definitions=PostgresDefinitionRepository(conn,GitDefinitionSource(git.root),active,roles,application_version=__version__)
            intent=ResolvedManualIntent(c.fingerprint,ref,NOW,canonical(dict(domain='study',task_type_ref=dict(id='source-type',version='1'))))
            out=PostgresManualTaskHandler(conn,codec,active,application_version=__version__,clock=CLOCK,definitions=definitions,
                grants=(g,),source_scopes=(SCOPE,),intents=(intent,)).create(raw,RequestContext(c.command_id,'schema-fixture'),
                expected_store_revision=conn.execute('SELECT revision FROM whattodo.store_epoch').fetchone()[0],audit_id='audit-'+c.command_id,caller=CALLER)
            require(out.code=='COMMITTED','GENERATION_FIXTURE_CREATION');return ref
        source_ref=manual('canonical-source',old)
        rule_sources={}
        for record in (first,second):
            ref=evidence('rule-'+record.rule.version,canonical(record.payload).encode(),old);rule_sources[record.key]=ref
            with h.target(db,'migration').connect() as owner:
                scope=acceptance_scope('RULE',record)
                with owner.transaction():owner.execute('INSERT INTO whattodo.authority_record VALUES(%s,%s,%s,%s,%s,%s,%s,%s)',
                    (record.rule.acceptance_ref,'user','USER_COMMAND',ref,digest(scope),Jsonb(scope),NOW,None))
                PostgresRelationshipRepository(owner,old,roles,application_version=__version__,caller=CALLER,source_scopes=(SCOPE,),clock=CLOCK).register_rule(record)
        # Legacy, explicitly unadmitted schema fixture is preserved without a history backfill.
        with h.target(db,'migration').connect() as owner:
            with owner.transaction():
                epoch=owner.execute('SELECT revision FROM whattodo.store_epoch FOR UPDATE').fetchone()[0]
                owner.execute('INSERT INTO whattodo.command_transaction VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)',
                    ('legacy-generation-tx','a'*64,'user','USER_COMMAND',first.rule.acceptance_ref,epoch,epoch+1,'legacy-generation-audit',NOW,Jsonb(dict(schema_fixture=True))))
                owner.execute("INSERT INTO whattodo.audit_entry VALUES('legacy-generation-audit','legacy-generation-tx',%s,'legacy',%s)",(rule_sources[first.key],NOW))
                owner.execute("INSERT INTO whattodo.audit_change VALUES('legacy-generation-change','legacy-generation-audit','GENERATION_OCCURRENCE','legacy-generation',NULL,1,NULL,%s,'legacy-generation-tx')",(Jsonb(dict(legacy=True)),))
                owner.execute('''INSERT INTO whattodo.generation_occurrence VALUES
                    ('legacy-generation','rule','1','canonical-source',1,'create-canonical-source','legacy-occurrence','preparation','SEPARATE_TASK',
                    'PENDING',NULL,NULL,NULL,NULL,%s,1,'legacy-generation-tx','legacy-generation-change','GENERATION_OCCURRENCE')''',(Jsonb(dict(legacy=True)),))
                owner.execute("UPDATE whattodo.store_epoch SET revision=%s,last_transaction_ref='legacy-generation-tx'",(epoch+1,))
            before=owner.execute("SELECT * FROM whattodo.generation_occurrence WHERE generation_key='legacy-generation'").fetchone()
            prefix=owner.execute('SELECT * FROM whattodo_meta.migration_history ORDER BY position').fetchall()
            result=apply_migrations(owner,plan,roles=roles,application_version=__version__)
            require(result.applied==('015_generation_occurrences','016_generation_processing','017_stage_commands','018_review_queue','019_review_batches') and owner.execute('SELECT * FROM whattodo_meta.migration_history WHERE position<=15 ORDER BY position').fetchall()==prefix,'GENERATION_UPGRADE_PREFIX')
            after=owner.execute("SELECT * FROM whattodo.generation_occurrence WHERE generation_key='legacy-generation'").fetchone()
            require(after[:len(before)]==before and all(v is None for v in after[len(before):]) and owner.execute('SELECT count(*) FROM whattodo.generation_occurrence_revision').fetchone()==(0,),'GENERATION_LEGACY_BACKFILL')
        checks.append('fifteen_step_upgrade_preserves_exact_receipts_and_legacy_head_without_fabricated_history')
        reader=PostgresTaskRepository(conn,codec,plan,application_version=__version__,clock=CLOCK)
        e=CreationEvent(*conn.execute('SELECT '+EVENT_COLUMNS+' FROM whattodo.canonical_creation_event e WHERE task_id=%s',('canonical-source',)).fetchone())
        task=reader.get('canonical-source',1)
        annotation=conn.execute('SELECT resolved_scope FROM whattodo.authority_record WHERE authority_ref=%s',(e.authority_ref,)).fetchone()[0]['authorization']
        source=GenerationSource(e,task,source_ref,canonical(annotation))
        require(e.authority_ref!=task.aggregate.as_record()['core']['acceptance']['authority_ref'],'GENERATION_ROOT_DERIVATIVE_NOT_DISTINCT')
        defs=PostgresDefinitionRepository(conn,GitDefinitionSource(git.root),plan,roles,application_version=__version__)
        use=AcceptedGenerationRule(first,'user',rule_sources[first.key],NOW);use2=AcceptedGenerationRule(second,'user',rule_sources[second.key],NOW)
        epoch=lambda:conn.execute('SELECT revision FROM whattodo.store_epoch').fetchone()[0]
        p=prepare_generation_commit(codec,source,use,defs,expected_store_revision=epoch(),correlation_ref='native-plan').plan
        require(p.occurrence.state=='PENDING' and len(p.request.writes)==1,'GENERATION_ACTUAL_SOURCE_PLAN')
        checks.append('actual_committed_source_with_distinct_root_and_derivative_authority_constructs_exact_pending_composite')
        patch=FactPatch('patch-source','user','root-patch-source','canonical-source',1,canonical(dict(importance=4)))
        patch_raw=canonical(patch.as_record()).encode();patch_ref=evidence('patch-source',patch_raw,plan)
        patch_grant=FactPatchGrant(patch,patch_ref,NOW,NOW+timedelta(hours=1),NOW)
        with h.target(db,'migration').connect() as owner:register_fact_patch_grant(owner,patch_grant,plan,application_version=__version__)
        patched=PostgresFactPatchHandler(conn,codec,plan,application_version=__version__,clock=CLOCK,grants=(patch_grant,),source_scopes=(SCOPE,)).patch(
            patch_raw,RequestContext('patch-source','schema-fixture'),expected_store_revision=epoch(),audit_id='audit-patch-source',caller=CALLER)
        require(patched.code=='COMMITTED' and reader.get('canonical-source').revision==2,'GENERATION_CURRENT_SOURCE_FIXTURE')
        def counts():return tuple(conn.execute('SELECT count(*) FROM whattodo.'+t).fetchone()[0] for t in ('command_transaction','audit_entry','audit_change','authority_record','generation_occurrence','generation_occurrence_revision'))+(epoch(),)
        def publish(record,*,history=True,head=True,alter_head=False,fail=False):
            # Metadata-only schema fixture; this is not the M3B-05.b Task generator.
            k=record.scope.generation_key;old_head=conn.execute('SELECT runtime_payload FROM whattodo.generation_occurrence WHERE generation_key=%s',(k,)).fetchone()
            with conn.transaction():
                n=conn.execute('SELECT revision FROM whattodo.store_epoch FOR UPDATE').fetchone()[0];tx='schema-'+digest([k,record.revision,n]);aid='audit-'+tx
                w=RecordWrite(AggregateKey('GENERATION_OCCURRENCE',k),record.revision-1 if old_head else None,canonical(record.payload))
                req=CommitRequest(RequestContext(tx,'schema-only'),'user',n,(w,),aid,rule_sources[first.key]);rec=CommitReceipt(tx,req.fingerprint,n+1,aid,(w.key,));permit='permit-'+tx
                conn.execute('INSERT INTO whattodo.authority_record VALUES(%s,%s,%s,%s,%s,%s,%s,%s)',(permit,'user','RELATIONSHIP_RULE',req.source_ref,req.fingerprint,Jsonb(dict(scope_kind='EXACT_TRANSACTION')),NOW,NOW+timedelta(minutes=1)))
                conn.execute('INSERT INTO whattodo.command_transaction VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)',(tx,req.fingerprint,'user','RELATIONSHIP_RULE',permit,n,n+1,aid,NOW,Jsonb(dict(request_id=tx,request_fingerprint=req.fingerprint,store_revision=n+1,audit_id=aid,changed_keys=[dict(kind=w.key.kind,id=k)]))))
                conn.execute('INSERT INTO whattodo.audit_entry VALUES(%s,%s,%s,%s,%s)',(aid,tx,req.source_ref,'schema-only',NOW))
                change='change-'+tx;conn.execute('INSERT INTO whattodo.audit_change VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s)',(change,aid,w.key.kind,k,w.expected_revision,record.revision,Jsonb(old_head[0]) if old_head else None,Jsonb(record.payload),tx))
                row=record.sql_row(tx,change)
                def insert(table,values):
                    conn.execute(sql.SQL('INSERT INTO whattodo.{} ({}) VALUES ({})').format(sql.Identifier(table),sql.SQL(',').join(map(sql.Identifier,values)),sql.SQL(',').join(sql.Placeholder() for _ in values)),tuple(Jsonb(v) if isinstance(v,dict) else v for v in values.values()))
                if history:insert('generation_occurrence_revision',row)
                if head:
                    if alter_head:row=dict(row,runtime_payload=record.payload|dict(manifest=dict(different=True)))
                    if old_head:
                        cols={a:v for a,v in row.items() if a!='generation_key'}
                        conn.execute(sql.SQL('UPDATE whattodo.generation_occurrence SET {} WHERE generation_key=%s').format(sql.SQL(',').join(sql.SQL('{}=%s').format(sql.Identifier(a)) for a in cols)),tuple(Jsonb(v) if isinstance(v,dict) else v for v in cols.values())+(k,))
                    else:insert('generation_occurrence',row)
                conn.execute('UPDATE whattodo.store_epoch SET revision=%s,last_transaction_ref=%s',(n+1,tx))
                if fail:raise HarnessError('GENERATION_INJECTED_ROLLBACK')
        def reject(action,state):
            before=counts()
            try:action()
            except psycopg.Error as exc:require(exc.sqlstate in ((state,) if isinstance(state,str) else state),'GENERATION_UNEXPECTED_SQLSTATE')
            else:require(False,'GENERATION_NEGATIVE_ADMITTED')
            require(counts()==before,'GENERATION_REJECTION_LEAK')
        reject(lambda:publish(replace(p.occurrence,source_task_revision=2)),'23503')
        checks.append('exact_event_fk_rejects_existing_later_task_revision_as_original_creation_source')
        reject(lambda:publish(p.occurrence,history=False),('23503','23514'))
        checks.append('typed_head_cannot_publish_without_matching_immutable_history_and_failure_rolls_back_metadata')
        reject(lambda:publish(p.occurrence,alter_head=True),'23514')
        checks.append('head_and_history_payloads_must_match_exactly_at_commit')
        before=counts()
        try:publish(p.occurrence,fail=True)
        except HarnessError as exc:require(str(exc)=='GENERATION_INJECTED_ROLLBACK','GENERATION_ROLLBACK_CODE')
        require(counts()==before,'GENERATION_STAGED_ROLLBACK_LEAK')
        checks.append('staged_history_head_authority_audit_receipt_and_epoch_roll_back_together')
        publish(p.occurrence)
        pending=GenerationOccurrenceRecord.from_payload(conn.execute('SELECT runtime_payload FROM whattodo.generation_occurrence_revision WHERE generation_key=%s AND revision=1',(p.occurrence.scope.generation_key,)).fetchone()[0])
        require(pending==p.occurrence,'GENERATION_PENDING_ROUNDTRIP')
        checks.append('typed_pending_history_round_trip_retains_exact_provenance_and_missing_facts')
        ready=prepare_generation_commit(codec,source,use2,defs,expected_store_revision=epoch(),previous=pending,correlation_ref='new-version').plan
        reject(lambda:publish(ready.occurrence),'23503')
        checks.append('created_occurrence_cannot_commit_a_nonexistent_target_reference')
        manual(ready.draft.target_id,plan)
        publish(ready.occurrence)
        require(conn.execute('SELECT rule_version,state,revision FROM whattodo.generation_occurrence WHERE generation_key=%s',(pending.scope.generation_key,)).fetchone()==('2','CREATED',2)
            and conn.execute('SELECT runtime_payload FROM whattodo.generation_occurrence_revision WHERE generation_key=%s AND revision=1',(pending.scope.generation_key,)).fetchone()==(pending.payload,),'GENERATION_VERSION_HISTORY')
        checks.append('pending_to_created_new_version_retains_first_immutable_snapshot_and_stable_occurrence')
        reject(lambda:publish(replace(ready.occurrence,revision=3)),'23514')
        checks.append('created_occurrence_is_terminal_and_cannot_publish_a_new_revision')
        for verb in ('UPDATE whattodo.generation_occurrence_revision SET revision=revision','DELETE FROM whattodo.generation_occurrence_revision'):
            reject(lambda:conn.execute(verb),'23514')
        reject(lambda:conn.execute('TRUNCATE whattodo.generation_occurrence_revision'),('23514','0A000','42501'))
        checks.append('application_role_cannot_update_delete_or_truncate_immutable_generation_history')
        require(conn.execute("SELECT count(*) FROM pg_tables WHERE schemaname='whattodo'").fetchone()[0]==89
            and conn.execute("SELECT count(*) FROM pg_constraint c JOIN pg_namespace n ON n.oid=c.connamespace WHERE n.nspname='whattodo' AND c.contype='f'").fetchone()[0]==230,'GENERATION_SCHEMA_COUNTS')
        r.update(schema_version=plan.schema_version,migration_steps=len(plan.steps),domain_tables=89,domain_foreign_keys=230)


def main():
    h=PostgresHarness();r=dict(task='M3B-05.a',status='IN_PROGRESS',scope='SYNTHETIC_COMPOSITE_PLANS_AND_SQL_GUARDS_ONLY',native_checks=[])
    try:
        with h:verify(h,r)
        r.update(status='PASS',native_check_count=len(r['native_checks']),limitations=['No generation runtime or independent generation authority resolution','Metadata-only SQL schema probes reference separately user-created synthetic targets, not automatic counterpart creation','Atomic Task/link/occurrence execution and concurrency are M3B-05.b'])
    except Exception as exc:r.update(status='FAIL',failure_type=type(exc).__name__,failure_code=str(exc) if isinstance(exc,HarnessError) else 'GENERATION_FOUNDATION_NATIVE_FAILED',failure_sqlstate=getattr(exc,'sqlstate',None))
    r['harness']=h.safe_summary();p=h.run_root/'generation-foundation-report.json'
    if h.run_root.exists():p.write_text(json.dumps(r,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(dict(status=r['status'],report=str(p),checks=len(r['native_checks']),server_stopped=r['harness']['server_stopped'])))
    return 0 if r['status']=='PASS' else 1


if __name__=='__main__':raise SystemExit(main())
