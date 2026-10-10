-- Generated draft 0.1.0: NOT release-frozen or application-migrated.
-- Review/freeze and run in an isolated database before activation.
BEGIN;
SET LOCAL search_path = pg_catalog;

CREATE TABLE "whattodo"."goal_revision" (
  "goal_id" "whattodo"."ref" NOT NULL,
  "revision" "whattodo"."revision" NOT NULL,
  "title" "whattodo"."ref" NOT NULL,
  "acceptance" "whattodo"."ref" NOT NULL,
  "acceptance_ref" "whattodo"."ref",
  "target_description" "whattodo"."ref",
  "target_amount" "whattodo"."measure",
  "target_unit" "whattodo"."ref",
  "total_workload" "whattodo"."measure",
  "workload_unit" "whattodo"."ref",
  "progress_measure_kind" "whattodo"."ref",
  "progress_unit" "whattodo"."ref",
  "target_due_known" boolean NOT NULL,
  "due_ref" "whattodo"."ref",
  "cadence" "whattodo"."json_object",
  "phases" "whattodo"."json_object",
  "generation_rule_refs" "whattodo"."json_object",
  "transaction_ref" "whattodo"."ref" NOT NULL,
  CONSTRAINT "goal_revision_pk_identity" PRIMARY KEY ("goal_id", "revision"),
  CONSTRAINT "goal_revision_ck_acceptance" CHECK ((acceptance = 'DRAFT' AND acceptance_ref IS NULL) OR (acceptance = 'ACCEPTED' AND acceptance_ref IS NOT NULL)),
  CONSTRAINT "goal_revision_ck_target_pair" CHECK ((target_amount IS NULL AND target_unit IS NULL) OR (target_amount IS NOT NULL AND target_unit IS NOT NULL)),
  CONSTRAINT "goal_revision_ck_workload_pair" CHECK ((total_workload IS NULL AND workload_unit IS NULL) OR (total_workload IS NOT NULL AND workload_unit IS NOT NULL)),
  CONSTRAINT "goal_revision_ck_progress_measure" CHECK ((progress_measure_kind IS NULL AND progress_unit IS NULL) OR (progress_measure_kind = 'CONFIRMED_OUTCOME' AND progress_unit IS NULL) OR (progress_measure_kind = 'QUANTITY' AND progress_unit IS NOT NULL)),
  CONSTRAINT "goal_revision_ck_known_due" CHECK (target_due_known = TRUE OR due_ref IS NULL)
);

CREATE TRIGGER "preserve_history" BEFORE UPDATE OR DELETE OR TRUNCATE ON "whattodo"."goal_revision"
  FOR EACH STATEMENT EXECUTE FUNCTION "whattodo"."reject_history_mutation"();

CREATE TABLE "whattodo"."goal_progress" (
  "progress_id" "whattodo"."ref" NOT NULL,
  "goal_id" "whattodo"."ref" NOT NULL,
  "goal_revision" "whattodo"."revision" NOT NULL,
  "amount" "whattodo"."measure",
  "unit" "whattodo"."ref",
  "completion" "whattodo"."ref" NOT NULL,
  "observed_at" "whattodo"."instant" NOT NULL,
  "source_record_ref" "whattodo"."ref" NOT NULL,
  "authority_ref" "whattodo"."ref" NOT NULL,
  "transaction_ref" "whattodo"."ref" NOT NULL,
  CONSTRAINT "goal_progress_pk_identity" PRIMARY KEY ("progress_id"),
  CONSTRAINT "goal_progress_ck_measure_pair" CHECK ((amount IS NULL AND unit IS NULL) OR (amount IS NOT NULL AND unit IS NOT NULL)),
  CONSTRAINT "goal_progress_ck_completion" CHECK (completion IN ('INCOMPLETE','COMPLETE'))
);

CREATE TRIGGER "preserve_history" BEFORE UPDATE OR DELETE OR TRUNCATE ON "whattodo"."goal_progress"
  FOR EACH STATEMENT EXECUTE FUNCTION "whattodo"."reject_history_mutation"();

