"""Actual custom-format backup/restore of synthetic prototype state."""
from copy import deepcopy
from dataclasses import replace
from datetime import datetime,timedelta,timezone
from hashlib import sha256
from pathlib import Path
from unittest.mock import patch
from uuid import uuid4
import json
import os
import shutil
import sys
ROOT=Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:sys.path.insert(0,str(ROOT))
from src import __version__
from src.adapters.clocks import FrozenClock
from src.adapters.extension_contracts import load_supported_schemas
from src.adapters.git_definitions import GitDefinitionSource
from src.adapters.migration_files import load_migration_plan
from src.adapters.postgres_authorization import register_grant
from src.adapters.postgres_definitions import PostgresDefinitionRepository
from src.adapters.postgres_evidence import PostgresEvidenceRepository,register_source_scope
from src.adapters.postgres_fact_patches import PostgresFactPatchHandler,register_fact_patch_grant
from src.adapters.postgres_lifecycle import PostgresLifecycleHandler
from src.adapters.postgres_manual_tasks import PostgresManualTaskHandler
from src.adapters.postgres_migrations import DatabaseRoles,apply_migrations,schema_checked_transaction
from src.adapters.postgres_read_models import PostgresReadService
from src.adapters.postgres_review_batches import PostgresReviewBatchHandler,register_review_batch_grant
from src.adapters.postgres_review_service import PostgresReviewQueueService
from src.adapters.postgres_resolution import PostgresResolutionService
from src.adapters.postgres_tasks import PostgresTaskRepository
from src.adapters.postgres_transactions import PostgresTransactionCoordinator
from src.adapters.postgres_work_reports import PostgresWorkReportHandler,register_work_report_grant
from src.adapters.prototype_codec import PrototypeJSONCodec
from src.adapters.runtime_config import load_runtime_config
from src.application.definitions import DefinitionKey,canonical
from src.application.direct_creation import DirectCreationNormalizer,UserInputBinding,guided_message
from src.application.evidence_storage import SourceScope
from src.application.fact_patches import FactPatch,FactPatchGrant
from src.application.manual_tasks import ResolvedManualIntent
from src.application.ports import RequestContext
from src.application.review_batches import BatchMember,ReviewBatchCommand,ReviewBatchGrant
from src.application.review_queue import ReviewQueueQuery
from src.application.work_reports import admit_work_report,WorkReportGrant
from src.domain.authorization import AuthorityGrant,CallerIdentity,Command,change
from src.domain.provenance import capture_source,make_candidate
from tools.development_backup import BackupBundle,BackupError,create_backup,restore_backup,validate_restored,checked_bundle,inventory,run_pg
from tools.git_definition_fixture import GitDefinitionFixture
from tools.postgres_harness import HarnessError,PostgresHarness,ROLES,require
from tools.verify_definition_repository import request as definition_request
NOW=datetime(2026,1,1,tzinfo=timezone.utc);CLOCK=FrozenClock(NOW);CALLER=CallerIdentity('principal','USER_COMMAND',True)
SCOPE=SourceScope('synthetic-backup','scope','account');KEY=b'synthetic-backup-read-key-00000001';SECRET='synthetic-credential-value-never-exported-0001'
DIMS=dict(thinking_depth=2,repetitive_volume=3,new_learning_load=2)

