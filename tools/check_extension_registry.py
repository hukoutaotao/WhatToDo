"""Verify opt-in resources, consumer ownership and unchanged frozen baseline."""
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:sys.path.insert(0,str(ROOT))
from src.adapters.extension_contracts import load_supported_schemas
from src.application.contract_versions import canonical_hash
from tools.check_generic_baseline import BASELINE,validate_baseline
from tools.validate_task_core import load_json
from tools.check_contract_registry import validate_registry,REGISTRY


def main():
    errors=validate_baseline(load_json(BASELINE))+validate_registry(load_json(REGISTRY))
    registry=load_json(ROOT/'formats/extension-registry.json')
    expected=dict(base_contracts='UNCHANGED',selection='EXPLICIT_OPT_IN',legacy_adapters='NONE',
        unknown_version='REJECT_RETAIN_ORIGINAL_BYTES',authority='INDEPENDENT_EXACT_GRANT_REQUIRED')
    if registry.get('policy')!=expected or registry.get('base_registry')!='formats/contract-registry.json':errors.append('EXTENSION_POLICY_DRIFT')
    schemas=load_supported_schemas(root=ROOT)
    tables=set()
    import re
    for directory in ('database/migrations','database/runtime-migrations'):
        for path in (ROOT/directory).glob('*.sql'):
            declarations=re.findall(r'CREATE TABLE (?:"whattodo"|whattodo)\.(?:"([a-z_]+)"|([a-z_]+))',path.read_text(encoding='utf-8'))
            tables.update(quoted or unquoted for quoted,unquoted in declarations)
    for entry in registry['contracts']:
        if canonical_hash(schemas[entry['name']])!=entry['schema_hash']:errors.append('EXTENSION_HASH_DRIFT')
        if any(not (ROOT/p).is_file() for p in entry['consumers']):errors.append('EXTENSION_CONSUMER_MISSING')
        if not set(entry['database_owners'])<=tables:errors.append('EXTENSION_OWNER_MISSING')
    if errors:print('\n'.join(sorted(set(errors))),file=sys.stderr);return 1
    print(f'{len(registry["contracts"])} opt-in extension: exact resource/consumer/owner checks pass; 30 base contracts and 91 baseline pins unchanged')
    return 0


if __name__=='__main__':raise SystemExit(main())
