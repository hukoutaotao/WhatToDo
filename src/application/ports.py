"""Internal application ports; never deserialize trusted caller/permits from input.

JSON aggregate bodies remain opaque to storage. Domain/schema/reference checks
and transaction-bound authority resolution precede writes in the application.
These contracts introduce neither a transport nor provider dependencies.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime
from hashlib import sha256
import json
import re
from typing import Generic, Protocol, TypeVar, runtime_checkable

from src.domain.ai_results import AIJob, AIResult
from src.domain.authorization import CallerIdentity
from src.domain.expiration import DispatchAttempt, DispatchResult
from src.domain.forecast import PlacementEvidence, RequiredProjection, forecast_fingerprint
from src.domain.plan_output import PlanSnapshot
from src.domain.provenance import SourceRecord
from src.domain.time_windows import AvailabilityFrame, CalendarEvent, ForecastWindow, Interval


T = TypeVar("T")


def identity(value):
    if not isinstance(value, str) or not value.strip():
        raise ValueError("A nonblank reference is required")


def instant(value):
    if not isinstance(value, datetime) or value.utcoffset() is None:
        raise ValueError("An aware instant is required")


def revision(value):
    if type(value) is not int or value < 1:
        raise ValueError("A positive revision is required")


def fingerprint(value):
    return sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()).hexdigest()


def _pairs(items):
    result = {}
    for name, value in items:
        if name in result:
            raise ValueError("Duplicate JSON field")
        result[name] = value
    return result


def _nonfinite(value):
    raise ValueError("Non-finite JSON value")


def canonical_body(raw):
    value = json.loads(raw, object_pairs_hook=_pairs, parse_constant=_nonfinite)
    if not isinstance(value, dict):
        raise ValueError("An aggregate body is an object")
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)


@dataclass(frozen=True)
class PortResult(Generic[T]):
    status: str
    code: str
    correlation_ref: str
    value: T | None = None

    def __post_init__(self):
        identity(self.correlation_ref)
        if not isinstance(self.code, str) or not re.fullmatch(r"[A-Z][A-Z0-9_]*", self.code):
            raise ValueError("Diagnostics are redacted codes, not raw provider messages")
        if self.status not in ("SUCCESS", "RETRYABLE", "PERMANENT", "CONFLICT", "UNKNOWN") or (self.status == "SUCCESS") != (self.value is not None):
            raise ValueError("Only successful operations carry a typed value")

    def __bool__(self):
        raise TypeError("Inspect status explicitly; unknown is not success")

    @property
    def next_action(self):
        return {"SUCCESS": "NONE", "RETRYABLE": "RETRY_LATER", "PERMANENT": "CORRECT_REQUEST", "CONFLICT": "RESOLVE_CONFLICT", "UNKNOWN": "RECONCILE"}[self.status]


@dataclass(frozen=True)
class RequestContext:
    request_id: str
    correlation_ref: str

    def __post_init__(self):
        identity(self.request_id)
        identity(self.correlation_ref)


@dataclass(frozen=True)
class AggregateKey:
    kind: str
    id: str

    def __post_init__(self):
        for value in (self.kind, self.id):
            identity(value)


@dataclass(frozen=True)
class StoredRecord:
    key: AggregateKey
    revision: int
    body_json: str

    def __post_init__(self):
        if not isinstance(self.key, AggregateKey):
            raise ValueError("A typed aggregate key is required")
        revision(self.revision)
        object.__setattr__(self, "body_json", canonical_body(self.body_json))

    @property
    def body(self):
        return json.loads(self.body_json)


@dataclass(frozen=True)
class RecordWrite:
    key: AggregateKey
    expected_revision: int | None
    body_json: str

    def __post_init__(self):
        if not isinstance(self.key, AggregateKey):
            raise ValueError("A typed aggregate key is required")
        if self.expected_revision is not None:
            revision(self.expected_revision)
        object.__setattr__(self, "body_json", canonical_body(self.body_json))


@dataclass(frozen=True)
class CommitRequest:
    context: RequestContext
    principal_id: str
    expected_store_revision: int
    writes: tuple[RecordWrite, ...]
    audit_id: str
    source_ref: str

    def __post_init__(self):
        identity(self.principal_id)
        identity(self.audit_id)
        identity(self.source_ref)
        revision(self.expected_store_revision)
        if not isinstance(self.context, RequestContext) or not isinstance(self.writes, tuple) or not self.writes or not all(isinstance(item, RecordWrite) for item in self.writes) or len({item.key for item in self.writes}) != len(self.writes):
            raise ValueError("A transaction has immutable distinct concrete writes")

    @property
    def fingerprint(self):
        # Correlation/request IDs identify transport attempts, not write meaning.
        writes = sorted((asdict(item) for item in self.writes), key=lambda item: (item["key"]["kind"], item["key"]["id"]))
        return fingerprint({"principal_id": self.principal_id, "expected_store_revision": self.expected_store_revision, "writes": writes, "audit_id": self.audit_id, "source_ref": self.source_ref})


@dataclass(frozen=True)
class TransactionPermit:
    """Independent trusted registry entry, not a serialized authority flag.

    Applications resolve a current domain authorization into this exact write
    fingerprint. Merely having an AuthorizationDecision does not mint a permit.
    """
    permit_ref: str
    principal_id: str
    origin: str
    request_fingerprint: str
    issued_at: datetime
    expires_at: datetime
    active: bool = True

    def __post_init__(self):
        identity(self.permit_ref)
        identity(self.principal_id)
        instant(self.issued_at)
        instant(self.expires_at)
        if self.origin not in ("USER_COMMAND", "RELATIONSHIP_RULE", "EXPIRATION_PROCESS") or not re.fullmatch(r"[a-f0-9]{64}", self.request_fingerprint) or type(self.active) is not bool or self.expires_at <= self.issued_at:
            raise ValueError("A permit binds exact authorized writes and validity")


@dataclass(frozen=True)
class AuditedChange:
    before: StoredRecord | None
    after: StoredRecord


@dataclass(frozen=True)
class AuditEntry:
    audit_id: str
    request_id: str
    request_fingerprint: str
    permit_ref: str
    principal_id: str
    source_ref: str
    committed_at: datetime
    changes: tuple[AuditedChange, ...]


@dataclass(frozen=True)
class CommitReceipt:
    request_id: str
    request_fingerprint: str
    store_revision: int
    audit_id: str
    changed_keys: tuple[AggregateKey, ...]


@dataclass(frozen=True)
class StoreSnapshot:
    store_revision: int
    captured_at: datetime
    records: tuple[StoredRecord, ...]
    audit: tuple[AuditEntry, ...]


@dataclass(frozen=True)
class SourceScope:
    provider: str
    scope_ref: str

    def __post_init__(self):
        identity(self.provider)
        identity(self.scope_ref)


@dataclass(frozen=True)
class SourceReadRequest:
    context: RequestContext
    scope: SourceScope
    window: Interval
    cursor: str | None = None

    def __post_init__(self):
        if not isinstance(self.context, RequestContext) or not isinstance(self.scope, SourceScope) or not isinstance(self.window, Interval):
            raise ValueError("Source reads bind explicit scope and finite window")
        if self.cursor is not None:
            identity(self.cursor)


@dataclass(frozen=True)
class CalendarBatch:
    scope: SourceScope
    window: Interval
    events: tuple[CalendarEvent, ...]
    captured_at: datetime
    quality: str
    complete: bool
    next_cursor: str | None
    gap_refs: tuple[str, ...] = ()

    def __post_init__(self):
        _source_batch(self)
        if not isinstance(self.events, tuple) or not all(isinstance(item, CalendarEvent) and (item.provider, item.scope_ref) == (self.scope.provider, self.scope.scope_ref) and item.interval.start < self.window.end and self.window.start < item.interval.end for item in self.events):
            raise ValueError("Calendar events must bind the queried scope/window")
        if len({item.source_identity for item in self.events}) != len(self.events):
            raise ValueError("Resolve duplicate source revisions before returning a page")


@dataclass(frozen=True)
class EvidenceBatch:
    scope: SourceScope
    window: Interval
    records: tuple[SourceRecord, ...]
    captured_at: datetime
    quality: str
    complete: bool
    next_cursor: str | None
    gap_refs: tuple[str, ...] = ()
    data_role: str = "DATA_NOT_INSTRUCTIONS"

    def __post_init__(self):
        _source_batch(self)
        if self.data_role != "DATA_NOT_INSTRUCTIONS" or not isinstance(self.records, tuple) or not all(isinstance(item, SourceRecord) and (item.provider, item.scope_ref) == (self.scope.provider, self.scope.scope_ref) and item.captured_at <= self.captured_at for item in self.records):
            raise ValueError("Evidence remains scoped data, never Task authority")
        if len({item.record_id for item in self.records}) != len(self.records):
            raise ValueError("Evidence pages must not contain duplicate records")


def _source_batch(batch):
    if not isinstance(batch.scope, SourceScope) or not isinstance(batch.window, Interval):
        raise ValueError("A scoped finite source window is required")
    instant(batch.captured_at)
    if batch.quality not in ("READY", "STALE", "UNRESOLVED") or type(batch.complete) is not bool or not isinstance(batch.gap_refs, tuple):
        raise ValueError("Explicit coverage and source quality are required")
    for gap in batch.gap_refs:
        identity(gap)
    if (batch.quality == "READY") != (not batch.gap_refs) or len(set(batch.gap_refs)) != len(batch.gap_refs):
        raise ValueError("Quality and unique unresolved source gaps must agree")
    if batch.next_cursor is not None:
        identity(batch.next_cursor)
    if batch.complete == (batch.next_cursor is not None):
        raise ValueError("Incomplete pages need a continuation cursor")


@dataclass(frozen=True)
class NotificationRequest:
    context: RequestContext
    notice_id: str
    channel_ref: str
    content_ref: str
    attempt: DispatchAttempt

    def __post_init__(self):
        for value in (self.notice_id, self.channel_ref, self.content_ref):
            identity(value)
        if not isinstance(self.context, RequestContext) or not isinstance(self.attempt, DispatchAttempt) or self.attempt.state != "PENDING":
            raise ValueError("Dispatch requests refer to registered pending attempts")

    @property
    def key(self):
        return self.channel_ref, self.notice_id, self.attempt.attempt_id


@dataclass(frozen=True)
class PredictionRequest:
    context: RequestContext
    job: AIJob

    def __post_init__(self):
        if not isinstance(self.context, RequestContext) or not isinstance(self.job, AIJob) or self.job.expected_kind != "NUMERIC_REMAINING" or self.job.status not in ("EXPORTED", "RUNNING"):
            raise ValueError("Predictors receive eligible numeric jobs, not policy writes")


@dataclass(frozen=True)
class SolverRequest:
    context: RequestContext
    window: ForecastWindow
    snapshot_ref: str
    availability: AvailabilityFrame
    projections: tuple[RequiredProjection, ...]
    hard_constraints_ref: str

    def __post_init__(self):
        if not isinstance(self.context, RequestContext) or not isinstance(self.window, ForecastWindow) or not isinstance(self.availability, AvailabilityFrame) or not isinstance(self.projections, tuple) or not all(isinstance(item, RequiredProjection) for item in self.projections):
            raise ValueError("Solver inputs are immutable domain records")
        if self.snapshot_ref != self.availability.snapshot_ref:
            raise ValueError("Solver context binds one snapshot")
        identity(self.hard_constraints_ref)

    @property
    def fingerprint(self):
        return forecast_fingerprint(self.window, snapshot_ref=self.snapshot_ref, availability=self.availability, projections=self.projections, hard_constraints_ref=self.hard_constraints_ref)


@dataclass(frozen=True)
class RenderRequest:
    context: RequestContext
    plan: PlanSnapshot
    template_ref: str

    def __post_init__(self):
        identity(self.template_ref)
        if not isinstance(self.context, RequestContext) or not isinstance(self.plan, PlanSnapshot):
            raise ValueError("Renderers receive validated Plan snapshots")


@dataclass(frozen=True)
class RenderedDocument:
    plan_id: str
    snapshot_ref: str
    phase: str
    template_ref: str
    media_type: str
    content: str
    rendered_at: datetime

    def __post_init__(self):
        for value in (self.plan_id, self.snapshot_ref, self.template_ref, self.content):
            identity(value)
        instant(self.rendered_at)
        if self.phase not in ("NORMAL", "UNVERIFIED", "PROVISIONAL_EMERGENCY", "FINAL_EMERGENCY") or self.media_type not in ("text/plain", "text/html"):
            raise ValueError("A rendered brief retains Plan phase and media type")


@runtime_checkable
class Clock(Protocol):
    def now(self) -> datetime: ...


@runtime_checkable
class StateStore(Protocol):
    def snapshot(self, context: RequestContext) -> PortResult[StoreSnapshot]: ...
    def commit(self, request: CommitRequest, *, caller: CallerIdentity, permit_ref: str) -> PortResult[CommitReceipt]: ...
    def lookup_commit(self, context: RequestContext, *, caller: CallerIdentity) -> PortResult[CommitReceipt]: ...


@runtime_checkable
class CalendarSource(Protocol):
    def read(self, request: SourceReadRequest) -> PortResult[CalendarBatch]: ...


@runtime_checkable
class EvidenceSource(Protocol):
    def read(self, request: SourceReadRequest) -> PortResult[EvidenceBatch]: ...


@runtime_checkable
class NotificationSink(Protocol):
    def send(self, request: NotificationRequest) -> PortResult[DispatchResult]: ...
    def reconcile(self, request: NotificationRequest) -> PortResult[DispatchResult]: ...


@runtime_checkable
class Predictor(Protocol):
    def predict(self, request: PredictionRequest) -> PortResult[AIResult]: ...


@runtime_checkable
class Solver(Protocol):
    def solve(self, request: SolverRequest) -> PortResult[PlacementEvidence]: ...


@runtime_checkable
class Renderer(Protocol):
    def render(self, request: RenderRequest) -> PortResult[RenderedDocument]: ...
