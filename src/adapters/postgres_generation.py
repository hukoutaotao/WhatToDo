"""Application-role generation: independent scope, exact atomic effects and replay.

Only event/rule identities enter the handler. Policy, caller and definition
repository are independently injected; supplied drafts or permits are rejected.
"""
from datetime import timedelta

from src.adapters.postgres_creation_outbox import EVENT_COLUMNS
from src.adapters.postgres_definitions import PostgresDefinitionRepository
from src.adapters.postgres_evidence import PostgresEvidenceRepository
from src.adapters.postgres_migrations import schema_checked_transaction
from src.adapters.postgres_relationships import rule_from_payload, relation_from_payload
from src.adapters.postgres_tasks import PostgresTaskRepository
from src.adapters.postgres_transactions import PostgresTransactionCoordinator
from src.application.command_ledger import receipt_from_row, validate_audit_fingerprint, validate_caller
from src.application.creation_outbox import CreationEvent
from src.application.creation_outbox import DeliveryLease
from src.application.definitions import DefinitionKey, canonical, identity, strict_json
from src.application.generation_commit import GenerationOccurrenceRecord, generation_scope, prepare_generation_commit, digest
from src.application.generation_evaluator import GenerationSource, AcceptedGenerationRule, require
from src.application.generation_runtime import GenerationPolicy, GenerationOutcome
from src.application.migrations import MigrationError
from src.application.ports import PortResult, TransactionPermit
from src.application.relationship_storage import acceptance_scope
from src.application.relationship_validation import GraphSnapshot, EndpointFact, validate_relationship_graph
from src.application.task_storage import TaskStorageBindings
from src.application.transactions import valid_permit
from src.domain.relationships import Endpoint


class _Definitions:
    """Read validated immutable cache values inside the enclosing snapshot."""
    def __init__(self, repository): self.repository = repository
    def get(self, key): return self.repository._record(key)


