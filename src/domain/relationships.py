"""Typed relationship checks and generation proposals without state writes.

Reference strings are provenance, not resolved authority. Durable generation and
Planner enforcement must consume these results through their own trusted ports.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime
import json
from typing import Mapping

from src.domain.authorization import CreationRecord, FIELDS, RuleScope, change


def _identity(value):
    if not isinstance(value, str) or not value.strip():
        raise ValueError("A nonblank identity is required")


def _unique(values):
    if len(values) != len(set(values)):
        raise ValueError("Duplicate relationship identity or target field")


def _record(value):
    return {"schema_version": "0.1.0-draft", **json.loads(json.dumps(asdict(value)))}


@dataclass(frozen=True, order=True)
class Endpoint:
    kind: str
    id: str

    def __post_init__(self):
        _identity(self.id)
        if self.kind not in ("TASK", "STAGE"):
            raise ValueError("Task and stage identity must be explicit")


@dataclass(frozen=True)
class TaskRelation:
    relation_id: str
    revision: int
    kind: str
    before: Endpoint
    after: Endpoint
    authority_ref: str
    origin_rule_id: str | None = None
    origin_rule_version: str | None = None

    def __post_init__(self):
        _identity(self.relation_id)
        _identity(self.authority_ref)
        if type(self.revision) is not int or self.revision < 1:
            raise ValueError("A positive relation revision is required")
        if self.kind not in ("COMPLETION_ORDER", "START_PREREQUISITE", "SOFT_SEQUENCE", "STAGE_MEMBERSHIP"):
            raise ValueError("Generation is a rule, not an execution-order link")
        if not isinstance(self.before, Endpoint) or not isinstance(self.after, Endpoint):
            raise ValueError("Typed endpoints are required")
        if self.kind == "STAGE_MEMBERSHIP" and (self.before.kind != "TASK" or self.after.kind != "STAGE"):
            raise ValueError("Membership runs from parent Task to stage")
        if (self.origin_rule_id is None) != (self.origin_rule_version is None):
            raise ValueError("Rule identity and audit version must travel together")
        if self.origin_rule_id is not None:
            _identity(self.origin_rule_id)
            _identity(self.origin_rule_version)

    def as_record(self):
        return _record(self)


@dataclass(frozen=True)
class FieldMapping:
    target_field: str
    kind: str
    source_field: str | None
    literal_json: str | None

    def __post_init__(self):
        if self.target_field not in FIELDS or self.kind not in ("SOURCE", "DEFAULT", "LITERAL"):
            raise ValueError("Unsupported mapped target field or binding")
        if self.kind == "LITERAL":
            if self.source_field is not None or not isinstance(self.literal_json, str):
                raise ValueError("A literal has no lookup field")
            # Reject non-finite JSON even if supplied through the typed API.
            json.dumps(json.loads(self.literal_json), allow_nan=False)
        else:
            _identity(self.source_field)
            if self.literal_json is not None:
                raise ValueError("A lookup is not also a literal")


def literal(target_field, value):
    return FieldMapping(target_field, "LITERAL", None, json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False))


@dataclass(frozen=True)
class RelationshipRule:
    rule_id: str
    version: str
    active: bool
    acceptance_ref: str | None
    trigger: str
    source_type_ref: str
    target_type_ref: str
    target_template_ref: str
    target_template_version: str
    target_role: str
    obligation_kind: str
    essential_fields: tuple[str, ...]
    mappings: tuple[FieldMapping, ...]

    def __post_init__(self):
        for value in (self.rule_id, self.version, self.source_type_ref, self.target_type_ref, self.target_template_ref, self.target_template_version, self.target_role):
            _identity(value)
        if type(self.active) is not bool or self.trigger != "CANONICAL_CREATION" or self.obligation_kind not in ("SEPARATE_TASK", "STAGE"):
            raise ValueError("An explicit canonical trigger and obligation kind are required")
        if self.acceptance_ref is not None:
            _identity(self.acceptance_ref)
        if self.active and self.acceptance_ref is None:
            raise ValueError("An active rule needs accepted provenance")
        if not isinstance(self.essential_fields, tuple) or not isinstance(self.mappings, tuple) or not self.mappings:
            raise ValueError("Mapping scope must be immutable")
        _unique(self.essential_fields)
        _unique([item.target_field for item in self.mappings])
        if set(self.essential_fields) - FIELDS or not {"title", "completion", "disposition"} <= set(self.essential_fields):
            raise ValueError("Essential creation facts must remain explicit")

    def as_record(self):
        return _record(self)


@dataclass(frozen=True)
class RelationshipIssue:
    code: str
    identities: tuple[str, ...]


def _cycles(edges):
    """Deterministic SCC diagnostics; iterative traversal handles finite chains."""
    adjacency, reverse = {}, {}
    for before, after, identity in edges:
        adjacency.setdefault(before, []).append(after)
        adjacency.setdefault(after, [])
        reverse.setdefault(after, []).append(before)
        reverse.setdefault(before, [])
    visited, finish = set(), []
    for root in sorted(adjacency):
        if root in visited:
            continue
        visited.add(root)
        stack = [(root, iter(sorted(adjacency[root])))]
        while stack:
            node, children = stack[-1]
            child = next(children, None)
            if child is None:
                finish.append(node)
                stack.pop()
            elif child not in visited:
                visited.add(child)
                stack.append((child, iter(sorted(adjacency[child]))))
    visited, results = set(), []
    for root in reversed(finish):
        if root in visited:
            continue
        members, pending = set(), [root]
        visited.add(root)
        while pending:
            node = pending.pop()
            members.add(node)
            for parent in reverse[node]:
                if parent not in visited:
                    visited.add(parent)
                    pending.append(parent)
        if len(members) > 1 or any(before == after and before in members for before, after, _ in edges):
            results.append(tuple(sorted({identity for before, after, identity in edges if before in members and after in members and identity is not None})))
    return tuple(sorted(results))


def check_relationships(rules: tuple[RelationshipRule, ...], relations: tuple[TaskRelation, ...], *, endpoints: frozenset[Endpoint]):
    """Keep generation, hard-order, soft and stage accounting graphs separate."""
    _unique([rule.rule_id for rule in rules])
    _unique([relation.relation_id for relation in relations])
    generation = [(rule.source_type_ref, rule.target_type_ref, rule.rule_id) for rule in rules if rule.active]
    issues = [RelationshipIssue("RECURSIVE_GENERATION", ids) for ids in _cycles(generation)]
    hard = [((endpoint.kind, endpoint.id, "START"), (endpoint.kind, endpoint.id, "FINISH"), None) for endpoint in endpoints]
    parents = {}
    for relation in relations:
        if relation.before not in endpoints or relation.after not in endpoints:
            issues.append(RelationshipIssue("UNRESOLVED_ENDPOINT", (relation.relation_id,)))
            continue
        if relation.kind == "STAGE_MEMBERSHIP":
            parents.setdefault(relation.after, []).append(relation.relation_id)
        elif relation.kind in ("COMPLETION_ORDER", "START_PREREQUISITE"):
            after_event = "START" if relation.kind == "START_PREREQUISITE" else "FINISH"
            hard.append(((relation.before.kind, relation.before.id, "FINISH"), (relation.after.kind, relation.after.id, after_event), relation.relation_id))
    issues.extend(RelationshipIssue("MULTIPLE_STAGE_PARENTS", tuple(sorted(ids))) for ids in parents.values() if len(ids) > 1)
    issues.extend(RelationshipIssue("CONTRADICTORY_HARD_ORDER", ids) for ids in _cycles(hard))
    return tuple(sorted(issues, key=lambda item: (item.code, item.identities)))


@dataclass(frozen=True)
class GenerationOccurrence:
    scope: RuleScope
    obligation_kind: str
    state: str
    target_id: str | None = None
    missing_fields: tuple[str, ...] = ()
    failure_code: str | None = None

    def __post_init__(self):
        if not isinstance(self.scope, RuleScope) or self.obligation_kind not in ("SEPARATE_TASK", "STAGE"):
            raise ValueError("Resolved occurrence scope is required")
        if not isinstance(self.missing_fields, tuple):
            raise ValueError("Pending facts must be immutable")
        _unique(self.missing_fields)
        for field in self.missing_fields:
            _identity(field)
        if self.state == "CREATED":
            _identity(self.target_id)
            if self.missing_fields or self.failure_code is not None:
                raise ValueError("Created occurrences cannot also be unresolved")
        elif self.state == "PENDING":
            if self.target_id is not None or not self.missing_fields or self.failure_code is not None:
                raise ValueError("Pending occurrences retain missing facts, no invented target")
        elif self.state == "FAILED":
            _identity(self.failure_code)
            if self.target_id is not None or self.missing_fields:
                raise ValueError("Failed occurrences carry a diagnostic")
        else:
            raise ValueError("Unsupported occurrence state")

    def as_record(self):
        scope = self.scope
        return {"schema_version": "0.1.0-draft", "generation_key": scope.generation_key, "rule_id": scope.rule_id, "rule_version": scope.version, "source_task_id": scope.source_task_id, "creation_event_ref": scope.creation_event_ref, "occurrence_key": scope.occurrence_key, "target_role": scope.target_role, "obligation_kind": self.obligation_kind, "state": self.state, "target_id": self.target_id, "missing_fields": list(self.missing_fields), "failure_code": self.failure_code}


@dataclass(frozen=True)
class GenerationResolution:
    state: str
    reason: str
    generation_key: str
    fields_json: str | None = None
    missing_fields: tuple[str, ...] = ()
    recorded: GenerationOccurrence | None = None

    @property
    def fields(self):
        return json.loads(self.fields_json) if self.fields_json is not None else None


def resolve_generation(rule: RelationshipRule, scope: RuleScope, *, creation: CreationRecord, source_type_ref: str, source_fields: Mapping, template_ref: str, template_version: str, defaults: Mapping, occurrences: Mapping[str, GenerationOccurrence]) -> GenerationResolution:
    """Resolve a proposal only; an independent grant is still required to write."""
    key = scope.generation_key
    if not rule.active or rule.acceptance_ref is None:
        return GenerationResolution("NOT_ELIGIBLE", "RULE_INACTIVE", key)
    if (scope.rule_id, scope.version, scope.target_role, source_type_ref, template_ref, template_version) != (rule.rule_id, rule.version, rule.target_role, rule.source_type_ref, rule.target_template_ref, rule.target_template_version):
        return GenerationResolution("NOT_ELIGIBLE", "RULE_SCOPE_MISMATCH", key)
    if not creation.canonical_creation or (creation.event_id, creation.source_task_id, creation.occurrence_key) != (scope.creation_event_ref, scope.source_task_id, scope.occurrence_key):
        return GenerationResolution("NOT_ELIGIBLE", "CANONICAL_CREATION_REQUIRED", key)
    previous = occurrences.get(key)
    if previous is not None:
        if previous.scope.generation_key != key or previous.obligation_kind != rule.obligation_kind:
            return GenerationResolution("CONFLICT", "OCCURRENCE_SCOPE_CONFLICT", key, recorded=previous)
        if previous.state == "CREATED":
            return GenerationResolution("ALREADY_RECORDED", "CREATION_REPLAY", key, recorded=previous)
    resolved = {}
    for binding in rule.mappings:
        if binding.kind == "LITERAL":
            resolved[binding.target_field] = json.loads(binding.literal_json)
        else:
            values = source_fields if binding.kind == "SOURCE" else defaults
            if binding.source_field in values:
                resolved[binding.target_field] = values[binding.source_field]
    missing = tuple(sorted(field for field in rule.essential_fields if field not in resolved or resolved[field] is None))
    if missing:
        return GenerationResolution("PENDING", "ESSENTIAL_FACTS_MISSING", key, missing_fields=missing)
    try:
        # Reuse typed creation-field checks; do not apply a Task mutation.
        change("synthetic-validation-only", None, "CREATE_TASK", resolved)
    except (ValueError, TypeError):
        return GenerationResolution("PENDING", "INVALID_MAPPED_FACTS", key)
    if resolved["completion"] != "INCOMPLETE" or resolved["disposition"] != "ACTIVE":
        return GenerationResolution("PENDING", "CREATION_CANNOT_INFER_OUTCOME", key)
    return GenerationResolution("PROPOSED", "MAPPING_RESOLVED_NOT_AUTHORIZED", key, json.dumps(resolved, sort_keys=True, separators=(",", ":"), allow_nan=False))


@dataclass(frozen=True)
class ExecutionTimes:
    endpoint: Endpoint
    started_at: datetime | None = None
    completed_at: datetime | None = None

    def __post_init__(self):
        if not isinstance(self.endpoint, Endpoint):
            raise ValueError("Typed execution identity is required")
        for instant in (self.started_at, self.completed_at):
            if instant is not None and (not isinstance(instant, datetime) or instant.utcoffset() is None):
                raise ValueError("An explicit timezone is required")
        if self.started_at is not None and self.completed_at is not None and self.started_at > self.completed_at:
            raise ValueError("A Task cannot finish before its recorded start")


def check_execution_order(relations: tuple[TaskRelation, ...], executions: Mapping[Endpoint, ExecutionTimes]):
    """Report hard ordering violations without rejecting or rewriting reality."""
    issues = []
    for relation in relations:
        if relation.kind not in ("COMPLETION_ORDER", "START_PREREQUISITE"):
            continue
        before, after = executions.get(relation.before), executions.get(relation.after)
        target_time = None if after is None else (after.started_at if relation.kind == "START_PREREQUISITE" else after.completed_at)
        if target_time is None:
            continue
        if before is None or before.completed_at is None:
            issues.append(RelationshipIssue("ORDER_EVIDENCE_MISSING", (relation.relation_id,)))
        elif before.completed_at > target_time:
            issues.append(RelationshipIssue("ORDER_VIOLATION", (relation.relation_id,)))
    return tuple(issues)
