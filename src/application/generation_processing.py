"""Finite processing limits and detached resumable rule checkpoints."""
from dataclasses import dataclass, asdict
from datetime import timedelta
from src.application.definitions import DefinitionKey, canonical, strict_json, identity
from src.application.creation_outbox import DeliveryOutcome
from src.application.generation_commit import digest
from src.application.generation_evaluator import require


@dataclass(frozen=True)
class ProcessingLimits:
    max_events: int = 32
    max_rules_per_lease: int = 16
    max_attempts: int = 5
    lease_seconds: int = 300
    retry_seconds: int = 30

    def __post_init__(self):
        ceilings=(1000,1000,100,3600,86400)
        require(all(type(v) is int and 0<v<=cap for v,cap in zip(asdict(self).values(),ceilings)), 'PROCESSING_POSITIVE_BOUNDED_LIMITS')


@dataclass(frozen=True)
class ProcessingCheckpoint:
    input_hash: str
    rule_keys: tuple[DefinitionKey,...]
    cursor: int = 0
    results_json: str = '[]'
    attempts: int = 1
    state: str = 'RUNNING'
    code: str | None = None

    def __post_init__(self):
        import re
        require(isinstance(self.input_hash,str) and re.fullmatch('[a-f0-9]{64}',self.input_hash)
            and isinstance(self.rule_keys,tuple) and all(isinstance(k,DefinitionKey) and k.kind=='RELATIONSHIP_RULE' for k in self.rule_keys)
            and len({k.id for k in self.rule_keys})==len(self.rule_keys) and len(self.rule_keys)<=2048, 'PROCESSING_CHECKPOINT_SCOPE')
        values=strict_json(self.results_json)
        require(type(self.cursor) is int and 0<=self.cursor<=len(self.rule_keys) and isinstance(values,list) and len(values)==self.cursor
            and type(self.attempts) is int and self.attempts>0 and self.state in ('RUNNING','DONE','WAITING_FACTS','FAILED'), 'PROCESSING_CHECKPOINT_STATE')
        require(self.code is None or isinstance(self.code,str) and re.fullmatch('[A-Z][A-Z0-9_]{0,63}',self.code),'PROCESSING_CLOSED_CODE')
        for k,v in zip(self.rule_keys,values):
            require(isinstance(v,dict) and set(v)=={'rule','state','occurrence_ref','receipt_ref'} and v['rule']==asdict(k)
                and v['state'] in ('CREATED','PENDING','FAILED','NOT_ELIGIBLE'), 'PROCESSING_RULE_RESULT')
            refs=(v['occurrence_ref'],v['receipt_ref'])
            require(all(identity(ref) for ref in refs) if v['state']!='NOT_ELIGIBLE' else refs==(None,None),'PROCESSING_RESULT_REFERENCES')
        require(self.state not in ('DONE','WAITING_FACTS') or self.cursor==len(self.rule_keys),'PROCESSING_INCOMPLETE_TERMINAL')
        require(self.state!='DONE' or all(v['state'] in ('CREATED','NOT_ELIGIBLE') for v in values),'PROCESSING_FALSE_DONE')
        require(self.state!='WAITING_FACTS' or any(v['state']=='PENDING' for v in values),'PROCESSING_WAITING_WITHOUT_FACTS')

    @property
    def payload(self):
        return dict(input_hash=self.input_hash,rule_keys=[asdict(k) for k in self.rule_keys],cursor=self.cursor,
            results=strict_json(self.results_json),attempts=self.attempts,state=self.state,code=self.code)

    @classmethod
    def from_payload(cls,value):
        require(isinstance(value,dict) and set(value)=={'input_hash','rule_keys','cursor','results','attempts','state','code'},'PROCESSING_CHECKPOINT_PAYLOAD')
        try:return cls(value['input_hash'],tuple(DefinitionKey(**k) for k in value['rule_keys']),value['cursor'],canonical(value['results']),value['attempts'],value['state'],value['code'])
        except (KeyError,TypeError,ValueError):require(False,'PROCESSING_CHECKPOINT_PAYLOAD')

    def outcome(self,*,now,limits):
        result='processing-'+digest(self.payload)
        if self.state=='DONE':return DeliveryOutcome('DONE',result_ref=result)
        if self.state=='WAITING_FACTS':return DeliveryOutcome('WAITING_FACTS',result_ref=result)
        if self.state=='FAILED':return DeliveryOutcome('FAILED',result_ref=result,code=self.code or 'GENERATION_PERMANENT_FAILURE')
        return DeliveryOutcome('RETRY',result_ref=result,code=self.code or 'GENERATION_BATCH_CONTINUES',retry_at=now+timedelta(seconds=limits.retry_seconds))


@dataclass(frozen=True)
class ProcessingBatch:
    processed_events: int
    states: tuple[str,...]
    idle: bool
