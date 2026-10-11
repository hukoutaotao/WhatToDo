-- Immutable source reports and settled increments; unknown session times stay NULL.
BEGIN;
SET LOCAL search_path=pg_catalog;
CREATE TABLE "whattodo"."actual_work_report" (
    observation_id whattodo.ref PRIMARY KEY,
    task_id whattodo.ref NOT NULL,
    kind whattodo.ref NOT NULL CHECK(kind='ACTUAL_WORK'),
    mode whattodo.ref NOT NULL CHECK(mode IN ('INCREMENT','CUMULATIVE')),
    reported_seconds whattodo.seconds NOT NULL,
    previous_total_seconds whattodo.seconds NOT NULL,
    increment_seconds whattodo.seconds NOT NULL,
    resulting_total_seconds whattodo.seconds NOT NULL,
    stage_id whattodo.ref,
    session_started_at whattodo.instant,
    session_ended_at whattodo.instant,
    source_record_ref whattodo.ref NOT NULL,
    authority_ref whattodo.ref NOT NULL,
    principal_id whattodo.ref NOT NULL,
    task_revision whattodo.revision NOT NULL,
    transaction_ref whattodo.ref NOT NULL,
    report_fingerprint whattodo.sha256 NOT NULL,
    fact_fingerprint whattodo.sha256 NOT NULL,
    content_hash whattodo.sha256 NOT NULL,
    raw_bytes bytea NOT NULL CHECK(octet_length(raw_bytes)>0 AND octet_length(raw_bytes)<=262144),
    CHECK(resulting_total_seconds=previous_total_seconds+increment_seconds),
    CHECK((mode='INCREMENT' AND increment_seconds=reported_seconds) OR
        (mode='CUMULATIVE' AND resulting_total_seconds=reported_seconds)),
    CHECK(session_started_at IS NULL OR session_ended_at IS NULL OR session_started_at<=session_ended_at),
    CHECK(encode(sha256(raw_bytes),'hex')=content_hash),
    CHECK(((convert_from(raw_bytes,'UTF8')::jsonb)->>'observation_id'=observation_id) IS TRUE),
    CHECK(((convert_from(raw_bytes,'UTF8')::jsonb)->>'task_id'=task_id) IS TRUE),
    CHECK((((convert_from(raw_bytes,'UTF8')::jsonb)->>'recorded_task_revision')::bigint=task_revision) IS TRUE),
    CHECK(((convert_from(raw_bytes,'UTF8')::jsonb)#>>'{report,command_id}'=transaction_ref) IS TRUE),
    CHECK(((convert_from(raw_bytes,'UTF8')::jsonb)#>>'{report,principal_id}'=principal_id) IS TRUE),
    CHECK(((convert_from(raw_bytes,'UTF8')::jsonb)#>>'{report,authority_ref}'=authority_ref) IS TRUE),
    CHECK(((convert_from(raw_bytes,'UTF8')::jsonb)#>>'{report,mode}'=mode) IS TRUE),
    CHECK((((convert_from(raw_bytes,'UTF8')::jsonb)#>>'{report,seconds}')::numeric=reported_seconds) IS TRUE),
    CHECK((((convert_from(raw_bytes,'UTF8')::jsonb)->>'previous_total_seconds')::numeric=previous_total_seconds) IS TRUE),
    CHECK((((convert_from(raw_bytes,'UTF8')::jsonb)->>'increment_seconds')::numeric=increment_seconds) IS TRUE),
    CHECK((((convert_from(raw_bytes,'UTF8')::jsonb)->>'resulting_total_seconds')::numeric=resulting_total_seconds) IS TRUE),
    CHECK(((convert_from(raw_bytes,'UTF8')::jsonb)->>'source_ref'=source_record_ref) IS TRUE),
    FOREIGN KEY(task_id,observation_id,kind,increment_seconds)
        REFERENCES whattodo.effort_observation(task_id,observation_id,kind,seconds) DEFERRABLE INITIALLY DEFERRED,
    FOREIGN KEY(task_id,task_revision) REFERENCES whattodo.task_revision(task_id,revision) DEFERRABLE INITIALLY DEFERRED,
    FOREIGN KEY(source_record_ref) REFERENCES whattodo.source_record(record_id) DEFERRABLE INITIALLY DEFERRED,
    FOREIGN KEY(authority_ref) REFERENCES whattodo.authority_record(authority_ref) DEFERRABLE INITIALLY DEFERRED,
    FOREIGN KEY(transaction_ref) REFERENCES whattodo.command_transaction(request_id) DEFERRABLE INITIALLY DEFERRED,
    FOREIGN KEY(stage_id,task_id) REFERENCES whattodo.stage_identity(stage_id,task_id) DEFERRABLE INITIALLY DEFERRED
);
CREATE TRIGGER preserve_history BEFORE UPDATE OR DELETE OR TRUNCATE ON whattodo.actual_work_report
FOR EACH STATEMENT EXECUTE FUNCTION whattodo.reject_history_mutation();
REVOKE ALL ON whattodo.actual_work_report FROM PUBLIC;
COMMIT;
