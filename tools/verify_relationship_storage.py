"""Owned PostgreSQL relationship storage; no live rule activation or generator."""
from dataclasses import replace
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:sys.path.insert(0,str(ROOT))
from src import __version__
from src.adapters.clocks import FrozenClock
from src.adapters.git_definitions import GitDefinitionSource
from src.adapters.migration_files import load_migration_plan
from src.adapters.postgres_definitions import PostgresDefinitionRepository
from src.adapters.postgres_migrations import DatabaseRoles,apply_migrations,schema_checked_transaction
from src.adapters.postgres_relationships import PostgresRelationshipRepository
from src.application.definitions import GitDefinitionRequest,canonical
from src.application.evidence_storage import SourceScope
from src.application.relationship_storage import (RelationshipStorageError,EndpointBinding,
    RelationStorageRecord,acceptance_scope,digest)
from src.domain.authorization import CallerIdentity
from src.domain.relationships import Endpoint,TaskRelation
from tools.git_definition_fixture import GitDefinitionFixture
from tools.postgres_harness import PostgresHarness,HarnessError,ROLES,require
from tools.verify_toolchain import native_transactions
from tests.test_relationship_storage import rule_record,relation_record

NOW=datetime(2026,1,1,tzinfo=timezone.utc)


def verify(harness,report):
    import psycopg
    from psycopg.types.json import Jsonb
    checks=report['native_checks'];plan=load_migration_plan(root=ROOT)
    roles=DatabaseRoles(ROLES['migration'],ROLES['application'],ROLES['test'])
    old=replace(plan,steps=plan.steps[:13]);db=harness.create_database(initialize_schema=False)
    with harness.target(db,'migration').connect() as conn:
        apply_migrations(conn,old,roles=roles,application_version=__version__)
        native_transactions(conn)
        prefix=conn.execute('SELECT * FROM whattodo_meta.migration_history ORDER BY position').fetchall()
        result=apply_migrations(conn,plan,roles=roles,application_version=__version__)
        require(result.applied==('013_relationship_storage','014_creation_outbox','015_generation_occurrences','016_generation_processing','017_stage_commands','018_review_queue') and conn.execute('SELECT * FROM whattodo_meta.migration_history WHERE position<=13 ORDER BY position').fetchall()==prefix,'RELATIONSHIP_UPGRADE_PREFIX')
        checks.append('upgrade_preserves_all_thirteen_prior_receipts_and_existing_source_authority')
        fixture=GitDefinitionFixture(harness.run_root/'git-fixture')
        definitions=PostgresDefinitionRepository(conn,GitDefinitionSource(fixture.root),plan,roles,application_version=__version__)
        repo=PostgresRelationshipRepository(conn,plan,roles,application_version=__version__,
            caller=CallerIdentity('principal','USER_COMMAND',True),source_scopes=(SourceScope('spike','scope','synthetic'),),clock=FrozenClock(NOW))

        def import_definitions(records):
            files={str(i)+'.json':canonical(envelope).encode() for i,envelope in enumerate(records)}
            commit=fixture.commit_objects(files)
            return definitions.register(tuple(GitDefinitionRequest(commit,name,digest(json.loads(raw))) for name,raw in files.items()))

        first,second=rule_record(),rule_record('2',active=False)
        import_definitions([dict(kind=k.kind,id=k.id,version=k.version,body={}) for k in (first.source_type,first.target_type,first.template)]+
                           [dict(kind=r.key.kind,id=r.key.id,version=r.key.version,body=r.payload) for r in (first,second)])

        def grant(ref,kind,record,*,principal='principal',scope_override=None,expires=None,source='record'):
            scope=scope_override if scope_override is not None else acceptance_scope(kind,record)
            with conn.transaction():conn.execute('INSERT INTO whattodo.authority_record VALUES(%s,%s,%s,%s,%s,%s,%s,%s)',
                (ref,principal,'USER_COMMAND',source,digest(scope),Jsonb(scope),NOW,expires))

        for r in (first,second):grant(r.rule.acceptance_ref,'RULE',r)
        repo.register_rule(first);require(repo.get_rule('prepare','1')==first,'RELATIONSHIP_RULE_ROUNDTRIP')
        checks.append('exact_git_definition_mapping_versions_and_independent_user_acceptance_round_trip')
        require(repo.register_rule(first)==first,'RELATIONSHIP_RULE_REPLAY')
        checks.append('identical_rule_registration_replays_without_mutating_original_version')

        def reject(action,code):
            try:action()
            except RelationshipStorageError as exc:require(str(exc)==code,'RELATIONSHIP_UNEXPECTED_CODE')
            else:require(False,'RELATIONSHIP_NEGATIVE_ACCEPTED')

        altered=replace(first,rule=replace(first.rule,target_role='changed'))
        reject(lambda:repo.register_rule(altered),'RELATIONSHIP_GIT_DEFINITION_MISMATCH')
        checks.append('same_version_changed_mapping_or_role_fails_without_rewriting_cache')
        for id in ('preparation-task','lab-task'):
            tx='seed-'+id;audit='audit-'+tx;change='change-'+tx
            with conn.transaction():
                epoch=conn.execute('SELECT revision FROM whattodo.store_epoch FOR UPDATE').fetchone()[0]
                conn.execute('INSERT INTO whattodo.command_transaction VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)',(tx,'c'*64,'principal','USER_COMMAND','authority',epoch,epoch+1,audit,NOW,Jsonb(dict(synthetic=True))))
                conn.execute('INSERT INTO whattodo.audit_entry VALUES(%s,%s,%s,%s,%s)',(audit,tx,'record','correlation',NOW))
                conn.execute('INSERT INTO whattodo.audit_change VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s)',(change,audit,'TASK',id,None,1,None,Jsonb(dict(synthetic=True)),tx))
                conn.execute('INSERT INTO whattodo.task_identity VALUES(%s,%s,%s)',(id,tx,NOW))
                conn.execute('''INSERT INTO whattodo.task_revision(task_id,revision,title,domain,acceptance_ref,completion,disposition,
                    requiredness,importance,thinking_depth,repetitive_volume,new_learning_load,audit_change_ref,aggregate_kind,transaction_ref,metadata)
                    VALUES(%s,1,'Synthetic persisted task','study','authority','INCOMPLETE','ACTIVE','REQUIRED',3,3,3,3,%s,'TASK',%s,%s)''',
                    (id,change,tx,Jsonb(dict(trust='UNKNOWN',overdue='UNKNOWN'))))
                conn.execute('UPDATE whattodo.store_epoch SET revision=%s,last_transaction_ref=%s WHERE singleton=TRUE',(epoch+1,tx))
        with conn.transaction():
            conn.execute("INSERT INTO whattodo.stage_identity VALUES('stage','lab-task','seed-lab-task')")
            conn.execute("INSERT INTO whattodo.stage_revision VALUES('stage',1,'lab-task',1,'Synthetic stage','INCOMPLETE',NULL,'authority','seed-lab-task',NULL,NULL)")

        def append(record,tx,*,fail=False,omit_audit=False):
            with schema_checked_transaction(conn,plan,application_version=__version__,read_only=False):
                epoch=conn.execute('SELECT revision FROM whattodo.store_epoch WHERE singleton=TRUE FOR UPDATE').fetchone()[0]
                audit='audit-'+tx;rid=record.relation.relation_id;revision=record.relation.revision
                conn.execute('INSERT INTO whattodo.command_transaction VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)',
                    (tx,record.content_hash,'principal','USER_COMMAND',record.relation.authority_ref,epoch,epoch+1,audit,NOW,Jsonb(dict(synthetic=True))))
                conn.execute('INSERT INTO whattodo.audit_entry VALUES(%s,%s,%s,%s,%s)',(audit,tx,'record','correlation',NOW))
                if not omit_audit:
                    old_value=conn.execute('SELECT runtime_payload FROM whattodo.task_relation_revision WHERE relation_id=%s AND revision=%s',(rid,revision-1)).fetchone()
                    conn.execute('INSERT INTO whattodo.audit_change VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s)',
                        ('change-'+tx,audit,'TASK_RELATION',rid,None if revision==1 else revision-1,revision,
                        None if revision==1 else Jsonb(old_value[0] if old_value else dict(synthetic=True)),Jsonb(record.payload),tx))
                repo.append_relation_in_transaction(record,tx)
                conn.execute('UPDATE whattodo.store_epoch SET revision=%s,last_transaction_ref=%s WHERE singleton=TRUE',(epoch+1,tx))
                if fail:raise RelationshipStorageError('INJECTED_ROLLBACK')

        link=relation_record();grant(link.relation.authority_ref,'RELATION',link)
        reject(lambda:repo.append_relation_in_transaction(link,'not-active'),'RELATIONSHIP_ENCLOSING_TRANSACTION_REQUIRED')
        checks.append('relation_write_requires_enclosing_schema_checked_audited_transaction')
        append(link,'link-create');require(repo.get_relation(link.relation.relation_id)==link,'RELATIONSHIP_LINK_ROUNDTRIP')
        checks.append('generation_lab_to_preparation_and_completion_preparation_before_lab_persist_separately')
        repo.register_rule(second)
        require(repo.get_rule('prepare','1')==first and repo.get_rule('prepare','2')==second and repo.get_relation(link.relation.relation_id)==link,'RELATIONSHIP_VERSION_PRESERVATION')
        checks.append('new_rule_version_preserves_old_rule_and_original_link_origin_without_recreation')
        revised=replace(link,relation=replace(link.relation,revision=2,kind='START_PREREQUISITE',authority_ref='revised-authority'))
        grant('revised-authority','RELATION',revised);append(revised,'revised-link')
        require(repo.get_relation(link.relation.relation_id,1)==link and repo.get_relation(link.relation.relation_id)==revised,
                'RELATIONSHIP_LINK_HISTORY')
        checks.append('new_concrete_link_revision_retains_exact_prior_payload_and_changes_only_latest_projection')

        missing=Endpoint('TASK','missing');bad=replace(link,relation=replace(link.relation,relation_id='bad',after=missing,authority_ref='bad-authority'),after=EndpointBinding(missing,'missing',1))
        grant('bad-authority','RELATION',bad)
        reject(lambda:append(bad,'bad-target'),'RELATIONSHIP_TARGET_NOT_OWNED')
        require(repo.get_relation('bad') is None and conn.execute("SELECT count(*) FROM whattodo.command_transaction WHERE request_id='bad-target'").fetchone()==(0,),'RELATIONSHIP_INVALID_TARGET_ROLLBACK')
        checks.append('missing_target_rejected_and_enclosing_receipt_audit_and_link_roll_back')

        soft=replace(link,relation=replace(link.relation,relation_id='soft',kind='SOFT_SEQUENCE',authority_ref='soft-authority',origin_rule_id=None,origin_rule_version=None))
        grant('soft-authority','RELATION',soft);append(soft,'soft-create')
        require(repo.get_relation('soft').relation.kind=='SOFT_SEQUENCE','RELATIONSHIP_SOFT_TYPE')
        checks.append('soft_sequence_remains_explicit_and_has_no_generation_origin_or_hard_edge_conversion')
        parent,stage=Endpoint('TASK','lab-task'),Endpoint('STAGE','stage')
        membership=RelationStorageRecord(TaskRelation('member',1,'STAGE_MEMBERSHIP',parent,stage,'member-authority'),
            EndpointBinding(parent,'lab-task',1),EndpointBinding(stage,'lab-task',1,1))
        grant('member-authority','RELATION',membership);append(membership,'member-create')
        require(repo.get_relation('member')==membership,'RELATIONSHIP_MEMBERSHIP_ROUNDTRIP')
        checks.append('stage_membership_binds_exact_existing_parent_task_and_stage_revisions')

        stale=replace(link,relation=replace(link.relation,revision=4,authority_ref='stale-authority'))
        grant('stale-authority','RELATION',stale);reject(lambda:append(stale,'stale-link'),'RELATIONSHIP_STALE_REVISION')
        checks.append('skipped_relation_revision_fails_without_changing_original_history')
        wrong=replace(soft,relation=replace(soft.relation,relation_id='wrong',authority_ref='wrong-authority'))
        grant('wrong-authority','RELATION',wrong,scope_override=dict(relationship_storage=dict(kind='RULE',payload_hash=wrong.content_hash)))
        reject(lambda:append(wrong,'wrong-scope'),'RELATIONSHIP_AUTHORITY_SCOPE_MISMATCH')
        checks.append('authority_reference_with_wrong_exact_effect_scope_cannot_authorize_link')
        expired=replace(soft,relation=replace(soft.relation,relation_id='expired',authority_ref='expired-authority'))
        grant('expired-authority','RELATION',expired,expires=NOW+timedelta(seconds=1))
        later=PostgresRelationshipRepository(conn,plan,roles,application_version=__version__,caller=repo.caller,source_scopes=repo.scopes,clock=FrozenClock(NOW+timedelta(seconds=2)))
        with schema_checked_transaction(conn,plan,application_version=__version__,read_only=False):
            reject(lambda:later.append_relation_in_transaction(expired,'unused'),'RELATIONSHIP_AUTHORITY_SCOPE_MISMATCH')
        checks.append('expired_acceptance_cannot_authorize_a_new_relation')
        unaudited=replace(soft,relation=replace(soft.relation,relation_id='unaudited',authority_ref='unaudited-authority'))
        grant('unaudited-authority','RELATION',unaudited);reject(lambda:append(unaudited,'no-audit',omit_audit=True),'RELATIONSHIP_AUDIT_REQUIRED')
        checks.append('matching_receipt_without_exact_relationship_audit_is_rejected')
        rolled=replace(soft,relation=replace(soft.relation,relation_id='rolled',authority_ref='rolled-authority'))
        grant('rolled-authority','RELATION',rolled);epoch=conn.execute('SELECT revision FROM whattodo.store_epoch').fetchone()
        reject(lambda:append(rolled,'rolled-link',fail=True),'INJECTED_ROLLBACK')
        require(repo.get_relation('rolled') is None and conn.execute('SELECT revision FROM whattodo.store_epoch').fetchone()==epoch,'RELATIONSHIP_ATOMIC_ROLLBACK')
        checks.append('failure_after_actual_link_insert_rolls_back_link_epoch_receipt_and_audit')

        foreign=PostgresRelationshipRepository(conn,plan,roles,application_version=__version__,caller=CallerIdentity('other','USER_COMMAND',True),source_scopes=repo.scopes,clock=FrozenClock(NOW))
        reject(lambda:foreign.get_relation(link.relation.relation_id),'RELATIONSHIP_FOREIGN_PRINCIPAL')
        reject(lambda:foreign.get_rule('prepare','1'),'RELATIONSHIP_FOREIGN_PRINCIPAL')
        checks.append('foreign_principal_cannot_read_owned_rules_or_links')
        wrong_scope=PostgresRelationshipRepository(conn,plan,roles,application_version=__version__,caller=repo.caller,
            source_scopes=(SourceScope('spike','scope','another-account'),),clock=FrozenClock(NOW))
        reject(lambda:wrong_scope.get_rule('prepare','1'),'RELATIONSHIP_FOREIGN_SOURCE_SCOPE')
        reject(lambda:wrong_scope.get_relation(link.relation.relation_id),'RELATIONSHIP_FOREIGN_SOURCE_SCOPE')
        with schema_checked_transaction(conn,plan,application_version=__version__,read_only=False):
            reject(lambda:wrong_scope.append_relation_in_transaction(link,'unused'),'RELATIONSHIP_AUTHORITY_SCOPE_MISMATCH')
        checks.append('same_principal_wrong_account_scope_cannot_read_or_append_relationships')
        for table in ('relationship_rule_revision','task_relation_revision'):
            for query in ('DELETE FROM whattodo.'+table,'UPDATE whattodo.'+table+' SET runtime_payload=runtime_payload'):
                try:
                    with conn.transaction():conn.execute(query)
                except psycopg.Error as exc:require(exc.sqlstate=='23514','RELATIONSHIP_HISTORY_SQLSTATE')
                else:require(False,'RELATIONSHIP_HISTORY_MUTATED')
        checks.append('rule_and_link_history_reject_sql_updates_and_deletes')
        report.update(migration_steps=len(plan.steps),schema_version=plan.schema_version,
            domain_tables=conn.execute("SELECT count(*) FROM pg_tables WHERE schemaname='whattodo'").fetchone()[0],
            domain_foreign_keys=conn.execute("SELECT count(*) FROM pg_constraint c JOIN pg_namespace n ON n.oid=c.connamespace WHERE n.nspname='whattodo' AND c.contype='f'").fetchone()[0])
        require((report['domain_tables'],report['domain_foreign_keys'])==(87,221),'RELATIONSHIP_SCHEMA_COUNTS')


def main():
    harness=PostgresHarness();report=dict(task='M3B-01',status='IN_PROGRESS',native_checks=[],scope='SYNTHETIC_OWNER_ONLY_TYPED_STORAGE')
    try:
        with harness:verify(harness,report)
        report.update(status='PASS',native_check_count=len(report['native_checks']),limitations=['No live personal rules, command endpoint or automatic generation','Enclosing coordinator owns receipt/audit/store-epoch publication; this port does not certify graph feasibility'])
    except Exception as exc:report.update(status='FAIL',failure_type=type(exc).__name__,failure_code=str(exc) if isinstance(exc,(HarnessError,RelationshipStorageError)) else 'RELATIONSHIP_NATIVE_FAILED',failure_sqlstate=getattr(exc,'sqlstate',None))
    report['harness']=harness.safe_summary();path=harness.run_root/'relationship-storage-report.json'
    if harness.run_root.exists():path.write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(dict(status=report['status'],report=str(path),checks=len(report['native_checks']),server_stopped=report['harness']['server_stopped'])))
    return 0 if report['status']=='PASS' else 1


if __name__=='__main__':raise SystemExit(main())
