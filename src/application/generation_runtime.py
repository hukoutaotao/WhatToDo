"""Trusted worker policy and detached outcomes; neither is an input authority."""
from dataclasses import dataclass, field

from src.application.definitions import DefinitionKey, identity
from src.application.evidence_storage import SourceScope
from src.application.generation_commit import GenerationOccurrenceRecord
from src.application.generation_evaluator import require
from src.application.ports import CommitReceipt
from src.application.relationship_validation import GraphLimits


@dataclass(frozen=True)
class GenerationPolicy:
    principal_id: str
    rule_keys: tuple[DefinitionKey, ...]
    source_scopes: tuple[SourceScope, ...]
    limits: GraphLimits = GraphLimits()

    def __post_init__(self):
        require(identity(self.principal_id) and isinstance(self.limits, GraphLimits), 'GENERATION_POLICY_IDENTITY')
        require(isinstance(self.rule_keys, tuple) and 0 < len(self.rule_keys) <= self.limits.max_rules
            and all(isinstance(k, DefinitionKey) and k.kind == 'RELATIONSHIP_RULE' for k in self.rule_keys)
            and len({k.id for k in self.rule_keys}) == len(self.rule_keys), 'GENERATION_POLICY_RULE_VERSIONS')
        require(isinstance(self.source_scopes, tuple) and 0 < len(self.source_scopes) <= 1000
            and all(isinstance(s, SourceScope) for s in self.source_scopes)
            and len({(s.provider, s.scope_ref) for s in self.source_scopes}) == len(self.source_scopes),
            'GENERATION_POLICY_SOURCE_SCOPES')


@dataclass(frozen=True)
class GenerationOutcome:
    state: str
    occurrence: GenerationOccurrenceRecord | None = field(default=None, repr=False)
    receipt: CommitReceipt | None = None

    def __post_init__(self):
        require((self.state == 'NOT_ELIGIBLE' and self.occurrence is None and self.receipt is None)
            or (isinstance(self.occurrence, GenerationOccurrenceRecord) and self.state == self.occurrence.state
                and isinstance(self.receipt, CommitReceipt)), 'GENERATION_OUTCOME')
