"""Fail-closed harness scope checks; native role probes run via the launcher."""
from pathlib import Path
from tempfile import TemporaryDirectory
import json
import unittest
from unittest.mock import patch

from tools.postgres_harness import ConnectionTarget,HarnessError,PostgresHarness,ROOT,owned_run,verify_identity


class PostgresHarnessTests(unittest.TestCase):
    def test_only_one_uuid_run_below_owned_root_is_accepted(self):
        chosen=ROOT/'.local-state/postgres-tests'/('a'*32)
        self.assertEqual(owned_run(chosen),chosen.resolve())
        for bad in (ROOT/'database',chosen.parent,chosen/'nested',chosen.parent/'existing',ROOT/'.local-state/toolchain'/('a'*32)):
            with self.assertRaises(HarnessError):owned_run(bad)

    def test_secret_targets_and_summary_do_not_expose_password(self):
        target=ConnectionTarget(5432,'synthetic','test','synthetic-password-never-print')
        self.assertNotIn('synthetic-password-never-print',repr(target))
        harness=PostgresHarness()
        for secret in harness._passwords.values():self.assertNotIn(secret,json.dumps(harness.safe_summary()))
        self.assertNotIn('password=',repr(harness))

    def test_unowned_database_and_role_are_rejected_without_connecting(self):
        harness=PostgresHarness()
        with patch.object(harness,'_admin',side_effect=AssertionError('Unexpected database connection')):
            with self.assertRaises(HarnessError):harness.drop_database('production')
            with self.assertRaises(HarnessError):harness.target('production')
            harness._active=True;harness._databases.add('synthetic')
            with self.assertRaises(HarnessError):harness.target('synthetic','bootstrap')

    def test_unrelated_server_is_rejected_before_any_write(self):
        class WrongConnection:
            def execute(self,statement):
                if statement!='SHOW data_directory':raise AssertionError('Unexpected SQL before identity match')
                return self
            def fetchone(self):return (str(ROOT/'unrelated'),)
        with self.assertRaises(HarnessError):verify_identity(WrongConnection(),ROOT/'expected','expected-name')

    def test_same_path_wrong_cluster_nonce_or_version_is_rejected(self):
        class FakeConnection:
            def __init__(self,name,version):self.name=name;self.version=version
            def execute(self,statement):
                self.value={'SHOW data_directory':str(ROOT/'expected'),'SHOW cluster_name':self.name,'SHOW server_version':self.version}[statement]
                return self
            def fetchone(self):return (self.value,)
        for name,version in [('wrong-name','18.6'),('expected','17.1')]:
            with self.assertRaises(HarnessError):verify_identity(FakeConnection(name,version),ROOT/'expected','expected')
        verify_identity(FakeConnection('expected','18.6'),ROOT/'expected','expected')

    def test_missing_or_changed_owner_marker_blocks_operations(self):
        with TemporaryDirectory() as directory:
            with patch('tools.postgres_harness.ROOT',Path(directory)):
                with patch('tools.postgres_harness.owned_run',side_effect=lambda path:owned_run(path,workspace=directory)):
                    harness=PostgresHarness()
                    harness.run_root.mkdir(parents=True)
                    with self.assertRaises(HarnessError):harness._owned()
                    marker=dict(run_id=harness.run_id,scope='SYNTHETIC_TEST_ONLY',cluster_name=harness.cluster_name)
                    (harness.run_root/'owner.json').write_text(json.dumps(marker),encoding='utf-8');harness._owned()
                    marker['scope']='PRODUCTION';(harness.run_root/'owner.json').write_text(json.dumps(marker),encoding='utf-8')
                    with self.assertRaises(HarnessError):harness._owned()


if __name__=='__main__':unittest.main()
