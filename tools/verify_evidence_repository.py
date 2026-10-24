"""Native synthetic evidence ingestion; no provider or Task handler activation."""
from dataclasses import replace
from datetime import datetime,timedelta,timezone
from decimal import Decimal
from hashlib import sha256
import json
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:sys.path.insert(0,str(ROOT))
from src import __version__
from src.adapters.clocks import FrozenClock
from src.adapters.contract_json import ContractJSONCodec
from src.adapters.migration_files import load_migration_plan
from src.adapters.postgres_migrations import DatabaseRoles,apply_migrations,schema_checked_transaction
from src.adapters.postgres_evidence import PostgresEvidenceRepository,register_source_scope,EVIDENCE_LOCK
from src.application.evidence_storage import (EvidenceError,SourceScope,admit_candidate,canonical,pending_id)
from src.domain.provenance import capture_source,make_candidate,mark_source_deleted
from tools.check_contract_registry import trusted_schemas
from tools.postgres_harness import HarnessError,PostgresHarness,ROLES,require
from tools.verify_toolchain import native_transactions

CAPTURE=datetime(2026,1,1,tzinfo=timezone.utc)
NOW=CAPTURE+timedelta(days=2)


def wire(value):return json.dumps(value,ensure_ascii=False,indent=2).encode()


def reject(action,code):
    try:action()
    except EvidenceError as exc:require(str(exc)==code,'EVIDENCE_UNEXPECTED_FAILURE_CODE')
    else:raise HarnessError('EVIDENCE_NEGATIVE_ACCEPTED')


