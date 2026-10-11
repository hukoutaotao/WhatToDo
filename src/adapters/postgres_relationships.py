"""Owner-only relationship cache/transaction port with independently stored scope.

Rule registration requires a matching immutable Git definition and source-backed
authority. Relation append is called inside the caller's audited transaction;
it does not publish a receipt, change the epoch or resolve graph feasibility.
"""
from src.adapters.postgres_migrations import (
    _owner, _snapshot, _legacy_receipts, schema_checked_transaction, LOCK_KEY)
from src.application.migrations import check_history
from src.application.definitions import DefinitionKey, identity
from src.application.evidence_storage import SourceScope
from src.application.relationship_storage import (
    RuleStorageRecord, RelationStorageRecord, EndpointBinding,
    RelationshipStorageError, acceptance_scope, digest, require)
from src.domain.authorization import CallerIdentity
from src.domain.relationships import RelationshipRule, TaskRelation, Endpoint, FieldMapping

RELATIONSHIP_LOCK = LOCK_KEY + 12


def rule_from_payload(payload):
    value = dict(payload['rule']); value.pop('schema_version')
    value['essential_fields'] = tuple(value['essential_fields'])
    value['mappings'] = tuple(FieldMapping(**item) for item in value['mappings'])
    return RuleStorageRecord(RelationshipRule(**value),
                             *(DefinitionKey(**item) for item in payload['references']))


def relation_from_payload(payload):
    value = dict(payload['relation']); value.pop('schema_version')
    value['before'] = Endpoint(**value['before']); value['after'] = Endpoint(**value['after'])
    bindings = []
    for name in ('before', 'after'):
        binding = dict(payload[name]); binding['endpoint'] = Endpoint(**binding['endpoint'])
        bindings.append(EndpointBinding(**binding))
    return RelationStorageRecord(TaskRelation(**value), *bindings)


