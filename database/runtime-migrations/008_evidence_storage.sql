-- Evidence ingestion is separate from canonical Task authority and transactions.
BEGIN;
SET LOCAL search_path=pg_catalog;
ALTER TABLE whattodo.source_record DROP CONSTRAINT source_record_uq_1;
ALTER TABLE whattodo.source_record ADD CONSTRAINT source_record_version_state
UNIQUE NULLS NOT DISTINCT(source_id,content_hash,external_revision,state,deleted_at);
ALTER TABLE whattodo.source_record ADD CONSTRAINT source_record_exact_identity
UNIQUE(record_id,source_id,content_hash);

CREATE TABLE whattodo.source_payload (
    record_id whattodo.ref PRIMARY KEY,
    source_id whattodo.ref NOT NULL,
    content_hash whattodo.sha256 NOT NULL,
    wire_hash whattodo.sha256 NOT NULL,
    raw_wire bytea NOT NULL CHECK(octet_length(raw_wire)>0 AND octet_length(raw_wire)<=1048576),
    UNIQUE(record_id,content_hash),
    CHECK(encode(sha256(raw_wire),'hex')=wire_hash),
    CHECK(((convert_from(raw_wire,'UTF8')::jsonb)->>'record_id'=record_id) IS TRUE),
    CHECK(((convert_from(raw_wire,'UTF8')::jsonb)->>'source_id'=source_id) IS TRUE),
    CHECK(((convert_from(raw_wire,'UTF8')::jsonb)->>'content_hash'=content_hash) IS TRUE),
    FOREIGN KEY(record_id,source_id,content_hash) REFERENCES whattodo.source_record(record_id,source_id,content_hash) DEFERRABLE INITIALLY DEFERRED
);
CREATE TABLE whattodo.source_raw_content (
    record_id whattodo.ref PRIMARY KEY,
    content_hash whattodo.sha256 NOT NULL,
    raw_content bytea,
    storage_state whattodo.ref NOT NULL CHECK(storage_state IN ('RETAINED','EXTERNAL_REFERENCE','MINIMIZED')),
    minimized_at whattodo.instant,
    reason_ref whattodo.ref,
    CHECK((storage_state='RETAINED' AND raw_content IS NOT NULL AND minimized_at IS NULL AND reason_ref IS NULL)
        OR (storage_state='EXTERNAL_REFERENCE' AND raw_content IS NULL AND minimized_at IS NULL AND reason_ref IS NULL)
        OR (storage_state='MINIMIZED' AND raw_content IS NULL AND minimized_at IS NOT NULL AND reason_ref IS NOT NULL)),
    CHECK(raw_content IS NULL OR (octet_length(raw_content)<=8388608 AND encode(sha256(raw_content),'hex')=content_hash)),
    FOREIGN KEY(record_id,content_hash) REFERENCES whattodo.source_payload(record_id,content_hash) DEFERRABLE INITIALLY DEFERRED
);
CREATE FUNCTION whattodo.guard_raw_minimization() RETURNS trigger
LANGUAGE plpgsql SET search_path=pg_catalog AS $guard$
BEGIN
    IF NEW.record_id IS DISTINCT FROM OLD.record_id OR NEW.content_hash IS DISTINCT FROM OLD.content_hash
        OR OLD.storage_state<>'RETAINED' OR NEW.storage_state<>'MINIMIZED'
        OR NEW.raw_content IS NOT NULL OR NEW.minimized_at IS NULL OR NEW.reason_ref IS NULL THEN
        RAISE EXCEPTION 'Only one-way raw minimization is permitted' USING ERRCODE='23514';
    END IF;
    RETURN NEW;
