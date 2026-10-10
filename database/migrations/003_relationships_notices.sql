-- Generated draft 0.1.0: NOT release-frozen or application-migrated.
-- Review/freeze and run in an isolated database before activation.
BEGIN;
SET LOCAL search_path = pg_catalog;

CREATE TABLE "whattodo"."relationship_rule_revision" (
  "rule_id" "whattodo"."ref" NOT NULL,
  "version" "whattodo"."ref" NOT NULL,
  "active" boolean NOT NULL,
  "acceptance_ref" "whattodo"."ref",
  "configuration_ref" "whattodo"."ref" NOT NULL,
  "trigger_kind" "whattodo"."ref" NOT NULL,
  "source_type_ref" "whattodo"."ref" NOT NULL,
  "target_type_ref" "whattodo"."ref" NOT NULL,
  "template_ref" "whattodo"."ref" NOT NULL,
  "template_version" "whattodo"."ref" NOT NULL,
  "target_role" "whattodo"."ref" NOT NULL,
  "obligation_kind" "whattodo"."ref" NOT NULL,
  "mappings" "whattodo"."json_object" NOT NULL,
  CONSTRAINT "relationship_rule_revision_pk_identity" PRIMARY KEY ("rule_id", "version"),
  CONSTRAINT "relationship_rule_revision_uq_1" UNIQUE ("rule_id", "version", "target_role"),
  CONSTRAINT "relationship_rule_revision_ck_accepted_active" CHECK (active = FALSE OR acceptance_ref IS NOT NULL),
  CONSTRAINT "relationship_rule_revision_ck_trigger" CHECK (trigger_kind = 'CANONICAL_CREATION'),
  CONSTRAINT "relationship_rule_revision_ck_obligation" CHECK (obligation_kind IN ('SEPARATE_TASK','STAGE'))
);

CREATE TRIGGER "preserve_history" BEFORE UPDATE OR DELETE OR TRUNCATE ON "whattodo"."relationship_rule_revision"
  FOR EACH STATEMENT EXECUTE FUNCTION "whattodo"."reject_history_mutation"();

CREATE TABLE "whattodo"."generation_occurrence" (
  "generation_key" "whattodo"."ref" NOT NULL,
  "rule_id" "whattodo"."ref" NOT NULL,
  "rule_version" "whattodo"."ref" NOT NULL,
  "source_task_id" "whattodo"."ref" NOT NULL,
  "source_task_revision" "whattodo"."revision" NOT NULL,
  "creation_transaction_ref" "whattodo"."ref" NOT NULL,
  "occurrence_key" "whattodo"."ref" NOT NULL,
  "target_role" "whattodo"."ref" NOT NULL,
  "obligation_kind" "whattodo"."ref" NOT NULL,
  "state" "whattodo"."ref" NOT NULL,
  "target_task_ref" "whattodo"."ref",
  "target_stage_ref" "whattodo"."ref",
  "target_stage_revision" "whattodo"."revision",
  "failure_code" "whattodo"."ref",
  "missing_facts" "whattodo"."json_object" NOT NULL,
  "revision" "whattodo"."revision" NOT NULL,
  "transaction_ref" "whattodo"."ref" NOT NULL,
  "audit_change_ref" "whattodo"."ref" NOT NULL,
  "aggregate_kind" "whattodo"."ref" NOT NULL,
  CONSTRAINT "generation_occurrence_pk_identity" PRIMARY KEY ("generation_key"),
  CONSTRAINT "generation_occurrence_uq_1" UNIQUE ("rule_id", "source_task_id", "occurrence_key", "target_role"),
  CONSTRAINT "generation_occurrence_ck_obligation" CHECK (obligation_kind IN ('SEPARATE_TASK','STAGE')),
  CONSTRAINT "generation_occurrence_ck_state" CHECK (state IN ('PENDING','CREATED','FAILED')),
  CONSTRAINT "generation_occurrence_ck_created_target" CHECK ((state = 'CREATED' AND ((obligation_kind = 'SEPARATE_TASK' AND target_task_ref IS NOT NULL AND target_stage_ref IS NULL AND target_stage_revision IS NULL) OR (obligation_kind = 'STAGE' AND target_task_ref IS NULL AND target_stage_ref IS NOT NULL AND target_stage_revision IS NOT NULL))) OR (state <> 'CREATED' AND target_task_ref IS NULL AND target_stage_ref IS NULL AND target_stage_revision IS NULL)),
  CONSTRAINT "generation_occurrence_ck_failure" CHECK ((state = 'FAILED' AND failure_code IS NOT NULL) OR (state <> 'FAILED' AND failure_code IS NULL)),
  CONSTRAINT "generation_occurrence_ck_audit_kind" CHECK (aggregate_kind = 'GENERATION_OCCURRENCE')
);

