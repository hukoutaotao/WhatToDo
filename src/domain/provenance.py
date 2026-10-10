"""Immutable source evidence and pending proposals; no canonical Task writes."""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import datetime
from decimal import Decimal
from hashlib import sha256
import json
import re
from typing import Any


def _identity(value):
    if not isinstance(value, str) or not value.strip():
        raise ValueError("A nonblank identity is required")


def _instant(value):
    if not isinstance(value, datetime) or value.utcoffset() is None:
        raise ValueError("An explicit timezone is required")


def _hash(value):
    if not isinstance(value, str) or re.fullmatch(r"[a-f0-9]{64}", value) is None:
        raise ValueError("A SHA-256 content hash is required")


def _key(parts):
    return sha256(json.dumps(parts, ensure_ascii=True, separators=(",", ":"), allow_nan=False).encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class SourceRecord:
    record_id: str
    source_id: str
    source_type: str
    provider: str
    scope_ref: str
    external_id: str
    external_revision: str | None
    content_hash: str
    source_timestamp: datetime | None
    captured_at: datetime
    state: str = "PRESENT"
    deleted_at: datetime | None = None

    def as_record(self):
        return {
            "schema_version": "0.1.0-draft", "record_id": self.record_id,
            "source_id": self.source_id, "source_type": self.source_type,
            "provider": self.provider, "scope_ref": self.scope_ref,
            "external_id": self.external_id, "external_revision": self.external_revision,
            "content_hash": self.content_hash,
            "source_timestamp": self.source_timestamp.isoformat() if self.source_timestamp else None,
            "captured_at": self.captured_at.isoformat(), "state": self.state,
            "deleted_at": self.deleted_at.isoformat() if self.deleted_at else None,
        }

    def __post_init__(self):
        for identity in (self.record_id, self.source_id, self.provider, self.scope_ref, self.external_id):
            _identity(identity)
        if self.external_revision is not None:
            _identity(self.external_revision)
        if self.source_type not in ("USER", "CALENDAR", "EMAIL", "LEARNING_PLATFORM", "OTHER"):
            raise ValueError("Unsupported source type")
        _hash(self.content_hash)
        _instant(self.captured_at)
        if self.source_timestamp is not None:
            _instant(self.source_timestamp)
        if self.state == "DELETED":
            _instant(self.deleted_at)
            if self.deleted_at < self.captured_at:
                raise ValueError("Deletion cannot precede the captured record")
        elif self.state != "PRESENT" or self.deleted_at is not None:
            raise ValueError("Source state/deletion metadata disagree")


def capture_source(
    *, provider: str, scope_ref: str, external_id: str, raw_bytes: bytes,
    captured_at: datetime, source_type: str = "OTHER",
    external_revision: str | None = None, source_timestamp: datetime | None = None,
) -> SourceRecord:
    """Hash exact bytes; scope separates identical external IDs across accounts."""
    if not isinstance(raw_bytes, bytes):
        raise ValueError("Source content must be exact bytes")
    source_id = "source-" + _key([provider, scope_ref, external_id])
    content_hash = sha256(raw_bytes).hexdigest()
    record_id = "source-record-" + _key([source_id, content_hash, external_revision])
    return SourceRecord(record_id, source_id, source_type, provider, scope_ref, external_id, external_revision, content_hash, source_timestamp, captured_at)


def mark_source_deleted(source: SourceRecord, deleted_at: datetime) -> SourceRecord:
    """Return a tombstone retaining the last content hash; do not cancel a Task."""
    _instant(deleted_at)
    if source.state == "DELETED":
        if source.deleted_at != deleted_at:
            raise ValueError("Conflicting source-deletion observation")
        return source
    return replace(source, record_id="source-record-" + _key([source.record_id, "DELETED", deleted_at.isoformat()]), state="DELETED", deleted_at=deleted_at)


ALLOWED_FACTS = frozenset(("title", "completion", "disposition", "requiredness", "importance", "difficulty", "remaining_seconds", "deadline_text"))


@dataclass(frozen=True)
class Candidate:
    candidate_id: str
    source_id: str
    source_record_id: str
    source_hash: str
    parser_version: str
    action: str
    target_task_id: str | None
    target_revision: int | None
    proposed_fields_json: str
    confidence: Decimal
    created_at: datetime
    review_state: str = "PENDING"
    authority_ref: str | None = None
    reviewed_at: datetime | None = None
    canonical_task_id: str | None = None

    def __post_init__(self):
        for identity in (self.candidate_id, self.source_id, self.source_record_id, self.parser_version):
            _identity(identity)
        _hash(self.source_hash)
        _instant(self.created_at)
        if self.action not in ("CREATE_TASK", "UPDATE_TASK", "COMPLETE_TASK", "CANCEL_TASK"):
            raise ValueError("Unsupported candidate action")
        if self.target_task_id is None:
            if self.target_revision is not None:
                raise ValueError("Unresolved target cannot carry a revision")
        else:
            _identity(self.target_task_id)
            if type(self.target_revision) is not int or self.target_revision < 1 or self.action == "CREATE_TASK":
                raise ValueError("Existing targets require a positive revision and update action")
        facts = json.loads(self.proposed_fields_json)
        if not isinstance(facts, dict) or not facts or set(facts) - ALLOWED_FACTS:
            raise ValueError("Proposed facts cannot include authority or unknown control fields")
        if self.action == "COMPLETE_TASK" and facts.get("completion") != "COMPLETE":
            raise ValueError("Completion proposals retain their stated action")
        if self.action == "CANCEL_TASK" and facts.get("disposition") != "CANCELLED":
            raise ValueError("Cancellation proposals retain their stated action")
        if not isinstance(self.confidence, Decimal) or not self.confidence.is_finite() or not 0 <= self.confidence <= 1:
            raise ValueError("Confidence must be a finite value in 0..1")
        if self.review_state in ("CONFIRMED", "REJECTED"):
            _identity(self.authority_ref)
            _instant(self.reviewed_at)
            if self.reviewed_at < self.created_at:
                raise ValueError("Review cannot precede the proposal")
            if self.review_state == "CONFIRMED":
                _identity(self.canonical_task_id)
            elif self.canonical_task_id is not None:
                raise ValueError("Rejected proposals are not canonical Tasks")
        elif self.review_state in ("PENDING", "CONFLICTED"):
            if any(value is not None for value in (self.authority_ref, self.reviewed_at, self.canonical_task_id)):
                raise ValueError("Pending/conflicted evidence carries no accepted authority")
        else:
            raise ValueError("Unsupported candidate review state")

    @property
    def proposed_fields(self) -> dict[str, Any]:
        # A caller cannot mutate the frozen candidate through a nested dict.
        return json.loads(self.proposed_fields_json)

    @property
    def proposal_fingerprint(self):
        return (self.source_id, self.source_record_id, self.source_hash, self.parser_version, self.action, self.target_task_id, self.target_revision, self.proposed_fields_json, self.confidence)

    def as_record(self):
        return {
            "schema_version": "0.1.0-draft", "candidate_id": self.candidate_id,
            "source_ref": {"source_id": self.source_id, "record_id": self.source_record_id, "content_hash": self.source_hash},
            "parser_version": self.parser_version, "action": self.action,
            "target_ref": None if self.target_task_id is None else {"task_id": self.target_task_id, "revision": self.target_revision},
            "proposed_fields": self.proposed_fields, "confidence": float(self.confidence), "created_at": self.created_at.isoformat(),
            "review": {"state": self.review_state, "authority_ref": self.authority_ref, "reviewed_at": self.reviewed_at.isoformat() if self.reviewed_at else None, "canonical_task_id": self.canonical_task_id},
        }


def make_candidate(
    source: SourceRecord, *, parser_version: str, action: str,
    proposed_fields: dict[str, Any], confidence: float | str | Decimal,
    target_task_id: str | None = None, target_revision: int | None = None,
) -> Candidate:
    """External confidence is advisory: every parser result starts pending."""
    if source.state != "PRESENT":
        raise ValueError("Source deletion does not manufacture a Task action")
    if isinstance(confidence, bool):
        raise ValueError("Confidence must be numeric")
    fields_json = json.dumps(proposed_fields, sort_keys=True, separators=(",", ":"), allow_nan=False)
    identity = "candidate-" + _key([source.record_id, source.content_hash, parser_version, action, target_task_id, target_revision])
    return Candidate(identity, source.source_id, source.record_id, source.content_hash, parser_version, action, target_task_id, target_revision, fields_json, Decimal(str(confidence)), source.captured_at)


def ingest_candidate(history: tuple[Candidate, ...], proposal: Candidate) -> tuple[Candidate, ...]:
    """Preserve reviewed history on replay; diagnose nondeterministic parsing."""
    if proposal.review_state != "PENDING":
        raise ValueError("Ingestion cannot mint a reviewed candidate")
    for previous in history:
        if previous.candidate_id == proposal.candidate_id:
            if previous.proposal_fingerprint != proposal.proposal_fingerprint:
                raise ValueError("Same source/parser identity produced conflicting facts")
            return history
    return history + (proposal,)
