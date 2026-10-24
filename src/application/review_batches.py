"""Scoped unchanged-estimate batch confirmation; verification never mutates U.

The SQL handler must independently resolve caller authority, current Tasks,
actual-work evidence and prior verifications, then call this builder inside its
transaction. A journal or verification reconstructed from stored JSON never
authorizes a second confirmation. Silence confirms none: a batch without an
explicit confirmed flag records no member verification.
"""
from base64 import b64decode, b64encode
from dataclasses import asdict, dataclass, field
from datetime import datetime
from hashlib import sha256
import re

from src.application.definitions import canonical, identity, strict_json
from src.application.ports import AggregateKey, CommitReceipt, CommitRequest, RecordWrite, RequestContext
from src.application.task_storage import TaskStorageRecord
from src.application.transactions import require
from src.domain.authorization import CallerIdentity
from src.domain.task_aggregate import instant

VERSION='0.1.0-review-batch'
JOURNAL_VERSION='0.1.0-review-batch-journal'
MAX_REVISION=9223372036854775807
MAX_MEMBERS=100
MAX_RAW_BYTES=262144
MAX_JOURNAL_BYTES=16777216


def digest(value):
    return sha256(canonical(value).encode()).hexdigest()


@dataclass(frozen=True)
class BatchMember:
    task_id: str
    expected_revision: int
    observation_id: str
    seconds: int

    def __post_init__(self):
        require(all(identity(v) for v in (self.task_id,self.observation_id)),'REVIEW_BATCH_MEMBER_IDENTITY')
        require(type(self.expected_revision) is int and 0<self.expected_revision<=MAX_REVISION
            and type(self.seconds) is int and 0<=self.seconds<=MAX_REVISION,'REVIEW_BATCH_MEMBER_VALUES')
    def as_record(self):
        return dict(task_id=self.task_id,revision=self.expected_revision,observation_id=self.observation_id,seconds=self.seconds)


@dataclass(frozen=True)
class ReviewBatchCommand:
    command_id: str
    principal_id: str
    authority_ref: str
    review_id: str
    frame_revision: int
    user_statement_ref: str
    batch_id: str
    confirmed: bool | None
    members: tuple[BatchMember,...]
    no_work_statement: bool | None = None

    def __post_init__(self):
        require(all(identity(v) for v in (self.command_id,self.principal_id,self.authority_ref,self.review_id,
            self.user_statement_ref,self.batch_id)),'REVIEW_BATCH_IDENTITY')
        require(type(self.frame_revision) is int and 0<self.frame_revision<=MAX_REVISION,'REVIEW_BATCH_FRAME')
        require(self.confirmed is None or type(self.confirmed) is bool
            and (self.no_work_statement is None or type(self.no_work_statement) is bool),'REVIEW_BATCH_FLAGS')
        require(isinstance(self.members,tuple) and self.members and len(self.members)<=MAX_MEMBERS
            and all(isinstance(m,BatchMember) for m in self.members),'REVIEW_BATCH_MEMBERS')
        require(len({m.task_id for m in self.members})==len(self.members),'REVIEW_BATCH_DUPLICATE_MEMBER')
        object.__setattr__(self,'members',tuple(sorted(self.members,key=lambda m:m.task_id)))

    @property
    def review(self):
        return dict(review_id=self.review_id,frame_revision=self.frame_revision,user_statement_ref=self.user_statement_ref)
    def as_record(self):
        return dict(schema_version=VERSION,command_id=self.command_id,principal_id=self.principal_id,origin='USER_COMMAND',
            authority_ref=self.authority_ref,review_ref=self.review,batch_id=self.batch_id,confirmed=self.confirmed,
            no_work_statement=self.no_work_statement,members=[m.as_record() for m in self.members])
    @property
    def fingerprint(self):return digest(self.as_record())


def admit_review_batch(codec,raw):
    require(isinstance(raw,bytes) and 0<len(raw)<=MAX_RAW_BYTES,'REVIEW_BATCH_SIZE')
    admission=codec.admit('review-batch',raw)
    require(admission.status=='SUPPORTED_SHAPE','REVIEW_BATCH_SHAPE_UNSUPPORTED')
    v=admission.payload;r=v['review_ref']
    members=tuple(BatchMember(m['task_id'],m['revision'],m['observation_id'],m['seconds']) for m in v['members'])
    return ReviewBatchCommand(v['command_id'],v['principal_id'],v['authority_ref'],r['review_id'],r['frame_revision'],
        r['user_statement_ref'],v['batch_id'],v['confirmed'],members,v['no_work_statement'])


