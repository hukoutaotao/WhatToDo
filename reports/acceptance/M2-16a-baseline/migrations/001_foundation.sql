-- Generated draft 0.1.0: NOT release-frozen or application-migrated.
-- Review/freeze and run in an isolated database before activation.
BEGIN;
SET LOCAL search_path = pg_catalog;

CREATE SCHEMA "whattodo";
REVOKE ALL ON SCHEMA "whattodo" FROM PUBLIC;

CREATE DOMAIN "whattodo"."ref" AS text CHECK (VALUE ~ '[^[:space:]]');
CREATE DOMAIN "whattodo"."sha256" AS text CHECK (VALUE ~ '^[a-f0-9]{64}$');
CREATE DOMAIN "whattodo"."revision" AS bigint CHECK (VALUE > 0);
CREATE DOMAIN "whattodo"."measure" AS numeric CHECK (VALUE >= 0 AND VALUE::text NOT IN ('NaN','Infinity','-Infinity'));
CREATE DOMAIN "whattodo"."seconds" AS numeric CHECK (VALUE >= 0 AND VALUE = trunc(VALUE) AND VALUE::text NOT IN ('NaN','Infinity','-Infinity'));
CREATE DOMAIN "whattodo"."positive_integer" AS numeric CHECK (VALUE > 0 AND VALUE = trunc(VALUE) AND VALUE::text NOT IN ('NaN','Infinity','-Infinity'));
CREATE DOMAIN "whattodo"."json_object" AS jsonb CHECK (jsonb_typeof(VALUE) = 'object');
CREATE DOMAIN "whattodo"."instant" AS timestamptz CHECK (isfinite(VALUE));
CREATE DOMAIN "whattodo"."calendar_date" AS date CHECK (isfinite(VALUE));

CREATE FUNCTION "whattodo"."reject_history_mutation"() RETURNS trigger
LANGUAGE plpgsql SET search_path = pg_catalog AS $guard$
BEGIN
  RAISE EXCEPTION 'Historical rows cannot be updated, deleted or truncated' USING ERRCODE = '23514';
END;
$guard$;
REVOKE ALL ON FUNCTION "whattodo"."reject_history_mutation"() FROM PUBLIC;

CREATE TABLE "whattodo"."source_scope" (
  "provider" "whattodo"."ref" NOT NULL,
  "scope_ref" "whattodo"."ref" NOT NULL,
  "account_ref" "whattodo"."ref" NOT NULL,
  "registered_at" "whattodo"."instant" NOT NULL,
  CONSTRAINT "source_scope_pk_identity" PRIMARY KEY ("provider", "scope_ref")
);

CREATE TRIGGER "preserve_history" BEFORE UPDATE OR DELETE OR TRUNCATE ON "whattodo"."source_scope"
  FOR EACH STATEMENT EXECUTE FUNCTION "whattodo"."reject_history_mutation"();

CREATE TABLE "whattodo"."source_identity" (
  "source_id" "whattodo"."ref" NOT NULL,
  "provider" "whattodo"."ref" NOT NULL,
  "scope_ref" "whattodo"."ref" NOT NULL,
  "external_id" "whattodo"."ref" NOT NULL,
  "source_type" "whattodo"."ref" NOT NULL,
  CONSTRAINT "source_identity_pk_identity" PRIMARY KEY ("source_id"),
  CONSTRAINT "source_identity_uq_1" UNIQUE ("provider", "scope_ref", "external_id"),
  CONSTRAINT "source_identity_ck_source_type" CHECK (source_type IN ('USER','CALENDAR','EMAIL','LEARNING_PLATFORM','OTHER'))
);

CREATE TRIGGER "preserve_history" BEFORE UPDATE OR DELETE OR TRUNCATE ON "whattodo"."source_identity"
  FOR EACH STATEMENT EXECUTE FUNCTION "whattodo"."reject_history_mutation"();

