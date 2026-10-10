-- Generated draft 0.1.0: NOT release-frozen or application-migrated.
-- Review/freeze and run in an isolated database before activation.
BEGIN;
SET LOCAL search_path = pg_catalog;

CREATE TABLE "whattodo"."task_identity" (
  "task_id" "whattodo"."ref" NOT NULL,
  "transaction_ref" "whattodo"."ref" NOT NULL,
  "created_at" "whattodo"."instant" NOT NULL,
  CONSTRAINT "task_identity_pk_identity" PRIMARY KEY ("task_id")
);

CREATE TRIGGER "preserve_history" BEFORE UPDATE OR DELETE OR TRUNCATE ON "whattodo"."task_identity"
  FOR EACH STATEMENT EXECUTE FUNCTION "whattodo"."reject_history_mutation"();

CREATE TABLE "whattodo"."effort_observation" (
  "observation_id" "whattodo"."ref" NOT NULL,
  "task_id" "whattodo"."ref" NOT NULL,
  "kind" "whattodo"."ref" NOT NULL,
  "seconds" "whattodo"."seconds",
  "observed_at" "whattodo"."instant" NOT NULL,
  "recorded_at" "whattodo"."instant" NOT NULL,
  "source_record_ref" "whattodo"."ref" NOT NULL,
  "authority_ref" "whattodo"."ref" NOT NULL,
  "batch_ref" "whattodo"."ref",
  "transaction_ref" "whattodo"."ref" NOT NULL,
  CONSTRAINT "effort_observation_pk_identity" PRIMARY KEY ("observation_id"),
  CONSTRAINT "effort_observation_uq_1" UNIQUE ("task_id", "observation_id", "kind", "seconds"),
  CONSTRAINT "effort_observation_uq_2" UNIQUE ("task_id", "observation_id", "kind"),
  CONSTRAINT "effort_observation_uq_3" UNIQUE ("task_id", "observation_id"),
  CONSTRAINT "effort_observation_ck_kind" CHECK (kind IN ('ACTUAL_WORK','USER_REMAINING','UNCHANGED_VERIFICATION')),
  CONSTRAINT "effort_observation_ck_meaning" CHECK ((kind = 'UNCHANGED_VERIFICATION' AND seconds IS NULL AND batch_ref IS NOT NULL) OR (kind IN ('ACTUAL_WORK','USER_REMAINING') AND seconds IS NOT NULL AND batch_ref IS NULL)),
  CONSTRAINT "effort_observation_ck_chronology" CHECK (recorded_at >= observed_at)
);

CREATE TRIGGER "preserve_history" BEFORE UPDATE OR DELETE OR TRUNCATE ON "whattodo"."effort_observation"
  FOR EACH STATEMENT EXECUTE FUNCTION "whattodo"."reject_history_mutation"();

