-- Generated draft 0.1.0: NOT release-frozen or application-migrated.
-- Review/freeze and run in an isolated database before activation.
BEGIN;
SET LOCAL search_path = pg_catalog;

CREATE TABLE "whattodo"."model_revision" (
  "model_id" "whattodo"."ref" NOT NULL,
  "version" "whattodo"."ref" NOT NULL,
  "artifact_hash" "whattodo"."sha256" NOT NULL,
  "artifact_ref" "whattodo"."ref" NOT NULL,
  "training_evidence_ref" "whattodo"."ref" NOT NULL,
  "registered_at" "whattodo"."instant" NOT NULL,
  "state" "whattodo"."ref" NOT NULL,
  CONSTRAINT "model_revision_pk_identity" PRIMARY KEY ("model_id", "version"),
  CONSTRAINT "model_revision_ck_state" CHECK (state IN ('CANDIDATE','VALIDATED','RETIRED'))
);

CREATE TRIGGER "preserve_history" BEFORE UPDATE OR DELETE OR TRUNCATE ON "whattodo"."model_revision"
  FOR EACH STATEMENT EXECUTE FUNCTION "whattodo"."reject_history_mutation"();

CREATE TABLE "whattodo"."ai_job_revision" (
  "job_id" "whattodo"."ref" NOT NULL,
  "revision" "whattodo"."revision" NOT NULL,
  "job_type" "whattodo"."ref" NOT NULL,
  "executor_class" "whattodo"."ref" NOT NULL,
  "priority" smallint NOT NULL,
  "context_ref" "whattodo"."ref" NOT NULL,
  "context_hash" "whattodo"."sha256" NOT NULL,
  "snapshot_ref" "whattodo"."ref" NOT NULL,
  "output_contract_ref" "whattodo"."ref" NOT NULL,
  "expected_kind" "whattodo"."ref" NOT NULL,
  "created_at" "whattodo"."instant" NOT NULL,
  "status" "whattodo"."ref" NOT NULL,
  "exported_at" "whattodo"."instant",
  "targets" "whattodo"."json_object" NOT NULL,
  CONSTRAINT "ai_job_revision_pk_identity" PRIMARY KEY ("job_id", "revision"),
  CONSTRAINT "ai_job_revision_uq_1" UNIQUE ("job_id", "revision", "context_hash", "snapshot_ref"),
  CONSTRAINT "ai_job_revision_uq_2" UNIQUE ("job_id", "revision", "context_hash", "snapshot_ref", "output_contract_ref", "expected_kind"),
  CONSTRAINT "ai_job_revision_ck_executor" CHECK (executor_class IN ('DETERMINISTIC','AUTOMATED','MANUAL_PREMIUM')),
  CONSTRAINT "ai_job_revision_ck_priority" CHECK (priority BETWEEN 1 AND 5),
  CONSTRAINT "ai_job_revision_ck_kind" CHECK (expected_kind IN ('NUMERIC_REMAINING','BEHAVIOR_PROPOSAL')),
  CONSTRAINT "ai_job_revision_ck_status" CHECK (status IN ('PENDING','EXPORTED','RUNNING','RESULT_RECEIVED','VALIDATED','REJECTED','CANCELLED')),
  CONSTRAINT "ai_job_revision_ck_export" CHECK ((status <> 'EXPORTED' OR exported_at IS NOT NULL) AND (status <> 'PENDING' OR exported_at IS NULL) AND (exported_at IS NULL OR exported_at >= created_at))
);

CREATE TRIGGER "preserve_history" BEFORE UPDATE OR DELETE OR TRUNCATE ON "whattodo"."ai_job_revision"
  FOR EACH STATEMENT EXECUTE FUNCTION "whattodo"."reject_history_mutation"();

