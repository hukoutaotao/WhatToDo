"""Exact composite stage journals and audit plans; never mutation authority.

The SQL handler must independently resolve ownership, grants and the complete
current order snapshot, then call this builder inside its transaction. A plan
or a journal reconstructed from stored JSON does not authorize a write.
"""
from base64 import b64decode, b64encode
from dataclasses import asdict, dataclass, field
from datetime import datetime
from hashlib import sha256
import re

from src.application.definitions import canonical, identity, strict_json
from src.application.ports import AggregateKey, CommitRequest, CommitReceipt, RecordWrite, RequestContext
from src.application.relationship_storage import EndpointBinding, RelationStorageRecord
from src.application.stage_commands import (StageCommand, StageCommandGrant, StageExecutionEvidence,
    StageOrderSnapshot, admit_stage_command, prepare_stage_command)
from src.application.task_storage import TaskStorageRecord
from src.application.transactions import require
from src.domain.relationships import Endpoint, TaskRelation
from src.domain.task_aggregate import instant

VERSION = '0.1.0-stage-journal'


def digest(value):
    return sha256(canonical(value).encode()).hexdigest()


def command_from_payload(value):
    require(isinstance(value, dict), 'STAGE_JOURNAL_COMMAND')
    try:
        t = value['target_ref']
        command = StageCommand(value['command_id'], value['principal_id'], value['authority_ref'],
            t['task_id'], t['revision'], t['stage_id'], t['stage_revision'], value['operation'], canonical(value['fields']))
    except (KeyError, TypeError, ValueError):
        require(False, 'STAGE_JOURNAL_COMMAND')
    require(value == command.as_record(), 'STAGE_JOURNAL_COMMAND')
    return command


def order_from_payload(value):
    require(isinstance(value, dict) and set(value) == {'relations', 'executions'}, 'STAGE_JOURNAL_ORDER')
    try:
        relations = []
        for item in value['relations']:
            r = dict(item['relation']); r.pop('schema_version')
            r['before'] = Endpoint(**r['before']); r['after'] = Endpoint(**r['after'])
            bindings = []
            for name in ('before', 'after'):
                b = dict(item[name]); b['endpoint'] = Endpoint(**b['endpoint'])
                bindings.append(EndpointBinding(**b))
            relations.append(RelationStorageRecord(TaskRelation(**r), *bindings))
        executions = []
        for item in value['executions']:
            e = dict(item); e['endpoint'] = Endpoint(**e['endpoint'])
            for name in ('started_at', 'completed_at'):
                e[name] = instant(e[name]) if e[name] is not None else None
            executions.append(StageExecutionEvidence(**e))
        order = StageOrderSnapshot(tuple(relations), tuple(executions))
    except (KeyError, TypeError, ValueError, OverflowError):
        require(False, 'STAGE_JOURNAL_ORDER')
    require(order.payload == value, 'STAGE_JOURNAL_ORDER')
    return order