CREATE FUNCTION "whattodo"."guard_generation_occurrence"() RETURNS trigger
LANGUAGE plpgsql SET search_path = pg_catalog AS $guard$
BEGIN
  IF NEW."generation_key" IS DISTINCT FROM OLD."generation_key" OR
     NEW."rule_id" IS DISTINCT FROM OLD."rule_id" OR
     NEW."rule_version" IS DISTINCT FROM OLD."rule_version" OR
     NEW."source_task_id" IS DISTINCT FROM OLD."source_task_id" OR
     NEW."source_task_revision" IS DISTINCT FROM OLD."source_task_revision" OR
     NEW."creation_transaction_ref" IS DISTINCT FROM OLD."creation_transaction_ref" OR
     NEW."occurrence_key" IS DISTINCT FROM OLD."occurrence_key" OR
     NEW."target_role" IS DISTINCT FROM OLD."target_role" OR
     NEW."obligation_kind" IS DISTINCT FROM OLD."obligation_kind" OR
     NEW."revision" IS DISTINCT FROM OLD."revision" + 1 OR
     NEW."transaction_ref" IS NOT DISTINCT FROM OLD."transaction_ref" OR
     (OLD.state <> 'CREATED' OR (NEW.state = 'CREATED' AND NEW.target_task_ref IS NOT DISTINCT FROM OLD.target_task_ref AND NEW.target_stage_ref IS NOT DISTINCT FROM OLD.target_stage_ref AND NEW.target_stage_revision IS NOT DISTINCT FROM OLD.target_stage_revision)) IS NOT TRUE THEN
    RAISE EXCEPTION 'Mutable head identity, version or terminal-state mismatch' USING ERRCODE = '23514';
  END IF;
  RETURN NEW;
END;
$guard$;
REVOKE ALL ON FUNCTION "whattodo"."guard_generation_occurrence"() FROM PUBLIC;
CREATE TRIGGER "guard_version" BEFORE UPDATE ON "whattodo"."generation_occurrence" FOR EACH ROW EXECUTE FUNCTION "whattodo"."guard_generation_occurrence"();
CREATE TRIGGER "preserve_row" BEFORE DELETE OR TRUNCATE ON "whattodo"."generation_occurrence" FOR EACH STATEMENT EXECUTE FUNCTION "whattodo"."reject_history_mutation"();