@dataclass(frozen=True)
class ReviewBatchGrant:
    command: ReviewBatchCommand = field(repr=False)
    evidence_ref: str
    issued_at: datetime
    source_observed_at: datetime
    expires_at: datetime | None = None
    active: bool = True

    def __post_init__(self):
        require(isinstance(self.command,ReviewBatchCommand) and identity(self.evidence_ref)
            and type(self.active) is bool,'REVIEW_BATCH_TYPED_GRANT')
        require(all(isinstance(t,datetime) and t.utcoffset() is not None for t in (self.issued_at,self.source_observed_at))
            and (self.expires_at is None or isinstance(self.expires_at,datetime) and self.expires_at.utcoffset() is not None
                and self.issued_at<self.expires_at),'REVIEW_BATCH_GRANT_TIME')

    def as_record(self):
        return dict(contract='review-batch',command=self.command.as_record(),active=self.active,
            source_observed_at=self.source_observed_at.isoformat())


@dataclass(frozen=True)
class BatchTaskEvidence:
    record: TaskStorageRecord = field(repr=False)
    work_status: str
    last_positive_work_at: datetime | None = None
    prior_verification_id: str | None = None
    prior_batch_record_id: str | None = None

    def __post_init__(self):
        require(isinstance(self.record,TaskStorageRecord),'REVIEW_BATCH_TYPED_EVIDENCE')
        require(self.work_status in ('UNTOUCHED','WORKED','UNKNOWN'),'REVIEW_BATCH_WORK_STATUS')
        require(self.last_positive_work_at is None or isinstance(self.last_positive_work_at,datetime)
            and self.last_positive_work_at.utcoffset() is not None,'REVIEW_BATCH_WORK_TIME')
        require((self.prior_verification_id is None)==(self.prior_batch_record_id is None),'REVIEW_BATCH_PRIOR_VERIFICATION')
        for v in (self.prior_verification_id,self.prior_batch_record_id):
            require(v is None or identity(v),'REVIEW_BATCH_PRIOR_VERIFICATION')


def validate_batch_grant(command,grant,*,now):
    require(isinstance(command,ReviewBatchCommand) and isinstance(grant,ReviewBatchGrant),'REVIEW_BATCH_INDEPENDENT_GRANT')
    require(grant.command.fingerprint==command.fingerprint,'REVIEW_BATCH_EXACT_SCOPE_MISMATCH')
    require(grant.active and grant.issued_at<=now and (grant.expires_at is None or now<grant.expires_at),'REVIEW_BATCH_INACTIVE_AUTHORITY')
    require(grant.source_observed_at<=now,'REVIEW_BATCH_FUTURE_OBSERVATION')


@dataclass(frozen=True)
class BatchVerificationRecord:
    verification_id: str
    task_id: str
    task_revision: int
    batch_record_id: str
    observation_id: str
    seconds: int
    observed_at: str
    verified_at: str
    no_work_statement: bool | None

    def __post_init__(self):
        require(all(identity(v) for v in (self.verification_id,self.task_id,self.observation_id,self.batch_record_id))
            and re.fullmatch('verification-[a-f0-9]{64}',self.verification_id) is not None
            and re.fullmatch('review-batch-[a-f0-9]{64}',self.batch_record_id) is not None,'REVIEW_BATCH_VERIFICATION_IDENTITY')
        require(type(self.task_revision) is int and 0<self.task_revision<=MAX_REVISION
            and type(self.seconds) is int and 0<=self.seconds<=MAX_REVISION,'REVIEW_BATCH_VERIFICATION_VALUES')
        require(self.no_work_statement is None or type(self.no_work_statement) is bool,'REVIEW_BATCH_VERIFICATION_FLAGS')
        require(isinstance(self.observed_at,str) and isinstance(self.verified_at,str),'REVIEW_BATCH_VERIFICATION_TIME')
        instant(self.observed_at);instant(self.verified_at)
        require(instant(self.verified_at)>=instant(self.observed_at),'REVIEW_BATCH_VERIFICATION_TIME')
        object.__setattr__(self,'verified_at',instant(self.verified_at).isoformat())
        object.__setattr__(self,'observed_at',instant(self.observed_at).isoformat())
    def as_record(self):
        return dict(verification_id=self.verification_id,task_id=self.task_id,task_revision=self.task_revision,
            batch_record_id=self.batch_record_id,estimate=dict(observation_id=self.observation_id,seconds=self.seconds,
                observed_at=self.observed_at,verified_at=self.verified_at),no_work_statement=self.no_work_statement)
    def sql_row(self,transaction_ref,audit_change_ref):
        require(identity(transaction_ref) and identity(audit_change_ref),'REVIEW_BATCH_VERIFICATION_TRANSACTION')
        return dict(verification_id=self.verification_id,batch_record_id=self.batch_record_id,task_id=self.task_id,
            task_revision=self.task_revision,estimate_kind='USER_REMAINING',observation_id=self.observation_id,
            seconds=self.seconds,observed_at=instant(self.observed_at),verified_at=instant(self.verified_at),
            no_work_statement=self.no_work_statement,transaction_ref=transaction_ref,
            audit_change_ref=audit_change_ref,runtime_payload=self.as_record())