CREATE TABLE "whattodo"."ai_result" (
  "job_id" "whattodo"."ref" NOT NULL,
  "result_id" "whattodo"."ref" NOT NULL,
  "job_revision" "whattodo"."revision" NOT NULL,
  "context_hash" "whattodo"."sha256" NOT NULL,
  "snapshot_ref" "whattodo"."ref" NOT NULL,
  "output_contract_ref" "whattodo"."ref" NOT NULL,
  "kind" "whattodo"."ref" NOT NULL,
  "executor_ref" "whattodo"."ref" NOT NULL,
  "finished_at" "whattodo"."instant" NOT NULL,
  "content_hash" "whattodo"."sha256" NOT NULL,
  "payload" "whattodo"."json_object" NOT NULL,
  "input_tokens" "whattodo"."seconds",
  "output_tokens" "whattodo"."seconds",
  "cost_amount" "whattodo"."measure",
  "currency" "whattodo"."ref",
  "resolved_job_id" "whattodo"."ref",
  "resolved_job_revision" "whattodo"."revision",
  "raw_source_record_ref" "whattodo"."ref" NOT NULL,
  CONSTRAINT "ai_result_pk_identity" PRIMARY KEY ("job_id", "result_id"),
  CONSTRAINT "ai_result_uq_1" UNIQUE ("job_id", "result_id", "content_hash"),
  CONSTRAINT "ai_result_uq_2" UNIQUE ("job_id", "result_id", "content_hash", "context_hash", "snapshot_ref", "output_contract_ref", "kind"),
  CONSTRAINT "ai_result_uq_3" UNIQUE ("job_id", "job_revision", "result_id", "content_hash", "context_hash", "snapshot_ref", "output_contract_ref", "kind"),
  CONSTRAINT "ai_result_ck_kind" CHECK (kind IN ('NUMERIC_REMAINING','BEHAVIOR_PROPOSAL')),
  CONSTRAINT "ai_result_ck_currency" CHECK (cost_amount IS NULL OR currency IS NOT NULL),
  CONSTRAINT "ai_result_ck_resolved_scope" CHECK ((resolved_job_id IS NULL AND resolved_job_revision IS NULL) OR (resolved_job_id IS NOT NULL AND resolved_job_revision IS NOT NULL AND resolved_job_id = job_id AND resolved_job_revision = job_revision))
);

CREATE TRIGGER "preserve_history" BEFORE UPDATE OR DELETE OR TRUNCATE ON "whattodo"."ai_result"
  FOR EACH STATEMENT EXECUTE FUNCTION "whattodo"."reject_history_mutation"();

CREATE TABLE "whattodo"."ai_import_record" (
  "import_id" "whattodo"."ref" NOT NULL,
  "job_id" "whattodo"."ref" NOT NULL,
  "result_id" "whattodo"."ref" NOT NULL,
  "result_hash" "whattodo"."sha256" NOT NULL,
  "validation_state" "whattodo"."ref" NOT NULL,
  "reason_code" "whattodo"."ref" NOT NULL,
  "validated_at" "whattodo"."instant" NOT NULL,
  CONSTRAINT "ai_import_record_pk_identity" PRIMARY KEY ("import_id"),
  CONSTRAINT "ai_import_record_uq_1" UNIQUE ("job_id", "result_id"),
  CONSTRAINT "ai_import_record_ck_state" CHECK (validation_state IN ('VALIDATED_NUMERIC','PENDING_REVIEW','REJECTED'))
);

CREATE TRIGGER "preserve_history" BEFORE UPDATE OR DELETE OR TRUNCATE ON "whattodo"."ai_import_record"
  FOR EACH STATEMENT EXECUTE FUNCTION "whattodo"."reject_history_mutation"();

