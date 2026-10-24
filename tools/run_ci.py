"""One fail-closed pinned synthetic baseline, without deployment or raw artifacts."""
import argparse
import importlib.metadata
import json
import os
from pathlib import Path
import platform
import re
import subprocess
import sys
from uuid import uuid4
ROOT=Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:sys.path.insert(0,str(ROOT))
from tools.ci_checks import CIError,need,check_secrets,check_documents,check_workflow,child_environment,closed_result,source_digest

CHECKS=(
 ('generic_baseline',('tools/check_generic_baseline.py',)),
 ('import_boundaries',('tools/check_import_boundaries.py',)),
 ('contract_registry',('tools/check_contract_registry.py',)),
 ('contract_cases',('-c','from tools.ci_checks import check_contract_cases; print(check_contract_cases())')),
 ('extensions',('tools/check_extension_registry.py',)),
 ('cross_contracts',('tools/check_cross_contracts.py',)),
 ('semantic_scenarios',('tools/check_semantic_catalog.py',)),
 ('database_design',('tools/check_database_design.py',)),
 ('sql_drift',('tools/render_database_design.py','--check')),
 ('aggregate_drift',('tools/render_task_aggregate_schema.py','--check')),
 ('configuration',('tools/check_runtime_config.py',)),
 ('authority',('-m','unittest','tests.test_authorization','tests.test_command_validation','tests.test_command_transport','-q')),
 ('unit_domain',('-m','unittest','discover','-s','tests','-q')),
 ('package_install',('tools/verify_package_install.py',)),
 ('native_migrations',('tools/verify_migrations.py',)),
 ('native_authority',('tools/verify_authorization_pipeline.py',)),
 ('native_transport',('tools/verify_command_transport.py',)),
 ('native_reads',('tools/verify_read_models.py',)),
 ('native_backup_restore',('tools/verify_backup_restore.py',)),
 ('native_relationships',('tools/verify_relationship_storage.py',)),
 ('native_creation_outbox',('tools/verify_creation_outbox.py',)),
 ('native_generation_foundation',('tools/verify_generation_foundation.py',)),
 ('native_generation_runtime',('tools/verify_generation_runtime.py',)),
 ('native_generation_worker',('tools/verify_generation_worker.py',)),
 ('native_stage_commands',('tools/verify_stage_commands.py',)),
 ('native_stage_generated',('tools/verify_stage_generated.py',)),
 ('native_review_storage',('tools/verify_review_queue_storage.py',)),
 ('native_review_sources',('tools/verify_review_sources.py',)))
NATIVE_REPORTS={'native_migrations':'migration-report.json','native_authority':'authorization-report.json','native_transport':'command-transport-report.json','native_reads':'read-models-report.json','native_backup_restore':'backup-restore-report.json','native_relationships':'relationship-storage-report.json'}
NATIVE_REPORTS['native_creation_outbox']='creation-outbox-report.json'
NATIVE_REPORTS['native_generation_foundation']='generation-foundation-report.json'
NATIVE_REPORTS['native_generation_runtime']='generation-runtime-report.json'
NATIVE_REPORTS['native_generation_worker']='generation-worker-report.json'
NATIVE_REPORTS['native_stage_commands']='stage-commands-report.json'
NATIVE_REPORTS['native_stage_generated']='stage-generated-report.json'
NATIVE_REPORTS['native_review_storage']='review-queue-storage-report.json'
NATIVE_REPORTS['native_review_sources']='review-sources-report.json'

def native_summary(root,check,before):
    choices=list((root/'.local-state/postgres-tests').glob('*/'+NATIVE_REPORTS[check]));new=[p for p in choices if p.parent.name not in before]
    need(len(new)==1,'CI_NATIVE_REPORT_MISSING')
    r=json.loads(new[0].read_text(encoding='utf-8'));h=r['harness']
    need(r['status']=='PASS' and h['server_stopped'] is True and h['databases_created']==h['databases_dropped'] and h['initdb_password_file_retained'] is False,'CI_NATIVE_CLEANUP_OR_RESULT')
    if check in ('native_transport','native_reads','native_review_sources'):need(r['http_server_stopped'] is True,'CI_HTTP_CLEANUP')
    count=len(r['native_checks'])
    if check in ('native_review_storage','native_review_sources'):
        need(isinstance(r['native_checks'],list) and all(isinstance(c,str) for c in r['native_checks'])
            and len(set(r['native_checks']))==count and count>0
            and type(r.get('native_check_count')) is int and r['native_check_count']==count,'CI_REVIEW_CASE_COUNTS')
        if check=='native_review_sources':
            # Only this group's new cases count. Re-executed read, stage,
            # lifecycle and generation prerequisite cases are separate evidence.
            keys=('read_fixture_checks_not_counted','stage_fixture_checks_not_counted',
                'lifecycle_fixture_checks_not_counted','generation_fixture_checks_not_counted')
            need(all(type(r.get(k)) is int and r[k]>=0 for k in keys),'CI_REVIEW_CASE_COUNTS')
    if check=='native_stage_commands':
        component=r.get('foundation_checks')
        need(isinstance(component,list) and all(isinstance(c,str) for c in component)
            and isinstance(r['native_checks'],list) and all(isinstance(c,str) for c in r['native_checks'])
            and type(r.get('native_check_count')) is int and r['native_check_count']==count
            and type(r.get('foundation_checks_not_counted')) is int
            and len(component)==r.get('foundation_checks_not_counted')
            and len(set(component+r['native_checks']))==len(component)+count,'CI_STAGE_COMPONENT_COUNTS')
        # This component has no separate CI group. Include it once here;
        # lifecycle/generation prerequisite re-execution remains uncounted.
        count+=len(component)
    return dict(native_checks=count,databases_created=h['databases_created'],databases_dropped=h['databases_dropped'],server_stopped=True)

