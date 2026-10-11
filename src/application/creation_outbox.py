"""Canonical source pins and bounded delivery values, never Task authority."""
from dataclasses import dataclass, field
from datetime import datetime
from hashlib import sha256
import re
from typing import Protocol

from src.application.definitions import identity
from src.domain.time_values import UtcInstant


class OutboxError(RuntimeError):
    pass


def require(value, code):
    if not value: raise OutboxError(code)


def instant(value):
    try: return UtcInstant(value).value
    except (TypeError, ValueError): raise OutboxError('OUTBOX_AWARE_INSTANT_REQUIRED') from None


def positive(value):
    return type(value) is int and value > 0


def lease_duration(seconds):
    require(positive(seconds) and seconds <= 3600, 'OUTBOX_LEASE_DURATION')
    return seconds


def source_reference(value):
    return isinstance(value,str) and bool(value.strip()) and '\x00' not in value and len(value)<=1048576


def event_id_for(task_id):
    require(source_reference(task_id),'OUTBOX_CREATION_IDENTITY')
    return 'creation:'+sha256(task_id.encode('utf-8')).hexdigest()


@dataclass(frozen=True)
class CreationEvent:
    event_id: str
    task_id: str
    task_revision: int
    content_hash: str
    creation_transaction_ref: str
    principal_id: str
    authority_ref: str
    occurred_at: datetime

    def __post_init__(self):
        require(source_reference(self.task_id) and self.event_id == event_id_for(self.task_id)
                and positive(self.task_revision), 'OUTBOX_CREATION_IDENTITY')
        require(all(source_reference(v) for v in (self.creation_transaction_ref,self.principal_id,self.authority_ref)),
                'OUTBOX_CREATION_PROVENANCE')
        require(isinstance(self.content_hash,str) and re.fullmatch('[a-f0-9]{64}',self.content_hash), 'OUTBOX_SOURCE_HASH')
        object.__setattr__(self,'occurred_at',instant(self.occurred_at))


@dataclass(frozen=True)
class DeliveryLease:
    event: CreationEvent
    revision: int
    attempt: int
    worker_id: str
    token: str = field(repr=False)
    changed_at: datetime
    expires_at: datetime

    def __post_init__(self):
        require(isinstance(self.event,CreationEvent) and positive(self.revision) and self.revision >= 2
                and positive(self.attempt) and identity(self.worker_id), 'OUTBOX_LEASE_IDENTITY')
        require(isinstance(self.token,str) and re.fullmatch('[a-f0-9]{32}',self.token), 'OUTBOX_LEASE_TOKEN')
        for name in ('changed_at','expires_at'):object.__setattr__(self,name,instant(getattr(self,name)))
        require(self.event.occurred_at <= self.changed_at < self.expires_at
                and (self.expires_at-self.changed_at).total_seconds() <= 3600, 'OUTBOX_LEASE_TIME')


@dataclass(frozen=True)
class DeliveryOutcome:
    kind: str
    result_ref: str | None = None
    code: str | None = None
    retry_at: datetime | None = None

    def __post_init__(self):
        require(self.kind in ('DONE','WAITING_FACTS','FAILED','RETRY'), 'OUTBOX_OUTCOME_KIND')
        require(self.result_ref is None or identity(self.result_ref), 'OUTBOX_RESULT_REFERENCE')
        require(self.code is None or isinstance(self.code,str) and
                re.fullmatch('[A-Z][A-Z0-9_]{0,63}',self.code), 'OUTBOX_CLOSED_DIAGNOSTIC')
        require((self.kind in ('DONE','WAITING_FACTS') and self.result_ref is not None and self.code is None and self.retry_at is None)
                or (self.kind == 'FAILED' and self.code is not None and self.retry_at is None)
                or (self.kind == 'RETRY' and self.code is not None and self.retry_at is not None), 'OUTBOX_OUTCOME_SHAPE')
        if self.retry_at is not None:object.__setattr__(self,'retry_at',instant(self.retry_at))

    @property
    def payload(self):
        return dict(kind=self.kind,result_ref=self.result_ref,code=self.code,
                    retry_at=self.retry_at.isoformat() if self.retry_at else None)

    @classmethod
    def from_payload(cls,value):
        require(isinstance(value,dict) and set(value)=={'kind','result_ref','code','retry_at'}, 'OUTBOX_RESULT_SHAPE')
        v=dict(value)
        if v['retry_at'] is not None:
            try:v['retry_at']=datetime.fromisoformat(v['retry_at'])
            except (ValueError,TypeError):raise OutboxError('OUTBOX_AWARE_INSTANT_REQUIRED') from None
        return cls(**v)


@dataclass(frozen=True)
class DeliverySnapshot:
    event: CreationEvent
    revision: int
    attempt: int
    state: str
    changed_at: datetime
    available_at: datetime
    lease: DeliveryLease | None
    outcome: DeliveryOutcome | None


class CreationOutbox(Protocol):
    def get(self,event_id:str)->DeliverySnapshot|None: ...
    def claim(self,*,lease_seconds:int=300)->DeliveryLease|None: ...
    def renew(self,lease:DeliveryLease,*,lease_seconds:int=300)->DeliveryLease: ...
    def settle(self,lease:DeliveryLease,outcome:DeliveryOutcome)->DeliverySnapshot: ...
