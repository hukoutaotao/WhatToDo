"""Standard-library preflight and closed diagnostics for synthetic CI only."""
from collections import Counter
from hashlib import sha256
import json
import os
from pathlib import Path
import re
import unicodedata
from urllib.parse import unquote,urlsplit

ROOT=Path(__file__).resolve().parents[1]
SKIP=frozenset(('.git','.venv','.dev-tools','.local-state','.agents','.codex','.aws','__pycache__','build','dist'))
ACTIONS={
    'actions/checkout':'df4cb1c069e1874edd31b4311f1884172cec0e10',
    'actions/setup-python':'a309ff8b426b58ec0e2a45f0f869d46889d02405',
    'actions/upload-artifact':'b7c566a772e6b6bfb58ed0dc250532a479d7789f'}

class CIError(RuntimeError):
    """Codes, never raw process output, source values or arbitrary exceptions."""

def need(condition,code):
    if not condition:raise CIError(code)

def source_paths(root=ROOT):
    root=Path(root).resolve();paths=[]
    for directory,folders,files in os.walk(root,followlinks=False):
        folders[:]=sorted(n for n in folders if n not in SKIP and not n.endswith('.egg-info'))
        need(all(not (Path(directory)/n).is_symlink() for n in folders),'CI_SOURCE_SYMLINK')
        for n in sorted(files):
            p=Path(directory)/n
            if p.suffix in ('.pyc','.pyo'):continue
            need(not p.is_symlink() and p.resolve().is_relative_to(root),'CI_SOURCE_SCOPE');paths.append(p)
    return paths

SECRET_PATTERNS=tuple(re.compile(p) for p in (
    r'\bsk-(?:proj-)?[A-Za-z0-9_-]{20,}',r'\bgh[pousr]_[A-Za-z0-9]{30,}',
    r'\bgithub_pat_[A-Za-z0-9_]{30,}',r'\bAIza[A-Za-z0-9_-]{30,}',
    r'\b(?:AKIA|ASIA)[A-Z0-9]{16}\b',r'-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----',
    r'''postgres(?:ql)?://[A-Za-z0-9._~%+-]+:[^\s/@"']+@[^\s"']+'''))

# Two existing negative validator fixtures, not a file-wide exemption. The
# fingerprint covers the exact matched synthetic URI only.
SYNTHETIC_MATCHES={('tests/test_development_backup.py',6):{
    '641a417beeb1ed2bfbbd2ffcdd4f1164f4a31930be7c4ea8e170534b0f3aa2bb',
    '78f1cda58359f568c7b720d112c56c3a3265c5b7c0c102887b875594f5bf2792'}}

def check_secrets(root=ROOT):
    paths=source_paths(root);findings=0
    for p in paths:
        n=p.name.lower()
        if n in ('.env','.pgpass','.netrc','credentials.json','token.json') or p.suffix.lower() in ('.pem','.p12','.pfx','.key') or n.startswith('.env.') and n not in ('.env.example','.env.sample'):
            findings+=1;continue
        need(p.stat().st_size<=2097152,'CI_SOURCE_SIZE_LIMIT')
        raw=p.read_bytes()
        try:s=raw.decode('utf-8')
        except UnicodeError:raise CIError('CI_SOURCE_ENCODING') from None
        for family,pattern in enumerate(SECRET_PATTERNS):
            for match in pattern.finditer(s):
                reviewed=SYNTHETIC_MATCHES.get((p.relative_to(root).as_posix(),family),set())
                if sha256(match[0].encode()).hexdigest() not in reviewed:findings+=1
    need(findings==0,'CI_SECRET_SIGNATURE_OR_CREDENTIAL_FILE')
    return dict(files_checked=len(paths),signature_families=len(SECRET_PATTERNS))

def slug(heading):
    text=re.sub(r'<[^>]+>','',heading).strip().lower()
    text=''.join(c for c in text if c in ('-','_',' ') or unicodedata.category(c)[0] in ('L','N'))
    return text.replace(' ','-')