CREATE TABLE "whattodo"."task_revision" (
  "task_id" "whattodo"."ref" NOT NULL,
  "revision" "whattodo"."revision" NOT NULL,
  "title" text NOT NULL,
  "domain" "whattodo"."ref" NOT NULL,
  "context_kind" "whattodo"."ref",
  "context_id" "whattodo"."ref",
  "task_type_ref" "whattodo"."ref",
  "acceptance_ref" "whattodo"."ref" NOT NULL,
  "completion" "whattodo"."ref" NOT NULL,
  "disposition" "whattodo"."ref" NOT NULL,
  "requiredness" "whattodo"."ref" NOT NULL,
  "importance" smallint NOT NULL,
  "thinking_depth" smallint NOT NULL,
  "repetitive_volume" smallint NOT NULL,
  "new_learning_load" smallint NOT NULL,
  "user_remaining_seconds" "whattodo"."seconds",
  "estimate_observation_id" "whattodo"."ref",
  "estimate_kind" "whattodo"."ref",
  "expiration_condition_ref" "whattodo"."ref",
  "expiration_notice_ref" "whattodo"."ref",
  "notice_task_revision" "whattodo"."revision",
  "audit_change_ref" "whattodo"."ref" NOT NULL,
  "aggregate_kind" "whattodo"."ref" NOT NULL,
  "transaction_ref" "whattodo"."ref" NOT NULL,
  "metadata" "whattodo"."json_object" NOT NULL,
  "due_ref" "whattodo"."ref",
  CONSTRAINT "task_revision_pk_identity" PRIMARY KEY ("task_id", "revision"),
  CONSTRAINT "task_revision_uq_1" UNIQUE ("task_id", "revision", "expiration_condition_ref"),
  CONSTRAINT "task_revision_uq_2" UNIQUE ("task_id", "revision", "transaction_ref"),
  CONSTRAINT "task_revision_uq_3" UNIQUE ("task_id", "revision", "completion"),
  CONSTRAINT "task_revision_ck_domain" CHECK (domain IN ('study','exercise','life_administration','other')),
  CONSTRAINT "task_revision_ck_context" CHECK ((context_kind IS NULL AND context_id IS NULL) OR (context_kind IS NOT NULL AND context_id IS NOT NULL AND context_kind IN ('COURSE','ACTIVITY','GOAL','EXAM'))),
  CONSTRAINT "task_revision_ck_completion" CHECK (completion IN ('INCOMPLETE','COMPLETE')),
  CONSTRAINT "task_revision_ck_disposition" CHECK (disposition IN ('ACTIVE','CANCELLED','EXPIRED')),
  CONSTRAINT "task_revision_ck_requiredness" CHECK (requiredness IN ('REQUIRED','OPTIONAL','EXPIRING')),
  CONSTRAINT "task_revision_ck_ratings" CHECK (importance BETWEEN 1 AND 5 AND thinking_depth BETWEEN 1 AND 5 AND repetitive_volume BETWEEN 1 AND 5 AND new_learning_load BETWEEN 1 AND 5),
  CONSTRAINT "task_revision_ck_complete_zero" CHECK (completion <> 'COMPLETE' OR (user_remaining_seconds IS NOT NULL AND user_remaining_seconds = 0)),
  CONSTRAINT "task_revision_ck_estimate_binding" CHECK ((user_remaining_seconds IS NULL AND estimate_observation_id IS NULL AND estimate_kind IS NULL) OR (user_remaining_seconds IS NOT NULL AND estimate_observation_id IS NOT NULL AND estimate_kind IS NOT NULL AND estimate_kind = 'USER_REMAINING')),
  CONSTRAINT "task_revision_ck_expiring_condition" CHECK ((requiredness = 'EXPIRING' AND expiration_condition_ref IS NOT NULL) OR (requiredness <> 'EXPIRING' AND expiration_condition_ref IS NULL)),
  CONSTRAINT "task_revision_ck_expiry_history" CHECK ((disposition = 'EXPIRED' AND completion = 'INCOMPLETE' AND requiredness = 'EXPIRING' AND expiration_notice_ref IS NOT NULL AND notice_task_revision IS NOT NULL AND notice_task_revision < revision) OR (disposition <> 'EXPIRED' AND expiration_notice_ref IS NULL AND notice_task_revision IS NULL)),
  CONSTRAINT "task_revision_ck_audit_kind" CHECK (aggregate_kind = 'TASK'),
  CONSTRAINT "task_revision_ck_title_length" CHECK (char_length(title) BETWEEN 1 AND 500 AND title ~ '[^[:space:]]')
);

CREATE TRIGGER "preserve_history" BEFORE UPDATE OR DELETE OR TRUNCATE ON "whattodo"."task_revision"
  FOR EACH STATEMENT EXECUTE FUNCTION "whattodo"."reject_history_mutation"();

CREATE TABLE "whattodo"."task_details_revision" (
  "task_id" "whattodo"."ref" NOT NULL,
  "task_revision" "whattodo"."revision" NOT NULL,
  "completion" "whattodo"."ref" NOT NULL,
  "created_at" "whattodo"."instant",
  "release_at" "whattodo"."instant",
  "release_original" text,
  "release_source_record_ref" "whattodo"."ref",
  "completed_at" "whattodo"."instant",
  "total_estimate_seconds" "whattodo"."seconds",
  "total_source_record_ref" "whattodo"."ref",
  "total_observed_at" "whattodo"."instant",
  "total_basis" "whattodo"."ref",
  "total_definition_kind" "whattodo"."ref",
  "total_definition_id" "whattodo"."ref",
  "total_definition_version" "whattodo"."ref",
  "minimum_session_seconds" "whattodo"."seconds",
  "fragmentable" boolean,
  CONSTRAINT "task_details_revision_pk_identity" PRIMARY KEY ("task_id", "task_revision"),
  CONSTRAINT "task_details_revision_ck_release_pair" CHECK ((release_at IS NULL AND release_original IS NULL AND release_source_record_ref IS NULL) OR (release_at IS NOT NULL AND release_original IS NOT NULL AND release_source_record_ref IS NOT NULL AND char_length(release_original) > 0)),
  CONSTRAINT "task_details_revision_ck_current_completion_time" CHECK (completed_at IS NULL OR completion = 'COMPLETE'),
  CONSTRAINT "task_details_revision_ck_minimum_session" CHECK (minimum_session_seconds IS NULL OR minimum_session_seconds > 0),
  CONSTRAINT "task_details_revision_ck_total_binding" CHECK ((total_estimate_seconds IS NULL AND total_source_record_ref IS NULL AND total_observed_at IS NULL AND total_basis IS NULL AND total_definition_kind IS NULL AND total_definition_id IS NULL AND total_definition_version IS NULL) OR (total_estimate_seconds IS NOT NULL AND total_source_record_ref IS NOT NULL AND total_observed_at IS NOT NULL AND total_basis IS NOT NULL AND ((total_basis = 'USER_REPORT' AND total_definition_kind IS NULL AND total_definition_id IS NULL AND total_definition_version IS NULL) OR (total_basis = 'TEMPLATE_DEFAULT' AND total_definition_kind IS NOT NULL AND total_definition_kind IN ('TASKTYPE','TASK_TEMPLATE') AND total_definition_id IS NOT NULL AND total_definition_version IS NOT NULL))))
);

