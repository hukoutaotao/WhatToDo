-- Fenced processing metadata; canonical writes remain independently authorized.
BEGIN;
SET LOCAL search_path=pg_catalog;
CREATE TABLE whattodo.generation_chain_event (
 event_id whattodo.ref PRIMARY KEY,
 root_event_id whattodo.ref NOT NULL,
 parent_event_id whattodo.ref,
 depth bigint NOT NULL CHECK(depth>=0),
 UNIQUE(event_id,root_event_id),
 FOREIGN KEY(event_id) REFERENCES whattodo.canonical_creation_event(event_id) DEFERRABLE INITIALLY DEFERRED,
 FOREIGN KEY(root_event_id) REFERENCES whattodo.generation_chain_event(event_id) DEFERRABLE INITIALLY DEFERRED,
 FOREIGN KEY(parent_event_id) REFERENCES whattodo.generation_chain_event(event_id) DEFERRABLE INITIALLY DEFERRED,
 CHECK((depth=0 AND parent_event_id IS NULL AND root_event_id=event_id) OR (depth>0 AND parent_event_id IS NOT NULL))
);
CREATE TABLE whattodo.generation_processing_revision (
 event_id whattodo.ref NOT NULL,
 revision whattodo.revision NOT NULL,
 lease_revision whattodo.revision NOT NULL,
 worker_id whattodo.ref NOT NULL,
 lease_token text NOT NULL CHECK(lease_token~'^[a-f0-9]{32}$'),
 changed_at whattodo.instant NOT NULL,
 progress whattodo.json_object NOT NULL,
 PRIMARY KEY(event_id,revision),
 FOREIGN KEY(event_id) REFERENCES whattodo.canonical_creation_event(event_id) DEFERRABLE INITIALLY DEFERRED,
 FOREIGN KEY(event_id,lease_revision) REFERENCES whattodo.creation_delivery_revision(event_id,revision) DEFERRABLE INITIALLY DEFERRED
);
CREATE TABLE whattodo.generation_processing_head (
 event_id whattodo.ref PRIMARY KEY,
 revision whattodo.revision NOT NULL,
 FOREIGN KEY(event_id,revision) REFERENCES whattodo.generation_processing_revision(event_id,revision) DEFERRABLE INITIALLY DEFERRED
);
CREATE TABLE whattodo.generation_chain_slot_revision (
 generation_key whattodo.ref NOT NULL,
 revision whattodo.revision NOT NULL,
 root_event_id whattodo.ref NOT NULL,
 source_event_id whattodo.ref NOT NULL,
 rule_id whattodo.ref NOT NULL,
 rule_version whattodo.ref NOT NULL,
 target_role whattodo.ref NOT NULL,
 state text NOT NULL CHECK(state IN ('RESERVED','CREATED','RELEASED')),
 worker_id whattodo.ref NOT NULL,
 lease_token text NOT NULL CHECK(lease_token~'^[a-f0-9]{32}$'),
 lease_revision whattodo.revision NOT NULL,
 occurrence_revision whattodo.revision,
 changed_at whattodo.instant NOT NULL,
 PRIMARY KEY(generation_key,revision),
 FOREIGN KEY(source_event_id,root_event_id) REFERENCES whattodo.generation_chain_event(event_id,root_event_id) DEFERRABLE INITIALLY DEFERRED,
 FOREIGN KEY(rule_id,rule_version,target_role) REFERENCES whattodo.relationship_rule_revision(rule_id,version,target_role) DEFERRABLE INITIALLY DEFERRED,
 FOREIGN KEY(source_event_id,lease_revision) REFERENCES whattodo.creation_delivery_revision(event_id,revision) DEFERRABLE INITIALLY DEFERRED,
 FOREIGN KEY(generation_key,occurrence_revision) REFERENCES whattodo.generation_occurrence_revision(generation_key,revision) DEFERRABLE INITIALLY DEFERRED,
 CHECK((state='CREATED')=(occurrence_revision IS NOT NULL))
);
CREATE TABLE whattodo.generation_chain_slot_head (
 generation_key whattodo.ref PRIMARY KEY,
 revision whattodo.revision NOT NULL,
 FOREIGN KEY(generation_key,revision) REFERENCES whattodo.generation_chain_slot_revision(generation_key,revision) DEFERRABLE INITIALLY DEFERRED
);
CREATE INDEX generation_chain_slot_root ON whattodo.generation_chain_slot_revision(root_event_id,generation_key,revision DESC);
CREATE FUNCTION whattodo.guard_generation_lineage() RETURNS trigger
LANGUAGE plpgsql SET search_path=pg_catalog AS $guard$
DECLARE prior whattodo.generation_chain_event%ROWTYPE;
BEGIN
 IF NEW.parent_event_id IS NOT NULL THEN
  SELECT * INTO prior FROM whattodo.generation_chain_event WHERE event_id=NEW.parent_event_id;
  IF NOT FOUND OR NEW.root_event_id<>prior.root_event_id OR NEW.depth<>prior.depth+1
   OR NOT EXISTS(SELECT 1 FROM whattodo.canonical_creation_event e JOIN whattodo.generation_occurrence_revision g
    ON g.target_task_ref=e.task_id AND g.transaction_ref=e.creation_transaction_ref
    WHERE e.event_id=NEW.event_id AND g.source_event_ref=NEW.parent_event_id AND g.state='CREATED') THEN
   RAISE EXCEPTION 'Processing lineage mismatch' USING ERRCODE='23514';
  END IF;
 ELSE
  IF NOT EXISTS(SELECT 1 FROM whattodo.canonical_creation_event e JOIN whattodo.command_transaction t ON t.request_id=e.creation_transaction_ref
   WHERE e.event_id=NEW.event_id AND t.origin='USER_COMMAND') THEN
   RAISE EXCEPTION 'Processing root mismatch' USING ERRCODE='23514';
  END IF;
 END IF;
 RETURN NEW;
