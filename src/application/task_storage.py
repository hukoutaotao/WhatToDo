"""Lossless admitted Task storage values and normalized row projections.

These values confer no authority and perform no I/O. Transaction handlers must
independently resolve references, caller scope, permits, audit and concurrency.
"""
from dataclasses import dataclass, field
from datetime import datetime
from fractions import Fraction
from hashlib import sha256
import json
from typing import Protocol

from src.application.definitions import DefinitionKey
from src.application.task_aggregate import admit_task
from src.domain.task_aggregate import TaskAggregate, instant


class TaskStorageError(RuntimeError):
    pass


def require(value, code):
    if not value:
        raise TaskStorageError(code)


@dataclass(frozen=True)
class TaskStorageRecord:
    """Original supported bytes plus detached facts; not a transaction permit."""
    raw_bytes: bytes = field(repr=False)
    content_hash: str
    aggregate: TaskAggregate

    def __post_init__(self):
        require(isinstance(self.raw_bytes, bytes) and 0 < len(self.raw_bytes) <= 1048576,
                'TASK_STORAGE_SIZE')
        require(sha256(self.raw_bytes).hexdigest() == self.content_hash,
                'TASK_STORAGE_HASH')
        require(isinstance(self.aggregate, TaskAggregate), 'TASK_STORAGE_AGGREGATE')
        # Construction is internal; trusted codec admission happens in admit_storage.
        require(json.loads(self.raw_bytes) == self.aggregate.as_record(),
                'TASK_STORAGE_PAYLOAD_DRIFT')

    @property
    def task_id(self):
        return self.aggregate.as_record()['core']['task_id']

    @property
    def revision(self):
        return self.aggregate.as_record()['core']['revision']


def admit_storage(codec, raw):
    require(isinstance(raw, bytes) and 0 < len(raw) <= 1048576, 'TASK_STORAGE_SIZE')
    admitted = admit_task(codec, raw)
    require(admitted.status == 'CONSISTENT_FACTS', 'TASK_STORAGE_ADMISSION')
    return TaskStorageRecord(raw, sha256(raw).hexdigest(), admitted.aggregate)


@dataclass(frozen=True)
class TaskStorageBindings:
    profile_key: DefinitionKey | None = None
    notice_task_revision: int | None = None

    def __post_init__(self):
        require(self.profile_key is None or isinstance(self.profile_key, DefinitionKey),
                'TASK_STORAGE_PROFILE_KEY')
        require(self.notice_task_revision is None or
                (type(self.notice_task_revision) is int and self.notice_task_revision > 0),
                'TASK_STORAGE_NOTICE_REVISION')


def validate_bindings(record, bindings):
    require(isinstance(record, TaskStorageRecord) and isinstance(bindings, TaskStorageBindings),
            'TASK_STORAGE_TYPED_VALUES')
    core = record.aggregate.as_record()['core']
    context = core['context']
    if context is not None and context['kind'] in ('COURSE', 'ACTIVITY'):
        kind = 'COURSE_PROFILE' if context['kind'] == 'COURSE' else 'ACTIVITY_PROFILE'
        require(bindings.profile_key is not None and
                (bindings.profile_key.kind, bindings.profile_key.id) == (kind, context['id']),
                'TASK_STORAGE_PROFILE_VERSION_REQUIRED')
    else:
        require(bindings.profile_key is None, 'TASK_STORAGE_PROFILE_CONTEXT_MISMATCH')
    if core['disposition'] == 'EXPIRED':
        require(bindings.notice_task_revision is not None and
                bindings.notice_task_revision < core['revision'],
                'TASK_STORAGE_NOTICE_REVISION_REQUIRED')
    else:
        require(bindings.notice_task_revision is None, 'TASK_STORAGE_UNEXPECTED_NOTICE_REVISION')


@dataclass(frozen=True)
class TaskRowProjection:
    """Detached normalized projections alongside retained wire representation."""
    _rows_json: str = field(repr=False)

    @property
    def rows(self):
        return json.loads(self._rows_json)


