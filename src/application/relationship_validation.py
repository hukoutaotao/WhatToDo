"""Bounded typed graph validation; no authority, mutation or Task generation.

Callers select one rule/link version per stable ID and resolve endpoint ownership
in their own scoped snapshot. A VALID result certifies only this input graph,
not a current commit, active rule selection, actual history or a feasible plan.
"""
from collections import deque
from dataclasses import asdict, dataclass

from src.application.definitions import canonical, identity
from src.application.relationship_storage import RuleStorageRecord, RelationStorageRecord, digest
from src.domain.relationships import Endpoint


class RelationshipGraphError(ValueError):
    pass


def require(value, code):
    if not value:
        raise RelationshipGraphError(code)


@dataclass(frozen=True)
class EndpointFact:
    endpoint: Endpoint
    parent_task_id: str | None = None

    def __post_init__(self):
        require(isinstance(self.endpoint, Endpoint) and identity(self.endpoint.id), 'GRAPH_ENDPOINT_FACT')
        require((self.endpoint.kind == 'TASK' and self.parent_task_id is None) or
                (self.endpoint.kind == 'STAGE' and identity(self.parent_task_id)), 'GRAPH_STAGE_OWNER_REQUIRED')


@dataclass(frozen=True)
class GraphSnapshot:
    rules: tuple[RuleStorageRecord, ...]
    relations: tuple[RelationStorageRecord, ...]
    endpoints: tuple[EndpointFact, ...]

    def __post_init__(self):
        for items, kind in ((self.rules, RuleStorageRecord), (self.relations, RelationStorageRecord),
                            (self.endpoints, EndpointFact)):
            require(isinstance(items, tuple) and all(isinstance(item, kind) for item in items), 'GRAPH_IMMUTABLE_TYPED_SNAPSHOT')


@dataclass(frozen=True)
class GraphLimits:
    max_rules: int = 2048
    max_relations: int = 4096
    max_endpoints: int = 4096
    max_payload_bytes: int = 8388608
    max_traversal_work: int = 250000
    max_generation_depth: int = 32
    max_generated_instances: int = 10000

    def __post_init__(self):
        require(all(type(value) is int and value > 0 for value in asdict(self).values()), 'GRAPH_POSITIVE_LIMITS')
        require(self.max_rules <= 100000 and self.max_relations <= 100000 and self.max_endpoints <= 100000
                and self.max_payload_bytes <= 67108864 and self.max_traversal_work <= 10000000
                and self.max_generation_depth <= 100000 and self.max_generated_instances <= 10000000,
                'GRAPH_LIMIT_CEILING')


@dataclass(frozen=True, order=True)
class GraphIssue:
    code: str
    identities: tuple[str, ...]
    limit: int = 0
    observed_lower_bound: int = 0


@dataclass(frozen=True)
class GraphValidation:
    status: str
    issues: tuple[GraphIssue, ...]
    input_hash: str | None
    traversal_work: int
    generation_depth: int | None
    generated_instances: int | None
    generation_counts_exact: bool
    complete: bool
    limits: GraphLimits

    @property
    def valid(self):
        return self.status == 'VALID' and self.complete


class _WorkLimit(Exception):
    def __init__(self, identity):
        self.identity = identity


class _Budget:
    def __init__(self, limit):
        self.limit = limit; self.used = 0

    def visit(self, identity=None):
        if self.used >= self.limit:
            raise _WorkLimit(identity)
        self.used += 1


def _components(edges, budget):
    """Iterative SCCs. Each node/edge is visited a bounded number of times."""
    outgoing, incoming = {}, {}
    for before, after, ident in edges:
        budget.visit(ident)
        outgoing.setdefault(before, []).append(after); outgoing.setdefault(after, [])
        incoming.setdefault(after, []).append(before); incoming.setdefault(before, [])
    seen, finish = set(), []
    for root in sorted(outgoing):
        budget.visit()
        if root in seen: continue
        seen.add(root); pending = [(root, iter(sorted(outgoing[root])))]
        while pending:
            node, children = pending[-1]; child = next(children, None); budget.visit()
            if child is None:
                finish.append(node); pending.pop()
            elif child not in seen:
                seen.add(child); pending.append((child, iter(sorted(outgoing[child]))))
    labels, size = {}, {}
    for root in reversed(finish):
        budget.visit()
        if root in labels: continue
        group = len(size); size[group] = 0; labels[root] = group; pending = [root]
        while pending:
            node = pending.pop(); size[group] += 1; budget.visit()
            for parent in incoming[node]:
                budget.visit()
                if parent not in labels:
                    labels[parent] = group; pending.append(parent)
    cycles = {}
    for before, after, ident in edges:
        budget.visit(ident); group = labels[before]
        if group == labels[after] and (size[group] > 1 or before == after):
            if ident is not None: cycles.setdefault(group, set()).add(ident)
    return tuple(sorted(tuple(sorted(ids)) for ids in cycles.values()))