CREATE TABLE "whattodo"."source_record" (
  "record_id" "whattodo"."ref" NOT NULL,
  "source_id" "whattodo"."ref" NOT NULL,
  "external_revision" "whattodo"."ref",
  "content_hash" "whattodo"."sha256" NOT NULL,
  "source_timestamp" "whattodo"."instant",
  "captured_at" "whattodo"."instant" NOT NULL,
  "state" "whattodo"."ref" NOT NULL,
  "deleted_at" "whattodo"."instant",
  "raw_content_ref" "whattodo"."ref" NOT NULL,
  CONSTRAINT "source_record_pk_identity" PRIMARY KEY ("record_id"),
  CONSTRAINT "source_record_uq_1" UNIQUE NULLS NOT DISTINCT ("source_id", "content_hash", "external_revision"),
  CONSTRAINT "source_record_ck_state" CHECK (state IN ('PRESENT','DELETED')),
  CONSTRAINT "source_record_ck_tombstone" CHECK ((state = 'PRESENT' AND deleted_at IS NULL) OR (state = 'DELETED' AND deleted_at IS NOT NULL AND deleted_at >= captured_at))
);

CREATE TRIGGER "preserve_history" BEFORE UPDATE OR DELETE OR TRUNCATE ON "whattodo"."source_record"
  FOR EACH STATEMENT EXECUTE FUNCTION "whattodo"."reject_history_mutation"();

CREATE TABLE "whattodo"."configuration_revision" (
  "configuration_ref" "whattodo"."ref" NOT NULL,
  "kind" "whattodo"."ref" NOT NULL,
  "id" "whattodo"."ref" NOT NULL,
  "version" "whattodo"."ref" NOT NULL,
  "content_hash" "whattodo"."sha256" NOT NULL,
  "git_revision" "whattodo"."ref" NOT NULL,
  "registered_at" "whattodo"."instant" NOT NULL,
  CONSTRAINT "configuration_revision_pk_identity" PRIMARY KEY ("configuration_ref"),
  CONSTRAINT "configuration_revision_uq_1" UNIQUE ("kind", "id", "version"),
  CONSTRAINT "configuration_revision_ck_kind" CHECK (kind IN ('COURSE_PROFILE','ACTIVITY_PROFILE','TASKTYPE','TASK_TEMPLATE','RELATIONSHIP_RULE','PREFERENCE'))
);

CREATE TRIGGER "preserve_history" BEFORE UPDATE OR DELETE OR TRUNCATE ON "whattodo"."configuration_revision"
  FOR EACH STATEMENT EXECUTE FUNCTION "whattodo"."reject_history_mutation"();

CREATE TABLE "whattodo"."authority_record" (
  "authority_ref" "whattodo"."ref" NOT NULL,
  "principal_id" "whattodo"."ref" NOT NULL,
  "origin" "whattodo"."ref" NOT NULL,
  "source_record_ref" "whattodo"."ref" NOT NULL,
  "resolved_scope_hash" "whattodo"."sha256" NOT NULL,
  "resolved_scope" "whattodo"."json_object" NOT NULL,
  "issued_at" "whattodo"."instant" NOT NULL,
  "expires_at" "whattodo"."instant",
  CONSTRAINT "authority_record_pk_identity" PRIMARY KEY ("authority_ref"),
  CONSTRAINT "authority_record_ck_origin" CHECK (origin IN ('USER_COMMAND','RELATIONSHIP_RULE','EXPIRATION_PROCESS')),
  CONSTRAINT "authority_record_ck_validity" CHECK (expires_at IS NULL OR expires_at > issued_at)
);

CREATE TRIGGER "preserve_history" BEFORE UPDATE OR DELETE OR TRUNCATE ON "whattodo"."authority_record"
  FOR EACH STATEMENT EXECUTE FUNCTION "whattodo"."reject_history_mutation"();