CREATE TRIGGER "preserve_history" BEFORE UPDATE OR DELETE OR TRUNCATE ON "whattodo"."task_details_revision"
  FOR EACH STATEMENT EXECUTE FUNCTION "whattodo"."reject_history_mutation"();

CREATE TABLE "whattodo"."task_field_provenance" (
  "task_id" "whattodo"."ref" NOT NULL,
  "task_revision" "whattodo"."revision" NOT NULL,
  "field_pointer" text NOT NULL,
  "source_record_ref" "whattodo"."ref" NOT NULL,
  CONSTRAINT "task_field_provenance_pk_identity" PRIMARY KEY ("task_id", "task_revision", "field_pointer"),
  CONSTRAINT "task_field_provenance_ck_field_pointer" CHECK (field_pointer LIKE '/%' AND char_length(field_pointer) <= 500)
);

CREATE TRIGGER "preserve_history" BEFORE UPDATE OR DELETE OR TRUNCATE ON "whattodo"."task_field_provenance"
  FOR EACH STATEMENT EXECUTE FUNCTION "whattodo"."reject_history_mutation"();

CREATE TABLE "whattodo"."task_head" (
  "task_id" "whattodo"."ref" NOT NULL,
  "revision" "whattodo"."revision" NOT NULL,
  "transaction_ref" "whattodo"."ref" NOT NULL,
  CONSTRAINT "task_head_pk_identity" PRIMARY KEY ("task_id")
);

CREATE FUNCTION "whattodo"."guard_task_head"() RETURNS trigger
LANGUAGE plpgsql SET search_path = pg_catalog AS $guard$
BEGIN
  IF NEW."task_id" IS DISTINCT FROM OLD."task_id" OR
     NEW."revision" IS DISTINCT FROM OLD."revision" + 1 OR
     NEW."transaction_ref" IS NOT DISTINCT FROM OLD."transaction_ref" THEN
    RAISE EXCEPTION 'Mutable head identity, version or terminal-state mismatch' USING ERRCODE = '23514';
  END IF;
  RETURN NEW;
END;
$guard$;
REVOKE ALL ON FUNCTION "whattodo"."guard_task_head"() FROM PUBLIC;
CREATE TRIGGER "guard_version" BEFORE UPDATE ON "whattodo"."task_head" FOR EACH ROW EXECUTE FUNCTION "whattodo"."guard_task_head"();
CREATE TRIGGER "preserve_row" BEFORE DELETE OR TRUNCATE ON "whattodo"."task_head" FOR EACH STATEMENT EXECUTE FUNCTION "whattodo"."reject_history_mutation"();

CREATE TABLE "whattodo"."stage_revision" (
  "stage_id" "whattodo"."ref" NOT NULL,
  "revision" "whattodo"."revision" NOT NULL,
  "task_id" "whattodo"."ref" NOT NULL,
  "task_revision" "whattodo"."revision" NOT NULL,
  "title" "whattodo"."ref" NOT NULL,
  "completion" "whattodo"."ref" NOT NULL,
  "user_remaining_seconds" "whattodo"."seconds",
  "acceptance_ref" "whattodo"."ref" NOT NULL,
  "transaction_ref" "whattodo"."ref" NOT NULL,
  "weight_numerator" "whattodo"."positive_integer",
  "weight_denominator" "whattodo"."positive_integer",
  CONSTRAINT "stage_revision_pk_identity" PRIMARY KEY ("stage_id", "revision"),
  CONSTRAINT "stage_revision_uq_1" UNIQUE ("stage_id", "revision", "task_id"),
  CONSTRAINT "stage_revision_ck_completion" CHECK (completion IN ('INCOMPLETE','COMPLETE')),
  CONSTRAINT "stage_revision_ck_weight_pair" CHECK ((weight_numerator IS NULL AND weight_denominator IS NULL) OR (weight_numerator IS NOT NULL AND weight_denominator IS NOT NULL))
);