def verify(harness,report):
    import psycopg
    plan=load_migration_plan(root=ROOT);codec=PrototypeJSONCodec(load_supported_schemas(root=ROOT));checks=report['native_checks'];options=dict(application_version=__version__,clock=CLOCK);roles=DatabaseRoles(ROLES['migration'],ROLES['application'],ROLES['test'])
    source_db=harness.create_database(initialize_schema=False)
    fixture=GitDefinitionFixture(harness.run_root/'git-fixture');profile=dict(kind='COURSE_PROFILE',id='synthetic-backup-course',version='1',body=dict(record_mode='SYNTHETIC'));commit=fixture.commit_objects({'profile.json':canonical(profile).encode()});git=GitDefinitionSource(fixture.root)
    with harness.target(source_db,'migration').connect() as owner:
        apply_migrations(owner,plan,roles=roles,application_version=__version__);register_source_scope(owner,plan,roles,SCOPE,**options)
        PostgresDefinitionRepository(owner,git,plan,roles,application_version=__version__).register((definition_request(commit,'profile.json',profile),))
    config_value=json.loads((ROOT/'config/runtime.example.json').read_text(encoding='utf-8'));config_value['adapters']['state_store']=dict(mode='LIVE',secret_env='WHATTODO_SYNTHETIC_BACKUP_SECRET');config_value['definitions']=[dict(kind=profile['kind'],id=profile['id'],version=profile['version'],path='profile.json',content_hash=sha256(canonical(profile).encode()).hexdigest())]
    config_file=harness.run_root/'configuration.json';config_file.write_text(canonical(config_value),encoding='utf-8');(harness.run_root/'profile.json').write_text(canonical(profile),encoding='utf-8');config=load_runtime_config(config_file,env={'WHATTODO_SYNTHETIC_BACKUP_SECRET':SECRET})
    with harness.target(source_db).connect() as conn:
        repo=PostgresEvidenceRepository(conn,codec,plan,**options,scopes=(SCOPE,));reader=PostgresTaskRepository(conn,codec,plan,**options);definitions=PostgresDefinitionRepository(conn,git,plan,roles,application_version=__version__)
        def epoch():return conn.execute('SELECT revision FROM whattodo.store_epoch').fetchone()[0]
        def source(name,raw,kind='USER'):
            s=capture_source(provider=SCOPE.provider,scope_ref=SCOPE.scope_ref,external_id=name,raw_bytes=raw,captured_at=NOW,source_type=kind);repo.observe_source(canonical(s.as_record()).encode(),raw_content=raw,locator_ref='synthetic-'+name);return s
        def grant(c,ref,database=source_db):
            g=AuthorityGrant(c.authority_ref,c.principal_id,c.origin,c.command_id,c.changes,ref,NOW-timedelta(minutes=1),expires_at=NOW+timedelta(hours=1))
            with harness.target(database,'migration').connect() as owner:register_grant(owner,g,plan,application_version=__version__)
            return g
        def create(name,partial=False):
            fields=dict(title='Synthetic '+name,importance=3,requiredness='REQUIRED',difficulty=DIMS,user_remaining_seconds=600)
            if partial:fields=dict(title='Partial creation')
            c=Command('create-'+name,'principal','USER_COMMAND','root-'+name,(change(name,None,'CREATE_TASK',fields),));ref=source(c.command_id,canonical(c.as_record()).encode()).record_id;g=grant(c,ref);intent=ResolvedManualIntent(c.fingerprint,ref,NOW,canonical({} if partial else dict(domain='study',total_estimate_seconds=1800)))
            out=PostgresManualTaskHandler(conn,codec,plan,**options,definitions=definitions,grants=(g,),source_scopes=(SCOPE,),intents=(intent,)).create(canonical(c.as_record()).encode(),RequestContext(c.command_id,'backup-correlation'),expected_store_revision=epoch(),audit_id='audit-'+c.command_id,caller=CALLER);require(out.code==('PENDING_DETAILS' if partial else 'COMMITTED'),'BACKUP_FIXTURE_CREATE_'+out.code);return c
        create('a');create('b');create('partial',True)
        p=FactPatch('patch-a','principal','root-patch-a','a',1,canonical(dict(deadline='2026-01-03T13:30:00.123456+08:00',importance=4)));ref=source(p.command_id,canonical(p.as_record()).encode()).record_id;pg=FactPatchGrant(p,ref,NOW,NOW+timedelta(hours=1),NOW)
        with harness.target(source_db,'migration').connect() as owner:register_fact_patch_grant(owner,pg,plan,application_version=__version__)
        out=PostgresFactPatchHandler(conn,codec,plan,**options,grants=(pg,),source_scopes=(SCOPE,)).patch(canonical(p.as_record()).encode(),RequestContext(p.command_id,'backup-correlation'),expected_store_revision=epoch(),audit_id='audit-patch-a',caller=CALLER);require(out.code=='COMMITTED','BACKUP_FIXTURE_PATCH_'+out.code)
        w=dict(schema_version='0.1.0-work-report',command_id='work-a',principal_id='principal',origin='USER_COMMAND',authority_ref='root-work-a',observation_id='actual-a',target_ref=dict(task_id='a',revision=2),mode='INCREMENT',seconds=900,stage_id=None,session_started_at=None,session_ended_at=None);wr=admit_work_report(codec,canonical(w).encode());ref=source(wr.command_id,canonical(w).encode()).record_id;wg=WorkReportGrant(wr,ref,NOW,NOW+timedelta(hours=1))
        with harness.target(source_db,'migration').connect() as owner:register_work_report_grant(owner,wg,plan,application_version=__version__)
        out=PostgresWorkReportHandler(conn,codec,plan,**options,grants=(wg,),source_scopes=(SCOPE,)).report(canonical(w).encode(),RequestContext(wr.command_id,'backup-correlation'),expected_store_revision=epoch(),audit_id='audit-work-a',caller=CALLER);require(out.code=='COMMITTED','BACKUP_FIXTURE_WORK_'+out.code)
        complete=Command('complete-a','principal','USER_COMMAND','root-complete-a',(change('a',3,'UPDATE_TASK',dict(completion='COMPLETE')),));ref=source(complete.command_id,canonical(complete.as_record()).encode()).record_id;g=grant(complete,ref);old_epoch=epoch()
        out=PostgresLifecycleHandler(conn,codec,plan,**options,grants=(g,),source_scopes=(SCOPE,)).complete(canonical(complete.as_record()).encode(),RequestContext(complete.command_id,'backup-correlation'),expected_store_revision=old_epoch,audit_id='audit-complete-a',caller=CALLER);require(out.code=='COMMITTED','BACKUP_FIXTURE_COMPLETE_'+out.code);original_receipt=out.value
        cancel=Command('cancel-a','principal','USER_COMMAND','root-cancel-a',(change('a',4,'UPDATE_TASK',dict(disposition='CANCELLED')),));ref=source(cancel.command_id,canonical(cancel.as_record()).encode()).record_id;g=grant(cancel,ref)
        out=PostgresLifecycleHandler(conn,codec,plan,**options,grants=(g,),source_scopes=(SCOPE,)).cancel(canonical(cancel.as_record()).encode(),RequestContext(cancel.command_id,'backup-correlation'),expected_store_revision=epoch(),audit_id='audit-cancel-a',caller=CALLER);require(out.code=='COMMITTED','BACKUP_FIXTURE_CANCEL_'+out.code)
        candidate_source=source('candidate',b'Synthetic external evidence','EMAIL');candidate=make_candidate(candidate_source,parser_version='synthetic-parser',action='CREATE_TASK',proposed_fields=dict(title='Synthetic proposal'),confidence='0.8');repo.observe_candidate(canonical(candidate.as_record()).encode());repo.observe_source(canonical(replace(candidate_source,source_timestamp=NOW).as_record()).encode(),raw_content=b'Synthetic external evidence',locator_ref='synthetic-conflict')
        raw=guided_message(dict(title='Synthetic unanswered followup'));s=source('followup',raw);bindings=(UserInputBinding('principal',SCOPE),);proposal=DirectCreationNormalizer(codec,clock=CLOCK,bindings=bindings).guided(raw,s,caller=CALLER)
        frame=PostgresResolutionService(conn,codec,plan,**options,input_bindings=bindings).begin_creation(proposal,RequestContext('followup-command','backup-correlation'),session_id='followup-session',desired_task_id='followup-task',caller=CALLER);require(frame.status=='SUCCESS','BACKUP_FIXTURE_FRAME_'+frame.code)
        q=dict(schema_version='0.1.0-read-query',view='TASKS',task_id=None,filters=dict(completion=None,disposition=None,trust=None,domain=None,context=None),pending_kind=None,include_closed=False,page_size=1,cursor=None)
        pages=PostgresReadService(conn,codec,plan,**options,cursor_key=KEY,scopes=(SCOPE,));first=pages.query(canonical(q).encode(),RequestContext('read','backup-correlation'),caller=CALLER);require(first.status=='SUCCESS' and first.value.as_record()['has_more'],'BACKUP_FIXTURE_READ');cursor=first.value.as_record()['next_cursor'];original_tasks={key:reader.get(key) for key in ('a','b')};original_history=[reader.get('a',r) for r in range(1,6)]
        checks.append('synthetic_fixture_contains_real_create_patch_actual_work_complete_cancel_audits_receipts_due_u_definitions_evidence_pending_clarification_and_read_snapshot_history')
        review_query=ReviewQueueQuery(1,1)
        review_service=PostgresReviewQueueService(conn,codec,plan,**options,cursor_key=KEY,source_scopes=(SCOPE,),definitions=definitions)
        review_first=review_service.query(canonical(review_query.as_record()).encode(),RequestContext('review-backup','review-backup'),caller=CALLER)
        require(review_first.status=='SUCCESS' and review_first.value['total_items']>=5
            and review_first.value['next_cursor'] is not None,'BACKUP_REVIEW_CAPTURE_'+review_first.code)
        review_cursor=review_first.value['next_cursor']
        review_second=review_service.query(canonical(replace(review_query,cursor=review_cursor).as_record()).encode(),
            RequestContext('review-backup-next','review-backup'),caller=CALLER)
        require(review_second.status=='SUCCESS','BACKUP_REVIEW_SECOND_'+review_second.code)
        original_run=run_pg;capture=dict(calls=0);captured_epoch=epoch()
        batch_record=reader.get('b');batch_estimate=batch_record.aggregate.as_record()['effort']['user_remaining']
        batch_command=ReviewBatchCommand('batch-b','principal','root-batch-b','review-backup',1,'statement-batch-b',
            'batch-b',True,(BatchMember('b',batch_record.revision,batch_estimate['observation_id'],batch_estimate['seconds']),))
        batch_source=source(batch_command.command_id,canonical(batch_command.as_record()).encode()).record_id
        batch_grant=ReviewBatchGrant(batch_command,batch_source,NOW-timedelta(minutes=1),NOW)
        with harness.target(source_db,'migration').connect() as owner:
            register_review_batch_grant(owner,batch_grant,plan,application_version=__version__)
        batch_out=PostgresReviewBatchHandler(conn,codec,plan,**options,grants=(batch_grant,)).confirm(
            canonical(batch_command.as_record()).encode(),RequestContext(batch_command.command_id,'backup-correlation'),
            expected_store_revision=epoch(),audit_id='audit-batch-b',caller=CALLER)
        require(batch_out.status=='SUCCESS' and batch_out.code=='REVIEW_BATCH_CONFIRMED','BACKUP_FIXTURE_BATCH_'+batch_out.code)
        original_batch_receipt=batch_out.value.receipt;captured_epoch=epoch()
        def interleaved(h,tool,args,**kw):
            if tool=='pg_dump':
                require(any(str(a).startswith('--snapshot=') for a in args),'BACKUP_NO_EXPORTED_SNAPSHOT');create('concurrent');capture['calls']+=1
            return original_run(h,tool,args,**kw)
        with patch('tools.development_backup.run_pg',side_effect=interleaved),patch.dict(os.environ,WHATTODO_SYNTHETIC_BACKUP_SECRET=SECRET,OPENAI_API_KEY=SECRET):
            bundle=create_backup(harness,source_db,plan=plan,application_version=__version__,config=config,clock=CLOCK)
        require(capture['calls']==1 and epoch()==captured_epoch+1 and reader.get('concurrent') is not None,'BACKUP_CONCURRENT_FIXTURE')
        manifest,refs=checked_bundle(harness,bundle,plan,__version__);require(manifest['inventory']['store_revision']==captured_epoch,'BACKUP_MIXED_SNAPSHOT');checks.append('archive_and_all_row_catalog_digests_share_one_exported_snapshot_even_when_another_connection_commits_during_capture')
        require(refs['adapters']['state_store']['secret_env']=='WHATTODO_SYNTHETIC_BACKUP_SECRET' and refs['definitions'][0]['content_hash']==sha256(canonical(profile).encode()).hexdigest() and SECRET not in canonical(refs),'BACKUP_CONFIG_SECRET')
        plain=harness.run_root/'inspection.sql';run_pg(harness,'pg_restore',['--file='+str(plain),str(bundle.path/'database.dump')]);dump_text=plain.read_text(encoding='utf-8');plain.unlink()
        require(SECRET not in dump_text and all(p not in dump_text for p in harness._passwords.values()) and 'CREATE ROLE' not in dump_text and 'ALTER ROLE' not in dump_text,'BACKUP_ROLE_OR_CREDENTIAL_EXPORT');checks.append('bundle_has_only_database_archive_manifest_and_hash_pinned_definition_adapter_secret_references_without_source_role_or_provider_credential_values')
        before_source=None
        with harness.target(source_db,'migration').connect() as owner:
            with schema_checked_transaction(owner,plan,application_version=__version__):before_source=inventory(owner)
        target_db=harness.create_database(initialize_schema=False)
        restored=restore_backup(harness,target_db,bundle,plan=plan,application_version=__version__)
        require(restored['status']=='VERIFIED' and restored['tables_checked']==92,'BACKUP_RESTORE_COUNTS');checks.append('actual_custom_archive_restores_all_89_domain_and_three_metadata_tables_and_catalog_constraints_functions_triggers_privileges_and_sequence_state_into_separate_empty_database')
        with harness.target(source_db,'migration').connect() as owner:
            with schema_checked_transaction(owner,plan,application_version=__version__):require(inventory(owner)==before_source,'BACKUP_SOURCE_RESTORE_MUTATED')
        checks.append('original_source_database_and_its_concurrent_postsnapshot_task_are_preserved_byte_for_byte_during_restore')
        with harness.target(target_db).connect() as restored_conn:
            restored_reader=PostgresTaskRepository(restored_conn,codec,plan,**options)
            require(all(restored_reader.get(k)==v for k,v in original_tasks.items()) and restored_reader.get('concurrent') is None and [restored_reader.get('a',r) for r in range(1,6)]==original_history,'BACKUP_TASK_HISTORY')
            v=restored_reader.get('a').aggregate.as_record();require(v['core']['completion']=='COMPLETE' and v['core']['disposition']=='CANCELLED' and v['effort']['user_remaining']['seconds']==0 and v['work']['total_estimate']['seconds']==1800 and restored_conn.execute("SELECT sum(seconds) FROM whattodo.effort_observation WHERE kind='ACTUAL_WORK'").fetchone()==(900,),'BACKUP_DIMENSIONS')
            require(v['timing']['deadline']['value']['original_value']=='2026-01-03T13:30:00.123456+08:00','BACKUP_DUE_PRECISION');checks.append('restored_current_and_historical_task_bytes_keep_completion_cancel_zero_u_original_total_actual_work_and_original_due_offset_microseconds_independent')
            commit_lookup=PostgresTransactionCoordinator(restored_conn,codec,plan,**options).lookup_commit(RequestContext(complete.command_id,'after-restore'),caller=CALLER);require(commit_lookup.code=='COMMIT_FOUND' and commit_lookup.value==original_receipt,'BACKUP_LEDGER_LOOKUP_'+commit_lookup.code)
            replay=PostgresLifecycleHandler(restored_conn,codec,plan,**options).complete(canonical(complete.as_record()).encode(),RequestContext(complete.command_id,'after-restore'),expected_store_revision=old_epoch,audit_id='audit-complete-a',caller=CALLER);require(replay.code=='REPLAY' and replay.value==original_receipt,'BACKUP_REPLAY_'+replay.code);checks.append('restored_receipt_lookup_and_original_completion_retry_validate_owned_audits_and_return_original_commit_without_live_grants_or_duplicate_publication')
            restored_page=PostgresReadService(restored_conn,codec,plan,**options,cursor_key=KEY,scopes=(SCOPE,)).query(canonical(dict(q,cursor=cursor)).encode(),RequestContext('read-restored','backup-correlation'),caller=CALLER);require(restored_page.status=='SUCCESS' and restored_page.value.as_record()['items'][0]['id']=='b','BACKUP_CURSOR_RESTORE');checks.append('retained_read_cursor_continues_original_snapshot_after_restore_with_independently_rebound_key_without_exporting_that_key')
            restored_reviews=PostgresReviewQueueService(restored_conn,codec,plan,**options,cursor_key=KEY,source_scopes=(SCOPE,))
            review_replay=restored_reviews.query(canonical(review_query.as_record()).encode(),RequestContext('review-backup','review-restored'),caller=CALLER)
            review_next=restored_reviews.query(canonical(replace(review_query,cursor=review_cursor).as_record()).encode(),
                RequestContext('review-restored-next','review-restored'),caller=CALLER)
            require(review_replay.status=='SUCCESS' and review_next.status=='SUCCESS'
                and review_replay.value==review_first.value and review_next.value==review_second.value
                and not review_next.value['personal_reconciliation_complete'],'BACKUP_REVIEW_REPLAY')
            require(restored_conn.execute('SELECT count(*) FROM whattodo.review_queue_snapshot').fetchone()==(1,)
                and restored_conn.execute('SELECT count(*) FROM whattodo.review_queue_entry').fetchone()==(review_first.value['total_items'],),
                'BACKUP_REVIEW_DUPLICATE_OR_LOST_ENTRY')
            checks.append('nonempty_complete_review_header_entries_and_original_request_replay_signed_cursor_unanswered_state_survive_actual_separate_database_restore')
            restored_batch=PostgresReviewBatchHandler(restored_conn,codec,plan,**options,grants=(batch_grant,)).confirm(
                canonical(batch_command.as_record()).encode(),RequestContext(batch_command.command_id,'batch-restored'),
                expected_store_revision=original_batch_receipt.store_revision-1,audit_id='audit-batch-b',caller=CALLER)
            require(restored_batch.status=='SUCCESS' and restored_batch.code=='REVIEW_BATCH_REPLAYED'
                and restored_batch.value.receipt==original_batch_receipt
                and restored_conn.execute('SELECT count(*) FROM whattodo.review_batch_confirmation').fetchone()==(1,)
                and restored_conn.execute('SELECT count(*) FROM whattodo.review_batch_verification').fetchone()==(1,)
                and restored_conn.execute("SELECT count(*) FROM whattodo.effort_observation WHERE kind='UNCHANGED_VERIFICATION'").fetchone()==(1,),
                'BACKUP_BATCH_RESTORE_'+restored_batch.code)
            checks.append('restored_batch_confirmation_verification_and_unchanged_observation_replay_without_duplicates')
            definition=PostgresDefinitionRepository(restored_conn,git,plan,roles,application_version=__version__).get(DefinitionKey(profile['kind'],profile['id'],profile['version']));require(definition is not None and definition.body==profile['body'],'BACKUP_DEFINITION_RESTORE')
            pending=PostgresReadService(restored_conn,codec,plan,**options,cursor_key=KEY,scopes=(SCOPE,)).query(canonical(dict(q,view='PENDING',page_size=100)).encode(),RequestContext('pending-restored','backup-correlation'),caller=CALLER);require(pending.status=='SUCCESS' and {i['kind'] for i in pending.value.as_record()['items']}=={'MANUAL_CREATION','EVIDENCE_CANDIDATE','EVIDENCE_CONFLICT','CLARIFICATION'},'BACKUP_PENDING_RESTORE');checks.append('restored_exact_definition_cache_source_candidate_conflict_manual_pending_and_unanswered_clarification_remain_readable_without_activation')
        for role,sql in [('application',"INSERT INTO whattodo.source_scope VALUES('blocked','blocked','blocked',CURRENT_TIMESTAMP)"),('test',"UPDATE whattodo.store_epoch SET revision=revision")]:
            with harness.target(target_db,role).connect() as denied:
                try:denied.execute(sql)
                except psycopg.Error as exc:require(exc.sqlstate=='42501','BACKUP_RESTORED_ROLE_POLICY')
                else:raise HarnessError('BACKUP_RESTORED_PRIVILEGE_EXPANSION')
        checks.append('restored_application_cannot_register_source_accounts_and_verifier_cannot_mutate_store_state')
        try:restore_backup(harness,source_db,bundle,plan=plan,application_version=__version__)
        except BackupError as exc:require(str(exc)=='BACKUP_SOURCE_OVERWRITE_DENIED','BACKUP_SOURCE_REJECTION')
        else:raise HarnessError('BACKUP_OVERWROTE_SOURCE')
        try:restore_backup(harness,target_db,bundle,plan=plan,application_version=__version__)
        except BackupError as exc:require(str(exc)=='BACKUP_EMPTY_TARGET_REQUIRED','BACKUP_NONEMPTY_REJECTION')
        else:raise HarnessError('BACKUP_OVERWROTE_EXISTING_TARGET')
        checks.append('source_and_already_restored_target_are_rejected_before_any_clean_create_or_restore_overwrite')
        def clone():
            root=harness.run_root/('backup_'+uuid4().hex);root.mkdir()
            for p in bundle.path.iterdir():shutil.copyfile(p,root/p.name)
            return BackupBundle(root,bundle.manifest_hash)
        corrupt=clone();p=corrupt.path/'database.dump';raw=p.read_bytes();p.write_bytes(raw[:-1]+bytes([raw[-1]^1]));empty_db=harness.create_database(initialize_schema=False)
        with patch('tools.development_backup.run_pg',side_effect=HarnessError('BACKUP_CORRUPT_ENTERED_CLIENT')):
            try:restore_backup(harness,empty_db,corrupt,plan=plan,application_version=__version__)
            except BackupError as exc:require(str(exc)=='BACKUP_FILE_HASH_DRIFT','BACKUP_CORRUPTION_REJECTION')
            else:raise HarnessError('BACKUP_CORRUPTION_ACCEPTED')
        with harness.target(empty_db,'migration').connect() as owner:require(owner.execute("SELECT count(*) FROM pg_namespace WHERE nspname IN ('whattodo','whattodo_meta')").fetchone()==(0,),'BACKUP_CORRUPTION_TOUCHED_TARGET')
        checks.append('single_byte_archive_corruption_is_rejected_by_independent_manifest_pin_before_client_start_or_target_mutation')
        m=json.loads((corrupt.path/'manifest.json').read_text(encoding='utf-8'));m['files']['database.dump']['sha256']=sha256(p.read_bytes()).hexdigest();(corrupt.path/'manifest.json').write_text(canonical(m),encoding='utf-8')
        try:checked_bundle(harness,corrupt,plan,__version__)
        except BackupError as exc:require(str(exc)=='BACKUP_MANIFEST_HASH_DRIFT','BACKUP_SELF_REHASH_REJECTION')
        else:raise HarnessError('BACKUP_SELF_REHASH_ACCEPTED')
        checks.append('rewriting_self_reported_archive_and_manifest_hashes_cannot_replace_the_independently_retained_bundle_pin')
        listing=run_pg(harness,'pg_restore',['--list',str(bundle.path/'database.dump')]);lines=listing.splitlines();removed=[line for line in lines if ' FUNCTION whattodo reject_history_mutation() ' in line];require(len(removed)==1,'BACKUP_FAULT_TOC_FUNCTION');bad_list=harness.run_root/'fault-restore.list';bad_list.write_text('\n'.join(';'+line if line in removed else line for line in lines)+'\n',encoding='utf-8')
        def late_failure(h,tool,args,**kw):
            if tool=='pg_restore' and kw.get('target') is not None:args=['--use-list='+str(bad_list),*args]
            return original_run(h,tool,args,**kw)
        with patch('tools.development_backup.run_pg',side_effect=late_failure):
            try:restore_backup(harness,empty_db,bundle,plan=plan,application_version=__version__)
            except BackupError as exc:require(str(exc)=='BACKUP_RESTORE_FAILED','BACKUP_LATE_RESTORE_ERROR')
            else:raise HarnessError('BACKUP_FAULT_RESTORE_ACCEPTED')
        with harness.target(empty_db,'migration').connect() as owner:require(owner.execute("SELECT count(*) FROM pg_namespace WHERE nspname IN ('whattodo','whattodo_meta')").fetchone()==(0,),'BACKUP_FAILED_RESTORE_LEFT_SCHEMA')
        require(restore_backup(harness,empty_db,bundle,plan=plan,application_version=__version__)['status']=='VERIFIED','BACKUP_FAILED_RESTORE_RETRY');checks.append('actual_postdata_trigger_failure_rolls_back_full_restore_to_empty_target_and_same_trusted_archive_retry_succeeds')
        with harness.target(target_db,'migration').connect() as owner:owner.execute('CREATE TABLE whattodo.synthetic_drift_marker(id integer)')
        try:validate_restored(harness,target_db,bundle,plan=plan,application_version=__version__)
        except BackupError as exc:require(str(exc)=='BACKUP_RESTORED_STATE_OR_SCHEMA_DRIFT','BACKUP_CATALOG_DRIFT_ERROR')
        else:raise HarnessError('BACKUP_CATALOG_DRIFT_ACCEPTED')
        checks.append('postrestore_extra_table_or_catalog_drift_is_detected_even_when_all_migration_receipts_are_unchanged')
        require(not list(harness.run_root.glob('backup-client-*.pgpass')),'BACKUP_PASSWORD_FILE_RETAINED');checks.append('client_password_files_are_outside_bundles_and_removed_after_success_and_failed_real_restore_without_diagnostic_secret_output')
        report.update(migration_steps=len(plan.steps),schema_version=plan.schema_version,source_database_preserved=True,restored_database_count=2,bundle_manifest_sha256=bundle.manifest_hash,bundle_archive_sha256=manifest['files']['database.dump']['sha256'],bundle_bytes=manifest['files']['database.dump']['bytes'],verified_tables=restored['tables_checked'],verified_catalog_categories=len(manifest['inventory']['catalogs']),captured_store_revision=captured_epoch,source_postcapture_store_revision=epoch(),config_references_only=True,role_credentials_exported=False)