CREATE TABLE "whattodo"."command_transaction" (
  "request_id" "whattodo"."ref" NOT NULL,
  "request_hash" "whattodo"."sha256" NOT NULL,
  "principal_id" "whattodo"."ref" NOT NULL,
  "origin" "whattodo"."ref" NOT NULL,
  "authority_ref" "whattodo"."ref" NOT NULL,
  "expected_store_revision" "whattodo"."revision" NOT NULL,
  "committed_store_revision" "whattodo"."revision" NOT NULL,
  "audit_id" "whattodo"."ref" NOT NULL,
  "committed_at" "whattodo"."instant" NOT NULL,
  "receipt" "whattodo"."json_object" NOT NULL,
  CONSTRAINT "command_transaction_pk_identity" PRIMARY KEY ("request_id"),
  CONSTRAINT "command_transaction_uq_1" UNIQUE ("committed_store_revision"),
  CONSTRAINT "command_transaction_uq_2" UNIQUE ("audit_id"),
  CONSTRAINT "command_transaction_uq_3" UNIQUE ("request_id", "audit_id"),
  CONSTRAINT "command_transaction_uq_4" UNIQUE ("request_id", "committed_store_revision"),
  CONSTRAINT "command_transaction_ck_origin" CHECK (origin IN ('USER_COMMAND','RELATIONSHIP_RULE','EXPIRATION_PROCESS')),
  CONSTRAINT "command_transaction_ck_epoch" CHECK (committed_store_revision = expected_store_revision + 1)
);

CREATE TRIGGER "preserve_history" BEFORE UPDATE OR DELETE OR TRUNCATE ON "whattodo"."command_transaction"
  FOR EACH STATEMENT EXECUTE FUNCTION "whattodo"."reject_history_mutation"();

CREATE TABLE "whattodo"."audit_entry" (
  "audit_id" "whattodo"."ref" NOT NULL,
  "request_id" "whattodo"."ref" NOT NULL,
  "source_record_ref" "whattodo"."ref" NOT NULL,
  "correlation_ref" "whattodo"."ref" NOT NULL,
  "committed_at" "whattodo"."instant" NOT NULL,
  CONSTRAINT "audit_entry_pk_identity" PRIMARY KEY ("audit_id"),
  CONSTRAINT "audit_entry_uq_1" UNIQUE ("request_id"),
  CONSTRAINT "audit_entry_uq_2" UNIQUE ("request_id", "audit_id"),
  CONSTRAINT "audit_entry_uq_3" UNIQUE ("audit_id", "request_id")
);

CREATE TRIGGER "preserve_history" BEFORE UPDATE OR DELETE OR TRUNCATE ON "whattodo"."audit_entry"
  FOR EACH STATEMENT EXECUTE FUNCTION "whattodo"."reject_history_mutation"();

CREATE TABLE "whattodo"."audit_change" (
  "change_id" "whattodo"."ref" NOT NULL,
  "audit_id" "whattodo"."ref" NOT NULL,
  "aggregate_kind" "whattodo"."ref" NOT NULL,
  "aggregate_id" "whattodo"."ref" NOT NULL,
  "before_revision" "whattodo"."revision",
  "after_revision" "whattodo"."revision" NOT NULL,
  "before_value" "whattodo"."json_object",
  "after_value" "whattodo"."json_object" NOT NULL,
  "request_id" "whattodo"."ref" NOT NULL,
  CONSTRAINT "audit_change_pk_identity" PRIMARY KEY ("change_id"),
  CONSTRAINT "audit_change_uq_1" UNIQUE ("audit_id", "aggregate_kind", "aggregate_id", "after_revision"),
  CONSTRAINT "audit_change_uq_2" UNIQUE ("change_id", "aggregate_kind", "aggregate_id", "after_revision"),
  CONSTRAINT "audit_change_uq_3" UNIQUE ("change_id", "aggregate_kind", "aggregate_id", "after_revision", "request_id"),
  CONSTRAINT "audit_change_ck_revision_step" CHECK ((before_revision IS NULL AND after_revision = 1 AND before_value IS NULL) OR (before_revision IS NOT NULL AND after_revision = before_revision + 1 AND before_value IS NOT NULL))
);

CREATE TRIGGER "preserve_history" BEFORE UPDATE OR DELETE OR TRUNCATE ON "whattodo"."audit_change"
  FOR EACH STATEMENT EXECUTE FUNCTION "whattodo"."reject_history_mutation"();