CREATE TABLE "whattodo"."numeric_eligibility" (
  "eligibility_ref" "whattodo"."ref" NOT NULL,
  "task_id" "whattodo"."ref" NOT NULL,
  "task_revision" "whattodo"."revision" NOT NULL,
  "model_id" "whattodo"."ref" NOT NULL,
  "model_version" "whattodo"."ref" NOT NULL,
  "context_hash" "whattodo"."sha256" NOT NULL,
  "snapshot_ref" "whattodo"."ref" NOT NULL,
  "evaluated_at" "whattodo"."instant" NOT NULL,
  "valid_until" "whattodo"."instant" NOT NULL,
  "evaluator_ref" "whattodo"."ref" NOT NULL,
  "model_state_event_ref" "whattodo"."ref" NOT NULL,
  "model_state" "whattodo"."ref" NOT NULL,
  CONSTRAINT "numeric_eligibility_pk_identity" PRIMARY KEY ("eligibility_ref"),
  CONSTRAINT "numeric_eligibility_uq_1" UNIQUE ("eligibility_ref", "task_id", "task_revision", "model_id", "model_version", "context_hash", "snapshot_ref"),
  CONSTRAINT "numeric_eligibility_ck_validity" CHECK (valid_until > evaluated_at),
  CONSTRAINT "numeric_eligibility_ck_model_validated" CHECK (model_state = 'VALIDATED')
);

CREATE TRIGGER "preserve_history" BEFORE UPDATE OR DELETE OR TRUNCATE ON "whattodo"."numeric_eligibility"
  FOR EACH STATEMENT EXECUTE FUNCTION "whattodo"."reject_history_mutation"();

CREATE TABLE "whattodo"."remaining_prediction" (
  "prediction_id" "whattodo"."ref" NOT NULL,
  "task_id" "whattodo"."ref" NOT NULL,
  "task_revision" "whattodo"."revision" NOT NULL,
  "model_id" "whattodo"."ref" NOT NULL,
  "model_version" "whattodo"."ref" NOT NULL,
  "job_id" "whattodo"."ref" NOT NULL,
  "result_id" "whattodo"."ref" NOT NULL,
  "result_hash" "whattodo"."sha256" NOT NULL,
  "eligibility_ref" "whattodo"."ref" NOT NULL,
  "context_hash" "whattodo"."sha256" NOT NULL,
  "snapshot_ref" "whattodo"."ref" NOT NULL,
  "remaining_seconds" "whattodo"."seconds" NOT NULL,
  "computed_at" "whattodo"."instant" NOT NULL,
  "valid_until" "whattodo"."instant" NOT NULL,
  "uncertainty_ref" "whattodo"."ref",
  "job_revision" "whattodo"."revision" NOT NULL,
  "output_contract_ref" "whattodo"."ref" NOT NULL,
  "kind" "whattodo"."ref" NOT NULL,
  CONSTRAINT "remaining_prediction_pk_identity" PRIMARY KEY ("prediction_id"),
  CONSTRAINT "remaining_prediction_ck_validity" CHECK (valid_until > computed_at),
  CONSTRAINT "remaining_prediction_ck_remaining_kind" CHECK (kind = 'NUMERIC_REMAINING')
);

CREATE TRIGGER "preserve_history" BEFORE UPDATE OR DELETE OR TRUNCATE ON "whattodo"."remaining_prediction"
  FOR EACH STATEMENT EXECUTE FUNCTION "whattodo"."reject_history_mutation"();

CREATE TABLE "whattodo"."behavior_candidate" (
  "candidate_id" "whattodo"."ref" NOT NULL,
  "job_id" "whattodo"."ref" NOT NULL,
  "result_id" "whattodo"."ref" NOT NULL,
  "result_hash" "whattodo"."sha256" NOT NULL,
  "target_kind" "whattodo"."ref" NOT NULL,
  "target_id" "whattodo"."ref" NOT NULL,
  "target_revision" "whattodo"."revision" NOT NULL,
  "policy_kind" "whattodo"."ref" NOT NULL,
  "proposed_value" "whattodo"."json_object" NOT NULL,
  "confidence" "whattodo"."measure" NOT NULL,
  "review_state" "whattodo"."ref" NOT NULL,
  "created_at" "whattodo"."instant" NOT NULL,
  CONSTRAINT "behavior_candidate_pk_identity" PRIMARY KEY ("candidate_id"),
  CONSTRAINT "behavior_candidate_ck_target_kind" CHECK (target_kind IN ('TASK','TASKTYPE','PREFERENCE','RELATIONSHIP_RULE')),
  CONSTRAINT "behavior_candidate_ck_policy_kind" CHECK (policy_kind IN ('PREFERENCE','TASKTYPE_DEFAULT','RELATIONSHIP_RULE','DECOMPOSITION')),
  CONSTRAINT "behavior_candidate_ck_confidence" CHECK (confidence <= 1),
  CONSTRAINT "behavior_candidate_ck_pending" CHECK (review_state = 'PENDING')
);