END;
$guard$;
REVOKE ALL ON FUNCTION whattodo.guard_raw_minimization() FROM PUBLIC;
CREATE TRIGGER raw_minimization BEFORE UPDATE ON whattodo.source_raw_content
FOR EACH ROW EXECUTE FUNCTION whattodo.guard_raw_minimization();
CREATE TRIGGER preserve_row BEFORE DELETE OR TRUNCATE ON whattodo.source_raw_content
FOR EACH STATEMENT EXECUTE FUNCTION whattodo.reject_history_mutation();
CREATE TABLE whattodo.source_tombstone (
    record_id whattodo.ref PRIMARY KEY,
    prior_record_id whattodo.ref NOT NULL UNIQUE,
    FOREIGN KEY(record_id) REFERENCES whattodo.source_record(record_id) DEFERRABLE INITIALLY DEFERRED,
    FOREIGN KEY(prior_record_id) REFERENCES whattodo.source_record(record_id) DEFERRABLE INITIALLY DEFERRED
);
CREATE TABLE whattodo.candidate_identity (
    candidate_id whattodo.ref PRIMARY KEY,
    source_record_ref whattodo.ref NOT NULL,
    parser_version whattodo.ref NOT NULL,
    action whattodo.ref NOT NULL CHECK(action IN ('CREATE_TASK','UPDATE_TASK','COMPLETE_TASK','CANCEL_TASK')),
    task_id whattodo.ref,
    task_revision whattodo.revision,
    CHECK((task_id IS NULL AND task_revision IS NULL) OR (task_id IS NOT NULL AND task_revision IS NOT NULL AND action<>'CREATE_TASK')),
    UNIQUE NULLS NOT DISTINCT(source_record_ref,parser_version,action,task_id,task_revision),
    UNIQUE(candidate_id,source_record_ref,parser_version,action),
    FOREIGN KEY(source_record_ref) REFERENCES whattodo.source_record(record_id) DEFERRABLE INITIALLY DEFERRED,
    FOREIGN KEY(task_id,task_revision) REFERENCES whattodo.task_revision(task_id,revision) DEFERRABLE INITIALLY DEFERRED
);
INSERT INTO whattodo.candidate_identity
SELECT DISTINCT ON(candidate_id) candidate_id,source_record_ref,parser_version,action,task_id,task_revision
FROM whattodo.candidate_revision ORDER BY candidate_id,revision;
ALTER TABLE whattodo.candidate_revision ADD CONSTRAINT candidate_permanent_origin
FOREIGN KEY(candidate_id,source_record_ref,parser_version,action)
REFERENCES whattodo.candidate_identity(candidate_id,source_record_ref,parser_version,action)
DEFERRABLE INITIALLY DEFERRED;
CREATE TABLE whattodo.candidate_payload (
    candidate_id whattodo.ref NOT NULL,
    revision whattodo.revision NOT NULL,
    source_record_ref whattodo.ref NOT NULL,
    source_id whattodo.ref NOT NULL,
    source_hash whattodo.sha256 NOT NULL,
    proposal_hash whattodo.sha256 NOT NULL,
    wire_hash whattodo.sha256 NOT NULL,
    raw_wire bytea NOT NULL CHECK(octet_length(raw_wire)>0 AND octet_length(raw_wire)<=1048576),
    PRIMARY KEY(candidate_id,revision),
    UNIQUE(candidate_id,revision,source_record_ref,source_id,source_hash),
    CHECK(encode(sha256(raw_wire),'hex')=wire_hash),
    CHECK(((convert_from(raw_wire,'UTF8')::jsonb)->>'candidate_id'=candidate_id) IS TRUE),
    FOREIGN KEY(candidate_id,revision) REFERENCES whattodo.candidate_revision(candidate_id,revision) DEFERRABLE INITIALLY DEFERRED,
    FOREIGN KEY(source_record_ref,source_id,source_hash) REFERENCES whattodo.source_record(record_id,source_id,content_hash) DEFERRABLE INITIALLY DEFERRED
);
CREATE TABLE whattodo.candidate_field_provenance (
    candidate_id whattodo.ref NOT NULL,
    revision whattodo.revision NOT NULL,
    field_pointer text NOT NULL CHECK(field_pointer LIKE '/proposed_fields/%'),
    source_record_ref whattodo.ref NOT NULL,
    source_id whattodo.ref NOT NULL,
    source_hash whattodo.sha256 NOT NULL,
    PRIMARY KEY(candidate_id,revision,field_pointer),
    FOREIGN KEY(candidate_id,revision,source_record_ref,source_id,source_hash)
        REFERENCES whattodo.candidate_payload(candidate_id,revision,source_record_ref,source_id,source_hash) DEFERRABLE INITIALLY DEFERRED
);
CREATE TABLE whattodo.evidence_conflict (
    conflict_id whattodo.ref PRIMARY KEY,
    kind whattodo.ref NOT NULL CHECK(kind IN ('SOURCE','CANDIDATE')),
    source_record_ref whattodo.ref,
    candidate_id whattodo.ref,
    expected_hash whattodo.sha256 NOT NULL,
    observed_hash whattodo.sha256 NOT NULL,
    wire_hash whattodo.sha256 NOT NULL,
    observed_wire bytea NOT NULL CHECK(octet_length(observed_wire)>0 AND octet_length(observed_wire)<=1048576),
    detected_at whattodo.instant NOT NULL,
    CHECK((kind='SOURCE' AND source_record_ref IS NOT NULL AND candidate_id IS NULL)
        OR (kind='CANDIDATE' AND source_record_ref IS NULL AND candidate_id IS NOT NULL)),
    CHECK(expected_hash<>observed_hash),
    CHECK(encode(sha256(observed_wire),'hex')=wire_hash),
    FOREIGN KEY(source_record_ref) REFERENCES whattodo.source_record(record_id) DEFERRABLE INITIALLY DEFERRED,
    FOREIGN KEY(candidate_id) REFERENCES whattodo.candidate_identity(candidate_id) DEFERRABLE INITIALLY DEFERRED
);
CREATE TABLE whattodo.pending_evidence_identity (
    pending_id whattodo.ref PRIMARY KEY,
    kind whattodo.ref NOT NULL CHECK(kind IN ('CANDIDATE','CONFLICT')),
    candidate_id whattodo.ref UNIQUE,
    conflict_id whattodo.ref UNIQUE,
    created_at whattodo.instant NOT NULL,
    CHECK((kind='CANDIDATE' AND candidate_id IS NOT NULL AND conflict_id IS NULL)
        OR (kind='CONFLICT' AND candidate_id IS NULL AND conflict_id IS NOT NULL)),
    FOREIGN KEY(candidate_id) REFERENCES whattodo.candidate_identity(candidate_id) DEFERRABLE INITIALLY DEFERRED,
    FOREIGN KEY(conflict_id) REFERENCES whattodo.evidence_conflict(conflict_id) DEFERRABLE INITIALLY DEFERRED
);
CREATE TABLE whattodo.pending_evidence_revision (
    pending_id whattodo.ref NOT NULL,
    revision whattodo.revision NOT NULL,
    state whattodo.ref NOT NULL CHECK(state IN ('OPEN','RESOLVED','REJECTED','SUPERSEDED')),
    authority_ref whattodo.ref,
    resolved_at whattodo.instant,
    transaction_ref whattodo.ref,
    PRIMARY KEY(pending_id,revision),
    CHECK((state='OPEN' AND authority_ref IS NULL AND resolved_at IS NULL AND transaction_ref IS NULL)
        OR (state<>'OPEN' AND authority_ref IS NOT NULL AND resolved_at IS NOT NULL AND transaction_ref IS NOT NULL)),
    FOREIGN KEY(pending_id) REFERENCES whattodo.pending_evidence_identity(pending_id) DEFERRABLE INITIALLY DEFERRED,
    FOREIGN KEY(authority_ref) REFERENCES whattodo.authority_record(authority_ref) DEFERRABLE INITIALLY DEFERRED,
    FOREIGN KEY(transaction_ref) REFERENCES whattodo.command_transaction(request_id) DEFERRABLE INITIALLY DEFERRED
);
CREATE TABLE whattodo.pending_evidence_head (
    pending_id whattodo.ref PRIMARY KEY,
    revision whattodo.revision NOT NULL,
    FOREIGN KEY(pending_id,revision) REFERENCES whattodo.pending_evidence_revision(pending_id,revision) DEFERRABLE INITIALLY DEFERRED
);
CREATE FUNCTION whattodo.guard_pending_head() RETURNS trigger
LANGUAGE plpgsql SET search_path=pg_catalog AS $guard$
BEGIN
    IF NEW.pending_id IS DISTINCT FROM OLD.pending_id OR NEW.revision IS DISTINCT FROM OLD.revision+1 THEN
        RAISE EXCEPTION 'Pending head must advance exactly one revision' USING ERRCODE='23514';
    END IF;
    RETURN NEW;
