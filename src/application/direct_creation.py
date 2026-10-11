"""Bounded direct-user creation input, frozen proposals and manual handoff.

Transport supplies caller and account bindings independently. These helpers
neither authenticate raw input nor mint grants, choose defaults or publish Tasks.
"""
from dataclasses import dataclass,field
from decimal import Decimal
from hashlib import sha256
import re
import unicodedata

from src.application.definitions import canonical,identity,strict_json
from src.application.evidence_storage import SourceScope,admit_source,admit_candidate
from src.application.manual_tasks import ResolvedManualIntent
from src.application.transactions import require
from src.domain.authorization import CallerIdentity,Command,change
from src.domain.provenance import SourceRecord,make_candidate

PARSER='direct-user-create-v1'
LABELS={'标题':'title','重要性':'importance','必做':'requiredness','要求':'requiredness','剩余':'remaining',
    '剩余时间':'remaining','难度':'difficulty','领域':'domain'}
UNKNOWN=frozenset(('', '不知道','不确定','暂不清楚','暂不回答','跳过'))
DOMAINS={'学习':'study','运动':'exercise','生活':'life_administration','其他':'other'}
REQUIREDNESS={'必须完成':'REQUIRED','必须做':'REQUIRED','必做':'REQUIRED','必须':'REQUIRED',
    '可选':'OPTIONAL','非必做':'OPTIONAL','自设':'OPTIONAL','不是必须':'OPTIONAL'}
PREFIX=re.compile(r'^(?:请)?(?:帮我)?(?:(?:新增|添加|创建|新建|记)(?:一个)?任务|加(?:一个|个)?任务)\s*[:：]?\s*')
TEMPORAL=re.compile(r'今天|明天|后天|本周|下周|月底|周[一二三四五六日天]|星期|每周|每天|截止|到期|之前|\d{1,2}[月:/]\d{1,2}')
COMPOUND=re.compile(r'(?:并且|然后|同时|顺便|以及|并|再).*(?:新增|创建|删除|取消|完成|修改|更新|安排|提醒|做|写)')


@dataclass(frozen=True)
class UserInputBinding:
    principal_id: str
    scope: SourceScope

    def __post_init__(self):
        require(identity(self.principal_id) and isinstance(self.scope,SourceScope),'DIRECT_TYPED_INPUT_BINDING_REQUIRED')


@dataclass(frozen=True)
class InputIssue:
    field: str
    code: str
    question: str


@dataclass(frozen=True)
class CreationProposal:
    principal_id: str
    statement_bytes: bytes = field(repr=False)
    source: SourceRecord = field(repr=False)
    input_mode: str
    candidate_json: str | None = field(repr=False)
    facts_json: str = field(repr=False)
    explicit_unknown_fields: tuple[str,...]
    issues: tuple[InputIssue,...]
    missing_fields: tuple[str,...]

    @property
    def candidate(self):return strict_json(self.candidate_json) if self.candidate_json is not None else None
    @property
    def facts(self):return strict_json(self.facts_json)
    @property
    def normalized(self):return self.candidate_json is not None and not self.issues
    @property
    def ready_for_creation(self):return self.normalized and not self.missing_fields
    @property
    def fingerprint(self):
        return sha256(canonical(dict(principal=self.principal_id,source=self.source.as_record(),mode=self.input_mode,
            statement_hash=sha256(self.statement_bytes).hexdigest(),candidate=self.candidate,facts=self.facts,
            unknown=list(self.explicit_unknown_fields),issues=[vars(i) for i in self.issues],missing=list(self.missing_fields))).encode()).hexdigest()


@dataclass(frozen=True)
class ManualInputHandoff:
    command: Command = field(repr=False)
    intent: ResolvedManualIntent = field(repr=False)
    proposal_fingerprint: str
    statement_bytes: bytes = field(repr=False)


def guided_message(answers):
    """Transport serialization retains every exact textual answer; users fill fields."""
    require(isinstance(answers,dict) and all(isinstance(k,str) and isinstance(v,str) for k,v in answers.items()),'DIRECT_GUIDED_TEXT_FIELDS_REQUIRED')
    return canonical(dict(input_kind='CREATE_TASK_GUIDED',answers=answers)).encode()


def _safe_title(value):
    return isinstance(value,str) and bool(value.strip()) and len(value)<=500 and not any(unicodedata.category(c).startswith('C') for c in value)


def _duration(raw):
    match=re.fullmatch(r'(?:大约|约)?\s*(\d{1,8}(?:\.\d{1,6})?)\s*(秒|分钟|分|小时)',raw)
    if not match:return None
    seconds=Decimal(match[1])*{'秒':1,'分钟':60,'分':60,'小时':3600}[match[2]]
    return int(seconds) if seconds==seconds.to_integral_value() else None