CREATE TABLE "whattodo"."milestone_revision" (
  "milestone_id" "whattodo"."ref" NOT NULL,
  "revision" "whattodo"."revision" NOT NULL,
  "goal_id" "whattodo"."ref" NOT NULL,
  "goal_revision" "whattodo"."revision" NOT NULL,
  "title" "whattodo"."ref" NOT NULL,
  "position" "whattodo"."revision" NOT NULL,
  "phase_ref" "whattodo"."ref",
  "target_amount" "whattodo"."measure",
  "target_unit" "whattodo"."ref",
  "due_ref" "whattodo"."ref",
  "transaction_ref" "whattodo"."ref" NOT NULL,
  CONSTRAINT "milestone_revision_pk_identity" PRIMARY KEY ("milestone_id", "revision"),
  CONSTRAINT "milestone_revision_ck_target_pair" CHECK ((target_amount IS NULL AND target_unit IS NULL) OR (target_amount IS NOT NULL AND target_unit IS NOT NULL))
);

CREATE TRIGGER "preserve_history" BEFORE UPDATE OR DELETE OR TRUNCATE ON "whattodo"."milestone_revision"
  FOR EACH STATEMENT EXECUTE FUNCTION "whattodo"."reject_history_mutation"();

CREATE TABLE "whattodo"."exam_revision" (
  "exam_id" "whattodo"."ref" NOT NULL,
  "revision" "whattodo"."revision" NOT NULL,
  "title" "whattodo"."ref" NOT NULL,
  "course_ref" "whattodo"."ref" NOT NULL,
  "acceptance" "whattodo"."ref" NOT NULL,
  "acceptance_ref" "whattodo"."ref",
  "source_record_ref" "whattodo"."ref",
  "timing_kind" "whattodo"."ref" NOT NULL,
  "exam_date" "whattodo"."calendar_date",
  "event_ref" "whattodo"."ref",
  "event_revision" "whattodo"."revision",
  "axis_coverage" "whattodo"."json_object",
  "transaction_ref" "whattodo"."ref" NOT NULL,
  CONSTRAINT "exam_revision_pk_identity" PRIMARY KEY ("exam_id", "revision"),
  CONSTRAINT "exam_revision_ck_acceptance" CHECK ((acceptance = 'DRAFT' AND acceptance_ref IS NULL) OR (acceptance = 'ACCEPTED' AND acceptance_ref IS NOT NULL)),
  CONSTRAINT "exam_revision_ck_time" CHECK ((timing_kind = 'UNKNOWN' AND exam_date IS NULL AND event_ref IS NULL AND event_revision IS NULL) OR (timing_kind = 'DATE_ONLY' AND exam_date IS NOT NULL AND event_ref IS NULL AND event_revision IS NULL) OR (timing_kind = 'EXACT_EVENT' AND exam_date IS NULL AND event_ref IS NOT NULL AND event_revision IS NOT NULL))
);

CREATE TRIGGER "preserve_history" BEFORE UPDATE OR DELETE OR TRUNCATE ON "whattodo"."exam_revision"
  FOR EACH STATEMENT EXECUTE FUNCTION "whattodo"."reject_history_mutation"();

