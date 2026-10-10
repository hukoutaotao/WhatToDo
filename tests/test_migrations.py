"""Migration pins, transaction boundaries and compatibility failure semantics."""
from copy import deepcopy
from dataclasses import replace
from pathlib import Path
from tempfile import TemporaryDirectory
from hashlib import sha256
import json
import unittest

from src.adapters.migration_files import load_migration_plan,migration_body
from src.adapters.postgres_migrations import DatabaseRoles
from src.application.migrations import MigrationError,MigrationPlan,MigrationRecord,SchemaState,check_history

ROOT=Path(__file__).resolve().parents[1]


class MigrationTests(unittest.TestCase):
    def setUp(self):self.plan=load_migration_plan(root=ROOT,manifest_path=ROOT/'reports/acceptance/M3A-05-migration-plan.json')

    def records(self):return tuple(MigrationRecord(i+1,s.migration_id,s.content_hash,s.schema_version) for i,s in enumerate(self.plan.steps))

    def test_all_sources_pinned_and_complete_history_is_compatible(self):
        self.assertEqual(len(self.plan.steps),6)
        self.assertEqual(self.plan.steps[0].migration_id,'000_runtime_metadata')
        state=SchemaState(6,self.plan.schema_version,False,None)
        self.assertEqual(check_history(self.plan,self.records(),state,application_version='0.1.0.dev0',complete=True),6)
        for step in self.plan.steps:self.assertEqual(sha256(step.source_sql.encode()).hexdigest(),step.content_hash)

    def test_partial_and_failed_history_cannot_start_application(self):
        for state,code in [(SchemaState(1,self.plan.steps[0].schema_version,False,None),'MIGRATION_SCHEMA_INCOMPATIBLE'),(SchemaState(1,self.plan.steps[0].schema_version,True,self.plan.steps[1].migration_id),'MIGRATION_RECOVERY_REQUIRED')]:
            with self.assertRaises(MigrationError) as caught:check_history(self.plan,self.records()[:1],state,application_version='0.1.0.dev0',complete=True)
            self.assertEqual(str(caught.exception),code)
            self.assertEqual(check_history(self.plan,self.records()[:1],state,application_version='0.1.0.dev0'),1)

    def test_unknown_future_changed_hash_and_history_holes_fail(self):
        records=self.records();state=SchemaState(6,self.plan.schema_version,False,None)
        cases=[(records+(MigrationRecord(7,'006_future','f'*64,'future'),),'MIGRATION_UNKNOWN_APPLIED_VERSION'),(records[:-1]+(replace(records[-1],content_hash='f'*64),),'MIGRATION_APPLIED_DRIFT'),(records[1:],'MIGRATION_APPLIED_DRIFT')]
        for data,code in cases:
            with self.assertRaises(MigrationError) as caught:check_history(self.plan,data,state,application_version='0.1.0.dev0')
            self.assertEqual(str(caught.exception),code)

    def test_version_state_and_recovery_drift_fail(self):
        for state in [SchemaState(5,self.plan.schema_version,False,None),SchemaState(6,'future',False,None),SchemaState(6,self.plan.schema_version,True,'006_future'),SchemaState(6.0,self.plan.schema_version,False,None)]:
            with self.assertRaises(MigrationError):check_history(self.plan,self.records(),state,application_version='0.1.0.dev0')
        with self.assertRaises(MigrationError) as caught:check_history(self.plan,self.records(),SchemaState(6,self.plan.schema_version,False,None),application_version='9.0')
        self.assertEqual(str(caught.exception),'MIGRATION_APPLICATION_INCOMPATIBLE')

    def test_lexical_guard_preserves_function_literals_and_rejects_transaction_escape(self):
        source="BEGIN; /* nested /* comment */ remains */ CREATE FUNCTION f() RETURNS integer LANGUAGE plpgsql AS $f$ BEGIN PERFORM 1; RETURN 2; END; $f$; SELECT 'COMMIT;''still text'; COMMIT;"
        body=migration_body(source)
        self.assertIn('BEGIN PERFORM 1; RETURN 2; END;',body)
        self.assertIn("'COMMIT;''still text'",body)
        for escape in ('COMMIT','ROLLBACK','START TRANSACTION','SAVEPOINT nope','PREPARE TRANSACTION \'x\''):
            with self.assertRaises(MigrationError) as caught:migration_body('BEGIN; SELECT 1; '+escape+'; COMMIT;')
            self.assertEqual(str(caught.exception),'MIGRATION_TRANSACTION_CONTROL')
        with self.assertRaises(MigrationError):migration_body("BEGIN; SELECT E'a\\\'b'; COMMIT;")

    def test_missing_wrapper_unfinished_quote_comment_or_dollar_body_fail(self):
        for source in ['SELECT 1;','BEGIN; SELECT 1;','BEGIN; SELECT \'unclosed; COMMIT;','BEGIN; /* unfinished','BEGIN; DO $bad$ BEGIN NULL; END; COMMIT;']:
            with self.assertRaises(MigrationError):migration_body(source)

    def test_duplicate_or_out_of_order_steps_and_bad_pins_fail(self):
        for steps in [self.plan.steps[::-1],self.plan.steps+(self.plan.steps[-1],),self.plan.steps[:-1]+(replace(self.plan.steps[-1],content_hash='a'*64),)]:
            with self.assertRaises(MigrationError):MigrationPlan(self.plan.manifest_version,self.plan.application_versions,steps)

    def test_source_scope_and_changed_file_rejected_before_database_connection(self):
        original=json.loads((ROOT/'database/migration-plan.json').read_text(encoding='utf-8'))
        with TemporaryDirectory() as directory:
            root=Path(directory);(root/'database').mkdir()
            manifest=deepcopy(original);manifest['steps']=manifest['steps'][:1]
            step=manifest['steps'][0];step['path']='../private-secret-file'
            (root/'database/migration-plan.json').write_text(json.dumps(manifest),encoding='utf-8')
            with self.assertRaises(MigrationError) as caught:load_migration_plan(root=root)
            self.assertEqual(str(caught.exception),'MIGRATION_RESOURCE_SCOPE');self.assertNotIn('private-secret-file',str(caught.exception))
            step['path']='database/meta.sql';(root/step['path']).write_text('BEGIN; SELECT 1; COMMIT;',encoding='utf-8')
            (root/'database/migration-plan.json').write_text(json.dumps(manifest),encoding='utf-8')
            with self.assertRaises(MigrationError) as caught:load_migration_plan(root=root)
            self.assertEqual(str(caught.exception),'MIGRATION_HASH')

    def test_roles_are_distinct_and_sql_is_not_retained_in_error_repr(self):
        for names in [('same','same',None),('owner','app','app'),('owner','bad\x00role',None)]:
            with self.assertRaises(MigrationError):DatabaseRoles(*names)
        self.assertNotIn('CREATE TABLE',repr(self.plan))
        error=MigrationError('MIGRATION_STEP_FAILED',failed_migration='001_synthetic',sqlstate='22012')
        self.assertEqual(str(error),'MIGRATION_STEP_FAILED')


if __name__=='__main__':unittest.main()
