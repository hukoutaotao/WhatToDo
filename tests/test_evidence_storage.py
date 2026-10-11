"""Evidence values retain original facts without claiming Task authority."""
from dataclasses import replace
from datetime import datetime,timedelta,timezone
from decimal import Decimal,localcontext
import json
from pathlib import Path
import unittest

from src.adapters.contract_json import ContractJSONCodec
from src.adapters.postgres_evidence import PostgresEvidenceRepository
from src.application.evidence_storage import (EvidenceError,SourceScope,EvidenceObservation,
    admit_source,admit_candidate,canonical,strict_json,conflict_id,pending_id)
from src.domain.provenance import capture_source,make_candidate,mark_source_deleted
from tools.check_contract_registry import trusted_schemas

NOW=datetime(2026,1,1,tzinfo=timezone.utc)


class EvidenceStorageTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.codec=ContractJSONCodec(trusted_schemas())

    def source(self,scope='scope-a',content=b'synthetic content'):
        return capture_source(provider='synthetic-provider',scope_ref=scope,external_id='same-id',
            raw_bytes=content,captured_at=NOW,source_type='OTHER')

    def wire(self,value):return json.dumps(value,ensure_ascii=False,indent=2).encode()

    def candidate(self):
        return make_candidate(self.source(),parser_version='parser-1',action='CREATE_TASK',
            proposed_fields=dict(title='Synthetic work',remaining_seconds=9007199254740993),confidence='0.8')

    def test_source_roundtrip_retains_wire_unknown_timestamp_and_original_content_hash(self):
        source=self.source(); raw=self.wire(source.as_record()); result=admit_source(self.codec,raw)
        self.assertEqual(result.source,source);self.assertEqual(result.raw_wire,raw)
        self.assertIsNone(result.source.source_timestamp)
        self.assertEqual(result.source.content_hash,source.content_hash)

    def test_capture_replay_does_not_change_semantic_source_version(self):
        source=self.source(); first=admit_source(self.codec,self.wire(source.as_record()))
        later=replace(source,captured_at=NOW+timedelta(hours=1))
        second=admit_source(self.codec,self.wire(later.as_record()))
        self.assertEqual(first.semantic_hash,second.semantic_hash)
        self.assertNotEqual(first.wire_hash,second.wire_hash)
        self.assertNotEqual(first.source.captured_at,second.source.captured_at)

    def test_two_scopes_and_changed_source_content_or_revision_stay_distinct(self):
        first=self.source(); other=self.source('scope-b'); changed=self.source(content=b'changed')
        self.assertNotEqual(first.source_id,other.source_id)
        self.assertEqual(first.source_id,changed.source_id)
        self.assertNotEqual(first.record_id,changed.record_id)
        revision=replace(first,external_revision='new-revision')
        self.assertNotEqual(admit_source(self.codec,self.wire(first.as_record())).semantic_hash,
            admit_source(self.codec,self.wire(revision.as_record())).semantic_hash)

    def test_tombstone_preserves_content_and_original_capture_time(self):
        source=self.source(); deleted=mark_source_deleted(source,NOW+timedelta(days=1))
        value=admit_source(self.codec,self.wire(deleted.as_record()))
        self.assertEqual(value.source.content_hash,source.content_hash)
        self.assertEqual(value.source.captured_at,source.captured_at)
        self.assertNotEqual(value.source.record_id,source.record_id)
        self.assertEqual(value.source.state,'DELETED')

    def test_candidate_proposals_preserve_large_integers_and_exact_decimal_confidence(self):
        raw=self.wire(self.candidate().as_record()).replace(b'"confidence": 0.8',
            b'"confidence": 0.812345678901234567890123456789')
        with localcontext() as context:
            context.prec=6
            value=admit_candidate(self.codec,raw,pending_only=True)
            self.assertEqual(value.candidate.confidence,Decimal('0.812345678901234567890123456789'))
            self.assertEqual(value.fields['remaining_seconds'],9007199254740993)
            digest=value.proposal_hash
        self.assertEqual(value.proposal_hash,digest)
        self.assertEqual(value.raw_wire,raw)

    def test_replay_fingerprint_excludes_capture_time_and_review_but_not_facts(self):
        value=self.candidate().as_record(); first=admit_candidate(self.codec,self.wire(value))
        value['created_at']=(NOW+timedelta(hours=1)).isoformat()
        later=admit_candidate(self.codec,self.wire(value))
        self.assertEqual(first.proposal_hash,later.proposal_hash)
        value['proposed_fields']['title']='Changed parse'
        self.assertNotEqual(first.proposal_hash,admit_candidate(self.codec,self.wire(value)).proposal_hash)

    def test_ingestion_cannot_mint_review_authority_even_with_supported_review_shape(self):
        value=self.candidate().as_record()
        value['review']=dict(state='CONFIRMED',authority_ref='synthetic-authority',
            reviewed_at=NOW.isoformat(),canonical_task_id='synthetic-task')
        self.assertEqual(admit_candidate(self.codec,self.wire(value)).candidate.review_state,'CONFIRMED')
        with self.assertRaisesRegex(EvidenceError,'EVIDENCE_INGEST_PENDING_ONLY'):
            admit_candidate(self.codec,self.wire(value),pending_only=True)

    def test_invalid_wire_control_fields_versions_and_nan_fail_admission(self):
        for mutate in [lambda v:v.update(schema_version='future'),
            lambda v:v['proposed_fields'].update(authority_ref='fake'),
            lambda v:v.update(confidence=True)]:
            value=self.candidate().as_record();mutate(value)
            with self.assertRaises(EvidenceError):admit_candidate(self.codec,self.wire(value))
        with self.assertRaises(EvidenceError):admit_source(self.codec,b'{"x":NaN}')
        with self.assertRaises(EvidenceError):admit_source(self.codec,b'x'*1048577)

    def test_finer_timestamp_precision_is_rejected_instead_of_silently_truncated(self):
        value=self.source().as_record();value['captured_at']='2026-01-01T00:00:00.0000001Z'
        with self.assertRaisesRegex(EvidenceError,'EVIDENCE_SOURCE_SEMANTICS'):
            admit_source(self.codec,self.wire(value))

    def test_decimal_canonicalization_preserves_digits_and_rejects_nonfinite_numbers(self):
        with localcontext() as context:
            context.prec=3
            value=Decimal('0.12345678901234567890123456789')
            self.assertEqual(strict_json(canonical(value)),value)
            self.assertEqual(canonical(Decimal('0.8000')),canonical(Decimal('0.8')))
        for value in [Decimal('NaN'),Decimal('Infinity'),float('inf')]:
            with self.assertRaises(EvidenceError):canonical(value)
        with self.assertRaisesRegex(EvidenceError,'EVIDENCE_DUPLICATE_JSON_KEY'):
            strict_json(b'{"a":1,"a":2}')

    def test_scope_registry_is_explicit_unique_and_immutable(self):
        scope=SourceScope('synthetic-provider','scope-a','synthetic-account')
        for value in ['', 'x'*201,'bad\x00scope']:
            with self.assertRaises(EvidenceError):SourceScope('provider',value,'account')
        for scopes in [[scope],(scope,scope)]:
            with self.assertRaisesRegex(EvidenceError,'EVIDENCE_TRUSTED_SCOPE_REGISTRY'):
                PostgresEvidenceRepository(None,self.codec,None,application_version='test',clock=None,scopes=scopes)
        empty=PostgresEvidenceRepository(None,self.codec,None,application_version='test',clock=None)
        self.assertEqual(empty.pending_items(),())

    def test_conflict_and_pending_identities_are_stable_and_result_is_not_approval(self):
        a=conflict_id('CANDIDATE','candidate','a'*64,'b'*64)
        self.assertEqual(a,conflict_id('CANDIDATE','candidate','a'*64,'b'*64))
        self.assertNotEqual(a,conflict_id('CANDIDATE','candidate','a'*64,'c'*64))
        self.assertNotEqual(pending_id('CANDIDATE','same'),pending_id('CONFLICT','same'))
        value=admit_source(self.codec,self.wire(self.source().as_record()))
        result=EvidenceObservation('INSERTED',value)
        with self.assertRaises(TypeError):bool(result)
        self.assertNotIn('synthetic content',repr(value))


if __name__=='__main__':unittest.main()