CREATE TRIGGER "preserve_history" BEFORE UPDATE OR DELETE OR TRUNCATE ON "whattodo"."behavior_candidate"
  FOR EACH STATEMENT EXECUTE FUNCTION "whattodo"."reject_history_mutation"();

CREATE TABLE "whattodo"."outbox_entry" (
  "outbox_id" "whattodo"."ref" NOT NULL,
  "idempotency_key" "whattodo"."ref" NOT NULL,
  "kind" "whattodo"."ref" NOT NULL,
  "aggregate_ref" "whattodo"."ref" NOT NULL,
  "payload_hash" "whattodo"."sha256" NOT NULL,
  "payload" "whattodo"."json_object" NOT NULL,
  "state" "whattodo"."ref" NOT NULL,
  "revision" "whattodo"."revision" NOT NULL,
  "delivery_evidence_ref" "whattodo"."ref",
  "delivered_at" "whattodo"."instant",
  "created_at" "whattodo"."instant" NOT NULL,
  "transaction_ref" "whattodo"."ref" NOT NULL,
  "audit_change_ref" "whattodo"."ref" NOT NULL,
  "aggregate_kind" "whattodo"."ref" NOT NULL,
  CONSTRAINT "outbox_entry_pk_identity" PRIMARY KEY ("outbox_id"),
  CONSTRAINT "outbox_entry_uq_1" UNIQUE ("idempotency_key"),
  CONSTRAINT "outbox_entry_ck_state" CHECK (state IN ('PENDING','IN_FLIGHT','FAILED','UNKNOWN','DELIVERED')),
  CONSTRAINT "outbox_entry_ck_delivery" CHECK ((state = 'DELIVERED' AND delivery_evidence_ref IS NOT NULL AND delivered_at IS NOT NULL AND delivered_at >= created_at) OR (state <> 'DELIVERED' AND delivery_evidence_ref IS NULL AND delivered_at IS NULL)),
  CONSTRAINT "outbox_entry_ck_audit_kind" CHECK (aggregate_kind = 'OUTBOX')
);

CREATE FUNCTION "whattodo"."guard_outbox_entry"() RETURNS trigger
LANGUAGE plpgsql SET search_path = pg_catalog AS $guard$
BEGIN
  IF NEW."outbox_id" IS DISTINCT FROM OLD."outbox_id" OR
     NEW."idempotency_key" IS DISTINCT FROM OLD."idempotency_key" OR
     NEW."kind" IS DISTINCT FROM OLD."kind" OR
     NEW."aggregate_ref" IS DISTINCT FROM OLD."aggregate_ref" OR
     NEW."payload_hash" IS DISTINCT FROM OLD."payload_hash" OR
     NEW."payload" IS DISTINCT FROM OLD."payload" OR
     NEW."created_at" IS DISTINCT FROM OLD."created_at" OR
     NEW."revision" IS DISTINCT FROM OLD."revision" + 1 OR
     NEW."transaction_ref" IS NOT DISTINCT FROM OLD."transaction_ref" OR
     (OLD.state <> 'DELIVERED' OR (NEW.state = 'DELIVERED' AND NEW.delivery_evidence_ref IS NOT DISTINCT FROM OLD.delivery_evidence_ref AND NEW.delivered_at IS NOT DISTINCT FROM OLD.delivered_at)) IS NOT TRUE THEN
    RAISE EXCEPTION 'Mutable head identity, version or terminal-state mismatch' USING ERRCODE = '23514';
  END IF;
  RETURN NEW;
