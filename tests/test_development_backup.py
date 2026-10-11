from dataclasses import replace
from datetime import datetime,timezone,timedelta
from decimal import Decimal
from hashlib import sha256
from pathlib import Path
from uuid import uuid4
import json
import shutil
import unittest
from src.adapters.migration_files import load_migration_plan
from src.adapters.runtime_config import load_runtime_config
from src.application.configuration import AdapterConfig,SecretRef
from src.application.definitions import canonical
from tools.development_backup import BackupBundle,BackupError,atom,config_references,checked_bundle,bundle_path,digest_file,row_digest,client_arguments,canonical_check
from tools.postgres_harness import PostgresHarness,owned_run
ROOT=Path(__file__).resolve().parents[1]
class DevelopmentBackupTests(unittest.TestCase):
    def setUp(self):
        self.h=PostgresHarness();self.h.run_root.mkdir(parents=True,exist_ok=False)
        self.root=self.h.run_root/('backup_'+uuid4().hex);self.root.mkdir()
        self.plan=load_migration_plan(root=ROOT);self.config=load_runtime_config(ROOT/'config/runtime.example.json',env={})
        refs=config_references(self.config);(self.root/'configuration-refs.json').write_bytes(canonical(refs).encode());(self.root/'database.dump').write_bytes(b'PGDMPsynthetic-archive-for-file-tests')
        self.manifest=dict(bundle_version='0.1.0-development-backup',scope='SYNTHETIC_OWNED_POSTGRES',postgres_version='18.6',application_version='0.1.0.dev0',schema_version=self.plan.schema_version,source=dict(run_id=self.h.run_id,database='wt_test_'+self.h.run_id+'_1'),captured_at='2026-01-01T00:00:00+00:00',migration_pins=[dict(id=s.migration_id,sha256=s.content_hash,schema_version=s.schema_version) for s in self.plan.steps],files={name:dict(sha256=sha256((self.root/name).read_bytes()).hexdigest(),bytes=(self.root/name).stat().st_size) for name in ('database.dump','configuration-refs.json')},inventory={})
        self.bundle=self.write_manifest()
    def tearDown(self):
        # Delete only this test's new UUID-owned directory after resolving scope.
        self.assertEqual(owned_run(self.h.run_root),self.h.run_root);shutil.rmtree(self.h.run_root)
    def write_manifest(self):
        raw=canonical(self.manifest).encode();(self.root/'manifest.json').write_bytes(raw);return BackupBundle(self.root,sha256(raw).hexdigest())
    def check(self,bundle=None,**kw):return checked_bundle(self.h,bundle or self.bundle,self.plan,kw.get('application_version','0.1.0.dev0'))
    def test_matching_bundle_references_are_detached(self):
        m,refs=self.check();self.assertEqual(m,self.manifest);self.assertEqual(refs,config_references(self.config));refs['adapters']['state_store']['mode']='LIVE';self.assertEqual(self.check()[1]['adapters']['state_store']['mode'],'FAKE')
    def test_independent_manifest_pin_required(self):
        for value in (None,'short','G'*64):
            with self.assertRaisesRegex(BackupError,'INDEPENDENT_MANIFEST_PIN'):self.check(BackupBundle(self.root,value))
    def test_manifest_tamper_is_rejected_even_after_valid_self_rehash(self):
        self.manifest['scope']='CHANGED';self.write_manifest()
        with self.assertRaisesRegex(BackupError,'MANIFEST_HASH_DRIFT'):self.check()
    def test_database_byte_corruption_rejected(self):
        p=self.root/'database.dump';v=p.read_bytes();p.write_bytes(v[:-1]+b'!')
        with self.assertRaisesRegex(BackupError,'FILE_HASH_DRIFT'):self.check()
    def test_valid_json_config_change_rejected(self):
        p=self.root/'configuration-refs.json';p.write_bytes(p.read_bytes()+b' ')
        with self.assertRaisesRegex(BackupError,'FILE_HASH_DRIFT'):self.check()
    def config_bundle(self,refs):
        p=self.root/'configuration-refs.json';p.write_bytes(canonical(refs).encode())
        self.manifest['files'][p.name]=dict(sha256=sha256(p.read_bytes()).hexdigest(),bytes=p.stat().st_size)
        return self.write_manifest()
    def test_configuration_rejects_embedded_values_even_with_trusted_file_pin(self):
        refs=config_references(self.config);refs['adapters']['state_store']['secret_value']='synthetic value'
        with self.assertRaisesRegex(BackupError,'CONFIG_REFERENCE_SHAPE'):self.check(self.config_bundle(refs))
    def test_configuration_rejects_nonobject_and_unsupported_identity(self):
        for refs in ([],dict(config_references(self.config),planning_timezone='UTC')):
            with self.assertRaisesRegex(BackupError,'CONFIG_REFERENCE_SHAPE'):self.check(self.config_bundle(refs))
    def test_configuration_rejects_duplicate_active_definition_references(self):
        refs=config_references(self.config);d=dict(kind='COURSE_PROFILE',id='synthetic-profile',version='v1',content_hash='a'*64);refs['definitions']=[d,dict(d,version='v2')]
        with self.assertRaisesRegex(BackupError,'CONFIG_REFERENCE_SHAPE'):self.check(self.config_bundle(refs))
    def test_extra_secret_file_rejected(self):
        (self.root/'secret.env').write_text('synthetic value',encoding='utf-8')
        with self.assertRaisesRegex(BackupError,'UNEXPECTED_BUNDLE_FILE'):self.check()
    def test_missing_archive_rejected(self):
        (self.root/'database.dump').unlink()
        with self.assertRaisesRegex(BackupError,'UNEXPECTED_BUNDLE_FILE'):self.check()
    def test_manifest_unknown_version_rejected(self):
        self.manifest['bundle_version']='future';b=self.write_manifest()
        with self.assertRaisesRegex(BackupError,'VERSION_OR_SCOPE'):self.check(b)
    def test_unknown_manifest_fields_rejected(self):
        self.manifest['credentials']={};b=self.write_manifest()
        with self.assertRaisesRegex(BackupError,'MANIFEST_SHAPE'):self.check(b)
    def test_application_version_drift_rejected(self):
        with self.assertRaisesRegex(BackupError,'MIGRATION_PLAN_DRIFT'):self.check(application_version='unsupported')
    def test_exact_migration_hashes_required(self):
        self.manifest['migration_pins'][0]['sha256']='a'*64;b=self.write_manifest()
        with self.assertRaisesRegex(BackupError,'MIGRATION_PLAN_DRIFT'):self.check(b)
    def test_arbitrary_file_paths_rejected(self):
        self.manifest['files']['../secret']=self.manifest['files'].pop('database.dump');b=self.write_manifest()
        with self.assertRaisesRegex(BackupError,'MANIFEST_FILE_SCOPE'):self.check(b)
    def test_zero_or_boolean_file_sizes_rejected(self):
        for value in (0,True,'10'):
            self.manifest['files']['database.dump']['bytes']=value;b=self.write_manifest()
            with self.assertRaisesRegex(BackupError,'FILE_PIN'):self.check(b)
    def test_non_postgresql_archive_magic_rejected(self):
        p=self.root/'database.dump';p.write_bytes(b'invalid archive');self.manifest['files']['database.dump']=dict(sha256=sha256(p.read_bytes()).hexdigest(),bytes=p.stat().st_size);b=self.write_manifest()
        with self.assertRaisesRegex(BackupError,'ARCHIVE_FORMAT'):self.check(b)
    def test_bundle_cannot_escape_owned_run(self):
        for path in (self.h.run_root.parent,self.h.run_root/'other',self.h.run_root/'nested'/self.root.name):
            with self.assertRaisesRegex(BackupError,'BUNDLE_SCOPE'):bundle_path(self.h,path)
    def test_file_digest_size_bound(self):
        with self.assertRaisesRegex(BackupError,'FILE_SIZE_OR_KIND'):digest_file(self.root/'database.dump',2)
    def test_configuration_export_contains_only_secret_references(self):
        adapters=tuple(AdapterConfig(a.name,'LIVE' if a.name=='state_store' else a.mode,SecretRef('WHATTODO_SYNTHETIC_DB_SECRET') if a.name=='state_store' else a.secret_ref) for a in self.config.adapters);refs=config_references(replace(self.config,adapters=adapters));self.assertEqual(refs['adapters']['state_store']['secret_env'],'WHATTODO_SYNTHETIC_DB_SECRET');self.assertNotIn('secret_value',canonical(refs));self.assertEqual(refs['authority'],'REFERENCES_ONLY_NO_ACTIVATION_OR_CREDENTIAL_VALUES')
    def test_configuration_requires_reviewed_shape_and_adapter_set(self):
        for value in (None,replace(self.config,planning_timezone='UTC'),replace(self.config,adapters=())):
            with self.assertRaises(BackupError):config_references(value)
    def test_secret_reference_rejects_connection_string_or_value(self):
        adapters=tuple(AdapterConfig(a.name,a.mode,SecretRef('postgresql://user:password@host')) if a.name=='state_store' else a for a in self.config.adapters)
        with self.assertRaisesRegex(BackupError,'CONFIG_REFERENCE'):config_references(replace(self.config,adapters=adapters))
    def test_database_timestamp_digest_is_timezone_independent(self):
        instant=datetime(2026,1,1,tzinfo=timezone.utc);self.assertEqual(atom(instant),atom(instant.astimezone(timezone(timedelta(hours=8)))))
        with self.assertRaisesRegex(BackupError,'NAIVE_DATABASE_TIME'):atom(datetime(2026,1,1))
    def test_exact_bytes_decimal_and_json_remain_distinct(self):
        self.assertEqual(atom(memoryview(b'\x00\xff')),dict(bytea='00ff'));self.assertNotEqual(atom(Decimal('1.00')),1);self.assertEqual(atom(dict(b=1,a=None)),dict(b=1,a=None))
    def test_streamed_row_digest_keeps_order_boundaries_and_nulls(self):
        class Rows:
            def __init__(self,rows):self.rows=iter([rows,[]])
            def fetchmany(self,n):return next(self.rows)
        self.assertNotEqual(row_digest(Rows([(1,None),(2,'x')])),row_digest(Rows([(2,'x'),(1,None)])))
        self.assertEqual(row_digest(Rows([]))['rows'],0)
    def test_manifest_source_database_identity_is_closed_and_owned(self):
        for source in (dict(run_id=self.h.run_id,database='production'),dict(run_id='bad',database='anything'),dict(run_id=self.h.run_id,database='wt_test_'+self.h.run_id+'_1',password='value')):
            self.manifest['source']=source;b=self.write_manifest()
            with self.assertRaisesRegex(BackupError,'SOURCE_IDENTITY'):self.check(b)
    def test_manifest_timestamp_requires_explicit_offset(self):
        for instant in ('invalid','2026-01-01T00:00:00',None):
            self.manifest['captured_at']=instant;b=self.write_manifest()
            with self.assertRaisesRegex(BackupError,'CAPTURE_TIME'):self.check(b)

    def test_client_arguments_reject_external_connection_and_overwrite_flags(self):
        from types import SimpleNamespace
        target=SimpleNamespace(database='owned')
        valid=['--single-transaction','--exit-on-error','--no-owner','--dbname=owned',str(self.root/'database.dump')]
        self.assertEqual(client_arguments(self.h,'pg_restore',valid,target=target),valid)
        for flag in ('--clean','--create','--host=external','--username=superuser','--dbname=postgresql://user:password@outside/db','--no-privileges'):
            with self.assertRaisesRegex(BackupError,'ARGUMENT_SCOPE'):client_arguments(self.h,'pg_restore',[flag,*valid],target=target)
    def test_client_arguments_reject_unowned_files_and_existing_output(self):
        with self.assertRaisesRegex(BackupError,'FILE_SCOPE'):client_arguments(self.h,'pg_restore',['--list',str(ROOT/'outside.dump')])
        with self.assertRaisesRegex(BackupError,'FILE_EXISTS'):client_arguments(self.h,'pg_restore',['--file='+str(self.root/'configuration-refs.json'),str(self.root/'database.dump')])
    def test_dump_arguments_must_use_both_owned_schemas_and_snapshot(self):
        from types import SimpleNamespace
        target=SimpleNamespace(database='owned');output=self.h.run_root/('backup_'+uuid4().hex)/'database.dump'
        valid=['--format=custom','--schema=whattodo','--schema=whattodo_meta','--strict-names','--snapshot=00000001-00000002-1','--file='+str(output)]
        self.assertEqual(client_arguments(self.h,'pg_dump',valid,target=target),valid)
        for bad in ([x for x in valid if x!='--schema=whattodo_meta'],[x.replace('--schema=whattodo','--schema=*') if x=='--schema=whattodo' else x for x in valid]):
            with self.assertRaisesRegex(BackupError,'ARGUMENT_SCOPE'):client_arguments(self.h,'pg_dump',bad,target=target)

    def test_check_associative_groups_normalize_without_changing_operands(self):
        self.assertEqual(canonical_check('CHECK (((a >= 1 AND a <= 5) AND (b >= 1 AND b <= 5)))'),canonical_check('CHECK ((a >= 1 AND a <= 5 AND (b >= 1 AND b <= 5)))'))
        self.assertNotEqual(canonical_check('CHECK ((a >= 1 AND a <= 5))'),canonical_check('CHECK ((a >= 1 AND a <= 6))'))
    def test_check_normalization_preserves_and_or_precedence(self):
        self.assertNotEqual(canonical_check('CHECK ((a OR b) AND c)'),canonical_check('CHECK (a OR (b AND c))'))
        self.assertNotEqual(canonical_check('CHECK ((a AND b) OR c)'),canonical_check('CHECK (a AND (b OR c))'))
        self.assertEqual(canonical_check('CHECK ((a OR b) OR c)'),canonical_check('CHECK (a OR (b OR c))'))
    def test_check_literals_and_no_inherit_remain_exact(self):
        self.assertNotEqual(canonical_check("CHECK ((name='A AND B') AND a>1)"),canonical_check("CHECK ((name='A OR B') AND a>1)"))
        self.assertNotEqual(canonical_check('CHECK (a>1)'),canonical_check('CHECK (a>1) NO INHERIT'))
        self.assertEqual(canonical_check('FOREIGN KEY (a) REFERENCES b(id)'), 'FOREIGN KEY (a) REFERENCES b(id)')
