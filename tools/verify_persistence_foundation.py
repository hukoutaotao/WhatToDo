"""Reproduce the bounded M3A gate in a fresh owned Windows checkout."""
from hashlib import sha256
import json
from pathlib import Path
import re
import shutil
import subprocess
import sys
from uuid import uuid4
ROOT=Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:sys.path.insert(0,str(ROOT))
from tools.ci_checks import CIError,need,source_paths,source_digest,child_environment

# Exact probe IDs, read together with their implementation; a green unrelated
# report or a matching word in a check title cannot satisfy this gate.
REQUIREMENTS={
 'create_patch_effort_complete':('command-transport',(
  'actual_http_create_uses_independent_principal_grant_intent_source_and_existing_atomic_task_audit_receipt_path',
  'fact_patch_route_preserves_opt_in_exact_grant_source_provenance_and_explicit_u',
  'reported_work_route_deduplicates_actual_observation_and_does_not_decrement_u_or_invent_session_bounds',
  'complete_and_cancel_routes_keep_separate_lifecycle_history_zero_u_and_original_actual_work')),
 'stale_publication':('authorization',('concurrent_change_after_scope_validation_rejects_stale_publication_without_audit_or_receipt',)),
 'duplicate_command':('command-transport',('same_request_replays_original_receipt_and_larger_transport_envelope_preserves_frozen_inner_contract_limit',)),
 'unauthorized_write':('authorization',('external_claimed_user_and_unauthenticated_callers_cannot_write_or_replay',)),
 'authenticated_scope':('command-transport',('payload_principal_and_task_scope_forgery_fail_before_existing_handler_invocation',)),
 'atomic_rollback':('command-transport',('native_precommit_failure_rolls_back_all_task_audit_receipt_epoch_state_then_same_wire_retry_commits_once',)),
 'lost_ack_reconciliation':('command-transport',('lost_transport_result_after_real_commit_stays_unknown_and_lookup_or_same_id_retry_recovers_one_original_receipt',)),
 'separate_restore':('backup-restore',('actual_custom_archive_restores_all_82_domain_and_three_metadata_tables_and_catalog_constraints_functions_triggers_privileges_and_sequence_state_into_separate_empty_database',)),
 'source_preservation':('backup-restore',('original_source_database_and_its_concurrent_postsnapshot_task_are_preserved_byte_for_byte_during_restore',)),
 'restored_canonical_history':('backup-restore',('restored_current_and_historical_task_bytes_keep_completion_cancel_zero_u_original_total_actual_work_and_original_due_offset_microseconds_independent',)),
 'restored_command_replay':('backup-restore',('restored_receipt_lookup_and_original_completion_retry_validate_owned_audits_and_return_original_commit_without_live_grants_or_duplicate_publication',)),
 'corruption_before_restore':('backup-restore',('single_byte_archive_corruption_is_rejected_by_independent_manifest_pin_before_client_start_or_target_mutation',)),
 'failed_restore_rollback':('backup-restore',('actual_postdata_trigger_failure_rolls_back_full_restore_to_empty_target_and_same_trusted_archive_retry_succeeds',))}

def artifact_pins(root):
    selected=set()
    for directory,pattern in [('src','*.py'),('tools','*.py'),('tests','test_*.py'),('formats','*.schema.json'),('database','*.sql')]:
        selected.update((root/directory).rglob(pattern))
    selected.update(root/p for p in ['pyproject.toml','requirements-toolchain.lock','requirements-build.lock','requirements-runtime.lock','toolchain/manifest.json','database/migration-plan.json','formats/contract-registry.json','formats/extension-registry.json','formats/generic-baseline.json','.github/workflows/baseline.yml'])
    return {p.relative_to(root).as_posix():sha256(p.read_bytes()).hexdigest() for p in sorted(selected)}