@dataclass(frozen=True)
class ReviewBatchJournal:
    command: ReviewBatchCommand = field(repr=False)
    source_ref: str
    source_observed_at: datetime
    raw_command: bytes = field(repr=False)
    state: str
    code: str
    verifications: tuple[BatchVerificationRecord,...] = ()

    def __post_init__(self):
        require(isinstance(self.command,ReviewBatchCommand) and identity(self.source_ref),'REVIEW_BATCH_JOURNAL_IDENTITY')
        require(isinstance(self.source_observed_at,datetime) and self.source_observed_at.utcoffset() is not None,
            'REVIEW_BATCH_JOURNAL_SOURCE_TIME')
        require(isinstance(self.raw_command,bytes) and 0<len(self.raw_command)<=MAX_RAW_BYTES,'REVIEW_BATCH_JOURNAL_RAW')
        require(command_from_payload(strict_json(self.raw_command.decode('utf-8')))==self.command,'REVIEW_BATCH_JOURNAL_RAW_COMMAND')
        require(isinstance(self.code,str) and re.fullmatch('[A-Z][A-Z0-9_]{0,63}',self.code),'REVIEW_BATCH_JOURNAL_CODE')
        require(self.code==('REVIEW_BATCH_CONFIRMED' if self.state=='CONFIRMED' else 'REVIEW_BATCH_NOT_CONFIRMED'),
            'REVIEW_BATCH_JOURNAL_CODE')
        require(isinstance(self.verifications,tuple) and all(isinstance(v,BatchVerificationRecord) for v in self.verifications),
            'REVIEW_BATCH_JOURNAL_VERIFICATIONS')
        require((self.state=='CONFIRMED' and self.command.confirmed is True
                and self.verifications and len(self.verifications)==len(self.command.members))
            or (self.state=='NOT_CONFIRMED' and self.command.confirmed is not True and not self.verifications),
            'REVIEW_BATCH_JOURNAL_EFFECTS')
        require(len({v.task_id for v in self.verifications})==len(self.verifications)
            and (not self.verifications or {v.task_id for v in self.verifications}=={m.task_id for m in self.command.members}),
            'REVIEW_BATCH_JOURNAL_MEMBERSHIP')
        for v in self.verifications:
            require(v.batch_record_id==self.record_id and v.no_work_statement==self.command.no_work_statement,
                'REVIEW_BATCH_JOURNAL_BINDING')

    @property
    def record_id(self):return 'review-batch-'+self.command.fingerprint
    @property
    def kind(self):return 'REVIEW_BATCH_CONFIRMED' if self.state=='CONFIRMED' else 'REVIEW_BATCH_NOT_CONFIRMED'
    def payload(self):
        return dict(schema_version=JOURNAL_VERSION,record_id=self.record_id,kind=self.kind,
            command=self.command.as_record(),command_fingerprint=self.command.fingerprint,source_ref=self.source_ref,
            source_observed_at=self.source_observed_at.isoformat(),
            raw_command_base64=b64encode(self.raw_command).decode('ascii'),raw_command_hash=sha256(self.raw_command).hexdigest(),
            state=self.state,code=self.code,verifications=[v.as_record() for v in self.verifications])

    def sql_row(self,transaction_ref,audit_change_ref):
        require(identity(transaction_ref) and identity(audit_change_ref),'REVIEW_BATCH_JOURNAL_TRANSACTION')
        c=self.command
        return dict(record_id=self.record_id,command_id=c.command_id,aggregate_kind=self.kind,revision=1,
            review_id=c.review_id,frame_revision=c.frame_revision,user_statement_ref=c.user_statement_ref,batch_id=c.batch_id,
            confirmed=self.command.confirmed is True,no_work_statement=c.no_work_statement,member_count=len(c.members),
            authority_ref=c.authority_ref,source_ref=self.source_ref,source_observed_at=self.source_observed_at,
            raw_command=self.raw_command,raw_command_hash=sha256(self.raw_command).hexdigest(),
            state=self.state,code=self.code,transaction_ref=transaction_ref,audit_change_ref=audit_change_ref,
            runtime_payload=self.payload())

    @classmethod
    def from_payload(cls,value):
        require(isinstance(value,dict),'REVIEW_BATCH_JOURNAL_PAYLOAD')
        try:
            command=command_from_payload(value['command'])
            verifications=tuple(BatchVerificationRecord(v['verification_id'],v['task_id'],v['task_revision'],
                v['batch_record_id'],v['estimate']['observation_id'],v['estimate']['seconds'],v['estimate']['observed_at'],
                v['estimate']['verified_at'],v['no_work_statement']) for v in value['verifications'])
            result=cls(command,value['source_ref'],instant(value['source_observed_at']),
                b64decode(value['raw_command_base64'],validate=True),value['state'],value['code'],verifications)
        except (KeyError,TypeError,ValueError,OverflowError):require(False,'REVIEW_BATCH_JOURNAL_PAYLOAD')
        require(result.payload()==value,'REVIEW_BATCH_JOURNAL_PAYLOAD')
        return result


