-- Immutable stage-command journals. Not activated in the runtime manifest yet.
BEGIN;
SET LOCAL search_path=pg_catalog;
ALTER TABLE whattodo.task_payload_revision ADD CONSTRAINT stage_journal_exact_task_hash
UNIQUE(task_id,task_revision,content_hash);
ALTER TABLE whattodo.task_stage_revision ADD CONSTRAINT stage_journal_exact_stage_binding
UNIQUE(task_id,task_revision,stage_id,stage_revision);

CREATE TABLE whattodo.stage_command_journal (
 record_id whattodo.ref PRIMARY KEY,
 command_id whattodo.ref NOT NULL UNIQUE,
 aggregate_kind whattodo.ref NOT NULL CHECK(aggregate_kind IN ('STAGE_TRANSITION','STAGE_PENDING')),
 revision whattodo.revision NOT NULL DEFAULT 1 CHECK(revision=1),
 task_id whattodo.ref NOT NULL,
 before_task_revision whattodo.revision NOT NULL,
 after_task_revision whattodo.revision,
 stage_id whattodo.ref NOT NULL,
 before_stage_revision whattodo.revision NOT NULL,
 after_stage_revision whattodo.revision,
 authority_ref whattodo.ref NOT NULL,
 source_ref whattodo.ref NOT NULL,
 source_observed_at whattodo.instant NOT NULL,
 raw_command bytea NOT NULL CHECK(octet_length(raw_command)>0 AND octet_length(raw_command)<=262144),
 raw_command_hash whattodo.sha256 NOT NULL,
 before_task_hash whattodo.sha256 NOT NULL,
 after_task_hash whattodo.sha256,
 state whattodo.ref NOT NULL CHECK(state IN ('COMMITTED','PENDING')),
 code whattodo.ref NOT NULL CHECK(code ~ '^[A-Z][A-Z0-9_]{0,63}$'),
 transaction_ref whattodo.ref NOT NULL,
 audit_change_ref whattodo.ref NOT NULL,
 runtime_payload whattodo.json_object NOT NULL CHECK(octet_length(runtime_payload::text)<=16777216),
 UNIQUE(record_id,aggregate_kind),
 CHECK(encode(sha256(raw_command),'hex')=raw_command_hash),
 CHECK((convert_from(raw_command,'UTF8')::jsonb=runtime_payload->'command') IS TRUE),
 CHECK((decode(runtime_payload->>'raw_command_base64','base64')=raw_command) IS TRUE),
 CHECK(((runtime_payload->>'source_observed_at')::timestamptz=source_observed_at) IS TRUE),
 CHECK((jsonb_typeof(runtime_payload->'missing_fields')='array'
  AND jsonb_array_length(runtime_payload->'missing_fields')<=100
  AND jsonb_typeof(runtime_payload->'order_snapshot')='object'
  AND runtime_payload-'command'-'missing_fields'-'transition'-'order_snapshot'-'raw_command_base64'-'source_observed_at'
  =jsonb_build_object('schema_version','0.1.0-stage-journal','record_id',record_id,'kind',aggregate_kind,
   'command_fingerprint',substring(record_id from 15),'source_ref',source_ref,'raw_command_hash',raw_command_hash,
   'before_task_hash',before_task_hash,'after_task_hash',after_task_hash,'state',state,'code',code)) IS TRUE),
 CHECK((record_id='stage-journal-'||(runtime_payload->>'command_fingerprint')
  AND runtime_payload->'command'->>'schema_version'='0.1.0-stage-command'
  AND runtime_payload->'command'->>'command_id'=command_id
  AND runtime_payload->'command'->>'origin'='USER_COMMAND'
  AND runtime_payload->'command'->>'authority_ref'=authority_ref
  AND runtime_payload#>'{command,target_ref}'=jsonb_build_object('task_id',task_id,'revision',before_task_revision,
   'stage_id',stage_id,'stage_revision',before_stage_revision)) IS TRUE),
 CHECK(((state='PENDING' AND aggregate_kind='STAGE_PENDING' AND after_task_revision IS NULL
   AND after_stage_revision IS NULL AND after_task_hash IS NULL AND runtime_payload->'transition'='null'::jsonb
   AND jsonb_array_length(runtime_payload->'missing_fields')>0)
  OR (state='COMMITTED' AND aggregate_kind='STAGE_TRANSITION' AND after_task_revision=before_task_revision+1
   AND after_task_hash IS NOT NULL AND after_stage_revision IN (before_stage_revision,before_stage_revision+1)
   AND jsonb_typeof(runtime_payload->'transition')='object' AND runtime_payload->'missing_fields'='[]'::jsonb
   AND runtime_payload#>'{transition,command}'=runtime_payload->'command'
   AND runtime_payload#>>'{transition,command_fingerprint}'=runtime_payload->>'command_fingerprint'
   AND runtime_payload#>>'{transition,source_ref}'=source_ref
   AND runtime_payload#>'{transition,previous_parent_revision}'=to_jsonb(before_task_revision)
   AND runtime_payload#>'{transition,parent_revision}'=to_jsonb(after_task_revision)
   AND runtime_payload#>'{transition,previous_stage_revision}'=to_jsonb(before_stage_revision)
   AND runtime_payload#>'{transition,stage_revision}'=to_jsonb(after_stage_revision)
   AND jsonb_typeof(runtime_payload#>'{transition,issues}')='array')) IS TRUE),
 FOREIGN KEY(task_id,before_task_revision,before_task_hash) REFERENCES whattodo.task_payload_revision(task_id,task_revision,content_hash) DEFERRABLE INITIALLY DEFERRED,
 FOREIGN KEY(task_id,after_task_revision,after_task_hash) REFERENCES whattodo.task_payload_revision(task_id,task_revision,content_hash) DEFERRABLE INITIALLY DEFERRED,
 FOREIGN KEY(task_id,after_task_revision,transaction_ref) REFERENCES whattodo.task_revision(task_id,revision,transaction_ref) DEFERRABLE INITIALLY DEFERRED,
 FOREIGN KEY(task_id,before_task_revision,stage_id,before_stage_revision) REFERENCES whattodo.task_stage_revision(task_id,task_revision,stage_id,stage_revision) DEFERRABLE INITIALLY DEFERRED,
 FOREIGN KEY(task_id,after_task_revision,stage_id,after_stage_revision) REFERENCES whattodo.task_stage_revision(task_id,task_revision,stage_id,stage_revision) DEFERRABLE INITIALLY DEFERRED,
 FOREIGN KEY(source_ref) REFERENCES whattodo.source_record(record_id) DEFERRABLE INITIALLY DEFERRED,
 FOREIGN KEY(authority_ref) REFERENCES whattodo.authority_record(authority_ref) DEFERRABLE INITIALLY DEFERRED,
 FOREIGN KEY(transaction_ref) REFERENCES whattodo.command_transaction(request_id) DEFERRABLE INITIALLY DEFERRED,
 FOREIGN KEY(audit_change_ref,aggregate_kind,record_id,revision,transaction_ref)
 REFERENCES whattodo.audit_change(change_id,aggregate_kind,aggregate_id,after_revision,request_id) DEFERRABLE INITIALLY DEFERRED
);
CREATE TABLE whattodo.stage_relationship_issue (
 issue_id whattodo.ref PRIMARY KEY,
 transition_ref whattodo.ref NOT NULL,
 transition_kind whattodo.ref NOT NULL DEFAULT 'STAGE_TRANSITION' CHECK(transition_kind='STAGE_TRANSITION'),
 relation_id whattodo.ref NOT NULL,
 relation_revision whattodo.revision NOT NULL,
 code whattodo.ref NOT NULL CHECK(code IN ('PREREQUISITE_INCOMPLETE','ORDER_EVIDENCE_MISSING','ORDER_VIOLATION')),
 kind whattodo.ref NOT NULL CHECK(kind IN ('COMPLETION_ORDER','START_PREREQUISITE')),
 aggregate_kind whattodo.ref NOT NULL DEFAULT 'STAGE_RELATIONSHIP_ISSUE' CHECK(aggregate_kind='STAGE_RELATIONSHIP_ISSUE'),
 revision whattodo.revision NOT NULL DEFAULT 1 CHECK(revision=1),
 transaction_ref whattodo.ref NOT NULL,
 audit_change_ref whattodo.ref NOT NULL,
 runtime_payload whattodo.json_object NOT NULL,
 UNIQUE(transition_ref,relation_id,relation_revision,code),
 CHECK(runtime_payload=jsonb_build_object('issue_id',issue_id,'transition_ref',transition_ref,'relation_id',relation_id,
  'relation_revision',relation_revision,'code',code,'kind',kind)),
 FOREIGN KEY(transition_ref,transition_kind) REFERENCES whattodo.stage_command_journal(record_id,aggregate_kind) DEFERRABLE INITIALLY DEFERRED,
 FOREIGN KEY(relation_id,relation_revision) REFERENCES whattodo.task_relation_revision(relation_id,revision) DEFERRABLE INITIALLY DEFERRED,
 FOREIGN KEY(audit_change_ref,aggregate_kind,issue_id,revision,transaction_ref)
 REFERENCES whattodo.audit_change(change_id,aggregate_kind,aggregate_id,after_revision,request_id) DEFERRABLE INITIALLY DEFERRED
);
CREATE TABLE whattodo.stage_pending_resolution (
 resolution_id whattodo.ref PRIMARY KEY,
 pending_ref whattodo.ref NOT NULL UNIQUE,
 pending_kind whattodo.ref NOT NULL DEFAULT 'STAGE_PENDING' CHECK(pending_kind='STAGE_PENDING'),
 transition_ref whattodo.ref NOT NULL,
 transition_kind whattodo.ref NOT NULL DEFAULT 'STAGE_TRANSITION' CHECK(transition_kind='STAGE_TRANSITION'),
 aggregate_kind whattodo.ref NOT NULL DEFAULT 'STAGE_PENDING_RESOLUTION' CHECK(aggregate_kind='STAGE_PENDING_RESOLUTION'),
 revision whattodo.revision NOT NULL DEFAULT 1 CHECK(revision=1),
 transaction_ref whattodo.ref NOT NULL,
 audit_change_ref whattodo.ref NOT NULL,
 runtime_payload whattodo.json_object NOT NULL,
 CHECK(runtime_payload=jsonb_build_object('resolution_id',resolution_id,'pending_ref',pending_ref,'transition_ref',transition_ref)),
 FOREIGN KEY(pending_ref,pending_kind) REFERENCES whattodo.stage_command_journal(record_id,aggregate_kind) DEFERRABLE INITIALLY DEFERRED,
 FOREIGN KEY(transition_ref,transition_kind) REFERENCES whattodo.stage_command_journal(record_id,aggregate_kind) DEFERRABLE INITIALLY DEFERRED,
 FOREIGN KEY(audit_change_ref,aggregate_kind,resolution_id,revision,transaction_ref)
 REFERENCES whattodo.audit_change(change_id,aggregate_kind,aggregate_id,after_revision,request_id) DEFERRABLE INITIALLY DEFERRED
);
CREATE TRIGGER preserve_history BEFORE UPDATE OR DELETE OR TRUNCATE ON whattodo.stage_command_journal
FOR EACH STATEMENT EXECUTE FUNCTION whattodo.reject_history_mutation();
CREATE TRIGGER preserve_history BEFORE UPDATE OR DELETE OR TRUNCATE ON whattodo.stage_relationship_issue
FOR EACH STATEMENT EXECUTE FUNCTION whattodo.reject_history_mutation();
CREATE TRIGGER preserve_history BEFORE UPDATE OR DELETE OR TRUNCATE ON whattodo.stage_pending_resolution
FOR EACH STATEMENT EXECUTE FUNCTION whattodo.reject_history_mutation();

CREATE FUNCTION whattodo.check_stage_command_journal() RETURNS trigger
LANGUAGE plpgsql SET search_path=pg_catalog AS $guard$
DECLARE txn whattodo.command_transaction%ROWTYPE; root whattodo.authority_record%ROWTYPE;
 permit whattodo.authority_record%ROWTYPE; change whattodo.audit_change%ROWTYPE;
BEGIN
 SELECT * INTO txn FROM whattodo.command_transaction WHERE request_id=NEW.transaction_ref;
 SELECT * INTO root FROM whattodo.authority_record WHERE authority_ref=NEW.authority_ref;
 SELECT * INTO permit FROM whattodo.authority_record WHERE authority_ref=txn.authority_ref;
 SELECT * INTO change FROM whattodo.audit_change WHERE change_id=NEW.audit_change_ref;
 IF txn.request_id IS DISTINCT FROM NEW.command_id OR txn.origin IS DISTINCT FROM 'USER_COMMAND'
  OR txn.principal_id IS DISTINCT FROM (NEW.runtime_payload#>>'{command,principal_id}')
  OR root.principal_id IS DISTINCT FROM txn.principal_id OR root.origin IS DISTINCT FROM 'USER_COMMAND'
  OR root.source_record_ref IS DISTINCT FROM NEW.source_ref
  OR root.resolved_scope_hash IS DISTINCT FROM (NEW.runtime_payload->>'command_fingerprint')
  OR root.resolved_scope IS DISTINCT FROM jsonb_build_object('contract','stage-command',
   'command',NEW.runtime_payload->'command','active',true,'source_observed_at',NEW.runtime_payload->'source_observed_at')
  OR root.issued_at>txn.committed_at OR (root.expires_at IS NOT NULL AND txn.committed_at>=root.expires_at)
  OR NEW.source_observed_at>txn.committed_at
  OR NOT EXISTS(SELECT 1 FROM whattodo.source_record r JOIN whattodo.source_identity s USING(source_id)
   WHERE r.record_id=NEW.source_ref AND r.captured_at=NEW.source_observed_at AND s.source_type='USER')
  OR permit.principal_id IS DISTINCT FROM txn.principal_id OR permit.origin IS DISTINCT FROM txn.origin
  OR permit.source_record_ref IS DISTINCT FROM NEW.source_ref OR permit.resolved_scope_hash IS DISTINCT FROM txn.request_hash
  OR permit.resolved_scope->>'scope_kind' IS DISTINCT FROM 'EXACT_TRANSACTION'
  OR permit.resolved_scope->>'request_fingerprint' IS DISTINCT FROM txn.request_hash
  OR permit.resolved_scope#>>'{authorization,contract}' IS DISTINCT FROM 'stage-command'
  OR permit.resolved_scope#>>'{authorization,grant_ref}' IS DISTINCT FROM NEW.authority_ref
  OR permit.resolved_scope#>>'{authorization,command_fingerprint}' IS DISTINCT FROM (NEW.runtime_payload->>'command_fingerprint')
  OR permit.issued_at>txn.committed_at OR permit.expires_at IS NULL OR txn.committed_at>=permit.expires_at
  OR change.after_value IS DISTINCT FROM NEW.runtime_payload OR change.before_revision IS NOT NULL
  OR change.before_value IS NOT NULL OR change.after_revision IS DISTINCT FROM 1
  OR change.audit_id IS DISTINCT FROM txn.audit_id
  OR NOT EXISTS(SELECT 1 FROM whattodo.command_transaction c WHERE c.request_id=txn.request_id
   AND c.xmin::text::numeric=(pg_current_xact_id()::text::numeric % 4294967296))
  OR NOT EXISTS(SELECT 1 FROM whattodo.audit_change a WHERE a.change_id=NEW.audit_change_ref
   AND a.xmin::text::numeric=(pg_current_xact_id()::text::numeric % 4294967296))
 THEN RAISE EXCEPTION 'Stage command exact source/authority/transaction mismatch' USING ERRCODE='23514'; END IF;
 IF NEW.state='PENDING' AND EXISTS(SELECT 1 FROM whattodo.audit_change a
  WHERE a.request_id=NEW.transaction_ref AND a.aggregate_kind='TASK') THEN
  RAISE EXCEPTION 'Pending stage command cannot change a Task' USING ERRCODE='23514';
 END IF;
 IF NEW.state='COMMITTED' AND NOT EXISTS(SELECT 1 FROM whattodo.audit_change a
  WHERE a.request_id=NEW.transaction_ref AND a.aggregate_kind='TASK' AND a.aggregate_id=NEW.task_id
   AND a.before_revision=NEW.before_task_revision AND a.after_revision=NEW.after_task_revision) THEN
  RAISE EXCEPTION 'Stage transition requires the same audited parent transaction' USING ERRCODE='23514';
 END IF;
 RETURN NEW;
END;
$guard$;
REVOKE ALL ON FUNCTION whattodo.check_stage_command_journal() FROM PUBLIC;
CREATE CONSTRAINT TRIGGER exact_stage_command AFTER INSERT ON whattodo.stage_command_journal
DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION whattodo.check_stage_command_journal();

CREATE FUNCTION whattodo.check_stage_command_child() RETURNS trigger
LANGUAGE plpgsql SET search_path=pg_catalog AS $guard$
DECLARE event whattodo.stage_command_journal%ROWTYPE; pending whattodo.stage_command_journal%ROWTYPE;
 change whattodo.audit_change%ROWTYPE;
BEGIN
 SELECT * INTO event FROM whattodo.stage_command_journal WHERE record_id=NEW.transition_ref;
 SELECT * INTO change FROM whattodo.audit_change WHERE change_id=NEW.audit_change_ref;
 IF event.state IS DISTINCT FROM 'COMMITTED' OR event.transaction_ref IS DISTINCT FROM NEW.transaction_ref
  OR change.after_value IS DISTINCT FROM NEW.runtime_payload OR change.before_revision IS NOT NULL
  OR change.before_value IS NOT NULL OR change.after_revision IS DISTINCT FROM 1 THEN
  RAISE EXCEPTION 'Stage child requires its exact transition/audit transaction' USING ERRCODE='23514';
 END IF;
 IF TG_TABLE_NAME='stage_relationship_issue' THEN
  IF NOT (event.runtime_payload#>'{transition,issues}' @> jsonb_build_array(NEW.runtime_payload-'issue_id'-'transition_ref'))
   OR NOT EXISTS(SELECT 1 FROM whattodo.task_relation_revision r WHERE r.relation_id=NEW.relation_id
    AND r.revision=NEW.relation_revision AND r.kind=NEW.kind AND r.after_stage_id=event.stage_id
    AND r.after_task_id=event.task_id) THEN
   RAISE EXCEPTION 'Stage issue must match actual incoming hard relation' USING ERRCODE='23514';
  END IF;
 ELSE
  SELECT * INTO pending FROM whattodo.stage_command_journal WHERE record_id=NEW.pending_ref;
  IF pending.state IS DISTINCT FROM 'PENDING' OR pending.task_id IS DISTINCT FROM event.task_id
   OR pending.stage_id IS DISTINCT FROM event.stage_id OR pending.before_stage_revision IS DISTINCT FROM event.before_stage_revision
   OR pending.before_task_revision>event.before_task_revision
   OR pending.runtime_payload#>>'{command,principal_id}' IS DISTINCT FROM event.runtime_payload#>>'{command,principal_id}'
   OR pending.runtime_payload#>>'{command,operation}' IS DISTINCT FROM event.runtime_payload#>>'{command,operation}'
   OR pending.runtime_payload#>>'{command,fields,intent}' IN ('CORRECTION','NEW_OBLIGATION') THEN
   RAISE EXCEPTION 'Pending resolution scope mismatch' USING ERRCODE='23514';
  END IF;
 END IF;
 RETURN NEW;
END;
$guard$;
REVOKE ALL ON FUNCTION whattodo.check_stage_command_child() FROM PUBLIC;
CREATE CONSTRAINT TRIGGER exact_stage_issue AFTER INSERT ON whattodo.stage_relationship_issue
DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION whattodo.check_stage_command_child();
CREATE CONSTRAINT TRIGGER exact_stage_resolution AFTER INSERT ON whattodo.stage_pending_resolution
DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION whattodo.check_stage_command_child();
COMMIT;
