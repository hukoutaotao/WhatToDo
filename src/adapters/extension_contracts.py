"""Opt-in versioned wire extensions, separate from the frozen base registry."""
from hashlib import sha256
import json
from pathlib import Path
import sysconfig

from src.adapters.contract_json import strict_json
from src.adapters.packaged_contracts import ContractResourceError,load_contract_schemas


def load_extension_schemas(*,root=None):
    resource=Path(sysconfig.get_path('data'))/'share/whattodo' if root is None else Path(root)
    try:
        resource=resource.resolve();registry=strict_json((resource/'formats/extension-registry.json').read_bytes())
        if not isinstance(registry,dict):raise ContractResourceError('EXTENSION_RESOURCES_UNREADABLE')
        if registry.get('registry_version')!='0.1.0-extensions' or registry.get('scope')!='GENERIC_DEVELOPMENT_ONLY':
            raise ContractResourceError('EXTENSION_RESOURCE_VERSION')
        result={}
        for entry in registry['contracts']:
            name=entry['name'];target=(resource/entry['path']).resolve()
            if not isinstance(name,str) or not name.strip() or name in result or not target.is_relative_to(resource/'formats/extensions'):
                raise ContractResourceError('EXTENSION_RESOURCE_SCOPE')
            schema=strict_json(target.read_bytes())
            digest=sha256(json.dumps(schema,sort_keys=True,ensure_ascii=False,separators=(',',':'),allow_nan=False).encode()).hexdigest()
            if digest!=entry['schema_hash'] or schema['$id']!=entry['schema_id'] or [schema['properties']['schema_version']['const']]!=entry['supported_versions']:
                raise ContractResourceError('EXTENSION_RESOURCE_DRIFT')
            result[name]=schema
        if not result:raise ContractResourceError('EXTENSION_RESOURCES_REQUIRED')
        return result
    except ContractResourceError:raise
    except (OSError,UnicodeError,ValueError,KeyError,TypeError,RecursionError):
        raise ContractResourceError('EXTENSION_RESOURCES_UNREADABLE') from None


def load_supported_schemas(*,root=None):
    base=load_contract_schemas(root=root);extensions=load_extension_schemas(root=root)
    if set(base)&set(extensions):raise ContractResourceError('EXTENSION_BASE_NAME_COLLISION')
    return base|extensions
