"""Scoped stage entrypoint: independent authority, current evidence and owned replay.

Only versioned command bytes enter this boundary. Caller, source scopes, exact
grants and (when needed) the definition repository are independently injected.
No supplied plan, relation snapshot, receipt or mutation permit is accepted.
"""
from dataclasses import dataclass
from datetime import timedelta
from hashlib import sha256
import re

from src.adapters.postgres_definitions import PostgresDefinitionRepository
from src.adapters.postgres_evidence import PostgresEvidenceRepository
from src.adapters.postgres_generation import PostgresGenerationHandler
from src.adapters.postgres_migrations import schema_checked_transaction
from src.adapters.postgres_relationships import relation_from_payload
from src.adapters.postgres_stage_commit import PostgresStageCommitWriter
from src.adapters.postgres_tasks import PostgresTaskRepository
from src.adapters.postgres_transactions import PostgresTransactionCoordinator
from src.application.command_ledger import receipt_from_row, validate_audit_fingerprint, validate_caller
from src.application.definitions import DefinitionKey, canonical, identity
from src.application.evidence_storage import SourceScope
from src.application.generation_runtime import GenerationPolicy
from src.application.migrations import MigrationError
from src.application.ports import CommitReceipt, PortResult, RequestContext, TransactionPermit
from src.application.relationship_storage import acceptance_scope
from src.application.relationship_validation import GraphLimits
from src.application.stage_commands import StageCommandGrant, StageExecutionEvidence, StageOrderSnapshot, admit_stage_command
from src.application.stage_commit import StageCommandJournal, STORAGE_ORDER_LIMITS, can_resolve_stage_pending, digest, order_from_payload, prepare_stage_commit
from src.application.task_storage import TaskStorageBindings
from src.application.transactions import require
from src.domain.authorization import CallerIdentity
from src.domain.relationships import Endpoint
from src.domain.task_aggregate import instant


@dataclass(frozen=True)
class StageCommandOutcome:
    journal: StageCommandJournal
    receipt: CommitReceipt
    def __post_init__(self):
        require(isinstance(self.journal,StageCommandJournal) and isinstance(self.receipt,CommitReceipt)
            and self.receipt.request_id==self.journal.command.command_id
            and any(k.kind==self.journal.kind and k.id==self.journal.record_id for k in self.receipt.changed_keys),
            'STAGE_TYPED_OUTCOME')
    @property
    def state(self): return self.journal.state


def register_stage_command_grant(connection, grant, plan, *, application_version):
    """Trusted setup/resolver only; the command entrypoint never registers grants."""
    require(isinstance(grant, StageCommandGrant), 'STAGE_TYPED_GRANT')
    from psycopg.types.json import Jsonb
    c = grant.command
    expected = (c.principal_id, 'USER_COMMAND', grant.evidence_ref, c.fingerprint,
        grant.as_record(), grant.issued_at, grant.expires_at)
    with schema_checked_transaction(connection, plan, application_version=application_version, read_only=False):
        row = connection.execute('''SELECT principal_id,origin,source_record_ref,resolved_scope_hash,
            resolved_scope,issued_at,expires_at FROM whattodo.authority_record WHERE authority_ref=%s''', (c.authority_ref,)).fetchone()
        if row is not None:
            require(row == expected, 'STAGE_AUTHORITY_IMMUTABLE_CONFLICT'); return
        connection.execute('INSERT INTO whattodo.authority_record VALUES(%s,%s,%s,%s,%s,%s,%s,%s)',
            (c.authority_ref, *expected[:4], Jsonb(expected[4]), *expected[5:]))