CREATE TRIGGER "preserve_history" BEFORE UPDATE OR DELETE OR TRUNCATE ON "whattodo"."stage_revision"
  FOR EACH STATEMENT EXECUTE FUNCTION "whattodo"."reject_history_mutation"();

CREATE TABLE "whattodo"."candidate_revision" (
  "candidate_id" "whattodo"."ref" NOT NULL,
  "revision" "whattodo"."revision" NOT NULL,
  "source_record_ref" "whattodo"."ref" NOT NULL,
  "parser_version" "whattodo"."ref" NOT NULL,
  "action" "whattodo"."ref" NOT NULL,
  "task_id" "whattodo"."ref",
  "task_revision" "whattodo"."revision",
  "proposed_fields" "whattodo"."json_object" NOT NULL,
  "confidence" "whattodo"."measure" NOT NULL,
  "review_state" "whattodo"."ref" NOT NULL,
  "review_authority_ref" "whattodo"."ref",
  "reviewed_at" "whattodo"."instant",
  "created_at" "whattodo"."instant" NOT NULL,
  "canonical_task_ref" "whattodo"."ref",
  CONSTRAINT "candidate_revision_pk_identity" PRIMARY KEY ("candidate_id", "revision"),
  CONSTRAINT "candidate_revision_ck_confidence" CHECK (confidence <= 1),
  CONSTRAINT "candidate_revision_ck_action" CHECK (action IN ('CREATE_TASK','UPDATE_TASK','COMPLETE_TASK','CANCEL_TASK')),
  CONSTRAINT "candidate_revision_ck_target" CHECK ((task_id IS NULL AND task_revision IS NULL) OR (task_id IS NOT NULL AND task_revision IS NOT NULL AND action <> 'CREATE_TASK')),
  CONSTRAINT "candidate_revision_ck_review_state" CHECK (review_state IN ('PENDING','CONFLICTED','CONFIRMED','REJECTED')),
  CONSTRAINT "candidate_revision_ck_review_authority" CHECK ((review_state IN ('PENDING','CONFLICTED') AND review_authority_ref IS NULL AND reviewed_at IS NULL) OR (review_state IN ('CONFIRMED','REJECTED') AND review_authority_ref IS NOT NULL AND reviewed_at IS NOT NULL AND reviewed_at >= created_at)),
  CONSTRAINT "candidate_revision_ck_adopted_task" CHECK ((review_state = 'CONFIRMED' AND canonical_task_ref IS NOT NULL) OR (review_state <> 'CONFIRMED' AND canonical_task_ref IS NULL))
);

CREATE TRIGGER "preserve_history" BEFORE UPDATE OR DELETE OR TRUNCATE ON "whattodo"."candidate_revision"
  FOR EACH STATEMENT EXECUTE FUNCTION "whattodo"."reject_history_mutation"();

CREATE TABLE "whattodo"."review_frame" (
  "review_id" "whattodo"."ref" NOT NULL,
  "frame_revision" "whattodo"."revision" NOT NULL,
  "queue_snapshot_ref" "whattodo"."ref" NOT NULL,
  "presented_at" "whattodo"."instant" NOT NULL,
  "full_frame" "whattodo"."json_object" NOT NULL,
  CONSTRAINT "review_frame_pk_identity" PRIMARY KEY ("review_id", "frame_revision")
);

CREATE TRIGGER "preserve_history" BEFORE UPDATE OR DELETE OR TRUNCATE ON "whattodo"."review_frame"
  FOR EACH STATEMENT EXECUTE FUNCTION "whattodo"."reject_history_mutation"();