END;
$guard$;
REVOKE ALL ON FUNCTION "whattodo"."guard_outbox_entry"() FROM PUBLIC;
CREATE TRIGGER "guard_version" BEFORE UPDATE ON "whattodo"."outbox_entry" FOR EACH ROW EXECUTE FUNCTION "whattodo"."guard_outbox_entry"();
CREATE TRIGGER "preserve_row" BEFORE DELETE OR TRUNCATE ON "whattodo"."outbox_entry" FOR EACH STATEMENT EXECUTE FUNCTION "whattodo"."reject_history_mutation"();

CREATE TABLE "whattodo"."collector_checkpoint" (
  "provider" "whattodo"."ref" NOT NULL,
  "scope_ref" "whattodo"."ref" NOT NULL,
  "collector_id" "whattodo"."ref" NOT NULL,
  "revision" "whattodo"."revision" NOT NULL,
  "cursor" "whattodo"."ref",
  "last_source_record_ref" "whattodo"."ref",
  "updated_at" "whattodo"."instant" NOT NULL,
  "transaction_ref" "whattodo"."ref" NOT NULL,
  "audit_change_ref" "whattodo"."ref" NOT NULL,
  "aggregate_key" "whattodo"."ref" NOT NULL,
  "aggregate_kind" "whattodo"."ref" NOT NULL,
  CONSTRAINT "collector_checkpoint_pk_identity" PRIMARY KEY ("provider", "scope_ref", "collector_id"),
  CONSTRAINT "collector_checkpoint_ck_audit_kind" CHECK (aggregate_kind = 'COLLECTOR_CHECKPOINT')
);

CREATE FUNCTION "whattodo"."guard_collector_checkpoint"() RETURNS trigger
LANGUAGE plpgsql SET search_path = pg_catalog AS $guard$
BEGIN
  IF NEW."provider" IS DISTINCT FROM OLD."provider" OR
     NEW."scope_ref" IS DISTINCT FROM OLD."scope_ref" OR
     NEW."collector_id" IS DISTINCT FROM OLD."collector_id" OR
     NEW."aggregate_key" IS DISTINCT FROM OLD."aggregate_key" OR
     NEW."revision" IS DISTINCT FROM OLD."revision" + 1 OR
     NEW."transaction_ref" IS NOT DISTINCT FROM OLD."transaction_ref" THEN
    RAISE EXCEPTION 'Mutable head identity, version or terminal-state mismatch' USING ERRCODE = '23514';
  END IF;
  RETURN NEW;
END;
$guard$;
REVOKE ALL ON FUNCTION "whattodo"."guard_collector_checkpoint"() FROM PUBLIC;
CREATE TRIGGER "guard_version" BEFORE UPDATE ON "whattodo"."collector_checkpoint" FOR EACH ROW EXECUTE FUNCTION "whattodo"."guard_collector_checkpoint"();
CREATE TRIGGER "preserve_row" BEFORE DELETE OR TRUNCATE ON "whattodo"."collector_checkpoint" FOR EACH STATEMENT EXECUTE FUNCTION "whattodo"."reject_history_mutation"();

