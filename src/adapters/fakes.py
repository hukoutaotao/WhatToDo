"""No-I/O test adapters. Canned responses are fixtures, not live evidence.

The fake store models linearizable publication in one process, not durability.
Independent permits are seeded by trusted test/application setup, never input.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import timedelta
from threading import RLock
from types import MappingProxyType

from src.application.ports import (
    AggregateKey, AuditEntry, AuditedChange, CalendarBatch, Clock, CommitReceipt,
    CommitRequest, EvidenceBatch, NotificationRequest, PortResult, PredictionRequest,
    RenderedDocument, RenderRequest, RequestContext, SolverRequest, SourceReadRequest,
    StoredRecord, StoreSnapshot, TransactionPermit, instant,
)
from src.domain.ai_results import AIResult
from src.domain.authorization import CallerIdentity
from src.domain.expiration import DispatchResult
from src.domain.forecast import PlacementEvidence


class FakeClock:
    def __init__(self, now):
        instant(now)
        self._now = now

    def now(self):
        return self._now

    def advance(self, duration: timedelta):
        if not isinstance(duration, timedelta) or duration < timedelta():
            raise ValueError("Fake clock advances monotonically")
        self._now += duration


@dataclass(frozen=True)
class _StoreState:
    revision: int
    records: tuple[StoredRecord, ...]
    audit: tuple[AuditEntry, ...]
    receipts: tuple[tuple[CommitReceipt, str], ...]  # Original authenticated origin.


class FakeStateStore:
    def __init__(self, *, clock: Clock, records=(), permits=(), fault=None):
        if not isinstance(clock, Clock) or not isinstance(records, tuple) or not all(isinstance(item, StoredRecord) for item in records) or len({item.key for item in records}) != len(records):
            raise ValueError("Trusted clock and unique immutable seed records required")
        if not isinstance(permits, tuple) or not all(isinstance(item, TransactionPermit) for item in permits) or len({item.permit_ref for item in permits}) != len(permits):
            raise ValueError("Independent trusted permit registry required")
        if fault not in (None, "BEFORE_COMMIT_RETRYABLE", "AUDIT_FAILURE", "AFTER_COMMIT_UNKNOWN"):
            raise ValueError("Unsupported one-shot fake fault")
        self._clock = clock
        self._permits = MappingProxyType({item.permit_ref: item for item in permits})
        self._fault = fault
        self._state = _StoreState(1, records, (), ())
        self._lock = RLock()

    def snapshot(self, context):
        if not isinstance(context, RequestContext):
            raise ValueError("Typed request context required")
        with self._lock:
            state = self._state
            snapshot = StoreSnapshot(state.revision, self._clock.now(), state.records, state.audit)
            return PortResult("SUCCESS", "SNAPSHOT", context.correlation_ref, snapshot)

    def _prior(self, request_id):
        return next((item for item in self._state.receipts if item[0].request_id == request_id), None)

    def _owns(self, prior, caller):
        receipt, origin = prior
        entry = next(item for item in self._state.audit if item.audit_id == receipt.audit_id)
        return isinstance(caller, CallerIdentity) and caller.authenticated and caller.origin != "EXTERNAL" and caller.principal_id == entry.principal_id and caller.origin == origin

    def lookup_commit(self, context, *, caller):
        if not isinstance(context, RequestContext):
            raise ValueError("Typed request context required")
        with self._lock:
            if not isinstance(caller, CallerIdentity) or not caller.authenticated or caller.origin == "EXTERNAL":
                return PortResult("PERMANENT", "UNTRUSTED_CALLER", context.correlation_ref)
            prior = self._prior(context.request_id)
            if prior is None:
                return PortResult("UNKNOWN", "COMMIT_NOT_OBSERVED", context.correlation_ref)
            if not self._owns(prior, caller):
                return PortResult("PERMANENT", "CALLER_SCOPE_MISMATCH", context.correlation_ref)
            return PortResult("SUCCESS", "COMMIT_FOUND", context.correlation_ref, prior[0])

    def commit(self, request, *, caller, permit_ref):
        if not isinstance(request, CommitRequest):
            raise ValueError("Typed transaction required")
        correlation = request.context.correlation_ref
        with self._lock:
            if not isinstance(caller, CallerIdentity) or not caller.authenticated or caller.origin == "EXTERNAL" or caller.principal_id != request.principal_id:
                return PortResult("PERMANENT", "UNTRUSTED_CALLER", correlation)
            prior = self._prior(request.context.request_id)
            if prior is not None:
                if not self._owns(prior, caller):
                    return PortResult("PERMANENT", "CALLER_SCOPE_MISMATCH", correlation)
                if prior[0].request_fingerprint != request.fingerprint:
                    return PortResult("CONFLICT", "REQUEST_ID_CONTENT_CONFLICT", correlation)
                return PortResult("SUCCESS", "REPLAY", correlation, prior[0])
            permit = self._permits.get(permit_ref)
            now = self._clock.now()
            if permit is None or not permit.active or not permit.issued_at <= now < permit.expires_at or (permit.principal_id, permit.origin, permit.request_fingerprint) != (caller.principal_id, caller.origin, request.fingerprint):
                return PortResult("PERMANENT", "EXACT_ACTIVE_PERMIT_REQUIRED", correlation)
            state = self._state
            if state.revision != request.expected_store_revision:
                return PortResult("CONFLICT", "STALE_STORE_REVISION", correlation)
            records = {item.key: item for item in state.records}
            if any((records[item.key].revision if item.key in records else None) != item.expected_revision for item in request.writes):
                return PortResult("CONFLICT", "STALE_AGGREGATE_REVISION", correlation)
            if any(item.audit_id == request.audit_id for item in state.audit):
                return PortResult("CONFLICT", "AUDIT_ID_ALREADY_USED", correlation)
            changes = []
            for write in request.writes:
                before = records.get(write.key)
                after = StoredRecord(write.key, before.revision + 1 if before else 1, write.body_json)
                records[write.key] = after
                changes.append(AuditedChange(before, after))
            entry = AuditEntry(request.audit_id, request.context.request_id, request.fingerprint, permit_ref, caller.principal_id, request.source_ref, now, tuple(changes))
            receipt = CommitReceipt(request.context.request_id, request.fingerprint, state.revision + 1, request.audit_id, tuple(write.key for write in request.writes))
            fault, self._fault = self._fault, None
            if fault in ("BEFORE_COMMIT_RETRYABLE", "AUDIT_FAILURE"):
                return PortResult("RETRYABLE", "AUDIT_WRITE_FAILED" if fault == "AUDIT_FAILURE" else "TRANSACTION_NOT_COMMITTED", correlation)
            # One publication includes records, full before/after audit and receipt.
            self._state = _StoreState(state.revision + 1, tuple(records.values()), state.audit + (entry,), state.receipts + ((receipt, caller.origin),))
            if fault == "AFTER_COMMIT_UNKNOWN":
                return PortResult("UNKNOWN", "COMMIT_ACKNOWLEDGEMENT_LOST", correlation)
            return PortResult("SUCCESS", "COMMITTED", correlation, receipt)


class _ReplyBook:
    """Exact fixture requests; changing input cannot reuse unrelated output."""
    def __init__(self, replies=()):
        self._replies = tuple(replies)
        self.calls = ()
        ids = [request.context.request_id for request, reply in self._replies]
        if len(ids) != len(set(ids)) or not all(isinstance(reply, PortResult) for _, reply in self._replies):
            raise ValueError("One explicit fake response per request identity")

    def call(self, request):
        self.calls += (request,)
        configured = next((item for item in self._replies if item[0].context.request_id == request.context.request_id), None)
        if configured is None:
            return PortResult("UNKNOWN", "FAKE_RESPONSE_NOT_CONFIGURED", request.context.correlation_ref)
        expected, reply = configured
        if replace(expected, context=request.context) != request:
            return PortResult("CONFLICT", "FAKE_REQUEST_SCOPE_MISMATCH", request.context.correlation_ref)
        return replace(reply, correlation_ref=request.context.correlation_ref)


class FakeCalendarSource:
    def __init__(self, replies=()):
        self._book = _ReplyBook(replies)

    def read(self, request):
        if not isinstance(request, SourceReadRequest):
            raise ValueError("Typed source request required")
        result = self._book.call(request)
        if result.status == "SUCCESS" and (not isinstance(result.value, CalendarBatch) or (result.value.scope, result.value.window) != (request.scope, request.window)):
            return PortResult("PERMANENT", "CALENDAR_RESPONSE_SCOPE_MISMATCH", request.context.correlation_ref)
        return result


class FakeEvidenceSource:
    def __init__(self, replies=()):
        self._book = _ReplyBook(replies)

    def read(self, request):
        if not isinstance(request, SourceReadRequest):
            raise ValueError("Typed source request required")
        result = self._book.call(request)
        if result.status == "SUCCESS" and (not isinstance(result.value, EvidenceBatch) or (result.value.scope, result.value.window) != (request.scope, request.window)):
            return PortResult("PERMANENT", "EVIDENCE_RESPONSE_SCOPE_MISMATCH", request.context.correlation_ref)
        return result


class FakeNotificationSink:
    def __init__(self, *, send_replies=(), reconcile_replies=()):
        self._send = _ReplyBook(send_replies)
        self._reconcile = _ReplyBook(reconcile_replies)
        self._attempts = {}
        self._lock = RLock()

    @property
    def send_count(self):
        return len(self._send.calls)

    def _bound_result(self, request, result):
        if result.status == "SUCCESS":
            value = result.value
            if not isinstance(value, DispatchResult) or value.notice_id != request.notice_id or (value.attempt.attempt_id, value.attempt.started_at, value.attempt.correlation_ref) != (request.attempt.attempt_id, request.attempt.started_at, request.attempt.correlation_ref):
                # After invoking a send, a bad receipt cannot prove no delivery.
                return PortResult("UNKNOWN", "DISPATCH_RECEIPT_UNRESOLVED", request.context.correlation_ref)
        return result

    @staticmethod
    def _same_attempt(left, right):
        return replace(left, context=right.context) == right

    def send(self, request):
        if not isinstance(request, NotificationRequest):
            raise ValueError("Typed pending notification required")
        with self._lock:
            prior = self._attempts.get(request.key)
            if prior is not None:
                original, reply = prior
                if not self._same_attempt(original, request):
                    return PortResult("CONFLICT", "DISPATCH_ID_CONTENT_CONFLICT", request.context.correlation_ref)
                return replace(reply, correlation_ref=request.context.correlation_ref)
            result = self._bound_result(request, self._send.call(request))
            self._attempts[request.key] = (request, result)
            return result

    def reconcile(self, request):
        if not isinstance(request, NotificationRequest):
            raise ValueError("Typed pending notification required")
        with self._lock:
            prior = self._attempts.get(request.key)
            if prior is None:
                return PortResult("UNKNOWN", "DISPATCH_NOT_OBSERVED", request.context.correlation_ref)
            if not self._same_attempt(prior[0], request):
                return PortResult("CONFLICT", "DISPATCH_ID_CONTENT_CONFLICT", request.context.correlation_ref)
            old = prior[1]
            if old.status == "SUCCESS" and old.value.attempt.state in ("DELIVERED", "FAILED"):
                return replace(old, correlation_ref=request.context.correlation_ref)
            result = self._bound_result(request, self._reconcile.call(request))
            if result.status == "SUCCESS":
                self._attempts[request.key] = (prior[0], result)
            return result


class FakePredictor:
    def __init__(self, replies=()):
        self._book = _ReplyBook(replies)

    def predict(self, request):
        if not isinstance(request, PredictionRequest):
            raise ValueError("Typed numeric prediction request required")
        result = self._book.call(request)
        if result.status == "SUCCESS":
            value, job = result.value, request.job
            if not isinstance(value, AIResult) or (value.job_id, value.job_revision, value.context_hash, value.snapshot_ref, value.output_contract_ref, value.kind) != (job.job_id, job.revision, job.context_hash, job.snapshot_ref, job.output_contract_ref, job.expected_kind):
                return PortResult("PERMANENT", "PREDICTOR_RESPONSE_SCOPE_MISMATCH", request.context.correlation_ref)
        return result  # Still untrusted: validate_import requires separate eligibility.


class FakeSolver:
    def __init__(self, replies=()):
        self._book = _ReplyBook(replies)

    def solve(self, request):
        if not isinstance(request, SolverRequest):
            raise ValueError("Typed solver request required")
        result = self._book.call(request)
        if result.status == "SUCCESS" and (not isinstance(result.value, PlacementEvidence) or result.value.input_fingerprint != request.fingerprint):
            return PortResult("PERMANENT", "SOLVER_RESPONSE_SCOPE_MISMATCH", request.context.correlation_ref)
        return result  # TIMEOUT/UNKNOWN evidence is never proof of feasibility.


class FakeRenderer:
    def __init__(self, replies=()):
        self._book = _ReplyBook(replies)

    def render(self, request):
        if not isinstance(request, RenderRequest):
            raise ValueError("Typed render request required")
        result = self._book.call(request)
        if result.status == "SUCCESS":
            value, plan = result.value, request.plan
            if not isinstance(value, RenderedDocument) or (value.plan_id, value.snapshot_ref, value.phase, value.template_ref) != (plan.plan_id, plan.snapshot_ref, plan.phase, request.template_ref) or value.rendered_at < plan.generated_at:
                return PortResult("PERMANENT", "RENDER_RESPONSE_SCOPE_MISMATCH", request.context.correlation_ref)
        return result  # Does not publish a message or Calendar event.
