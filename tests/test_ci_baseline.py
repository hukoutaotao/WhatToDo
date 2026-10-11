"""Security and failure propagation at the CI publication boundary."""
from contextlib import redirect_stdout
from io import StringIO
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch
from tools.ci_checks import ROOT,CIError,anchors,check_secrets,check_documents,check_workflow,child_environment,closed_result,source_paths
from tools.run_ci import run,process,native_summary

class CIBaselineTests(unittest.TestCase):
    def test_child_environment_excludes_provider_git_pip_python_and_pg_overrides(self):
        env=child_environment(Path('owned'),dict(PATH='git-path',SystemRoot='windows',OPENAI_API_KEY='synthetic',WHATTODO_DB_URL='synthetic',PGHOST='external',PGOPTIONS='unsafe',PYTHONPATH='outside',PIP_INDEX_URL='outside',GITHUB_TOKEN='synthetic',GIT_CONFIG_COUNT='1'))
        self.assertEqual(env['PATH'],'git-path')
        self.assertTrue(set(env).isdisjoint({'OPENAI_API_KEY','WHATTODO_DB_URL','PGHOST','PGOPTIONS','PYTHONPATH','PIP_INDEX_URL','GITHUB_TOKEN','GIT_CONFIG_COUNT'}))
        self.assertEqual(env['GIT_TERMINAL_PROMPT'],'0')
    def test_secret_signature_is_blocked_without_echoing_the_value(self):
        with TemporaryDirectory() as d:
            p=Path(d)/'source.py';value='sk-'+'a'*30;p.write_text(value,encoding='utf-8')
            with self.assertRaisesRegex(CIError,'CI_SECRET_SIGNATURE_OR_CREDENTIAL_FILE') as e:check_secrets(Path(d))
            self.assertNotIn(value,str(e.exception))
    def test_local_credential_file_is_blocked_even_without_known_token(self):
        with TemporaryDirectory() as d:
            (Path(d)/'.env').write_text('value=synthetic',encoding='utf-8')
            with self.assertRaisesRegex(CIError,'CREDENTIAL_FILE'):check_secrets(Path(d))
    def test_owned_state_is_excluded_and_workflow_is_included(self):
        with TemporaryDirectory() as d:
            root=Path(d);(root/'.local-state').mkdir();(root/'.local-state/.env').write_text('synthetic',encoding='utf-8');(root/'.github').mkdir();p=root/'.github/source.txt';p.write_text('reviewed',encoding='utf-8')
            self.assertEqual(source_paths(root),[p]);self.assertEqual(check_secrets(root)['files_checked'],1)
    def test_synthetic_fixture_annotation_does_not_exempt_other_credentials(self):
        with TemporaryDirectory() as d:
            root=Path(d);p=root/'tests/test_development_backup.py';p.parent.mkdir();p.write_text('postgresql://user'+':password@host',encoding='utf-8');self.assertEqual(check_secrets(root)['files_checked'],1)
            p.write_text('postgresql://user'+':different-password@host',encoding='utf-8')
            with self.assertRaises(CIError):check_secrets(root)
    def test_duplicate_and_inline_code_heading_anchors(self):
        self.assertEqual(anchors('# `Example`\n# Example\n```\n# Hidden\n```'),{'example','example-1'})
    def test_broken_links_and_fragments_fail(self):
        with TemporaryDirectory() as d:
            root=Path(d);p=root/'README.md';p.write_text('[missing](missing.md)',encoding='utf-8')
            with self.assertRaisesRegex(CIError,'LINK_MISSING'):check_documents(root)
            p.write_text('# Real\n[missing](#missing)',encoding='utf-8')
            with self.assertRaisesRegex(CIError,'FRAGMENT_MISSING'):check_documents(root)
    def test_cyclic_task_prerequisites_fail_with_valid_links(self):
        with TemporaryDirectory() as d:
            root=Path(d);p=root/'plan/tasks/T.md';p.parent.mkdir(parents=True);p.write_text('### M3A-01\n- Prerequisites: [M3A-02](#m3a-02)\n### M3A-02\n- Prerequisites: [M3A-01](#m3a-01)',encoding='utf-8')
            with self.assertRaisesRegex(CIError,'DEPENDENCY_CYCLE'):check_documents(root)
    def test_workflow_cannot_add_live_secrets_or_deployment_or_soft_failure(self):
        original=json.loads((ROOT/'.github/workflows/baseline.yml').read_text(encoding='utf-8'))
        with TemporaryDirectory() as d:
            root=Path(d);p=root/'.github/workflows/baseline.yml';p.parent.mkdir(parents=True)
            for field,value in [('continue-on-error',True),('environment','production'),('secrets','inherit')]:
                w=json.loads(json.dumps(original));w['jobs']['baseline'][field]=value;p.write_text(json.dumps(w),encoding='utf-8')
                with self.assertRaisesRegex(CIError,'WORKFLOW_POLICY'):check_workflow(root)
    def test_closed_diagnostics_reject_arbitrary_text_or_secret_fields(self):
        for kw in (dict(code='synthetic secret text'),dict(counts={'secret':'synthetic'}),dict(counts={'raw-content':1})):
            with self.assertRaises(CIError):closed_result('authority','FAIL',**kw)
    def test_secret_failure_precedes_bootstrap_and_publishes_only_closed_report(self):
        with TemporaryDirectory() as d:
            root=Path(d);value='ghp_'+'a'*36;(root/'source.txt').write_text(value,encoding='utf-8');out=StringIO()
            with patch('tools.run_ci.process',side_effect=AssertionError('Child must not start')),redirect_stdout(out):rc=run(root=root,bootstrap=True)
            self.assertEqual(rc,1);report=json.loads(next((root/'.local-state/ci-artifacts').glob('*.json')).read_text(encoding='utf-8'))
            self.assertEqual(report['checks'],[{'check':'secrets','status':'FAIL','code':'CI_SECRET_SIGNATURE_OR_CREDENTIAL_FILE'}]);self.assertNotIn(value,json.dumps(report)+out.getvalue())
    def test_child_error_is_fail_closed_without_publishing_process_output(self):
        from subprocess import CompletedProcess
        sentinel='synthetic-sensitive-diagnostic'
        with patch('tools.run_ci.subprocess.run',return_value=CompletedProcess(['child'],7,stdout=sentinel.encode(),stderr=sentinel.encode())):
            self.assertEqual(process(['child'],environment={}),7)
    def test_native_summary_rejects_missing_cleanup_and_closed_count_only(self):
        with TemporaryDirectory() as d:
            root=Path(d);p=root/'.local-state/postgres-tests/synthetic/migration-report.json';p.parent.mkdir(parents=True)
            value={'status':'PASS','native_checks':['synthetic'],'harness':{'server_stopped':False,'databases_created':1,'databases_dropped':1,'initdb_password_file_retained':False},'raw_content':'synthetic-sensitive'};p.write_text(json.dumps(value),encoding='utf-8')
            with self.assertRaisesRegex(CIError,'CLEANUP_OR_RESULT'):native_summary(root,'native_migrations',set())
            value['harness']['server_stopped']=True;p.write_text(json.dumps(value),encoding='utf-8');self.assertEqual(native_summary(root,'native_migrations',set()),dict(native_checks=1,databases_created=1,databases_dropped=1,server_stopped=True))

if __name__=='__main__':unittest.main()