CREATE TABLE "whattodo"."model_lifecycle_event" (
  "event_id" "whattodo"."ref" NOT NULL,
  "model_id" "whattodo"."ref" NOT NULL,
  "model_version" "whattodo"."ref" NOT NULL,
  "sequence" "whattodo"."revision" NOT NULL,
  "state" "whattodo"."ref" NOT NULL,
  "evaluator_ref" "whattodo"."ref" NOT NULL,
  "evidence_hash" "whattodo"."sha256" NOT NULL,
  "observed_at" "whattodo"."instant" NOT NULL,
  CONSTRAINT "model_lifecycle_event_pk_identity" PRIMARY KEY ("event_id"),
  CONSTRAINT "model_lifecycle_event_uq_1" UNIQUE ("model_id", "model_version", "sequence"),
  CONSTRAINT "model_lifecycle_event_uq_2" UNIQUE ("event_id", "model_id", "model_version", "state"),
  CONSTRAINT "model_lifecycle_event_ck_state" CHECK (state IN ('CANDIDATE','VALIDATED','RETIRED'))
);

CREATE TRIGGER "preserve_history" BEFORE UPDATE OR DELETE OR TRUNCATE ON "whattodo"."model_lifecycle_event"
  FOR EACH STATEMENT EXECUTE FUNCTION "whattodo"."reject_history_mutation"();

CREATE TABLE "whattodo"."ai_job_event" (
  "event_id" "whattodo"."ref" NOT NULL,
  "job_id" "whattodo"."ref" NOT NULL,
  "job_revision" "whattodo"."revision" NOT NULL,
  "sequence" "whattodo"."revision" NOT NULL,
  "status" "whattodo"."ref" NOT NULL,
  "exported_at" "whattodo"."instant",
  "observed_at" "whattodo"."instant" NOT NULL,
  "evaluator_ref" "whattodo"."ref" NOT NULL,
  "source_record_ref" "whattodo"."ref",
  CONSTRAINT "ai_job_event_pk_identity" PRIMARY KEY ("event_id"),
  CONSTRAINT "ai_job_event_uq_1" UNIQUE ("job_id", "job_revision", "sequence"),
  CONSTRAINT "ai_job_event_ck_status" CHECK (status IN ('PENDING','EXPORTED','RUNNING','RESULT_RECEIVED','VALIDATED','REJECTED','CANCELLED')),
  CONSTRAINT "ai_job_event_ck_export" CHECK ((status <> 'EXPORTED' OR exported_at IS NOT NULL) AND (status <> 'PENDING' OR exported_at IS NULL) AND (exported_at IS NULL OR exported_at <= observed_at))
);

CREATE TRIGGER "preserve_history" BEFORE UPDATE OR DELETE OR TRUNCATE ON "whattodo"."ai_job_event"
  FOR EACH STATEMENT EXECUTE FUNCTION "whattodo"."reject_history_mutation"();

ALTER TABLE "whattodo"."ai_job_revision" ADD CONSTRAINT "ai_job_revision_fk_1"
  FOREIGN KEY ("snapshot_ref") REFERENCES "whattodo"."planning_snapshot" ("snapshot_id")
  ON UPDATE NO ACTION ON DELETE NO ACTION DEFERRABLE INITIALLY DEFERRED;

ALTER TABLE "whattodo"."ai_result" ADD CONSTRAINT "ai_result_fk_1"
  FOREIGN KEY ("resolved_job_id", "resolved_job_revision", "context_hash", "snapshot_ref") REFERENCES "whattodo"."ai_job_revision" ("job_id", "revision", "context_hash", "snapshot_ref")
  ON UPDATE NO ACTION ON DELETE NO ACTION DEFERRABLE INITIALLY DEFERRED;

ALTER TABLE "whattodo"."ai_result" ADD CONSTRAINT "ai_result_fk_2"
  FOREIGN KEY ("raw_source_record_ref") REFERENCES "whattodo"."source_record" ("record_id")
  ON UPDATE NO ACTION ON DELETE NO ACTION DEFERRABLE INITIALLY DEFERRED;

ALTER TABLE "whattodo"."ai_import_record" ADD CONSTRAINT "ai_import_record_fk_1"
  FOREIGN KEY ("job_id", "result_id", "result_hash") REFERENCES "whattodo"."ai_result" ("job_id", "result_id", "content_hash")
  ON UPDATE NO ACTION ON DELETE NO ACTION DEFERRABLE INITIALLY DEFERRED;