def verify(harness,report):
    import psycopg
    from psycopg.types.json import Jsonb
    codec=ContractJSONCodec(trusted_schemas());clock=FrozenClock(NOW)
    plan=load_migration_plan(root=ROOT)
    old=load_migration_plan(root=ROOT,manifest_path=ROOT/'reports/acceptance/M3A-07-migration-plan.json')
    roles=DatabaseRoles(ROLES['migration'],ROLES['application'],ROLES['test'])
    a=SourceScope('synthetic-evidence','scope-a','synthetic-account-a')
    b=SourceScope('synthetic-evidence','scope-b','synthetic-account-b')
    legacy=SourceScope('spike','scope','synthetic')
    checks=report['native_checks']; name=harness.create_database(initialize_schema=False)
    with harness.target(name,'migration').connect() as migration:
        apply_migrations(migration,old,roles=roles,application_version=__version__)
        native_transactions(migration)
        before=migration.execute('SELECT * FROM whattodo_meta.migration_history ORDER BY position').fetchall()
        result=apply_migrations(migration,plan,roles=roles,application_version=__version__)
        require(result.applied==tuple(s.migration_id for s in plan.steps[len(old.steps):]),'EVIDENCE_FORWARD_UPGRADE')
        require(migration.execute('SELECT * FROM whattodo_meta.migration_history WHERE position<=%s ORDER BY position',(len(old.steps),)).fetchall()==before,
            'EVIDENCE_CHANGED_OLD_RECEIPTS')
        checks.append('current_forward_suffix_preserves_all_eight_original_checkpoint_receipts')
        for scope in (a,b):register_source_scope(migration,plan,roles,scope,application_version=__version__,clock=clock)
        register_source_scope(migration,plan,roles,a,application_version=__version__,clock=clock)
        reject(lambda:register_source_scope(migration,plan,roles,replace(a,account_ref='other-account'),
            application_version=__version__,clock=clock),'EVIDENCE_SCOPE_IDENTITY_CONFLICT')
        checks.append('scope_registration_is_idempotent_and_cannot_retag_an_account')
        with migration.transaction():
            migration.execute("INSERT INTO whattodo.command_transaction VALUES('evidence-task',%s,'principal','USER_COMMAND','authority',2,3,'evidence-task-audit',%s,%s)",
                ('e'*64,NOW,Jsonb(dict(synthetic=True))))
            migration.execute("INSERT INTO whattodo.audit_entry VALUES('evidence-task-audit','evidence-task','record','synthetic-correlation',%s)",(NOW,))
            migration.execute("INSERT INTO whattodo.audit_change VALUES('evidence-task-change','evidence-task-audit','TASK','existing-task',NULL,1,NULL,%s,'evidence-task')",
                (Jsonb(dict(synthetic=True)),))
            migration.execute("INSERT INTO whattodo.task_identity VALUES('existing-task','evidence-task',%s)",(NOW,))
            migration.execute('''INSERT INTO whattodo.task_revision(task_id,revision,title,domain,acceptance_ref,completion,disposition,
                requiredness,importance,thinking_depth,repetitive_volume,new_learning_load,audit_change_ref,aggregate_kind,transaction_ref,metadata)
                VALUES('existing-task',1,'Synthetic existing Task','other','authority','INCOMPLETE','ACTIVE','REQUIRED',3,3,3,3,
                'evidence-task-change','TASK','evidence-task',%s)''',(Jsonb(dict(trust='TRUSTED',overdue='UNKNOWN')),))
            migration.execute("INSERT INTO whattodo.task_head VALUES('existing-task',1,'evidence-task')")
            migration.execute("UPDATE whattodo.store_epoch SET revision=3,last_transaction_ref='evidence-task' WHERE singleton=TRUE AND revision=2")
    with harness.target(name).connect() as conn:
        def repository(connection=conn,scopes=(a,)):
            return PostgresEvidenceRepository(connection,codec,plan,application_version=__version__,clock=clock,scopes=scopes)
        repo=repository(); all_repo=repository(scopes=(a,b,legacy))
        tables=['task_identity','task_revision','task_head','task_details_revision','task_payload_revision','stage_identity',
            'stage_revision','task_stage_revision','stage_effort_revision','task_field_provenance','effort_observation',
            'authority_record','command_transaction','audit_entry','audit_change','store_epoch']
        def canonical_snapshot():return tuple(conn.execute('SELECT * FROM whattodo.'+table+' ORDER BY 1,2').fetchall() for table in tables)
        canonical_before=canonical_snapshot()
        reject(lambda:all_repo.get_source('record'),'EVIDENCE_LEGACY_SOURCE_PAYLOAD_UNAVAILABLE')
        checks.append('legacy_source_without_wire_bytes_is_explicitly_unavailable')
        raw=b'synthetic source body; not a real message'
        source=capture_source(provider=a.provider,scope_ref=a.scope_ref,external_id='same-external-id',
            raw_bytes=raw,captured_at=CAPTURE,source_type='OTHER')
        original=repo.observe_source(wire(source.as_record()),raw_content=raw,locator_ref='synthetic-raw-a')
        require(original.outcome=='INSERTED' and repo.get_source(source.record_id)==original.stored,
            'EVIDENCE_SOURCE_ROUNDTRIP')
        require(repo.get_raw(source.record_id).raw_bytes==raw,'EVIDENCE_RAW_ROUNDTRIP')
        checks.append('source_wire_content_hash_and_exact_raw_bytes_roundtrip')
        repeat=replace(source,captured_at=CAPTURE+timedelta(hours=1))
        replay=repo.observe_source(wire(repeat.as_record()),raw_content=raw,locator_ref='later-locator')
        require(replay.outcome=='REPLAY' and replay.stored==original.stored and
            repo.get_raw(source.record_id).locator_ref=='synthetic-raw-a','EVIDENCE_SOURCE_REPLAY_CHANGED_FIRST_SEEN')
        checks.append('source_replay_preserves_initial_wire_capture_time_and_locator')
        other=capture_source(provider=b.provider,scope_ref=b.scope_ref,external_id=source.external_id,
            raw_bytes=raw,captured_at=CAPTURE,source_type='OTHER')
        repo_b=repository(scopes=(b,));repo_b.observe_source(wire(other.as_record()),raw_content=raw,locator_ref='synthetic-raw-b')
        require(other.source_id!=source.source_id and other.record_id!=source.record_id,'EVIDENCE_SCOPE_COLLISION')
        reject(lambda:repo.get_source(other.record_id),'EVIDENCE_SOURCE_SCOPE_NOT_AUTHORIZED')
        reject(lambda:repo.observe_source(wire(other.as_record()),raw_content=raw,locator_ref='forbidden'),
            'EVIDENCE_SOURCE_SCOPE_NOT_AUTHORIZED')
        checks.append('same_external_id_in_two_scopes_is_distinct_and_cross_scope_read_write_is_denied')
        changed_bytes=b'synthetic changed source body'
        changed=capture_source(provider=a.provider,scope_ref=a.scope_ref,external_id=source.external_id,
            raw_bytes=changed_bytes,captured_at=CAPTURE+timedelta(days=1),source_type='OTHER')
        repo.observe_source(wire(changed.as_record()),raw_content=changed_bytes,locator_ref='synthetic-raw-changed')
        require(repo.get_source(source.record_id)==original.stored and changed.record_id!=source.record_id,
            'EVIDENCE_OLD_SOURCE_REWRITTEN')
        checks.append('changed_content_adds_a_distinct_immutable_source_version')
        source_conflict=repo.observe_source(wire(replace(source,source_timestamp=CAPTURE).as_record()),
            raw_content=raw,locator_ref='synthetic-conflicting-metadata')
        require(source_conflict.outcome=='CONFLICT' and source_conflict.stored==original.stored,
            'EVIDENCE_SOURCE_CONFLICT_REWRITTEN')
        require(repo.get_conflict(source_conflict.conflict_id) is not None,'EVIDENCE_SOURCE_CONFLICT_NOT_RETAINED')
        checks.append('source_metadata_conflict_retains_original_and_observed_evidence')

        candidate=make_candidate(source,parser_version='parser-v1',action='CREATE_TASK',
            proposed_fields=dict(title='Synthetic proposal',remaining_seconds=400),confidence='0.8')
        first=repo.observe_candidate(wire(candidate.as_record()))
        require(first.outcome=='INSERTED' and repo.get_candidate(candidate.candidate_id)==(first.stored,1),
            'EVIDENCE_CANDIDATE_ROUNDTRIP')
        count=len(repo.pending_items())
        require(repo.observe_candidate(wire(replace(candidate,created_at=CAPTURE+timedelta(hours=1)).as_record())).outcome=='REPLAY'
            and len(repo.pending_items())==count,'EVIDENCE_DUPLICATE_PENDING_CANDIDATE')
        checks.append('repeated_source_parser_observation_does_not_duplicate_candidate_or_pending_item')
        require(conn.execute('SELECT count(*) FROM whattodo.candidate_field_provenance WHERE candidate_id=%s',
            (candidate.candidate_id,)).fetchone()==(2,),'EVIDENCE_FIELD_PROVENANCE_MISSING')
        checks.append('each_proposed_field_binds_its_exact_source_version')
        mismatch=replace(candidate,proposed_fields_json=json.dumps(dict(title='Nondeterministic parse',remaining_seconds=400)))
        conflict=repo.observe_candidate(wire(mismatch.as_record()))
        require(conflict.outcome=='CONFLICT' and repo.get_candidate(candidate.candidate_id)==(first.stored,1),
            'EVIDENCE_CANDIDATE_CONFLICT_OVERWROTE_PROPOSAL')
        require(repo.observe_candidate(wire(mismatch.as_record())).conflict_id==conflict.conflict_id,
            'EVIDENCE_DUPLICATE_CONFLICT')
        checks.append('nondeterministic_parse_retains_one_original_and_one_deduplicated_conflict')
        high=make_candidate(changed,parser_version='precise-parser',action='CREATE_TASK',
            proposed_fields=dict(remaining_seconds=9007199254740993),confidence='0.8')
        precise_wire=wire(high.as_record()).replace(b'"confidence": 0.8',b'"confidence": 0.812345678901234567890123456789')
        precise=repo.observe_candidate(precise_wire)
        require(repo.get_candidate(high.candidate_id)[0].candidate.confidence==Decimal('0.812345678901234567890123456789')
            and precise.stored.fields['remaining_seconds']==9007199254740993,'EVIDENCE_DECIMAL_PRECISION_LOST')
        checks.append('original_confidence_and_large_integer_proposals_are_not_float_rounded')
        complete=make_candidate(source,parser_version='complete-parser',action='COMPLETE_TASK',
            proposed_fields=dict(completion='COMPLETE'),confidence=1,target_task_id='existing-task',target_revision=1)
        require(repo.observe_candidate(wire(complete.as_record())).stored.candidate.review_state=='PENDING',
            'EVIDENCE_CONFIDENCE_BECAME_AUTHORITY')
        require(canonical_snapshot()==canonical_before,'EVIDENCE_CHANGED_CANONICAL_STATE')
        checks.append('confidence_one_and_external_completion_proposal_leave_all_canonical_tables_unchanged')
        confirmed=candidate.as_record();confirmed['review']=dict(state='CONFIRMED',authority_ref='authority',
            reviewed_at=NOW.isoformat(),canonical_task_id='existing-task')
        reject(lambda:repo.observe_candidate(wire(confirmed)),'EVIDENCE_INGEST_PENDING_ONLY')
        unknown=make_candidate(source,parser_version='unknown-target',action='UPDATE_TASK',
            proposed_fields=dict(title='Unknown target'),confidence=1,target_task_id='unknown-task',target_revision=1)
        reject(lambda:repo.observe_candidate(wire(unknown.as_record())),'EVIDENCE_UNKNOWN_TARGET')
        reject(lambda:repo.observe_source(wire(source.as_record()),raw_content=b'wrong bytes',locator_ref='wrong'),
            'EVIDENCE_RAW_CONTENT_HASH')
        checks.append('unsupported_review_unknown_target_and_wrong_raw_hash_cannot_ingest')
        cb=make_candidate(other,parser_version='parser-v1',action='CREATE_TASK',proposed_fields=dict(title='Scope B proposal'),confidence=1)
        repo_b.observe_candidate(wire(cb.as_record()))
        require(all(row[2]!=cb.candidate_id for row in repo.pending_items()) and len(repo_b.pending_items())==1,
            'EVIDENCE_PENDING_QUEUE_LEAKED_OTHER_SCOPE')
        checks.append('pending_queue_only_contains_registered_account_scopes')
        before_fields=repo.get_candidate(candidate.candidate_id)
        minimized=repo.minimize_raw(source.record_id,reason_ref='synthetic-retention-test')
        require(minimized.storage_state=='MINIMIZED' and minimized.raw_bytes is None
            and minimized.content_hash==source.content_hash and repo.get_candidate(candidate.candidate_id)==before_fields,
            'EVIDENCE_MINIMIZATION_LOST_SEMANTICS')
        require(repo.minimize_raw(source.record_id,reason_ref='later-reason')==minimized
            and repo.observe_source(wire(source.as_record()),raw_content=raw,locator_ref='retry-after-prune').outcome=='REPLAY'
            and repo.get_raw(source.record_id)==minimized,'EVIDENCE_RAW_CONTENT_RESURRECTED')
        checks.append('raw_minimization_preserves_source_candidate_hashes_and_cannot_be_undone_by_replay')
        deleted=mark_source_deleted(source,CAPTURE+timedelta(days=1))
        tombstone=repo.observe_source(wire(deleted.as_record()),locator_ref='unused',prior_record_id=source.record_id)
        require(tombstone.outcome=='INSERTED' and repo.get_source(source.record_id)==original.stored
            and repo.get_source(deleted.record_id).source.content_hash==source.content_hash,
            'EVIDENCE_TOMBSTONE_OVERWROTE_PRIOR')
        require(repo.observe_source(wire(deleted.as_record()),locator_ref='unused',prior_record_id=source.record_id).outcome=='REPLAY',
            'EVIDENCE_DUPLICATE_TOMBSTONE')
        different_deletion=mark_source_deleted(source,CAPTURE+timedelta(days=1,hours=1))
        require(repo.observe_source(wire(different_deletion.as_record()),locator_ref='unused',prior_record_id=source.record_id).outcome=='CONFLICT',
            'EVIDENCE_CONTRADICTORY_DELETION_LOST')
        require(canonical_snapshot()==canonical_before,'EVIDENCE_DELETION_CANCELLED_TASK')
        checks.append('tombstone_keeps_prior_hash_is_idempotent_and_never_cancels_accepted_task')
        fresh_parser=make_candidate(source,parser_version='after-deletion-parser',action='CREATE_TASK',
            proposed_fields=dict(title='Stale source'),confidence=1)
        reject(lambda:repo.observe_candidate(wire(fresh_parser.as_record())),'EVIDENCE_DELETED_SOURCE_CANNOT_CREATE_PROPOSAL')
        require(repo.observe_candidate(wire(candidate.as_record())).outcome=='REPLAY','EVIDENCE_DELETION_LOST_HISTORY')
        checks.append('deleted_version_rejects_new_parser_proposals_but_keeps_replay_history')

        class FaultRepository(PostgresEvidenceRepository):
            def _pending(self,kind,target_id):
                super()._pending(kind,target_id)
                raise EvidenceError('SYNTHETIC_PENDING_WRITE_FAILURE')
        rollback=make_candidate(changed,parser_version='rollback-parser',action='CREATE_TASK',
            proposed_fields=dict(title='Synthetic rollback'),confidence=1)
        failing=FaultRepository(conn,codec,plan,application_version=__version__,clock=clock,scopes=(a,))
        pending_before=repo.pending_items()
        reject(lambda:failing.observe_candidate(wire(rollback.as_record())),'SYNTHETIC_PENDING_WRITE_FAILURE')
        require(repo.get_candidate(rollback.candidate_id) is None and repo.pending_items()==pending_before
            and conn.execute('SELECT 1 FROM whattodo.candidate_identity WHERE candidate_id=%s',(rollback.candidate_id,)).fetchone() is None,
            'EVIDENCE_PARTIAL_INGESTION_COMMITTED')
        checks.append('failure_after_payload_provenance_and_pending_staging_rolls_back_entire_ingestion')

        # A trusted fixture prepares a reviewed history version. There is no
        # ingestion endpoint that can do this; later command handlers own it.
        reviewed=admit_candidate(codec,wire(confirmed)); c=reviewed.candidate
        with conn.transaction():
            repo._insert('candidate_revision',dict(candidate_id=c.candidate_id,revision=2,
                source_record_ref=c.source_record_id,parser_version=c.parser_version,action=c.action,
                task_id=c.target_task_id,task_revision=c.target_revision,proposed_fields=Jsonb(reviewed.fields,dumps=canonical),
                confidence=c.confidence,review_state=c.review_state,review_authority_ref=c.authority_ref,
                reviewed_at=c.reviewed_at,created_at=c.created_at,canonical_task_ref=c.canonical_task_id))
            repo._insert('candidate_payload',dict(candidate_id=c.candidate_id,revision=2,source_record_ref=c.source_record_id,
                source_id=c.source_id,source_hash=c.source_hash,proposal_hash=reviewed.proposal_hash,
                wire_hash=reviewed.wire_hash,raw_wire=reviewed.raw_wire))
            for key in sorted(reviewed.fields):
                repo._insert('candidate_field_provenance',dict(candidate_id=c.candidate_id,revision=2,
                    field_pointer='/proposed_fields/'+key,source_record_ref=c.source_record_id,source_id=c.source_id,source_hash=c.source_hash))
            pending=pending_id('CANDIDATE',c.candidate_id)
            repo._insert('pending_evidence_revision',dict(pending_id=pending,revision=2,state='RESOLVED',
                authority_ref='authority',resolved_at=NOW,transaction_ref='evidence-task'))
            conn.execute('UPDATE whattodo.pending_evidence_head SET revision=2 WHERE pending_id=%s AND revision=1',(pending,))
        require(repo.get_candidate(candidate.candidate_id)==(reviewed,2)
            and repo.get_candidate(candidate.candidate_id,1)==before_fields,'EVIDENCE_REVIEW_HISTORY_LOST')
        replay=repo.observe_candidate(wire(candidate.as_record()))
        require(replay.outcome=='REPLAY' and replay.revision==2 and replay.stored.candidate.review_state=='CONFIRMED'
            and all(row[2]!=candidate.candidate_id for row in repo.pending_items()),'EVIDENCE_REPLAY_REOPENED_REVIEW')
        checks.append('replay_preserves_confirmed_history_and_does_not_reopen_resolved_pending_item')

        with harness.target(name).connect() as contender:
            with schema_checked_transaction(conn,plan,application_version=__version__,read_only=False):
                conn.execute('SELECT pg_advisory_xact_lock(%s)',(EVIDENCE_LOCK,))
                reject(lambda:repository(contender).observe_candidate(wire(candidate.as_record())),'EVIDENCE_IMPORT_BUSY')
        checks.append('concurrent_ingestion_is_serialized_without_duplicate_registration')
        try:
            with conn.transaction():
                conn.execute('''INSERT INTO whattodo.candidate_field_provenance VALUES(%s,1,
                    '/proposed_fields/other-scope',%s,%s,%s)''',
                    (candidate.candidate_id,other.record_id,other.source_id,other.content_hash))
        except psycopg.errors.ForeignKeyViolation:
            checks.append('native_field_provenance_fk_rejects_an_unrelated_source_version')
        else:raise HarnessError('EVIDENCE_NATIVE_FIELD_SCOPE_MISMATCH_ACCEPTED')
        try:
            with conn.transaction():
                repo._insert('source_raw_content',dict(record_id='unregistered-raw',content_hash=source.content_hash,
                    raw_content=raw,storage_state='RETAINED',minimized_at=None,reason_ref=None))
        except psycopg.errors.ForeignKeyViolation:
            checks.append('native_raw_content_fk_rejects_an_unregistered_source_payload')
        else:raise HarnessError('EVIDENCE_NATIVE_ORPHAN_RAW_ACCEPTED')
        for table in ['source_payload','candidate_identity','candidate_payload','candidate_field_provenance',
                'evidence_conflict','pending_evidence_identity','pending_evidence_revision']:
            try:
                with conn.transaction():conn.execute('DELETE FROM whattodo.'+table)
            except psycopg.errors.CheckViolation:checks.append(table+'_history_is_append_only')
            else:raise HarnessError('EVIDENCE_HISTORY_MUTATED')
        try:
            with conn.transaction():
                conn.execute("UPDATE whattodo.source_raw_content SET raw_content=%s,storage_state='RETAINED',minimized_at=NULL,reason_ref=NULL WHERE record_id=%s",(raw,source.record_id))
        except psycopg.errors.CheckViolation:checks.append('native_guard_prevents_restoring_minimized_raw_bytes')
        else:raise HarnessError('EVIDENCE_NATIVE_RAW_RESURRECTION')
        try:conn.execute("INSERT INTO whattodo.source_scope VALUES('forbidden','forbidden','forbidden',CURRENT_TIMESTAMP)")
        except psycopg.errors.InsufficientPrivilege:checks.append('application_cannot_self_register_source_account_scope')
        else:raise HarnessError('EVIDENCE_SCOPE_CONFIGURATION_BYPASSED')
        report['domain_tables']=conn.execute("SELECT count(*) FROM pg_tables WHERE schemaname='whattodo'").fetchone()[0]
        report['domain_foreign_keys']=conn.execute("SELECT count(*) FROM pg_constraint c JOIN pg_namespace n ON n.oid=c.connamespace WHERE n.nspname='whattodo' AND c.contype='f'").fetchone()[0]
        require((report['domain_tables'],report['domain_foreign_keys'])==(87,221),'EVIDENCE_SCHEMA_COUNTS')
        checks.append('native_schema_has_87_domain_tables_and_221_foreign_keys')
        require(canonical_snapshot()==canonical_before,'EVIDENCE_FINAL_CANONICAL_STATE_CHANGED')
    with harness.target(name).connect() as restarted:
        repository=PostgresEvidenceRepository(restarted,codec,plan,application_version=__version__,clock=clock,scopes=(a,))
        require(repository.get_candidate(candidate.candidate_id)==(reviewed,2)
            and repository.get_candidate(candidate.candidate_id,1)==before_fields
            and repository.get_raw(source.record_id)==minimized,'EVIDENCE_RESTART_LOST_HISTORY')
        checks.append('fresh_connection_preserves_semantic_history_and_raw_minimization')