def _generation_bounds(edges, limits, budget):
    """Per initial occurrence, parallel rules/converging paths create own targets.

    Counts saturate at cap + 1 rather than expanding the cascade or growing big
    integers. A stage counts as generated work, never as a second effort budget.
    """
    outgoing, indegree = {}, {}
    for source, target, ident in edges:
        budget.visit(ident)
        outgoing.setdefault(source, []).append((target, ident)); outgoing.setdefault(target, [])
        indegree.setdefault(source, 0); indegree[target] = indegree.get(target, 0) + 1
    pending = deque(sorted(node for node in outgoing if indegree[node] == 0))
    depth = {node: 0 for node in outgoing}; parent = {}; ordered = []; issues = []
    deepest = 0
    while pending:
        node = pending.popleft(); ordered.append(node); budget.visit()
        for child, ident in sorted(outgoing[node]):
            budget.visit(ident)
            if depth[node] + 1 > depth[child]:
                depth[child] = depth[node] + 1; parent[child] = (node, ident)
            deepest = max(deepest, depth[child]); indegree[child] -= 1
            if indegree[child] == 0: pending.append(child)
    if deepest > limits.max_generation_depth:
        offender = min(node for node in depth if depth[node] == deepest)
        path = []
        while offender in parent:
            budget.visit(); offender, ident = parent[offender]; path.append(ident)
        issues.append(GraphIssue('GENERATION_DEPTH_LIMIT', tuple(reversed(path)), limits.max_generation_depth, deepest))
    counts = {}; witness = {}; largest = 0
    cap = limits.max_generated_instances
    for node in reversed(ordered):
        total = 0; prefix = []
        for child, ident in sorted(outgoing[node]):
            budget.visit(ident); prefix.append(ident)
            total = min(cap + 1, total + 1 + counts[child])
            if total > cap: break
        counts[node] = total; largest = max(largest, total)
        if total > cap: witness[node] = tuple(prefix)
    if largest > cap:
        # Find a bounded, connected witness. Traversal never enumerates targets.
        root = min(node for node in witness)
        selected, pending, visited = set(), [root], set()
        while pending:
            node = pending.pop(); budget.visit()
            if node in visited: continue
            visited.add(node)
            for child, ident in outgoing[node]:
                budget.visit(ident); selected.add(ident); pending.append(child)
        issues.append(GraphIssue('GENERATION_INSTANCE_LIMIT', tuple(sorted(selected)), cap, cap + 1))
    return deepest, largest, tuple(issues)


def _bounded_payload(snapshot, limits):
    """Check literal bounds before constructing serialized rule payloads."""
    total = 0
    for record in snapshot.rules:
        value = record.rule
        if any(isinstance(item, str) and len(item) > limits.max_payload_bytes
               for item in vars(value).values()):
            return False
        for mapping in record.rule.mappings:
            if any(isinstance(item, str) and len(item) > limits.max_payload_bytes for item in vars(mapping).values()):
                return False
        total += len(canonical(record.payload).encode('utf-8'))
        if total > limits.max_payload_bytes: return False
    for record in snapshot.relations:
        if any(isinstance(item, str) and len(item) > limits.max_payload_bytes
               for item in vars(record.relation).values()):
            return False
        total += len(canonical(record.payload).encode('utf-8'))
        if total > limits.max_payload_bytes: return False
    total += len(canonical([asdict(item) for item in snapshot.endpoints]).encode('utf-8'))
    return total <= limits.max_payload_bytes