def command_from_payload(value):
    require(isinstance(value,dict),'REVIEW_BATCH_JOURNAL_COMMAND')
    try:
        r=value['review_ref']
        members=tuple(BatchMember(m['task_id'],m['revision'],m['observation_id'],m['seconds']) for m in value['members'])
        command=ReviewBatchCommand(value['command_id'],value['principal_id'],value['authority_ref'],r['review_id'],
            r['frame_revision'],r['user_statement_ref'],value['batch_id'],value['confirmed'],members,value['no_work_statement'])
    except (KeyError,TypeError,ValueError):require(False,'REVIEW_BATCH_JOURNAL_COMMAND')
    require(value==command.as_record(),'REVIEW_BATCH_JOURNAL_COMMAND')
    return command


@dataclass(frozen=True)
class PreparedReviewBatch:
    state: str
    code: str
    verifications: tuple[BatchVerificationRecord,...] = ()

    def __post_init__(self):
        require(self.state in ('CONFIRMED','NOT_CONFIRMED'),'REVIEW_BATCH_PREPARATION_STATE')
        require(isinstance(self.verifications,tuple) and all(isinstance(v,BatchVerificationRecord) for v in self.verifications),
            'REVIEW_BATCH_PREPARATION_EFFECTS')
        require((self.state=='CONFIRMED' and self.verifications) or (self.state=='NOT_CONFIRMED' and not self.verifications),
            'REVIEW_BATCH_PREPARATION_EFFECTS')
        require(len({v.task_id for v in self.verifications})==len(self.verifications),'REVIEW_BATCH_PREPARATION_MEMBERSHIP')


def verification_identity(command,member):
    """Deterministic identity bound to review/frame, statement, batch, task and estimate."""
    return 'verification-'+digest([command.review_id,command.frame_revision,command.batch_id,member.task_id,
        member.observation_id,command.user_statement_ref])


