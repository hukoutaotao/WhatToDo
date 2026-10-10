"""Resolve the offline version/ownership registry against authoritative files."""
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path: sys.path.insert(0, str(ROOT))
from src.application.contract_versions import canonical_hash
from tools.check_contracts import SCHEMAS
from tools.validate_task_core import load_json

REGISTRY = ROOT / "formats/contract-registry.json"


def validate_registry(registry):
    errors = []
    if not isinstance(registry, dict): return ["REGISTRY_OBJECT_REQUIRED"]
    if registry.get("registry_version") != "0.1.0-draft" or registry.get("evidence_level") != "OFFLINE_NOT_RELEASE_FROZEN": errors.append("REGISTRY_SCOPE_MISMATCH")
    policy = registry.get("policy", {})
    expected = {"unknown_version": "REJECT_RETAIN_ORIGINAL_BYTES", "missing_version": "REJECT_NO_DEFAULT", "unknown_fields": "SCHEMA_POLICY_NO_SILENT_DROP", "automatic_legacy_adapters": "NONE_IMPLEMENTED", "structural_optional_addition": "BREAKING_FOR_STRICT_OLD_CONSUMERS", "complex_schema_change": "REVIEW_REQUIRED_INVALIDATE_CONSUMERS", "domain_authority": "REQUIRED_AFTER_VERSION_AND_SHAPE"}
    if policy != expected: errors.append("REGISTRY_POLICY_MISMATCH")
    contracts = registry.get("contracts")
    if not isinstance(contracts, list) or not all(isinstance(row, dict) and isinstance(row.get("name"), str) for row in contracts): return errors + ["REGISTRY_CONTRACTS_REQUIRED"]
    if len(contracts) != len(SCHEMAS) or {c["name"] for c in contracts} != set(SCHEMAS): return errors + ["REGISTRY_COVERAGE_MISMATCH"]
    ownership = {c["contract"]: c["tables"] for c in load_json(ROOT / "database/design/ownership.json")["contract_ownership"]}
    for row in contracts:
        path = SCHEMAS[row["name"]]
        schema = load_json(path)
        if row.get("path") != path.relative_to(ROOT).as_posix() or row.get("schema_id") != schema["$id"] or row.get("schema_hash") != canonical_hash(schema): errors.append("REGISTRY_SCHEMA_DRIFT")
        version = schema.get("properties", {}).get("schema_version", {}).get("const")
        if row.get("supported_versions") != [version] or row.get("adapters") != []: errors.append("REGISTRY_VERSION_OR_ADAPTER_DRIFT")
        if row.get("database_owners") != ownership[row["name"]]: errors.append("REGISTRY_OWNERSHIP_DRIFT")
        consumers = row.get("consumers")
        if not isinstance(consumers, list) or not consumers or not all(isinstance(p, str) and (ROOT / p).resolve().is_relative_to(ROOT) and (ROOT / p).is_file() for p in consumers): errors.append("REGISTRY_CONSUMER_MISSING")
    return sorted(set(errors))


def trusted_schemas():
    registry = load_json(REGISTRY)
    if validate_registry(registry): raise ValueError("Contract registry requires explicit review")
    return {name: load_json(path) for name, path in SCHEMAS.items()}


def main():
    try: errors = validate_registry(load_json(REGISTRY))
    except (ValueError, OSError, KeyError, TypeError): errors = ["REGISTRY_UNREADABLE"]
    if errors:
        print("\n".join(errors), file=sys.stderr); return 1
    print(f"{len(SCHEMAS)} draft contracts: exact versions/hashes/owners/consumers resolve; release gate remains open")
    return 0


if __name__ == "__main__": raise SystemExit(main())