ALTER TABLE "whattodo"."numeric_eligibility" ADD CONSTRAINT "numeric_eligibility_fk_1"
  FOREIGN KEY ("task_id", "task_revision") REFERENCES "whattodo"."task_revision" ("task_id", "revision")
  ON UPDATE NO ACTION ON DELETE NO ACTION DEFERRABLE INITIALLY DEFERRED;

ALTER TABLE "whattodo"."numeric_eligibility" ADD CONSTRAINT "numeric_eligibility_fk_2"
  FOREIGN KEY ("model_id", "model_version") REFERENCES "whattodo"."model_revision" ("model_id", "version")
  ON UPDATE NO ACTION ON DELETE NO ACTION DEFERRABLE INITIALLY DEFERRED;

ALTER TABLE "whattodo"."numeric_eligibility" ADD CONSTRAINT "numeric_eligibility_fk_3"
  FOREIGN KEY ("snapshot_ref") REFERENCES "whattodo"."planning_snapshot" ("snapshot_id")
  ON UPDATE NO ACTION ON DELETE NO ACTION DEFERRABLE INITIALLY DEFERRED;

ALTER TABLE "whattodo"."numeric_eligibility" ADD CONSTRAINT "numeric_eligibility_fk_4"
  FOREIGN KEY ("model_state_event_ref", "model_id", "model_version", "model_state") REFERENCES "whattodo"."model_lifecycle_event" ("event_id", "model_id", "model_version", "state")
  ON UPDATE NO ACTION ON DELETE NO ACTION DEFERRABLE INITIALLY DEFERRED;

ALTER TABLE "whattodo"."remaining_prediction" ADD CONSTRAINT "remaining_prediction_fk_1"
  FOREIGN KEY ("eligibility_ref", "task_id", "task_revision", "model_id", "model_version", "context_hash", "snapshot_ref") REFERENCES "whattodo"."numeric_eligibility" ("eligibility_ref", "task_id", "task_revision", "model_id", "model_version", "context_hash", "snapshot_ref")
  ON UPDATE NO ACTION ON DELETE NO ACTION DEFERRABLE INITIALLY DEFERRED;

ALTER TABLE "whattodo"."remaining_prediction" ADD CONSTRAINT "remaining_prediction_fk_2"
  FOREIGN KEY ("job_id", "job_revision", "result_id", "result_hash", "context_hash", "snapshot_ref", "output_contract_ref", "kind") REFERENCES "whattodo"."ai_result" ("job_id", "job_revision", "result_id", "content_hash", "context_hash", "snapshot_ref", "output_contract_ref", "kind")
  ON UPDATE NO ACTION ON DELETE NO ACTION DEFERRABLE INITIALLY DEFERRED;

ALTER TABLE "whattodo"."remaining_prediction" ADD CONSTRAINT "remaining_prediction_fk_3"
  FOREIGN KEY ("job_id", "job_revision", "context_hash", "snapshot_ref", "output_contract_ref", "kind") REFERENCES "whattodo"."ai_job_revision" ("job_id", "revision", "context_hash", "snapshot_ref", "output_contract_ref", "expected_kind")
  ON UPDATE NO ACTION ON DELETE NO ACTION DEFERRABLE INITIALLY DEFERRED;

ALTER TABLE "whattodo"."behavior_candidate" ADD CONSTRAINT "behavior_candidate_fk_1"
  FOREIGN KEY ("job_id", "result_id", "result_hash") REFERENCES "whattodo"."ai_result" ("job_id", "result_id", "content_hash")
  ON UPDATE NO ACTION ON DELETE NO ACTION DEFERRABLE INITIALLY DEFERRED;