def project_task(record, bindings):
    validate_bindings(record, bindings)
    value = record.aggregate.as_record()
    core, effort, timing, work = (value[k] for k in ('core', 'effort', 'timing', 'work'))
    context, expiration, estimate = core['context'], core['expiration'], effort['user_remaining']
    task_type = core['task_type_ref']
    deadline, release, total = timing['deadline'], timing['release'], work['total_estimate']
    definition = total['definition_ref'] if total is not None else None
    task = dict(task_id=core['task_id'], revision=core['revision'], title=core['title'],
        domain=core['domain'], context_kind=context['kind'] if context else None,
        context_id=context['id'] if context else None,
        task_type_ref=DefinitionKey('TASKTYPE', **task_type).configuration_ref if task_type else None,
        acceptance_ref=core['acceptance']['authority_ref'], completion=core['completion'],
        disposition=core['disposition'], requiredness=core['requiredness'],
        importance=core['importance'], **core['difficulty'],
        user_remaining_seconds=estimate['seconds'] if estimate else None,
        estimate_observation_id=estimate['observation_id'] if estimate else None,
        estimate_kind='USER_REMAINING' if estimate else None,
        expiration_condition_ref=expiration['condition_ref'] if expiration else None,
        expiration_notice_ref=expiration['notice_ref'] if expiration else None,
        notice_task_revision=bindings.notice_task_revision, aggregate_kind='TASK',
        metadata=core['metadata'], due_ref=deadline['due_ref'] if deadline else None)
    details = dict(task_id=record.task_id, task_revision=record.revision,
        completion=core['completion'], created_at=timing['created_at'],
        release_at=release['instant'] if release else None,
        release_original=release['original_value'] if release else None,
        release_source_record_ref=release['source_ref'] if release else None,
        completed_at=timing['completed_at'],
        total_estimate_seconds=total['seconds'] if total else None,
        total_source_record_ref=total['source_ref'] if total else None,
        total_observed_at=total['observed_at'] if total else None,
        total_basis=total['basis'] if total else None,
        total_definition_kind=definition['kind'] if definition else None,
        total_definition_id=definition['id'] if definition else None,
        total_definition_version=definition['version'] if definition else None,
        minimum_session_seconds=work['minimum_session_seconds'], fragmentable=work['fragmentable'])
    by_id = {s['stage_id']: s for s in value['stage_details']}
    stages, stage_estimates, membership = [], [], []
    for ordinal, stage in enumerate(effort['stages']):
        detail = by_id[stage['stage_id']]
        weight = Fraction(str(stage['weight'])) if stage['weight'] is not None else None
        u = stage['user_remaining']
        stages.append(dict(stage_id=stage['stage_id'], revision=detail['revision'],
            task_id=record.task_id, title=detail['title'], completion=stage['completion'],
            user_remaining_seconds=u['seconds'] if u else None,
            acceptance_ref=core['acceptance']['authority_ref'],
            weight_numerator=weight.numerator if weight else None,
            weight_denominator=weight.denominator if weight else None))
        stage_estimates.append(dict(stage_id=stage['stage_id'], stage_revision=detail['revision'],
            task_id=record.task_id, user_remaining_seconds=u['seconds'] if u else None,
            observation_id=u['observation_id'] if u else None,
            estimate_kind='USER_REMAINING' if u else None,
            observed_at=u['observed_at'] if u else None, verified_at=u['verified_at'] if u else None))
        membership.append(dict(task_id=record.task_id, task_revision=record.revision,
            stage_id=stage['stage_id'], stage_revision=detail['revision'], ordinal=ordinal))
    provenance = [dict(task_id=record.task_id, task_revision=record.revision,
        field_pointer=p['field'], source_record_ref=p['source_ref']) for p in value['provenance']]
    payload = dict(task_id=record.task_id, task_revision=record.revision,
        content_hash=record.content_hash,
        profile_ref=bindings.profile_key.configuration_ref if bindings.profile_key else None,
        prediction_ref=effort['prediction']['prediction_id'] if effort['prediction'] else None)
    rows = dict(task_revision=task, task_details_revision=details,
        stage_revision=stages, stage_effort_revision=stage_estimates,
        task_stage_revision=membership, task_field_provenance=provenance,
        task_payload_revision=payload)
    return TaskRowProjection(json.dumps(rows, ensure_ascii=False, allow_nan=False,
        separators=(',', ':')))


def sql_value(column, value):
    """Explicit offsets normalize only for SQL comparison, never retained bytes."""
    if value is not None and column.endswith('_at'):
        if isinstance(value, datetime):
            require(value.utcoffset() is not None, 'TASK_STORAGE_EXPLICIT_TIME_REQUIRED')
            return value
        return instant(value)
    return value


class TaskRepository(Protocol):
    def get(self, task_id: str, revision: int | None = None) -> TaskStorageRecord | None: ...
