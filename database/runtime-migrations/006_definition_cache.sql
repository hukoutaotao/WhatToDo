-- Forward migration: Git remains authoritative; these rows are immutable cache.
BEGIN;
SET LOCAL search_path=pg_catalog;
ALTER TABLE whattodo.configuration_revision ADD CONSTRAINT configuration_revision_exact_identity
UNIQUE(configuration_ref,kind,id,version,content_hash);
CREATE TABLE whattodo.definition_cache (
    kind whattodo.ref NOT NULL,
    id whattodo.ref NOT NULL,
    version whattodo.ref NOT NULL,
    configuration_ref whattodo.ref NOT NULL UNIQUE,
    content_hash whattodo.sha256 NOT NULL,
    git_path text NOT NULL CHECK(length(git_path)>0),
    blob_oid text NOT NULL CHECK(blob_oid~'^([a-f0-9]{40}|[a-f0-9]{64})$'),
    raw_hash whattodo.sha256 NOT NULL,
    raw_bytes bytea NOT NULL CHECK(octet_length(raw_bytes)>0 AND octet_length(raw_bytes)<=1048576),
    PRIMARY KEY(kind,id,version),
    CHECK(encode(sha256(raw_bytes),'hex')=raw_hash),
    CHECK(((convert_from(raw_bytes,'UTF8')::jsonb)->>'kind'=kind) IS TRUE),
    CHECK(((convert_from(raw_bytes,'UTF8')::jsonb)->>'id'=id) IS TRUE),
    CHECK(((convert_from(raw_bytes,'UTF8')::jsonb)->>'version'=version) IS TRUE),
    CHECK((jsonb_typeof((convert_from(raw_bytes,'UTF8')::jsonb)->'body')='object') IS TRUE),
    FOREIGN KEY(configuration_ref,kind,id,version,content_hash)
        REFERENCES whattodo.configuration_revision(configuration_ref,kind,id,version,content_hash)
        DEFERRABLE INITIALLY DEFERRED
);
CREATE TABLE whattodo.definition_reference (
    source_kind whattodo.ref NOT NULL,
    source_id whattodo.ref NOT NULL,
    source_version whattodo.ref NOT NULL,
    ordinal integer NOT NULL CHECK(ordinal>=0),
    target_kind whattodo.ref NOT NULL,
    target_id whattodo.ref NOT NULL,
    target_version whattodo.ref NOT NULL,
    PRIMARY KEY(source_kind,source_id,source_version,ordinal),
    UNIQUE(source_kind,source_id,source_version,target_kind,target_id,target_version),
    FOREIGN KEY(source_kind,source_id,source_version) REFERENCES whattodo.definition_cache(kind,id,version)
        DEFERRABLE INITIALLY DEFERRED,
    FOREIGN KEY(target_kind,target_id,target_version) REFERENCES whattodo.definition_cache(kind,id,version)
        DEFERRABLE INITIALLY DEFERRED
);
CREATE TRIGGER preserve_history BEFORE UPDATE OR DELETE OR TRUNCATE ON whattodo.definition_cache
FOR EACH STATEMENT EXECUTE FUNCTION whattodo.reject_history_mutation();
CREATE TRIGGER preserve_history BEFORE UPDATE OR DELETE OR TRUNCATE ON whattodo.definition_reference
FOR EACH STATEMENT EXECUTE FUNCTION whattodo.reject_history_mutation();
REVOKE ALL ON whattodo.definition_cache,whattodo.definition_reference FROM PUBLIC;
COMMIT;