def markdown(text):
    # Skip fenced code before evaluating links/headings; inline code stays in
    # headings because GitHub retains its text in the corresponding anchor.
    lines=[];fence=None
    for line in text.splitlines():
        match=re.match(r'^\s*(`{3,}|~{3,})',line)
        if match:
            marker=match[1][0]
            if fence is None:fence=marker
            elif fence==marker:fence=None
            continue
        if fence is None:lines.append(line)
    return '\n'.join(lines)

def anchors(text):
    result=set();counts=Counter()
    for line in markdown(text).splitlines():
        m=re.match(r'^#{1,6}\s+(.+?)\s*#*$',line)
        if m:
            key=slug(m[1]);index=counts[key];counts[key]+=1;result.add(key+('-'+str(index) if index else ''))
    result.update(re.findall(r'<(?:a|[a-z]+)\s+[^>]*?(?:id|name)=[\"\']([^\"\']+)[\"\']',text))
    return result

def check_documents(root=ROOT):
    root=Path(root).resolve();paths=[p for p in source_paths(root) if p.suffix=='.md'];cache={p:anchors(p.read_text(encoding='utf-8')) for p in paths};links=fragments=0
    for p in paths:
        text=markdown(p.read_text(encoding='utf-8'))
        for target in re.findall(r'\]\((<[^>]+>|[^\s)]+)(?:\s+"[^"]*")?\)',text):
            parsed=urlsplit(target.strip('<>'))
            if parsed.scheme:continue
            need(not parsed.netloc and not parsed.query,'CI_DOCUMENT_LINK_SCOPE')
            dest=(p.parent/unquote(parsed.path)).resolve() if parsed.path else p
            need(dest.is_relative_to(root) and dest.exists(),'CI_DOCUMENT_LINK_MISSING');links+=1
            if parsed.fragment:
                need(dest in cache and unquote(parsed.fragment) in cache[dest],'CI_DOCUMENT_FRAGMENT_MISSING');fragments+=1
    # Catalog links are already checked above; additionally prove its dependency
    # graph references exact definitions and stays acyclic.
    nodes={};dependencies={}
    for p in paths:
        if p.parent!=root/'plan/tasks':continue
        text=p.read_text(encoding='utf-8')
        for m in re.finditer(r'^### (M[0-9][A-Z]?-\d+(?:\.[a-z])?)\s*$',text,re.M):
            key=m[1];need(key not in nodes,'CI_TASK_ID_DUPLICATE');nodes[key]=(p,m.end())
    for key,(p,start) in nodes.items():
        rest=p.read_text(encoding='utf-8')[start:];end=re.search(r'^### ',rest,re.M);section=rest[:end.start()] if end else rest
        line=next((x for x in section.splitlines() if x.startswith('- Prerequisites:')),'')
        dependencies[key]=set(re.findall(r'\[(M[0-9][A-Z]?-\d+(?:\.[a-z])?)\]',line))
        need(dependencies[key]<=nodes.keys(),'CI_TASK_DEPENDENCY_MISSING')
    visiting=set();done=set()
    def visit(key):
        need(key not in visiting,'CI_TASK_DEPENDENCY_CYCLE')
        if key in done:return
        visiting.add(key)
        for dep in dependencies[key]:visit(dep)
        visiting.remove(key);done.add(key)
    for key in nodes:visit(key)
    return dict(markdown_files=len(paths),local_links=links,fragments=fragments,task_definitions=len(nodes))