CREATE TABLE "whattodo"."calendar_event_revision" (
  "event_id" "whattodo"."ref" NOT NULL,
  "revision" "whattodo"."revision" NOT NULL,
  "provider" "whattodo"."ref" NOT NULL,
  "scope_ref" "whattodo"."ref" NOT NULL,
  "external_id" "whattodo"."ref" NOT NULL,
  "source_record_ref" "whattodo"."ref" NOT NULL,
  "kind" "whattodo"."ref" NOT NULL,
  "timing_kind" "whattodo"."ref" NOT NULL,
  "starts_at" "whattodo"."instant" NOT NULL,
  "ends_at" "whattodo"."instant" NOT NULL,
  "original_timezone" "whattodo"."ref" NOT NULL,
  "original_start" "whattodo"."ref" NOT NULL,
  "original_end" "whattodo"."ref" NOT NULL,
  "occupancy" "whattodo"."ref" NOT NULL,
  "state" "whattodo"."ref" NOT NULL,
  "task_ref" "whattodo"."ref",
  "authority_ref" "whattodo"."ref",
  CONSTRAINT "calendar_event_revision_pk_identity" PRIMARY KEY ("event_id", "revision"),
  CONSTRAINT "calendar_event_revision_uq_1" UNIQUE ("provider", "scope_ref", "external_id", "revision"),
  CONSTRAINT "calendar_event_revision_ck_interval" CHECK (ends_at > starts_at),
  CONSTRAINT "calendar_event_revision_ck_kind" CHECK (kind IN ('EXTERNAL_FIXED','PLANNED_WORK','REMINDER')),
  CONSTRAINT "calendar_event_revision_ck_timing_kind" CHECK (timing_kind IN ('TIMED','ALL_DAY')),
  CONSTRAINT "calendar_event_revision_ck_occupancy" CHECK (occupancy IN ('BLOCKING','NON_BLOCKING','UNKNOWN')),
  CONSTRAINT "calendar_event_revision_ck_state" CHECK (state IN ('CONFIRMED','TENTATIVE','CANCELLED')),
  CONSTRAINT "calendar_event_revision_ck_planned_ownership" CHECK (kind <> 'PLANNED_WORK' OR (task_ref IS NOT NULL AND authority_ref IS NOT NULL))
);

CREATE TRIGGER "preserve_history" BEFORE UPDATE OR DELETE OR TRUNCATE ON "whattodo"."calendar_event_revision"
  FOR EACH STATEMENT EXECUTE FUNCTION "whattodo"."reject_history_mutation"();

CREATE TABLE "whattodo"."normalized_due" (
  "due_id" "whattodo"."ref" NOT NULL,
  "input_kind" "whattodo"."ref" NOT NULL,
  "original_value" "whattodo"."ref" NOT NULL,
  "source_record_ref" "whattodo"."ref" NOT NULL,
  "due_at" "whattodo"."instant" NOT NULL,
  "original_date" "whattodo"."calendar_date",
  "default_policy_ref" "whattodo"."ref",
  "default_timezone" "whattodo"."ref",
  CONSTRAINT "normalized_due_pk_identity" PRIMARY KEY ("due_id"),
  CONSTRAINT "normalized_due_ck_meaning" CHECK ((input_kind = 'DATE_ONLY' AND original_date IS NOT NULL AND default_policy_ref IS NOT NULL AND default_timezone IS NOT NULL AND default_timezone = 'Asia/Shanghai' AND due_at = ((original_date + TIME '23:59') AT TIME ZONE 'Asia/Shanghai')) OR (input_kind = 'EXPLICIT_INSTANT' AND original_date IS NULL AND default_policy_ref IS NULL AND default_timezone IS NULL))
);

CREATE TRIGGER "preserve_history" BEFORE UPDATE OR DELETE OR TRUNCATE ON "whattodo"."normalized_due"
  FOR EACH STATEMENT EXECUTE FUNCTION "whattodo"."reject_history_mutation"();

CREATE TABLE "whattodo"."today_lock" (
  "lock_id" "whattodo"."ref" NOT NULL,
  "task_id" "whattodo"."ref" NOT NULL,
  "task_revision" "whattodo"."revision" NOT NULL,
  "intent" "whattodo"."ref" NOT NULL,
  "authority_ref" "whattodo"."ref" NOT NULL,
  "created_at" "whattodo"."instant" NOT NULL,
  "expires_at" "whattodo"."instant" NOT NULL,
  "timezone" "whattodo"."ref" NOT NULL,
  CONSTRAINT "today_lock_pk_identity" PRIMARY KEY ("lock_id"),
  CONSTRAINT "today_lock_ck_intent" CHECK (intent IN ('COMPLETE','ADVANCE')),
  CONSTRAINT "today_lock_ck_day_end" CHECK (timezone = 'Asia/Shanghai' AND expires_at = ((((created_at AT TIME ZONE 'Asia/Shanghai')::date + 1)::timestamp) AT TIME ZONE 'Asia/Shanghai'))
);