CREATE TABLE "whattodo"."task_relation_revision" (
  "relation_id" "whattodo"."ref" NOT NULL,
  "revision" "whattodo"."revision" NOT NULL,
  "kind" "whattodo"."ref" NOT NULL,
  "before_kind" "whattodo"."ref" NOT NULL,
  "before_task_id" "whattodo"."ref" NOT NULL,
  "before_task_revision" "whattodo"."revision" NOT NULL,
  "before_stage_id" "whattodo"."ref",
  "before_stage_revision" "whattodo"."revision",
  "after_kind" "whattodo"."ref" NOT NULL,
  "after_task_id" "whattodo"."ref" NOT NULL,
  "after_task_revision" "whattodo"."revision" NOT NULL,
  "after_stage_id" "whattodo"."ref",
  "after_stage_revision" "whattodo"."revision",
  "acceptance_ref" "whattodo"."ref" NOT NULL,
  "transaction_ref" "whattodo"."ref" NOT NULL,
  CONSTRAINT "task_relation_revision_pk_identity" PRIMARY KEY ("relation_id", "revision"),
  CONSTRAINT "task_relation_revision_ck_kind" CHECK (kind IN ('COMPLETION_ORDER','START_PREREQUISITE','SOFT_SEQUENCE','STAGE_MEMBERSHIP')),
  CONSTRAINT "task_relation_revision_ck_before_endpoint" CHECK ((before_kind = 'TASK' AND before_stage_id IS NULL AND before_stage_revision IS NULL) OR (before_kind = 'STAGE' AND before_stage_id IS NOT NULL AND before_stage_revision IS NOT NULL)),
  CONSTRAINT "task_relation_revision_ck_after_endpoint" CHECK ((after_kind = 'TASK' AND after_stage_id IS NULL AND after_stage_revision IS NULL) OR (after_kind = 'STAGE' AND after_stage_id IS NOT NULL AND after_stage_revision IS NOT NULL))
);

CREATE TRIGGER "preserve_history" BEFORE UPDATE OR DELETE OR TRUNCATE ON "whattodo"."task_relation_revision"
  FOR EACH STATEMENT EXECUTE FUNCTION "whattodo"."reject_history_mutation"();

CREATE TABLE "whattodo"."expiration_notice" (
  "notice_id" "whattodo"."ref" NOT NULL,
  "task_id" "whattodo"."ref" NOT NULL,
  "task_revision" "whattodo"."revision" NOT NULL,
  "condition_ref" "whattodo"."ref" NOT NULL,
  "condition_evidence_ref" "whattodo"."ref" NOT NULL,
  "detected_at" "whattodo"."instant" NOT NULL,
  "transaction_ref" "whattodo"."ref" NOT NULL,
  CONSTRAINT "expiration_notice_pk_identity" PRIMARY KEY ("notice_id"),
  CONSTRAINT "expiration_notice_uq_1" UNIQUE ("task_id", "task_revision", "condition_ref"),
  CONSTRAINT "expiration_notice_uq_2" UNIQUE ("notice_id", "task_id", "task_revision", "condition_ref")
);

CREATE TRIGGER "preserve_history" BEFORE UPDATE OR DELETE OR TRUNCATE ON "whattodo"."expiration_notice"
  FOR EACH STATEMENT EXECUTE FUNCTION "whattodo"."reject_history_mutation"();

CREATE TABLE "whattodo"."dispatch_attempt" (
  "notice_id" "whattodo"."ref" NOT NULL,
  "attempt_id" "whattodo"."ref" NOT NULL,
  "channel_ref" "whattodo"."ref" NOT NULL,
  "content_ref" "whattodo"."ref" NOT NULL,
  "correlation_ref" "whattodo"."ref",
  "started_at" "whattodo"."instant" NOT NULL,
  "transaction_ref" "whattodo"."ref" NOT NULL,
  CONSTRAINT "dispatch_attempt_pk_identity" PRIMARY KEY ("notice_id", "attempt_id"),
  CONSTRAINT "dispatch_attempt_uq_1" UNIQUE ("notice_id", "attempt_id", "started_at")
);

CREATE TRIGGER "preserve_history" BEFORE UPDATE OR DELETE OR TRUNCATE ON "whattodo"."dispatch_attempt"
  FOR EACH STATEMENT EXECUTE FUNCTION "whattodo"."reject_history_mutation"();

