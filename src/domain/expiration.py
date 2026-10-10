"""Provider-independent expiration notices; pure state and readiness checks.

Detection and queued attempts never expire a Task. Trusted adapters must supply
condition/delivery evidence, and persistence must revalidate before committing.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, replace
from datetime import datetime
from hashlib import sha256
import json

from src.domain.authorization import NoticeEvidence, TaskState


def _identity(value):
    if not isinstance(value, str) or not value.strip():
        raise ValueError("A nonblank identity is required")


def _instant(value):
    if not isinstance(value, datetime) or value.utcoffset() is None:
        raise ValueError("An explicit timezone is required")


def _json_value(value):
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, dict):
        return {key: _json_value(item) for key, item in value.items()}
    if isinstance(value, (tuple, list)):
        return [_json_value(item) for item in value]
    return value


@dataclass(frozen=True)
class ConditionEvidence:
    evidence_id: str
    condition_ref: str
    confirmed: bool | None
    observed_at: datetime

    def __post_init__(self):
        _identity(self.evidence_id)
        _identity(self.condition_ref)
        _instant(self.observed_at)
        if self.confirmed is not None and type(self.confirmed) is not bool:
            raise ValueError("An uncertain condition is distinct from confirmed true")


@dataclass(frozen=True)
class DispatchAttempt:
    attempt_id: str
    started_at: datetime
    state: str
    finished_at: datetime | None = None
    delivered_at: datetime | None = None
    evidence_ref: str | None = None
    correlation_ref: str | None = None

    def __post_init__(self):
        _identity(self.attempt_id)
        _instant(self.started_at)
        if self.correlation_ref is not None:
            _identity(self.correlation_ref)
        if self.state == "PENDING":
            if any(value is not None for value in (self.finished_at, self.delivered_at, self.evidence_ref)):
                raise ValueError("An unsent or pending request is not a dispatch result")
        elif self.state in ("DELIVERED", "FAILED", "UNKNOWN"):
            _instant(self.finished_at)
            _identity(self.evidence_ref)
            if self.finished_at < self.started_at:
                raise ValueError("Dispatch result cannot precede its request")
            if self.state == "DELIVERED":
                _instant(self.delivered_at)
                if not self.started_at <= self.delivered_at <= self.finished_at:
                    raise ValueError("Confirmed delivery must fall within the attempt")
            elif self.delivered_at is not None:
                raise ValueError("Unknown or failed delivery has no confirmed delivery time")
        else:
            raise ValueError("Unsupported dispatch state")


@dataclass(frozen=True)
class DispatchResult:
    notice_id: str
    attempt: DispatchAttempt

    def __post_init__(self):
        _identity(self.notice_id)
        if not isinstance(self.attempt, DispatchAttempt) or self.attempt.state == "PENDING":
            raise ValueError("A terminal or ambiguous dispatch result is required")

    def as_record(self):
        return {"schema_version": "0.1.0-draft", **_json_value(asdict(self))}


@dataclass(frozen=True)
class ExpirationNotice:
    notice_id: str
    task_id: str
    task_revision: int
    condition_ref: str
    condition_evidence_ref: str
    detected_at: datetime
    attempts: tuple[DispatchAttempt, ...] = ()
    dispatch_history: tuple[DispatchResult, ...] = ()

    def __post_init__(self):
        for value in (self.notice_id, self.task_id, self.condition_ref, self.condition_evidence_ref):
            _identity(value)
        _instant(self.detected_at)
        if type(self.task_revision) is not int or self.task_revision < 1 or not isinstance(self.attempts, tuple) or not isinstance(self.dispatch_history, tuple):
            raise ValueError("Notice binds one task revision and immutable attempts")
        if len({attempt.attempt_id for attempt in self.attempts}) != len(self.attempts):
            raise ValueError("Duplicate dispatch attempt")
        if any(attempt.started_at < self.detected_at for attempt in self.attempts):
            raise ValueError("An attempt cannot precede detection")
        if any(result.notice_id != self.notice_id or not any(attempt.attempt_id == result.attempt.attempt_id and attempt.started_at == result.attempt.started_at for attempt in self.attempts) for result in self.dispatch_history):
            raise ValueError("Dispatch history must bind registered notice attempts")

    @property
    def delivery_state(self):
        if any(attempt.state == "DELIVERED" for attempt in self.attempts):
            return "DELIVERED"
        return self.attempts[-1].state if self.attempts else "PENDING"

    def as_record(self):
        return {"schema_version": "0.1.0-draft", **_json_value(asdict(self)), "delivery_state": self.delivery_state}


@dataclass(frozen=True)
class DetectionResult:
    state: str
    reason: str
    notice: ExpirationNotice | None = None


def detect_expiration(task: TaskState, condition: ConditionEvidence, *, now: datetime):
    _instant(now)
    if task.requiredness != "EXPIRING" or task.completion != "INCOMPLETE" or task.disposition != "ACTIVE":
        return DetectionResult("NOT_APPLICABLE", "TASK_NOT_EXPIRABLE")
    if task.expiration_condition_ref != condition.condition_ref or condition.observed_at > now:
        return DetectionResult("UNCERTAIN", "CONDITION_SCOPE_OR_TIME_UNRESOLVED")
    if condition.confirmed is None:
        return DetectionResult("UNCERTAIN", "CONDITION_UNCONFIRMED")
    if not condition.confirmed:
        return DetectionResult("NOT_APPLICABLE", "CONDITION_NOT_REACHED")
    parts = (task.task_id, task.revision, condition.condition_ref)
    identity = "expiry-notice-" + sha256(json.dumps(parts, separators=(",", ":")).encode()).hexdigest()
    notice = ExpirationNotice(identity, task.task_id, task.revision, condition.condition_ref, condition.evidence_id, now)
    return DetectionResult("NOTICE_REQUIRED", "CONFIRMED_CONDITION", notice)


def begin_dispatch(notice: ExpirationNotice, *, attempt_id: str, started_at: datetime, correlation_ref: str | None = None):
    """Register a request only; transport may still fail or never send it."""
    attempt = DispatchAttempt(attempt_id, started_at, "PENDING", correlation_ref=correlation_ref)
    previous = next((item for item in notice.attempts if item.attempt_id == attempt_id), None)
    if previous is not None:
        if previous.started_at != started_at or previous.correlation_ref != correlation_ref:
            raise ValueError("Conflicting dispatch request replay")
        return notice
    if notice.delivery_state == "DELIVERED":
        raise ValueError("Already delivered; a second notice is not required")
    if notice.attempts and notice.delivery_state in ("PENDING", "UNKNOWN"):
        raise ValueError("Reconcile in-flight or ambiguous delivery before resending")
    if notice.attempts and started_at < notice.attempts[-1].finished_at:
        raise ValueError("A retry cannot precede the previous failure")
    return replace(notice, attempts=notice.attempts + (attempt,))


def _record_result(notice, result, *, reconciliation):
    if result.notice_id != notice.notice_id:
        raise ValueError("Dispatch result belongs to another notice")
    previous = next((item for item in notice.attempts if item.attempt_id == result.attempt.attempt_id), None)
    if previous is None or previous.started_at != result.attempt.started_at:
        raise ValueError("An independently registered attempt is required")
    if previous == result.attempt:
        return notice
    if previous.state == "UNKNOWN" and reconciliation:
        if result.attempt.state not in ("DELIVERED", "FAILED") or result.attempt.finished_at < previous.finished_at:
            raise ValueError("Reconciliation needs later confirmed evidence")
    elif previous.state != "PENDING" or reconciliation:
        raise ValueError("Conflicting final result or unresolved ambiguity")
    if previous.correlation_ref is not None and result.attempt.correlation_ref != previous.correlation_ref:
        raise ValueError("Dispatch correlation changed")
    return replace(notice, attempts=tuple(result.attempt if item.attempt_id == previous.attempt_id else item for item in notice.attempts), dispatch_history=notice.dispatch_history + (result,))


def record_dispatch(notice: ExpirationNotice, result: DispatchResult):
    return _record_result(notice, result, reconciliation=False)


def reconcile_dispatch(notice: ExpirationNotice, result: DispatchResult):
    """Trusted receipt/query resolves the original UNKNOWN attempt, not a retry."""
    return _record_result(notice, result, reconciliation=True)


@dataclass(frozen=True)
class ExpirationReadiness:
    ready: bool
    reason: str
    notice_evidence: NoticeEvidence | None = None


def revalidate_expiration(notice: ExpirationNotice, task: TaskState, condition: ConditionEvidence, *, checked_at: datetime):
    _instant(checked_at)
    delivered = next((item for item in notice.attempts if item.state == "DELIVERED"), None)
    if delivered is None:
        return ExpirationReadiness(False, "NOTICE_NOT_DELIVERED")
    if delivered.finished_at > checked_at or condition.observed_at > checked_at:
        return ExpirationReadiness(False, "FUTURE_EVIDENCE")
    if (task.task_id, task.revision, task.expiration_condition_ref) != (notice.task_id, notice.task_revision, notice.condition_ref):
        return ExpirationReadiness(False, "STALE_NOTICE_SCOPE")
    if task.requiredness != "EXPIRING" or task.completion != "INCOMPLETE" or task.disposition != "ACTIVE":
        return ExpirationReadiness(False, "TASK_NOT_EXPIRABLE")
    if condition.condition_ref != notice.condition_ref or condition.confirmed is not True or condition.observed_at < delivered.delivered_at:
        return ExpirationReadiness(False, "CURRENT_CONDITION_UNCONFIRMED")
    evidence = NoticeEvidence(notice.notice_id, notice.task_id, notice.task_revision, notice.condition_ref, True, notice.detected_at, "DELIVERED", delivered.delivered_at)
    return ExpirationReadiness(True, "READY_FOR_AUTHORIZED_TRANSACTION", evidence)