CREATE TRIGGER "preserve_history" BEFORE UPDATE OR DELETE OR TRUNCATE ON "whattodo"."today_lock"
  FOR EACH STATEMENT EXECUTE FUNCTION "whattodo"."reject_history_mutation"();

CREATE TABLE "whattodo"."planning_snapshot" (
  "snapshot_id" "whattodo"."ref" NOT NULL,
  "store_revision" "whattodo"."revision" NOT NULL,
  "last_transaction_ref" "whattodo"."ref",
  "configuration_ref" "whattodo"."ref" NOT NULL,
  "captured_at" "whattodo"."instant" NOT NULL,
  "data_quality" "whattodo"."ref" NOT NULL,
  "input_payload" "whattodo"."json_object" NOT NULL,
  CONSTRAINT "planning_snapshot_pk_identity" PRIMARY KEY ("snapshot_id"),
  CONSTRAINT "planning_snapshot_uq_1" UNIQUE ("snapshot_id", "captured_at"),
  CONSTRAINT "planning_snapshot_ck_quality" CHECK (data_quality IN ('READY','STALE','UNRESOLVED')),
  CONSTRAINT "planning_snapshot_ck_initial_epoch" CHECK (last_transaction_ref IS NOT NULL OR store_revision = 1)
);

CREATE TRIGGER "preserve_history" BEFORE UPDATE OR DELETE OR TRUNCATE ON "whattodo"."planning_snapshot"
  FOR EACH STATEMENT EXECUTE FUNCTION "whattodo"."reject_history_mutation"();

CREATE TABLE "whattodo"."forecast_horizon" (
  "snapshot_id" "whattodo"."ref" NOT NULL,
  "horizon_days" smallint NOT NULL,
  "snapshot_at" "whattodo"."instant" NOT NULL,
  "cutoff" "whattodo"."instant" NOT NULL,
  "timezone" "whattodo"."ref" NOT NULL,
  "capacity_numerator" "whattodo"."seconds",
  "capacity_denominator" "whattodo"."positive_integer",
  "required_numerator" "whattodo"."seconds",
  "required_denominator" "whattodo"."positive_integer",
  "reserve_seconds" "whattodo"."seconds" NOT NULL,
  "risk" "whattodo"."ref",
  "data_quality" "whattodo"."ref" NOT NULL,
  "hard_constraints_ref" "whattodo"."ref" NOT NULL,
  "input_fingerprint" "whattodo"."sha256" NOT NULL,
  "placement_state" "whattodo"."ref" NOT NULL,
  "proof_ref" "whattodo"."ref",
  "assessed_at" "whattodo"."instant" NOT NULL,
  "projections" "whattodo"."json_object" NOT NULL,
  CONSTRAINT "forecast_horizon_pk_identity" PRIMARY KEY ("snapshot_id", "horizon_days"),
  CONSTRAINT "forecast_horizon_ck_days" CHECK (horizon_days IN (1,3,7)),
  CONSTRAINT "forecast_horizon_ck_timezone" CHECK (timezone = 'Asia/Shanghai'),
  CONSTRAINT "forecast_horizon_ck_cutoff" CHECK (cutoff = ((((snapshot_at AT TIME ZONE 'Asia/Shanghai')::date + horizon_days - 1) + TIME '23:59') AT TIME ZONE 'Asia/Shanghai')),
  CONSTRAINT "forecast_horizon_ck_capacity_pair" CHECK ((capacity_numerator IS NULL AND capacity_denominator IS NULL) OR (capacity_numerator IS NOT NULL AND capacity_denominator IS NOT NULL)),
  CONSTRAINT "forecast_horizon_ck_required_pair" CHECK ((required_numerator IS NULL AND required_denominator IS NULL) OR (required_numerator IS NOT NULL AND required_denominator IS NOT NULL)),
  CONSTRAINT "forecast_horizon_ck_reserve" CHECK (reserve_seconds = horizon_days * 3600),
  CONSTRAINT "forecast_horizon_ck_risk" CHECK (risk IS NULL OR risk IN ('SAFE','DANGER','EMERGENCY')),
  CONSTRAINT "forecast_horizon_ck_proof" CHECK (placement_state NOT IN ('FEASIBLE','INFEASIBLE') OR proof_ref IS NOT NULL),
  CONSTRAINT "forecast_horizon_ck_chronology" CHECK (assessed_at >= snapshot_at),
  CONSTRAINT "forecast_horizon_ck_quality" CHECK (data_quality IN ('READY','STALE','UNRESOLVED','CONFLICTED')),
  CONSTRAINT "forecast_horizon_ck_placement" CHECK (placement_state IN ('FEASIBLE','INFEASIBLE','UNKNOWN','NOT_EVALUATED')),
  CONSTRAINT "forecast_horizon_ck_known_risk" CHECK (risk IS NULL OR (data_quality = 'READY' AND capacity_numerator IS NOT NULL AND required_numerator IS NOT NULL)),
  CONSTRAINT "forecast_horizon_ck_safe_proof" CHECK (risk IS NULL OR risk <> 'SAFE' OR (placement_state = 'FEASIBLE' AND proof_ref IS NOT NULL AND capacity_numerator IS NOT NULL AND required_numerator IS NOT NULL AND capacity_numerator * required_denominator - required_numerator * capacity_denominator >= reserve_seconds * capacity_denominator * required_denominator))
);

