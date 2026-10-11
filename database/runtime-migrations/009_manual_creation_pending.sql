-- Lossless manual creation drafts whose essential facts are unresolved.
BEGIN;
SET LOCAL search_path=pg_catalog;
CREATE TABLE whattodo.manual_creation_pending (
    pending_id whattodo.ref PRIMARY KEY,
    command_id whattodo.ref NOT NULL,
    principal_id whattodo.ref NOT NULL,
    source_record_ref whattodo.ref NOT NULL,
    intent_hash whattodo.sha256 NOT NULL,
    command_hash whattodo.sha256 NOT NULL,
    desired_task_id whattodo.ref NOT NULL,
    proposal_hash whattodo.sha256 NOT NULL,
    proposal_bytes bytea NOT NULL CHECK(octet_length(proposal_bytes)>0 AND octet_length(proposal_bytes)<=1048576),
    created_at whattodo.instant NOT NULL,
    UNIQUE(principal_id,command_id,intent_hash),
    CHECK(encode(sha256(proposal_bytes),'hex')=proposal_hash),
    CHECK(((convert_from(proposal_bytes,'UTF8')::jsonb)#>>'{command,command_id}'=command_id) IS TRUE),
    CHECK(((convert_from(proposal_bytes,'UTF8')::jsonb)#>>'{command,principal_id}'=principal_id) IS TRUE),
    CHECK(((convert_from(proposal_bytes,'UTF8')::jsonb)#>>'{command,changes,0,task_id}'=desired_task_id) IS TRUE),
    CHECK(((convert_from(proposal_bytes,'UTF8')::jsonb)#>>'{resolved_creation,intent_fingerprint}'=intent_hash) IS TRUE),
    CHECK(((convert_from(proposal_bytes,'UTF8')::jsonb)#>>'{resolved_creation,command_fingerprint}'=command_hash) IS TRUE),
    CHECK(((convert_from(proposal_bytes,'UTF8')::jsonb)#>>'{resolved_creation,source_ref}'=source_record_ref) IS TRUE),
    CHECK((jsonb_typeof((convert_from(proposal_bytes,'UTF8')::jsonb)->'missing_fields')='array'
        AND jsonb_array_length((convert_from(proposal_bytes,'UTF8')::jsonb)->'missing_fields')>0) IS TRUE),
    FOREIGN KEY(source_record_ref) REFERENCES whattodo.source_record(record_id) DEFERRABLE INITIALLY DEFERRED
);
CREATE TRIGGER preserve_history BEFORE UPDATE OR DELETE OR TRUNCATE ON whattodo.manual_creation_pending
FOR EACH STATEMENT EXECUTE FUNCTION whattodo.reject_history_mutation();
REVOKE ALL ON whattodo.manual_creation_pending FROM PUBLIC;
COMMIT;