CREATE TABLE "whattodo"."store_epoch" (
  "singleton" boolean NOT NULL,
  "revision" "whattodo"."revision" NOT NULL,
  "last_transaction_ref" "whattodo"."ref",
  CONSTRAINT "store_epoch_pk_identity" PRIMARY KEY ("singleton"),
  CONSTRAINT "store_epoch_ck_singleton" CHECK (singleton = TRUE),
  CONSTRAINT "store_epoch_ck_bootstrap" CHECK ((revision = 1 AND last_transaction_ref IS NULL) OR (revision > 1 AND last_transaction_ref IS NOT NULL))
);

CREATE FUNCTION "whattodo"."guard_store_epoch"() RETURNS trigger
LANGUAGE plpgsql SET search_path = pg_catalog AS $guard$
BEGIN
  IF NEW."singleton" IS DISTINCT FROM OLD."singleton" OR
     NEW."revision" IS DISTINCT FROM OLD."revision" + 1 THEN
    RAISE EXCEPTION 'Mutable head identity, version or terminal-state mismatch' USING ERRCODE = '23514';
  END IF;
  RETURN NEW;
END;
$guard$;
REVOKE ALL ON FUNCTION "whattodo"."guard_store_epoch"() FROM PUBLIC;
CREATE TRIGGER "guard_version" BEFORE UPDATE ON "whattodo"."store_epoch" FOR EACH ROW EXECUTE FUNCTION "whattodo"."guard_store_epoch"();
CREATE TRIGGER "preserve_row" BEFORE DELETE OR TRUNCATE ON "whattodo"."store_epoch" FOR EACH STATEMENT EXECUTE FUNCTION "whattodo"."reject_history_mutation"();

CREATE TABLE "whattodo"."schema_migration" (
  "migration_id" "whattodo"."ref" NOT NULL,
  "content_hash" "whattodo"."sha256" NOT NULL,
  "design_version" "whattodo"."ref" NOT NULL,
  "applied_at" "whattodo"."instant" NOT NULL,
  CONSTRAINT "schema_migration_pk_identity" PRIMARY KEY ("migration_id")
);

CREATE TRIGGER "preserve_history" BEFORE UPDATE OR DELETE OR TRUNCATE ON "whattodo"."schema_migration"
  FOR EACH STATEMENT EXECUTE FUNCTION "whattodo"."reject_history_mutation"();

CREATE TABLE "whattodo"."source_lifecycle_event" (
  "event_id" "whattodo"."ref" NOT NULL,
  "record_id" "whattodo"."ref" NOT NULL,
  "sequence" "whattodo"."revision" NOT NULL,
  "state" "whattodo"."ref" NOT NULL,
  "observed_at" "whattodo"."instant" NOT NULL,
  "source_evidence_ref" "whattodo"."ref" NOT NULL,
  CONSTRAINT "source_lifecycle_event_pk_identity" PRIMARY KEY ("event_id"),
  CONSTRAINT "source_lifecycle_event_uq_1" UNIQUE ("record_id", "sequence"),
  CONSTRAINT "source_lifecycle_event_ck_state" CHECK (state IN ('PRESENT','DELETED'))
);

CREATE TRIGGER "preserve_history" BEFORE UPDATE OR DELETE OR TRUNCATE ON "whattodo"."source_lifecycle_event"
  FOR EACH STATEMENT EXECUTE FUNCTION "whattodo"."reject_history_mutation"();

ALTER TABLE "whattodo"."source_identity" ADD CONSTRAINT "source_identity_fk_1"
  FOREIGN KEY ("provider", "scope_ref") REFERENCES "whattodo"."source_scope" ("provider", "scope_ref")
  ON UPDATE NO ACTION ON DELETE NO ACTION DEFERRABLE INITIALLY DEFERRED;