CREATE TRIGGER "preserve_history" BEFORE UPDATE OR DELETE OR TRUNCATE ON "whattodo"."forecast_horizon"
  FOR EACH STATEMENT EXECUTE FUNCTION "whattodo"."reject_history_mutation"();

CREATE TABLE "whattodo"."plan_record" (
  "plan_id" "whattodo"."ref" NOT NULL,
  "snapshot_ref" "whattodo"."ref" NOT NULL,
  "configuration_ref" "whattodo"."ref" NOT NULL,
  "state_revision" "whattodo"."revision" NOT NULL,
  "phase" "whattodo"."ref" NOT NULL,
  "generated_at" "whattodo"."instant" NOT NULL,
  "review_response_ref" "whattodo"."ref",
  "review_commit_ref" "whattodo"."ref",
  "recompute_ref" "whattodo"."ref",
  "output_payload" "whattodo"."json_object" NOT NULL,
  CONSTRAINT "plan_record_pk_identity" PRIMARY KEY ("plan_id"),
  CONSTRAINT "plan_record_uq_1" UNIQUE ("plan_id", "snapshot_ref"),
  CONSTRAINT "plan_record_ck_phase" CHECK (phase IN ('NORMAL','UNVERIFIED','PROVISIONAL_EMERGENCY','FINAL_EMERGENCY')),
  CONSTRAINT "plan_record_ck_final_review" CHECK (phase <> 'FINAL_EMERGENCY' OR (review_response_ref IS NOT NULL AND review_commit_ref IS NOT NULL AND recompute_ref IS NOT NULL))
);

CREATE TRIGGER "preserve_history" BEFORE UPDATE OR DELETE OR TRUNCATE ON "whattodo"."plan_record"
  FOR EACH STATEMENT EXECUTE FUNCTION "whattodo"."reject_history_mutation"();

CREATE TABLE "whattodo"."plan_allocation" (
  "allocation_id" "whattodo"."ref" NOT NULL,
  "plan_id" "whattodo"."ref" NOT NULL,
  "task_id" "whattodo"."ref" NOT NULL,
  "task_revision" "whattodo"."revision" NOT NULL,
  "stage_id" "whattodo"."ref",
  "stage_revision" "whattodo"."revision",
  "seconds_numerator" "whattodo"."positive_integer" NOT NULL,
  "seconds_denominator" "whattodo"."positive_integer" NOT NULL,
  "objective" "whattodo"."ref" NOT NULL,
  "session_mode" "whattodo"."ref" NOT NULL,
  CONSTRAINT "plan_allocation_pk_identity" PRIMARY KEY ("allocation_id"),
  CONSTRAINT "plan_allocation_ck_stage_pair" CHECK ((stage_id IS NULL AND stage_revision IS NULL) OR (stage_id IS NOT NULL AND stage_revision IS NOT NULL)),
  CONSTRAINT "plan_allocation_ck_session_mode" CHECK (session_mode IN ('CONTINUOUS','FRAGMENTABLE','EITHER'))
);