ALTER TABLE "whattodo"."outbox_entry" ADD CONSTRAINT "outbox_entry_fk_1"
  FOREIGN KEY ("delivery_evidence_ref") REFERENCES "whattodo"."source_record" ("record_id")
  ON UPDATE NO ACTION ON DELETE NO ACTION DEFERRABLE INITIALLY DEFERRED;

ALTER TABLE "whattodo"."outbox_entry" ADD CONSTRAINT "outbox_entry_fk_2"
  FOREIGN KEY ("transaction_ref") REFERENCES "whattodo"."command_transaction" ("request_id")
  ON UPDATE NO ACTION ON DELETE NO ACTION DEFERRABLE INITIALLY DEFERRED;

ALTER TABLE "whattodo"."outbox_entry" ADD CONSTRAINT "outbox_entry_fk_3"
  FOREIGN KEY ("audit_change_ref", "aggregate_kind", "outbox_id", "revision", "transaction_ref") REFERENCES "whattodo"."audit_change" ("change_id", "aggregate_kind", "aggregate_id", "after_revision", "request_id")
  ON UPDATE NO ACTION ON DELETE NO ACTION DEFERRABLE INITIALLY DEFERRED;

ALTER TABLE "whattodo"."collector_checkpoint" ADD CONSTRAINT "collector_checkpoint_fk_1"
  FOREIGN KEY ("provider", "scope_ref") REFERENCES "whattodo"."source_scope" ("provider", "scope_ref")
  ON UPDATE NO ACTION ON DELETE NO ACTION DEFERRABLE INITIALLY DEFERRED;

ALTER TABLE "whattodo"."collector_checkpoint" ADD CONSTRAINT "collector_checkpoint_fk_2"
  FOREIGN KEY ("last_source_record_ref") REFERENCES "whattodo"."source_record" ("record_id")
  ON UPDATE NO ACTION ON DELETE NO ACTION DEFERRABLE INITIALLY DEFERRED;

ALTER TABLE "whattodo"."collector_checkpoint" ADD CONSTRAINT "collector_checkpoint_fk_3"
  FOREIGN KEY ("transaction_ref") REFERENCES "whattodo"."command_transaction" ("request_id")
  ON UPDATE NO ACTION ON DELETE NO ACTION DEFERRABLE INITIALLY DEFERRED;

ALTER TABLE "whattodo"."collector_checkpoint" ADD CONSTRAINT "collector_checkpoint_fk_4"
  FOREIGN KEY ("audit_change_ref", "aggregate_kind", "aggregate_key", "revision", "transaction_ref") REFERENCES "whattodo"."audit_change" ("change_id", "aggregate_kind", "aggregate_id", "after_revision", "request_id")
  ON UPDATE NO ACTION ON DELETE NO ACTION DEFERRABLE INITIALLY DEFERRED;

ALTER TABLE "whattodo"."model_lifecycle_event" ADD CONSTRAINT "model_lifecycle_event_fk_1"
  FOREIGN KEY ("model_id", "model_version") REFERENCES "whattodo"."model_revision" ("model_id", "version")
  ON UPDATE NO ACTION ON DELETE NO ACTION DEFERRABLE INITIALLY DEFERRED;

ALTER TABLE "whattodo"."ai_job_event" ADD CONSTRAINT "ai_job_event_fk_1"
  FOREIGN KEY ("job_id", "job_revision") REFERENCES "whattodo"."ai_job_revision" ("job_id", "revision")
  ON UPDATE NO ACTION ON DELETE NO ACTION DEFERRABLE INITIALLY DEFERRED;

ALTER TABLE "whattodo"."ai_job_event" ADD CONSTRAINT "ai_job_event_fk_2"
  FOREIGN KEY ("source_record_ref") REFERENCES "whattodo"."source_record" ("record_id")
  ON UPDATE NO ACTION ON DELETE NO ACTION DEFERRABLE INITIALLY DEFERRED;

REVOKE ALL ON ALL TABLES IN SCHEMA "whattodo" FROM PUBLIC;
COMMIT;