def main():
    harness=PostgresHarness();report=dict(task='M3A-08',status='IN_PROGRESS',scope='SYNTHETIC_EVIDENCE_REPOSITORY',verified_on='2026-10-10',native_checks=[])
    try:
        with harness:verify(harness,report)
        report.update(status='PASS',native_check_count=len(report['native_checks']),limitations=[
            'Synthetic sources/scopes only; no live collector or account activation',
            'Ingestion supports pending proposals only; reviewed commands remain separate',
            'Raw minimization exercised only on synthetic test data',
            'No canonical Task, authority, audit or store epoch mutation from ingestion'])
    except Exception as exc:
        report.update(status='FAIL',failure_type=type(exc).__name__,failure_sqlstate=getattr(exc,'sqlstate',None),
            failure_code=str(exc) if isinstance(exc,(EvidenceError,HarnessError)) else 'EVIDENCE_NATIVE_CHECK_FAILED')
    report['harness']=harness.safe_summary();target=harness.run_root/'evidence-report.json'
    if harness.run_root.exists():target.write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(dict(status=report['status'],report=str(target),checks=len(report['native_checks']),server_stopped=report['harness']['server_stopped'])))
    return 0 if report['status']=='PASS' else 1


if __name__=='__main__':raise SystemExit(main())