CREATE TABLE "whattodo"."review_member" (
  "review_id" "whattodo"."ref" NOT NULL,
  "frame_revision" "whattodo"."revision" NOT NULL,
  "member_kind" "whattodo"."ref" NOT NULL,
  "member_id" "whattodo"."ref" NOT NULL,
  "member_revision" "whattodo"."revision" NOT NULL,
  "task_ref" "whattodo"."ref",
  "task_revision" "whattodo"."revision",
  "candidate_ref" "whattodo"."ref",
  "candidate_revision" "whattodo"."revision",
  "estimate_observation_ref" "whattodo"."ref",
  CONSTRAINT "review_member_pk_identity" PRIMARY KEY ("review_id", "frame_revision", "member_kind", "member_id"),
  CONSTRAINT "review_member_uq_1" UNIQUE ("review_id", "frame_revision", "member_kind", "member_id", "member_revision", "estimate_observation_ref"),
  CONSTRAINT "review_member_ck_kind" CHECK ((member_kind = 'TASK' AND task_ref IS NOT NULL AND task_revision IS NOT NULL AND task_ref = member_id AND task_revision = member_revision AND candidate_ref IS NULL AND candidate_revision IS NULL) OR (member_kind = 'CANDIDATE' AND candidate_ref IS NOT NULL AND candidate_revision IS NOT NULL AND candidate_ref = member_id AND candidate_revision = member_revision AND task_ref IS NULL AND task_revision IS NULL)),
  CONSTRAINT "review_member_ck_candidate_estimate" CHECK (member_kind <> 'CANDIDATE' OR estimate_observation_ref IS NULL)
);

CREATE TRIGGER "preserve_history" BEFORE UPDATE OR DELETE OR TRUNCATE ON "whattodo"."review_member"
  FOR EACH STATEMENT EXECUTE FUNCTION "whattodo"."reject_history_mutation"();

CREATE TABLE "whattodo"."review_response" (
  "response_id" "whattodo"."ref" NOT NULL,
  "review_id" "whattodo"."ref" NOT NULL,
  "frame_revision" "whattodo"."revision" NOT NULL,
  "submitted" boolean NOT NULL,
  "user_statement_ref" "whattodo"."ref",
  "received_at" "whattodo"."instant" NOT NULL,
  "response" "whattodo"."json_object" NOT NULL,
  CONSTRAINT "review_response_pk_identity" PRIMARY KEY ("response_id"),
  CONSTRAINT "review_response_uq_1" UNIQUE ("response_id", "review_id", "frame_revision"),
  CONSTRAINT "review_response_ck_explicit_submission" CHECK ((submitted = TRUE AND user_statement_ref IS NOT NULL) OR (submitted = FALSE AND user_statement_ref IS NULL))
);

CREATE TRIGGER "preserve_history" BEFORE UPDATE OR DELETE OR TRUNCATE ON "whattodo"."review_response"
  FOR EACH STATEMENT EXECUTE FUNCTION "whattodo"."reject_history_mutation"();

CREATE TABLE "whattodo"."estimate_verification" (
  "verification_id" "whattodo"."ref" NOT NULL,
  "task_id" "whattodo"."ref" NOT NULL,
  "task_revision" "whattodo"."revision" NOT NULL,
  "observation_id" "whattodo"."ref" NOT NULL,
  "batch_id" "whattodo"."ref" NOT NULL,
  "response_id" "whattodo"."ref" NOT NULL,
  "review_id" "whattodo"."ref" NOT NULL,
  "frame_revision" "whattodo"."revision" NOT NULL,
  "member_kind" "whattodo"."ref" NOT NULL,
  "verified_at" "whattodo"."instant" NOT NULL,
  "authority_ref" "whattodo"."ref" NOT NULL,
  "transaction_ref" "whattodo"."ref" NOT NULL,
  "observation_kind" "whattodo"."ref" NOT NULL,
  CONSTRAINT "estimate_verification_pk_identity" PRIMARY KEY ("verification_id"),
  CONSTRAINT "estimate_verification_uq_1" UNIQUE ("response_id", "batch_id", "task_id"),
  CONSTRAINT "estimate_verification_ck_kind" CHECK (member_kind = 'TASK'),
  CONSTRAINT "estimate_verification_ck_user_estimate" CHECK (observation_kind = 'USER_REMAINING')
);

CREATE TRIGGER "preserve_history" BEFORE UPDATE OR DELETE OR TRUNCATE ON "whattodo"."estimate_verification"
  FOR EACH STATEMENT EXECUTE FUNCTION "whattodo"."reject_history_mutation"();

ALTER TABLE "whattodo"."task_identity" ADD CONSTRAINT "task_identity_fk_1"
  FOREIGN KEY ("transaction_ref") REFERENCES "whattodo"."command_transaction" ("request_id")
  ON UPDATE NO ACTION ON DELETE NO ACTION DEFERRABLE INITIALLY DEFERRED;

