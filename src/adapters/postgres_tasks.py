"""Lossless Task queries and internal, transaction-bound append storage.

No public commit/create/update/delete endpoint. A trusted command coordinator
prepares authority, audit and store concurrency before calling the internal
append hook in that same PostgreSQL transaction.
"""
import json

from src.adapters.postgres_migrations import (LOCK_KEY, _snapshot,
    _legacy_receipts, schema_checked_transaction)
from src.application.definitions import DefinitionKey
from src.application.migrations import check_history
from src.application.ports import (AggregateKey, CommitRequest, TransactionPermit)
from src.application.task_storage import (TaskStorageBindings, TaskStorageRecord,
    admit_storage, project_task, require, sql_value)
from src.domain.authorization import CallerIdentity


class PostgresTaskRepository:
    def __init__(self, connection, codec, plan, *, application_version, clock,
                 permits=()):
        require(isinstance(permits, tuple) and
                all(isinstance(p, TransactionPermit) for p in permits) and
                len({p.permit_ref for p in permits}) == len(permits),
                'TASK_STORAGE_TRUSTED_PERMIT_REGISTRY')
        self.connection = connection
        self.codec = codec
        self.plan = plan
        self.application_version = application_version
        self.clock = clock
        self._permits = {p.permit_ref: p for p in permits}

    def get(self, task_id, revision=None):
        require(isinstance(task_id, str) and task_id.strip(), 'TASK_STORAGE_TASK_ID')
        require(revision is None or (type(revision) is int and revision > 0),
                'TASK_STORAGE_REVISION')
        with schema_checked_transaction(self.connection, self.plan,
                application_version=self.application_version):
            return self._get_in_transaction(task_id, revision)

    def list_current(self, *, completion=None, disposition=None, trust=None):
        require(completion in (None, 'INCOMPLETE', 'COMPLETE') and
                disposition in (None, 'ACTIVE', 'CANCELLED', 'EXPIRED') and
                trust in (None, 'TRUSTED', 'STALE', 'CONFLICTED', 'UNKNOWN'),
                'TASK_STORAGE_QUERY_FILTER')
        with schema_checked_transaction(self.connection, self.plan,
                application_version=self.application_version):
            rows = self.connection.execute('''SELECT h.task_id,h.revision
                FROM whattodo.task_head h JOIN whattodo.task_revision t
                ON (t.task_id,t.revision)=(h.task_id,h.revision)
                WHERE (%s::text IS NULL OR t.completion=%s)
                AND (%s::text IS NULL OR t.disposition=%s)
                AND (%s::text IS NULL OR t.metadata->>'trust'=%s)
                ORDER BY h.task_id''', (completion, completion, disposition,
                    disposition, trust, trust)).fetchall()
            return tuple(self._get_in_transaction(*row) for row in rows)

    def _select_row(self, table, expected, where, parameters):
        # Identifiers come solely from project_task's fixed implementation.
        from psycopg import sql
        query = sql.SQL('SELECT {} FROM whattodo.{} WHERE ').format(
            sql.SQL(',').join(map(sql.Identifier, expected)), sql.Identifier(table))
        rows = self.connection.execute(query + sql.SQL(where), parameters).fetchall()
        require(len(rows) == 1, 'TASK_STORAGE_PROJECTION_MISSING')
        actual = rows[0]
        values = tuple(sql_value(k, v) for k, v in expected.items())
        require(actual == values, 'TASK_STORAGE_PROJECTION_DRIFT')

    def _get_in_transaction(self, task_id, revision=None):
        if revision is None:
            row = self.connection.execute('SELECT revision FROM whattodo.task_head WHERE task_id=%s',
                (task_id,)).fetchone()
            if row is None:
                return None
            revision = row[0]
        row = self.connection.execute('''SELECT raw_bytes,content_hash,profile_ref
            FROM whattodo.task_payload_revision WHERE task_id=%s AND task_revision=%s''',
            (task_id, revision)).fetchone()
        if row is None:
            exists = self.connection.execute('SELECT EXISTS(SELECT 1 FROM whattodo.task_revision WHERE task_id=%s AND revision=%s)',
                (task_id, revision)).fetchone()[0]
            require(not exists, 'TASK_STORAGE_LEGACY_PAYLOAD_UNAVAILABLE')
            return None
        record = admit_storage(self.codec, bytes(row[0]))
        require((record.task_id, record.revision, record.content_hash) ==
                (task_id, revision, row[1]), 'TASK_STORAGE_PAYLOAD_DRIFT')
        profile_key = None
        if row[2] is not None:
            profile = self.connection.execute('SELECT kind,id,version FROM whattodo.definition_cache WHERE configuration_ref=%s',
                (row[2],)).fetchone()
            require(profile is not None, 'TASK_STORAGE_UNRESOLVED_PROFILE')
            profile_key = DefinitionKey(*profile)
        notice = self.connection.execute('SELECT notice_task_revision FROM whattodo.task_revision WHERE task_id=%s AND revision=%s',
            (task_id, revision)).fetchone()
        require(notice is not None, 'TASK_STORAGE_PROJECTION_MISSING')
        bindings = TaskStorageBindings(profile_key, notice[0])
        rows = project_task(record, bindings).rows
        for table in ('task_revision', 'task_details_revision', 'task_payload_revision'):
            column = 'revision' if table == 'task_revision' else 'task_revision'
            self._select_row(table, rows[table], 'task_id=%s AND '+column+'=%s',
                (task_id, revision))
        actual_members = self.connection.execute('''SELECT stage_id,stage_revision,ordinal
            FROM whattodo.task_stage_revision WHERE task_id=%s AND task_revision=%s
            ORDER BY ordinal''', (task_id, revision)).fetchall()
        require(actual_members == [(r['stage_id'], r['stage_revision'], r['ordinal'])
                for r in rows['task_stage_revision']], 'TASK_STORAGE_STAGE_MEMBERSHIP_DRIFT')
        for stage, estimate in zip(rows['stage_revision'], rows['stage_effort_revision']):
            key = (stage['stage_id'], stage['revision'], task_id)
            self._select_row('stage_revision', stage,
                'stage_id=%s AND revision=%s AND task_id=%s', key)
            self._select_row('stage_effort_revision', estimate,
                'stage_id=%s AND stage_revision=%s AND task_id=%s', key)
        actual_provenance = self.connection.execute('''SELECT field_pointer,source_record_ref
            FROM whattodo.task_field_provenance WHERE task_id=%s AND task_revision=%s
            ORDER BY field_pointer''', (task_id, revision)).fetchall()
        require(actual_provenance == sorted((r['field_pointer'], r['source_record_ref'])
                for r in rows['task_field_provenance']), 'TASK_STORAGE_PROVENANCE_DRIFT')
        self._check_references(record, bindings)
        return record

    def _check_references(self, record, bindings, *, resolved_estimates=(), resolved_dues=()):
        value = record.aggregate.as_record()
        core = value['core']
        context = core['context']
        if context is not None and context['kind'] in ('GOAL', 'EXAM'):
            # These wire contexts name a logical identity, not a version. Check
            # its existence without selecting/activating a convenient revision.
            table, column = {'GOAL': ('goal_revision', 'goal_id'),
                'EXAM': ('exam_revision', 'exam_id')}[context['kind']]
            from psycopg import sql
            exists = self.connection.execute(sql.SQL(
                'SELECT EXISTS(SELECT 1 FROM whattodo.{} WHERE {}=%s AND acceptance=\'ACCEPTED\')').format(
                    sql.Identifier(table), sql.Identifier(column)), (context['id'],)).fetchone()[0]
            require(exists, 'TASK_STORAGE_UNRESOLVED_CONTEXT')
        if core['task_type_ref'] is not None:
            key = DefinitionKey('TASKTYPE', **core['task_type_ref'])
            require(self.connection.execute('SELECT EXISTS(SELECT 1 FROM whattodo.definition_cache WHERE kind=%s AND id=%s AND version=%s AND configuration_ref=%s)',
                (key.kind, key.id, key.version, key.configuration_ref)).fetchone()[0],
                'TASK_STORAGE_UNRESOLVED_TASK_TYPE')
        if bindings.profile_key is not None:
            key = bindings.profile_key
            require(self.connection.execute('SELECT EXISTS(SELECT 1 FROM whattodo.definition_cache WHERE kind=%s AND id=%s AND version=%s AND configuration_ref=%s)',
                (key.kind, key.id, key.version, key.configuration_ref)).fetchone()[0],
                'TASK_STORAGE_UNRESOLVED_PROFILE')
        total = value['work']['total_estimate']
        if total is not None and total['definition_ref'] is not None:
            key = DefinitionKey(**total['definition_ref'])
            require(self.connection.execute('SELECT EXISTS(SELECT 1 FROM whattodo.definition_cache WHERE kind=%s AND id=%s AND version=%s)',
                (key.kind, key.id, key.version)).fetchone()[0],
                'TASK_STORAGE_UNRESOLVED_TOTAL_DEFINITION')
        for estimate in [value['effort']['user_remaining']] + [s['user_remaining'] for s in value['effort']['stages']]:
            if estimate is not None:
                actual = self.connection.execute('SELECT task_id,kind,seconds,observed_at FROM whattodo.effort_observation WHERE observation_id=%s',
                    (estimate['observation_id'],)).fetchone()
                if actual is None:
                    # Read-only authorization can resolve a typed supporting
                    # fact which the coordinator will atomically insert first.
                    # Append passes no such values and checks actual SQL rows.
                    proposed=next((r for r in resolved_estimates if r[0]==estimate['observation_id']),None)
                    if proposed is not None:actual=proposed[1:5]
                require(actual == (record.task_id, 'USER_REMAINING', estimate['seconds'],
                    sql_value('observed_at', estimate['observed_at'])), 'TASK_STORAGE_ESTIMATE_REFERENCE_DRIFT')
        deadline = value['timing']['deadline']
        if deadline is not None:
            due = deadline['value']
            expected = (due['input_kind'], due['original_value'], due['source_ref'],
                sql_value('due_at', due['instant']), due['default_policy_ref'])
            actual=self.connection.execute('SELECT input_kind,original_value,source_record_ref,due_at,default_policy_ref FROM whattodo.normalized_due WHERE due_id=%s',
                (deadline['due_ref'],)).fetchone()
            if actual is None:
                proposed=next((r for r in resolved_dues if r[0]==deadline['due_ref']),None)
                if proposed is not None:actual=proposed[1:]
            require(actual == expected, 'TASK_STORAGE_DUE_REFERENCE_DRIFT')
        prediction = value['effort']['prediction']
        if prediction is not None:
            expected = (record.task_id, prediction['task_revision'], prediction['model_ref']['id'],
                prediction['model_ref']['version'], prediction['seconds'],
                sql_value('computed_at', prediction['computed_at']),
                sql_value('valid_until_at', prediction['valid_until']))
            require(self.connection.execute('SELECT task_id,task_revision,model_id,model_version,remaining_seconds,computed_at,valid_until FROM whattodo.remaining_prediction WHERE prediction_id=%s',
                (prediction['prediction_id'],)).fetchone() == expected,
                'TASK_STORAGE_PREDICTION_REFERENCE_DRIFT')

    def _insert(self, table, values):
        from psycopg import sql
        from psycopg.types.json import Jsonb
        self.connection.execute(sql.SQL('INSERT INTO whattodo.{} ({}) VALUES ({})').format(
            sql.Identifier(table), sql.SQL(',').join(map(sql.Identifier, values)),
            sql.SQL(',').join(sql.Placeholder() for _ in values)),
            tuple(Jsonb(v) if isinstance(v, dict) else sql_value(k, v)
                for k, v in values.items()))

    def _append_in_transaction(self, record, bindings, *, request, caller,
                               permit_ref, audit_change_ref):
        """Internal hook; caller owns the checked transaction and publication.

        Never begins/commits a transaction, creates authority/audit, advances the
        store epoch or accepts a serialized permit. M3A-09 will coordinate those.
        """
        from psycopg.pq import TransactionStatus
        require(self.connection.info.transaction_status == TransactionStatus.INTRANS,
                'TASK_STORAGE_TRANSACTION_REQUIRED')
        # A caught semantic error must not leave half a Task in the coordinator's
        # transaction. This is a nested savepoint, never an independent commit.
        with self.connection.transaction():
            return self._append_checked(record, bindings, request=request,
                caller=caller, permit_ref=permit_ref, audit_change_ref=audit_change_ref)

    def _append_checked(self, record, bindings, *, request, caller,
                        permit_ref, audit_change_ref):
        require(isinstance(record, TaskStorageRecord), 'TASK_STORAGE_TYPED_VALUES')
        # A constructed value alone is never proof of supported wire admission.
        record = admit_storage(self.codec, record.raw_bytes)
        require(isinstance(request, CommitRequest) and isinstance(caller, CallerIdentity)
                and caller.authenticated and caller.origin != 'EXTERNAL'
                and caller.principal_id == request.principal_id,
                'TASK_STORAGE_UNTRUSTED_CALLER')
        permit = self._permits.get(permit_ref)
        now = self.clock.now()
        require(permit is not None and permit.active and permit.issued_at <= now < permit.expires_at
                and (permit.principal_id, permit.origin, permit.request_fingerprint) ==
                (caller.principal_id, caller.origin, request.fingerprint),
                'TASK_STORAGE_EXACT_ACTIVE_PERMIT_REQUIRED')
        require(self.connection.execute('SELECT pg_try_advisory_xact_lock_shared(%s)',
                (LOCK_KEY,)).fetchone()[0], 'TASK_STORAGE_SCHEMA_BUSY')
        snapshot = _snapshot(self.connection)
        require(snapshot is not None, 'TASK_STORAGE_SCHEMA_UNINITIALIZED')
        check_history(self.plan, *snapshot, application_version=self.application_version, complete=True)
        _legacy_receipts(self.connection, self.plan, snapshot[0])
        require(self.connection.execute('SELECT revision FROM whattodo.store_epoch WHERE singleton=TRUE FOR UPDATE').fetchone()
                == (request.expected_store_revision,), 'TASK_STORAGE_STALE_STORE_REVISION')
        write = next((w for w in request.writes if w.key == AggregateKey('TASK', record.task_id)), None)
        require(write is not None and json.loads(write.body_json) == record.aggregate.as_record()
                and record.revision == (write.expected_revision or 0) + 1,
                'TASK_STORAGE_EXACT_WRITE_REQUIRED')
        # A prepared receipt must belong to this still-open transaction. xmin is
        # the 32-bit XID; PostgreSQL's full transaction ID also includes the epoch.
        prepared = self.connection.execute('''SELECT request_hash,principal_id,origin,
            authority_ref,expected_store_revision,audit_id,
            xmin::text::numeric=(pg_current_xact_id()::text::numeric %% 4294967296)
            FROM whattodo.command_transaction WHERE request_id=%s''',
            (request.context.request_id,)).fetchone()
        require(prepared == (request.fingerprint, caller.principal_id, caller.origin,
                permit_ref, request.expected_store_revision, request.audit_id, True),
                'TASK_STORAGE_PREPARED_TRANSACTION_REQUIRED')
        authority = self.connection.execute('SELECT principal_id,origin,source_record_ref,resolved_scope_hash FROM whattodo.authority_record WHERE authority_ref=%s',
            (permit_ref,)).fetchone()
        require(authority == (caller.principal_id, caller.origin, request.source_ref,
                request.fingerprint), 'TASK_STORAGE_AUTHORITY_REFERENCE_DRIFT')
        previous = self._get_in_transaction(record.task_id)
        require((previous.revision if previous else None) == write.expected_revision,
                'TASK_STORAGE_STALE_TASK_REVISION')
        audit = self.connection.execute('''SELECT audit_id,aggregate_kind,aggregate_id,
            before_revision,after_revision,before_value,after_value,request_id
            FROM whattodo.audit_change WHERE change_id=%s''', (audit_change_ref,)).fetchone()
        require(audit == (request.audit_id, 'TASK', record.task_id, write.expected_revision,
                record.revision, previous.aggregate.as_record() if previous else None,
                record.aggregate.as_record(), request.context.request_id),
                'TASK_STORAGE_PREPARED_AUDIT_REQUIRED')
        rows = project_task(record, bindings).rows
        self._check_references(record, bindings)
        transaction_ref = request.context.request_id
        if previous is None:
            self._insert('task_identity', dict(task_id=record.task_id,
                transaction_ref=transaction_ref, created_at=now))
        self._insert('task_revision', dict(rows['task_revision'],
            audit_change_ref=audit_change_ref, transaction_ref=transaction_ref))
        self._insert('task_details_revision', rows['task_details_revision'])
        for stage, estimate in zip(rows['stage_revision'], rows['stage_effort_revision']):
            owner = self.connection.execute('SELECT task_id FROM whattodo.stage_identity WHERE stage_id=%s',
                (stage['stage_id'],)).fetchone()
            if owner is None:
                self._insert('stage_identity', dict(stage_id=stage['stage_id'],
                    task_id=record.task_id, transaction_ref=transaction_ref))
            else:
                require(owner == (record.task_id,), 'TASK_STORAGE_STAGE_OWNER_CONFLICT')
            latest = self.connection.execute('SELECT max(revision) FROM whattodo.stage_revision WHERE stage_id=%s',
                (stage['stage_id'],)).fetchone()[0]
            if latest == stage['revision']:
                self._select_row('stage_revision', stage, 'stage_id=%s AND revision=%s',
                    (stage['stage_id'], stage['revision']))
                self._select_row('stage_effort_revision', estimate, 'stage_id=%s AND stage_revision=%s',
                    (stage['stage_id'], stage['revision']))
            else:
                # A first persisted reviewed snapshot may already name a later
                # stage version. Preserve it without fabricating prior history.
                require(latest is None or stage['revision'] == latest + 1,
                    'TASK_STORAGE_STALE_STAGE_REVISION')
                self._insert('stage_revision', dict(stage, task_revision=record.revision,
                    transaction_ref=transaction_ref))
                self._insert('stage_effort_revision', estimate)
        for table in ('task_stage_revision', 'task_field_provenance'):
            for row in rows[table]:
                self._insert(table, row)
        self._insert('task_payload_revision', dict(rows['task_payload_revision'],
            transaction_ref=transaction_ref, raw_bytes=record.raw_bytes))
        if previous is None:
            self._insert('task_head', dict(task_id=record.task_id, revision=record.revision,
                transaction_ref=transaction_ref))
        else:
            changed = self.connection.execute('UPDATE whattodo.task_head SET revision=%s,transaction_ref=%s WHERE task_id=%s AND revision=%s',
                (record.revision, transaction_ref, record.task_id, previous.revision)).rowcount
            require(changed == 1, 'TASK_STORAGE_STALE_TASK_REVISION')
        require(self._get_in_transaction(record.task_id) == record,
                'TASK_STORAGE_ROUNDTRIP_FAILED')
