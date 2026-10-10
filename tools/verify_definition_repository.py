"""Native Git-to-PostgreSQL definition cache and historical Task probes."""
from dataclasses import replace
import json
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:sys.path.insert(0,str(ROOT))
from src import __version__
from src.adapters.git_definitions import GitDefinitionSource
from src.adapters.migration_files import load_migration_plan
from src.adapters.postgres_definitions import PostgresDefinitionRepository,REGISTRY_LOCK
from src.adapters.postgres_migrations import DatabaseRoles,apply_migrations,verify_schema_compatibility
from src.application.definitions import DefinitionError,DefinitionKey,GitDefinitionRequest,canonical,defaults_from,resolve_task_definitions
from tools.git_definition_fixture import GitDefinitionFixture
from tools.postgres_harness import HarnessError,PostgresHarness,ROLES,require
from tools.verify_toolchain import native_transactions


def envelope(kind,id,version,body):return dict(kind=kind,id=id,version=version,body=body)


def request(commit,path,value):
    from hashlib import sha256
    return GitDefinitionRequest(commit,path,sha256(canonical(value).encode()).hexdigest())


def reject(action,code):
    try:action()
    except DefinitionError as exc:require(str(exc)==code,'DEFINITION_UNEXPECTED_CODE')
    else:raise HarnessError('DEFINITION_NEGATIVE_ACCEPTED')