CREATE TABLE "whattodo"."dispatch_result" (
  "result_id" "whattodo"."ref" NOT NULL,
  "notice_id" "whattodo"."ref" NOT NULL,
  "attempt_id" "whattodo"."ref" NOT NULL,
  "started_at" "whattodo"."instant" NOT NULL,
  "state" "whattodo"."ref" NOT NULL,
  "finished_at" "whattodo"."instant" NOT NULL,
  "delivered_at" "whattodo"."instant",
  "evidence_ref" "whattodo"."ref" NOT NULL,
  "correlation_ref" "whattodo"."ref",
  "content_hash" "whattodo"."sha256" NOT NULL,
  CONSTRAINT "dispatch_result_pk_identity" PRIMARY KEY ("result_id"),
  CONSTRAINT "dispatch_result_uq_1" UNIQUE ("notice_id", "attempt_id", "content_hash"),
  CONSTRAINT "dispatch_result_ck_state" CHECK (state IN ('DELIVERED','FAILED','UNKNOWN')),
  CONSTRAINT "dispatch_result_ck_chronology" CHECK (finished_at >= started_at),
  CONSTRAINT "dispatch_result_ck_delivery" CHECK ((state = 'DELIVERED' AND delivered_at IS NOT NULL AND delivered_at >= started_at AND delivered_at <= finished_at) OR (state IN ('FAILED','UNKNOWN') AND delivered_at IS NULL))
);

CREATE TRIGGER "preserve_history" BEFORE UPDATE OR DELETE OR TRUNCATE ON "whattodo"."dispatch_result"
  FOR EACH STATEMENT EXECUTE FUNCTION "whattodo"."reject_history_mutation"();

ALTER TABLE "whattodo"."task_revision" ADD CONSTRAINT "task_revision_fk_5"
  FOREIGN KEY ("expiration_notice_ref", "task_id", "notice_task_revision", "expiration_condition_ref") REFERENCES "whattodo"."expiration_notice" ("notice_id", "task_id", "task_revision", "condition_ref")
  ON UPDATE NO ACTION ON DELETE NO ACTION DEFERRABLE INITIALLY DEFERRED;

ALTER TABLE "whattodo"."relationship_rule_revision" ADD CONSTRAINT "relationship_rule_revision_fk_1"
  FOREIGN KEY ("configuration_ref") REFERENCES "whattodo"."configuration_revision" ("configuration_ref")
  ON UPDATE NO ACTION ON DELETE NO ACTION DEFERRABLE INITIALLY DEFERRED;

ALTER TABLE "whattodo"."relationship_rule_revision" ADD CONSTRAINT "relationship_rule_revision_fk_2"
  FOREIGN KEY ("source_type_ref") REFERENCES "whattodo"."configuration_revision" ("configuration_ref")
  ON UPDATE NO ACTION ON DELETE NO ACTION DEFERRABLE INITIALLY DEFERRED;

ALTER TABLE "whattodo"."relationship_rule_revision" ADD CONSTRAINT "relationship_rule_revision_fk_3"
  FOREIGN KEY ("target_type_ref") REFERENCES "whattodo"."configuration_revision" ("configuration_ref")
  ON UPDATE NO ACTION ON DELETE NO ACTION DEFERRABLE INITIALLY DEFERRED;

ALTER TABLE "whattodo"."relationship_rule_revision" ADD CONSTRAINT "relationship_rule_revision_fk_4"
  FOREIGN KEY ("template_ref") REFERENCES "whattodo"."configuration_revision" ("configuration_ref")
  ON UPDATE NO ACTION ON DELETE NO ACTION DEFERRABLE INITIALLY DEFERRED;

ALTER TABLE "whattodo"."relationship_rule_revision" ADD CONSTRAINT "relationship_rule_revision_fk_5"
  FOREIGN KEY ("acceptance_ref") REFERENCES "whattodo"."authority_record" ("authority_ref")
  ON UPDATE NO ACTION ON DELETE NO ACTION DEFERRABLE INITIALLY DEFERRED;

