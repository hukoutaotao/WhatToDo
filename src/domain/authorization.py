"""Pure scoped authorization, using independently trusted context/records.

Command JSON never constructs caller identities or populates the grant registry.
This module makes decisions only; authentication, transactions, audit and replay
are application/adapter responsibilities.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime
from hashlib import sha256
import json
from typing import Mapping


ORIGINS = frozenset(("USER_COMMAND", "RELATIONSHIP_RULE", "EXPIRATION_PROCESS", "EXTERNAL"))
FIELDS = frozenset(("title", "completion", "disposition", "requiredness", "importance", "difficulty", "user_remaining_seconds", "expiration_condition_ref", "expiration_notice_ref"))


def _identity(value):
    if not isinstance(value, str) or not value.strip():
        raise ValueError("A nonblank identity is required")


def _instant(value):
    if not isinstance(value, datetime) or value.utcoffset() is None:
        raise ValueError("An explicit timezone is required")


def _fields(fields):
    for name in ("importance",):
        if name in fields and (type(fields[name]) is not int or not 1 <= fields[name] <= 5):
            raise ValueError("Task ratings must be integers 1..5")
    if "difficulty" in fields:
        values = fields["difficulty"]
        if not isinstance(values, dict) or set(values) != {"thinking_depth", "repetitive_volume", "new_learning_load"} or any(type(value) is not int or not 1 <= value <= 5 for value in values.values()):
            raise ValueError("All three task-level difficulty ratings are required")
    if "user_remaining_seconds" in fields:
        value = fields["user_remaining_seconds"]
        if value is not None and (type(value) is not int or value < 0):
            raise ValueError("User remaining effort is unknown or nonnegative integer seconds")
    for name, allowed in (("completion", ("COMPLETE", "INCOMPLETE")), ("disposition", ("ACTIVE", "CANCELLED", "EXPIRED")), ("requiredness", ("REQUIRED", "OPTIONAL", "EXPIRING"))):
        if name in fields and fields[name] not in allowed:
            raise ValueError("Unsupported task dimension")
    if "title" in fields:
        _identity(fields["title"])
    for name in ("expiration_condition_ref", "expiration_notice_ref"):
        if name in fields and fields[name] is not None:
            _identity(fields[name])


@dataclass(frozen=True)
class Change:
    task_id: str
    expected_revision: int | None
    action: str
    fields_json: str

    def __post_init__(self):
        _identity(self.task_id)
        fields = json.loads(self.fields_json)
        if not isinstance(fields, dict) or not fields or set(fields) - FIELDS:
            raise ValueError("Unknown/empty change fields")
        _fields(fields)
        if self.action == "CREATE_TASK":
            if self.expected_revision is not None:
                raise ValueError("Creation expects an absent target")
        elif self.action in ("UPDATE_TASK", "EXPIRE_TASK"):
            if type(self.expected_revision) is not int or self.expected_revision < 1:
                raise ValueError("Mutation requires a positive expected revision")
        else:
            raise ValueError("Unsupported command action")

    @property
    def fields(self):
        return json.loads(self.fields_json)

    @property
    def fingerprint(self):
        return (self.task_id, self.expected_revision, self.action, self.fields_json)


def change(task_id, expected_revision, action, fields):
    return Change(task_id, expected_revision, action, json.dumps(fields, sort_keys=True, separators=(",", ":"), allow_nan=False))


@dataclass(frozen=True)
class RuleScope:
    rule_id: str
    version: str
    source_task_id: str
    creation_event_ref: str
    occurrence_key: str
    target_role: str

    def __post_init__(self):
        for value in asdict(self).values():
            _identity(value)

    @property
    def generation_key(self):
        # Rule version is audit metadata, not a new occurrence/creation key.
        parts = (self.rule_id, self.source_task_id, self.occurrence_key, self.target_role)
        return "generation-" + sha256(json.dumps(parts, separators=(",", ":")).encode()).hexdigest()


@dataclass(frozen=True)
class Command:
    command_id: str
    principal_id: str
    origin: str
    authority_ref: str
    changes: tuple[Change, ...]
    rule_scope: RuleScope | None = None
    batch_ref: str | None = None
    batch_members: tuple[str, ...] = ()

    def __post_init__(self):
        for value in (self.command_id, self.principal_id, self.authority_ref):
            _identity(value)
        if self.origin not in ORIGINS or not self.changes:
            raise ValueError("Command origin and concrete changes are required")
        if not isinstance(self.changes, tuple) or not all(isinstance(item, Change) for item in self.changes):
            raise ValueError("Resolved changes must be immutable")
        ids = [item.task_id for item in self.changes]
        if len(ids) != len(set(ids)):
            raise ValueError("Resolve repeated targets into one change before authorization")
        if (self.origin == "RELATIONSHIP_RULE") != (self.rule_scope is not None):
            raise ValueError("Rule origin and scope must agree")
        if self.rule_scope is not None and not isinstance(self.rule_scope, RuleScope):
            raise ValueError("Rule scope must be a resolved immutable value")
        if not isinstance(self.batch_members, tuple):
            raise ValueError("Batch membership must be immutable")
        for member in self.batch_members:
            _identity(member)
        if self.batch_ref is None:
            if self.batch_members:
                raise ValueError("Batch members require a batch reference")
        else:
            _identity(self.batch_ref)
            if len(self.batch_members) != len(set(self.batch_members)) or set(self.batch_members) != set(ids):
                raise ValueError("Batch membership must match exact resolved targets")

    @property
    def resolved_changes(self):
        return tuple(sorted((item.fingerprint for item in self.changes), key=lambda item: item[0]))

    def as_record(self):
        return {
            "schema_version": "0.1.0-draft", "command_id": self.command_id,
            "principal_id": self.principal_id, "origin": self.origin, "authority_ref": self.authority_ref,
            "changes": [{"task_id": item.task_id, "expected_revision": item.expected_revision, "action": item.action, "fields": item.fields} for item in self.changes],
            "rule_scope": asdict(self.rule_scope) if self.rule_scope else None,
            "batch_ref": self.batch_ref, "batch_members": list(self.batch_members),
        }

    @property
    def fingerprint(self):
        record = self.as_record()
        record["changes"] = sorted(record["changes"], key=lambda item: item["task_id"])
        record["batch_members"] = sorted(record["batch_members"])
        return sha256(json.dumps(record, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()).hexdigest()


@dataclass(frozen=True)
class CallerIdentity:
    """Injected by a trusted authenticated transport, never decoded from JSON."""
    principal_id: str
    origin: str
    authenticated: bool

    def __post_init__(self):
        _identity(self.principal_id)
        if self.origin not in ORIGINS or type(self.authenticated) is not bool:
            raise ValueError("Explicit trusted caller context is required")


@dataclass(frozen=True)
class AuthorityGrant:
    """Resolved from a user instruction/accepted rule/policy by trusted code."""
    grant_id: str
    principal_id: str
    origin: str
    command_id: str
    changes: tuple[Change, ...]
    evidence_ref: str
    issued_at: datetime
    active: bool = True
    expires_at: datetime | None = None
    rule_scope: RuleScope | None = None
    essential_fields: frozenset[str] = frozenset()
    batch_ref: str | None = None
    batch_members: tuple[str, ...] = ()

    def __post_init__(self):
        for value in (self.grant_id, self.principal_id, self.command_id, self.evidence_ref):
            _identity(value)
        _instant(self.issued_at)
        if self.expires_at is not None:
            _instant(self.expires_at)
            if self.expires_at <= self.issued_at:
                raise ValueError("Grant validity must end after issuance")
        if self.origin not in ORIGINS - {"EXTERNAL"} or type(self.active) is not bool:
            raise ValueError("External evidence cannot be an authority grant")
        Command(self.command_id, self.principal_id, self.origin, self.grant_id, self.changes, self.rule_scope, self.batch_ref, self.batch_members)
        if not isinstance(self.essential_fields, frozenset) or self.essential_fields - FIELDS:
            raise ValueError("Essential field scope must be explicit and supported")

    @property
    def resolved_changes(self):
        return tuple(sorted((item.fingerprint for item in self.changes), key=lambda item: item[0]))


@dataclass(frozen=True)
class TaskState:
    task_id: str
    revision: int
    requiredness: str = "REQUIRED"
    completion: str = "INCOMPLETE"
    disposition: str = "ACTIVE"
    expiration_condition_ref: str | None = None

    def __post_init__(self):
        _identity(self.task_id)
        if type(self.revision) is not int or self.revision < 1:
            raise ValueError("Positive canonical revision required")
        if self.requiredness not in ("REQUIRED", "OPTIONAL", "EXPIRING") or self.completion not in ("COMPLETE", "INCOMPLETE") or self.disposition not in ("ACTIVE", "CANCELLED", "EXPIRED"):
            raise ValueError("Unsupported canonical task dimensions")


@dataclass(frozen=True)
class CreationRecord:
    event_id: str
    source_task_id: str
    occurrence_key: str
    canonical_creation: bool

    def __post_init__(self):
        for value in (self.event_id, self.source_task_id, self.occurrence_key):
            _identity(value)
        if type(self.canonical_creation) is not bool:
            raise ValueError("Creation evidence must distinguish canonical events explicitly")


@dataclass(frozen=True)
class NoticeEvidence:
    notice_id: str
    task_id: str
    task_revision: int
    condition_ref: str
    condition_confirmed: bool
    condition_observed_at: datetime
    delivery_state: str
    delivered_at: datetime | None

    def __post_init__(self):
        for value in (self.notice_id, self.task_id, self.condition_ref):
            _identity(value)
        _instant(self.condition_observed_at)
        if type(self.task_revision) is not int or self.task_revision < 1 or type(self.condition_confirmed) is not bool:
            raise ValueError("Notice target/version/condition must be explicit")
        if self.delivery_state not in ("PENDING", "DELIVERED", "FAILED", "UNKNOWN"):
            raise ValueError("Unsupported dispatch result")
        if self.delivery_state == "DELIVERED":
            _instant(self.delivered_at)
            if self.delivered_at < self.condition_observed_at:
                raise ValueError("Delivery cannot precede detection")
        elif self.delivered_at is not None:
            raise ValueError("Unconfirmed delivery cannot carry a confirmed delivery time")


@dataclass(frozen=True)
class AuthorizationDecision:
    allowed: bool
    reason: str
    request_fingerprint: str


def authorize(
    command: Command, *, caller: CallerIdentity,
    grants: Mapping[str, AuthorityGrant], tasks: Mapping[str, TaskState], now: datetime,
    creations: Mapping[str, CreationRecord] | None = None,
    notices: Mapping[str, NoticeEvidence] | None = None,
) -> AuthorizationDecision:
    """Require exact resolved scope and current state; never mutate inputs."""
    _instant(now)
    fingerprint = command.fingerprint
    def deny(reason):
        return AuthorizationDecision(False, reason, fingerprint)

    if not caller.authenticated:
        return deny("UNAUTHENTICATED")
    if caller.origin == "EXTERNAL" or command.origin == "EXTERNAL":
        return deny("EXTERNAL_IS_NOT_AUTHORITY")
    grant = grants.get(command.authority_ref)
    if grant is None or grant.grant_id != command.authority_ref:
        return deny("UNREGISTERED_AUTHORITY")
    if not grant.active or grant.issued_at > now or (grant.expires_at is not None and grant.expires_at <= now):
        return deny("INACTIVE_AUTHORITY")
    if command.principal_id != caller.principal_id or grant.principal_id != caller.principal_id or command.origin != caller.origin or grant.origin != caller.origin:
        return deny("CALLER_SCOPE_MISMATCH")
    if grant.command_id != command.command_id or grant.resolved_changes != command.resolved_changes:
        return deny("EXACT_CHANGE_SCOPE_MISMATCH")
    if grant.batch_ref != command.batch_ref or set(grant.batch_members) != set(command.batch_members):
        return deny("BATCH_SCOPE_MISMATCH")
    if grant.rule_scope != command.rule_scope:
        return deny("RULE_SCOPE_MISMATCH")

    if caller.origin == "RELATIONSHIP_RULE":
        scope = command.rule_scope
        creation = (creations or {}).get(scope.creation_event_ref)
        source = tasks.get(scope.source_task_id)
        if source is None or source.task_id != scope.source_task_id or creation is None or not creation.canonical_creation or creation.event_id != scope.creation_event_ref or creation.source_task_id != scope.source_task_id or creation.occurrence_key != scope.occurrence_key:
            return deny("CANONICAL_CREATION_REQUIRED")

    for item in command.changes:
        fields = item.fields
        state = tasks.get(item.task_id)
        if item.action == "CREATE_TASK":
            if state is not None:
                return deny("TARGET_ALREADY_EXISTS")
        elif state is None or state.task_id != item.task_id:
            return deny("UNKNOWN_TARGET")
        elif state.revision != item.expected_revision:
            return deny("STALE_STATE_VERSION")

        if caller.origin == "RELATIONSHIP_RULE":
            if item.action != "CREATE_TASK":
                return deny("RULE_CREATES_ONLY")
            if fields.get("completion", "INCOMPLETE") != "INCOMPLETE" or fields.get("disposition", "ACTIVE") != "ACTIVE":
                return deny("RULE_CANNOT_ASSERT_OUTCOME")
            if any(name not in fields or fields[name] is None for name in grant.essential_fields):
                return deny("MISSING_ESSENTIAL_FACTS")
        if caller.origin == "EXPIRATION_PROCESS" and item.action != "EXPIRE_TASK":
            return deny("EXPIRY_PROCESS_EXPIRES_ONLY")
        if fields.get("disposition") == "EXPIRED" and item.action != "EXPIRE_TASK":
            return deny("EXPIRED_REQUIRES_NOTICE_PROCESS")
        if item.action == "EXPIRE_TASK":
            if set(fields) != {"disposition", "expiration_notice_ref"} or fields.get("disposition") != "EXPIRED":
                return deny("EXPIRY_CANNOT_REWRITE_EFFORT_OR_COMPLETION")
            if state is None or state.requiredness != "EXPIRING" or state.completion != "INCOMPLETE" or state.disposition != "ACTIVE":
                return deny("TASK_NOT_EXPIRABLE")
            notice = (notices or {}).get(fields.get("expiration_notice_ref"))
            if notice is None or notice.notice_id != fields.get("expiration_notice_ref") or notice.task_id != state.task_id or notice.task_revision != state.revision or notice.condition_ref != state.expiration_condition_ref:
                return deny("NOTICE_SCOPE_MISMATCH")
            if not notice.condition_confirmed or notice.delivery_state != "DELIVERED" or notice.delivered_at > now:
                return deny("CONFIRMED_NOTICE_REQUIRED")

    return AuthorizationDecision(True, "AUTHORIZED_EXACT_SCOPE", fingerprint)