class PostgresGenerationHandler:
    def __init__(self, connection, codec, plan, *, application_version, clock, policy, definitions=None):
        require(isinstance(policy, GenerationPolicy), 'GENERATION_TRUSTED_POLICY_REQUIRED')
        require(definitions is None or isinstance(definitions, PostgresDefinitionRepository)
            and definitions.connection is connection and definitions.plan == plan,
            'GENERATION_TRUSTED_DEFINITION_REPOSITORY')
        self.connection = connection; self.codec = codec; self.plan = plan
        self.application_version = application_version; self.clock = clock; self.policy = policy
        self.definitions = _Definitions(definitions) if definitions is not None else None
        self.reader = PostgresTaskRepository(connection, codec, plan, application_version=application_version, clock=clock)
        self.evidence = PostgresEvidenceRepository(connection, codec, plan, application_version=application_version,
            clock=clock, scopes=policy.source_scopes)
        self._receipts = {}

    def _source_evidence(self, ref):
        record = self.evidence._source(ref)
        require(record is not None and record.source.source_type == 'USER'
            and record.source.captured_at <= self.clock.now(), 'GENERATION_USER_SOURCE_REQUIRED')
        return record.source

    def _authority(self, ref, *, at=None):
        row = self.connection.execute('''SELECT principal_id,origin,source_record_ref,resolved_scope_hash,
            resolved_scope,issued_at,expires_at FROM whattodo.authority_record WHERE authority_ref=%s''', (ref,)).fetchone()
        require(row is not None and row[0] == self.policy.principal_id, 'GENERATION_AUTHORITY_PRINCIPAL')
        self._source_evidence(row[2])
        if at is not None:
            require(row[5] <= at and (row[6] is None or at < row[6]), 'GENERATION_AUTHORITY_INACTIVE')
        return row

    def _rule(self, key, *, at=None):
        row = self.connection.execute('SELECT runtime_payload FROM whattodo.relationship_rule_revision WHERE rule_id=%s AND version=%s',
            (key.id, key.version)).fetchone()
        require(row is not None and isinstance(row[0], dict), 'GENERATION_RULE_NOT_ADMITTED')
        record = rule_from_payload(row[0]); require(record.key == key, 'GENERATION_RULE_CACHE_DRIFT')
        root = self._authority(record.rule.acceptance_ref, at=at)
        scope = acceptance_scope('RULE', record)
        require(root[1] == 'USER_COMMAND' and (root[3], root[4]) == (digest(scope), scope), 'GENERATION_RULE_AUTHORITY_SCOPE')
        cached = self.definitions.get(key)
        require(cached is not None and cached.body == record.payload, 'GENERATION_RULE_DEFINITION_DRIFT')
        return AcceptedGenerationRule(record, root[0], root[2], root[5])

    def _occurrence(self, key, revision=None):
        table = 'generation_occurrence' if revision is None else 'generation_occurrence_revision'
        from psycopg import sql
        condition = sql.SQL('generation_key=%s') + (sql.SQL(' AND revision=%s') if revision is not None else sql.SQL(''))
        row = self.connection.execute(sql.SQL('SELECT runtime_payload,transaction_ref,audit_change_ref FROM whattodo.{} WHERE ').format(
            sql.Identifier(table)) + condition, (key,) if revision is None else (key, revision)).fetchone()
        if row is None: return None
        require(isinstance(row[0], dict), 'GENERATION_LEGACY_OCCURRENCE_NOT_ADMITTED')
        record = GenerationOccurrenceRecord.from_payload(row[0]); require(record.scope.generation_key == key, 'GENERATION_OCCURRENCE_DRIFT')
        require(revision is None or record.revision == revision, 'GENERATION_OCCURRENCE_DRIFT')
        values = record.sql_row(row[1], row[2])
        actual = self.connection.execute(sql.SQL('SELECT {} FROM whattodo.{} WHERE ').format(
            sql.SQL(',').join(map(sql.Identifier, values)), sql.Identifier(table)) + condition,
            (key,) if revision is None else (key, revision)).fetchone()
        require(actual == tuple(values.values()), 'GENERATION_OCCURRENCE_PROJECTION_DRIFT')
        if revision is None:
            require(self._occurrence(key, record.revision) == (record, row[1], row[2]), 'GENERATION_OCCURRENCE_HISTORY_DRIFT')
        return record, row[1], row[2]

    def _source(self, event_id, depth=0):
        require(depth <= self.policy.limits.max_generation_depth, 'GENERATION_RECEIPT_DEPTH_LIMIT')
        row = self.connection.execute('SELECT ' + EVENT_COLUMNS + ' FROM whattodo.canonical_creation_event e WHERE event_id=%s',
            (event_id,)).fetchone()
        require(row is not None, 'GENERATION_CANONICAL_EVENT_REQUIRED')
        event = CreationEvent(*row)
        require(event.principal_id == self.policy.principal_id and event.occurred_at <= self.clock.now(), 'GENERATION_SOURCE_PRINCIPAL_OR_TIME')
        receipt, annotation, source_ref = self._receipt(event.creation_transaction_ref, depth=depth)
        require(receipt.request_id == event.creation_transaction_ref, 'GENERATION_SOURCE_RECEIPT_DRIFT')
        record = self.reader._get_in_transaction(event.task_id, event.task_revision)
        require(record is not None, 'GENERATION_ORIGINAL_SOURCE_REQUIRED')
        root_ref = record.aggregate.as_record()['core']['acceptance']['authority_ref']
        root = self._authority(root_ref, at=event.occurred_at)
        if 'command' in annotation:
            require(root[1] == 'USER_COMMAND' and root[4].get('active') is True
                and root[4].get('command') == annotation['command'] and root[3] == annotation.get('command_fingerprint'),
                'GENERATION_SOURCE_ROOT_SCOPE')
        else:
            generation = annotation.get('generation', {})
            require(generation.get('state') == 'CREATED' and generation.get('target_task_ref') == event.task_id
                and generation.get('manifest', {}).get('authority_ref') == root_ref, 'GENERATION_SOURCE_ROOT_SCOPE')
        return GenerationSource(event, record, source_ref, canonical(annotation))

    def _receipt(self, request_id, depth=0):
        require(depth <= self.policy.limits.max_generation_depth, 'GENERATION_RECEIPT_DEPTH_LIMIT')
        if request_id in self._receipts: return self._receipts[request_id]
        row = self.connection.execute('''SELECT request_hash,principal_id,origin,authority_ref,expected_store_revision,
            committed_store_revision,audit_id,committed_at,receipt FROM whattodo.command_transaction WHERE request_id=%s''', (request_id,)).fetchone()
        require(row is not None and row[1] == self.policy.principal_id, 'GENERATION_RECEIPT_NOT_OWNED')
        fingerprint, principal, origin, authority, epoch, committed, aid, at, body = row
        root = self._authority(authority, at=at)
        require(root[:4] == (principal, origin, root[2], fingerprint) and root[4].get('scope_kind') == 'EXACT_TRANSACTION'
            and root[4].get('request_fingerprint') == fingerprint, 'GENERATION_RECEIPT_AUTHORITY_DRIFT')
        annotation = root[4].get('authorization'); require(isinstance(annotation, dict), 'GENERATION_RECEIPT_ANNOTATION')
        if origin == 'USER_COMMAND':
            from src.domain.authorization import CallerIdentity
            coordinator = PostgresTransactionCoordinator(self.connection, self.codec, self.plan,
                application_version=self.application_version, clock=self.clock)
            receipt = coordinator._lookup_in_transaction(request_id, CallerIdentity(principal, origin, True))
        else:
            require(origin == 'RELATIONSHIP_RULE', 'GENERATION_RECEIPT_ORIGIN')
            receipt = receipt_from_row(body, request_id=request_id, request_hash=fingerprint, store_revision=committed, audit_id=aid)
            audit = self.connection.execute('SELECT source_record_ref,correlation_ref,committed_at FROM whattodo.audit_entry WHERE request_id=%s AND audit_id=%s',
                (request_id, aid)).fetchone()
            require(audit is not None and audit[0] == root[2] and audit[2] == at, 'GENERATION_RECEIPT_AUDIT_DRIFT')
            changes = tuple(self.connection.execute('''SELECT aggregate_kind,aggregate_id,before_revision,after_revision,before_value,after_value
                FROM whattodo.audit_change WHERE request_id=%s AND audit_id=%s ORDER BY aggregate_kind,aggregate_id''', (request_id, aid)).fetchall())
            validate_audit_fingerprint(receipt, principal_id=principal, expected_store_revision=epoch,
                source_ref=root[2], correlation_ref=audit[1], changes=changes)
            occurrence_changes = [c for c in changes if c[0] == 'GENERATION_OCCURRENCE']
            require(len(occurrence_changes) == 1 and len(changes) <= 3, 'GENERATION_RECEIPT_EFFECT_SCOPE')
            _, key, before, after, old, value = occurrence_changes[0]
            observed = self._occurrence(key, after)
            require(observed is not None and observed[0].payload == value and observed[1] == request_id
                and annotation.get('generation') == value, 'GENERATION_RECEIPT_OCCURRENCE_DRIFT')
            record = observed[0]; use = self._rule(DefinitionKey('RELATIONSHIP_RULE', record.scope.rule_id, record.scope.version), at=at)
            require(use.record.rule.active and use.record.content_hash == annotation.get('rule_hash')
                and root[2] == use.source_record_ref and record.payload['manifest'].get('principal_id') == principal,
                'GENERATION_RECEIPT_RULE_SCOPE')
            previous = self._occurrence(key, before) if before is not None else None
            require((previous[0].payload if previous else None) == old, 'GENERATION_RECEIPT_PREVIOUS_DRIFT')
            if record.state == 'CREATED':
                source = self._source(record.scope.creation_event_ref, depth + 1)
                parent_revision = record.payload['manifest'].get('source_current_revision')
                current = self.reader._get_in_transaction(source.event.task_id, parent_revision)
                require(current is not None, 'GENERATION_RECEIPT_PARENT_DRIFT')
                # Separate concrete links may bind a later source revision.
                relation = None
                if record.relation_ref:
                    relation_row = self.connection.execute('SELECT runtime_payload,transaction_ref FROM whattodo.task_relation_revision WHERE relation_id=%s AND revision=%s',
                        (record.relation_ref, record.relation_revision)).fetchone()
                    require(relation_row is not None and relation_row[1] == request_id, 'GENERATION_RECEIPT_RELATION_DRIFT')
                    relation = relation_from_payload(relation_row[0])
                    if record.obligation_kind == 'SEPARATE_TASK':
                        binding = next(b for b in (relation.before, relation.after) if b.task_id == source.event.task_id)
                        current = self.reader._get_in_transaction(binding.task_id, binding.task_revision)
                rebuilt = prepare_generation_commit(self.codec, source, use, self.definitions, expected_store_revision=epoch,
                    previous=previous[0] if previous else None, current_source=current, current_bindings=self._bindings(current), correlation_ref=audit[1])
                require(rebuilt.plan is not None and rebuilt.plan.request.fingerprint == fingerprint
                    and tuple(a.tuple for a in rebuilt.plan.audits) == changes, 'GENERATION_RECEIPT_RECONSTRUCTION_DRIFT')
                for c in changes:
                    if c[0] == 'TASK':
                        actual = self.reader._get_in_transaction(c[1], c[3])
                        require(actual is not None and actual.aggregate.as_record() == c[5], 'GENERATION_RECEIPT_TASK_DRIFT')
                        if c[2] is not None:
                            require(self.reader._get_in_transaction(c[1], c[2]).aggregate.as_record() == c[4], 'GENERATION_RECEIPT_TASK_DRIFT')
                    elif c[0] == 'TASK_RELATION':
                        require(relation is not None and c[1:4] == (relation.relation.relation_id, None, 1)
                            and c[5] == relation.payload, 'GENERATION_RECEIPT_RELATION_DRIFT')
                    else: require(c[0] == 'GENERATION_OCCURRENCE', 'GENERATION_RECEIPT_EFFECT_SCOPE')
            else:
                require(len(changes) == 1, 'GENERATION_RECEIPT_UNCREATED_EFFECT')
            require(self.connection.execute('SELECT revision FROM whattodo.store_epoch').fetchone()[0] >= committed,
                'GENERATION_RECEIPT_EPOCH_DRIFT')
        result = receipt, annotation, root[2]; self._receipts[request_id] = result
        return result

    def _bindings(self, record):
        row = self.connection.execute('SELECT profile_ref FROM whattodo.task_payload_revision WHERE task_id=%s AND task_revision=%s',
            (record.task_id, record.revision)).fetchone()
        require(row is not None, 'GENERATION_CURRENT_PARENT_REQUIRED')
        if row[0] is None: return TaskStorageBindings()
        key = self.connection.execute('SELECT kind,id,version FROM whattodo.definition_cache WHERE configuration_ref=%s', (row[0],)).fetchone()
        require(key is not None, 'GENERATION_PARENT_PROFILE_REQUIRED')
        return TaskStorageBindings(DefinitionKey(*key))

    def _graph(self, proposal):
        limits = self.policy.limits
        rules = tuple(self._rule(key, at=self.clock.now()).record for key in self.policy.rule_keys)
        relation_rows = self.connection.execute('''SELECT DISTINCT ON(r.relation_id) r.runtime_payload,r.acceptance_ref,r.transaction_ref
            FROM whattodo.task_relation_revision r JOIN whattodo.authority_record a ON a.authority_ref=r.acceptance_ref
            WHERE a.principal_id=%s ORDER BY r.relation_id,r.revision DESC LIMIT %s''',
            (self.policy.principal_id, limits.max_relations + 1)).fetchall()
        require(len(relation_rows) <= limits.max_relations, 'GENERATION_GRAPH_RELATION_LIMIT')
        relations = []
        for payload, ref, tx in relation_rows:
            require(isinstance(payload, dict), 'GENERATION_LEGACY_RELATION_NOT_ADMITTED')
            record = relation_from_payload(payload); root = self._authority(ref)
            if root[1] == 'USER_COMMAND':
                scope = acceptance_scope('RELATION', record)
                require((root[3], root[4]) == (digest(scope), scope), 'GENERATION_GRAPH_RELATION_AUTHORITY')
            else: self._receipt(tx)
            relations.append(record)
        rows = self.connection.execute('''SELECT h.task_id FROM whattodo.task_head h JOIN whattodo.task_revision t ON(t.task_id,t.revision)=(h.task_id,h.revision)
            JOIN whattodo.authority_record a ON a.authority_ref=t.acceptance_ref WHERE a.principal_id=%s ORDER BY h.task_id LIMIT %s''',
            (self.policy.principal_id, limits.max_endpoints + 1)).fetchall()
        endpoints = {Endpoint('TASK', row[0]): EndpointFact(Endpoint('TASK', row[0])) for row in rows}
        stages = self.connection.execute('''SELECT s.stage_id,s.task_id FROM whattodo.stage_identity s JOIN whattodo.task_head h USING(task_id)
            JOIN whattodo.task_revision t ON(t.task_id,t.revision)=(h.task_id,h.revision)
            JOIN whattodo.authority_record a ON a.authority_ref=t.acceptance_ref WHERE a.principal_id=%s ORDER BY s.stage_id LIMIT %s''',
            (self.policy.principal_id, limits.max_endpoints + 1)).fetchall()
        endpoints.update({Endpoint('STAGE', sid): EndpointFact(Endpoint('STAGE', sid), tid) for sid, tid in stages})
        if proposal.draft.target:
            task = proposal.draft.target; endpoints[Endpoint('TASK', task.task_id)] = EndpointFact(Endpoint('TASK', task.task_id))
        if proposal.draft.parent_after:
            stage = proposal.draft.target_id; endpoints[Endpoint('STAGE', stage)] = EndpointFact(Endpoint('STAGE', stage), proposal.draft.parent_after.task_id)
        if proposal.relation: relations.append(proposal.relation)
        result = validate_relationship_graph(GraphSnapshot(rules, tuple(relations), tuple(endpoints.values())), limits=limits)
        require(result.valid, 'GENERATION_GRAPH_REJECTED')
        return result.input_hash

    def _publish(self, prepared, caller, graph_hash):
        from psycopg.types.json import Jsonb
        from psycopg import sql
        request = prepared.request; now = self.clock.now()
        permit = TransactionPermit(prepared.permit_ref, caller.principal_id, caller.origin, request.fingerprint, now, now + timedelta(minutes=1))
        valid_permit(request, caller, permit, now)
        scope = dict(scope_kind='EXACT_TRANSACTION', request_fingerprint=request.fingerprint,
            authorization=prepared.authorization_context | dict(graph_hash=graph_hash))
        self.connection.execute('INSERT INTO whattodo.authority_record VALUES(%s,%s,%s,%s,%s,%s,%s,%s)',
            (permit.permit_ref, caller.principal_id, caller.origin, request.source_ref, request.fingerprint, Jsonb(scope), now, permit.expires_at))
        self.connection.execute('INSERT INTO whattodo.command_transaction VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)',
            (request.context.request_id, request.fingerprint, caller.principal_id, caller.origin, permit.permit_ref,
                request.expected_store_revision, prepared.receipt.store_revision, request.audit_id, now, Jsonb(prepared.receipt_body)))
        self.connection.execute('INSERT INTO whattodo.audit_entry VALUES(%s,%s,%s,%s,%s)',
            (request.audit_id, request.context.request_id, request.source_ref, request.context.correlation_ref, now))
        for a in prepared.audits:
            kind, item, before, after, old, new = a.tuple
            self.connection.execute('INSERT INTO whattodo.audit_change VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s)',
                (a.change_ref, request.audit_id, kind, item, before, after, Jsonb(old) if old is not None else None, Jsonb(new), request.context.request_id))
        task = prepared.draft.target or prepared.draft.parent_after
        for o in prepared.observations:
            self._source_evidence(o.source_ref)
            require(task is not None and o.task_id == task.task_id and o.authority_ref == permit.permit_ref and o.observed_at <= now,
                'GENERATION_OBSERVATION_SCOPE')
            self.connection.execute('INSERT INTO whattodo.effort_observation VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)',
                (*o.row[:5], now, *o.row[5:], None, request.context.request_id))
        repository = PostgresTaskRepository(self.connection, self.codec, self.plan, application_version=self.application_version,
            clock=self.clock, permits=(permit,))
        if task:
            a = next(a for a in prepared.audits if a.key.kind == 'TASK')
            repository._append_in_transaction(task, prepared.draft.bindings, request=request, caller=caller,
                permit_ref=permit.permit_ref, audit_change_ref=a.change_ref)
        if prepared.relation:
            r = prepared.relation; b, a = r.before, r.after
            self.connection.execute('''INSERT INTO whattodo.task_relation_revision
                (relation_id,revision,kind,before_kind,before_task_id,before_task_revision,before_stage_id,before_stage_revision,
                 after_kind,after_task_id,after_task_revision,after_stage_id,after_stage_revision,acceptance_ref,transaction_ref,
                 runtime_payload,origin_rule_id,origin_rule_version) VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)''',
                (r.relation.relation_id, 1, r.relation.kind, b.endpoint.kind, b.task_id, b.task_revision,
                    b.endpoint.id if b.endpoint.kind == 'STAGE' else None, b.stage_revision, a.endpoint.kind, a.task_id, a.task_revision,
                    a.endpoint.id if a.endpoint.kind == 'STAGE' else None, a.stage_revision, permit.permit_ref, request.context.request_id,
                    Jsonb(r.payload), r.relation.origin_rule_id, r.relation.origin_rule_version))
        a = next(a for a in prepared.audits if a.key.kind == 'GENERATION_OCCURRENCE')
        values = prepared.occurrence.sql_row(request.context.request_id, a.change_ref)
        for table in ('generation_occurrence_revision', 'generation_occurrence'):
            if table == 'generation_occurrence' and prepared.occurrence.revision > 1:
                columns = {k: v for k, v in values.items() if k != 'generation_key'}
                count = self.connection.execute(sql.SQL('UPDATE whattodo.generation_occurrence SET {} WHERE generation_key=%s AND revision=%s').format(
                    sql.SQL(',').join(sql.SQL('{}=%s').format(sql.Identifier(k)) for k in columns)),
                    tuple(Jsonb(v) if isinstance(v, dict) else v for v in columns.values()) + (prepared.occurrence.scope.generation_key, prepared.occurrence.revision - 1)).rowcount
                require(count == 1, 'GENERATION_STALE_OCCURRENCE')
            else:
                self.connection.execute(sql.SQL('INSERT INTO whattodo.{} ({}) VALUES ({})').format(sql.Identifier(table),
                    sql.SQL(',').join(map(sql.Identifier, values)), sql.SQL(',').join(sql.Placeholder() for _ in values)),
                    tuple(Jsonb(v) if isinstance(v, dict) else v for v in values.values()))
        valid_permit(request, caller, permit, self.clock.now())
        count = self.connection.execute('UPDATE whattodo.store_epoch SET revision=%s,last_transaction_ref=%s WHERE revision=%s',
            (prepared.receipt.store_revision, request.context.request_id, request.expected_store_revision)).rowcount
        require(count == 1, 'GENERATION_STALE_EPOCH')

    def _fence(self, lease, caller):
        from src.adapters.postgres_creation_outbox import PostgresCreationOutbox
        outbox=PostgresCreationOutbox(self.connection,self.plan,application_version=self.application_version,
            clock=self.clock,caller=caller,worker_id=lease.worker_id,source_scopes=self.policy.source_scopes)
        row=outbox._owned(lease);outbox._live(row,lease,self.clock.now())

    def _run(self, event_id, rule_id, correlation_ref, caller, *, lookup=False, lease=None):
        require(identity(correlation_ref), 'GENERATION_CORRELATION_REQUIRED')
        phase = 'READING'; database_error = (); transport_error = ()
        try:
            validate_caller(caller, principal_id=self.policy.principal_id)
            require(caller.origin == 'RELATIONSHIP_RULE' and identity(event_id) and identity(rule_id), 'GENERATION_TRUSTED_RULE_CALLER')
            require(lease is None or isinstance(lease,DeliveryLease) and lease.event.event_id==event_id
                and lease.event.principal_id==caller.principal_id,'GENERATION_LEASE_SCOPE')
            key = next((k for k in self.policy.rule_keys if k.id == rule_id), None)
            require(key is not None, 'GENERATION_RULE_NOT_SELECTED')
            from psycopg import Error as database_error, OperationalError as transport_error, InterfaceError
            require(self.definitions is not None, 'GENERATION_DEFINITION_REPOSITORY_REQUIRED')
            self._receipts = {}
            with schema_checked_transaction(self.connection, self.plan, application_version=self.application_version, read_only=lookup):
                if not lookup:
                    epoch = self.connection.execute('SELECT revision FROM whattodo.store_epoch FOR UPDATE NOWAIT').fetchone()[0]
                    if lease is not None:self._fence(lease,caller)
                source = self._source(event_id); use = self._rule(key)
                prior = self._occurrence(generation_scope(source, use).generation_key)
                if prior:
                    receipt = self._receipt(prior[1])[0]
                    if lookup or prior[0].state == 'CREATED':
                        return PortResult('SUCCESS', 'GENERATION_REPLAY' if not lookup else 'GENERATION_FOUND', correlation_ref,
                            GenerationOutcome(prior[0].state, prior[0], receipt))
                if lookup: return PortResult('UNKNOWN', 'GENERATION_NOT_OBSERVED', correlation_ref)
                self._rule(key, at=self.clock.now())
                current = self.reader._get_in_transaction(source.event.task_id)
                require(current is not None, 'GENERATION_CURRENT_SOURCE_REQUIRED')
                prepared = prepare_generation_commit(self.codec, source, use, self.definitions, expected_store_revision=epoch,
                    previous=prior[0] if prior else None, current_source=current, current_bindings=self._bindings(current), correlation_ref=correlation_ref)
                if prepared.plan is None:
                    return PortResult('SUCCESS', prepared.code, correlation_ref, GenerationOutcome('NOT_ELIGIBLE'))
                plan = prepared.plan
                if prior and {k:v for k,v in prior[0].payload.items() if k!='revision'} == {k:v for k,v in plan.occurrence.payload.items() if k!='revision'}:
                    return PortResult('SUCCESS', 'GENERATION_REPLAY', correlation_ref, GenerationOutcome(prior[0].state, prior[0], receipt))
                graph_hash = self._graph(plan)
                if lease is not None and plan.draft.ready:
                    slot=self.connection.execute('''SELECT r.state,r.worker_id,r.lease_token,r.source_event_id,r.rule_version FROM whattodo.generation_chain_slot_head h
                        JOIN whattodo.generation_chain_slot_revision r USING(generation_key,revision) WHERE generation_key=%s''',
                        (plan.occurrence.scope.generation_key,)).fetchone()
                    if slot!=('RESERVED',lease.worker_id,lease.token,event_id,use.record.rule.version):
                        return PortResult('RETRYABLE','GENERATION_RESERVATION_REQUIRED',correlation_ref)
                phase = 'STAGING'; self._publish(plan, caller, graph_hash)
                self._rule(key, at=self.clock.now())
                if lease is not None:self._fence(lease,caller)
                phase = 'COMMITTING'
            return PortResult('SUCCESS', 'GENERATION_COMMITTED', correlation_ref, GenerationOutcome(plan.occurrence.state, plan.occurrence, plan.receipt))
        except MigrationError as exc:
            retryable = str(exc) in ('MIGRATION_BUSY','MIGRATION_METADATA_UNREADABLE')
            return PortResult('RETRYABLE' if retryable else 'PERMANENT',
                'GENERATION_SCHEMA_UNAVAILABLE' if retryable else 'GENERATION_SCHEMA_INCOMPATIBLE', correlation_ref)
        except ImportError:
            return PortResult('PERMANENT', 'TRANSACTION_DRIVER_UNAVAILABLE', correlation_ref)
        except database_error as exc:
            if phase == 'COMMITTING' and (isinstance(exc, (transport_error, InterfaceError)) or getattr(exc, 'sqlstate', None) is None):
                return PortResult('UNKNOWN', 'GENERATION_ACKNOWLEDGEMENT_LOST', correlation_ref)
            if isinstance(exc, (transport_error, InterfaceError)) or getattr(exc, 'sqlstate', None) in ('55P03', '40001', '40P01'):
                return PortResult('RETRYABLE', 'GENERATION_STORAGE_UNAVAILABLE', correlation_ref)
            return PortResult('PERMANENT', 'GENERATION_DATABASE_REJECTED', correlation_ref)
        except (ValueError, RuntimeError) as exc:
            code = str(exc)
            import re
            return PortResult('PERMANENT', code if re.fullmatch('[A-Z][A-Z0-9_]{0,63}', code) else 'GENERATION_INVALID', correlation_ref)
        except Exception:
            return PortResult('PERMANENT', 'GENERATION_INTERNAL_FAILURE', correlation_ref)

    def generate(self, event_id, rule_id, *, correlation_ref, caller, lease=None):
        return self._run(event_id, rule_id, correlation_ref, caller,lease=lease)

    def lookup(self, event_id, rule_id, *, correlation_ref, caller):
        return self._run(event_id, rule_id, correlation_ref, caller, lookup=True)