ALTER TABLE "whattodo"."generation_occurrence" ADD CONSTRAINT "generation_occurrence_fk_1"
  FOREIGN KEY ("rule_id", "rule_version", "target_role") REFERENCES "whattodo"."relationship_rule_revision" ("rule_id", "version", "target_role")
  ON UPDATE NO ACTION ON DELETE NO ACTION DEFERRABLE INITIALLY DEFERRED;

ALTER TABLE "whattodo"."generation_occurrence" ADD CONSTRAINT "generation_occurrence_fk_2"
  FOREIGN KEY ("source_task_id", "source_task_revision") REFERENCES "whattodo"."task_revision" ("task_id", "revision")
  ON UPDATE NO ACTION ON DELETE NO ACTION DEFERRABLE INITIALLY DEFERRED;

ALTER TABLE "whattodo"."generation_occurrence" ADD CONSTRAINT "generation_occurrence_fk_3"
  FOREIGN KEY ("creation_transaction_ref") REFERENCES "whattodo"."command_transaction" ("request_id")
  ON UPDATE NO ACTION ON DELETE NO ACTION DEFERRABLE INITIALLY DEFERRED;

ALTER TABLE "whattodo"."generation_occurrence" ADD CONSTRAINT "generation_occurrence_fk_4"
  FOREIGN KEY ("target_task_ref") REFERENCES "whattodo"."task_identity" ("task_id")
  ON UPDATE NO ACTION ON DELETE NO ACTION DEFERRABLE INITIALLY DEFERRED;

ALTER TABLE "whattodo"."generation_occurrence" ADD CONSTRAINT "generation_occurrence_fk_5"
  FOREIGN KEY ("target_stage_ref", "target_stage_revision") REFERENCES "whattodo"."stage_revision" ("stage_id", "revision")
  ON UPDATE NO ACTION ON DELETE NO ACTION DEFERRABLE INITIALLY DEFERRED;

ALTER TABLE "whattodo"."generation_occurrence" ADD CONSTRAINT "generation_occurrence_fk_6"
  FOREIGN KEY ("transaction_ref") REFERENCES "whattodo"."command_transaction" ("request_id")
  ON UPDATE NO ACTION ON DELETE NO ACTION DEFERRABLE INITIALLY DEFERRED;

ALTER TABLE "whattodo"."generation_occurrence" ADD CONSTRAINT "generation_occurrence_fk_7"
  FOREIGN KEY ("audit_change_ref", "aggregate_kind", "generation_key", "revision", "transaction_ref") REFERENCES "whattodo"."audit_change" ("change_id", "aggregate_kind", "aggregate_id", "after_revision", "request_id")
  ON UPDATE NO ACTION ON DELETE NO ACTION DEFERRABLE INITIALLY DEFERRED;

ALTER TABLE "whattodo"."task_relation_revision" ADD CONSTRAINT "task_relation_revision_fk_1"
  FOREIGN KEY ("before_task_id", "before_task_revision") REFERENCES "whattodo"."task_revision" ("task_id", "revision")
  ON UPDATE NO ACTION ON DELETE NO ACTION DEFERRABLE INITIALLY DEFERRED;

ALTER TABLE "whattodo"."task_relation_revision" ADD CONSTRAINT "task_relation_revision_fk_2"
  FOREIGN KEY ("before_stage_id", "before_stage_revision", "before_task_id") REFERENCES "whattodo"."stage_revision" ("stage_id", "revision", "task_id")
  ON UPDATE NO ACTION ON DELETE NO ACTION DEFERRABLE INITIALLY DEFERRED;

ALTER TABLE "whattodo"."task_relation_revision" ADD CONSTRAINT "task_relation_revision_fk_3"
  FOREIGN KEY ("after_task_id", "after_task_revision") REFERENCES "whattodo"."task_revision" ("task_id", "revision")
  ON UPDATE NO ACTION ON DELETE NO ACTION DEFERRABLE INITIALLY DEFERRED;

