"""Source-authorized actual increments/cumulative reports; U is independent."""
from copy import deepcopy
from dataclasses import dataclass,field
from datetime import datetime
from hashlib import sha256

from src.application.command_validation import PreparedUserEstimate
from src.application.definitions import canonical,identity,strict_json
from src.application.task_storage import TaskStorageRecord,admit_storage
from src.application.transactions import require
from src.domain.task_aggregate import instant


@dataclass(frozen=True)
class WorkReport:
    payload_json: str = field(repr=False)

    def __post_init__(self):
        v=self.as_record()
        require(isinstance(v,dict) and set(v)<= {'schema_version','command_id','principal_id','origin','authority_ref',
            'observation_id','target_ref','mode','seconds','stage_id','session_started_at','session_ended_at','user_remaining_seconds'},'WORK_REPORT_FIELDS')
        require(v['schema_version']=='0.1.0-work-report' and v['origin']=='USER_COMMAND'
            and all(identity(v[n]) for n in ('command_id','principal_id','authority_ref','observation_id')),'WORK_REPORT_IDENTITY')
        require(isinstance(v['target_ref'],dict) and set(v['target_ref'])=={'task_id','revision'} and identity(v['target_ref']['task_id'])
            and type(v['target_ref']['revision']) is int and v['target_ref']['revision']>0,'WORK_REPORT_TARGET')
        require(v['mode'] in ('INCREMENT','CUMULATIVE') and type(v['seconds']) is int and v['seconds']>=0,'WORK_REPORT_SECONDS')
        require(v['stage_id'] is None or identity(v['stage_id']),'WORK_REPORT_STAGE')
        if 'user_remaining_seconds' in v:
            require(v['user_remaining_seconds'] is None or type(v['user_remaining_seconds']) is int and v['user_remaining_seconds']>=0,'WORK_REPORT_U')
        try:
            start=instant(v['session_started_at']) if v['session_started_at'] is not None else None
            end=instant(v['session_ended_at']) if v['session_ended_at'] is not None else None
        except (ValueError,TypeError):require(False,'WORK_REPORT_SESSION_TIME')
        require(start is None or end is None or start<=end,'WORK_REPORT_SESSION_ORDER')
        object.__setattr__(self,'payload_json',canonical(v))

    def as_record(self):return strict_json(self.payload_json)
    @property
    def command_id(self):return self.as_record()['command_id']
    @property
    def principal_id(self):return self.as_record()['principal_id']
    @property
    def authority_ref(self):return self.as_record()['authority_ref']
    @property
    def observation_id(self):return self.as_record()['observation_id']
    @property
    def task_id(self):return self.as_record()['target_ref']['task_id']
    @property
    def expected_revision(self):return self.as_record()['target_ref']['revision']
    @property
    def fingerprint(self):return sha256(self.payload_json.encode()).hexdigest()
    @property
    def fact_fingerprint(self):
        v=self.as_record();v={k:val for k,val in v.items() if k not in ('command_id','authority_ref','origin','schema_version','target_ref')}
        v['task_id']=self.task_id;return sha256(canonical(v).encode()).hexdigest()


def admit_work_report(codec,raw):
    require(isinstance(raw,bytes) and 0<len(raw)<=262144,'WORK_REPORT_SIZE_LIMIT')
    admitted=codec.admit('work-report',raw);require(admitted.status=='SUPPORTED_SHAPE','WORK_REPORT_SHAPE_UNSUPPORTED')
    return WorkReport(canonical(admitted.payload))


@dataclass(frozen=True)
class WorkReportGrant:
    report: WorkReport = field(repr=False)
    evidence_ref: str
    issued_at: datetime
    expires_at: datetime | None = None
    active: bool = True

    def __post_init__(self):
        require(isinstance(self.report,WorkReport) and identity(self.evidence_ref) and type(self.active) is bool,'WORK_REPORT_TYPED_GRANT')
        require(isinstance(self.issued_at,datetime) and self.issued_at.utcoffset() is not None
            and (self.expires_at is None or isinstance(self.expires_at,datetime) and self.expires_at.utcoffset() is not None
            and self.issued_at<self.expires_at),'WORK_REPORT_GRANT_TIME')

    def as_record(self):return dict(contract='work-report',command=self.report.as_record(),active=self.active)


def validate_work_grant(report,grant,caller,now):
    require(isinstance(grant,WorkReportGrant),'UNREGISTERED_AUTHORITY')
    require(caller.authenticated and caller.origin=='USER_COMMAND' and caller.principal_id==report.principal_id,'UNTRUSTED_CALLER')
    require(grant.report.fingerprint==report.fingerprint,'WORK_REPORT_EXACT_SCOPE_MISMATCH')
    require(grant.active and grant.issued_at<=now and (grant.expires_at is None or now<grant.expires_at),'INACTIVE_AUTHORITY')


