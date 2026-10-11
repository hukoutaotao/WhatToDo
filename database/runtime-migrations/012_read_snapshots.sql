-- Immutable owned query snapshots, separate from canonical Task state.
BEGIN;
SET LOCAL search_path=pg_catalog;
CREATE TABLE "whattodo"."read_snapshot" (
 snapshot_id whattodo.ref PRIMARY KEY,
 principal_id whattodo.ref NOT NULL,
 query_hash whattodo.sha256 NOT NULL,
 scope_hash whattodo.sha256 NOT NULL,
 store_revision whattodo.revision NOT NULL,
 last_transaction_ref whattodo.ref,
 observed_at whattodo.instant NOT NULL,
 expires_at whattodo.instant NOT NULL,
 payload_hash whattodo.sha256 NOT NULL,
 payload_bytes bytea NOT NULL,
 CHECK(expires_at>observed_at),
 CHECK((store_revision=1 AND last_transaction_ref IS NULL) OR (store_revision>1 AND last_transaction_ref IS NOT NULL)),
 CHECK(octet_length(payload_bytes)>0 AND octet_length(payload_bytes)<=8388608),
 CHECK(encode(sha256(payload_bytes),'hex')=payload_hash),
 CHECK(((convert_from(payload_bytes,'UTF8')::jsonb)->>'snapshot_id'=snapshot_id) IS TRUE),
 CHECK(((convert_from(payload_bytes,'UTF8')::jsonb)->>'principal_id'=principal_id) IS TRUE),
 CHECK(((convert_from(payload_bytes,'UTF8')::jsonb)->>'query_hash'=query_hash) IS TRUE),
 CHECK(((convert_from(payload_bytes,'UTF8')::jsonb)->>'scope_hash'=scope_hash) IS TRUE),
 CHECK((((convert_from(payload_bytes,'UTF8')::jsonb)->>'store_revision')::bigint=store_revision) IS TRUE),
 CHECK((((convert_from(payload_bytes,'UTF8')::jsonb)->>'observed_at')::timestamptz=observed_at) IS TRUE),
 CHECK((((convert_from(payload_bytes,'UTF8')::jsonb)->>'expires_at')::timestamptz=expires_at) IS TRUE),
 CHECK(((convert_from(payload_bytes,'UTF8')::jsonb)->>'last_transaction_ref') IS NOT DISTINCT FROM last_transaction_ref),
 FOREIGN KEY(last_transaction_ref,store_revision) REFERENCES whattodo.command_transaction(request_id,committed_store_revision) DEFERRABLE INITIALLY DEFERRED
);
CREATE TRIGGER preserve_history BEFORE UPDATE OR DELETE OR TRUNCATE ON whattodo.read_snapshot
FOR EACH STATEMENT EXECUTE FUNCTION whattodo.reject_history_mutation();
REVOKE ALL ON whattodo.read_snapshot FROM PUBLIC;
COMMIT;
