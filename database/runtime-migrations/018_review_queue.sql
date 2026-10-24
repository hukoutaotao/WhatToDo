-- Complete immutable review captures; additive runtime step pinned in the manifest.
BEGIN;
SET LOCAL search_path=pg_catalog;
CREATE TABLE whattodo.review_queue_snapshot (
 snapshot_id whattodo.ref PRIMARY KEY,
 principal_id whattodo.ref NOT NULL,
 request_id whattodo.ref NOT NULL,
 query_hash whattodo.sha256 NOT NULL,
 scope_hash whattodo.sha256 NOT NULL,
 store_revision whattodo.revision NOT NULL,
 last_transaction_ref whattodo.ref,
 observed_at whattodo.instant NOT NULL,
 expires_at whattodo.instant NOT NULL CHECK(expires_at>observed_at),
 item_count integer NOT NULL CHECK(item_count>=0 AND item_count<=1000000),
 entries_hash whattodo.sha256 NOT NULL,
 header_hash whattodo.sha256 NOT NULL,
 header_bytes bytea NOT NULL CHECK(octet_length(header_bytes)>0 AND octet_length(header_bytes)<=8388608),
 UNIQUE(principal_id,request_id),
 CHECK(encode(sha256(header_bytes),'hex')=header_hash),
 CHECK(((convert_from(header_bytes,'UTF8')::jsonb)-'query'-'groups'-'coverage_blockers'-'observed_at'-'expires_at'
  =jsonb_build_object('schema_version','0.1.0-review-queue-snapshot','snapshot_id',snapshot_id,'principal_id',principal_id,
   'request_id',request_id,'query_hash',query_hash,'scope_hash',scope_hash,'store_revision',store_revision,
   'last_transaction_ref',last_transaction_ref,'item_count',item_count,'entries_hash',entries_hash)) IS TRUE),
 CHECK((((convert_from(header_bytes,'UTF8')::jsonb)->>'observed_at')::timestamptz=observed_at) IS TRUE),
 CHECK((((convert_from(header_bytes,'UTF8')::jsonb)->>'expires_at')::timestamptz=expires_at) IS TRUE),
 CHECK((store_revision=1 AND last_transaction_ref IS NULL) OR (store_revision>1 AND last_transaction_ref IS NOT NULL)),
 FOREIGN KEY(last_transaction_ref,store_revision) REFERENCES whattodo.command_transaction(request_id,committed_store_revision) DEFERRABLE INITIALLY DEFERRED
);
CREATE TABLE whattodo.review_queue_entry (
 snapshot_id whattodo.ref NOT NULL,
 ordinal integer NOT NULL CHECK(ordinal>0 AND ordinal<=1000000),
 item_id whattodo.ref NOT NULL CHECK(item_id ~ '^review-item-[a-f0-9]{64}$'),
 payload_hash whattodo.sha256 NOT NULL,
 payload_bytes bytea NOT NULL CHECK(octet_length(payload_bytes)>0 AND octet_length(payload_bytes)<=2097152),
 PRIMARY KEY(snapshot_id,ordinal),
 UNIQUE(snapshot_id,item_id),
 CHECK(encode(sha256(payload_bytes),'hex')=payload_hash),
 CHECK(((convert_from(payload_bytes,'UTF8')::jsonb)->>'item_id'=item_id) IS TRUE),
 CHECK(((convert_from(payload_bytes,'UTF8')::jsonb)->'answer'='null'::jsonb
  AND (convert_from(payload_bytes,'UTF8')::jsonb)->'requires_response'=CASE
   WHEN (convert_from(payload_bytes,'UTF8')::jsonb)->>'kind'='SOURCE_BLOCKER'
    OR ((convert_from(payload_bytes,'UTF8')::jsonb)->>'kind'='CLARIFICATION'
     AND (convert_from(payload_bytes,'UTF8')::jsonb)->>'reason'='AWAITING_EXECUTION')
   THEN 'false'::jsonb ELSE 'true'::jsonb END) IS TRUE),
 FOREIGN KEY(snapshot_id) REFERENCES whattodo.review_queue_snapshot(snapshot_id) DEFERRABLE INITIALLY DEFERRED
);
CREATE TRIGGER preserve_history BEFORE UPDATE OR DELETE OR TRUNCATE ON whattodo.review_queue_snapshot
FOR EACH STATEMENT EXECUTE FUNCTION whattodo.reject_history_mutation();
CREATE TRIGGER preserve_history BEFORE UPDATE OR DELETE OR TRUNCATE ON whattodo.review_queue_entry
FOR EACH STATEMENT EXECUTE FUNCTION whattodo.reject_history_mutation();

CREATE FUNCTION whattodo.check_review_queue_capture() RETURNS trigger
LANGUAGE plpgsql SET search_path=pg_catalog AS $guard$
DECLARE n bigint; low integer; high integer; bytes bigint; actual_hash text;
BEGIN
 SELECT count(*),coalesce(min(ordinal),0),coalesce(max(ordinal),0),coalesce(sum(octet_length(payload_bytes)),0),
  encode(sha256(convert_to(coalesce(string_agg(ordinal::text||':'||item_id||':'||payload_hash||chr(10),'' ORDER BY ordinal),''),'UTF8')),'hex')
 INTO n,low,high,bytes,actual_hash FROM whattodo.review_queue_entry WHERE snapshot_id=NEW.snapshot_id;
 IF n<>NEW.item_count OR high<>n OR low<>(CASE WHEN n=0 THEN 0 ELSE 1 END) OR actual_hash<>NEW.entries_hash
  OR bytes+octet_length(NEW.header_bytes)>268435456 THEN
  RAISE EXCEPTION 'Review capture must include its exact full ordered membership' USING ERRCODE='23514';
 END IF;
 RETURN NEW;
END;
$guard$;
REVOKE ALL ON FUNCTION whattodo.check_review_queue_capture() FROM PUBLIC;
CREATE CONSTRAINT TRIGGER exact_review_capture AFTER INSERT ON whattodo.review_queue_snapshot
DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION whattodo.check_review_queue_capture();

CREATE FUNCTION whattodo.guard_review_queue_entry() RETURNS trigger
LANGUAGE plpgsql SET search_path=pg_catalog AS $guard$
BEGIN
 IF NOT EXISTS(SELECT 1 FROM whattodo.review_queue_snapshot s WHERE s.snapshot_id=NEW.snapshot_id
  AND NEW.ordinal<=s.item_count AND s.xmin::text::numeric=(pg_current_xact_id()::text::numeric % 4294967296)) THEN
  RAISE EXCEPTION 'Review entries belong to one new complete capture transaction' USING ERRCODE='23514';
 END IF;
 RETURN NEW;
END;
$guard$;
REVOKE ALL ON FUNCTION whattodo.guard_review_queue_entry() FROM PUBLIC;
CREATE TRIGGER exact_new_review_entry BEFORE INSERT ON whattodo.review_queue_entry
FOR EACH ROW EXECUTE FUNCTION whattodo.guard_review_queue_entry();
COMMIT;
