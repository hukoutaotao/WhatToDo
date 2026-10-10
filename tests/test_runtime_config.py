"""Config layers preserve versioned data without storing secrets or authority."""
from copy import deepcopy
from pathlib import Path
from tempfile import TemporaryDirectory
import json
import unittest

from src.adapters.runtime_config import ConfigurationError,load_runtime_config
from src.application.contract_versions import canonical_hash
from tools.validate_task_core import ROOT,load_json


class RuntimeConfigurationTests(unittest.TestCase):
    def setUp(self):
        self.temp=TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.root=Path(self.temp.name)
        self.base=self.root/'base.json';self.data=load_json(ROOT/'config/runtime.example.json');self.write(self.base,self.data)

    def write(self,path,value):path.write_text(json.dumps(value,ensure_ascii=False),encoding='utf-8')

    def load(self,**kwargs):return load_runtime_config(self.base,env=kwargs.pop('env',{}),**kwargs)

    def definition(self):
        body=dict(kind='TASKTYPE',id='synthetic-workflow',version='1',body=dict(importance=3,description='private-definition-body'))
        path=self.root/'definition.json';self.write(path,body)
        ref=dict(kind=body['kind'],id=body['id'],version=body['version'],path=path.name,content_hash=canonical_hash(body))
        self.data['definitions']=[ref];self.write(self.base,self.data)
        return body,ref,path

    def test_example_core_starts_without_optional_credentials(self):
        config=self.load()
        self.assertEqual(config.planning_timezone,'Asia/Shanghai')
        self.assertEqual(config.definitions,())
        self.assertEqual(config.safe_summary()['adapter_modes']['predictor'],'DISABLED')
        self.assertEqual(config.safe_summary()['authority'],'CONFIGURATION_DATA_NOT_ACTIVATION_AUTHORITY')

    def test_partial_override_and_secret_reference_precedence(self):
        override=self.root/'local.json';self.write(override,dict(adapters=dict(predictor=dict(mode='LIVE',secret_env='SYNTHETIC_MODEL_KEY'))))
        config=self.load(override_path=override,env={'SYNTHETIC_MODEL_KEY':'do-not-print-secret-value'})
        predictor=next(a for a in config.adapters if a.name=='predictor')
        self.assertEqual(predictor.mode,'LIVE');self.assertEqual(predictor.secret_ref.env_name,'SYNTHETIC_MODEL_KEY')
        self.assertNotIn('do-not-print-secret-value',repr(config));self.assertNotIn('do-not-print-secret-value',json.dumps(config.safe_summary()))
        self.assertEqual(next(a.mode for a in config.adapters if a.name=='state_store'),'FAKE')

    def test_disabled_missing_reference_is_ignored_but_enabled_fails(self):
        self.data['adapters']['predictor']['secret_env']='SYNTHETIC_MODEL_KEY';self.write(self.base,self.data)
        self.load()
        self.data['adapters']['predictor']['mode']='LIVE';self.write(self.base,self.data)
        with self.assertRaises(ConfigurationError) as caught:self.load()
        self.assertEqual(str(caught.exception),'CONFIG_ENABLED_SECRET_UNAVAILABLE')
        self.data['adapters']['state_store']['mode']='LIVE';self.data['adapters']['state_store']['secret_env']=None
        self.data['adapters']['predictor']['mode']='DISABLED';self.write(self.base,self.data)
        with self.assertRaises(ConfigurationError):self.load()

    def test_versioned_definition_body_is_detached_and_not_activation(self):
        self.definition();config=self.load();body=config.definitions[0].body;body['importance']=5
        self.assertEqual(config.definitions[0].body['importance'],3)
        self.assertNotIn('private-definition-body',repr(config));self.assertNotIn('private-definition-body',json.dumps(config.safe_summary()))

    def test_changed_definition_or_wrong_header_version_requires_review(self):
        body,ref,path=self.definition();body['body']['importance']=5;self.write(path,body)
        with self.assertRaises(ConfigurationError) as caught:self.load()
        self.assertEqual(str(caught.exception),'CONFIG_DEFINITION_HASH')
        body['version']='2';self.write(path,body);ref['content_hash']=canonical_hash(body);self.write(self.base,self.data)
        with self.assertRaises(ConfigurationError) as caught:self.load()
        self.assertEqual(str(caught.exception),'CONFIG_DEFINITION_VERSION')

    def test_outside_path_and_multiple_active_versions_fail(self):
        body,ref,path=self.definition();ref['path']='../private-secret-path';self.write(self.base,self.data)
        with self.assertRaises(ConfigurationError) as caught:self.load()
        self.assertEqual(str(caught.exception),'CONFIG_DEFINITION_PATH_SCOPE')
        ref['path']=path.name;self.data['definitions'].append(deepcopy(ref));self.write(self.base,self.data)
        with self.assertRaises(ConfigurationError) as caught:self.load()
        self.assertEqual(str(caught.exception),'CONFIG_DUPLICATE_ACTIVE_DEFINITION')

    def test_malformed_config_is_redacted_and_timezone_cannot_drift(self):
        for mutation,code in [(lambda d:d.update(secret_value='never-print-this'), 'CONFIG_FIELDS'),(lambda d:d.update(planning_timezone='America/Denver'),'CONFIG_PLANNING_TIMEZONE'),(lambda d:d['adapters']['predictor'].update(mode=['LIVE']),'CONFIG_ADAPTER_MODE'),(lambda d:d['adapters']['predictor'].update(secret_env='token://never-print-this'),'CONFIG_SECRET_REFERENCE')]:
            data=load_json(ROOT/'config/runtime.example.json');mutation(data);self.write(self.base,data)
            with self.assertRaises(ConfigurationError) as caught:self.load()
            self.assertEqual(str(caught.exception),code);self.assertNotIn('never-print-this',str(caught.exception))

    def test_duplicate_json_and_unhashable_definition_kind_fail_clearly(self):
        self.base.write_text('{"secret":"never-print-this","secret":1}',encoding='utf-8')
        with self.assertRaises(ConfigurationError) as caught:self.load()
        self.assertEqual(str(caught.exception),'CONFIG_BASE_UNREADABLE')
        body,ref,path=self.definition();ref['kind']=[];self.write(self.base,self.data)
        with self.assertRaises(ConfigurationError) as caught:self.load()
        self.assertEqual(str(caught.exception),'CONFIG_DEFINITION_IDENTITY')

    def test_invalid_environment_oversized_file_and_unicode_fail_clearly(self):
        with self.assertRaises(ConfigurationError) as caught:self.load(env=[])
        self.assertEqual(str(caught.exception),'CONFIG_ENVIRONMENT_MAPPING')
        self.base.write_bytes(b' ' * 1048577)
        with self.assertRaises(ConfigurationError) as caught:self.load()
        self.assertEqual(str(caught.exception),'CONFIG_INPUT_TOO_LARGE')
        body,ref,path=self.definition();body['body']['description']='\ud800'
        path.write_text(json.dumps(body,ensure_ascii=True),encoding='utf-8')
        with self.assertRaises(ConfigurationError) as caught:self.load()
        self.assertEqual(str(caught.exception),'CONFIG_DEFINITION_ENCODING')


if __name__=='__main__':unittest.main()
