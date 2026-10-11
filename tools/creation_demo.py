"""Local synthetic creation input demo; caller fixture, no SQL or live transport."""
import argparse
from datetime import datetime,timezone
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:sys.path.insert(0,str(ROOT))
from src.adapters.clocks import FrozenClock
from src.adapters.contract_json import ContractJSONCodec
from src.application.direct_creation import DirectCreationNormalizer,UserInputBinding,guided_message
from src.application.evidence_storage import SourceScope
from src.domain.authorization import CallerIdentity
from src.domain.provenance import capture_source
from tools.check_contract_registry import trusted_schemas


def main():
    for stream in (sys.stdin,sys.stdout,sys.stderr):
        if hasattr(stream,'reconfigure'):stream.reconfigure(encoding='utf-8')
    flags=argparse.ArgumentParser(description=__doc__)
    flags.add_argument('--interactive',action='store_true');flags.add_argument('--guided',action='store_true');args=flags.parse_args()
    if args.guided:
        prompts={'title':'任务标题','importance':'重要性（1–5）','requiredness':'必须完成或可选','difficulty':'思考／重复／新知难度（例如 3/2/3）',
            'remaining':'剩余时间（例如约40分钟，不知道可留空）','domain':'领域（学习／运动／生活／其他）'}
        examples=dict(title='阅读论文',importance='4',requiredness='可选',difficulty='3/2/3',remaining='约40分钟',domain='学习')
        raw=guided_message({k:input(v+'：') for k,v in prompts.items()} if args.interactive else examples)
    else:
        statement=input('要新增什么任务：') if args.interactive else '新增任务：阅读论文，可选，重要性4，难度3/2/3，剩余约40分钟，领域学习'
        raw=statement.encode()
    now=datetime(2026,1,1,tzinfo=timezone.utc);scope=SourceScope('synthetic-demo','scope','account');caller=CallerIdentity('synthetic-user','USER_COMMAND',True)
    source=capture_source(provider=scope.provider,scope_ref=scope.scope_ref,external_id='synthetic-message',raw_bytes=raw,captured_at=now,source_type='USER')
    normalizer=DirectCreationNormalizer(ContractJSONCodec(trusted_schemas()),clock=FrozenClock(now),bindings=(UserInputBinding(caller.principal_id,scope),))
    proposal=(normalizer.guided if args.guided else normalizer.natural)(raw,source,caller=caller)
    if proposal.candidate is not None:
        values=proposal.candidate['proposed_fields'];print('任务：'+values.get('title','尚未提供'))
        print('重要性：'+str(values.get('importance','尚未提供')))
        print('要求：'+{'REQUIRED':'必须完成','OPTIONAL':'可选'}.get(values.get('requiredness'),'尚未提供'))
        print('剩余时间：'+(str(values['remaining_seconds'])+'秒' if 'remaining_seconds' in values else '尚不清楚'))
    for issue in proposal.issues:print(issue.question)
    if proposal.missing_fields:
        names={'/core/title':'标题','/core/importance':'重要性','/core/requiredness':'是否必须完成','/core/difficulty':'三项难度','/core/domain':'领域'}
        print('待补充：'+'、'.join(names[x] for x in proposal.missing_fields))
    print('输入已明确，可交给创建服务处理。' if proposal.ready_for_creation else '保留这次输入，待补充后继续。')
    print('这是合成数据的输入演示，未写入任务。')
    return 0


if __name__=='__main__':raise SystemExit(main())