@dataclass(frozen=True)
class ActualWorkStorageRecord:
    raw_bytes: bytes = field(repr=False)
    content_hash: str
    payload_json: str = field(repr=False)

    def __post_init__(self):
        require(isinstance(self.raw_bytes,bytes) and 0<len(self.raw_bytes)<=262144 and sha256(self.raw_bytes).hexdigest()==self.content_hash,
            'ACTUAL_WORK_PAYLOAD_HASH')
        v=self.as_record();require(strict_json(self.raw_bytes.decode())==v,'ACTUAL_WORK_PAYLOAD_DRIFT')
        r=WorkReport(canonical(v['report']))
        require(v['schema_version']=='0.1.0-actual-work-record' and (v['observation_id'],v['task_id'],v['revision'],v['recorded_task_revision'])
            ==(r.observation_id,r.task_id,1,r.expected_revision+1),'ACTUAL_WORK_IDENTITY')
        require(identity(v['source_ref']),'ACTUAL_WORK_SOURCE')
        require(all(type(v[n]) is int and v[n]>=0 for n in ('previous_total_seconds','increment_seconds','resulting_total_seconds')),'ACTUAL_WORK_TOTAL')
        require(v['resulting_total_seconds']==v['previous_total_seconds']+v['increment_seconds'] and
            (v['increment_seconds']==r.as_record()['seconds'] if r.as_record()['mode']=='INCREMENT' else v['resulting_total_seconds']==r.as_record()['seconds']),
            'ACTUAL_WORK_SETTLEMENT')
        try:
            observed=instant(v['source_observed_at'])
            require(all(t is None or instant(t)<=observed for t in (r.as_record()['session_started_at'],r.as_record()['session_ended_at'])),
                'WORK_REPORT_FUTURE_SESSION')
        except ValueError:require(False,'ACTUAL_WORK_SOURCE_TIME')

    def as_record(self):return strict_json(self.payload_json)
    @property
    def observation_id(self):return self.as_record()['observation_id']
    @property
    def task_id(self):return self.as_record()['task_id']
    @property
    def revision(self):return 1
    @property
    def report(self):return WorkReport(canonical(self.as_record()['report']))


def admit_actual_record(codec,raw):
    require(isinstance(raw,bytes) and 0<len(raw)<=262144,'ACTUAL_WORK_SIZE_LIMIT')
    wire=codec.admit('actual-work-record',raw);require(wire.status=='SUPPORTED_SHAPE','ACTUAL_WORK_SHAPE_UNSUPPORTED')
    return ActualWorkStorageRecord(raw,sha256(raw).hexdigest(),canonical(wire.payload))


@dataclass(frozen=True)
class PreparedWorkReport:
    task: TaskStorageRecord = field(repr=False)
    work: ActualWorkStorageRecord = field(repr=False)
    estimates: tuple[PreparedUserEstimate,...]


def prepare_work_report(codec,report,grant,before,*,caller,previous_total_seconds,source_observed_at,now):
    validate_work_grant(report,grant,caller,now)
    require(isinstance(before,TaskStorageRecord) and before.task_id==report.task_id,'UNKNOWN_TARGET')
    require(before.revision==report.expected_revision,'STALE_STATE_VERSION')
    require(type(previous_total_seconds) is int and previous_total_seconds>=0,'WORK_REPORT_PREVIOUS_TOTAL')
    require(isinstance(source_observed_at,datetime) and source_observed_at.utcoffset() is not None and source_observed_at<=now,
        'WORK_REPORT_SOURCE_TIME_REQUIRED')
    f=report.as_record();increment=f['seconds'] if f['mode']=='INCREMENT' else f['seconds']-previous_total_seconds
    require(increment>=0,'WORK_REPORT_CUMULATIVE_BELOW_RECORDED_TOTAL')
    for value in (f['session_started_at'],f['session_ended_at']):
        require(value is None or instant(value)<=source_observed_at,'WORK_REPORT_FUTURE_SESSION')
    v=deepcopy(before.aggregate.as_record());v['core']['revision']=v['effort']['task_revision']=before.revision+1;estimates=()
    if v['effort']['prediction'] is not None:v['effort']['prediction']['valid']=v['effort']['prediction']['applicable']=False
    if 'user_remaining_seconds' in f:
        seconds=f['user_remaining_seconds'];require(v['core']['completion']!='COMPLETE' or seconds==0,'WORK_REPORT_COMPLETED_U_CONFLICT')
        u=None
        if seconds is not None:
            observation=PreparedUserEstimate('remaining-'+sha256((report.fingerprint+grant.evidence_ref).encode()).hexdigest(),
                report.task_id,seconds,source_observed_at,grant.evidence_ref,report.authority_ref)
            u=dict(seconds=seconds,observation_id=observation.observation_id,observed_at=source_observed_at.isoformat(),verified_at=source_observed_at.isoformat())
            estimates=(observation,)
        v['effort']['user_remaining']=u
        provenance={p['field']:p['source_ref'] for p in v['provenance'] if not p['field'].startswith('/effort/user_remaining/')}
        provenance['/effort/user_remaining']=grant.evidence_ref
        v['provenance']=[dict(field=k,source_ref=s) for k,s in sorted(provenance.items())]
    work=dict(schema_version='0.1.0-actual-work-record',observation_id=report.observation_id,task_id=report.task_id,revision=1,
        recorded_task_revision=before.revision+1,report=report.as_record(),source_ref=grant.evidence_ref,source_observed_at=source_observed_at.isoformat(),
        previous_total_seconds=previous_total_seconds,increment_seconds=increment,resulting_total_seconds=previous_total_seconds+increment)
    return PreparedWorkReport(admit_storage(codec,canonical(v).encode()),admit_actual_record(codec,canonical(work).encode()),estimates)
