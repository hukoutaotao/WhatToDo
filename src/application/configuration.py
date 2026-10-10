"""Validated runtime references; no credential values or activation authority."""
from dataclasses import dataclass,field
import json


@dataclass(frozen=True)
class SecretRef:
    env_name:str


@dataclass(frozen=True)
class AdapterConfig:
    name:str
    mode:str
    secret_ref:SecretRef|None


@dataclass(frozen=True)
class DefinitionSnapshot:
    kind:str
    definition_id:str
    version:str
    content_hash:str
    _body_json:str=field(repr=False)

    @property
    def body(self):return json.loads(self._body_json)


@dataclass(frozen=True)
class RuntimeConfig:
    schema_version:str
    planning_timezone:str
    definitions:tuple[DefinitionSnapshot,...]
    adapters:tuple[AdapterConfig,...]

    def safe_summary(self):
        return dict(schema_version=self.schema_version,planning_timezone=self.planning_timezone,definitions=[dict(kind=d.kind,id=d.definition_id,version=d.version) for d in self.definitions],adapter_modes={a.name:a.mode for a in self.adapters},authority='CONFIGURATION_DATA_NOT_ACTIVATION_AUTHORITY')
