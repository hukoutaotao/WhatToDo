-- Scoped unchanged-estimate batch confirmations and per-member verification history.
BEGIN;
SET LOCAL search_path=pg_catalog;

CREATE TABLE whattodo.review_batch_confirmation (
 record_id whattodo.ref PRIMARY KEY,
 command_id whattodo.ref NOT NULL UNIQUE,
 aggregate_kind whattodo.ref NOT NULL CHECK(aggregate_kind IN ('REVIEW_BATCH_CONFIRMED','REVIEW_BATCH_NOT_CONFIRMED')),
 revision whattodo.revision NOT NULL DEFAULT 1 CHECK(revision=1),
 review_id whattodo.ref NOT NULL,
 frame_revision whattodo.revision NOT NULL,
 user_statement_ref whattodo.ref NOT NULL,
 batch_id whattodo.ref NOT NULL,
 confirmed boolean NOT NULL,
 no_work_statement boolean,
 member_count integer NOT NULL CHECK(member_count>=0 AND member_count<=100),
 authority_ref whattodo.ref NOT NULL,
 source_ref whattodo.ref NOT NULL,
 source_observed_at whattodo.instant NOT NULL,
 raw_command bytea NOT NULL CHECK(octet_length(raw_command)>0 AND octet_length(raw_command)<=262144),
 raw_command_hash whattodo.sha256 NOT NULL,
 state whattodo.ref NOT NULL CHECK(state IN ('CONFIRMED','NOT_CONFIRMED')),
 code whattodo.ref NOT NULL CHECK(code ~ '^[A-Z][A-Z0-9_]{0,63}$'),
 transaction_ref whattodo.ref NOT NULL,
 audit_change_ref whattodo.ref NOT NULL,
 runtime_payload whattodo.json_object NOT NULL CHECK(octet_length(runtime_payload::text)<=16777216),
 UNIQUE(record_id,aggregate_kind),
 CHECK(encode(sha256(raw_command),'hex')=raw_command_hash),
 CHECK((convert_from(raw_command,'UTF8')::jsonb=runtime_payload->'command') IS TRUE),
 CHECK((decode(runtime_payload->>'raw_command_base64','base64')=raw_command) IS TRUE),
 CHECK(((runtime_payload->>'source_observed_at')::timestamptz=source_observed_at) IS TRUE),
 CHECK((record_id='review-batch-'||(runtime_payload->>'command_fingerprint')
   AND runtime_payload->'command'->>'schema_version'='0.1.0-review-batch'
   AND runtime_payload->'command'->>'command_id'=command_id
   AND runtime_payload->'command'->>'origin'='USER_COMMAND'
   AND runtime_payload->'command'->>'authority_ref'=authority_ref
   AND runtime_payload->'command'->>'batch_id'=batch_id
   AND runtime_payload->'command'#>'{review_ref}'=jsonb_build_object('review_id',review_id,
    'frame_revision',frame_revision,'user_statement_ref',user_statement_ref)
   AND runtime_payload->>'schema_version'='0.1.0-review-batch-journal'
   AND runtime_payload->>'kind'=aggregate_kind
   AND runtime_payload->>'state'=state
   AND runtime_payload->>'code'=code
   AND runtime_payload->>'source_ref'=source_ref) IS TRUE),
 CHECK((confirmed=(state='CONFIRMED')
   AND member_count=jsonb_array_length(runtime_payload->'command'->'members')
   AND (CASE WHEN runtime_payload->'command'->>'confirmed'='true' THEN true ELSE false END)=confirmed) IS TRUE),
 CHECK(((state='CONFIRMED' AND aggregate_kind='REVIEW_BATCH_CONFIRMED'
    AND jsonb_array_length(runtime_payload->'verifications')=member_count)
   OR (state='NOT_CONFIRMED' AND aggregate_kind='REVIEW_BATCH_NOT_CONFIRMED'
    AND runtime_payload->'verifications'='[]'::jsonb AND confirmed=false)) IS TRUE),
 CHECK((no_work_statement IS NULL AND runtime_payload->'command'->'no_work_statement'='null'::jsonb)
   OR (no_work_statement IS NOT NULL AND (runtime_payload->'command'->>'no_work_statement')::boolean=no_work_statement)),
 FOREIGN KEY(source_ref) REFERENCES whattodo.source_record(record_id) DEFERRABLE INITIALLY DEFERRED,
 FOREIGN KEY(authority_ref) REFERENCES whattodo.authority_record(authority_ref) DEFERRABLE INITIALLY DEFERRED,
 FOREIGN KEY(transaction_ref) REFERENCES whattodo.command_transaction(request_id) DEFERRABLE INITIALLY DEFERRED,
 FOREIGN KEY(audit_change_ref,aggregate_kind,record_id,revision,transaction_ref)
  REFERENCES whattodo.audit_change(change_id,aggregate_kind,aggregate_id,after_revision,request_id) DEFERRABLE INITIALLY DEFERRED
);