END;
$guard$;
CREATE FUNCTION whattodo.guard_generation_processing_head() RETURNS trigger
LANGUAGE plpgsql SET search_path=pg_catalog AS $guard$
BEGIN
 IF NEW.event_id IS DISTINCT FROM OLD.event_id OR NEW.revision<>OLD.revision+1 THEN
  RAISE EXCEPTION 'Processing head mismatch' USING ERRCODE='23514';
 END IF;
 RETURN NEW;
END;
$guard$;
CREATE FUNCTION whattodo.guard_generation_slot_head() RETURNS trigger
LANGUAGE plpgsql SET search_path=pg_catalog AS $guard$
BEGIN
 IF NEW.generation_key IS DISTINCT FROM OLD.generation_key OR NEW.revision<>OLD.revision+1 THEN
  RAISE EXCEPTION 'Processing slot head mismatch' USING ERRCODE='23514';
 END IF;
 RETURN NEW;
END;
$guard$;
REVOKE ALL ON FUNCTION whattodo.guard_generation_lineage(),whattodo.guard_generation_processing_head(),whattodo.guard_generation_slot_head() FROM PUBLIC;
CREATE TRIGGER guard_lineage BEFORE INSERT ON whattodo.generation_chain_event FOR EACH ROW EXECUTE FUNCTION whattodo.guard_generation_lineage();
CREATE TRIGGER guard_version BEFORE UPDATE ON whattodo.generation_processing_head FOR EACH ROW EXECUTE FUNCTION whattodo.guard_generation_processing_head();
CREATE TRIGGER guard_version BEFORE UPDATE ON whattodo.generation_chain_slot_head FOR EACH ROW EXECUTE FUNCTION whattodo.guard_generation_slot_head();
CREATE TRIGGER preserve_history BEFORE UPDATE OR DELETE OR TRUNCATE ON whattodo.generation_chain_event FOR EACH STATEMENT EXECUTE FUNCTION whattodo.reject_history_mutation();
CREATE TRIGGER preserve_history BEFORE UPDATE OR DELETE OR TRUNCATE ON whattodo.generation_processing_revision FOR EACH STATEMENT EXECUTE FUNCTION whattodo.reject_history_mutation();
CREATE TRIGGER preserve_history BEFORE UPDATE OR DELETE OR TRUNCATE ON whattodo.generation_chain_slot_revision FOR EACH STATEMENT EXECUTE FUNCTION whattodo.reject_history_mutation();
CREATE TRIGGER preserve_history BEFORE DELETE OR TRUNCATE ON whattodo.generation_processing_head FOR EACH STATEMENT EXECUTE FUNCTION whattodo.reject_history_mutation();
CREATE TRIGGER preserve_history BEFORE DELETE OR TRUNCATE ON whattodo.generation_chain_slot_head FOR EACH STATEMENT EXECUTE FUNCTION whattodo.reject_history_mutation();
-- A trusted processing owner may take a new lease after changed inputs. Old
-- settlement tokens/revisions remain distinct and replay their original result.
CREATE OR REPLACE FUNCTION whattodo.guard_creation_delivery_revision() RETURNS trigger
LANGUAGE plpgsql SET search_path=pg_catalog AS $guard$
DECLARE prior whattodo.creation_delivery_revision%ROWTYPE;
BEGIN
 SELECT r.* INTO prior FROM whattodo.creation_delivery_head h JOIN whattodo.creation_delivery_revision r USING(event_id,revision) WHERE h.event_id=NEW.event_id;
 IF NOT FOUND THEN
  IF (NEW.revision=1 AND NEW.state='READY' AND NEW.attempt=0 AND NEW.changed_at=NEW.available_at
   AND NEW.changed_at=(SELECT occurred_at FROM whattodo.canonical_creation_event WHERE event_id=NEW.event_id)) IS NOT TRUE THEN
   RAISE EXCEPTION 'Outbox initial state mismatch' USING ERRCODE='23514';
  END IF;
 ELSE
  IF NEW.revision<>prior.revision+1 OR NEW.changed_at<prior.changed_at THEN
   RAISE EXCEPTION 'Outbox stale revision or clock' USING ERRCODE='23514';
  END IF;
  IF NEW.state='CLAIMED' THEN
   IF (NEW.available_at=prior.available_at AND
    ((((prior.state='READY' AND prior.available_at<=NEW.changed_at) OR (prior.state='CLAIMED' AND prior.lease_until<=NEW.changed_at)
        OR prior.state IN ('WAITING_FACTS','FAILED')) AND NEW.attempt=prior.attempt+1 AND NEW.lease_token IS DISTINCT FROM prior.lease_token)
     OR (prior.state='CLAIMED' AND prior.lease_until>NEW.changed_at AND NEW.worker_id=prior.worker_id AND NEW.lease_token=prior.lease_token
         AND NEW.attempt=prior.attempt AND NEW.lease_until>prior.lease_until))) IS NOT TRUE THEN
    RAISE EXCEPTION 'Outbox claim or renewal mismatch' USING ERRCODE='23514';
   END IF;
  ELSE
   IF (prior.state='CLAIMED' AND prior.lease_until>NEW.changed_at AND NEW.attempt=prior.attempt AND NEW.settled_worker_id=prior.worker_id
    AND NEW.settled_token=prior.lease_token AND NEW.settled_revision=prior.revision
    AND (NEW.state<>'READY' OR NEW.available_at>=NEW.changed_at)) IS NOT TRUE THEN
    RAISE EXCEPTION 'Outbox settlement mismatch' USING ERRCODE='23514';
   END IF;
  END IF;
 END IF;
 RETURN NEW;
END;
$guard$;
REVOKE ALL ON FUNCTION whattodo.guard_creation_delivery_revision() FROM PUBLIC;
COMMIT;