CREATE TRIGGER "preserve_history" BEFORE UPDATE OR DELETE OR TRUNCATE ON "whattodo"."plan_allocation"
  FOR EACH STATEMENT EXECUTE FUNCTION "whattodo"."reject_history_mutation"();

ALTER TABLE "whattodo"."task_revision" ADD CONSTRAINT "task_revision_fk_8"
  FOREIGN KEY ("due_ref") REFERENCES "whattodo"."normalized_due" ("due_id")
  ON UPDATE NO ACTION ON DELETE NO ACTION DEFERRABLE INITIALLY DEFERRED;

ALTER TABLE "whattodo"."goal_revision" ADD CONSTRAINT "goal_revision_fk_1"
  FOREIGN KEY ("acceptance_ref") REFERENCES "whattodo"."authority_record" ("authority_ref")
  ON UPDATE NO ACTION ON DELETE NO ACTION DEFERRABLE INITIALLY DEFERRED;

ALTER TABLE "whattodo"."goal_revision" ADD CONSTRAINT "goal_revision_fk_2"
  FOREIGN KEY ("due_ref") REFERENCES "whattodo"."normalized_due" ("due_id")
  ON UPDATE NO ACTION ON DELETE NO ACTION DEFERRABLE INITIALLY DEFERRED;

ALTER TABLE "whattodo"."goal_revision" ADD CONSTRAINT "goal_revision_fk_3"
  FOREIGN KEY ("transaction_ref") REFERENCES "whattodo"."command_transaction" ("request_id")
  ON UPDATE NO ACTION ON DELETE NO ACTION DEFERRABLE INITIALLY DEFERRED;

ALTER TABLE "whattodo"."goal_progress" ADD CONSTRAINT "goal_progress_fk_1"
  FOREIGN KEY ("goal_id", "goal_revision") REFERENCES "whattodo"."goal_revision" ("goal_id", "revision")
  ON UPDATE NO ACTION ON DELETE NO ACTION DEFERRABLE INITIALLY DEFERRED;

ALTER TABLE "whattodo"."goal_progress" ADD CONSTRAINT "goal_progress_fk_2"
  FOREIGN KEY ("source_record_ref") REFERENCES "whattodo"."source_record" ("record_id")
  ON UPDATE NO ACTION ON DELETE NO ACTION DEFERRABLE INITIALLY DEFERRED;

ALTER TABLE "whattodo"."goal_progress" ADD CONSTRAINT "goal_progress_fk_3"
  FOREIGN KEY ("authority_ref") REFERENCES "whattodo"."authority_record" ("authority_ref")
  ON UPDATE NO ACTION ON DELETE NO ACTION DEFERRABLE INITIALLY DEFERRED;

ALTER TABLE "whattodo"."goal_progress" ADD CONSTRAINT "goal_progress_fk_4"
  FOREIGN KEY ("transaction_ref") REFERENCES "whattodo"."command_transaction" ("request_id")
  ON UPDATE NO ACTION ON DELETE NO ACTION DEFERRABLE INITIALLY DEFERRED;

ALTER TABLE "whattodo"."milestone_revision" ADD CONSTRAINT "milestone_revision_fk_1"
  FOREIGN KEY ("goal_id", "goal_revision") REFERENCES "whattodo"."goal_revision" ("goal_id", "revision")
  ON UPDATE NO ACTION ON DELETE NO ACTION DEFERRABLE INITIALLY DEFERRED;

ALTER TABLE "whattodo"."milestone_revision" ADD CONSTRAINT "milestone_revision_fk_2"
  FOREIGN KEY ("due_ref") REFERENCES "whattodo"."normalized_due" ("due_id")
  ON UPDATE NO ACTION ON DELETE NO ACTION DEFERRABLE INITIALLY DEFERRED;

