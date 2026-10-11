"""Independent event-closure and cascade-enumeration oracles for the runtime gate."""
from collections import deque
from dataclasses import replace
import random
import unittest

from src.application.definitions import DefinitionKey
from src.application.relationship_storage import EndpointBinding, RelationStorageRecord, RuleStorageRecord
from src.application.relationship_validation import (EndpointFact, GraphSnapshot, GraphLimits,
    RelationshipGraphError, validate_relationship_graph)
from src.domain.relationships import Endpoint, RelationshipRule, TaskRelation, literal


def rule(id, source='a-type', target='b-type', *, version='1', source_version='1', target_version='1', active=True, obligation='SEPARATE_TASK'):
    r=RelationshipRule(id,version,active,'synthetic-acceptance-'+id,'CANONICAL_CREATION',source,target,
        'synthetic-template','1','counterpart',obligation,('title','completion','disposition'),
        (literal('title','Synthetic counterpart'),literal('completion','INCOMPLETE'),literal('disposition','ACTIVE')))
    return RuleStorageRecord(r,DefinitionKey('TASKTYPE',source,source_version),
        DefinitionKey('TASKTYPE',target,target_version),DefinitionKey('TASK_TEMPLATE','synthetic-template','1'))


A,B,C=(Endpoint('TASK',name) for name in ('a','b','c'))
FACTS=tuple(EndpointFact(e) for e in (A,B,C))


def link(id, kind='COMPLETION_ORDER', before=A, after=B, *, revision=1, before_owner=None, after_owner=None):
    r=TaskRelation(id,revision,kind,before,after,'synthetic-link-acceptance-'+id)
    def bind(endpoint,owner):
        return EndpointBinding(endpoint,owner or endpoint.id,1,1 if endpoint.kind=='STAGE' else None)
    return RelationStorageRecord(r,bind(before,before_owner),bind(after,after_owner))


def check(rules=(),relations=(),facts=FACTS,limits=None):
    return validate_relationship_graph(GraphSnapshot(tuple(rules),tuple(relations),tuple(facts)),
                                       limits=limits or GraphLimits())


def cyclic_ids(edges):
    """Small independent oracle: Floyd-Warshall, not the service's SCC walk."""
    nodes=sorted({n for edge in edges for n in edge[:2]});reachable={(n,n):True for n in nodes}
    for before,after,ident in edges:reachable[before,after]=True
    for middle in nodes:
        for before in nodes:
            for after in nodes:
                if reachable.get((before,middle)) and reachable.get((middle,after)):reachable[before,after]=True
    groups=set()
    for before,after,ident in edges:
        if ident is not None and reachable.get((after,before)):
            group=frozenset(n for n in nodes if reachable.get((before,n)) and reachable.get((n,before)))
            groups.add(group)
    return tuple(sorted(tuple(sorted(ident for before,after,ident in edges if ident is not None and before in group and after in group)) for group in groups))


