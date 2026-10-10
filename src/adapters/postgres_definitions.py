"""Git-backed immutable definition cache; no generic canonical write API."""
from src.adapters.git_definitions import GitDefinitionSource
from src.adapters.postgres_migrations import LOCK_KEY,schema_checked_transaction,_owner
from src.application.definitions import (CachedDefinition,DefinitionArtifact,DefinitionError,
    DefinitionKey,GitDefinitionRequest,need)

REGISTRY_LOCK=LOCK_KEY+1


class PostgresDefinitionRepository:
    def __init__(self,connection,source,plan,roles,*,application_version):
        need(isinstance(source,GitDefinitionSource),'DEFINITION_TRUSTED_GIT_SOURCE_REQUIRED')
        self.connection=connection;self.source=source;self.plan=plan;self.roles=roles;self.application_version=application_version

    def _record(self,key):
        need(isinstance(key,DefinitionKey),'DEFINITION_KEY')
        row=self.connection.execute('''SELECT c.content_hash,c.git_revision,c.registered_at,d.git_path,d.blob_oid,d.raw_bytes
            FROM whattodo.definition_cache d JOIN whattodo.configuration_revision c USING(configuration_ref,kind,id,version,content_hash)
            WHERE d.kind=%s AND d.id=%s AND d.version=%s''',(key.kind,key.id,key.version)).fetchone()
        if row is None:return None
        artifact=DefinitionArtifact(GitDefinitionRequest(row[1],row[3],row[0]),row[4],bytes(row[5]))
        need(artifact.key==key,'DEFINITION_CACHE_DRIFT')
        actual=tuple(DefinitionKey(*r) for r in self.connection.execute('SELECT target_kind,target_id,target_version FROM whattodo.definition_reference WHERE source_kind=%s AND source_id=%s AND source_version=%s ORDER BY ordinal',(key.kind,key.id,key.version)).fetchall())
        need(actual==artifact.references,'DEFINITION_CACHE_REFERENCE_DRIFT')
        return CachedDefinition(artifact,row[2])

    def get(self,key):
        with schema_checked_transaction(self.connection,self.plan,application_version=self.application_version):return self._record(key)

    def register(self,requests):
        import psycopg
        artifacts=tuple(self.source.read(request) for request in requests)
        keys=tuple(a.key for a in artifacts);need(len(set(keys))==len(keys),'DEFINITION_DUPLICATE_IMPORT')
        try:
            with schema_checked_transaction(self.connection,self.plan,application_version=self.application_version,read_only=False):
                _owner(self.connection,self.roles)
                need(self.connection.execute('SELECT pg_try_advisory_xact_lock(%s)',(REGISTRY_LOCK,)).fetchone()==(True,),'DEFINITION_IMPORT_BUSY')
                staged=[]
                for artifact in sorted(artifacts,key=lambda a:a.key):
                    key=artifact.key;previous=self._record(key)
                    if previous is not None:
                        need(previous.artifact.request.content_hash==artifact.request.content_hash,'DEFINITION_IMMUTABLE_CONFLICT');continue
                    header=self.connection.execute('SELECT configuration_ref,content_hash,git_revision FROM whattodo.configuration_revision WHERE kind=%s AND id=%s AND version=%s',(key.kind,key.id,key.version)).fetchone()
                    expected=(key.configuration_ref,artifact.request.content_hash,artifact.request.commit)
                    if header is not None:need(header==expected,'DEFINITION_EXISTING_HEADER_CONFLICT')
                    else:self.connection.execute('INSERT INTO whattodo.configuration_revision VALUES(%s,%s,%s,%s,%s,%s,CURRENT_TIMESTAMP)',(key.configuration_ref,key.kind,key.id,key.version,artifact.request.content_hash,artifact.request.commit))
                    self.connection.execute('INSERT INTO whattodo.definition_cache VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s)',(key.kind,key.id,key.version,key.configuration_ref,artifact.request.content_hash,artifact.request.path,artifact.blob_oid,artifact.raw_hash,artifact.raw_bytes))
                    staged.append(artifact)
                for artifact in staged:
                    source=artifact.key
                    for ordinal,target in enumerate(artifact.references):
                        need(self.connection.execute('SELECT EXISTS(SELECT 1 FROM whattodo.definition_cache WHERE kind=%s AND id=%s AND version=%s)',(target.kind,target.id,target.version)).fetchone()==(True,),'DEFINITION_UNRESOLVED_REFERENCE')
                        self.connection.execute('INSERT INTO whattodo.definition_reference VALUES(%s,%s,%s,%s,%s,%s,%s)',(source.kind,source.id,source.version,ordinal,target.kind,target.id,target.version))
                return tuple(self._record(key) for key in keys)
        except psycopg.Error:raise DefinitionError('DEFINITION_STORAGE_FAILED') from None