CREATE TABLE whattodo.review_batch_verification (
 verification_id whattodo.ref PRIMARY KEY CHECK(verification_id ~ '^verification-[a-f0-9]{64}$'),
 batch_record_id whattodo.ref NOT NULL CHECK(batch_record_id ~ '^review-batch-[a-f0-9]{64}$'),
 aggregate_kind whattodo.ref NOT NULL DEFAULT 'REVIEW_VERIFICATION' CHECK(aggregate_kind='REVIEW_VERIFICATION'),
 revision whattodo.revision NOT NULL DEFAULT 1 CHECK(revision=1),
 task_id whattodo.ref NOT NULL,
 task_revision whattodo.revision NOT NULL,
 estimate_kind whattodo.ref NOT NULL DEFAULT 'USER_REMAINING' CHECK(estimate_kind='USER_REMAINING'),
 observation_id whattodo.ref NOT NULL,
 seconds whattodo.seconds NOT NULL,
 observed_at whattodo.instant NOT NULL,
 verified_at whattodo.instant NOT NULL,
 CHECK(verified_at>=observed_at),
 no_work_statement boolean,
 transaction_ref whattodo.ref NOT NULL,
 audit_change_ref whattodo.ref NOT NULL,
 runtime_payload whattodo.json_object NOT NULL CHECK(octet_length(runtime_payload::text)<=2097152),
 -- One confirmed estimate accepts exactly one verification; overlapping
 -- confirmed batches fail here instead of silently approving again.
 UNIQUE(task_id,observation_id),
 UNIQUE(batch_record_id,task_id),
 CHECK((runtime_payload->>'verification_id'=verification_id
   AND runtime_payload->>'batch_record_id'=batch_record_id
   AND runtime_payload->>'task_id'=task_id
   AND (runtime_payload->>'task_revision')::bigint=task_revision
   AND runtime_payload#>>'{estimate,observation_id}'=observation_id
   AND (runtime_payload#>>'{estimate,seconds}')::numeric=seconds
   AND (runtime_payload#>>'{estimate,observed_at}')::timestamptz=observed_at
   AND (runtime_payload#>>'{estimate,verified_at}')::timestamptz=verified_at
   AND (no_work_statement IS NULL AND runtime_payload->'no_work_statement'='null'::jsonb)
   OR (no_work_statement IS NOT NULL
    AND (runtime_payload->>'no_work_statement')::boolean=no_work_statement)) IS TRUE),
 FOREIGN KEY(batch_record_id) REFERENCES whattodo.review_batch_confirmation(record_id) DEFERRABLE INITIALLY DEFERRED,
 FOREIGN KEY(task_id,task_revision) REFERENCES whattodo.task_revision(task_id,revision) DEFERRABLE INITIALLY DEFERRED,
 FOREIGN KEY(task_id,observation_id,estimate_kind,seconds)
  REFERENCES whattodo.effort_observation(task_id,observation_id,kind,seconds) DEFERRABLE INITIALLY DEFERRED,
 FOREIGN KEY(transaction_ref) REFERENCES whattodo.command_transaction(request_id) DEFERRABLE INITIALLY DEFERRED,
 FOREIGN KEY(audit_change_ref,aggregate_kind,verification_id,revision,transaction_ref)
  REFERENCES whattodo.audit_change(change_id,aggregate_kind,aggregate_id,after_revision,request_id) DEFERRABLE INITIALLY DEFERRED
);
CREATE INDEX review_batch_verification_batch ON whattodo.review_batch_verification(batch_record_id);

CREATE TRIGGER preserve_history BEFORE UPDATE OR DELETE OR TRUNCATE ON whattodo.review_batch_confirmation
FOR EACH STATEMENT EXECUTE FUNCTION whattodo.reject_history_mutation();
CREATE TRIGGER preserve_history BEFORE UPDATE OR DELETE OR TRUNCATE ON whattodo.review_batch_verification
FOR EACH STATEMENT EXECUTE FUNCTION whattodo.reject_history_mutation();
REVOKE ALL ON whattodo.review_batch_confirmation,whattodo.review_batch_verification FROM PUBLIC;
COMMIT;