ALTER TABLE "whattodo"."milestone_revision" ADD CONSTRAINT "milestone_revision_fk_3"
  FOREIGN KEY ("transaction_ref") REFERENCES "whattodo"."command_transaction" ("request_id")
  ON UPDATE NO ACTION ON DELETE NO ACTION DEFERRABLE INITIALLY DEFERRED;

ALTER TABLE "whattodo"."exam_revision" ADD CONSTRAINT "exam_revision_fk_1"
  FOREIGN KEY ("acceptance_ref") REFERENCES "whattodo"."authority_record" ("authority_ref")
  ON UPDATE NO ACTION ON DELETE NO ACTION DEFERRABLE INITIALLY DEFERRED;

ALTER TABLE "whattodo"."exam_revision" ADD CONSTRAINT "exam_revision_fk_2"
  FOREIGN KEY ("source_record_ref") REFERENCES "whattodo"."source_record" ("record_id")
  ON UPDATE NO ACTION ON DELETE NO ACTION DEFERRABLE INITIALLY DEFERRED;

ALTER TABLE "whattodo"."exam_revision" ADD CONSTRAINT "exam_revision_fk_3"
  FOREIGN KEY ("event_ref", "event_revision") REFERENCES "whattodo"."calendar_event_revision" ("event_id", "revision")
  ON UPDATE NO ACTION ON DELETE NO ACTION DEFERRABLE INITIALLY DEFERRED;

ALTER TABLE "whattodo"."exam_revision" ADD CONSTRAINT "exam_revision_fk_4"
  FOREIGN KEY ("transaction_ref") REFERENCES "whattodo"."command_transaction" ("request_id")
  ON UPDATE NO ACTION ON DELETE NO ACTION DEFERRABLE INITIALLY DEFERRED;

ALTER TABLE "whattodo"."calendar_event_revision" ADD CONSTRAINT "calendar_event_revision_fk_1"
  FOREIGN KEY ("provider", "scope_ref") REFERENCES "whattodo"."source_scope" ("provider", "scope_ref")
  ON UPDATE NO ACTION ON DELETE NO ACTION DEFERRABLE INITIALLY DEFERRED;

ALTER TABLE "whattodo"."calendar_event_revision" ADD CONSTRAINT "calendar_event_revision_fk_2"
  FOREIGN KEY ("source_record_ref") REFERENCES "whattodo"."source_record" ("record_id")
  ON UPDATE NO ACTION ON DELETE NO ACTION DEFERRABLE INITIALLY DEFERRED;

ALTER TABLE "whattodo"."calendar_event_revision" ADD CONSTRAINT "calendar_event_revision_fk_3"
  FOREIGN KEY ("task_ref") REFERENCES "whattodo"."task_identity" ("task_id")
  ON UPDATE NO ACTION ON DELETE NO ACTION DEFERRABLE INITIALLY DEFERRED;

ALTER TABLE "whattodo"."calendar_event_revision" ADD CONSTRAINT "calendar_event_revision_fk_4"
  FOREIGN KEY ("authority_ref") REFERENCES "whattodo"."authority_record" ("authority_ref")
  ON UPDATE NO ACTION ON DELETE NO ACTION DEFERRABLE INITIALLY DEFERRED;

ALTER TABLE "whattodo"."normalized_due" ADD CONSTRAINT "normalized_due_fk_1"
  FOREIGN KEY ("source_record_ref") REFERENCES "whattodo"."source_record" ("record_id")
  ON UPDATE NO ACTION ON DELETE NO ACTION DEFERRABLE INITIALLY DEFERRED;

ALTER TABLE "whattodo"."today_lock" ADD CONSTRAINT "today_lock_fk_1"
  FOREIGN KEY ("task_id", "task_revision") REFERENCES "whattodo"."task_revision" ("task_id", "revision")
  ON UPDATE NO ACTION ON DELETE NO ACTION DEFERRABLE INITIALLY DEFERRED;