def prepare_review_batch(command,grant,evidence,*,caller,now):
    """Validate every member against independently resolved evidence; one invalid member rejects the batch."""
    validate_batch_grant(command,grant,now=now)
    require(isinstance(caller,CallerIdentity) and caller.authenticated and caller.origin=='USER_COMMAND'
        and caller.principal_id==command.principal_id,'REVIEW_BATCH_TRUSTED_USER_CALLER')
    require(isinstance(now,datetime) and now.utcoffset() is not None,'REVIEW_BATCH_CLOCK_REQUIRED')
    require(isinstance(evidence,tuple) and len(evidence)==len(command.members)
        and all(isinstance(e,BatchTaskEvidence) for e in evidence),'REVIEW_BATCH_EVIDENCE_SCOPE')
    by_task={e.record.task_id:e for e in evidence}
    require(set(by_task)=={m.task_id for m in command.members},'REVIEW_BATCH_EVIDENCE_SCOPE')
    if command.confirmed is not True:
        # Silence confirms none: an explicit non-confirmation records no member effect.
        return PreparedReviewBatch('NOT_CONFIRMED','REVIEW_BATCH_NOT_CONFIRMED')
    if command.no_work_statement is False:
        require(False,'REVIEW_BATCH_WORK_STATUS_UNCONFIRMED')
    verifications=[]
    for member in command.members:
        e=by_task[member.task_id];core=e.record.aggregate.as_record()['core']
        require(e.prior_verification_id is None,'REVIEW_BATCH_OVERLAPPING_VERIFICATION')
        require(e.record.revision==member.expected_revision,'REVIEW_BATCH_STALE_MEMBER')
        require(core['disposition']=='ACTIVE' and core['completion']=='INCOMPLETE','REVIEW_BATCH_MEMBER_INELIGIBLE')
        estimate=e.record.aggregate.as_record()['effort']['user_remaining']
        require(estimate is not None,'REVIEW_BATCH_MISSING_ESTIMATE')
        require(estimate['observation_id']==member.observation_id and estimate['seconds']==member.seconds,
            'REVIEW_BATCH_CHANGED_ESTIMATE')
        require(e.work_status!='WORKED','REVIEW_BATCH_MEMBER_WORKED_ON')
        require(e.work_status=='UNTOUCHED' or command.no_work_statement is True,'REVIEW_BATCH_WORK_STATUS_UNCONFIRMED')
        observed=instant(estimate['observed_at'])
        require(grant.source_observed_at>=observed,'REVIEW_BATCH_VERIFICATION_BEFORE_OBSERVATION')
        verifications.append(BatchVerificationRecord(verification_identity(command,member),member.task_id,
            member.expected_revision,'review-batch-'+command.fingerprint,member.observation_id,member.seconds,
            estimate['observed_at'],grant.source_observed_at.isoformat(),command.no_work_statement))
    return PreparedReviewBatch('CONFIRMED','REVIEW_BATCH_CONFIRMED',tuple(verifications))


@dataclass(frozen=True)
class BatchAuditChange:
    change_ref: str
    key: AggregateKey
    before_revision: int | None
    after_revision: int
    before_json: str | None = field(repr=False)
    after_json: str = field(repr=False)
    @property
    def tuple(self):
        return (self.key.kind,self.key.id,self.before_revision,self.after_revision,
            strict_json(self.before_json) if self.before_json is not None else None,strict_json(self.after_json))


@dataclass(frozen=True)
class BatchCommitPlan:
    request: CommitRequest
    receipt: CommitReceipt
    journal: ReviewBatchJournal = field(repr=False)
    audits: tuple[BatchAuditChange,...] = field(repr=False)
    @property
    def receipt_body(self):return asdict(self.receipt)


def prepare_batch_commit(codec,raw,grant,evidence,*,caller,now,context,expected_store_revision,audit_id):
    """Recompute exact verification effects from independently resolved inputs, without a permit."""
    command=admit_review_batch(codec,raw)
    require(isinstance(context,RequestContext) and context.request_id==command.command_id,'REVIEW_BATCH_COMMIT_REQUEST_SCOPE')
    prepared=prepare_review_batch(command,grant,evidence,caller=caller,now=now)
    journal=ReviewBatchJournal(command,grant.evidence_ref,grant.source_observed_at,raw,prepared.state,
        prepared.code,prepared.verifications)
    changes=[(AggregateKey(journal.kind,journal.record_id),None,1,None,journal.payload())]
    for v in journal.verifications:
        changes.append((AggregateKey('REVIEW_VERIFICATION',v.verification_id),None,1,None,v.as_record()))
    require(len(changes)<=MAX_MEMBERS+1,'REVIEW_BATCH_COMMIT_EFFECT_LIMIT')
    changes.sort(key=lambda c:(c[0].kind,c[0].id))
    writes=tuple(RecordWrite(key,revision,canonical(new)) for key,revision,_,_,new in changes)
    require(sum(len(w.body_json.encode()) for w in writes)<=MAX_JOURNAL_BYTES,'REVIEW_BATCH_COMMIT_SIZE_LIMIT')
    request=CommitRequest(context,command.principal_id,expected_store_revision,writes,audit_id,grant.evidence_ref)
    receipt=CommitReceipt(command.command_id,request.fingerprint,expected_store_revision+1,audit_id,tuple(w.key for w in writes))
    audits=tuple(BatchAuditChange('change-'+digest([audit_id,key.kind,key.id,after]),key,revision,after,
        canonical(old) if old is not None else None,canonical(new)) for key,revision,after,old,new in changes)
    return BatchCommitPlan(request,receipt,journal,audits)
