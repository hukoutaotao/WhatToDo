"""Atomic in-memory test cache sharing exact production definition values."""
from src.application.definitions import CachedDefinition,DefinitionError,need


class MemoryDefinitionRepository:
    def __init__(self,clock):self.clock=clock;self._records={}
    def get(self,key):return self._records.get(key)
    def register_artifacts(self,artifacts):
        artifacts=tuple(artifacts);proposed=dict(self._records);seen=set()
        for artifact in artifacts:
            key=artifact.key;need(key not in seen,'DEFINITION_DUPLICATE_IMPORT');seen.add(key)
            previous=proposed.get(key)
            if previous is not None:need(previous.artifact.request.content_hash==artifact.request.content_hash,'DEFINITION_IMMUTABLE_CONFLICT')
            else:proposed[key]=CachedDefinition(artifact,self.clock.now())
        for record in proposed.values():
            for reference in record.artifact.references:need(reference in proposed,'DEFINITION_UNRESOLVED_REFERENCE')
        self._records=proposed
        return tuple(self._records[artifact.key] for artifact in artifacts)
