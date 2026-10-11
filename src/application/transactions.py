"""Bounded, detached preparation for exact-permit audited Task transactions."""
from dataclasses import asdict, dataclass, field
from datetime import datetime
from hashlib import sha256
import json

from src.application.ports import (CommitReceipt, CommitRequest, TransactionPermit)
from src.application.task_storage import (TaskStorageBindings, TaskStorageRecord,
    admit_storage, validate_bindings)
from src.domain.authorization import CallerIdentity


class TransactionError(RuntimeError):
    """Redacted semantic diagnostic; no input/provider content in messages."""


def require(value, code):
    if not value:
        raise TransactionError(code)


def valid_permit(request, caller, permit, at):
    require(isinstance(caller, CallerIdentity) and caller.authenticated and
        caller.origin != 'EXTERNAL' and caller.principal_id == request.principal_id,
        'UNTRUSTED_CALLER')
    require(isinstance(at, datetime) and at.utcoffset() is not None,
        'TRANSACTION_CLOCK_REQUIRED')
    require(isinstance(permit, TransactionPermit) and permit.active and
        permit.issued_at <= at < permit.expires_at and
        (permit.principal_id, permit.origin, permit.request_fingerprint) ==
        (caller.principal_id, caller.origin, request.fingerprint),
        'EXACT_ACTIVE_PERMIT_REQUIRED')


@dataclass(frozen=True)
class PreparedTaskWrite:
    record: TaskStorageRecord = field(repr=False)
    bindings: TaskStorageBindings
    change_ref: str


@dataclass(frozen=True)
class PreparedActualWorkWrite:
    record: object = field(repr=False)
    change_ref: str


@dataclass(frozen=True)
class PreparedTransaction:
    writes: tuple[PreparedTaskWrite | PreparedActualWorkWrite, ...] = field(repr=False)
    receipt: CommitReceipt

    @property
    def receipt_body(self):
        return asdict(self.receipt)


def prepare_transaction(codec, request, *, caller, permit, at, bindings=()):
    require(isinstance(request, CommitRequest), 'TYPED_TRANSACTION_REQUIRED')
    valid_permit(request, caller, permit, at)
    require(1 <= len(request.writes) <= 100 and
        sum(len(w.body_json.encode('utf-8')) for w in request.writes) <= 8388608,
        'TRANSACTION_SIZE_LIMIT')
    require(request.expected_store_revision < 9223372036854775807,
        'TRANSACTION_REVISION_LIMIT')
    require(isinstance(bindings, tuple) and all(isinstance(b, tuple) and len(b)==2
        and isinstance(b[0], str) and isinstance(b[1], TaskStorageBindings)
        for b in bindings) and len({b[0] for b in bindings}) == len(bindings),
        'TRANSACTION_BINDING_REGISTRY')
    by_id = dict(bindings)
    writes = []
    for write in request.writes:
        if write.key.kind=='WORK_REPORT':
            from src.application.work_reports import admit_actual_record
            record=admit_actual_record(codec,write.body_json.encode())
            require(write.key.id==record.observation_id and write.expected_revision is None,'TRANSACTION_EXACT_WRITE_REQUIRED')
            report=record.report
            task_write=next((w for w in request.writes if w.key.kind=='TASK' and w.key.id==record.task_id),None)
            require(task_write is not None and task_write.expected_revision==report.expected_revision
                and (report.command_id,report.principal_id,record.as_record()['source_ref'])==
                    (request.context.request_id,request.principal_id,request.source_ref),'TRANSACTION_WORK_REPORT_SCOPE')
            change_ref='change-'+sha256(json.dumps([request.audit_id,write.key.kind,write.key.id,1],separators=(',',':')).encode()).hexdigest()
            writes.append(PreparedActualWorkWrite(record,change_ref));continue
        require(write.key.kind == 'TASK', 'TRANSACTION_UNSUPPORTED_AGGREGATE')
        record = admit_storage(codec, write.body_json.encode('utf-8'))
        require(record.task_id == write.key.id and
            record.revision == (write.expected_revision or 0)+1 and
            record.revision <= 9223372036854775807,
            'TRANSACTION_EXACT_WRITE_REQUIRED')
        binding = by_id.get(record.task_id, TaskStorageBindings())
        validate_bindings(record, binding)
        change_ref = 'change-'+sha256(json.dumps([request.audit_id,
            write.key.kind,write.key.id,record.revision],separators=(',',':')).encode()).hexdigest()
        writes.append(PreparedTaskWrite(record,binding,change_ref))
    receipt = CommitReceipt(request.context.request_id,request.fingerprint,
        request.expected_store_revision+1,request.audit_id,
        tuple(w.key for w in request.writes))
    return PreparedTransaction(tuple(writes),receipt)
