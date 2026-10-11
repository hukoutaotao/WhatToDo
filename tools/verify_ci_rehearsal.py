"""Rehearse the workflow entrypoint in a new checkout/environment with failures."""
from hashlib import sha256
import json
from pathlib import Path
import shutil
import subprocess
import sys
from uuid import uuid4
ROOT=Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:sys.path.insert(0,str(ROOT))
from tools.ci_checks import CIError,need,source_paths,source_digest,child_environment

def verify():
    run_id=uuid4().hex;owned=(ROOT/'.dev-tools/ci-rehearsals'/run_id).resolve()
    need(owned.parent==(ROOT/'.dev-tools/ci-rehearsals').resolve(),'CI_REHEARSAL_SCOPE');owned.mkdir(parents=True,exist_ok=False)
    checkout=owned/'checkout';checkout.mkdir();files=source_paths()
    for p in files:
        dest=checkout/p.relative_to(ROOT);dest.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(p,dest)
    digest=source_digest(checkout);need(digest==source_digest(ROOT),'CI_REHEARSAL_COPY_DRIFT')
    need(not any((checkout/n).exists() for n in ('.venv','.git','.local-state','.dev-tools')),'CI_REHEARSAL_DIRTY_SETUP')
    # Seed only the public PostgreSQL ZIP, not an environment or extracted DB.
    # Bootstrap revalidates the exact size/hash and extracts a fresh binary tree.
    manifest=json.loads((checkout/'toolchain/manifest.json').read_text(encoding='utf-8'));pg=manifest['postgresql'];name=pg['url'].rsplit('/',1)[1];archive=ROOT/'.dev-tools/downloads'/name
    if archive.is_file():
        h=sha256()
        with archive.open('rb') as f:
            for chunk in iter(lambda:f.read(1048576),b''):h.update(chunk)
        need(archive.stat().st_size==pg['bytes'] and h.hexdigest()==pg['sha256'],'CI_REHEARSAL_CACHE_PIN')
        dest=checkout/'.dev-tools/downloads'/name;dest.parent.mkdir(parents=True);shutil.copyfile(archive,dest);seeded=True
    else:seeded=False
    temp=owned/'temp';temp.mkdir();env=child_environment(temp);env['OPENAI_API_KEY']='synthetic-parent-must-not-be-forwarded';env['PGHOST']='synthetic-unrelated-endpoint'
    report=dict(task='M3A-20',status='IN_PROGRESS',scope='FRESH_WINDOWS_CHECKOUT_WORKER_REHEARSAL',source_sha256=digest,copied_source_files=len(files),inherited_environment=False,inherited_database=False,seeded_public_postgres_archive=seeded,hosted_github_run=False,checks=[])
    def call(label,*,bootstrap=False,expected=0,failure=None):
        before=set((checkout/'.local-state/ci-artifacts').glob('*.json'))
        argv=[sys._base_executable,'tools/run_ci.py']+(['--bootstrap'] if bootstrap else [])
        # The entrypoint itself only prints closed result names/codes. Do not
        # print or archive even those child strings from the rehearsal wrapper.
        r=subprocess.run(argv,cwd=checkout,env=env,capture_output=True,timeout=1800,creationflags=subprocess.CREATE_NO_WINDOW if sys.platform=='win32' else 0)
        new=set((checkout/'.local-state/ci-artifacts').glob('*.json'))-before;need(len(new)==1,'CI_REHEARSAL_REPORT_MISSING')
        result=json.loads(new.pop().read_text(encoding='utf-8'));need(r.returncode==expected and result['status']==('PASS' if expected==0 else 'FAIL'),'CI_REHEARSAL_UNEXPECTED_RESULT')
        if failure:need(result['checks'][-1]['check']==failure,'CI_REHEARSAL_FAILURE_GATE')
        report['checks'].append(dict(check=label,status='PASS',worker_result=result));print(label+' PASS',flush=True)
        return result
    try:
        call('fresh_bootstrap_and_complete_baseline',bootstrap=True)
        p=checkout/'.env';p.write_text('SYNTHETIC=value',encoding='utf-8')
        try:r=call('credential_file_rejected_before_children',expected=1,failure='secrets');need(len(r['checks'])==1,'CI_REHEARSAL_NOT_FAIL_FAST')
        finally:p.unlink()
        p=checkout/'tests/fixtures/ci_mutation/cases.json';p.parent.mkdir();p.write_text(json.dumps(dict(synthetic=True,cases=[dict(id='synthetic-contract-regression',contract='effort',valid=True,payload={'schema_version':'unsupported'})])),encoding='utf-8')
        try:r=call('invalid_contract_blocks_before_authority_package_and_native',expected=1,failure='contract_cases')
        finally:p.unlink();p.parent.rmdir()
        p=checkout/'tests/test_command_validation.py';old=p.read_bytes();p.write_bytes(old+b'\nclass InjectedAuthorityRegression(unittest.TestCase):\n    def test_synthetic_authority_regression(self):\n        self.fail("synthetic-private-diagnostic-must-not-be-published")\n')
        try:
            r=call('authority_regression_blocks_before_package_and_native',expected=1,failure='authority')
            need('synthetic-private-diagnostic' not in json.dumps(r),'CI_REHEARSAL_RAW_FAILURE_EXPORTED')
        finally:p.write_bytes(old)
        need(source_digest(checkout)==digest,'CI_REHEARSAL_SOURCE_NOT_RESTORED')
        report['status']='PASS';report['native_cleanup_verified']=all(c['status']=='PASS' and c.get('counts',{}).get('server_stopped') is True for c in report['checks'][0]['worker_result']['checks'] if c['check'].startswith('native_'))
        need(report['native_cleanup_verified'],'CI_REHEARSAL_NATIVE_CLEANUP')
    except Exception as exc:
        report.update(status='FAIL',failure_code=str(exc) if isinstance(exc,CIError) else 'CI_REHEARSAL_UNEXPECTED_FAILURE')
    target=owned/'rehearsal-report.json';target.write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8');print(json.dumps(dict(status=report['status'],report=str(target))),flush=True)
    return 0 if report['status']=='PASS' else 1
if __name__=='__main__':raise SystemExit(verify())