ALTER TABLE "whattodo"."effort_observation" ADD CONSTRAINT "effort_observation_fk_1"
  FOREIGN KEY ("task_id") REFERENCES "whattodo"."task_identity" ("task_id")
  ON UPDATE NO ACTION ON DELETE NO ACTION DEFERRABLE INITIALLY DEFERRED;

ALTER TABLE "whattodo"."effort_observation" ADD CONSTRAINT "effort_observation_fk_2"
  FOREIGN KEY ("source_record_ref") REFERENCES "whattodo"."source_record" ("record_id")
  ON UPDATE NO ACTION ON DELETE NO ACTION DEFERRABLE INITIALLY DEFERRED;

ALTER TABLE "whattodo"."effort_observation" ADD CONSTRAINT "effort_observation_fk_3"
  FOREIGN KEY ("authority_ref") REFERENCES "whattodo"."authority_record" ("authority_ref")
  ON UPDATE NO ACTION ON DELETE NO ACTION DEFERRABLE INITIALLY DEFERRED;

ALTER TABLE "whattodo"."effort_observation" ADD CONSTRAINT "effort_observation_fk_4"
  FOREIGN KEY ("transaction_ref") REFERENCES "whattodo"."command_transaction" ("request_id")
  ON UPDATE NO ACTION ON DELETE NO ACTION DEFERRABLE INITIALLY DEFERRED;

ALTER TABLE "whattodo"."task_revision" ADD CONSTRAINT "task_revision_fk_1"
  FOREIGN KEY ("task_id") REFERENCES "whattodo"."task_identity" ("task_id")
  ON UPDATE NO ACTION ON DELETE NO ACTION DEFERRABLE INITIALLY DEFERRED;

ALTER TABLE "whattodo"."task_revision" ADD CONSTRAINT "task_revision_fk_2"
  FOREIGN KEY ("task_type_ref") REFERENCES "whattodo"."configuration_revision" ("configuration_ref")
  ON UPDATE NO ACTION ON DELETE NO ACTION DEFERRABLE INITIALLY DEFERRED;

ALTER TABLE "whattodo"."task_revision" ADD CONSTRAINT "task_revision_fk_3"
  FOREIGN KEY ("acceptance_ref") REFERENCES "whattodo"."authority_record" ("authority_ref")
  ON UPDATE NO ACTION ON DELETE NO ACTION DEFERRABLE INITIALLY DEFERRED;

ALTER TABLE "whattodo"."task_revision" ADD CONSTRAINT "task_revision_fk_4"
  FOREIGN KEY ("task_id", "estimate_observation_id", "estimate_kind", "user_remaining_seconds") REFERENCES "whattodo"."effort_observation" ("task_id", "observation_id", "kind", "seconds")
  ON UPDATE NO ACTION ON DELETE NO ACTION DEFERRABLE INITIALLY DEFERRED;

ALTER TABLE "whattodo"."task_revision" ADD CONSTRAINT "task_revision_fk_6"
  FOREIGN KEY ("transaction_ref") REFERENCES "whattodo"."command_transaction" ("request_id")
  ON UPDATE NO ACTION ON DELETE NO ACTION DEFERRABLE INITIALLY DEFERRED;

ALTER TABLE "whattodo"."task_revision" ADD CONSTRAINT "task_revision_fk_7"
  FOREIGN KEY ("audit_change_ref", "aggregate_kind", "task_id", "revision", "transaction_ref") REFERENCES "whattodo"."audit_change" ("change_id", "aggregate_kind", "aggregate_id", "after_revision", "request_id")
  ON UPDATE NO ACTION ON DELETE NO ACTION DEFERRABLE INITIALLY DEFERRED;

ALTER TABLE "whattodo"."task_details_revision" ADD CONSTRAINT "task_details_revision_fk_1"
  FOREIGN KEY ("task_id", "task_revision", "completion") REFERENCES "whattodo"."task_revision" ("task_id", "revision", "completion")
  ON UPDATE NO ACTION ON DELETE NO ACTION DEFERRABLE INITIALLY DEFERRED;

ALTER TABLE "whattodo"."task_details_revision" ADD CONSTRAINT "task_details_revision_fk_2"
  FOREIGN KEY ("release_source_record_ref") REFERENCES "whattodo"."source_record" ("record_id")
  ON UPDATE NO ACTION ON DELETE NO ACTION DEFERRABLE INITIALLY DEFERRED;

ALTER TABLE "whattodo"."task_details_revision" ADD CONSTRAINT "task_details_revision_fk_3"
  FOREIGN KEY ("total_source_record_ref") REFERENCES "whattodo"."source_record" ("record_id")
  ON UPDATE NO ACTION ON DELETE NO ACTION DEFERRABLE INITIALLY DEFERRED;