def main():
    harness=PostgresHarness();report=dict(task='M3A-18',status='IN_PROGRESS',scope='SYNTHETIC_DEVELOPMENT_BACKUP_SEPARATE_DATABASE_RESTORE',verified_on='2026-10-10',native_checks=[])
    try:
        with harness:verify(harness,report)
        report.update(status='PASS',native_check_count=len(report['native_checks']),limitations=['Owned Windows PostgreSQL 18.6 synthetic development harness only; no production endpoint or deployed backup service','Archive is trusted executable database content; independent checksum detects corruption but is not authorization for untrusted archives','Secret values and global role credentials are not exported; runtime secrets/cursor keys and external definition sources require separate trusted rebinding','This logical probe does not claim continuous recovery, remote retention or live activation'])
    except Exception as exc:
        import traceback
        frames=traceback.extract_tb(exc.__traceback__)
        report.update(status='FAIL',failure_type=type(exc).__name__,failure_code=str(exc) if isinstance(exc,(HarnessError,BackupError)) else 'BACKUP_NATIVE_FAILED',failure_sqlstate=getattr(exc,'sqlstate',None),failure_location=dict(file=Path(frames[-1].filename).name,line=frames[-1].lineno))

        if isinstance(exc,BackupError) and exc.diagnostic is not None:report['failure_diagnostic']=exc.diagnostic
    report['harness']=harness.safe_summary();target=harness.run_root/'backup-restore-report.json'
    if harness.run_root.exists():target.write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(dict(status=report['status'],report=str(target),checks=len(report['native_checks']),server_stopped=report['harness']['server_stopped'])))
    return 0 if report['status']=='PASS' else 1
if __name__=='__main__':raise SystemExit(main())
