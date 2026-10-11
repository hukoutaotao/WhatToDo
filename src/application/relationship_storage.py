"""Immutable relationship storage values; references do not grant authority.

The owner-only repository is an internal transaction port. It is not exposed
by the command transport and never creates a Task or generation occurrence.
"""
from dataclasses import dataclass
from hashlib import sha256
from typing import Protocol

from src.application.definitions import DefinitionKey, canonical, identity
from src.domain.relationships import Endpoint, RelationshipRule, TaskRelation


class RelationshipStorageError(RuntimeError):
    pass


def require(value, code):
    if not value:
        raise RelationshipStorageError(code)


def digest(value):
    return sha256(canonical(value).encode('utf-8')).hexdigest()


@dataclass(frozen=True)
class RuleStorageRecord:
    rule: RelationshipRule
    source_type: DefinitionKey
    target_type: DefinitionKey
    template: DefinitionKey

    def __post_init__(self):
        require(isinstance(self.rule, RelationshipRule) and self.rule.acceptance_ref is not None,
                'RELATIONSHIP_ACCEPTED_RULE_REQUIRED')
        require(all(isinstance(k, DefinitionKey) for k in
                    (self.source_type, self.target_type, self.template)), 'RELATIONSHIP_DEFINITION_KEYS')
        require((self.source_type.kind, self.source_type.id) == ('TASKTYPE', self.rule.source_type_ref)
                and (self.target_type.kind, self.target_type.id) == ('TASKTYPE', self.rule.target_type_ref)
                and (self.template.kind, self.template.id, self.template.version) ==
                    ('TASK_TEMPLATE', self.rule.target_template_ref, self.rule.target_template_version),
                'RELATIONSHIP_DEFINITION_BINDINGS')

    @property
    def key(self):
        return DefinitionKey('RELATIONSHIP_RULE', self.rule.rule_id, self.rule.version)

    @property
    def payload(self):
        return dict(rule=self.rule.as_record(), references=[dict(kind=k.kind, id=k.id, version=k.version)
                    for k in (self.source_type, self.target_type, self.template)])

    @property
    def content_hash(self):
        return digest(self.payload)


@dataclass(frozen=True)
class EndpointBinding:
    endpoint: Endpoint
    task_id: str
    task_revision: int
    stage_revision: int | None = None

    def __post_init__(self):
        require(isinstance(self.endpoint, Endpoint) and identity(self.task_id)
                and type(self.task_revision) is int and self.task_revision > 0,
                'RELATIONSHIP_ENDPOINT_BINDING')
        require((self.endpoint.kind == 'TASK' and self.endpoint.id == self.task_id
                 and self.stage_revision is None) or
                (self.endpoint.kind == 'STAGE' and type(self.stage_revision) is int
                 and self.stage_revision > 0), 'RELATIONSHIP_ENDPOINT_BINDING')

    @property
    def payload(self):
        return dict(endpoint=dict(kind=self.endpoint.kind, id=self.endpoint.id), task_id=self.task_id,
                    task_revision=self.task_revision, stage_revision=self.stage_revision)


@dataclass(frozen=True)
class RelationStorageRecord:
    relation: TaskRelation
    before: EndpointBinding
    after: EndpointBinding

    def __post_init__(self):
        require(isinstance(self.relation, TaskRelation) and
                isinstance(self.before, EndpointBinding) and isinstance(self.after, EndpointBinding),
                'RELATIONSHIP_TYPED_RELATION_REQUIRED')
        require((self.before.endpoint, self.after.endpoint) ==
                (self.relation.before, self.relation.after), 'RELATIONSHIP_ENDPOINT_DRIFT')
        if self.relation.kind == 'STAGE_MEMBERSHIP':
            require(self.before.task_id == self.after.task_id and
                    self.before.task_revision == self.after.task_revision,
                    'RELATIONSHIP_STAGE_PARENT_MISMATCH')

    @property
    def payload(self):
        return dict(relation=self.relation.as_record(), before=self.before.payload, after=self.after.payload)

    @property
    def content_hash(self):
        return digest(self.payload)


def acceptance_scope(kind, record):
    require((kind == 'RULE' and isinstance(record, RuleStorageRecord)) or
            (kind == 'RELATION' and isinstance(record, RelationStorageRecord)), 'RELATIONSHIP_SCOPE_KIND')
    return dict(relationship_storage=dict(kind=kind, payload_hash=record.content_hash))


class RelationshipRepository(Protocol):
    def register_rule(self, record: RuleStorageRecord): ...
    def get_rule(self, rule_id: str, version: str): ...
    def get_relation(self, relation_id: str, revision: int | None = None): ...
    def append_relation_in_transaction(self, record: RelationStorageRecord, transaction_ref: str): ...