def parse_creation_answers(answers):
    """Pure textual field validation for original input and scoped follow-up."""
    require(isinstance(answers,dict) and all(isinstance(k,str) and isinstance(v,str) for k,v in answers.items()),"DIRECT_GUIDED_TEXT_FIELDS_REQUIRED")
    fields={};facts={};unknown=[];issues=[]
    def issue(field,code,question):issues.append(InputIssue(field,code,question))
    for key,untrimmed in answers.items():
        value=untrimmed.strip()
        if key=='title':
            if not _safe_title(value):issue(key,'TITLE_REQUIRED','新增任务的标题是什么？')
            else:fields['title']=value
            continue
        if value in UNKNOWN:
            unknown.append(key);continue
        if key=='importance':
            if re.fullmatch('[1-5]',value):fields['importance']=int(value)
            else:issue(key,'RATING_REQUIRED','重要性请给一个 1–5 的分数。')
        elif key=='requiredness':
            if value in REQUIREDNESS:fields['requiredness']=REQUIREDNESS[value]
            else:issue(key,'REQUIREDNESS_UNRESOLVED','这项任务是必须完成，还是可选？会失效的任务还需明确失效条件。')
        elif key=='difficulty':
            match=re.fullmatch(r'([1-5])\s*[/／ ]\s*([1-5])\s*[/／ ]\s*([1-5])',value) or re.fullmatch(r'([1-5])([1-5])([1-5])',value)
            if match:fields['difficulty']=dict(zip(('thinking_depth','repetitive_volume','new_learning_load'),map(int,match.groups())))
            else:issue(key,'THREE_RATINGS_REQUIRED','思考深度、重复工作量、新知识学习量各是多少（1–5，按此顺序）？')
        elif key=='remaining':
            seconds=_duration(value)
            if seconds is not None:fields['remaining_seconds']=seconds
            else:issue(key,'ONE_DURATION_REQUIRED','大约还需多久？请给一个带秒、分钟或小时的估计；暂时不知道也可以。')
        elif key=='domain':
            if value in DOMAINS:facts['domain']=DOMAINS[value]
            else:issue(key,'DOMAIN_UNRESOLVED','这项任务属于学习、运动、生活，还是其他？')
        else:issue(key,'UNSUPPORTED_FIELD','这段附加要求尚不能确定处理方式，请单独说明。')
    if 'title' not in answers:issue('title','TITLE_REQUIRED','新增任务的标题是什么？')
    return fields,facts,tuple(sorted(unknown)),tuple(issues)


