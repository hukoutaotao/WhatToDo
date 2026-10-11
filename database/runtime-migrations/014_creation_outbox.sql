-- Atomic first canonical payload capture; no historical backfill or generation.
BEGIN;
SET LOCAL search_path=pg_catalog;
ALTER TABLE whattodo.task_payload_revision ADD CONSTRAINT outbox_exact_source_payload
UNIQUE(task_id,task_revision,transaction_ref,content_hash);
ALTER TABLE whattodo.task_identity ADD CONSTRAINT outbox_exact_creation_identity UNIQUE(task_id,transaction_ref);
ALTER TABLE whattodo.command_transaction ADD CONSTRAINT outbox_exact_creation_receipt
UNIQUE(request_id,principal_id,authority_ref,committed_at);
CREATE TABLE whattodo.canonical_creation_event (
 event_id whattodo.ref PRIMARY KEY,
 task_id whattodo.ref NOT NULL UNIQUE,
 task_revision whattodo.revision NOT NULL,
 content_hash whattodo.sha256 NOT NULL,
 creation_transaction_ref whattodo.ref NOT NULL,
 principal_id whattodo.ref NOT NULL,
 authority_ref whattodo.ref NOT NULL,
 occurred_at whattodo.instant NOT NULL,
 CHECK(event_id='creation:'||encode(sha256(convert_to(task_id,'UTF8')),'hex')),
 FOREIGN KEY(task_id,task_revision,creation_transaction_ref,content_hash)
 REFERENCES whattodo.task_payload_revision(task_id,task_revision,transaction_ref,content_hash) DEFERRABLE INITIALLY DEFERRED,
 FOREIGN KEY(task_id,creation_transaction_ref) REFERENCES whattodo.task_identity(task_id,transaction_ref) DEFERRABLE INITIALLY DEFERRED,
 FOREIGN KEY(creation_transaction_ref,principal_id,authority_ref,occurred_at)
 REFERENCES whattodo.command_transaction(request_id,principal_id,authority_ref,committed_at) DEFERRABLE INITIALLY DEFERRED
);
CREATE TABLE whattodo.creation_delivery_revision (
 event_id whattodo.ref NOT NULL,
 revision whattodo.revision NOT NULL,
 state text NOT NULL CHECK(state IN ('READY','CLAIMED','DONE','WAITING_FACTS','FAILED')),
 attempt bigint NOT NULL CHECK(attempt>=0),
 changed_at whattodo.instant NOT NULL,
 available_at whattodo.instant NOT NULL,
 worker_id whattodo.ref,
 lease_token text CHECK(lease_token~'^[a-f0-9]{32}$'),
 lease_until whattodo.instant,
 settled_worker_id whattodo.ref,
 settled_token text CHECK(settled_token~'^[a-f0-9]{32}$'),
 settled_revision whattodo.revision,
 outcome whattodo.json_object,
 CHECK(outcome IS NULL OR ((outcome ?& ARRAY['kind','result_ref','code','retry_at']
  AND outcome-ARRAY['kind','result_ref','code','retry_at']='{}'::jsonb
  AND (outcome->'result_ref'='null'::jsonb OR (jsonb_typeof(outcome->'result_ref')='string'
   AND length(outcome->>'result_ref') BETWEEN 1 AND 200 AND btrim(outcome->>'result_ref')<>''))
  AND ((outcome->>'kind' IN ('DONE','WAITING_FACTS') AND jsonb_typeof(outcome->'result_ref')='string'
    AND outcome->'code'='null'::jsonb AND outcome->'retry_at'='null'::jsonb)
   OR (outcome->>'kind' IN ('FAILED','RETRY') AND jsonb_typeof(outcome->'code')='string'
    AND outcome->>'code'~'^[A-Z][A-Z0-9_]{0,63}$'
    AND ((outcome->>'kind'='FAILED' AND outcome->'retry_at'='null'::jsonb)
     OR (outcome->>'kind'='RETRY' AND jsonb_typeof(outcome->'retry_at')='string'
      AND outcome->>'retry_at'~'(Z|[+-][0-9]{2}:[0-9]{2})$'))))) IS TRUE)),
 PRIMARY KEY(event_id,revision),
 FOREIGN KEY(event_id) REFERENCES whattodo.canonical_creation_event(event_id) DEFERRABLE INITIALLY DEFERRED,
 CHECK(((state='CLAIMED' AND attempt>0 AND worker_id IS NOT NULL AND lease_token IS NOT NULL
  AND lease_until>changed_at AND lease_until<=changed_at+interval '1 hour' AND settled_token IS NULL
  AND settled_worker_id IS NULL AND settled_revision IS NULL AND outcome IS NULL)
 OR (state<>'CLAIMED' AND worker_id IS NULL AND lease_token IS NULL AND lease_until IS NULL
  AND ((state='READY' AND attempt=0 AND outcome IS NULL AND settled_token IS NULL AND settled_worker_id IS NULL AND settled_revision IS NULL)
   OR (attempt>0 AND outcome IS NOT NULL AND settled_token IS NOT NULL AND settled_worker_id IS NOT NULL AND settled_revision IS NOT NULL
    AND ((state='READY' AND outcome->>'kind'='RETRY' AND available_at=(outcome->>'retry_at')::timestamptz)
     OR (state<>'READY' AND outcome->>'kind'=state AND outcome->>'retry_at' IS NULL)))))) IS TRUE)
);
CREATE TABLE whattodo.creation_delivery_head (
 event_id whattodo.ref PRIMARY KEY,
 revision whattodo.revision NOT NULL,
 FOREIGN KEY(event_id,revision) REFERENCES whattodo.creation_delivery_revision(event_id,revision) DEFERRABLE INITIALLY DEFERRED
);
CREATE INDEX outbox_principal_event_order ON whattodo.canonical_creation_event(principal_id,occurred_at,event_id);
CREATE INDEX outbox_settlement_replay ON whattodo.creation_delivery_revision(event_id,settled_token,settled_revision)
WHERE settled_token IS NOT NULL;
CREATE TRIGGER preserve_history BEFORE UPDATE OR DELETE OR TRUNCATE ON whattodo.canonical_creation_event
FOR EACH STATEMENT EXECUTE FUNCTION whattodo.reject_history_mutation();
CREATE TRIGGER preserve_history BEFORE UPDATE OR DELETE OR TRUNCATE ON whattodo.creation_delivery_revision
FOR EACH STATEMENT EXECUTE FUNCTION whattodo.reject_history_mutation();
CREATE TRIGGER preserve_history BEFORE DELETE OR TRUNCATE ON whattodo.creation_delivery_head
FOR EACH STATEMENT EXECUTE FUNCTION whattodo.reject_history_mutation();
CREATE FUNCTION whattodo.guard_creation_delivery_head() RETURNS trigger
LANGUAGE plpgsql SET search_path=pg_catalog AS $guard$
BEGIN
 IF NEW.event_id IS DISTINCT FROM OLD.event_id OR NEW.revision IS DISTINCT FROM OLD.revision+1 THEN
  RAISE EXCEPTION 'Outbox head identity/revision mismatch' USING ERRCODE='23514';
 END IF;
 RETURN NEW;