def process(argv,*,environment,timeout=300,root=ROOT,counts=None):
    # Process output is captured locally and discarded, even on failure. Only
    # closed_result summaries cross the publication boundary.
    try:r=subprocess.run(list(map(str,argv)),cwd=root,env=environment,capture_output=True,timeout=timeout,creationflags=subprocess.CREATE_NO_WINDOW if os.name=='nt' else 0)
    except subprocess.TimeoutExpired:raise CIError('CI_CHILD_TIMEOUT') from None
    except OSError:raise CIError('CI_CHILD_START_FAILED') from None
    if counts is not None:
        match=re.search(rb'\bRan ([0-9]+) tests? in ',r.stderr or b'')
        if match:counts['unittest_methods']=int(match[1])
    return r.returncode

def run(*,bootstrap=False,root=ROOT):
    root=Path(root).resolve();target=root/'.local-state/ci-artifacts';target.mkdir(parents=True,exist_ok=True)
    run_id=uuid4().hex;temp=root/'.local-state/ci-runs'/run_id;temp.mkdir(parents=True,exist_ok=False)
    report=dict(schema_version='0.1.0-synthetic-ci',task='M3A-20',status='IN_PROGRESS',scope='PINNED_WINDOWS_SYNTHETIC_BASELINE',checks=[],deployment=False,provider_credentials=False)
    env=child_environment(temp);current='preflight'
    def execute(check,argv,timeout=300):
        nonlocal current
        current=check;counts={};rc=process(argv,environment=env,timeout=timeout,root=root,counts=counts)
        if rc:report['checks'].append(closed_result(check,'FAIL',exit_code=rc));raise CIError('CI_CHILD_CHECK_FAILED')
        return counts
    try:
        for current,fn in [('secrets',check_secrets),('documents',check_documents),('workflow',check_workflow)]:
            counts=fn(root);report['checks'].append(closed_result(current,'PASS',counts=counts));print(current+' PASS',flush=True)
        manifest=json.loads((root/'toolchain/manifest.json').read_text(encoding='utf-8'))
        need(os.name=='nt' and platform.machine().lower() in ('amd64','x86_64') and platform.python_version()==manifest['python_version'],'CI_PLATFORM_PIN')
        report['source_sha256']=source_digest(root)
        if bootstrap:
            execute('bootstrap',[sys.executable,'tools/bootstrap_toolchain.py'],900);report['checks'].append(closed_result('bootstrap','PASS'))
        interpreter=root/'.venv/Scripts/python.exe';need(interpreter.is_file(),'CI_BOOTSTRAP_REQUIRED')
        # Probe dependency versions with the selected interpreter, not whichever
        # stdlib interpreter invoked this entrypoint before bootstrapping.
        probe='import importlib.metadata,json,platform; m=json.load(open("toolchain/manifest.json",encoding="utf-8")); assert platform.python_version()==m["python_version"]; assert all(importlib.metadata.version(p["name"])==p["version"] for p in m["python_packages"])'
        execute('dependency_pins',[interpreter,'-c',probe]);report['checks'].append(closed_result('dependency_pins','PASS'))
        for label,lock in [('build','requirements-build.lock'),('core','requirements-runtime.lock')]:
            wheelhouse=root/'.dev-tools/wheelhouse'/label;wheelhouse.mkdir(parents=True,exist_ok=True)
            # Wheel hashes are required even if a previous run filled the cache.
            execute('wheelhouse_'+label,[interpreter,'-m','pip','download','--require-hashes','--only-binary=:all:','--index-url','https://pypi.org/simple','--dest',wheelhouse,'-r',lock],300)
            report['checks'].append(closed_result('wheelhouse_'+label,'PASS'))
        for check,args in CHECKS:
            before={p.name for p in (root/'.local-state/postgres-tests').glob('*')} if check in NATIVE_REPORTS else set()
            if args and args[0].startswith('tools/') and args[0].endswith('.py'):
                args=('-m',args[0][:-3].replace('/','.'),*args[1:])
            counts=execute(check,[interpreter,*args],420 if check in ('package_install','native_generation_worker','native_review_sources') else 300)
            if check in ('authority','unit_domain'):need(counts.get('unittest_methods',0)>0,'CI_UNIT_COUNT_MISSING')
            if check in NATIVE_REPORTS:counts=native_summary(root,check,before)
            report['checks'].append(closed_result(check,'PASS',counts=counts));print(check+' PASS',flush=True)
        report['status']='PASS'
    except Exception as exc:
        code=str(exc) if isinstance(exc,CIError) else 'CI_UNEXPECTED_FAILURE'
        report['status']='FAIL'
        if not report['checks'] or report['checks'][-1].get('status')!='FAIL':report['checks'].append(closed_result(current,'FAIL',code=code))
        report['failure_code']=code;print(current+' FAIL '+code,flush=True)
    out=target/(run_id+'.json');out.write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
    print('Synthetic CI '+report['status']+'; closed report '+out.relative_to(root).as_posix(),flush=True)
    return 0 if report['status']=='PASS' else 1

def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--bootstrap',action='store_true');args=parser.parse_args()
    return run(bootstrap=args.bootstrap)
if __name__=='__main__':raise SystemExit(main())
