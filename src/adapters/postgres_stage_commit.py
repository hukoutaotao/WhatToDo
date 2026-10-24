"""Internal stage publication, inside an already authorized transaction.

This is not a command entrypoint. The stage handler must independently
resolve principal/account ownership and complete current order evidence before
minting an exact permit. Publication rechecks stored USER authority and rebuilds
the complete plan; it never commits, registers a grant or issues a permit.
"""
from src.adapters.postgres_tasks import PostgresTaskRepository
from src.application.command_ledger import validate_audit_fingerprint, validate_caller
from src.application.stage_commands import StageCommandGrant
from src.application.stage_commit import StageCommandJournal, StageCommitPlan, STORAGE_ORDER_LIMITS, order_from_payload, prepare_stage_commit
from src.application.transactions import require, valid_permit


class PostgresStageCommitWriter:
    def __init__(self, connection, codec, plan, *, application_version, clock):
        self.connection = connection; self.codec = codec; self.plan = plan
        self.application_version = application_version; self.clock = clock

    def _root(self, journal, at):
        row = self.connection.execute('''SELECT principal_id,origin,source_record_ref,resolved_scope_hash,
            resolved_scope,issued_at,expires_at FROM whattodo.authority_record WHERE authority_ref=%s''',
            (journal.command.authority_ref,)).fetchone()
        require(row is not None, 'STAGE_UNREGISTERED_AUTHORITY')
        grant = StageCommandGrant(journal.command, journal.source_ref, row[5], journal.source_observed_at, row[6])
        require(row[:5] == (journal.command.principal_id, 'USER_COMMAND', journal.source_ref,
            journal.command.fingerprint, grant.as_record()), 'STAGE_REGISTERED_AUTHORITY_MISMATCH')
        require(row[5] <= at and (row[6] is None or at < row[6]), 'STAGE_INACTIVE_AUTHORITY')
        source = self.connection.execute('''SELECT r.captured_at,s.source_type FROM whattodo.source_record r
            JOIN whattodo.source_identity s USING(source_id) WHERE r.record_id=%s''', (journal.source_ref,)).fetchone()
        require(source == (journal.source_observed_at, 'USER') and journal.source_observed_at <= at,
            'STAGE_REGISTERED_SOURCE_MISMATCH')
        return grant

    def append_in_transaction(self, prepared, *, caller, permit, bindings):
        from psycopg.pq import TransactionStatus
        from psycopg.types.json import Jsonb
        from psycopg import sql
        require(self.connection.info.transaction_status == TransactionStatus.INTRANS, 'STAGE_OPEN_TRANSACTION_REQUIRED')
        require(isinstance(prepared, StageCommitPlan), 'STAGE_TYPED_COMMIT_REQUIRED')
        request = prepared.request; journal = prepared.journal; now = self.clock.now()
        validate_caller(caller, principal_id=request.principal_id)
        require(caller.origin == 'USER_COMMAND', 'STAGE_TRUSTED_USER_CALLER')
        valid_permit(request, caller, permit, now)
        root = self._root(journal, now)
        repository = PostgresTaskRepository(self.connection, self.codec, self.plan,
            application_version=self.application_version, clock=self.clock, permits=(permit,))
        before = repository._get_in_transaction(journal.command.task_id)
        require(before is not None and before.content_hash == journal.before_task_hash, 'STAGE_CURRENT_PARENT_MISMATCH')
        pending=[]
        for resolution in prepared.resolutions:
            row=self.connection.execute('''SELECT runtime_payload FROM whattodo.stage_command_journal j
                WHERE record_id=%s AND NOT EXISTS(SELECT 1 FROM whattodo.stage_pending_resolution r WHERE r.pending_ref=j.record_id)''',
                (resolution['pending_ref'],)).fetchone()
            require(row is not None,'STAGE_PENDING_ALREADY_RESOLVED')
            pending.append(StageCommandJournal.from_payload(row[0]))
        rebuilt = prepare_stage_commit(self.codec, journal.raw_command, root, before, caller=caller, now=now,
            context=request.context, expected_store_revision=request.expected_store_revision, audit_id=request.audit_id,
            order=order_from_payload(journal.payload['order_snapshot'],limits=STORAGE_ORDER_LIMITS),pending=tuple(pending))
        require(rebuilt == prepared, 'STAGE_EXACT_COMMIT_PLAN_REQUIRED')
        require(self.connection.execute('SELECT revision FROM whattodo.store_epoch WHERE singleton=TRUE FOR UPDATE NOWAIT').fetchone()
            == (request.expected_store_revision,), 'STAGE_STALE_STORE_REVISION')
        validate_audit_fingerprint(prepared.receipt, principal_id=request.principal_id,
            expected_store_revision=request.expected_store_revision, source_ref=request.source_ref,
            correlation_ref=request.context.correlation_ref, changes=tuple(a.tuple for a in prepared.audits))
        annotation = dict(contract='stage-command', grant_ref=journal.command.authority_ref,
            command_fingerprint=journal.command.fingerprint, command=journal.command.as_record(),
            command_wire_hash=journal.payload['raw_command_hash'], order_input_hash=journal.transition['order_input_hash']
                if journal.transition is not None else None)
        scope = dict(scope_kind='EXACT_TRANSACTION', request_fingerprint=request.fingerprint, authorization=annotation)
        self.connection.execute('INSERT INTO whattodo.authority_record VALUES(%s,%s,%s,%s,%s,%s,%s,%s)',
            (permit.permit_ref, caller.principal_id, caller.origin, request.source_ref, request.fingerprint,
                Jsonb(scope), permit.issued_at, permit.expires_at))
        self.connection.execute('INSERT INTO whattodo.command_transaction VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)',
            (request.context.request_id, request.fingerprint, caller.principal_id, caller.origin, permit.permit_ref,
                request.expected_store_revision, prepared.receipt.store_revision, request.audit_id, now, Jsonb(prepared.receipt_body)))
        self.connection.execute('INSERT INTO whattodo.audit_entry VALUES(%s,%s,%s,%s,%s)',
            (request.audit_id, request.context.request_id, request.source_ref, request.context.correlation_ref, now))
        for a in prepared.audits:
            kind, item, previous, after, old, new = a.tuple
            self.connection.execute('INSERT INTO whattodo.audit_change VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s)',
                (a.change_ref, request.audit_id, kind, item, previous, after,
                    Jsonb(old) if old is not None else None, Jsonb(new), request.context.request_id))
        for observation in prepared.observations:
            require(observation.authority_ref == journal.command.authority_ref
                and observation.source_ref == journal.source_ref and observation.observed_at == journal.source_observed_at,
                'STAGE_OBSERVATION_ORIGINAL_SOURCE')
            self.connection.execute('INSERT INTO whattodo.effort_observation VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)',
                (*observation.row[:5], now, *observation.row[5:], None, request.context.request_id))
        if prepared.task is not None:
            change = next(a for a in prepared.audits if a.key.kind == 'TASK')
            repository._append_in_transaction(prepared.task, bindings, request=request, caller=caller,
                permit_ref=permit.permit_ref, audit_change_ref=change.change_ref)
        change = next(a for a in prepared.audits if a.key.kind == journal.kind)
        row = journal.sql_row(request.context.request_id, change.change_ref)
        columns = tuple(row)
        self.connection.execute(sql.SQL('INSERT INTO whattodo.stage_command_journal ({}) VALUES ({})').format(
            sql.SQL(',').join(map(sql.Identifier, columns)), sql.SQL(',').join(sql.Placeholder() for _ in columns)),
            tuple(Jsonb(v) if isinstance(v, dict) else v for v in row.values()))
        for issue in prepared.issues:
            change = next(a for a in prepared.audits if a.key.id == issue['issue_id'])
            self.connection.execute('''INSERT INTO whattodo.stage_relationship_issue
                (issue_id,transition_ref,relation_id,relation_revision,code,kind,transaction_ref,audit_change_ref,runtime_payload)
                VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s)''',
                (issue['issue_id'], issue['transition_ref'], issue['relation_id'], issue['relation_revision'],
                    issue['code'], issue['kind'], request.context.request_id, change.change_ref, Jsonb(issue)))
        for resolution in prepared.resolutions:
            change=next(a for a in prepared.audits if a.key.id==resolution['resolution_id'])
            self.connection.execute('''INSERT INTO whattodo.stage_pending_resolution
                (resolution_id,pending_ref,transition_ref,transaction_ref,audit_change_ref,runtime_payload)
                VALUES(%s,%s,%s,%s,%s,%s)''',
                (resolution['resolution_id'],resolution['pending_ref'],resolution['transition_ref'],
                    request.context.request_id,change.change_ref,Jsonb(resolution)))
        self._root(journal, self.clock.now())
        valid_permit(request, caller, permit, self.clock.now())
        updated = self.connection.execute('''UPDATE whattodo.store_epoch SET revision=%s,last_transaction_ref=%s
            WHERE singleton=TRUE AND revision=%s''',
            (prepared.receipt.store_revision, request.context.request_id, request.expected_store_revision)).rowcount
        require(updated == 1, 'STAGE_STALE_STORE_REVISION')
        return prepared.receipt
