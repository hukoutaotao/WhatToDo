"""Build and install a pinned private wheel in two new project-owned environments.

All pip work after cache preparation is offline. No existing environment is
replaced or deleted, and no global installation or package publication occurs.
"""
from hashlib import sha256
import json
import os
from pathlib import Path
import platform
import subprocess
import sys
from uuid import uuid4
import venv
import zipfile

ROOT=Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:sys.path.insert(0,str(ROOT))
from tools.check_generic_baseline import BASELINE,validate_baseline
from tools.check_import_boundaries import check_tree
from tools.validate_task_core import load_json


def run(argv, *, cwd, env):
    result=subprocess.run([str(a) for a in argv],cwd=cwd,env=env,capture_output=True,text=True,encoding='utf-8',errors='replace',timeout=120,creationflags=subprocess.CREATE_NO_WINDOW if os.name=='nt' else 0)
    if result.returncode:raise RuntimeError('PACKAGE_COMMAND_FAILED:'+Path(str(argv[0])).name+'\n'+result.stderr[-2000:])
    return result.stdout.strip()


def interpreter(root):return root/('Scripts/python.exe' if os.name=='nt' else 'bin/python')


def main():
    if os.name!='nt' or platform.python_version()!='3.13.5' or platform.machine().lower() not in ('amd64','x86_64'):
        print('Package-install acceptance currently targets Windows x64 / Python 3.13.5',file=sys.stderr);return 1
    errors=validate_baseline(load_json(BASELINE));module_count,import_errors=check_tree()
    if errors or import_errors:print('BASELINE_OR_IMPORT_BOUNDARY_FAILED',file=sys.stderr);return 1
    run_root=ROOT/'.dev-tools/package-validation'/uuid4().hex
    run_root.mkdir(parents=True,exist_ok=False)
    env=dict(os.environ)
    for key in list(env):
        if key.startswith(('OPENAI_','ANTHROPIC_','WHATTODO_')) or key in ('PYTHONPATH','PYTHONHOME'):env.pop(key,None)
    env.update(PIP_NO_INDEX='1',PIP_DISABLE_PIP_VERSION_CHECK='1',PYTHONNOUSERSITE='1',PYTHONUTF8='1')
    report=dict(task='M3A-01',status='IN_PROGRESS',scope='PRIVATE_PACKAGE_SYNTHETIC_ACCEPTANCE',python_version=platform.python_version(),import_modules_checked=module_count,optional_credentials='ABSENT_IN_CHILD_ENV',network='DISABLED_FOR_BUILD_AND_INSTALL',global_environment_modified=False)
    try:
        build_env=run_root/'builder';clean_env=run_root/'installed';venv.EnvBuilder(with_pip=True).create(build_env);venv.EnvBuilder(with_pip=True).create(clean_env)
        builder=interpreter(build_env);installed=interpreter(clean_env)
        run([builder,'-m','pip','install','--no-index','--find-links',ROOT/'.dev-tools/wheelhouse/build','--require-hashes','-r',ROOT/'requirements-build.lock'],cwd=run_root,env=env)
        wheel_dir=run_root/'wheels'
        run([builder,'-m','pip','wheel','--no-build-isolation','--no-deps','--wheel-dir',wheel_dir,ROOT],cwd=run_root,env=env)
        wheels=list(wheel_dir.glob('whattodo_core-0.1.0.dev0-*.whl'))
        if len(wheels)!=1:raise RuntimeError('PACKAGE_WHEEL_IDENTITY')
        wheel=wheels[0]
        with zipfile.ZipFile(wheel) as archive:
            names=archive.namelist()
            if any('/intake/' in n or n.startswith(('tests/','tools/','plan/','.')) for n in names):raise RuntimeError('PRIVATE_OR_DEVELOPER_ARTIFACT_PACKAGED')
            schemas=[n for n in names if n.endswith('.schema.json')]
            if len(schemas)!=30:raise RuntimeError('PACKAGED_CONTRACT_COVERAGE')
        run([installed,'-m','pip','install','--no-index','--find-links',ROOT/'.dev-tools/wheelhouse/core','--require-hashes','-r',ROOT/'requirements-runtime.lock'],cwd=run_root,env=env)
        local_lock=run_root/'package.lock'
        digest=sha256(wheel.read_bytes()).hexdigest()
        local_lock.write_text(wheel.as_uri()+' --hash=sha256:'+digest+'\n',encoding='utf-8')
        run([installed,'-m','pip','install','--no-index','--no-deps','--require-hashes','-r',local_lock],cwd=run_root,env=env)
        report['pip_check']=run([installed,'-m','pip','check'],cwd=run_root,env=env)
        code="""import json,pathlib,sys,sysconfig,importlib.util,importlib.metadata
from datetime import datetime,timezone,date
import src
from src.application.package_smoke import domain_smoke
from src.adapters.packaged_contracts import load_contract_schemas
from src.adapters.contract_json import ContractJSONCodec
from src.adapters.clocks import FrozenClock
from src.domain.time_values import UtcInstant,DateOnly
from src.adapters.runtime_config import load_runtime_config
from src.adapters.migration_files import load_migration_plan
from src.adapters.postgres_migrations import DatabaseRoles
schemas=load_contract_schemas()
codec=ContractJSONCodec(schemas)
assert pathlib.Path(src.__file__).resolve().is_relative_to(pathlib.Path(sys.prefix).resolve())
assert importlib.util.find_spec('psycopg') is None
assert len(schemas)==30
clock=FrozenClock(datetime(2026,12,31,16,tzinfo=timezone.utc))
assert UtcInstant(clock.now()).beijing_date==date(2027,1,1)
assert DateOnly.parse('2027-01-01').as_due(source_ref='synthetic-source').instant.hour==23
config=load_runtime_config(pathlib.Path(sysconfig.get_path('data'))/'share/whattodo/config/runtime.example.json',env={})
assert config.definitions==()
plan=load_migration_plan()
assert len(plan.steps)==7
assert plan.schema_version=='0.2.0-definition-cache'
DatabaseRoles('synthetic_migration','synthetic_application')
print(json.dumps(dict(version=importlib.metadata.version('whattodo-core'),installed_source=src.__file__,contracts=len(schemas),postgres_driver='ABSENT_OPTIONAL',domain=domain_smoke(),clock_check='BEIJING_YEAR_ROLLOVER',configuration=config.safe_summary(),migration_steps=len(plan.steps),schema_version=plan.schema_version,migration_module='IMPORTS_WITHOUT_OPTIONAL_DRIVER')))
"""
        observed=json.loads(run([installed,'-I','-c',code],cwd=run_root,env=env))
        script=clean_env/'Scripts/whattodo-smoke.exe'
        entry=json.loads(run([script],cwd=run_root,env=env))
        if entry!=observed['domain']:raise RuntimeError('INSTALLED_ENTRYPOINT_MISMATCH')
        report.update(status='PASS',wheel=wheel.relative_to(ROOT).as_posix(),wheel_sha256=digest,packaged_schema_count=len(schemas),installed_checks=observed,entrypoint=entry,clean_install=True,source_checkout_import='EXCLUDED_BY_ISOLATED_INTERPRETER',build_lock='requirements-build.lock',runtime_lock='requirements-runtime.lock',limitations=['Private Windows/Python development package only','Not a deployed command transport, persistence adapter or authenticated user channel','Real provider/profile activation remains deferred'])
    except (RuntimeError,OSError,subprocess.SubprocessError,ValueError) as exc:
        report.update(status='FAIL',diagnostic=str(exc)[-2500:]);print(report['diagnostic'],file=sys.stderr)
    target=run_root/'report.json';target.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print('Package acceptance report: '+str(target))
    return 0 if report['status']=='PASS' else 1


if __name__=='__main__':raise SystemExit(main())
