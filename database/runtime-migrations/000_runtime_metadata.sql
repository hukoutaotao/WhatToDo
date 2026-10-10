-- Runtime migration metadata, separate from the immutable M2 domain draft.
BEGIN;
SET LOCAL search_path = pg_catalog;
CREATE SCHEMA whattodo_meta;
REVOKE ALL ON SCHEMA whattodo_meta FROM PUBLIC;
CREATE FUNCTION whattodo_meta.reject_history_mutation() RETURNS trigger
LANGUAGE plpgsql SET search_path=pg_catalog AS $guard$
BEGIN
    RAISE EXCEPTION 'Migration history is immutable' USING ERRCODE='23514';
END;
$guard$;
REVOKE ALL ON FUNCTION whattodo_meta.reject_history_mutation() FROM PUBLIC;
CREATE TABLE whattodo_meta.migration_history (
    position integer PRIMARY KEY CHECK(position>0),
    migration_id text NOT NULL UNIQUE CHECK(migration_id~'^[0-9]{3}_[a-z0-9_]+$'),
    content_hash text NOT NULL CHECK(content_hash~'^[a-f0-9]{64}$'),
    schema_version text NOT NULL CHECK(length(schema_version)>0),
    applied_at timestamptz NOT NULL CHECK(isfinite(applied_at))
);
CREATE TABLE whattodo_meta.schema_state (
    singleton boolean PRIMARY KEY CHECK(singleton),
    generation integer NOT NULL CHECK(generation>=0),
    schema_version text NOT NULL,
    recovery_required boolean NOT NULL,
    failed_migration_id text,
    CHECK(recovery_required=(failed_migration_id IS NOT NULL))
);
INSERT INTO whattodo_meta.schema_state VALUES(TRUE,0,'UNINITIALIZED',FALSE,NULL);
CREATE TABLE whattodo_meta.migration_failure (
    attempt_id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    migration_id text NOT NULL,
    content_hash text NOT NULL CHECK(content_hash~'^[a-f0-9]{64}$'),
    error_code text NOT NULL CHECK(error_code~'^[A-Z0-9]{5}$'),
    failed_at timestamptz NOT NULL CHECK(isfinite(failed_at))
);
CREATE TRIGGER preserve_history BEFORE UPDATE OR DELETE OR TRUNCATE
ON whattodo_meta.migration_history FOR EACH STATEMENT
EXECUTE FUNCTION whattodo_meta.reject_history_mutation();
CREATE TRIGGER preserve_history BEFORE UPDATE OR DELETE OR TRUNCATE
ON whattodo_meta.migration_failure FOR EACH STATEMENT
EXECUTE FUNCTION whattodo_meta.reject_history_mutation();
REVOKE ALL ON ALL TABLES IN SCHEMA whattodo_meta FROM PUBLIC;
REVOKE ALL ON ALL SEQUENCES IN SCHEMA whattodo_meta FROM PUBLIC;
COMMIT;
