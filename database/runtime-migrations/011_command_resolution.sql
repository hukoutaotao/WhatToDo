-- Owned process history for reference clarification, separate from Task writes.
BEGIN;
SET LOCAL search_path=pg_catalog;
CREATE TABLE "whattodo"."command_resolution_revision" (
    session_id whattodo.ref NOT NULL,
    revision whattodo.revision NOT NULL,
    previous_revision whattodo.revision,
    command_id whattodo.ref NOT NULL,
    principal_id whattodo.ref NOT NULL,
    state whattodo.ref NOT NULL CHECK(state IN ('NEEDS_COURSE','NEEDS_TASK','NEEDS_DETAILS','RESOLVED')),
    query_source_ref whattodo.ref NOT NULL,
    last_source_ref whattodo.ref NOT NULL,
    frame_hash whattodo.sha256 NOT NULL,
    frame_bytes bytea NOT NULL CHECK(octet_length(frame_bytes)>0 AND octet_length(frame_bytes)<=1048576),
    created_at whattodo.instant NOT NULL,
    PRIMARY KEY(session_id,revision),
    UNIQUE(session_id,revision,principal_id,command_id),
    UNIQUE(session_id,revision,principal_id),
    UNIQUE(principal_id,command_id,revision),
    CHECK((revision=1 AND previous_revision IS NULL) OR (revision>1 AND previous_revision=revision-1)),
    CHECK(encode(sha256(frame_bytes),'hex')=frame_hash),
    CHECK(((convert_from(frame_bytes,'UTF8')::jsonb)->>'session_id'=session_id) IS TRUE),
    CHECK((((convert_from(frame_bytes,'UTF8')::jsonb)->>'revision')::bigint=revision) IS TRUE),
    CHECK(((convert_from(frame_bytes,'UTF8')::jsonb)->>'command_id'=command_id) IS TRUE),
    CHECK(((convert_from(frame_bytes,'UTF8')::jsonb)->>'principal_id'=principal_id) IS TRUE),
    CHECK(((convert_from(frame_bytes,'UTF8')::jsonb)->>'state'=state) IS TRUE),
    CHECK(((convert_from(frame_bytes,'UTF8')::jsonb)->>'query_source_ref'=query_source_ref) IS TRUE),
    CHECK(((convert_from(frame_bytes,'UTF8')::jsonb)->>'last_source_ref'=last_source_ref) IS TRUE),
    FOREIGN KEY(query_source_ref) REFERENCES whattodo.source_record(record_id) DEFERRABLE INITIALLY DEFERRED,
    FOREIGN KEY(last_source_ref) REFERENCES whattodo.source_record(record_id) DEFERRABLE INITIALLY DEFERRED,
    FOREIGN KEY(session_id,previous_revision) REFERENCES whattodo.command_resolution_revision(session_id,revision) DEFERRABLE INITIALLY DEFERRED
);
CREATE TABLE "whattodo"."command_resolution_head" (
    session_id whattodo.ref PRIMARY KEY,
    revision whattodo.revision NOT NULL,
    principal_id whattodo.ref NOT NULL,
    command_id whattodo.ref NOT NULL,
    UNIQUE(principal_id,command_id),
    FOREIGN KEY(session_id,revision,principal_id,command_id)
        REFERENCES whattodo.command_resolution_revision(session_id,revision,principal_id,command_id) DEFERRABLE INITIALLY DEFERRED
);
CREATE FUNCTION whattodo.guard_resolution_head() RETURNS trigger LANGUAGE plpgsql SET search_path=pg_catalog AS $guard$
BEGIN
    IF NEW.session_id IS DISTINCT FROM OLD.session_id OR NEW.principal_id IS DISTINCT FROM OLD.principal_id
        OR NEW.command_id IS DISTINCT FROM OLD.command_id OR NEW.revision IS DISTINCT FROM OLD.revision+1 THEN
        RAISE EXCEPTION 'Resolution head must advance exactly one owned version' USING ERRCODE='23514';
    END IF;
    RETURN NEW;
END;
$guard$;
REVOKE ALL ON FUNCTION whattodo.guard_resolution_head() FROM PUBLIC;
CREATE TRIGGER guard_version BEFORE UPDATE ON whattodo.command_resolution_head FOR EACH ROW EXECUTE FUNCTION whattodo.guard_resolution_head();
CREATE TRIGGER preserve_head BEFORE DELETE OR TRUNCATE ON whattodo.command_resolution_head FOR EACH STATEMENT EXECUTE FUNCTION whattodo.reject_history_mutation();
CREATE TABLE "whattodo"."command_resolution_reply" (
    reply_id whattodo.ref PRIMARY KEY,
    principal_id whattodo.ref NOT NULL,
    session_id whattodo.ref NOT NULL,
    before_revision whattodo.revision NOT NULL,
    after_revision whattodo.revision NOT NULL CHECK(after_revision=before_revision+1),
    request_hash whattodo.sha256 NOT NULL,
    source_record_ref whattodo.ref NOT NULL,
    reply_bytes bytea NOT NULL CHECK(octet_length(reply_bytes)>0 AND octet_length(reply_bytes)<=8192),
    reply_hash whattodo.sha256 NOT NULL,
    CHECK(encode(sha256(reply_bytes),'hex')=reply_hash),
    CHECK(((convert_from(reply_bytes,'UTF8')::jsonb)->>'reply_id'=reply_id) IS TRUE),
    CHECK(((convert_from(reply_bytes,'UTF8')::jsonb)->>'session_id'=session_id) IS TRUE),
    CHECK((((convert_from(reply_bytes,'UTF8')::jsonb)->>'expected_revision')::bigint=before_revision) IS TRUE),
    FOREIGN KEY(source_record_ref) REFERENCES whattodo.source_record(record_id) DEFERRABLE INITIALLY DEFERRED,
    FOREIGN KEY(session_id,before_revision,principal_id) REFERENCES whattodo.command_resolution_revision(session_id,revision,principal_id) DEFERRABLE INITIALLY DEFERRED,
    FOREIGN KEY(session_id,after_revision,principal_id) REFERENCES whattodo.command_resolution_revision(session_id,revision,principal_id) DEFERRABLE INITIALLY DEFERRED
);
CREATE TRIGGER preserve_history BEFORE UPDATE OR DELETE OR TRUNCATE ON whattodo.command_resolution_revision FOR EACH STATEMENT EXECUTE FUNCTION whattodo.reject_history_mutation();
CREATE TRIGGER preserve_history BEFORE UPDATE OR DELETE OR TRUNCATE ON whattodo.command_resolution_reply FOR EACH STATEMENT EXECUTE FUNCTION whattodo.reject_history_mutation();
REVOKE ALL ON whattodo.command_resolution_revision,whattodo.command_resolution_head,whattodo.command_resolution_reply FROM PUBLIC;
COMMIT;