class DirectCreationNormalizer:
    def __init__(self,codec,*,clock,bindings=()):
        require(isinstance(bindings,tuple) and all(isinstance(b,UserInputBinding) for b in bindings)
            and len({(b.principal_id,b.scope.provider,b.scope.scope_ref) for b in bindings})==len(bindings),'DIRECT_TRUSTED_BINDING_REGISTRY')
        self.codec=codec;self.clock=clock
        self._bindings={(b.principal_id,b.scope.provider,b.scope.scope_ref):b for b in bindings}

    def _context(self,raw,source,caller):
        require(isinstance(caller,CallerIdentity) and caller.authenticated and caller.origin=='USER_COMMAND','DIRECT_AUTHENTICATED_USER_REQUIRED')
        require(isinstance(raw,bytes) and 0<len(raw)<=8192,'DIRECT_INPUT_SIZE_LIMIT')
        require(isinstance(source,SourceRecord),'DIRECT_TYPED_SOURCE_REQUIRED')
        source=admit_source(self.codec,canonical(source.as_record()).encode()).source
        require(source.source_type=='USER' and source.state=='PRESENT','DIRECT_PRESENT_USER_SOURCE_REQUIRED')
        require((caller.principal_id,source.provider,source.scope_ref) in self._bindings,'DIRECT_USER_ACCOUNT_SCOPE_REQUIRED')
        require(sha256(raw).hexdigest()==source.content_hash,'DIRECT_EXACT_STATEMENT_REQUIRED')
        require(source.captured_at<=self.clock.now(),'DIRECT_FUTURE_SOURCE_REJECTED')
        try:return raw.decode('utf-8')
        except UnicodeError:require(False,'DIRECT_UTF8_REQUIRED')

    def _result(self,raw,source,caller,mode,answers,issues):
        fields,facts,unknown,found=parse_creation_answers(answers)
        issues=[*issues,*found]
        missing=tuple(sorted('/core/'+key for key in ('title','importance','requiredness','difficulty','domain') if key not in (fields|facts)))
        candidate=None
        if fields:
            v=make_candidate(source,parser_version=PARSER+'-'+mode.lower(),action='CREATE_TASK',proposed_fields=fields,confidence=1 if not issues else 0).as_record()
            candidate=admit_candidate(self.codec,canonical(v).encode(),pending_only=True).candidate.as_record()
        return CreationProposal(caller.principal_id,raw,source,mode,canonical(candidate) if candidate is not None else None,
            canonical(facts),tuple(sorted(unknown)),tuple(issues),missing)

    def natural(self,raw,source,*,caller):
        text=self._context(raw,source,caller);issues=[];answers={}
        def problem(code,question):issues.append(InputIssue('statement',code,question))
        stripped=text.strip();match=PREFIX.match(stripped)
        if not match:
            problem('CREATE_INTENT_UNRESOLVED','你要新增什么任务？可以说“新增任务：读论文”，或逐项填写。')
            return self._result(raw,source,caller,'NATURAL',answers,issues)
        rest=stripped[match.end():];tail=''
        quotes={'“':'”','"':'"','「':'」'}
        if rest and rest[0] in quotes:
            close=rest.find(quotes[rest[0]],1)
            if close<0:problem('UNCLOSED_TITLE','任务标题的引号没有闭合，请补全标题。')
            else:
                answers['title']=rest[1:close];tail=rest[close+1:]
                if tail and not re.match(r'^\s*[,，;；\n]',tail):problem('UNSUPPORTED_TRAILING_TEXT','标题后还有一段要求，请单独说明。')
        else:
            pieces=re.split(r'[,，;；\n]',rest,maxsplit=1);answers['title']=pieces[0].strip();tail=pieces[1] if len(pieces)>1 else ''
            if answers['title'].endswith(('?','？')) or COMPOUND.search(answers['title']) or TEMPORAL.search(answers['title']):
                problem('TITLE_OR_EXTRA_INTENT_UNRESOLVED','请明确任务标题；时间安排或其他动作需要单独说明。')
            if re.match(r'^(?:那个|这个|上面|刚才|之前|上一)',answers['title']):
                problem('REFERENCED_TITLE_UNRESOLVED','你指的是哪项具体内容？请给新增任务的标题。')
        for segment in re.split(r'[,，;；\n]',tail):
            segment=segment.strip()
            if not segment:continue
            if segment in REQUIREDNESS:key='requiredness';value=segment
            else:
                label=re.match(r'^(剩余时间|重要性|剩余|难度|领域|要求|必做)\s*[:：]?\s*(.*)$',segment)
                if label:key=LABELS[label[1]];value=label[2]
                else:
                    problem('UNSUPPORTED_TRAILING_TEXT','这段附加要求尚不能确定处理方式，请单独说明。');continue
            if key in answers:issues.append(InputIssue(key,'DUPLICATE_FIELD','同一项信息出现了两次，请明确以哪个值为准。'))
            else:answers[key]=value
        return self._result(raw,source,caller,'NATURAL',answers,issues)

    def guided(self,raw,source,*,caller):
        text=self._context(raw,source,caller)
        try:v=strict_json(text)
        except (ValueError,RuntimeError):require(False,'DIRECT_GUIDED_ENVELOPE_INVALID')
        require(isinstance(v,dict) and set(v)=={'input_kind','answers'} and v['input_kind']=='CREATE_TASK_GUIDED'
            and isinstance(v['answers'],dict) and all(isinstance(k,str) and isinstance(x,str) for k,x in v['answers'].items()),'DIRECT_GUIDED_ENVELOPE_INVALID')
        return self._result(raw,source,caller,'GUIDED',v['answers'],[])

    def manual_handoff(self,proposal,*,command_id,task_id,authority_ref,caller):
        require(isinstance(proposal,CreationProposal),'DIRECT_TYPED_PROPOSAL_REQUIRED')
        require(isinstance(caller,CallerIdentity) and caller.principal_id==proposal.principal_id,'DIRECT_PROPOSAL_OWNER_REQUIRED')
        fn=self.natural if proposal.input_mode=='NATURAL' else self.guided
        rebuilt=fn(proposal.statement_bytes,proposal.source,caller=caller)
        require(rebuilt.fingerprint==proposal.fingerprint,'DIRECT_PROPOSAL_DRIFT')
        require(proposal.normalized,'DIRECT_CLARIFICATION_REQUIRED')
        require(all(identity(v) for v in (command_id,task_id,authority_ref)),'DIRECT_TYPED_HANDOFF_IDS_REQUIRED')
        fields=dict(proposal.candidate['proposed_fields'])
        if 'remaining_seconds' in fields:fields['user_remaining_seconds']=fields.pop('remaining_seconds')
        elif 'remaining' in proposal.explicit_unknown_fields:fields['user_remaining_seconds']=None
        command=Command(command_id,caller.principal_id,'USER_COMMAND',authority_ref,(change(task_id,None,'CREATE_TASK',fields),))
        intent=ResolvedManualIntent(command.fingerprint,proposal.source.record_id,proposal.source.captured_at,canonical(proposal.facts))
        return ManualInputHandoff(command,intent,proposal.fingerprint,proposal.statement_bytes)