ALTER TABLE "whattodo"."source_record" ADD CONSTRAINT "source_record_fk_1"
  FOREIGN KEY ("source_id") REFERENCES "whattodo"."source_identity" ("source_id")
  ON UPDATE NO ACTION ON DELETE NO ACTION DEFERRABLE INITIALLY DEFERRED;

ALTER TABLE "whattodo"."authority_record" ADD CONSTRAINT "authority_record_fk_1"
  FOREIGN KEY ("source_record_ref") REFERENCES "whattodo"."source_record" ("record_id")
  ON UPDATE NO ACTION ON DELETE NO ACTION DEFERRABLE INITIALLY DEFERRED;

ALTER TABLE "whattodo"."command_transaction" ADD CONSTRAINT "command_transaction_fk_1"
  FOREIGN KEY ("authority_ref") REFERENCES "whattodo"."authority_record" ("authority_ref")
  ON UPDATE NO ACTION ON DELETE NO ACTION DEFERRABLE INITIALLY DEFERRED;

ALTER TABLE "whattodo"."command_transaction" ADD CONSTRAINT "command_transaction_fk_2"
  FOREIGN KEY ("request_id", "audit_id") REFERENCES "whattodo"."audit_entry" ("request_id", "audit_id")
  ON UPDATE NO ACTION ON DELETE NO ACTION DEFERRABLE INITIALLY DEFERRED;

ALTER TABLE "whattodo"."audit_entry" ADD CONSTRAINT "audit_entry_fk_1"
  FOREIGN KEY ("request_id", "audit_id") REFERENCES "whattodo"."command_transaction" ("request_id", "audit_id")
  ON UPDATE NO ACTION ON DELETE NO ACTION DEFERRABLE INITIALLY DEFERRED;

ALTER TABLE "whattodo"."audit_entry" ADD CONSTRAINT "audit_entry_fk_2"
  FOREIGN KEY ("source_record_ref") REFERENCES "whattodo"."source_record" ("record_id")
  ON UPDATE NO ACTION ON DELETE NO ACTION DEFERRABLE INITIALLY DEFERRED;

ALTER TABLE "whattodo"."audit_change" ADD CONSTRAINT "audit_change_fk_1"
  FOREIGN KEY ("audit_id") REFERENCES "whattodo"."audit_entry" ("audit_id")
  ON UPDATE NO ACTION ON DELETE NO ACTION DEFERRABLE INITIALLY DEFERRED;

ALTER TABLE "whattodo"."audit_change" ADD CONSTRAINT "audit_change_fk_2"
  FOREIGN KEY ("audit_id", "request_id") REFERENCES "whattodo"."audit_entry" ("audit_id", "request_id")
  ON UPDATE NO ACTION ON DELETE NO ACTION DEFERRABLE INITIALLY DEFERRED;

ALTER TABLE "whattodo"."store_epoch" ADD CONSTRAINT "store_epoch_fk_1"
  FOREIGN KEY ("last_transaction_ref", "revision") REFERENCES "whattodo"."command_transaction" ("request_id", "committed_store_revision")
  ON UPDATE NO ACTION ON DELETE NO ACTION DEFERRABLE INITIALLY DEFERRED;

ALTER TABLE "whattodo"."source_lifecycle_event" ADD CONSTRAINT "source_lifecycle_event_fk_1"
  FOREIGN KEY ("record_id") REFERENCES "whattodo"."source_record" ("record_id")
  ON UPDATE NO ACTION ON DELETE NO ACTION DEFERRABLE INITIALLY DEFERRED;

ALTER TABLE "whattodo"."source_lifecycle_event" ADD CONSTRAINT "source_lifecycle_event_fk_2"
  FOREIGN KEY ("source_evidence_ref") REFERENCES "whattodo"."source_record" ("record_id")
  ON UPDATE NO ACTION ON DELETE NO ACTION DEFERRABLE INITIALLY DEFERRED;

INSERT INTO "whattodo"."store_epoch" ("singleton", "revision", "last_transaction_ref") VALUES (TRUE, 1, NULL);

REVOKE ALL ON ALL TABLES IN SCHEMA "whattodo" FROM PUBLIC;
COMMIT;
