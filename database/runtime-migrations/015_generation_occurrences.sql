-- Composite generation occurrence history; legacy rows remain unadmitted.
BEGIN;
SET LOCAL search_path=pg_catalog;
ALTER TABLE whattodo.canonical_creation_event ADD CONSTRAINT generation_exact_source_event
UNIQUE(event_id,task_id,task_revision,creation_transaction_ref);
ALTER TABLE whattodo.generation_occurrence
 ADD COLUMN source_event_ref whattodo.ref,
 ADD COLUMN relation_ref whattodo.ref,
 ADD COLUMN relation_revision whattodo.revision,
 ADD COLUMN runtime_payload whattodo.json_object,
 ADD CONSTRAINT generation_source_event FOREIGN KEY(source_event_ref,source_task_id,source_task_revision,creation_transaction_ref)
 REFERENCES whattodo.canonical_creation_event(event_id,task_id,task_revision,creation_transaction_ref) DEFERRABLE INITIALLY DEFERRED,
 ADD CONSTRAINT generation_relation FOREIGN KEY(relation_ref,relation_revision)
 REFERENCES whattodo.task_relation_revision(relation_id,revision) DEFERRABLE INITIALLY DEFERRED,
 ADD CONSTRAINT generation_runtime_payload CHECK
 ((runtime_payload IS NULL AND source_event_ref IS NULL AND relation_ref IS NULL AND relation_revision IS NULL)
 OR ((source_event_ref IS NOT NULL AND occurrence_key=source_event_ref
 AND jsonb_typeof(runtime_payload->'manifest')='object'
 AND runtime_payload-'manifest'=jsonb_build_object(
  'generation_key',generation_key,'rule_id',rule_id,'rule_version',rule_version,
  'source_task_id',source_task_id,'source_task_revision',source_task_revision,
  'creation_transaction_ref',creation_transaction_ref,'source_event_ref',source_event_ref,
  'occurrence_key',occurrence_key,'target_role',target_role,'obligation_kind',obligation_kind,
  'state',state,'revision',revision,'target_task_ref',target_task_ref,'target_stage_ref',target_stage_ref,
  'target_stage_revision',target_stage_revision,'failure_code',failure_code,
  'missing_fields',missing_facts->'fields','relation_ref',relation_ref,'relation_revision',relation_revision)
 AND jsonb_typeof(missing_facts->'fields')='array' AND missing_facts=jsonb_build_object('fields',missing_facts->'fields')
 AND ((state='PENDING' AND jsonb_array_length(missing_facts->'fields')>0)
  OR (state IN ('CREATED','FAILED') AND missing_facts->'fields'='[]'::jsonb))
 AND ((relation_ref IS NULL AND relation_revision IS NULL)
  OR (state='CREATED' AND relation_ref IS NOT NULL AND relation_revision=1))) IS TRUE));

CREATE TABLE whattodo.generation_occurrence_revision (
 LIKE whattodo.generation_occurrence INCLUDING DEFAULTS INCLUDING CONSTRAINTS,
 PRIMARY KEY(generation_key,revision),
 FOREIGN KEY(rule_id,rule_version,target_role) REFERENCES whattodo.relationship_rule_revision(rule_id,version,target_role) DEFERRABLE INITIALLY DEFERRED,
 FOREIGN KEY(source_event_ref,source_task_id,source_task_revision,creation_transaction_ref)
 REFERENCES whattodo.canonical_creation_event(event_id,task_id,task_revision,creation_transaction_ref) DEFERRABLE INITIALLY DEFERRED,
 FOREIGN KEY(target_task_ref) REFERENCES whattodo.task_identity(task_id) DEFERRABLE INITIALLY DEFERRED,
 FOREIGN KEY(target_stage_ref,target_stage_revision) REFERENCES whattodo.stage_revision(stage_id,revision) DEFERRABLE INITIALLY DEFERRED,
 FOREIGN KEY(relation_ref,relation_revision) REFERENCES whattodo.task_relation_revision(relation_id,revision) DEFERRABLE INITIALLY DEFERRED,
 FOREIGN KEY(transaction_ref) REFERENCES whattodo.command_transaction(request_id) DEFERRABLE INITIALLY DEFERRED,
 FOREIGN KEY(audit_change_ref,aggregate_kind,generation_key,revision,transaction_ref)
 REFERENCES whattodo.audit_change(change_id,aggregate_kind,aggregate_id,after_revision,request_id) DEFERRABLE INITIALLY DEFERRED
);
ALTER TABLE whattodo.generation_occurrence_revision ALTER COLUMN runtime_payload SET NOT NULL;
-- Nullable/unadmitted legacy heads intentionally have no fabricated history.
ALTER TABLE whattodo.generation_occurrence ADD COLUMN runtime_history_key whattodo.ref
GENERATED ALWAYS AS (CASE WHEN runtime_payload IS NOT NULL THEN generation_key ELSE NULL END) STORED;
ALTER TABLE whattodo.generation_occurrence ADD CONSTRAINT generation_exact_history
FOREIGN KEY(runtime_history_key,revision) REFERENCES whattodo.generation_occurrence_revision(generation_key,revision) DEFERRABLE INITIALLY DEFERRED;
CREATE TRIGGER preserve_history BEFORE UPDATE OR DELETE OR TRUNCATE ON whattodo.generation_occurrence_revision
FOR EACH STATEMENT EXECUTE FUNCTION whattodo.reject_history_mutation();