def check_workflow(root=ROOT):
    # JSON is YAML's closed flow-style subset. No additional unpinned YAML parser.
    try:w=json.loads((Path(root)/'.github/workflows/baseline.yml').read_text(encoding='utf-8'))
    except (OSError,ValueError):raise CIError('CI_WORKFLOW_SHAPE') from None
    need(set(w)=={'name','on','permissions','jobs'} and set(w['on'])=={'push','pull_request','workflow_dispatch'} and w['permissions']=={'contents':'read'},'CI_WORKFLOW_POLICY')
    need(set(w['jobs'])=={'baseline'},'CI_WORKFLOW_POLICY');job=w['jobs']['baseline']
    need(set(job)=={'runs-on','timeout-minutes','defaults','steps'} and job['runs-on']=='windows-2022' and job['timeout-minutes']==35 and job['defaults']=={'run':{'shell':'pwsh'}},'CI_WORKFLOW_POLICY')
    steps=job['steps'];need(isinstance(steps,list) and len(steps)==4,'CI_WORKFLOW_POLICY')
    need(steps[0]=={'name':'Checkout','uses':'actions/checkout@'+ACTIONS['actions/checkout'],'with':{'persist-credentials':False,'fetch-depth':1}},'CI_WORKFLOW_POLICY')
    need(steps[1]=={'name':'Pinned Python','uses':'actions/setup-python@'+ACTIONS['actions/setup-python'],'with':{'python-version':'3.13.5','architecture':'x64'}},'CI_WORKFLOW_POLICY')
    need(steps[2]=={'name':'Synthetic baseline','run':'python tools/run_ci.py --bootstrap'},'CI_WORKFLOW_POLICY')
    need(steps[3]=={'name':'Closed diagnostics','if':'${{ always() }}','uses':'actions/upload-artifact@'+ACTIONS['actions/upload-artifact'],'with':{'name':'synthetic-baseline-diagnostics','path':'.local-state/ci-artifacts/*.json','include-hidden-files':True,'if-no-files-found':'warn','retention-days':7}},'CI_WORKFLOW_POLICY')
    return dict(action_pins=len(ACTIONS),deployment_steps=0,provider_secrets=0)

def check_contract_cases(root=ROOT):
    from tools.check_contracts import validate_contract
    root=Path(root);cases=0;bundles=sorted((root/'tests/fixtures').glob('*/cases.json'))
    need(bool(bundles),'CI_CONTRACT_FIXTURE_COVERAGE')
    for p in bundles:
        value=json.loads(p.read_text(encoding='utf-8'));need(value.get('synthetic') is True,'CI_CONTRACT_FIXTURE_AUTHORITY')
        for case in value['cases']:
            contract=case.get('contract','task-core' if p.parent.name=='task_core' else None)
            need(type(case['valid']) is bool and (not validate_contract(contract,case['payload'])) is case['valid'],'CI_CONTRACT_EXPECTATION_FAILED');cases+=1
    return dict(synthetic_bundles=len(bundles),shape_cases=cases)

def child_environment(temp,environment=None):
    source=os.environ if environment is None else environment
    allowed={'SYSTEMROOT','WINDIR','COMSPEC','PATH','PATHEXT','NUMBER_OF_PROCESSORS','PROCESSOR_ARCHITECTURE'}
    env={k:v for k,v in source.items() if k.upper() in allowed}
    env.update(TEMP=str(temp),TMP=str(temp),PYTHONUTF8='1',PYTHONNOUSERSITE='1',PIP_CONFIG_FILE=os.devnull,PIP_DISABLE_PIP_VERSION_CHECK='1',GIT_CONFIG_NOSYSTEM='1',GIT_CONFIG_GLOBAL=os.devnull,GIT_TERMINAL_PROMPT='0')
    return env

def closed_result(check,status,*,exit_code=None,code=None,counts=None):
    need(re.fullmatch('[a-z][a-z0-9_]{0,63}',check) and status in ('PASS','FAIL'),'CI_DIAGNOSTIC_SHAPE')
    value=dict(check=check,status=status)
    if exit_code is not None:need(type(exit_code) is int,'CI_DIAGNOSTIC_SHAPE');value['exit_code']=exit_code
    if code is not None:need(re.fullmatch('CI_[A-Z0-9_]+',code),'CI_DIAGNOSTIC_SHAPE');value['code']=code
    if counts is not None:
        need(isinstance(counts,dict) and all(re.fullmatch('[a-z][a-z0-9_]{0,63}',k) and type(v) in (int,bool) for k,v in counts.items()),'CI_DIAGNOSTIC_SHAPE');value['counts']=counts
    return value

def source_digest(root=ROOT):
    h=sha256()
    for p in source_paths(root):
        raw=p.relative_to(root).as_posix().encode();body=p.read_bytes()
        h.update(len(raw).to_bytes(8,'big'));h.update(raw);h.update(len(body).to_bytes(8,'big'));h.update(body)
    return h.hexdigest()