def validate_relationship_graph(snapshot, *, limits=GraphLimits()):
    require(isinstance(snapshot, GraphSnapshot) and isinstance(limits, GraphLimits), 'GRAPH_TYPED_INPUT')
    for items, cap, code in ((snapshot.rules, limits.max_rules, 'GRAPH_RULE_LIMIT'),
                             (snapshot.relations, limits.max_relations, 'GRAPH_RELATION_LIMIT'),
                             (snapshot.endpoints, limits.max_endpoints, 'GRAPH_ENDPOINT_LIMIT')):
        if len(items) > cap:
            return GraphValidation('LIMIT_EXCEEDED', (GraphIssue(code, (), cap, len(items)),),
                                   None, 0, None, None, False, False, limits)
    if not _bounded_payload(snapshot, limits):
        return GraphValidation('LIMIT_EXCEEDED', (GraphIssue('GRAPH_PAYLOAD_LIMIT', (), limits.max_payload_bytes,
                                limits.max_payload_bytes + 1),), None, 0, None, None, False, False, limits)
    fingerprint = digest(dict(rules=sorted((r.key.id, r.key.version, r.content_hash) for r in snapshot.rules),
        relations=sorted((r.relation.relation_id, r.relation.revision, r.content_hash) for r in snapshot.relations),
        endpoints=sorted((f.endpoint.kind, f.endpoint.id, f.parent_task_id or '') for f in snapshot.endpoints),
        limits=asdict(limits)))
    snapshot = GraphSnapshot(tuple(sorted(snapshot.rules, key=lambda r:(r.key.id,r.key.version))),
        tuple(sorted(snapshot.relations, key=lambda r:(r.relation.relation_id,r.relation.revision))),
        tuple(sorted(snapshot.endpoints, key=lambda f:(f.endpoint.kind,f.endpoint.id,f.parent_task_id or ''))))
    issues = []; budget = _Budget(limits.max_traversal_work); generation_depth = instances = None
    counts_exact = True; completed = True
    try:
        seen = {}
        for collection, name, key in ((snapshot.rules, 'AMBIGUOUS_RULE_VERSION', lambda r:r.rule.rule_id),
                                     (snapshot.relations, 'AMBIGUOUS_RELATION_VERSION', lambda r:r.relation.relation_id),
                                     (snapshot.endpoints, 'AMBIGUOUS_ENDPOINT', lambda f:(f.endpoint.kind,f.endpoint.id))):
            seen.clear()
            for record in collection:
                ident = key(record); budget.visit(ident if isinstance(ident,str) else ident[1])
                if ident in seen:
                    issues.append(GraphIssue(name, (ident if isinstance(ident,str) else ident[1],)))
                seen[ident] = record
        if issues:
            return GraphValidation('INVALID', tuple(sorted(set(issues))), fingerprint, budget.used,
                                   None, None, False, True, limits)
        facts = {fact.endpoint:fact for fact in snapshot.endpoints}
        for fact in snapshot.endpoints:
            budget.visit(fact.endpoint.id)
            if fact.parent_task_id is not None and Endpoint('TASK',fact.parent_task_id) not in facts:
                issues.append(GraphIssue('UNRESOLVED_STAGE_OWNER',(fact.endpoint.id,fact.parent_task_id)))
        generation = [(r.source_type,r.target_type,r.rule.rule_id) for r in snapshot.rules if r.rule.active]
        cycles = _components(generation, budget)
        issues.extend(GraphIssue('RECURSIVE_GENERATION', ids) for ids in cycles)
        if not cycles:
            generation_depth, instances, limits_issues = _generation_bounds(generation, limits, budget)
            issues.extend(limits_issues)
            counts_exact = not any(i.code == 'GENERATION_INSTANCE_LIMIT' for i in limits_issues)
        else:
            counts_exact = False
        hard = [((f.endpoint.kind,f.endpoint.id,'START'),(f.endpoint.kind,f.endpoint.id,'FINISH'),None)
                for f in snapshot.endpoints]
        parents = {}; memberships = {}
        for record in snapshot.relations:
            r = record.relation; budget.visit(r.relation_id)
            if r.before not in facts or r.after not in facts:
                issues.append(GraphIssue('UNRESOLVED_ENDPOINT',(r.relation_id,))); continue
            for binding in (record.before,record.after):
                if binding.endpoint.kind == 'STAGE' and facts[binding.endpoint].parent_task_id != binding.task_id:
                    issues.append(GraphIssue('STAGE_OWNER_MISMATCH',(r.relation_id,)))
            if r.kind == 'STAGE_MEMBERSHIP':
                parents.setdefault(r.after,{}).setdefault(r.before,[]).append(r.relation_id)
                memberships.setdefault((r.before,r.after),[]).append(r.relation_id)
            elif r.kind in ('COMPLETION_ORDER','START_PREREQUISITE'):
                event = 'START' if r.kind == 'START_PREREQUISITE' else 'FINISH'
                hard.append(((r.before.kind,r.before.id,'FINISH'),(r.after.kind,r.after.id,event),r.relation_id))
        for values in parents.values():
            if len(values) > 1:
                issues.append(GraphIssue('MULTIPLE_STAGE_PARENTS',tuple(sorted(i for ids in values.values() for i in ids))))
        for ids in memberships.values():
            if len(ids) > 1: issues.append(GraphIssue('DUPLICATE_STAGE_MEMBERSHIP',tuple(sorted(ids))))
        issues.extend(GraphIssue('CONTRADICTORY_HARD_ORDER',ids) for ids in _components(hard,budget))
    except _WorkLimit as exc:
        issues.append(GraphIssue('GRAPH_TRAVERSAL_LIMIT', (exc.identity,) if exc.identity else (),
                                 limits.max_traversal_work, limits.max_traversal_work + 1))
        completed = False; counts_exact = False
    issues = tuple(sorted(set(issues)))
    limited = any(issue.limit > 0 for issue in issues)
    status = 'LIMIT_EXCEEDED' if limited else 'INVALID' if issues else 'VALID'
    return GraphValidation(status, issues, fingerprint, budget.used, generation_depth, instances,
                           counts_exact, completed, limits)