END;
$guard$;
REVOKE ALL ON FUNCTION whattodo.guard_creation_delivery_head() FROM PUBLIC;
CREATE TRIGGER guard_version BEFORE UPDATE ON whattodo.creation_delivery_head
FOR EACH ROW EXECUTE FUNCTION whattodo.guard_creation_delivery_head();
CREATE FUNCTION whattodo.guard_creation_delivery_revision() RETURNS trigger
LANGUAGE plpgsql SET search_path=pg_catalog AS $guard$
DECLARE prior whattodo.creation_delivery_revision%ROWTYPE;
BEGIN
 SELECT r.* INTO prior FROM whattodo.creation_delivery_head h
 JOIN whattodo.creation_delivery_revision r USING(event_id,revision) WHERE h.event_id=NEW.event_id;
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
    ((((prior.state='READY' AND prior.available_at<=NEW.changed_at) OR (prior.state='CLAIMED' AND prior.lease_until<=NEW.changed_at))
      AND NEW.attempt=prior.attempt+1 AND NEW.lease_token IS DISTINCT FROM prior.lease_token)
    OR (prior.state='CLAIMED' AND prior.lease_until>NEW.changed_at AND NEW.worker_id=prior.worker_id
      AND NEW.lease_token=prior.lease_token AND NEW.attempt=prior.attempt AND NEW.lease_until>prior.lease_until))) IS NOT TRUE THEN
    RAISE EXCEPTION 'Outbox claim or renewal mismatch' USING ERRCODE='23514';
   END IF;
  ELSE
   IF (prior.state='CLAIMED' AND prior.lease_until>NEW.changed_at AND NEW.attempt=prior.attempt
    AND NEW.settled_worker_id=prior.worker_id AND NEW.settled_token=prior.lease_token AND NEW.settled_revision=prior.revision
    AND (NEW.state<>'READY' OR NEW.available_at>=NEW.changed_at)) IS NOT TRUE THEN
    RAISE EXCEPTION 'Outbox settlement mismatch' USING ERRCODE='23514';
   END IF;
  END IF;
 END IF;
 RETURN NEW;
