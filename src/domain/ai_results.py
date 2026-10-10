"""Scoped AI handoff; numeric predictions are derived, policy proposals pending.

No provider SDK, file access, training, authentication or canonical mutation.
The caller supplies independently trusted jobs, registry state and eligibility.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, replace
from datetime import datetime
from decimal import Decimal
from hashlib import sha256
import json
import re
from typing import Mapping

from src.domain.authorization import TaskState
from src.domain.effort import RemainingPrediction


KINDS = frozenset(("NUMERIC_REMAINING", "BEHAVIOR_PROPOSAL"))


def _identity(value):
    if not isinstance(value, str) or not value.strip():
        raise ValueError("A nonblank identity is required")


def _revision(value):
    if type(value) is not int or value < 1:
        raise ValueError("A positive revision is required")


def _instant(value):
    if not isinstance(value, datetime) or value.utcoffset() is None:
        raise ValueError("An explicit timezone is required")


def _hash(value):
    if not isinstance(value, str) or not re.fullmatch(r"[a-f0-9]{64}", value):
        raise ValueError("A SHA256 content hash is required")


def _canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)


def _key(value):
    return sha256(_canonical(value).encode()).hexdigest()


def _strict_pairs(pairs):
    result = {}
    for name, value in pairs:
        if name in result:
            raise ValueError("Duplicate JSON member")
        result[name] = value
    return result


def _nonfinite(_):
    raise ValueError("Non-finite JSON value")


def _json(text):
    return json.loads(text, object_pairs_hook=_strict_pairs, parse_constant=_nonfinite)


def _times(value):
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, dict):
        return {name: _times(item) for name, item in value.items()}
    if isinstance(value, (tuple, list)):
        return [_times(item) for item in value]
    return value


@dataclass(frozen=True)
class TargetBinding:
    kind: str
    id: str
    revision: int

    def __post_init__(self):
        if self.kind not in ("TASK", "TASKTYPE", "PREFERENCE", "RELATIONSHIP_RULE"):
            raise ValueError("Target kind is explicit")
        _identity(self.id)
        _revision(self.revision)


@dataclass(frozen=True)
class AIJob:
    job_id: str
    revision: int
    job_type: str
    executor_class: str
    priority: int
    reason: str
    context_ref: str
    context_hash: str
    snapshot_ref: str
    targets: tuple[TargetBinding, ...]
    output_contract_ref: str
    expected_kind: str
    created_at: datetime
    status: str = "PENDING"
    exported_at: datetime | None = None

    def __post_init__(self):
        for value in (self.job_id, self.job_type, self.reason, self.context_ref, self.snapshot_ref, self.output_contract_ref):
            _identity(value)
        _revision(self.revision)
        _hash(self.context_hash)
        _instant(self.created_at)
        if self.executor_class not in ("DETERMINISTIC", "AUTOMATED", "MANUAL_PREMIUM") or type(self.priority) is not int or not 1 <= self.priority <= 5 or self.expected_kind not in KINDS:
            raise ValueError("Executor/priority/result kind must be explicit")
        if not isinstance(self.targets, tuple) or not self.targets or not all(isinstance(item, TargetBinding) for item in self.targets) or len({(item.kind, item.id) for item in self.targets}) != len(self.targets):
            raise ValueError("Targets must be resolved, immutable and unique")
        if self.status not in ("PENDING", "EXPORTED", "RUNNING", "RESULT_RECEIVED", "VALIDATED", "REJECTED", "CANCELLED"):
            raise ValueError("Unsupported job status")
        if self.exported_at is not None:
            _instant(self.exported_at)
            if self.exported_at < self.created_at:
                raise ValueError("Export cannot precede job creation")
        if self.status == "EXPORTED" and self.exported_at is None or self.status == "PENDING" and self.exported_at is not None:
            raise ValueError("Job status must retain export chronology")

    def as_record(self):
        return {"schema_version": "0.1.0-draft", **_times(asdict(self))}


def export_job(job: AIJob, *, exported_at: datetime):
    """Return reference-only handoff; actual minimized context building is later."""
    _instant(exported_at)
    if job.status == "PENDING":
        job = replace(job, status="EXPORTED", exported_at=exported_at)
    elif job.status != "EXPORTED":
        raise ValueError("Only pending/already exported jobs can be exported")
    elif exported_at < job.exported_at:
        raise ValueError("Replay cannot precede the original export")
    artifact = {"schema_version": "0.1.0-draft", "job_id": job.job_id, "job_revision": job.revision, "context_ref": job.context_ref, "context_hash": job.context_hash, "snapshot_ref": job.snapshot_ref, "targets": [asdict(item) for item in job.targets], "output_contract_ref": job.output_contract_ref, "expected_kind": job.expected_kind, "exported_at": job.exported_at.isoformat(), "external_content_role": "DATA_NOT_INSTRUCTIONS"}
    artifact["export_id"] = "ai-export-" + _key(artifact)
    return job, artifact


@dataclass(frozen=True)
class Usage:
    input_tokens: int | None = None
    output_tokens: int | None = None
    cost_amount: Decimal | None = None
    currency: str | None = None

    def __post_init__(self):
        for value in (self.input_tokens, self.output_tokens):
            if value is not None and (type(value) is not int or value < 0):
                raise ValueError("Unknown token usage is not zero")
        if self.currency is not None:
            _identity(self.currency)
        if self.cost_amount is not None:
            if not isinstance(self.cost_amount, Decimal) or not self.cost_amount.is_finite() or self.cost_amount < 0:
                raise ValueError("Cost is unknown or a finite nonnegative Decimal")
            _identity(self.currency)

    def as_record(self):
        amount = format(self.cost_amount if self.cost_amount else Decimal(0), "f") if self.cost_amount is not None else None
        return {"input_tokens": self.input_tokens, "output_tokens": self.output_tokens, "cost_amount": amount, "currency": self.currency}


@dataclass(frozen=True)
class AIResult:
    result_id: str
    job_id: str
    job_revision: int
    context_hash: str
    snapshot_ref: str
    output_contract_ref: str
    kind: str
    executor_ref: str
    finished_at: datetime
    payload_json: str
    usage: Usage

    def __post_init__(self):
        for value in (self.result_id, self.job_id, self.snapshot_ref, self.output_contract_ref, self.executor_ref):
            _identity(value)
        _revision(self.job_revision)
        _hash(self.context_hash)
        _instant(self.finished_at)
        if self.kind not in KINDS or not isinstance(self.usage, Usage) or not isinstance(_json(self.payload_json), dict):
            raise ValueError("Result structure and usage meaning must be explicit")
        object.__setattr__(self, "payload_json", _canonical(_json(self.payload_json)))

    @property
    def payload(self):
        return _json(self.payload_json)

    def as_record(self):
        return {"schema_version": "0.1.0-draft", "result_id": self.result_id, "job_id": self.job_id, "job_revision": self.job_revision, "context_hash": self.context_hash, "snapshot_ref": self.snapshot_ref, "output_contract_ref": self.output_contract_ref, "kind": self.kind, "executor_ref": self.executor_ref, "finished_at": self.finished_at.isoformat(), "payload": self.payload, "usage": self.usage.as_record()}

    @property
    def content_hash(self):
        # Canonical semantic body fingerprint; raw-byte source hash is separate.
        return _key(self.as_record())


@dataclass(frozen=True)
class NumericEligibility:
    eligibility_ref: str
    task_id: str
    task_revision: int
    model_id: str
    model_version: str
    context_hash: str
    snapshot_ref: str
    evaluated_at: datetime
    valid_until: datetime

    def __post_init__(self):
        for value in (self.eligibility_ref, self.task_id, self.model_id, self.model_version, self.snapshot_ref):
            _identity(value)
        _revision(self.task_revision)
        _hash(self.context_hash)
        _instant(self.evaluated_at)
        _instant(self.valid_until)
        if self.valid_until <= self.evaluated_at:
            raise ValueError("Trusted eligibility needs a finite validity interval")


@dataclass(frozen=True)
class DerivedPrediction:
    job_id: str
    result_id: str
    result_hash: str
    task_id: str
    eligibility_ref: str
    external_prediction_id: str
    uncertainty_ref: str | None
    prediction: RemainingPrediction

    def __post_init__(self):
        for value in (self.job_id, self.result_id, self.task_id, self.eligibility_ref, self.external_prediction_id):
            _identity(value)
        _hash(self.result_hash)
        if self.uncertainty_ref is not None:
            _identity(self.uncertainty_ref)
        if not isinstance(self.prediction, RemainingPrediction) or not self.prediction.valid or not self.prediction.applicable:
            raise ValueError("Derived predictions require independently validated eligibility")

    def as_record(self):
        return {"schema_version": "0.1.0-draft", **_times(asdict(self))}


@dataclass(frozen=True)
class BehaviorCandidate:
    candidate_id: str
    job_id: str
    result_id: str
    result_hash: str
    target: TargetBinding
    policy_kind: str
    description: str
    proposed_value_json: str
    confidence: Decimal
    created_at: datetime
    review_state: str = "PENDING"

    def __post_init__(self):
        for value in (self.candidate_id, self.job_id, self.result_id, self.description):
            _identity(value)
        _hash(self.result_hash)
        _instant(self.created_at)
        if not isinstance(self.target, TargetBinding) or self.policy_kind not in ("PREFERENCE", "TASKTYPE_DEFAULT", "RELATIONSHIP_RULE", "DECOMPOSITION") or self.review_state != "PENDING":
            raise ValueError("Imported behavioral proposals are pending, never accepted policy")
        if not isinstance(self.confidence, Decimal) or not self.confidence.is_finite() or not 0 <= self.confidence <= 1 or not isinstance(_json(self.proposed_value_json), dict):
            raise ValueError("Policy values remain data; confidence is bounded evidence")
        object.__setattr__(self, "proposed_value_json", _canonical(_json(self.proposed_value_json)))

    @property
    def proposed_value(self):
        return _json(self.proposed_value_json)

    def as_record(self):
        return {"schema_version": "0.1.0-draft", "candidate_id": self.candidate_id, "job_id": self.job_id, "result_id": self.result_id, "result_hash": self.result_hash, "target": asdict(self.target), "policy_kind": self.policy_kind, "description": self.description, "proposed_value": self.proposed_value, "confidence": format(self.confidence if self.confidence else Decimal(0), "f"), "created_at": self.created_at.isoformat(), "review_state": self.review_state}


@dataclass(frozen=True)
class ImportRecord:
    result_id: str
    job_id: str
    job_revision: int
    result_hash: str
    validation_state: str
    reason: str
    validated_at: datetime

    def __post_init__(self):
        for value in (self.result_id, self.job_id, self.reason):
            _identity(value)
        _revision(self.job_revision)
        _hash(self.result_hash)
        _instant(self.validated_at)
        if self.validation_state not in ("VALIDATED_NUMERIC", "PENDING_REVIEW", "REJECTED"):
            raise ValueError("Import history records a terminal validation outcome")

    def as_record(self):
        return {"schema_version": "0.1.0-draft", **_times(asdict(self))}


@dataclass(frozen=True)
class ImportOutcome:
    state: str
    reason: str
    record: ImportRecord | None
    history: tuple[ImportRecord, ...]
    prediction: DerivedPrediction | None = None
    behavior: BehaviorCandidate | None = None


def validate_import(job: AIJob, result: AIResult, *, current_snapshot_ref: str, current_context_hash: str, target_revisions: Mapping[tuple[str, str], int], tasks: Mapping[str, TaskState], eligibility: NumericEligibility | None, now: datetime, history: tuple[ImportRecord, ...] = ()):
    """Validate a new result or return no-effect replay; never apply a mutation."""
    _instant(now)
    _identity(current_snapshot_ref)
    _hash(current_context_hash)
    if not isinstance(history, tuple) or not all(isinstance(item, ImportRecord) for item in history):
        raise ValueError("Immutable import history is required")
    if len({(item.job_id, item.result_id) for item in history}) != len(history):
        raise ValueError("Ambiguous import history must be reconciled")
    prior = next((item for item in history if (item.job_id, item.result_id) == (result.job_id, result.result_id)), None)
    if prior is not None:
        if prior.result_hash != result.content_hash:
            return ImportOutcome("CONFLICT", "RESULT_ID_CONTENT_CONFLICT", prior, history)
        return ImportOutcome("REPLAY", "ALREADY_RECORDED_NO_EFFECT", prior, history)

    def outcome(state, reason, prediction=None, behavior=None):
        record = ImportRecord(result.result_id, result.job_id, result.job_revision, result.content_hash, state, reason, now)
        return ImportOutcome(state, reason, record, history + (record,), prediction, behavior)

    if job.status in ("CANCELLED", "REJECTED", "PENDING"):
        return outcome("REJECTED", "JOB_NOT_ELIGIBLE")
    if (result.job_id, result.job_revision, result.context_hash, result.snapshot_ref, result.output_contract_ref, result.kind) != (job.job_id, job.revision, job.context_hash, job.snapshot_ref, job.output_contract_ref, job.expected_kind):
        return outcome("REJECTED", "JOB_SCOPE_MISMATCH")
    dispatched_at = job.exported_at or job.created_at
    if current_snapshot_ref != job.snapshot_ref or current_context_hash != job.context_hash or not dispatched_at <= result.finished_at <= now:
        return outcome("REJECTED", "STALE_CONTEXT_OR_RESULT_TIME")
    if any(target_revisions.get((item.kind, item.id)) != item.revision for item in job.targets):
        return outcome("REJECTED", "TARGET_REVISION_UNRESOLVED")
    fields = result.payload
    try:
        if result.kind == "NUMERIC_REMAINING":
            expected = {"quantity_kind", "task_id", "task_revision", "prediction_id", "model_id", "model_version", "remaining_seconds", "computed_at", "valid_until", "uncertainty_ref"}
            if set(fields) != expected or fields["quantity_kind"] != "REMAINING":
                return outcome("REJECTED", "UNSUPPORTED_NUMERIC_PAYLOAD")
            target = TargetBinding("TASK", fields["task_id"], fields["task_revision"])
            task = tasks.get(target.id)
            if target not in job.targets or task is None or task.revision != target.revision or task.completion != "INCOMPLETE" or task.disposition != "ACTIVE":
                return outcome("REJECTED", "NUMERIC_TARGET_NOT_ACTIVE")
            if eligibility is None or not isinstance(eligibility, NumericEligibility) or (eligibility.task_id, eligibility.task_revision, eligibility.model_id, eligibility.model_version, eligibility.context_hash, eligibility.snapshot_ref) != (target.id, target.revision, fields["model_id"], fields["model_version"], job.context_hash, job.snapshot_ref) or not job.created_at <= eligibility.evaluated_at <= now < eligibility.valid_until:
                return outcome("REJECTED", "NUMERIC_ELIGIBILITY_UNRESOLVED")
            _identity(fields["prediction_id"])
            if fields["uncertainty_ref"] is not None:
                _identity(fields["uncertainty_ref"])
            prediction = RemainingPrediction(fields["remaining_seconds"], "prediction-" + _key([job.job_id, job.revision, result.content_hash, target.id]), fields["model_id"], fields["model_version"], target.revision, datetime.fromisoformat(fields["computed_at"]), datetime.fromisoformat(fields["valid_until"]), True, True)
            if not dispatched_at <= prediction.computed_at <= result.finished_at or prediction.valid_until <= now or prediction.valid_until > eligibility.valid_until:
                return outcome("REJECTED", "NUMERIC_TIME_OR_VALIDITY_UNRESOLVED")
            derived = DerivedPrediction(job.job_id, result.result_id, result.content_hash, target.id, eligibility.eligibility_ref, fields["prediction_id"], fields["uncertainty_ref"], prediction)
            return outcome("VALIDATED_NUMERIC", "DERIVED_REMAINING_ONLY", prediction=derived)

        expected = {"proposal_id", "target", "policy_kind", "description", "proposed_value", "confidence"}
        if set(fields) != expected or not isinstance(fields["target"], dict) or set(fields["target"]) != {"kind", "id", "revision"} or not isinstance(fields["proposed_value"], dict) or type(fields["confidence"]) is not str:
            return outcome("REJECTED", "UNSUPPORTED_BEHAVIOR_PAYLOAD")
        _identity(fields["proposal_id"])
        target = TargetBinding(**fields["target"])
        if target not in job.targets:
            return outcome("REJECTED", "BEHAVIOR_TARGET_SCOPE_MISMATCH")
        candidate = BehaviorCandidate("behavior-" + _key([job.job_id, job.revision, result.content_hash, fields["proposal_id"]]), job.job_id, result.result_id, result.content_hash, target, fields["policy_kind"], fields["description"], _canonical(fields["proposed_value"]), Decimal(fields["confidence"]), now)
        return outcome("PENDING_REVIEW", "POLICY_REQUIRES_SCOPED_USER_AUTHORITY", behavior=candidate)
    except (ValueError, TypeError, KeyError, ArithmeticError):
        return outcome("REJECTED", "INVALID_RESULT_PAYLOAD")
