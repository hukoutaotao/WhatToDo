"""Package ownership and boundary failures, independent of the build backend."""
from copy import deepcopy
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import tomllib
import unittest

import src
from src.adapters.packaged_contracts import ContractResourceError,load_contract_schemas
from src.application.package_smoke import domain_smoke
from tools.check_contracts import SCHEMAS
from tools.check_import_boundaries import check_tree,inspect_source
from tools.validate_task_core import ROOT,load_json


class PackageFoundationTests(unittest.TestCase):
    def test_domain_smoke_preserves_user_and_natural_day_values(self):
        self.assertEqual(domain_smoke(),dict(scope='SYNTHETIC_PACKAGE_CHECK',budget_seconds=1800,budget_source='USER_FALLBACK',beijing_start_date='2026-01-01',beijing_end_date='2026-01-03',canonical_user_seconds=1800))

    def test_actual_module_import_boundaries_and_metadata_resolve(self):
        count,errors=check_tree()
        self.assertGreaterEqual(count,20);self.assertEqual(errors,())
        project=tomllib.loads((ROOT/'pyproject.toml').read_text(encoding='utf-8'))
        self.assertEqual(project['project']['version'],src.__version__)
        self.assertEqual(project['tool']['setuptools']['packages'],['src','src.domain','src.application','src.adapters'])
        self.assertNotIn('psycopg',str(project['project']['dependencies']))

    def test_provider_and_reverse_dependency_imports_are_rejected(self):
        for source,module,code in [('import psycopg','src.domain.example','DOMAIN_IMPORT'),('from src.adapters.fakes import FakeClock','src.domain.example','DOMAIN_IMPORT'),('from ..application import ports','src.domain.example','DOMAIN_IMPORT'),('from src.adapters.fakes import FakeClock','src.application.example','APPLICATION_BOUNDARY'),('from tests import fixture','src.adapters.example','ADAPTER_TEST_DEPENDENCY')]:
            with self.subTest(source=source):self.assertIn(code,[e[1] for e in inspect_source(source,module=module)])

    def test_wall_clock_alias_and_dynamic_execution_are_rejected(self):
        for source in ['from datetime import datetime as D\nD.now()','import datetime as dt\ndt.date.today()','exec("import os")']:
            self.assertTrue(inspect_source(source,module='src.domain.example'))

    def test_exact_schema_resources_resolve_without_profiles(self):
        schemas=load_contract_schemas(root=ROOT)
        self.assertEqual(set(schemas),set(SCHEMAS))
        self.assertEqual(len(schemas),30)

    def test_resource_drift_outside_scope_and_malformed_root_are_redacted(self):
        original=load_json(ROOT/'formats/contract-registry.json')
        for mutation,expected in [('hash','CONTRACT_RESOURCE_DRIFT'),('outside','CONTRACT_RESOURCE_SCOPE'),('root','CONTRACT_RESOURCES_UNREADABLE')]:
            with TemporaryDirectory() as tmp:
                root=Path(tmp);(root/'formats/input').mkdir(parents=True)
                registry=deepcopy(original);entry=next(e for e in registry['contracts'] if e['name']=='task-core');registry['contracts']=[entry]
                (root/entry['path']).write_bytes((ROOT/entry['path']).read_bytes())
                if mutation=='hash':entry['schema_hash']='0'*64
                elif mutation=='outside':entry['path']='../secret-value'
                else:registry=[]
                (root/'formats/contract-registry.json').write_text(json.dumps(registry),encoding='utf-8')
                with self.assertRaises(ContractResourceError) as caught:load_contract_schemas(root=root)
                self.assertEqual(str(caught.exception),expected)
                self.assertNotIn('secret-value',str(caught.exception))


if __name__=='__main__':unittest.main()
