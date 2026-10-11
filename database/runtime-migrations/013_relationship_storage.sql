-- Additive typed storage metadata. Legacy rows remain explicitly unadmitted.
BEGIN;
SET LOCAL search_path=pg_catalog;
ALTER TABLE whattodo.relationship_rule_revision
ADD COLUMN runtime_payload whattodo.json_object;
ALTER TABLE whattodo.task_relation_revision
ADD COLUMN runtime_payload whattodo.json_object,
ADD COLUMN origin_rule_id whattodo.ref,
ADD COLUMN origin_rule_version whattodo.ref,
ADD CONSTRAINT relation_origin_pair CHECK ((origin_rule_id IS NULL) = (origin_rule_version IS NULL)),
ADD CONSTRAINT relation_exact_origin FOREIGN KEY(origin_rule_id,origin_rule_version)
REFERENCES whattodo.relationship_rule_revision(rule_id,version) DEFERRABLE INITIALLY DEFERRED,
ADD CONSTRAINT relation_membership_parent CHECK
(kind <> 'STAGE_MEMBERSHIP' OR (before_kind='TASK' AND after_kind='STAGE'
AND before_task_id=after_task_id AND before_task_revision=after_task_revision));
COMMIT;