def verify():
    run_id=uuid4().hex;owned=(ROOT/'.dev-tools/foundation-validation'/run_id).resolve()
    need(owned.parent==(ROOT/'.dev-tools/foundation-validation').resolve(),'CI_FOUNDATION_SCOPE');owned.mkdir(parents=True,exist_ok=False)
    checkout=owned/'checkout';checkout.mkdir();temp=owned/'temp';temp.mkdir()
    report=dict(task='M3A-19',schema_version='0.1.0-persistence-gate',status='IN_PROGRESS',scope='FRESH_SYNTHETIC_AUTHORIZED_REPLAYABLE_POSTGRESQL_PROTOTYPE',requirements={},production_endpoint=False,hosted_actions=False)
    try:
        progress=(ROOT/'plan/PROGRESS.md').read_text(encoding='utf-8')
        need(all('| '+key+' | DONE |' in progress for key in ('M3A-02','M3A-18','M3A-20')),'CI_FOUNDATION_PREREQUISITE')
        sources=source_paths();snapshot=source_digest(ROOT)
        for p in sources:
            dest=checkout/p.relative_to(ROOT);dest.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(p,dest)
        need(snapshot==source_digest(checkout),'CI_FOUNDATION_COPY_DRIFT')
        need(not any((checkout/name).exists() for name in ('.venv','.git','.local-state','.dev-tools')),'CI_FOUNDATION_NOT_FRESH')
        pins=artifact_pins(checkout);report.update(source_snapshot_sha256=snapshot,copied_source_files=len(sources),artifact_hashes=pins)
        manifest=json.loads((checkout/'toolchain/manifest.json').read_text(encoding='utf-8'));pg=manifest['postgresql'];name=pg['url'].rsplit('/',1)[1];archive=ROOT/'.dev-tools/downloads'/name
        if archive.is_file():
            h=sha256()
            with archive.open('rb') as f:
                for chunk in iter(lambda:f.read(1048576),b''):h.update(chunk)
            need(archive.stat().st_size==pg['bytes'] and h.hexdigest()==pg['sha256'],'CI_FOUNDATION_CACHE_DRIFT')
            target=checkout/'.dev-tools/downloads'/name;target.parent.mkdir(parents=True);shutil.copyfile(archive,target);report['seeded_public_archive']=True
        else:report['seeded_public_archive']=False
        env=child_environment(temp)
        result=subprocess.run([sys._base_executable,'tools/run_ci.py','--bootstrap'],cwd=checkout,env=env,capture_output=True,timeout=1800,creationflags=subprocess.CREATE_NO_WINDOW if sys.platform=='win32' else 0)
        files=list((checkout/'.local-state/ci-artifacts').glob('*.json'));need(len(files)==1,'CI_FOUNDATION_WORKER_REPORT')
        worker=json.loads(files[0].read_text(encoding='utf-8'));report['worker_result']=worker
        need(result.returncode==0 and worker['status']=='PASS','CI_FOUNDATION_WORKER_FAILED')
        print('Fresh bootstrap, unit/contract/package and native CI PASS',flush=True)
        groups={}
        for name in ('migration','authorization','command-transport','read-models','backup-restore'):
            files=list((checkout/'.local-state/postgres-tests').glob('*/'+name+'-report.json'));need(len(files)==1,'CI_FOUNDATION_NATIVE_REPORT')
            value=json.loads(files[0].read_text(encoding='utf-8'));h=value['harness']
            need(value['status']=='PASS' and h['server_stopped'] is True and h['databases_created']==h['databases_dropped'] and not h['initdb_password_file_retained'],'CI_FOUNDATION_NATIVE_CLEANUP')
            if name in ('command-transport','read-models'):need(value['http_server_stopped'] is True,'CI_FOUNDATION_HTTP_CLEANUP')
            need(not list(files[0].parent.glob('backup-client-*.pgpass')),'CI_FOUNDATION_PASSWORD_FILE')
            groups[name]=dict(status=value['status'],native_checks=value['native_checks'],native_check_count=len(value['native_checks']),harness=h)
        for key,(group,checks) in REQUIREMENTS.items():
            need(set(checks)<=set(groups[group]['native_checks']),'CI_FOUNDATION_REQUIREMENT_MISSING')
            report['requirements'][key]=dict(status='PASS',native_group=group,probe_ids=list(checks))
        interpreter=checkout/'.venv/Scripts/python.exe'
        times=subprocess.run([interpreter,'-m','unittest','tests.test_clock_values','-q'],cwd=checkout,env=env,capture_output=True,timeout=60,creationflags=subprocess.CREATE_NO_WINDOW if sys.platform=='win32' else 0)
        count=re.search(rb'\bRan ([0-9]+) tests in ',times.stderr or b'');need(times.returncode==0 and count and int(count[1])==6,'CI_FOUNDATION_TIME_PRIMITIVES')
        report['requirements']['time_primitives']=dict(status='PASS',unittest_methods=6)
        report['requirements']['clean_setup_without_live_credentials']=dict(status='PASS',fresh_environment=True,fresh_database=True,source_copy_matching=True,worker_status=worker['status'])
        packages=list((checkout/'.dev-tools/package-validation').glob('*/report.json'));need(len(packages)==1,'CI_FOUNDATION_PACKAGE_REPORT');package=json.loads(packages[0].read_text(encoding='utf-8'))
        installed=Path(package['installed_checks']['installed_source']).parent
        need(installed.resolve().is_relative_to((checkout/'.dev-tools/package-validation').resolve()),'CI_FOUNDATION_INSTALLED_SCOPE')
        py=list((checkout/'src').rglob('*.py'));need(package['status']=='PASS' and all(p.read_bytes()==(installed/p.relative_to(checkout/'src')).read_bytes() for p in py),'CI_FOUNDATION_INSTALLED_SOURCE_DRIFT')
        need(artifact_pins(ROOT)==pins and artifact_pins(checkout)==pins,'CI_FOUNDATION_ARTIFACT_DRIFT')
        report.update(status='PASS',native_groups=groups,native_check_count=sum(g['native_check_count'] for g in groups.values()),full_unittest_methods=next(c['counts']['unittest_methods'] for c in worker['checks'] if c['check']=='unit_domain'),installed_source_files=len(py),installed_modules=package['import_modules_checked'],packaged_schemas=package['packaged_schema_count'],total_test_databases_dropped=sum(g['harness']['databases_dropped'] for g in groups.values()),schema_version=manifest['postgresql']['version'],limitations=['Synthetic generic persistence foundation only; not full StateStore, relationship/review/expiration application runtime or a production service','Fresh Windows source snapshot without Git credentials or inherited environment/database; public pinned PostgreSQL archive may be seeded','Hosted Actions, real providers/models, personal activation, Planner and deployment are not certified','CREATE_TASK natural/guided normalization is the implemented first command class; other repeated classes remain incomplete'])
        from src.adapters.migration_files import load_migration_plan
        plan=load_migration_plan(root=ROOT);report.update(schema_version=plan.schema_version,migration_steps=len(plan.steps),migration_pins=[dict(id=s.migration_id,sha256=s.content_hash) for s in plan.steps])
    except Exception as exc:
        code=str(exc) if isinstance(exc,CIError) else 'CI_FOUNDATION_FAILED';report.update(status='FAIL',failure_code=code)
    target=owned/'foundation-report.json';target.write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8');print(json.dumps(dict(status=report['status'],report=str(target))),flush=True)
    return 0 if report['status']=='PASS' else 1
if __name__=='__main__':raise SystemExit(verify())