ALTER TABLE "whattodo"."task_relation_revision" ADD CONSTRAINT "task_relation_revision_fk_4"
  FOREIGN KEY ("after_stage_id", "after_stage_revision", "after_task_id") REFERENCES "whattodo"."stage_revision" ("stage_id", "revision", "task_id")
  ON UPDATE NO ACTION ON DELETE NO ACTION DEFERRABLE INITIALLY DEFERRED;

ALTER TABLE "whattodo"."task_relation_revision" ADD CONSTRAINT "task_relation_revision_fk_5"
  FOREIGN KEY ("acceptance_ref") REFERENCES "whattodo"."authority_record" ("authority_ref")
  ON UPDATE NO ACTION ON DELETE NO ACTION DEFERRABLE INITIALLY DEFERRED;

ALTER TABLE "whattodo"."task_relation_revision" ADD CONSTRAINT "task_relation_revision_fk_6"
  FOREIGN KEY ("transaction_ref") REFERENCES "whattodo"."command_transaction" ("request_id")
  ON UPDATE NO ACTION ON DELETE NO ACTION DEFERRABLE INITIALLY DEFERRED;

ALTER TABLE "whattodo"."expiration_notice" ADD CONSTRAINT "expiration_notice_fk_1"
  FOREIGN KEY ("task_id", "task_revision", "condition_ref") REFERENCES "whattodo"."task_revision" ("task_id", "revision", "expiration_condition_ref")
  ON UPDATE NO ACTION ON DELETE NO ACTION DEFERRABLE INITIALLY DEFERRED;

ALTER TABLE "whattodo"."expiration_notice" ADD CONSTRAINT "expiration_notice_fk_2"
  FOREIGN KEY ("condition_evidence_ref") REFERENCES "whattodo"."source_record" ("record_id")
  ON UPDATE NO ACTION ON DELETE NO ACTION DEFERRABLE INITIALLY DEFERRED;

ALTER TABLE "whattodo"."expiration_notice" ADD CONSTRAINT "expiration_notice_fk_3"
  FOREIGN KEY ("transaction_ref") REFERENCES "whattodo"."command_transaction" ("request_id")
  ON UPDATE NO ACTION ON DELETE NO ACTION DEFERRABLE INITIALLY DEFERRED;

ALTER TABLE "whattodo"."dispatch_attempt" ADD CONSTRAINT "dispatch_attempt_fk_1"
  FOREIGN KEY ("notice_id") REFERENCES "whattodo"."expiration_notice" ("notice_id")
  ON UPDATE NO ACTION ON DELETE NO ACTION DEFERRABLE INITIALLY DEFERRED;

ALTER TABLE "whattodo"."dispatch_attempt" ADD CONSTRAINT "dispatch_attempt_fk_2"
  FOREIGN KEY ("transaction_ref") REFERENCES "whattodo"."command_transaction" ("request_id")
  ON UPDATE NO ACTION ON DELETE NO ACTION DEFERRABLE INITIALLY DEFERRED;

ALTER TABLE "whattodo"."dispatch_result" ADD CONSTRAINT "dispatch_result_fk_1"
  FOREIGN KEY ("notice_id", "attempt_id", "started_at") REFERENCES "whattodo"."dispatch_attempt" ("notice_id", "attempt_id", "started_at")
  ON UPDATE NO ACTION ON DELETE NO ACTION DEFERRABLE INITIALLY DEFERRED;

ALTER TABLE "whattodo"."dispatch_result" ADD CONSTRAINT "dispatch_result_fk_2"
  FOREIGN KEY ("evidence_ref") REFERENCES "whattodo"."source_record" ("record_id")
  ON UPDATE NO ACTION ON DELETE NO ACTION DEFERRABLE INITIALLY DEFERRED;

CREATE UNIQUE INDEX "dispatch_terminal_once" ON "whattodo"."dispatch_result" ("notice_id", "attempt_id") WHERE state IN ('DELIVERED','FAILED');

REVOKE ALL ON ALL TABLES IN SCHEMA "whattodo" FROM PUBLIC;
COMMIT;