ALTER TABLE "whattodo"."task_details_revision" ADD CONSTRAINT "task_details_revision_fk_4"
  FOREIGN KEY ("total_definition_kind", "total_definition_id", "total_definition_version") REFERENCES "whattodo"."configuration_revision" ("kind", "id", "version")
  ON UPDATE NO ACTION ON DELETE NO ACTION DEFERRABLE INITIALLY DEFERRED;

ALTER TABLE "whattodo"."task_field_provenance" ADD CONSTRAINT "task_field_provenance_fk_1"
  FOREIGN KEY ("task_id", "task_revision") REFERENCES "whattodo"."task_revision" ("task_id", "revision")
  ON UPDATE NO ACTION ON DELETE NO ACTION DEFERRABLE INITIALLY DEFERRED;

ALTER TABLE "whattodo"."task_field_provenance" ADD CONSTRAINT "task_field_provenance_fk_2"
  FOREIGN KEY ("source_record_ref") REFERENCES "whattodo"."source_record" ("record_id")
  ON UPDATE NO ACTION ON DELETE NO ACTION DEFERRABLE INITIALLY DEFERRED;

ALTER TABLE "whattodo"."task_head" ADD CONSTRAINT "task_head_fk_1"
  FOREIGN KEY ("transaction_ref") REFERENCES "whattodo"."command_transaction" ("request_id")
  ON UPDATE NO ACTION ON DELETE NO ACTION DEFERRABLE INITIALLY DEFERRED;

ALTER TABLE "whattodo"."task_head" ADD CONSTRAINT "task_head_fk_2"
  FOREIGN KEY ("task_id", "revision", "transaction_ref") REFERENCES "whattodo"."task_revision" ("task_id", "revision", "transaction_ref")
  ON UPDATE NO ACTION ON DELETE NO ACTION DEFERRABLE INITIALLY DEFERRED;

ALTER TABLE "whattodo"."stage_revision" ADD CONSTRAINT "stage_revision_fk_1"
  FOREIGN KEY ("task_id", "task_revision") REFERENCES "whattodo"."task_revision" ("task_id", "revision")
  ON UPDATE NO ACTION ON DELETE NO ACTION DEFERRABLE INITIALLY DEFERRED;

ALTER TABLE "whattodo"."stage_revision" ADD CONSTRAINT "stage_revision_fk_2"
  FOREIGN KEY ("acceptance_ref") REFERENCES "whattodo"."authority_record" ("authority_ref")
  ON UPDATE NO ACTION ON DELETE NO ACTION DEFERRABLE INITIALLY DEFERRED;

ALTER TABLE "whattodo"."stage_revision" ADD CONSTRAINT "stage_revision_fk_3"
  FOREIGN KEY ("transaction_ref") REFERENCES "whattodo"."command_transaction" ("request_id")
  ON UPDATE NO ACTION ON DELETE NO ACTION DEFERRABLE INITIALLY DEFERRED;

ALTER TABLE "whattodo"."candidate_revision" ADD CONSTRAINT "candidate_revision_fk_1"
  FOREIGN KEY ("source_record_ref") REFERENCES "whattodo"."source_record" ("record_id")
  ON UPDATE NO ACTION ON DELETE NO ACTION DEFERRABLE INITIALLY DEFERRED;

ALTER TABLE "whattodo"."candidate_revision" ADD CONSTRAINT "candidate_revision_fk_2"
  FOREIGN KEY ("task_id", "task_revision") REFERENCES "whattodo"."task_revision" ("task_id", "revision")
  ON UPDATE NO ACTION ON DELETE NO ACTION DEFERRABLE INITIALLY DEFERRED;

ALTER TABLE "whattodo"."candidate_revision" ADD CONSTRAINT "candidate_revision_fk_3"
  FOREIGN KEY ("review_authority_ref") REFERENCES "whattodo"."authority_record" ("authority_ref")
  ON UPDATE NO ACTION ON DELETE NO ACTION DEFERRABLE INITIALLY DEFERRED;

ALTER TABLE "whattodo"."candidate_revision" ADD CONSTRAINT "candidate_revision_fk_4"
  FOREIGN KEY ("canonical_task_ref") REFERENCES "whattodo"."task_identity" ("task_id")
  ON UPDATE NO ACTION ON DELETE NO ACTION DEFERRABLE INITIALLY DEFERRED;