ALTER TABLE "whattodo"."today_lock" ADD CONSTRAINT "today_lock_fk_2"
  FOREIGN KEY ("authority_ref") REFERENCES "whattodo"."authority_record" ("authority_ref")
  ON UPDATE NO ACTION ON DELETE NO ACTION DEFERRABLE INITIALLY DEFERRED;

ALTER TABLE "whattodo"."planning_snapshot" ADD CONSTRAINT "planning_snapshot_fk_1"
  FOREIGN KEY ("last_transaction_ref", "store_revision") REFERENCES "whattodo"."command_transaction" ("request_id", "committed_store_revision")
  ON UPDATE NO ACTION ON DELETE NO ACTION DEFERRABLE INITIALLY DEFERRED;

ALTER TABLE "whattodo"."planning_snapshot" ADD CONSTRAINT "planning_snapshot_fk_2"
  FOREIGN KEY ("configuration_ref") REFERENCES "whattodo"."configuration_revision" ("configuration_ref")
  ON UPDATE NO ACTION ON DELETE NO ACTION DEFERRABLE INITIALLY DEFERRED;

ALTER TABLE "whattodo"."forecast_horizon" ADD CONSTRAINT "forecast_horizon_fk_1"
  FOREIGN KEY ("snapshot_id", "snapshot_at") REFERENCES "whattodo"."planning_snapshot" ("snapshot_id", "captured_at")
  ON UPDATE NO ACTION ON DELETE NO ACTION DEFERRABLE INITIALLY DEFERRED;

ALTER TABLE "whattodo"."plan_record" ADD CONSTRAINT "plan_record_fk_1"
  FOREIGN KEY ("snapshot_ref") REFERENCES "whattodo"."planning_snapshot" ("snapshot_id")
  ON UPDATE NO ACTION ON DELETE NO ACTION DEFERRABLE INITIALLY DEFERRED;

ALTER TABLE "whattodo"."plan_record" ADD CONSTRAINT "plan_record_fk_2"
  FOREIGN KEY ("configuration_ref") REFERENCES "whattodo"."configuration_revision" ("configuration_ref")
  ON UPDATE NO ACTION ON DELETE NO ACTION DEFERRABLE INITIALLY DEFERRED;

ALTER TABLE "whattodo"."plan_record" ADD CONSTRAINT "plan_record_fk_3"
  FOREIGN KEY ("review_response_ref") REFERENCES "whattodo"."review_response" ("response_id")
  ON UPDATE NO ACTION ON DELETE NO ACTION DEFERRABLE INITIALLY DEFERRED;

ALTER TABLE "whattodo"."plan_record" ADD CONSTRAINT "plan_record_fk_4"
  FOREIGN KEY ("review_commit_ref") REFERENCES "whattodo"."command_transaction" ("request_id")
  ON UPDATE NO ACTION ON DELETE NO ACTION DEFERRABLE INITIALLY DEFERRED;

ALTER TABLE "whattodo"."plan_allocation" ADD CONSTRAINT "plan_allocation_fk_1"
  FOREIGN KEY ("plan_id") REFERENCES "whattodo"."plan_record" ("plan_id")
  ON UPDATE NO ACTION ON DELETE NO ACTION DEFERRABLE INITIALLY DEFERRED;

ALTER TABLE "whattodo"."plan_allocation" ADD CONSTRAINT "plan_allocation_fk_2"
  FOREIGN KEY ("task_id", "task_revision") REFERENCES "whattodo"."task_revision" ("task_id", "revision")
  ON UPDATE NO ACTION ON DELETE NO ACTION DEFERRABLE INITIALLY DEFERRED;

ALTER TABLE "whattodo"."plan_allocation" ADD CONSTRAINT "plan_allocation_fk_3"
  FOREIGN KEY ("stage_id", "stage_revision", "task_id") REFERENCES "whattodo"."stage_revision" ("stage_id", "revision", "task_id")
  ON UPDATE NO ACTION ON DELETE NO ACTION DEFERRABLE INITIALLY DEFERRED;

REVOKE ALL ON ALL TABLES IN SCHEMA "whattodo" FROM PUBLIC;
COMMIT;