class PostgresRelationshipRepository:
    def __init__(self, connection, plan, roles, *, application_version, caller, source_scopes, clock):
        require(isinstance(caller, CallerIdentity) and caller.authenticated and caller.origin == 'USER_COMMAND',
                'RELATIONSHIP_TRUSTED_CALLER')
        require(isinstance(source_scopes, tuple) and source_scopes and
                all(isinstance(s, SourceScope) for s in source_scopes), 'RELATIONSHIP_SOURCE_REGISTRY')
        self.connection = connection; self.plan = plan; self.roles = roles
        self.application_version = application_version; self.caller = caller
        self.scopes = source_scopes; self.clock = clock

    def _visible(self, ref):
        row = self.connection.execute('''SELECT a.principal_id,s.source_type,s.provider,s.scope_ref,p.account_ref
            FROM whattodo.authority_record a JOIN whattodo.source_record r ON r.record_id=a.source_record_ref
            JOIN whattodo.source_identity s USING(source_id)
            JOIN whattodo.source_scope p USING(provider,scope_ref) WHERE a.authority_ref=%s''', (ref,)).fetchone()
        require(row is not None and row[0] == self.caller.principal_id, 'RELATIONSHIP_FOREIGN_PRINCIPAL')
        require(row[1] == 'USER' and any((s.provider,s.scope_ref,s.account_ref) == row[2:] for s in self.scopes),
                'RELATIONSHIP_FOREIGN_SOURCE_SCOPE')

    def _authority(self, ref, kind, record):
        row = self.connection.execute('''SELECT a.principal_id,a.origin,a.resolved_scope_hash,
            a.resolved_scope,a.issued_at,a.expires_at,s.source_type,s.provider,s.scope_ref,p.account_ref
            FROM whattodo.authority_record a JOIN whattodo.source_record r ON r.record_id=a.source_record_ref
            JOIN whattodo.source_identity s USING(source_id)
            JOIN whattodo.source_scope p USING(provider,scope_ref) WHERE a.authority_ref=%s''', (ref,)).fetchone()
        scope = acceptance_scope(kind, record); now = self.clock.now()
        require(row is not None and row[:4] == (self.caller.principal_id, 'USER_COMMAND', digest(scope), scope)
                and row[4] <= now and (row[5] is None or now < row[5]) and row[6] == 'USER'
                and any((s.provider, s.scope_ref, s.account_ref) == row[7:] for s in self.scopes),
                'RELATIONSHIP_AUTHORITY_SCOPE_MISMATCH')

    def _cached_rule(self, record):
        key = record.key
        row = self.connection.execute('SELECT raw_bytes FROM whattodo.definition_cache WHERE kind=%s AND id=%s AND version=%s',
                                      (key.kind, key.id, key.version)).fetchone()
        from src.application.definitions import strict_json
        require(row is not None and strict_json(bytes(row[0]))['body'] == record.payload,
                'RELATIONSHIP_GIT_DEFINITION_MISMATCH')
        for ref in (record.source_type, record.target_type, record.template):
            require(self.connection.execute('SELECT EXISTS(SELECT 1 FROM whattodo.definition_cache WHERE kind=%s AND id=%s AND version=%s)',
                    (ref.kind, ref.id, ref.version)).fetchone() == (True,), 'RELATIONSHIP_UNRESOLVED_DEFINITION')

    def register_rule(self, record):
        require(isinstance(record, RuleStorageRecord), 'RELATIONSHIP_TYPED_RULE_REQUIRED')
        from psycopg import Error
        from psycopg.types.json import Jsonb
        try:
            with schema_checked_transaction(self.connection, self.plan,
                    application_version=self.application_version, read_only=False):
                _owner(self.connection, self.roles)
                require(self.connection.execute('SELECT pg_try_advisory_xact_lock(%s)', (RELATIONSHIP_LOCK,)).fetchone() == (True,),
                        'RELATIONSHIP_WRITE_BUSY')
                self._cached_rule(record)
                self._authority(record.rule.acceptance_ref, 'RULE', record)
                row = self.connection.execute('SELECT runtime_payload FROM whattodo.relationship_rule_revision WHERE rule_id=%s AND version=%s',
                                              (record.rule.rule_id, record.rule.version)).fetchone()
                if row is not None:
                    require(row[0] == record.payload, 'RELATIONSHIP_RULE_IMMUTABLE_CONFLICT')
                    return record
                r = record.rule
                self.connection.execute('''INSERT INTO whattodo.relationship_rule_revision
                    (rule_id,version,active,acceptance_ref,configuration_ref,trigger_kind,source_type_ref,
                     target_type_ref,template_ref,template_version,target_role,obligation_kind,mappings,runtime_payload)
                    VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)''',
                    (r.rule_id,r.version,r.active,r.acceptance_ref,record.key.configuration_ref,r.trigger,
                     record.source_type.configuration_ref,record.target_type.configuration_ref,
                     record.template.configuration_ref,r.target_template_version,r.target_role,r.obligation_kind,
                     Jsonb(dict(essential_fields=list(r.essential_fields), bindings=r.as_record()['mappings'])), Jsonb(record.payload)))
                return record
        except Error:
            raise RelationshipStorageError('RELATIONSHIP_STORAGE_FAILED') from None

    def get_rule(self, rule_id, version):
        require(identity(rule_id) and identity(version), 'RELATIONSHIP_RULE_ID')
        with schema_checked_transaction(self.connection, self.plan, application_version=self.application_version):
            row = self.connection.execute('''SELECT r.runtime_payload,a.principal_id,r.acceptance_ref FROM whattodo.relationship_rule_revision r
                JOIN whattodo.authority_record a ON a.authority_ref=r.acceptance_ref WHERE rule_id=%s AND version=%s''', (rule_id,version)).fetchone()
            require(row is None or row[1] == self.caller.principal_id, 'RELATIONSHIP_FOREIGN_PRINCIPAL')
            if row is not None: self._visible(row[2])
            return rule_from_payload(row[0]) if row and row[0] is not None else None

    def get_relation(self, relation_id, revision=None):
        require(identity(relation_id) and (revision is None or type(revision) is int and revision > 0), 'RELATIONSHIP_RELATION_ID')
        with schema_checked_transaction(self.connection, self.plan, application_version=self.application_version):
            row = self.connection.execute('''SELECT r.runtime_payload,a.principal_id,r.acceptance_ref FROM whattodo.task_relation_revision r
                JOIN whattodo.authority_record a ON a.authority_ref=r.acceptance_ref
                WHERE relation_id=%s AND (%s::bigint IS NULL OR revision=%s) ORDER BY revision DESC LIMIT 1''',
                (relation_id,revision,revision)).fetchone()
            require(row is None or row[1] == self.caller.principal_id, 'RELATIONSHIP_FOREIGN_PRINCIPAL')
            if row is not None: self._visible(row[2])
            return relation_from_payload(row[0]) if row and row[0] is not None else None

    def append_relation_in_transaction(self, record, transaction_ref):
        require(isinstance(record, RelationStorageRecord) and identity(transaction_ref), 'RELATIONSHIP_TYPED_WRITE')
        from psycopg.pq import TransactionStatus
        from psycopg.types.json import Jsonb
        require(self.connection.info.transaction_status == TransactionStatus.INTRANS,
                'RELATIONSHIP_ENCLOSING_TRANSACTION_REQUIRED')
        _owner(self.connection, self.roles)
        require(self.connection.execute('SELECT pg_try_advisory_xact_lock_shared(%s)', (LOCK_KEY,)).fetchone() == (True,),
                'RELATIONSHIP_MIGRATION_BUSY')
        snapshot = _snapshot(self.connection)
        require(snapshot is not None, 'RELATIONSHIP_SCHEMA_REQUIRED')
        check_history(self.plan, *snapshot, application_version=self.application_version, complete=True)
        _legacy_receipts(self.connection, self.plan, snapshot[0])
        require(self.connection.execute('SELECT pg_try_advisory_xact_lock(%s)', (RELATIONSHIP_LOCK,)).fetchone() == (True,),
                'RELATIONSHIP_WRITE_BUSY')
        r = record.relation; self._authority(r.authority_ref, 'RELATION', record)
        receipt = self.connection.execute('SELECT principal_id,origin,authority_ref FROM whattodo.command_transaction WHERE request_id=%s',
                                          (transaction_ref,)).fetchone()
        require(receipt == (self.caller.principal_id, 'USER_COMMAND', r.authority_ref), 'RELATIONSHIP_TRANSACTION_SCOPE')
        audit = self.connection.execute('''SELECT after_value FROM whattodo.audit_change
            WHERE request_id=%s AND aggregate_kind='TASK_RELATION' AND aggregate_id=%s AND after_revision=%s''',
            (transaction_ref,r.relation_id,r.revision)).fetchall()
        require(audit == [(record.payload,)], 'RELATIONSHIP_AUDIT_REQUIRED')
        for binding in (record.before,record.after):
            owner = self.connection.execute('''SELECT a.principal_id FROM whattodo.task_revision t
                JOIN whattodo.authority_record a ON a.authority_ref=t.acceptance_ref
                WHERE task_id=%s AND revision=%s''', (binding.task_id,binding.task_revision)).fetchone()
            require(owner == (self.caller.principal_id,), 'RELATIONSHIP_TARGET_NOT_OWNED')
            if binding.endpoint.kind == 'STAGE':
                require(self.connection.execute('''SELECT EXISTS(SELECT 1 FROM whattodo.stage_revision
                    WHERE stage_id=%s AND revision=%s AND task_id=%s AND task_revision=%s)''',
                    (binding.endpoint.id,binding.stage_revision,binding.task_id,binding.task_revision)).fetchone() == (True,),
                    'RELATIONSHIP_STAGE_NOT_RESOLVED')
        if r.origin_rule_id is not None:
            origin = self.connection.execute('''SELECT runtime_payload,a.principal_id FROM whattodo.relationship_rule_revision r
                JOIN whattodo.authority_record a ON a.authority_ref=r.acceptance_ref WHERE rule_id=%s AND version=%s''',
                (r.origin_rule_id,r.origin_rule_version)).fetchone()
            require(origin is not None and origin[0] is not None and origin[1] == self.caller.principal_id,
                    'RELATIONSHIP_ORIGIN_NOT_RESOLVED')
        old = self.connection.execute('SELECT revision,runtime_payload,transaction_ref FROM whattodo.task_relation_revision WHERE relation_id=%s ORDER BY revision DESC LIMIT 1',
                                      (r.relation_id,)).fetchone()
        if old is not None and old == (r.revision,record.payload,transaction_ref): return record
        require(r.revision == (1 if old is None else old[0]+1), 'RELATIONSHIP_STALE_REVISION')
        b,a = record.before,record.after
        self.connection.execute('''INSERT INTO whattodo.task_relation_revision
            (relation_id,revision,kind,before_kind,before_task_id,before_task_revision,before_stage_id,before_stage_revision,
             after_kind,after_task_id,after_task_revision,after_stage_id,after_stage_revision,acceptance_ref,transaction_ref,
             runtime_payload,origin_rule_id,origin_rule_version) VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)''',
            (r.relation_id,r.revision,r.kind,b.endpoint.kind,b.task_id,b.task_revision,b.endpoint.id if b.endpoint.kind=='STAGE' else None,b.stage_revision,
             a.endpoint.kind,a.task_id,a.task_revision,a.endpoint.id if a.endpoint.kind=='STAGE' else None,a.stage_revision,r.authority_ref,transaction_ref,
             Jsonb(record.payload),r.origin_rule_id,r.origin_rule_version))
        return record
