"""Read immutable bundled schema definitions; never activate profiles or Tasks."""
from hashlib import sha256
import json
from pathlib import Path
import sysconfig

from src.adapters.contract_json import strict_json


class ContractResourceError(ValueError):
    """Redacted startup diagnostic, without file contents or submitted values."""


def load_contract_schemas(*, root: Path | None = None):
    resource_root = Path(sysconfig.get_path("data"))/"share/whattodo" if root is None else Path(root)
    try:
        resource_root = resource_root.resolve()
        registry = strict_json((resource_root/"formats/contract-registry.json").read_bytes())
        if not isinstance(registry,dict): raise ContractResourceError("CONTRACT_RESOURCES_UNREADABLE")
        if registry.get("registry_version") != "0.1.0-draft" or registry.get("evidence_level") != "OFFLINE_NOT_RELEASE_FROZEN":
            raise ContractResourceError("CONTRACT_RESOURCE_VERSION")
        contracts = registry["contracts"]
        if not isinstance(contracts,list) or not contracts: raise ContractResourceError("CONTRACT_RESOURCES_REQUIRED")
        result = {}
        for entry in contracts:
            name,path = entry["name"],entry["path"]
            if not isinstance(path,str): raise ContractResourceError("CONTRACT_RESOURCE_SCOPE")
            target = (resource_root/path).resolve()
            if not isinstance(name,str) or not name.strip() or name in result or not target.is_relative_to(resource_root):
                raise ContractResourceError("CONTRACT_RESOURCE_SCOPE")
            schema = strict_json(target.read_bytes())
            digest = sha256(json.dumps(schema,sort_keys=True,ensure_ascii=False,separators=(",",":"),allow_nan=False).encode()).hexdigest()
            if digest != entry["schema_hash"] or schema["$id"] != entry["schema_id"] or [schema["properties"]["schema_version"]["const"]] != entry["supported_versions"]:
                raise ContractResourceError("CONTRACT_RESOURCE_DRIFT")
            result[name] = schema
        return result
    except ContractResourceError: raise
    except (OSError,UnicodeError,ValueError,KeyError,TypeError,RecursionError):
        raise ContractResourceError("CONTRACT_RESOURCES_UNREADABLE") from None