END;
$guard$;
REVOKE ALL ON FUNCTION whattodo.guard_creation_delivery_revision() FROM PUBLIC;
CREATE TRIGGER guard_append BEFORE INSERT ON whattodo.creation_delivery_revision
FOR EACH ROW EXECUTE FUNCTION whattodo.guard_creation_delivery_revision();
CREATE FUNCTION whattodo.capture_canonical_creation() RETURNS trigger
LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog AS $capture$
DECLARE receipt whattodo.command_transaction%ROWTYPE;
 ident text;
BEGIN
 IF NOT EXISTS(SELECT 1 FROM whattodo.task_identity i WHERE i.task_id=NEW.task_id AND i.transaction_ref=NEW.transaction_ref)
  OR EXISTS(SELECT 1 FROM whattodo.task_payload_revision p WHERE p.task_id=NEW.task_id AND p.task_revision<>NEW.task_revision) THEN
  RETURN NEW;
 END IF;
 SELECT * INTO STRICT receipt FROM whattodo.command_transaction WHERE request_id=NEW.transaction_ref;
 IF receipt.origin NOT IN ('USER_COMMAND','RELATIONSHIP_RULE') THEN
  RAISE EXCEPTION 'Canonical creation origin mismatch' USING ERRCODE='23514';
 END IF;
 ident:='creation:'||encode(sha256(convert_to(NEW.task_id,'UTF8')),'hex');
 INSERT INTO whattodo.canonical_creation_event VALUES(ident,NEW.task_id,NEW.task_revision,NEW.content_hash,
  NEW.transaction_ref,receipt.principal_id,receipt.authority_ref,receipt.committed_at);
 INSERT INTO whattodo.creation_delivery_revision(event_id,revision,state,attempt,changed_at,available_at)
 VALUES(ident,1,'READY',0,receipt.committed_at,receipt.committed_at);
 INSERT INTO whattodo.creation_delivery_head VALUES(ident,1);
 RETURN NEW;
END;
$capture$;
REVOKE ALL ON FUNCTION whattodo.capture_canonical_creation() FROM PUBLIC;
CREATE TRIGGER canonical_creation_outbox AFTER INSERT ON whattodo.task_payload_revision
FOR EACH ROW EXECUTE FUNCTION whattodo.capture_canonical_creation();
COMMIT;