CREATE OR REPLACE FUNCTION whattodo.guard_generation_occurrence() RETURNS trigger
LANGUAGE plpgsql SET search_path=pg_catalog AS $guard$
BEGIN
 IF (NEW.generation_key,NEW.rule_id,NEW.source_task_id,NEW.source_task_revision,NEW.creation_transaction_ref,
     NEW.occurrence_key,NEW.target_role,NEW.obligation_kind,NEW.source_event_ref)
 IS DISTINCT FROM
    (OLD.generation_key,OLD.rule_id,OLD.source_task_id,OLD.source_task_revision,OLD.creation_transaction_ref,
     OLD.occurrence_key,OLD.target_role,OLD.obligation_kind,OLD.source_event_ref)
 OR NEW.revision<>OLD.revision+1 OR NEW.transaction_ref IS NOT DISTINCT FROM OLD.transaction_ref THEN
  RAISE EXCEPTION 'Generation head identity/revision mismatch' USING ERRCODE='23514';
 END IF;
 IF OLD.runtime_payload IS NULL THEN
  IF NEW.runtime_payload IS NOT NULL OR NEW.rule_version IS DISTINCT FROM OLD.rule_version
   OR (OLD.state='CREATED' AND (NEW.state,NEW.target_task_ref,NEW.target_stage_ref,NEW.target_stage_revision)
      IS DISTINCT FROM (OLD.state,OLD.target_task_ref,OLD.target_stage_ref,OLD.target_stage_revision)) THEN
   RAISE EXCEPTION 'Legacy generation head cannot be silently admitted' USING ERRCODE='23514';
  END IF;
 ELSIF OLD.state='CREATED' OR NEW.runtime_payload IS NULL THEN
  RAISE EXCEPTION 'Created generation occurrence is terminal' USING ERRCODE='23514';
 END IF;
 RETURN NEW;
END;
$guard$;
REVOKE ALL ON FUNCTION whattodo.guard_generation_occurrence() FROM PUBLIC;

CREATE FUNCTION whattodo.guard_generation_history() RETURNS trigger
LANGUAGE plpgsql SET search_path=pg_catalog AS $guard$
DECLARE prior whattodo.generation_occurrence%ROWTYPE;
BEGIN
 SELECT * INTO prior FROM whattodo.generation_occurrence WHERE generation_key=NEW.generation_key;
 IF NOT FOUND THEN
  IF NEW.revision<>1 THEN RAISE EXCEPTION 'Generation first revision mismatch' USING ERRCODE='23514'; END IF;
 ELSE
  IF prior.runtime_payload IS NULL OR prior.state='CREATED' OR NEW.revision<>prior.revision+1
   OR (NEW.rule_id,NEW.source_task_id,NEW.source_task_revision,NEW.creation_transaction_ref,
       NEW.occurrence_key,NEW.target_role,NEW.obligation_kind,NEW.source_event_ref)
   IS DISTINCT FROM (prior.rule_id,prior.source_task_id,prior.source_task_revision,prior.creation_transaction_ref,
       prior.occurrence_key,prior.target_role,prior.obligation_kind,prior.source_event_ref)
   OR NEW.transaction_ref IS NOT DISTINCT FROM prior.transaction_ref THEN
   RAISE EXCEPTION 'Generation history identity/revision mismatch' USING ERRCODE='23514';
  END IF;
 END IF;
 RETURN NEW;
END;
$guard$;
REVOKE ALL ON FUNCTION whattodo.guard_generation_history() FROM PUBLIC;
CREATE TRIGGER guard_append BEFORE INSERT ON whattodo.generation_occurrence_revision
FOR EACH ROW EXECUTE FUNCTION whattodo.guard_generation_history();

CREATE FUNCTION whattodo.check_generation_head_history() RETURNS trigger
LANGUAGE plpgsql SET search_path=pg_catalog AS $guard$
DECLARE saved jsonb;
BEGIN
 IF NEW.runtime_payload IS NOT NULL THEN
  SELECT to_jsonb(r) INTO saved FROM whattodo.generation_occurrence_revision r
  WHERE generation_key=NEW.generation_key AND revision=NEW.revision;
  IF saved IS DISTINCT FROM to_jsonb(NEW)-'runtime_history_key' THEN
   RAISE EXCEPTION 'Typed generation head must equal immutable history' USING ERRCODE='23514';
  END IF;
 END IF;
 RETURN NEW;
END;
$guard$;
REVOKE ALL ON FUNCTION whattodo.check_generation_head_history() FROM PUBLIC;
CREATE CONSTRAINT TRIGGER exact_generation_head AFTER INSERT OR UPDATE ON whattodo.generation_occurrence
DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION whattodo.check_generation_head_history();
COMMIT;