@dataclass(frozen=True)
class StageCommandJournal:
    command: StageCommand = field(repr=False)
    source_ref: str
    source_observed_at: datetime
    raw_command: bytes = field(repr=False)
    before_task_hash: str
    after_task_hash: str | None
    state: str
    code: str
    missing_fields: tuple[str, ...] = ()
    transition_json: str | None = field(default=None, repr=False)
    order_json: str = field(default='{"executions":[],"relations":[]}', repr=False)

    def __post_init__(self):
        require(isinstance(self.command, StageCommand) and identity(self.source_ref), 'STAGE_JOURNAL_IDENTITY')
        require(isinstance(self.source_observed_at, datetime) and self.source_observed_at.utcoffset() is not None,
            'STAGE_JOURNAL_SOURCE_TIME')
        require(isinstance(self.raw_command, bytes) and 0 < len(self.raw_command) <= 262144
            and command_from_payload(strict_json(self.raw_command.decode('utf-8'))) == self.command, 'STAGE_JOURNAL_RAW_COMMAND')
        require(isinstance(self.before_task_hash, str) and re.fullmatch('[a-f0-9]{64}', self.before_task_hash)
            and (self.after_task_hash is None or isinstance(self.after_task_hash, str)
                and re.fullmatch('[a-f0-9]{64}', self.after_task_hash)), 'STAGE_JOURNAL_TASK_HASH')
        require(isinstance(self.code, str) and re.fullmatch('[A-Z][A-Z0-9_]{0,63}', self.code), 'STAGE_JOURNAL_CODE')
        require(isinstance(self.missing_fields, tuple) and self.missing_fields == tuple(sorted(set(self.missing_fields)))
            and len(self.missing_fields) <= 100 and all(identity(k) for k in self.missing_fields), 'STAGE_JOURNAL_MISSING_FIELDS')
        require((self.state == 'PENDING' and self.after_task_hash is None and self.transition_json is None and self.missing_fields)
            or (self.state == 'COMMITTED' and self.after_task_hash is not None and self.transition_json is not None and not self.missing_fields),
            'STAGE_JOURNAL_EFFECTS')
        require(isinstance(self.order_json, str) and len(self.order_json.encode()) <= 8388608, 'STAGE_JOURNAL_ORDER_SIZE')
        order = order_from_payload(strict_json(self.order_json))
        object.__setattr__(self, 'order_json', canonical(order.payload))
        if self.transition_json is not None:
            require(isinstance(self.transition_json, str) and len(self.transition_json.encode()) <= 8388608, 'STAGE_JOURNAL_TRANSITION_SIZE')
            t = strict_json(self.transition_json); c = self.command
            require(isinstance(t, dict) and set(t) == {'command', 'command_fingerprint', 'source_ref', 'source_observed_at',
                'previous_parent_revision', 'parent_revision', 'previous_stage_revision', 'stage_revision',
                'previous_parent_completion', 'previous_stage_completion', 'previous_parent_completed_at',
                'previous_stage_completed_at', 'target_execution', 'order_input_hash', 'reported_completed_at', 'issues', 'order_snapshot'},
                'STAGE_JOURNAL_TRANSITION')
            require(t['command'] == c.as_record() and t['command_fingerprint'] == c.fingerprint
                and t['source_ref'] == self.source_ref and t['source_observed_at'] == self.source_observed_at.isoformat()
                and type(t['previous_parent_revision']) is int and t['previous_parent_revision'] == c.expected_revision
                and type(t['parent_revision']) is int and t['parent_revision'] == c.expected_revision + 1
                and type(t['previous_stage_revision']) is int and t['previous_stage_revision'] == c.expected_stage_revision
                and type(t['stage_revision']) is int and t['stage_revision'] in (c.expected_stage_revision, c.expected_stage_revision + 1)
                and t['order_input_hash'] == digest(order.payload), 'STAGE_JOURNAL_TRANSITION_BINDING')
            require(isinstance(t['issues'], list) and len(t['issues']) <= order.limits.max_relations, 'STAGE_JOURNAL_ISSUES')
            accepted = {(r.relation.relation_id, r.relation.revision, r.relation.kind) for r in order.relations
                if r.relation.after == Endpoint('STAGE', c.stage_id) and r.relation.kind in ('COMPLETION_ORDER', 'START_PREREQUISITE')}
            keys = []
            for issue in t['issues']:
                require(isinstance(issue, dict) and set(issue) == {'code', 'relation_id', 'relation_revision', 'kind'}
                    and issue['code'] in ('PREREQUISITE_INCOMPLETE', 'ORDER_EVIDENCE_MISSING', 'ORDER_VIOLATION')
                    and type(issue['relation_revision']) is int
                    and (issue['relation_id'], issue['relation_revision'], issue['kind']) in accepted, 'STAGE_JOURNAL_ISSUE_BINDING')
                keys.append((issue['relation_id'], issue['relation_revision'], issue['code']))
            require(len(keys) == len(set(keys)), 'STAGE_JOURNAL_DUPLICATE_ISSUE')
            object.__setattr__(self, 'transition_json', canonical(t))

    @property
    def record_id(self): return 'stage-journal-' + self.command.fingerprint
    @property
    def kind(self): return 'STAGE_PENDING' if self.state == 'PENDING' else 'STAGE_TRANSITION'
    @property
    def transition(self): return strict_json(self.transition_json) if self.transition_json is not None else None
    @property
    def payload(self):
        return dict(schema_version=VERSION, record_id=self.record_id, kind=self.kind, command=self.command.as_record(),
            command_fingerprint=self.command.fingerprint, source_ref=self.source_ref,
            source_observed_at=self.source_observed_at.isoformat(), raw_command_base64=b64encode(self.raw_command).decode('ascii'),
            raw_command_hash=sha256(self.raw_command).hexdigest(), before_task_hash=self.before_task_hash,
            after_task_hash=self.after_task_hash, state=self.state, code=self.code, missing_fields=list(self.missing_fields),
            transition=self.transition, order_snapshot=strict_json(self.order_json))

    def sql_row(self, transaction_ref, audit_change_ref):
        require(identity(transaction_ref) and identity(audit_change_ref), 'STAGE_JOURNAL_TRANSACTION')
        c = self.command; t = self.transition
        return dict(record_id=self.record_id, command_id=c.command_id, aggregate_kind=self.kind, revision=1,
            task_id=c.task_id, before_task_revision=c.expected_revision,
            after_task_revision=t['parent_revision'] if t else None, stage_id=c.stage_id,
            before_stage_revision=c.expected_stage_revision, after_stage_revision=t['stage_revision'] if t else None,
            authority_ref=c.authority_ref, source_ref=self.source_ref, source_observed_at=self.source_observed_at,
            raw_command=self.raw_command, raw_command_hash=sha256(self.raw_command).hexdigest(),
            before_task_hash=self.before_task_hash, after_task_hash=self.after_task_hash, state=self.state, code=self.code,
            transaction_ref=transaction_ref, audit_change_ref=audit_change_ref, runtime_payload=self.payload)

    @classmethod
    def from_payload(cls, value):
        require(isinstance(value, dict), 'STAGE_JOURNAL_PAYLOAD')
        try:
            result = cls(command_from_payload(value['command']), value['source_ref'], instant(value['source_observed_at']),
                b64decode(value['raw_command_base64'], validate=True), value['before_task_hash'], value['after_task_hash'],
                value['state'], value['code'], tuple(value['missing_fields']),
                canonical(value['transition']) if value['transition'] is not None else None, canonical(value['order_snapshot']))
        except (KeyError, TypeError, ValueError, OverflowError):
            require(False, 'STAGE_JOURNAL_PAYLOAD')
        require(result.payload == value, 'STAGE_JOURNAL_PAYLOAD')
        return result


