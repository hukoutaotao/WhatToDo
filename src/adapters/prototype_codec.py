"""Larger bounded transport envelopes without widening frozen inner contracts."""
from hashlib import sha256
import json
from jsonschema import Draft202012Validator,FormatChecker
from src.adapters.contract_json import ContractJSONCodec,InputAdmission,strict_json
from src.application.command_transport import MAX_REQUEST_BYTES,MAX_RESPONSE_BYTES


class PrototypeJSONCodec:
    def __init__(self,trusted_schemas):
        self._base=ContractJSONCodec(trusted_schemas)
        self._transport={}
        for name in ('prototype-request','prototype-response'):
            if name not in trusted_schemas:raise ValueError('Explicit prototype schemas are required')
            schema=strict_json(json.dumps(trusted_schemas[name],allow_nan=False).encode())
            self._transport[name]=(schema['properties']['schema_version']['const'],Draft202012Validator(schema,format_checker=FormatChecker()))

    def admit(self,contract,raw):
        if contract not in self._transport:return self._base.admit(contract,raw)
        if not isinstance(raw,bytes):raise ValueError('Immutable transport bytes are required')
        digest=sha256(raw).hexdigest()
        def result(status,reason,version=None,issues=()):return InputAdmission(contract,status,reason,raw,digest,version,issues)
        maximum=MAX_REQUEST_BYTES if contract=='prototype-request' else MAX_RESPONSE_BYTES
        if len(raw)>maximum:return result('REJECTED','INPUT_TOO_LARGE')
        try:v=strict_json(raw)
        except (UnicodeError,ValueError,RecursionError):return result('REJECTED','MALFORMED_JSON')
        if not isinstance(v,dict):return result('REJECTED','OBJECT_REQUIRED')
        version=v.get('schema_version');expected,validator=self._transport[contract]
        if version!=expected:return result('REJECTED','UNSUPPORTED_VERSION',version if isinstance(version,str) else None)
        try:issues=tuple(sorted({('/'+'/'.join(str(x) for x in e.absolute_path),str(e.validator)) for e in validator.iter_errors(v)}))
        except RecursionError:return result('REJECTED','VALIDATION_LIMIT',version)
        return result('REJECTED','INVALID_SHAPE',version,issues) if issues else result('SUPPORTED_SHAPE','SUPPORTED_VERSION_AND_SHAPE',version)
