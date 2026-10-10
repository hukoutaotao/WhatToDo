"""Version/shape admission for trusted checked-in schemas; never authorizes writes.

All outcomes retain exact original immutable bytes/hash. Schema support is
separate from domain references, independently authenticated callers and commit.
"""
from dataclasses import dataclass
from hashlib import sha256
import json
import math
from types import MappingProxyType

from jsonschema import Draft202012Validator, FormatChecker


def _pairs(pairs):
    result = {}
    for key, value in pairs:
        if key in result: raise ValueError("Duplicate JSON key")
        result[key] = value
    return result


def _constant(value):
    raise ValueError("Nonfinite JSON constant")


def _float(value):
    result = float(value)
    if not math.isfinite(result): raise ValueError("Nonfinite JSON exponent")
    return result


def strict_json(raw):
    return json.loads(raw.decode("utf-8"), object_pairs_hook=_pairs, parse_constant=_constant, parse_float=_float)


def _check_local_references(value):
    if isinstance(value, dict):
        for key, item in value.items():
            if key in ("$ref", "$dynamicRef", "$recursiveRef") and (not isinstance(item, str) or not item.startswith("#")):
                raise ValueError("Offline admission requires locally resolved schemas")
            if key in ("properties", "$defs", "definitions", "patternProperties", "dependentSchemas"):
                for child in item.values(): _check_local_references(child)
            elif key in ("allOf", "anyOf", "oneOf", "prefixItems"):
                for child in item: _check_local_references(child)
            elif key in ("additionalProperties", "unevaluatedProperties", "items", "contains", "propertyNames", "not", "if", "then", "else", "additionalItems", "unevaluatedItems", "contentSchema"):
                _check_local_references(item)


@dataclass(frozen=True)
class InputAdmission:
    contract: str
    status: str
    reason: str
    raw_bytes: bytes
    content_hash: str
    schema_version: str | None
    issues: tuple[tuple[str, str], ...] = ()

    @property
    def payload(self):
        if self.status != "SUPPORTED_SHAPE": raise ValueError("Input has not passed supported-version/shape admission")
        return strict_json(self.raw_bytes)

    def __bool__(self):
        raise TypeError("Inspect admission status; shape support is not authority")


class ContractJSONCodec:
    def __init__(self, trusted_schemas):
        if not isinstance(trusted_schemas, dict) or not trusted_schemas: raise ValueError("Trusted local schemas are required")
        records = {}
        for name, schema in trusted_schemas.items():
            if not isinstance(name, str) or not name.strip() or not isinstance(schema, dict): raise ValueError("Explicit contract/schema ownership is required")
            # Own a detached snapshot; caller mutation cannot alter support.
            schema = json.loads(json.dumps(schema, allow_nan=False))
            Draft202012Validator.check_schema(schema)
            _check_local_references(schema)
            version = schema.get("properties", {}).get("schema_version", {}).get("const")
            if not isinstance(version, str) or not version.strip(): raise ValueError("An exact schema version is required")
            records[name] = (version, Draft202012Validator(schema, format_checker=FormatChecker()))
        self._schemas = MappingProxyType(records)

    def admit(self, contract, raw):
        if not isinstance(contract, str) or not isinstance(raw, bytes): raise ValueError("Contract name and immutable bytes are required")
        digest = sha256(raw).hexdigest()
        def result(status, reason, version=None, issues=()):
            return InputAdmission(contract, status, reason, raw, digest, version, issues)
        if contract not in self._schemas: return result("REJECTED", "UNKNOWN_CONTRACT")
        # Parser work is bounded; rejection preserves bytes for source history.
        if len(raw) > 262144: return result("REJECTED", "INPUT_TOO_LARGE")
        try: payload = strict_json(raw)
        except (UnicodeError, ValueError, RecursionError): return result("REJECTED", "MALFORMED_JSON")
        if not isinstance(payload, dict): return result("REJECTED", "OBJECT_REQUIRED")
        version = payload.get("schema_version")
        if not isinstance(version, str): return result("REJECTED", "VERSION_REQUIRED")
        expected, validator = self._schemas[contract]
        if version != expected: return result("REJECTED", "UNSUPPORTED_VERSION", version)
        try:
            errors = tuple(sorted({("/" + "/".join(str(p).replace("~", "~0").replace("/", "~1") for p in error.absolute_path), str(error.validator)) for error in validator.iter_errors(payload)}))
        except RecursionError:
            return result("REJECTED", "VALIDATION_LIMIT", version)
        if errors: return result("REJECTED", "INVALID_SHAPE", version, errors)
        return result("SUPPORTED_SHAPE", "DOMAIN_AND_AUTHORITY_CHECKS_REQUIRED", version)