END;
$guard$;
REVOKE ALL ON FUNCTION whattodo.guard_pending_head() FROM PUBLIC;
CREATE TRIGGER guard_version BEFORE UPDATE ON whattodo.pending_evidence_head
FOR EACH ROW EXECUTE FUNCTION whattodo.guard_pending_head();
CREATE TRIGGER preserve_row BEFORE DELETE OR TRUNCATE ON whattodo.pending_evidence_head
FOR EACH STATEMENT EXECUTE FUNCTION whattodo.reject_history_mutation();
CREATE TRIGGER preserve_history BEFORE UPDATE OR DELETE OR TRUNCATE ON whattodo.source_payload
FOR EACH STATEMENT EXECUTE FUNCTION whattodo.reject_history_mutation();
CREATE TRIGGER preserve_history BEFORE UPDATE OR DELETE OR TRUNCATE ON whattodo.source_tombstone
FOR EACH STATEMENT EXECUTE FUNCTION whattodo.reject_history_mutation();
CREATE TRIGGER preserve_history BEFORE UPDATE OR DELETE OR TRUNCATE ON whattodo.candidate_identity
FOR EACH STATEMENT EXECUTE FUNCTION whattodo.reject_history_mutation();
CREATE TRIGGER preserve_history BEFORE UPDATE OR DELETE OR TRUNCATE ON whattodo.candidate_payload
FOR EACH STATEMENT EXECUTE FUNCTION whattodo.reject_history_mutation();
CREATE TRIGGER preserve_history BEFORE UPDATE OR DELETE OR TRUNCATE ON whattodo.candidate_field_provenance
FOR EACH STATEMENT EXECUTE FUNCTION whattodo.reject_history_mutation();
CREATE TRIGGER preserve_history BEFORE UPDATE OR DELETE OR TRUNCATE ON whattodo.evidence_conflict
FOR EACH STATEMENT EXECUTE FUNCTION whattodo.reject_history_mutation();
CREATE TRIGGER preserve_history BEFORE UPDATE OR DELETE OR TRUNCATE ON whattodo.pending_evidence_identity
FOR EACH STATEMENT EXECUTE FUNCTION whattodo.reject_history_mutation();
CREATE TRIGGER preserve_history BEFORE UPDATE OR DELETE OR TRUNCATE ON whattodo.pending_evidence_revision
FOR EACH STATEMENT EXECUTE FUNCTION whattodo.reject_history_mutation();
REVOKE ALL ON whattodo.source_payload,whattodo.source_raw_content,whattodo.source_tombstone,
    whattodo.candidate_identity,whattodo.candidate_payload,whattodo.candidate_field_provenance,
    whattodo.evidence_conflict,whattodo.pending_evidence_identity,whattodo.pending_evidence_revision,
    whattodo.pending_evidence_head FROM PUBLIC;
COMMIT;
