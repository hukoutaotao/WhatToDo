-- Additive lossless Task snapshots and permanent stage ownership.
BEGIN;
SET LOCAL search_path=pg_catalog;
CREATE TABLE whattodo.stage_identity (
    stage_id whattodo.ref PRIMARY KEY,
    task_id whattodo.ref NOT NULL,
    transaction_ref whattodo.ref NOT NULL,
    UNIQUE(stage_id,task_id),
    FOREIGN KEY(task_id) REFERENCES whattodo.task_identity(task_id) DEFERRABLE INITIALLY DEFERRED,
    FOREIGN KEY(transaction_ref) REFERENCES whattodo.command_transaction(request_id) DEFERRABLE INITIALLY DEFERRED
);
-- Existing valid stages keep their original owner and first creation transaction.
-- If old history reused an ID across unrelated tasks, validation fails explicitly.
INSERT INTO whattodo.stage_identity(stage_id,task_id,transaction_ref)
SELECT DISTINCT ON(stage_id) stage_id,task_id,transaction_ref
FROM whattodo.stage_revision ORDER BY stage_id,revision;
ALTER TABLE whattodo.stage_revision ADD CONSTRAINT stage_permanent_owner
FOREIGN KEY(stage_id,task_id) REFERENCES whattodo.stage_identity(stage_id,task_id)
DEFERRABLE INITIALLY DEFERRED;

CREATE TABLE whattodo.task_payload_revision (
    task_id whattodo.ref NOT NULL,
    task_revision whattodo.revision NOT NULL,
    transaction_ref whattodo.ref NOT NULL,
    content_hash whattodo.sha256 NOT NULL,
    raw_bytes bytea NOT NULL CHECK(octet_length(raw_bytes)>0 AND octet_length(raw_bytes)<=1048576),
    profile_ref whattodo.ref,
    prediction_ref whattodo.ref,
    PRIMARY KEY(task_id,task_revision),
    CHECK(encode(sha256(raw_bytes),'hex')=content_hash),
    CHECK(((convert_from(raw_bytes,'UTF8')::jsonb)#>>'{core,task_id}'=task_id) IS TRUE),
    CHECK((((convert_from(raw_bytes,'UTF8')::jsonb)#>>'{core,revision}')::bigint=task_revision) IS TRUE),
    CHECK(((convert_from(raw_bytes,'UTF8')::jsonb)#>>'{effort,task_id}'=task_id) IS TRUE),
    CHECK((((convert_from(raw_bytes,'UTF8')::jsonb)#>>'{effort,task_revision}')::bigint=task_revision) IS TRUE),
    FOREIGN KEY(task_id,task_revision,transaction_ref)
        REFERENCES whattodo.task_revision(task_id,revision,transaction_ref) DEFERRABLE INITIALLY DEFERRED,
    FOREIGN KEY(profile_ref) REFERENCES whattodo.definition_cache(configuration_ref) DEFERRABLE INITIALLY DEFERRED,
    FOREIGN KEY(prediction_ref) REFERENCES whattodo.remaining_prediction(prediction_id) DEFERRABLE INITIALLY DEFERRED
);

CREATE TABLE whattodo.task_stage_revision (
    task_id whattodo.ref NOT NULL,
    task_revision whattodo.revision NOT NULL,
    stage_id whattodo.ref NOT NULL,
    stage_revision whattodo.revision NOT NULL,
    ordinal integer NOT NULL CHECK(ordinal>=0),
    PRIMARY KEY(task_id,task_revision,stage_id),
    UNIQUE(task_id,task_revision,ordinal),
    FOREIGN KEY(task_id,task_revision) REFERENCES whattodo.task_revision(task_id,revision) DEFERRABLE INITIALLY DEFERRED,
    FOREIGN KEY(stage_id,task_id) REFERENCES whattodo.stage_identity(stage_id,task_id) DEFERRABLE INITIALLY DEFERRED,
    FOREIGN KEY(stage_id,stage_revision,task_id) REFERENCES whattodo.stage_revision(stage_id,revision,task_id) DEFERRABLE INITIALLY DEFERRED
);

CREATE TABLE whattodo.stage_effort_revision (
    stage_id whattodo.ref NOT NULL,
    stage_revision whattodo.revision NOT NULL,
    task_id whattodo.ref NOT NULL,
    user_remaining_seconds whattodo.seconds,
    observation_id whattodo.ref,
    estimate_kind whattodo.ref,
    observed_at whattodo.instant,
    verified_at whattodo.instant,
    PRIMARY KEY(stage_id,stage_revision),
    CHECK((user_remaining_seconds IS NULL AND observation_id IS NULL AND estimate_kind IS NULL AND observed_at IS NULL AND verified_at IS NULL)
        OR (user_remaining_seconds IS NOT NULL AND observation_id IS NOT NULL AND estimate_kind IS NOT NULL AND estimate_kind='USER_REMAINING' AND observed_at IS NOT NULL AND verified_at IS NOT NULL AND verified_at>=observed_at)),
    FOREIGN KEY(stage_id,stage_revision,task_id) REFERENCES whattodo.stage_revision(stage_id,revision,task_id) DEFERRABLE INITIALLY DEFERRED,
    FOREIGN KEY(task_id,observation_id,estimate_kind,user_remaining_seconds)
        REFERENCES whattodo.effort_observation(task_id,observation_id,kind,seconds) DEFERRABLE INITIALLY DEFERRED
);

CREATE TRIGGER preserve_history BEFORE UPDATE OR DELETE OR TRUNCATE ON whattodo.stage_identity
FOR EACH STATEMENT EXECUTE FUNCTION whattodo.reject_history_mutation();
CREATE TRIGGER preserve_history BEFORE UPDATE OR DELETE OR TRUNCATE ON whattodo.task_payload_revision
FOR EACH STATEMENT EXECUTE FUNCTION whattodo.reject_history_mutation();
CREATE TRIGGER preserve_history BEFORE UPDATE OR DELETE OR TRUNCATE ON whattodo.task_stage_revision
FOR EACH STATEMENT EXECUTE FUNCTION whattodo.reject_history_mutation();
CREATE TRIGGER preserve_history BEFORE UPDATE OR DELETE OR TRUNCATE ON whattodo.stage_effort_revision
FOR EACH STATEMENT EXECUTE FUNCTION whattodo.reject_history_mutation();
REVOKE ALL ON whattodo.stage_identity,whattodo.task_payload_revision,whattodo.task_stage_revision,whattodo.stage_effort_revision FROM PUBLIC;
COMMIT;