@dataclass(frozen=True)
class StageAuditChange:
    change_ref: str
    key: AggregateKey
    before_revision: int | None
    after_revision: int
    before_json: str | None = field(repr=False)
    after_json: str = field(repr=False)
    @property
    def tuple(self):
        return (self.key.kind, self.key.id, self.before_revision, self.after_revision,
            strict_json(self.before_json) if self.before_json is not None else None, strict_json(self.after_json))


@dataclass(frozen=True)
class StageCommitPlan:
    request: CommitRequest
    receipt: CommitReceipt
    journal: StageCommandJournal = field(repr=False)
    task: TaskStorageRecord | None = field(repr=False)
    observations: tuple = field(repr=False)
    audits: tuple[StageAuditChange, ...] = field(repr=False)
    issue_jsons: tuple[str, ...] = field(default=(), repr=False)
    @property
    def receipt_body(self): return asdict(self.receipt)
    @property
    def issues(self): return tuple(strict_json(v) for v in self.issue_jsons)


def prepare_stage_commit(codec, raw, grant, before, *, caller, now, context, expected_store_revision, audit_id,
                         order=StageOrderSnapshot()):
    """Recompute exact effects from independently resolved inputs, without a permit."""
    command = admit_stage_command(codec, raw)
    require(isinstance(context, RequestContext) and context.request_id == command.command_id, 'STAGE_COMMIT_REQUEST_SCOPE')
    prepared = prepare_stage_command(codec, command, grant, before, caller=caller, now=now, order=order)
    journal = StageCommandJournal(command, grant.evidence_ref, grant.source_observed_at, raw, before.content_hash,
        prepared.record.content_hash if prepared.record else None, 'COMMITTED' if prepared.state == 'PREPARED' else 'PENDING',
        prepared.code, tuple(sorted(prepared.missing_fields)), prepared.transition_json, canonical(order.payload))
    changes = []
    if prepared.record is not None:
        changes.append((AggregateKey('TASK', before.task_id), before.revision, prepared.record.revision,
            before.aggregate.as_record(), prepared.record.aggregate.as_record()))
    changes.append((AggregateKey(journal.kind, journal.record_id), None, 1, None, journal.payload))
    issues = []
    for item in journal.transition['issues'] if journal.transition is not None else ():
        body = dict(issue_id='stage-issue-' + digest([journal.record_id, item]), transition_ref=journal.record_id, **item)
        issues.append(canonical(body))
        changes.append((AggregateKey('STAGE_RELATIONSHIP_ISSUE', body['issue_id']), None, 1, None, body))
    require(len(changes) <= 100, 'STAGE_COMMIT_EFFECT_LIMIT')
    changes.sort(key=lambda c: (c[0].kind, c[0].id))
    writes = tuple(RecordWrite(key, revision, canonical(new)) for key, revision, _, _, new in changes)
    require(sum(len(w.body_json.encode()) for w in writes) <= 8388608, 'STAGE_COMMIT_SIZE_LIMIT')
    request = CommitRequest(context, command.principal_id, expected_store_revision, writes, audit_id, grant.evidence_ref)
    receipt = CommitReceipt(command.command_id, request.fingerprint, expected_store_revision + 1, audit_id, tuple(w.key for w in writes))
    audits = tuple(StageAuditChange('change-' + digest([audit_id, key.kind, key.id, after]), key, revision, after,
        canonical(old) if old is not None else None, canonical(new)) for key, revision, after, old, new in changes)
    return StageCommitPlan(request, receipt, journal, prepared.record, prepared.estimates, audits, tuple(issues))