class RelationshipValidationTests(unittest.TestCase):
    def test_reversed_generation_and_both_order_kinds_are_valid(self):
        for kind in ('COMPLETION_ORDER','START_PREREQUISITE'):
            result=check((rule('generate'),),(link('before',kind,B,A),))
            self.assertTrue(result.valid);self.assertEqual((result.generation_depth,result.generated_instances),(1,1))

    def test_unrelated_rules_are_excluded_from_generation_cycle_diagnostic(self):
        result=check((rule('forward'),rule('reverse','b-type','a-type'),rule('unrelated','x','y')))
        self.assertEqual([(i.code,i.identities) for i in result.issues],[('RECURSIVE_GENERATION',('forward','reverse'))])
        self.assertFalse(result.valid);self.assertIsNone(result.generated_instances)

    def test_inactive_recursive_rule_does_not_generate_an_edge(self):
        self.assertTrue(check((rule('inactive','same','same',active=False),)).valid)
        result=check((rule('active','same','same'),))
        self.assertEqual(result.issues[0].identities,('active',))

    def test_hard_cycle_reports_only_involved_links(self):
        result=check(relations=(link('finish','COMPLETION_ORDER',A,B),link('start','START_PREREQUISITE',B,A),link('unrelated','COMPLETION_ORDER',B,C)))
        self.assertEqual(result.issues[0].code,'CONTRADICTORY_HARD_ORDER')
        self.assertEqual(result.issues[0].identities,('finish','start'))

    def test_both_cycle_categories_are_reported_separately(self):
        result=check((rule('gen-a'),rule('gen-b','b-type','a-type')),
                     (link('hard-a',before=A,after=B),link('hard-b',before=B,after=A)))
        self.assertEqual({i.code for i in result.issues},{'RECURSIVE_GENERATION','CONTRADICTORY_HARD_ORDER'})

    def test_soft_cycles_do_not_become_hard_constraints(self):
        result=check(relations=(link('hard','START_PREREQUISITE',A,B),link('soft','SOFT_SEQUENCE',B,A)))
        self.assertTrue(result.valid)
        self.assertTrue(check(relations=(link('one','SOFT_SEQUENCE',A,B),link('two','SOFT_SEQUENCE',B,A))).valid)

    def test_membership_does_not_imply_finish_or_start_order(self):
        stage=Endpoint('STAGE','stage');facts=FACTS+(EndpointFact(stage,'a'),)
        result=check(relations=(link('membership','STAGE_MEMBERSHIP',A,stage,after_owner='a'),
                               link('reverse','START_PREREQUISITE',stage,A,before_owner='a')),facts=facts)
        self.assertTrue(result.valid)

    def test_unresolved_endpoint_is_not_created_or_assumed(self):
        result=check(relations=(link('missing',after=Endpoint('TASK','unknown')),))
        self.assertEqual(result.issues[0].identities,('missing',));self.assertEqual(result.issues[0].code,'UNRESOLVED_ENDPOINT')

    def test_multiple_stage_parents_report_all_involved_memberships(self):
        stage=Endpoint('STAGE','stage');facts=FACTS+(EndpointFact(stage,'a'),)
        result=check(relations=(link('member-a','STAGE_MEMBERSHIP',A,stage,after_owner='a'),
                               link('member-b','STAGE_MEMBERSHIP',B,stage,after_owner='b')),facts=facts)
        self.assertIn(('MULTIPLE_STAGE_PARENTS',('member-a','member-b')),[(i.code,i.identities) for i in result.issues])
        self.assertIn(('STAGE_OWNER_MISMATCH',('member-b',)),[(i.code,i.identities) for i in result.issues])

    def test_duplicate_membership_does_not_masquerade_as_two_parents(self):
        stage=Endpoint('STAGE','stage');facts=FACTS+(EndpointFact(stage,'a'),)
        result=check(relations=(link('one','STAGE_MEMBERSHIP',A,stage,after_owner='a'),link('two','STAGE_MEMBERSHIP',A,stage,after_owner='a')),facts=facts)
        self.assertEqual([(i.code,i.identities) for i in result.issues],[('DUPLICATE_STAGE_MEMBERSHIP',('one','two'))])

    def test_stage_owner_must_resolve_in_the_same_registry(self):
        result=check(facts=(EndpointFact(Endpoint('STAGE','stage'),'missing-parent'),))
        self.assertEqual(result.issues[0].code,'UNRESOLVED_STAGE_OWNER')

    def test_task_and_stage_with_same_text_id_remain_distinct(self):
        stage=Endpoint('STAGE','a');facts=FACTS+(EndpointFact(stage,'a'),)
        self.assertTrue(check(relations=(link('membership','STAGE_MEMBERSHIP',A,stage,after_owner='a'),),facts=facts).valid)

    def test_generation_type_versions_are_not_collapsed(self):
        rules=(rule('one','a-type','b-type',target_version='1'),rule('two','b-type','a-type',source_version='2'))
        self.assertTrue(check(rules).valid)
        self.assertFalse(check((rules[0],rule('two','b-type','a-type'))).valid)

    def test_rule_version_edit_does_not_invalidate_old_link_origin(self):
        old=link('old',before=B,after=A)
        old=replace(old,relation=replace(old.relation,origin_rule_id='generate',origin_rule_version='1'))
        self.assertTrue(check((rule('generate',version='2',active=False),),(old,)).valid)

    def test_unselected_duplicate_versions_are_rejected_without_highest_version_guess(self):
        result=check((rule('same',version='1'),rule('same',version='2')))
        self.assertEqual(result.issues[0].code,'AMBIGUOUS_RULE_VERSION')
        result=check(relations=(link('same'),link('same',revision=2)))
        self.assertEqual(result.issues[0].code,'AMBIGUOUS_RELATION_VERSION')

    def test_duplicate_endpoint_facts_are_rejected(self):
        self.assertEqual(check(facts=FACTS+(FACTS[0],)).issues[0].code,'AMBIGUOUS_ENDPOINT')

    def test_chain_depth_has_exact_boundary_and_offending_path(self):
        rules=tuple(rule('r'+str(i),'type'+str(i),'type'+str(i+1)) for i in range(4))
        self.assertTrue(check(rules,limits=GraphLimits(max_generation_depth=4)).valid)
        result=check(rules,limits=GraphLimits(max_generation_depth=3))
        self.assertEqual(result.status,'LIMIT_EXCEEDED');issue=result.issues[0]
        self.assertEqual((issue.code,issue.identities,issue.limit,issue.observed_lower_bound),('GENERATION_DEPTH_LIMIT',('r0','r1','r2','r3'),3,4))

    def test_long_finite_chain_is_iterative_under_explicit_large_limit(self):
        rules=tuple(rule('r'+str(i),'t'+str(i),'t'+str(i+1)) for i in range(1200))
        result=check(rules,facts=(),limits=GraphLimits(max_generation_depth=1200,max_generated_instances=1200))
        self.assertTrue(result.valid);self.assertEqual((result.generation_depth,result.generated_instances),(1200,1200))

    def test_converging_generation_paths_count_separate_source_occurrences(self):
        rules=(rule('ab','a','b'),rule('ac','a','c'),rule('bd','b','d'),rule('cd','c','d'))
        result=check(rules,limits=GraphLimits(max_generated_instances=4))
        self.assertTrue(result.valid);self.assertEqual(result.generated_instances,4)
        result=check(rules,limits=GraphLimits(max_generated_instances=3))
        self.assertFalse(result.generation_counts_exact);self.assertEqual(result.generated_instances,4)
        self.assertEqual(result.issues[0].observed_lower_bound,4)

    def test_parallel_rules_count_own_targets_and_stages_do_not_add_effort(self):
        result=check((rule('one'),rule('two',obligation='STAGE')))
        self.assertEqual(result.generated_instances,2);self.assertTrue(result.valid)

    def test_branching_cascade_is_saturated_without_enumerating_instances(self):
        rules=[]
        for i in range(31):
            for role in ('left','right'):rules.append(rule(role+str(i),'t'+str(i),'t'+str(i+1)))
        result=check(rules,limits=GraphLimits(max_generated_instances=1000))
        self.assertEqual(result.status,'LIMIT_EXCEEDED');self.assertEqual(result.generated_instances,1001)
        self.assertFalse(result.generation_counts_exact);self.assertLess(result.traversal_work,10000)

    def test_count_limits_fail_before_fingerprinting_or_traversing(self):
        cases=((dict(rules=(rule('one'),rule('two'))),GraphLimits(max_rules=1),'GRAPH_RULE_LIMIT'),
               (dict(relations=(link('one'),link('two'))),GraphLimits(max_relations=1),'GRAPH_RELATION_LIMIT'),
               ({},GraphLimits(max_endpoints=1),'GRAPH_ENDPOINT_LIMIT'))
        for args,limits,code in cases:
            with self.subTest(code=code):
                result=check(**args,limits=limits);self.assertEqual(result.issues[0].code,code)
                self.assertEqual(result.traversal_work,0);self.assertIsNone(result.input_hash)

    def test_payload_limit_and_large_literal_fail_without_authority_or_writes(self):
        result=check((rule('one'),),limits=GraphLimits(max_payload_bytes=100))
        self.assertEqual(result.issues[0].code,'GRAPH_PAYLOAD_LIMIT')
        self.assertFalse(result.complete)

    def test_traversal_budget_is_exact_and_cannot_certify_partial_graph(self):
        result=check((rule('one'),),(link('link'),),limits=GraphLimits(max_traversal_work=5))
        self.assertEqual(result.status,'LIMIT_EXCEEDED');self.assertEqual(result.traversal_work,5)
        self.assertFalse(result.complete);self.assertFalse(result.valid)
        self.assertEqual(result.issues[-1].observed_lower_bound,6)

    def test_limits_reject_zero_negative_boolean_and_unbounded_values(self):
        for value in (0,-1,True,10000001):
            with self.subTest(value=value),self.assertRaises(RelationshipGraphError):GraphLimits(max_traversal_work=value)

    def test_snapshot_requires_immutable_typed_values(self):
        with self.assertRaises(RelationshipGraphError):GraphSnapshot([],(),())
        with self.assertRaises(RelationshipGraphError):GraphSnapshot(('rule',),(),())
        with self.assertRaises(RelationshipGraphError):EndpointFact(Endpoint('STAGE','stage'))

    def test_diagnostics_fingerprint_and_limit_result_are_order_independent(self):
        rules=(rule('one'),rule('two','b-type','a-type'))
        links=(link('one'),link('two',before=B,after=A))
        for limits in (GraphLimits(),GraphLimits(max_traversal_work=6)):
            first=check(rules,links,limits=limits)
            second=check(tuple(reversed(rules)),tuple(reversed(links)),tuple(reversed(FACTS)),limits=limits)
            self.assertEqual(first,second)

    def test_fingerprint_pins_versions_ownership_and_budgets_without_mutation(self):
        r=rule('one');before=r.payload;first=check((r,));second=check((rule('one',version='2'),))
        self.assertNotEqual(first.input_hash,second.input_hash)
        self.assertNotEqual(first.input_hash,check((r,),limits=GraphLimits(max_generation_depth=33)).input_hash)
        self.assertEqual(r.payload,before)

    def test_random_event_graphs_match_independent_temporal_closure(self):
        rng=random.Random(20261010)
        for case in range(60):
            links=tuple(link('r'+str(i),rng.choice(('COMPLETION_ORDER','START_PREREQUISITE','SOFT_SEQUENCE')),rng.choice((A,B,C)),rng.choice((A,B,C))) for i in range(rng.randrange(1,12)))
            edges=[((e.id,'START'),(e.id,'FINISH'),None) for e in (A,B,C)]
            for record in links:
                v=record.relation
                if v.kind!='SOFT_SEQUENCE':edges.append(((v.before.id,'FINISH'),(v.after.id,'START' if v.kind=='START_PREREQUISITE' else 'FINISH'),v.relation_id))
            actual=tuple(i.identities for i in check(relations=links).issues if i.code=='CONTRADICTORY_HARD_ORDER')
            with self.subTest(case=case):self.assertEqual(actual,cyclic_ids(edges))

    def test_random_generation_graphs_match_independent_type_closure(self):
        rng=random.Random(72)
        for case in range(60):
            rules=tuple(rule('r'+str(i),rng.choice(('a','b','c')),rng.choice(('a','b','c')),active=rng.choice((True,True,False))) for i in range(8))
            edges=[(r.source_type.id,r.target_type.id,r.rule.rule_id) for r in rules if r.rule.active]
            actual=tuple(i.identities for i in check(rules).issues if i.code=='RECURSIVE_GENERATION')
            with self.subTest(case=case):self.assertEqual(actual,cyclic_ids(edges))

    def test_small_dags_match_explicit_occurrence_enumeration(self):
        rng=random.Random(73)
        for case in range(30):
            pairs=[(str(a),str(b)) for a in range(5) for b in range(a+1,5) if rng.randrange(2)]
            rules=tuple(rule('r'+str(i),a,b) for i,(a,b) in enumerate(pairs));expected=0
            for root in map(str,range(5)):
                pending=deque([root]);count=0
                while pending:
                    node=pending.popleft()
                    for before,after in pairs:
                        if before==node:count+=1;pending.append(after)
                expected=max(expected,count)
            with self.subTest(case=case):self.assertEqual(check(rules).generated_instances,expected)


if __name__=='__main__':unittest.main()
