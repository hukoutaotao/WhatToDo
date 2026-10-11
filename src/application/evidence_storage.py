"""Admitted immutable evidence; proposals carry no canonical write authority."""
from dataclasses import dataclass, field
from datetime import timezone
from decimal import Decimal
from hashlib import sha256
import json

from src.domain.provenance import SourceRecord, Candidate
from src.domain.task_aggregate import instant


class EvidenceError(RuntimeError):
    pass


def require(value, code):
    if not value:
        raise EvidenceError(code)


def identity(value):
    require(isinstance(value, str) and value.strip() and len(value)<=200 and '\x00' not in value,
        'EVIDENCE_IDENTITY')


def canonical(value):
    """Exact finite decimal/integer JSON; no float roundtrip for confidence."""
    if value is None: return 'null'
    if value is True: return 'true'
    if value is False: return 'false'
    if isinstance(value, str): return json.dumps(value, ensure_ascii=True)
    if type(value) is int: return str(value)
    if isinstance(value, (Decimal, float)):
        number = value if isinstance(value, Decimal) else Decimal(str(value))
        require(number.is_finite(), 'EVIDENCE_FINITE_NUMBER')
        if number == 0: return '0'
        # normalize() uses the ambient Decimal precision; preserve all digits.
        sign, digits, exponent = number.as_tuple()
        digits = list(digits)
        while digits[-1] == 0:
            digits.pop(); exponent += 1
        return ('-' if sign else '') + ''.join(map(str,digits)) + 'e' + str(exponent)
    if isinstance(value, list): return '['+','.join(canonical(v) for v in value)+']'
    if isinstance(value, dict):
        require(all(isinstance(k,str) for k in value), 'EVIDENCE_JSON_KEYS')
        return '{'+','.join(canonical(k)+':'+canonical(value[k]) for k in sorted(value))+'}'
    raise EvidenceError('EVIDENCE_JSON_VALUE')


def digest(value):
    return sha256(canonical(value).encode()).hexdigest()


def strict_json(raw):
    def pairs(values):
        result={}
        for key,value in values:
            require(key not in result,'EVIDENCE_DUPLICATE_JSON_KEY'); result[key]=value
        return result
    def invalid(value): raise EvidenceError('EVIDENCE_FINITE_NUMBER')
    return json.loads(raw, object_pairs_hook=pairs, parse_float=Decimal, parse_constant=invalid)


@dataclass(frozen=True)
class SourceScope:
    provider: str
    scope_ref: str
    account_ref: str

    def __post_init__(self):
        for value in (self.provider,self.scope_ref,self.account_ref): identity(value)


@dataclass(frozen=True)
class SourceEvidence:
    raw_wire: bytes = field(repr=False)
    source: SourceRecord = field(repr=False)

    @property
    def wire_hash(self): return sha256(self.raw_wire).hexdigest()

    @property
    def semantic_hash(self):
        value=self.source.as_record(); value.pop('captured_at')
        for key in ('source_timestamp','deleted_at'):
            if value[key] is not None:
                value[key]=instant(value[key]).astimezone(timezone.utc).isoformat()
        return digest(value)


def admit_source(codec,raw):
    require(isinstance(raw,bytes) and 0<len(raw)<=1048576,'EVIDENCE_WIRE_SIZE')
    admission=codec.admit('source',raw)
    require(admission.status=='SUPPORTED_SHAPE','EVIDENCE_SOURCE_ADMISSION')
    value=admission.payload.copy(); value.pop('schema_version')
    try:
        for key in ('source_timestamp','captured_at','deleted_at'):
            if value[key] is not None: value[key]=instant(value[key])
        source=SourceRecord(**value)
    except (ValueError,TypeError): raise EvidenceError('EVIDENCE_SOURCE_SEMANTICS') from None
    return SourceEvidence(raw,source)


@dataclass(frozen=True)
class CandidateEvidence:
    raw_wire: bytes = field(repr=False)
    candidate: Candidate = field(repr=False)

    @property
    def wire_hash(self): return sha256(self.raw_wire).hexdigest()

    @property
    def proposal_hash(self):
        c=self.candidate
        return digest([c.source_id,c.source_record_id,c.source_hash,c.parser_version,
            c.action,c.target_task_id,c.target_revision,strict_json(c.proposed_fields_json),c.confidence])

    @property
    def fields(self): return strict_json(self.candidate.proposed_fields_json)


def admit_candidate(codec,raw,*,pending_only=False):
    require(isinstance(raw,bytes) and 0<len(raw)<=1048576,'EVIDENCE_WIRE_SIZE')
    admission=codec.admit('candidate',raw)
    require(admission.status=='SUPPORTED_SHAPE','EVIDENCE_CANDIDATE_ADMISSION')
    value=strict_json(raw); source=value['source_ref']; target=value['target_ref']; review=value['review']
    try:
        candidate=Candidate(value['candidate_id'],source['source_id'],source['record_id'],
            source['content_hash'],value['parser_version'],value['action'],
            target['task_id'] if target else None,target['revision'] if target else None,
            canonical(value['proposed_fields']),Decimal(value['confidence']),instant(value['created_at']),
            review['state'],review['authority_ref'],
            instant(review['reviewed_at']) if review['reviewed_at'] is not None else None,
            review['canonical_task_id'])
    except (ValueError,TypeError): raise EvidenceError('EVIDENCE_CANDIDATE_SEMANTICS') from None
    require(not pending_only or candidate.review_state=='PENDING','EVIDENCE_INGEST_PENDING_ONLY')
    return CandidateEvidence(raw,candidate)


@dataclass(frozen=True)
class EvidenceObservation:
    outcome: str
    stored: SourceEvidence | CandidateEvidence = field(repr=False)
    revision: int = 1
    conflict_id: str | None = None

    def __post_init__(self):
        require(self.outcome in ('INSERTED','REPLAY','CONFLICT'),'EVIDENCE_OBSERVATION_OUTCOME')
        require((self.outcome=='CONFLICT')==(self.conflict_id is not None),
            'EVIDENCE_OBSERVATION_CONFLICT')

    def __bool__(self):
        raise TypeError('Inspect observation outcome; evidence is not authority')


def pending_id(kind,target_id): return 'pending-'+digest([kind,target_id])


def conflict_id(kind,target_id,expected_hash,observed_hash):
    return 'conflict-'+digest([kind,target_id,expected_hash,observed_hash])