def verify(harness,report):
    import psycopg
    from psycopg.types.json import Jsonb
    checks=report['native_checks']
    fixture=GitDefinitionFixture(harness.run_root/'git-fixture')
    profile=envelope('COURSE_PROFILE','synthetic-course','1',dict(record_mode='SYNTHETIC',display_name='Synthetic course',unknown_term=True))
    template=envelope('TASK_TEMPLATE','synthetic-template','1',dict(stages=[dict(id='read',weight='1/3'),dict(id='write',weight='2/3')]))
    original=envelope('TASKTYPE','synthetic-work','1',dict(defaults=dict(importance=3,requiredness='REQUIRED',difficulty=dict(thinking_depth=3,repetitive_volume=2,new_learning_load=2),total_estimate_seconds=1800,minimum_session_seconds=1200,fragmentable=True),references=[dict(kind='COURSE_PROFILE',id='synthetic-course',version='1'),dict(kind='TASK_TEMPLATE',id='synthetic-template',version='1')]))
    activity=envelope('ACTIVITY_PROFILE','synthetic-activity','1',dict(record_mode='SYNTHETIC',activity_category='synthetic-category'))
    rule=envelope('RELATIONSHIP_RULE','synthetic-rule','1',dict(references=[dict(kind='TASKTYPE',id='synthetic-work',version='1')],approval='DATA_ONLY_NOT_AUTHORITY'))
    preference=envelope('PREFERENCE','synthetic-preference','1',dict(extra_data=dict(exact_literal='9007199254740993')))
    files={name:canonical(value).encode() for name,value in [('profile.json',profile),('template.json',template),('type.json',original),('activity.json',activity),('rule.json',rule),('preference.json',preference)]}
    commit=fixture.commit_objects(files);source=GitDefinitionSource(fixture.root)
    requests=[request(commit,name,value) for name,value in [('type.json',original),('profile.json',profile),('template.json',template),('activity.json',activity),('rule.json',rule),('preference.json',preference)]]
    # An uncommitted edit must not change an exact-commit import.
    (fixture.root/'type.json').write_text('not the committed definition',encoding='utf-8')
    require(source.read(requests[0]).envelope==original,'DEFINITION_WORKTREE_USED')
    checks.append('exact_commit_blob_ignores_dirty_worktree')
    reject(lambda:source.read(replace(requests[0],commit='f'*40)),'DEFINITION_GIT_OBJECT_UNAVAILABLE')
    reject(lambda:source.read(replace(requests[0],content_hash='f'*64)),'DEFINITION_HASH')
    checks.extend(['missing_git_commit_rejected','wrong_source_hash_rejected'])
    plan=load_migration_plan(root=ROOT)
    old=load_migration_plan(root=ROOT,manifest_path=ROOT/'reports/acceptance/M3A-05-migration-plan.json')
    roles=DatabaseRoles(ROLES['migration'],ROLES['application'],ROLES['test'])
    name=harness.create_database(initialize_schema=False)
    with harness.target(name,'migration').connect() as conn:
        apply_migrations(conn,old,roles=roles,application_version=__version__)
        before=conn.execute('SELECT * FROM whattodo_meta.migration_history ORDER BY position').fetchall()
        upgraded=apply_migrations(conn,plan,roles=roles,application_version=__version__)
        require(upgraded.applied==('006_definition_cache',),'DEFINITION_FORWARD_UPGRADE')
        require(conn.execute('SELECT * FROM whattodo_meta.migration_history WHERE position<=6 ORDER BY position').fetchall()==before,'DEFINITION_OLD_MIGRATIONS_CHANGED')
        checks.append('forward_upgrade_preserves_all_six_old_migration_receipts')
        repo=PostgresDefinitionRepository(conn,source,plan,roles,application_version=__version__)
        records=repo.register(requests)
        require(len(records)==6,'DEFINITION_BUNDLE_IMPORT')
        require(tuple(repo.get(r.key) for r in records)==records,'DEFINITION_ROUNDTRIP')
        checks.append('all_six_kinds_roundtrip_same_versioned_envelope')
        first=records[0];initial=defaults_from(first)
        raw=first.artifact.raw_bytes
        require(repo.register(requests)==records,'DEFINITION_REPLAY_CHANGED_ORIGIN')
        require(first.artifact.request.commit==commit and first.artifact.raw_bytes==raw,'DEFINITION_ORIGIN')
        checks.append('replay_preserves_initial_git_origin_bytes_and_registration_time')
        initial.values['importance']=1
        require(defaults_from(repo.get(first.key)).values['importance']==3,'DEFINITION_MUTABLE_DEFAULT')
        checks.append('defaults_are_detached_immutable_initial_values')
        task_core=dict(task_type_ref=dict(id='synthetic-work',version='1'),context=dict(kind='COURSE',id='synthetic-course'))
        resolved=resolve_task_definitions(repo,task_core,profile_key=DefinitionKey('COURSE_PROFILE','synthetic-course','1'))
        require(len(resolved)==3,'DEFINITION_TRANSITIVE_RESOLUTION')
        checks.append('task_type_profile_and_template_references_resolve_exact_versions')
        reject(lambda:resolve_task_definitions(repo,task_core,profile_key=DefinitionKey('COURSE_PROFILE','synthetic-course','missing')),'DEFINITION_UNRESOLVED_REFERENCE')
        checks.append('task_context_with_unregistered_profile_version_is_rejected')

        native_transactions(conn)
        with conn.transaction():
            conn.execute("INSERT INTO whattodo.command_transaction VALUES('definition-task-create',%s,'principal','USER_COMMAND','authority',2,3,'definition-task-audit',CURRENT_TIMESTAMP,%s)",('e'*64,Jsonb(dict(synthetic=True))))
            conn.execute("INSERT INTO whattodo.audit_entry VALUES('definition-task-audit','definition-task-create','record','synthetic-correlation',CURRENT_TIMESTAMP)")
            conn.execute("INSERT INTO whattodo.task_identity VALUES('old-default-task','definition-task-create',CURRENT_TIMESTAMP)")
            conn.execute("INSERT INTO whattodo.audit_change VALUES('definition-task-change','definition-task-audit','TASK','old-default-task',NULL,1,NULL,%s,'definition-task-create')",(Jsonb(dict(synthetic=True)),))
            conn.execute('''INSERT INTO whattodo.task_revision
                (task_id,revision,title,domain,context_kind,context_id,task_type_ref,acceptance_ref,completion,disposition,requiredness,importance,thinking_depth,repetitive_volume,new_learning_load,audit_change_ref,aggregate_kind,transaction_ref,metadata)
                VALUES('old-default-task',1,'Synthetic historical task','study','COURSE','synthetic-course',%s,'authority','INCOMPLETE','ACTIVE','REQUIRED',3,3,2,2,'definition-task-change','TASK','definition-task-create',%s)''',(first.key.configuration_ref,Jsonb(dict(trust='TRUSTED',overdue='UNKNOWN'))))
            conn.execute("INSERT INTO whattodo.task_head VALUES('old-default-task',1,'definition-task-create')")
            conn.execute("UPDATE whattodo.store_epoch SET revision=3,last_transaction_ref='definition-task-create' WHERE singleton=TRUE AND revision=2")
        task_before=conn.execute("SELECT * FROM whattodo.task_revision WHERE task_id='old-default-task'").fetchall()
        head_before=conn.execute('SELECT * FROM whattodo.task_head').fetchall()
        next_type=envelope('TASKTYPE','synthetic-work','2',dict(defaults=dict(importance=5,total_estimate_seconds=600),references=original['body']['references']))
        changed=envelope('TASKTYPE','synthetic-work','1',dict(defaults=dict(importance=1)))
        absent=envelope('TASKTYPE','unresolved-import','1',dict(references=[dict(kind='COURSE_PROFILE',id='missing-profile',version='1')]))
        second_files={'next.json':canonical(next_type).encode(),'changed.json':canonical(changed).encode(),'absent.json':canonical(absent).encode()}
        second_commit=fixture.commit_objects(second_files)
        new_record,=repo.register([request(second_commit,'next.json',next_type)])
        require(defaults_from(new_record).values['importance']==5 and defaults_from(repo.get(first.key)).values['importance']==3,'DEFINITION_VERSIONED_DEFAULTS')
        require(conn.execute("SELECT * FROM whattodo.task_revision WHERE task_id='old-default-task'").fetchall()==task_before and conn.execute('SELECT * FROM whattodo.task_head').fetchall()==head_before,'DEFINITION_REWROTE_TASK')
        checks.extend(['new_default_version_is_separate_from_old_version','new_defaults_never_rewrite_existing_task_or_head'])
        reject(lambda:repo.register([request(second_commit,'changed.json',changed)]),'DEFINITION_IMMUTABLE_CONFLICT')
        checks.append('same_definition_version_cannot_change_content')
        reject(lambda:repo.register([request(second_commit,'absent.json',absent)]),'DEFINITION_UNRESOLVED_REFERENCE')
        require(conn.execute("SELECT count(*) FROM whattodo.configuration_revision WHERE id='unresolved-import'").fetchone()==(0,),'DEFINITION_PARTIAL_HEADER')
        checks.append('missing_profile_reference_rolls_back_header_body_and_links')
        with harness.target(name,'migration').connect() as second:
            with conn.transaction():
                conn.execute('SELECT pg_advisory_xact_lock(%s)',(REGISTRY_LOCK,))
                contender=PostgresDefinitionRepository(second,source,plan,roles,application_version=__version__)
                reject(lambda:contender.register([requests[0]]),'DEFINITION_IMPORT_BUSY')
        checks.append('concurrent_registry_import_cannot_race_version_registration')
        for table in ['definition_cache','definition_reference']:
            try:
                with conn.transaction():conn.execute('DELETE FROM whattodo.'+table)
            except psycopg.errors.CheckViolation:checks.append(table+'_history_is_immutable')
            else:raise HarnessError('DEFINITION_HISTORY_CHANGED')
        try:
            with conn.transaction():conn.execute("INSERT INTO whattodo.definition_reference VALUES('TASKTYPE','synthetic-work','1',9,'COURSE_PROFILE','unregistered','1')")
        except psycopg.errors.ForeignKeyViolation:checks.append('native_fk_rejects_unregistered_profile_even_without_repository')
        else:raise HarnessError('DEFINITION_NATIVE_FK_ACCEPTED')
        report['cached_versions']=conn.execute('SELECT count(*) FROM whattodo.definition_cache').fetchone()[0]
        report['domain_tables']=conn.execute("SELECT count(*) FROM pg_tables WHERE schemaname='whattodo'").fetchone()[0]
        report['domain_foreign_keys']=conn.execute("SELECT count(*) FROM pg_constraint c JOIN pg_namespace n ON n.oid=c.connamespace WHERE n.nspname='whattodo' AND c.contype='f'").fetchone()[0]
    with harness.target(name).connect() as app:
        verify_schema_compatibility(app,plan,application_version=__version__)
        reader=PostgresDefinitionRepository(app,source,plan,roles,application_version=__version__)
        require(reader.get(first.key).artifact.raw_bytes==raw,'DEFINITION_APPLICATION_READ')
        checks.append('application_can_read_cached_definition')
        for table in ['configuration_revision','definition_cache','definition_reference']:
            try:app.execute('DELETE FROM whattodo.'+table)
            except psycopg.errors.InsufficientPrivilege:checks.append('application_cannot_write_'+table)
            else:raise HarnessError('DEFINITION_APPLICATION_WROTE_CACHE')
    report['synthetic_git_commit']=commit
    report['real_course_activation']='NONE'


def main():
    harness=PostgresHarness();report=dict(task='M3A-06',status='IN_PROGRESS',scope='GIT_BACKED_DEFINITION_CACHE',verified_on='2026-10-10',native_checks=[])
    try:
        with harness:verify(harness,report)
        report.update(status='PASS',native_check_count=len(report['native_checks']),limitations=['Synthetic Git objects and isolated PostgreSQL only','Not a frozen machine Profile/decomposition policy validator','No real profile activation or canonical Task creation handler','No current project Git history, index or remote changed'])
    except Exception as exc:report.update(status='FAIL',failure_type=type(exc).__name__,failure_code=str(exc) if isinstance(exc,(HarnessError,DefinitionError)) else 'DEFINITION_NATIVE_CHECK_FAILED')
    report['harness']=harness.safe_summary()
    target=harness.run_root/'definition-report.json'
    if harness.run_root.exists():target.write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(dict(status=report['status'],report=str(target),checks=len(report['native_checks']),server_stopped=report['harness']['server_stopped'])))
    return 0 if report['status']=='PASS' else 1


if __name__=='__main__':raise SystemExit(main())