ALTER TABLE "whattodo"."review_member" ADD CONSTRAINT "review_member_fk_1"
  FOREIGN KEY ("review_id", "frame_revision") REFERENCES "whattodo"."review_frame" ("review_id", "frame_revision")
  ON UPDATE NO ACTION ON DELETE NO ACTION DEFERRABLE INITIALLY DEFERRED;

ALTER TABLE "whattodo"."review_member" ADD CONSTRAINT "review_member_fk_2"
  FOREIGN KEY ("task_ref", "task_revision") REFERENCES "whattodo"."task_revision" ("task_id", "revision")
  ON UPDATE NO ACTION ON DELETE NO ACTION DEFERRABLE INITIALLY DEFERRED;

ALTER TABLE "whattodo"."review_member" ADD CONSTRAINT "review_member_fk_3"
  FOREIGN KEY ("candidate_ref", "candidate_revision") REFERENCES "whattodo"."candidate_revision" ("candidate_id", "revision")
  ON UPDATE NO ACTION ON DELETE NO ACTION DEFERRABLE INITIALLY DEFERRED;

ALTER TABLE "whattodo"."review_member" ADD CONSTRAINT "review_member_fk_4"
  FOREIGN KEY ("task_ref", "estimate_observation_ref") REFERENCES "whattodo"."effort_observation" ("task_id", "observation_id")
  ON UPDATE NO ACTION ON DELETE NO ACTION DEFERRABLE INITIALLY DEFERRED;

ALTER TABLE "whattodo"."review_response" ADD CONSTRAINT "review_response_fk_1"
  FOREIGN KEY ("review_id", "frame_revision") REFERENCES "whattodo"."review_frame" ("review_id", "frame_revision")
  ON UPDATE NO ACTION ON DELETE NO ACTION DEFERRABLE INITIALLY DEFERRED;

ALTER TABLE "whattodo"."review_response" ADD CONSTRAINT "review_response_fk_2"
  FOREIGN KEY ("user_statement_ref") REFERENCES "whattodo"."source_record" ("record_id")
  ON UPDATE NO ACTION ON DELETE NO ACTION DEFERRABLE INITIALLY DEFERRED;

ALTER TABLE "whattodo"."estimate_verification" ADD CONSTRAINT "estimate_verification_fk_1"
  FOREIGN KEY ("task_id", "task_revision") REFERENCES "whattodo"."task_revision" ("task_id", "revision")
  ON UPDATE NO ACTION ON DELETE NO ACTION DEFERRABLE INITIALLY DEFERRED;

ALTER TABLE "whattodo"."estimate_verification" ADD CONSTRAINT "estimate_verification_fk_2"
  FOREIGN KEY ("response_id", "review_id", "frame_revision") REFERENCES "whattodo"."review_response" ("response_id", "review_id", "frame_revision")
  ON UPDATE NO ACTION ON DELETE NO ACTION DEFERRABLE INITIALLY DEFERRED;

ALTER TABLE "whattodo"."estimate_verification" ADD CONSTRAINT "estimate_verification_fk_3"
  FOREIGN KEY ("authority_ref") REFERENCES "whattodo"."authority_record" ("authority_ref")
  ON UPDATE NO ACTION ON DELETE NO ACTION DEFERRABLE INITIALLY DEFERRED;

ALTER TABLE "whattodo"."estimate_verification" ADD CONSTRAINT "estimate_verification_fk_4"
  FOREIGN KEY ("transaction_ref") REFERENCES "whattodo"."command_transaction" ("request_id")
  ON UPDATE NO ACTION ON DELETE NO ACTION DEFERRABLE INITIALLY DEFERRED;

ALTER TABLE "whattodo"."estimate_verification" ADD CONSTRAINT "estimate_verification_fk_5"
  FOREIGN KEY ("task_id", "observation_id", "observation_kind") REFERENCES "whattodo"."effort_observation" ("task_id", "observation_id", "kind")
  ON UPDATE NO ACTION ON DELETE NO ACTION DEFERRABLE INITIALLY DEFERRED;

ALTER TABLE "whattodo"."estimate_verification" ADD CONSTRAINT "estimate_verification_fk_6"
  FOREIGN KEY ("review_id", "frame_revision", "member_kind", "task_id", "task_revision", "observation_id") REFERENCES "whattodo"."review_member" ("review_id", "frame_revision", "member_kind", "member_id", "member_revision", "estimate_observation_ref")
  ON UPDATE NO ACTION ON DELETE NO ACTION DEFERRABLE INITIALLY DEFERRED;

REVOKE ALL ON ALL TABLES IN SCHEMA "whattodo" FROM PUBLIC;
COMMIT;