class PostgresStageCommandHandler:
    def __init__(self, connection, codec, plan, *, application_version, clock, grants=(), source_scopes=(),
                 limits=GraphLimits(), definitions=None):
        require(isinstance(grants, tuple) and all(isinstance(g, StageCommandGrant) for g in grants)
            and len({g.command.authority_ref for g in grants}) == len(grants), 'STAGE_TRUSTED_GRANT_REGISTRY')
        require(isinstance(source_scopes, tuple) and len(source_scopes) <= 1000
            and all(isinstance(s, SourceScope) for s in source_scopes)
            and len({(s.provider,s.scope_ref) for s in source_scopes}) == len(source_scopes), 'STAGE_TRUSTED_SOURCE_REGISTRY')
        require(isinstance(limits, GraphLimits), 'STAGE_TYPED_LIMITS')
        require(definitions is None or isinstance(definitions, PostgresDefinitionRepository)
            and definitions.connection is connection and definitions.plan == plan, 'STAGE_TRUSTED_DEFINITIONS')
        self.connection = connection; self.codec = codec; self.plan = plan
        self.application_version = application_version; self.clock = clock; self.limits = limits
        self.grants = {g.command.authority_ref:g for g in grants}; self.scopes = source_scopes; self.definitions = definitions
        self.reader = PostgresTaskRepository(connection, codec, plan, application_version=application_version, clock=clock)
        self.evidence = PostgresEvidenceRepository(connection, codec, plan, application_version=application_version,
            clock=clock, scopes=source_scopes)
        self.writer = PostgresStageCommitWriter(connection, codec, plan, application_version=application_version, clock=clock)

    def _source(self, ref, *, at=None):
        evidence = self.evidence._source(ref)
        require(evidence is not None and evidence.source.source_type == 'USER', 'STAGE_USER_SOURCE_REQUIRED')
        require(evidence.source.captured_at <= (at or self.clock.now()), 'STAGE_FUTURE_SOURCE')
        return evidence.source

    def _authority(self, ref, principal, *, at=None):
        row = self.connection.execute('''SELECT principal_id,origin,source_record_ref,resolved_scope_hash,
            resolved_scope,issued_at,expires_at FROM whattodo.authority_record WHERE authority_ref=%s''', (ref,)).fetchone()
        require(row is not None and row[0] == principal, 'STAGE_FOREIGN_PRINCIPAL')
        self._source(row[2], at=at)
        if at is not None:
            require(row[5] <= at and (row[6] is None or at < row[6]), 'STAGE_INACTIVE_AUTHORITY')
        return row

    def _generated_receipt(self, transaction, principal, scope):
        require(self.definitions is not None, 'STAGE_GENERATED_DEFINITIONS_REQUIRED')
        generation = scope.get('authorization', {}).get('generation')
        require(isinstance(generation, dict) and identity(generation.get('rule_id')) and identity(generation.get('rule_version')),
            'STAGE_GENERATED_RECEIPT_SCOPE')
        policy = GenerationPolicy(principal, (DefinitionKey('RELATIONSHIP_RULE', generation['rule_id'], generation['rule_version']),),
            self.scopes, self.limits)
        return PostgresGenerationHandler(self.connection, self.codec, self.plan, application_version=self.application_version,
            clock=self.clock, policy=policy, definitions=self.definitions)._receipt(transaction)[0]

    def _owned_task(self, task_id, principal, *, revision=None):
        birth = self.connection.execute('''SELECT i.transaction_ref,c.principal_id,c.origin,c.authority_ref,c.committed_at
            FROM whattodo.task_identity i JOIN whattodo.command_transaction c ON c.request_id=i.transaction_ref
            WHERE i.task_id=%s''', (task_id,)).fetchone()
        require(birth is not None and birth[1] == principal, 'STAGE_PARENT_NOT_OWNED')
        key = (task_id, principal)
        if key not in self._owners:
            root = self._authority(birth[3], principal, at=birth[4])
            if birth[2] == 'USER_COMMAND':
                receipt = PostgresTransactionCoordinator(self.connection, self.codec, self.plan,
                    application_version=self.application_version, clock=self.clock)._lookup_in_transaction(
                        birth[0], CallerIdentity(principal, 'USER_COMMAND', True))
            else: receipt = self._generated_receipt(birth[0], principal, root[4])
            require(receipt is not None and any(k.kind == 'TASK' and k.id == task_id for k in receipt.changed_keys),
                'STAGE_PARENT_BIRTH_RECEIPT')
            self._owners.add(key)
        record = self.reader._get_in_transaction(task_id, revision)
        require(record is not None, 'STAGE_PARENT_HISTORY_UNAVAILABLE')
        return record

    def _binding(self, record):
        row = self.connection.execute('''SELECT p.profile_ref,t.notice_task_revision FROM whattodo.task_payload_revision p
            JOIN whattodo.task_revision t ON(t.task_id,t.revision)=(p.task_id,p.task_revision)
            WHERE p.task_id=%s AND p.task_revision=%s''', (record.task_id,record.revision)).fetchone()
        require(row is not None, 'STAGE_PARENT_BINDING_UNAVAILABLE')
        profile = None
        if row[0] is not None:
            key = self.connection.execute('SELECT kind,id,version FROM whattodo.definition_cache WHERE configuration_ref=%s', (row[0],)).fetchone()
            require(key is not None, 'STAGE_PARENT_PROFILE_UNAVAILABLE'); profile = DefinitionKey(*key)
        return TaskStorageBindings(profile,row[1])

    def _journal(self, record_id):
        row = self.connection.execute('SELECT runtime_payload,transaction_ref,audit_change_ref FROM whattodo.stage_command_journal WHERE record_id=%s',
            (record_id,)).fetchone()
        require(row is not None, 'STAGE_JOURNAL_UNAVAILABLE')
        journal = StageCommandJournal.from_payload(row[0]); values = journal.sql_row(row[1],row[2])
        from psycopg import sql
        actual = self.connection.execute(sql.SQL('SELECT {} FROM whattodo.stage_command_journal WHERE record_id=%s').format(
            sql.SQL(',').join(map(sql.Identifier, values))), (record_id,)).fetchone()
        require(actual == tuple(values.values()), 'STAGE_JOURNAL_PROJECTION_DRIFT')
        audit = self.connection.execute('''SELECT after_value,aggregate_kind,aggregate_id,after_revision,request_id
            FROM whattodo.audit_change WHERE change_id=%s''', (row[2],)).fetchone()
        require(audit == (journal.payload,journal.kind,journal.record_id,1,row[1]), 'STAGE_JOURNAL_AUDIT_DRIFT')
        return journal,row[1],row[2]

    def _execution(self, endpoint, task_id, principal, *, revision=None):
        record = self._owned_task(task_id,principal,revision=revision); value = record.aggregate.as_record()
        if endpoint.kind == 'TASK':
            return StageExecutionEvidence(endpoint,task_id,record.revision,value['core']['completion'],
                completed_at=instant(value['timing']['completed_at']) if value['timing']['completed_at'] is not None else None)
        detail = next((d for d in value['stage_details'] if d['stage_id']==endpoint.id),None)
        stage = next((s for s in value['effort']['stages'] if s['stage_id']==endpoint.id),None)
        require(detail is not None and stage is not None, 'STAGE_EXECUTION_TARGET_UNAVAILABLE')
        row = self.connection.execute('''SELECT record_id FROM whattodo.stage_command_journal
            WHERE task_id=%s AND stage_id=%s AND state='COMMITTED' AND after_task_revision<=%s
            ORDER BY after_task_revision DESC LIMIT 1''', (task_id,endpoint.id,record.revision)).fetchone()
        ended = None
        if row is not None:
            journal,_,_ = self._journal(row[0]); t = journal.transition
            if t['stage_revision']==detail['revision'] and stage['completion']=='COMPLETE' and journal.command.operation=='COMPLETE':
                reported = t['reported_completed_at'] or t['previous_stage_completed_at']
                ended = instant(reported) if reported is not None else None
        # Release times, source capture and class windows are not actual starts.
        return StageExecutionEvidence(endpoint,task_id,record.revision,stage['completion'],detail['revision'],completed_at=ended)

    def _relation(self, payload, principal):
        record = relation_from_payload(payload); r = record.relation; b = record.before; a = record.after
        require(record.payload == payload, 'STAGE_RELATION_PAYLOAD_DRIFT')
        row = self.connection.execute('''SELECT kind,before_kind,before_task_id,before_task_revision,before_stage_id,before_stage_revision,
            after_kind,after_task_id,after_task_revision,after_stage_id,after_stage_revision,acceptance_ref,transaction_ref,
            origin_rule_id,origin_rule_version FROM whattodo.task_relation_revision WHERE relation_id=%s AND revision=%s''',
            (r.relation_id,r.revision)).fetchone()
        expected = (r.kind,b.endpoint.kind,b.task_id,b.task_revision,b.endpoint.id if b.endpoint.kind=='STAGE' else None,b.stage_revision,
            a.endpoint.kind,a.task_id,a.task_revision,a.endpoint.id if a.endpoint.kind=='STAGE' else None,a.stage_revision,
            r.authority_ref,row[12] if row else None,r.origin_rule_id,r.origin_rule_version)
        require(row == expected, 'STAGE_RELATION_PROJECTION_DRIFT')
        txn = self.connection.execute('SELECT principal_id,origin,authority_ref,committed_at FROM whattodo.command_transaction WHERE request_id=%s',
            (row[12],)).fetchone()
        require(txn is not None and txn[:3] == (principal,txn[1],r.authority_ref), 'STAGE_RELATION_TRANSACTION_SCOPE')
        root = self._authority(r.authority_ref,principal,at=txn[3])
        if root[1] == 'USER_COMMAND':
            scope = acceptance_scope('RELATION',record)
            require(root[3:5] == (digest(scope),scope) and txn[1]=='USER_COMMAND', 'STAGE_RELATION_ACCEPTANCE_SCOPE')
        else:
            self._generated_receipt(row[12],principal,root[4])
        require(self.connection.execute('''SELECT after_value FROM whattodo.audit_change WHERE request_id=%s
            AND aggregate_kind='TASK_RELATION' AND aggregate_id=%s AND after_revision=%s''',
            (row[12],r.relation_id,r.revision)).fetchall() == [(payload,)], 'STAGE_RELATION_AUDIT_DRIFT')
        for binding in (b,a):
            parent = self._owned_task(binding.task_id,principal,revision=binding.task_revision)
            if binding.endpoint.kind=='STAGE':
                require(any(d['stage_id']==binding.endpoint.id and d['revision']==binding.stage_revision
                    for d in parent.aggregate.as_record()['stage_details']), 'STAGE_RELATION_HISTORICAL_OWNER_DRIFT')
        return record

    def _order(self, command):
        rows = self.connection.execute('''SELECT r.runtime_payload FROM
            (SELECT DISTINCT ON(relation_id) * FROM whattodo.task_relation_revision ORDER BY relation_id,revision DESC) r
            WHERE r.after_kind='STAGE' AND r.after_stage_id=%s AND r.kind IN ('COMPLETION_ORDER','START_PREREQUISITE')
            ORDER BY r.relation_id LIMIT %s''', (command.stage_id,self.limits.max_relations+1)).fetchall()
        require(len(rows)<=self.limits.max_relations, 'STAGE_CURRENT_RELATION_LIMIT')
        relations = tuple(self._relation(row[0],command.principal_id) for row in rows)
        endpoints = {Endpoint('STAGE',command.stage_id):command.task_id}
        for record in relations:
            require(record.after.task_id == command.task_id, 'STAGE_CURRENT_RELATION_OWNER_DRIFT')
            old = endpoints.setdefault(record.before.endpoint,record.before.task_id)
            require(old == record.before.task_id, 'STAGE_CURRENT_ENDPOINT_OWNER_DRIFT')
        require(len(endpoints)<=self.limits.max_endpoints, 'STAGE_CURRENT_ENDPOINT_LIMIT')
        executions = tuple(self._execution(e,owner,command.principal_id) for e,owner in sorted(endpoints.items(),key=lambda item:(item[0].kind,item[0].id)))
        return StageOrderSnapshot(relations,executions,self.limits)

    def _pending(self, command):
        rows=self.connection.execute('''SELECT record_id FROM whattodo.stage_command_journal j
            WHERE task_id=%s AND stage_id=%s AND before_stage_revision=%s AND state='PENDING'
             AND runtime_payload#>>'{command,principal_id}'=%s AND runtime_payload#>>'{command,operation}'=%s
             AND NOT EXISTS(SELECT 1 FROM whattodo.stage_pending_resolution r WHERE r.pending_ref=j.record_id)
            ORDER BY record_id LIMIT 101''',
            (command.task_id,command.stage_id,command.expected_stage_revision,command.principal_id,command.operation)).fetchall()
        require(len(rows)<=100,'STAGE_PENDING_QUEUE_LIMIT')
        selected=[]
        for row in rows:
            journal,_,_=self._journal(row[0])
            self._source(journal.source_ref)
            if can_resolve_stage_pending(journal,command):selected.append(journal)
        return tuple(selected)

    def _replay(self, command, caller, *, epoch=None, audit_id=None):
        row = self.connection.execute('''SELECT j.record_id,c.request_hash,c.principal_id,c.origin,c.authority_ref,
            c.expected_store_revision,c.committed_store_revision,c.audit_id,c.committed_at,c.receipt,e.source_record_ref,e.correlation_ref,e.committed_at
            FROM whattodo.stage_command_journal j JOIN whattodo.command_transaction c ON c.request_id=j.transaction_ref
            JOIN whattodo.audit_entry e ON(e.request_id,e.audit_id)=(c.request_id,c.audit_id) WHERE j.command_id=%s''',
            (command.command_id,)).fetchone()
        if row is None:
            require(self.connection.execute('SELECT 1 FROM whattodo.command_transaction WHERE request_id=%s',(command.command_id,)).fetchone() is None,
                'STAGE_REPLAY_SCOPE_CONFLICT')
            return None
        journal,tx,_ = self._journal(row[0])
        require(journal.command.fingerprint == command.fingerprint and row[2:4] == (caller.principal_id,'USER_COMMAND')
            and (epoch is None or epoch==row[5]) and (audit_id is None or audit_id==row[7]), 'STAGE_REPLAY_SCOPE_CONFLICT')
        require(tx==command.command_id and row[10]==journal.source_ref and row[12]==row[8], 'STAGE_REPLAY_RECEIPT_DRIFT')
        before = self._owned_task(command.task_id,command.principal_id,revision=command.expected_revision)
        require(before.content_hash==journal.before_task_hash, 'STAGE_REPLAY_PARENT_DRIFT')
        grant = self.writer._root(journal,row[8]); self._source(journal.source_ref,at=row[8])
        order = order_from_payload(journal.payload['order_snapshot'],limits=STORAGE_ORDER_LIMITS)
        for r in order.relations: require(self._relation(r.payload,command.principal_id)==r, 'STAGE_REPLAY_RELATION_DRIFT')
        for e in order.executions:
            require(self._execution(e.endpoint,e.task_id,command.principal_id,revision=e.task_revision)==e, 'STAGE_REPLAY_EXECUTION_DRIFT')
        resolution_rows=self.connection.execute('SELECT runtime_payload FROM whattodo.stage_pending_resolution WHERE transaction_ref=%s ORDER BY resolution_id',(tx,)).fetchall()
        pending=tuple(self._journal(v[0]['pending_ref'])[0] for v in resolution_rows)
        prepared = prepare_stage_commit(self.codec,journal.raw_command,grant,before,caller=caller,now=row[8],
            context=RequestContext(command.command_id,row[11]),expected_store_revision=row[5],audit_id=row[7],order=order,pending=pending)
        require([v[0] for v in resolution_rows]==sorted(prepared.resolutions,key=lambda v:v['resolution_id']), 'STAGE_REPLAY_RESOLUTION_DRIFT')
        receipt = receipt_from_row(row[9],request_id=tx,request_hash=row[1],store_revision=row[6],audit_id=row[7])
        require(receipt == prepared.receipt and prepared.journal == journal, 'STAGE_REPLAY_PLAN_DRIFT')
        root = self._authority(row[4],command.principal_id,at=row[8])
        annotation=dict(contract='stage-command',grant_ref=command.authority_ref,command_fingerprint=command.fingerprint,
            command=command.as_record(),command_wire_hash=journal.payload['raw_command_hash'],
            order_input_hash=journal.transition['order_input_hash'] if journal.transition is not None else None)
        require(root[:4] == (command.principal_id,'USER_COMMAND',journal.source_ref,prepared.request.fingerprint)
            and root[4]==dict(scope_kind='EXACT_TRANSACTION',request_fingerprint=prepared.request.fingerprint,authorization=annotation),
            'STAGE_REPLAY_PERMIT_DRIFT')
        changes = tuple(self.connection.execute('''SELECT aggregate_kind,aggregate_id,before_revision,after_revision,before_value,after_value
            FROM whattodo.audit_change WHERE request_id=%s AND audit_id=%s ORDER BY aggregate_kind,aggregate_id''',(tx,row[7])).fetchall())
        require(changes==tuple(a.tuple for a in prepared.audits), 'STAGE_REPLAY_AUDIT_DRIFT')
        validate_audit_fingerprint(receipt,principal_id=command.principal_id,expected_store_revision=row[5],
            source_ref=journal.source_ref,correlation_ref=row[11],changes=changes)
        if prepared.task is not None:
            after = self.reader._get_in_transaction(command.task_id,command.expected_revision+1)
            require(after == prepared.task, 'STAGE_REPLAY_TASK_DRIFT')
        observations = self.connection.execute('''SELECT observation_id,task_id,kind,seconds,observed_at,recorded_at,source_record_ref,authority_ref,batch_ref,transaction_ref
            FROM whattodo.effort_observation WHERE transaction_ref=%s ORDER BY observation_id''',(tx,)).fetchall()
        expected = sorted(((*o.row[:5],row[8],*o.row[5:],None,tx) for o in prepared.observations),key=lambda v:v[0])
        require(observations == expected, 'STAGE_REPLAY_OBSERVATION_DRIFT')
        issues = self.connection.execute('SELECT runtime_payload FROM whattodo.stage_relationship_issue WHERE transaction_ref=%s ORDER BY issue_id',(tx,)).fetchall()
        require([v[0] for v in issues]==sorted(prepared.issues,key=lambda v:v['issue_id']), 'STAGE_REPLAY_ISSUE_DRIFT')
        require(self.connection.execute('SELECT revision FROM whattodo.store_epoch WHERE singleton=TRUE').fetchone()[0]>=receipt.store_revision,
            'STAGE_REPLAY_EPOCH_DRIFT')
        return StageCommandOutcome(journal,receipt)

    def _run(self, raw, context, caller, *, epoch=None, audit_id=None, lookup=False):
        require(isinstance(context,RequestContext), 'TYPED_REQUEST_CONTEXT_REQUIRED')
        correlation = context.correlation_ref; phase = 'ADMISSION'; database_error = (); transport_error = (); interface_error = ()
        try:
            command = admit_stage_command(self.codec,raw); validate_caller(caller,principal_id=command.principal_id)
            require(caller.origin=='USER_COMMAND' and context.request_id==command.command_id, 'STAGE_TRUSTED_USER_CALLER')
            from psycopg import Error as database_error, OperationalError as transport_error, InterfaceError as interface_error
            require(any(s.migration_id=='017_stage_commands' for s in self.plan.steps), 'STAGE_SCHEMA_NOT_ENABLED')
            self._owners = set()
            with schema_checked_transaction(self.connection,self.plan,application_version=self.application_version,read_only=lookup):
                prior = self._replay(command,caller,epoch=epoch,audit_id=audit_id)
                if prior is not None: return PortResult('SUCCESS','STAGE_COMMAND_REPLAYED',correlation,prior)
                if lookup: return PortResult('UNKNOWN','STAGE_COMMAND_NOT_OBSERVED',correlation)
                grant = self.grants.get(command.authority_ref)
                require(grant is not None and grant.command.fingerprint==command.fingerprint, 'STAGE_INDEPENDENT_GRANT_REQUIRED')
                self._source(grant.evidence_ref)
                before = self._owned_task(command.task_id,command.principal_id)
                prepared = prepare_stage_commit(self.codec,raw,grant,before,caller=caller,now=self.clock.now(),context=context,
                    expected_store_revision=epoch,audit_id=audit_id)
                if prepared.journal.state=='COMMITTED':
                    order=self._order(command)
                    prepared=prepare_stage_commit(self.codec,raw,grant,before,caller=caller,now=self.clock.now(),context=context,
                        expected_store_revision=epoch,audit_id=audit_id,order=order,pending=self._pending(command))
                require(self.writer._root(prepared.journal,self.clock.now()) == grant, 'STAGE_REGISTERED_AUTHORITY_MISMATCH')
                now = self.clock.now(); expires = min(now+timedelta(minutes=1),grant.expires_at) if grant.expires_at else now+timedelta(minutes=1)
                permit = TransactionPermit('stage-permit-'+sha256((command.fingerprint+prepared.request.fingerprint).encode()).hexdigest(),
                    command.principal_id,'USER_COMMAND',prepared.request.fingerprint,now,expires)
                phase = 'STAGING'
                self.writer.append_in_transaction(prepared,caller=caller,permit=permit,bindings=self._binding(before))
                phase = 'COMMITTING'
            return PortResult('SUCCESS','STAGE_COMMAND_'+prepared.journal.state,correlation,StageCommandOutcome(prepared.journal,prepared.receipt))
        except MigrationError as exc:
            retry = str(exc) in ('MIGRATION_BUSY','MIGRATION_METADATA_UNREADABLE')
            return PortResult('RETRYABLE' if retry else 'PERMANENT','STAGE_SCHEMA_UNAVAILABLE' if retry else 'STAGE_SCHEMA_INCOMPATIBLE',correlation)
        except ImportError: return PortResult('PERMANENT','TRANSACTION_DRIVER_UNAVAILABLE',correlation)
        except database_error as exc:
            if phase=='COMMITTING' and (isinstance(exc,(transport_error,interface_error)) or exc.sqlstate is None):
                return PortResult('UNKNOWN','STAGE_ACKNOWLEDGEMENT_LOST',correlation)
            if isinstance(exc,(transport_error,interface_error)) or exc.sqlstate in ('55P03','40001','40P01'):
                return PortResult('RETRYABLE','STAGE_STORAGE_UNAVAILABLE',correlation)
            return PortResult('CONFLICT' if exc.sqlstate=='23505' else 'PERMANENT','STAGE_DATABASE_REJECTED',correlation)
        except (ValueError,RuntimeError) as exc:
            code = str(exc) if re.fullmatch('[A-Z][A-Z0-9_]{0,63}',str(exc)) else 'STAGE_COMMAND_INVALID'
            conflict = any(s in code for s in ('STALE','CONFLICT','MISMATCH','DRIFT'))
            return PortResult('CONFLICT' if conflict else 'PERMANENT',code,correlation)
        except Exception: return PortResult('PERMANENT','STAGE_COMMAND_INTERNAL_FAILURE',correlation)

    def execute(self, raw, context, *, expected_store_revision, audit_id, caller):
        return self._run(raw,context,caller,epoch=expected_store_revision,audit_id=audit_id)

    def lookup(self, raw, context, *, caller):
        return self._run(raw,context,caller,lookup=True)
