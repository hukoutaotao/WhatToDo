"""Synthetic local guided-review demo; no account, provider or persistent writes."""
from __future__ import annotations

import argparse
from datetime import datetime, timedelta, timezone
from hashlib import sha256
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path: sys.path.insert(0, str(ROOT))
from src.application.guided_review import candidate_reply, prepare_response, present_review, render_review, task_reply, unchanged_reply
from src.domain.authorization import CallerIdentity
from src.domain.effort import UserEstimate
from src.domain.review import ReviewFrame, ReviewTask, assess_review


def main():
    for stream in (sys.stdin, sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"): stream.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--interactive", action="store_true", help="Answer the synthetic fixture through local text prompts")
    parser.add_argument("--batch-demo", action="store_true", help="Demonstrate explicit full-scope unchanged verification")
    args = parser.parse_args()
    now = datetime(2026, 1, 1, 12, tzinfo=timezone.utc)
    tasks = tuple(ReviewTask("demo-" + str(i), 1, i, "INCOMPLETE", "ACTIVE", True, UserEstimate(3600, "observation-" + str(i), now - timedelta(days=1), now - timedelta(days=1)), "UNTOUCHED", "CURRENT") for i in (1, 2))
    frame = ReviewFrame("demo-review", 1, "synthetic-queue", now - timedelta(minutes=10), tasks, ("demo-candidate",))
    view = present_review(frame, task_labels={"demo-1": "整理示例笔记", "demo-2": "完成示例作业"}, candidate_labels={"demo-candidate": "核对外部来源的示例事项"})
    print(render_review(view))
    replies, candidates, raw, batches = [], [], [], []
    selected = input("要批量保持不变的任务编号（如1,2），留空逐项回答：") if args.interactive else ("1,2" if args.batch_demo else "")
    raw.append(selected)
    selected_numbers = ()
    if selected.strip():
        try:
            selected_numbers = tuple(int(value.strip()) for value in selected.split(","))
            for number in selected_numbers: view.task(number)
            if len(set(selected_numbers)) != len(selected_numbers): raise ValueError("Duplicate selection")
        except ValueError:
            print("任务编号需要在本次复核范围内，且不能重复。请重新打开演示。"); return 1
        prompts = [("confirm_estimate", "所选事项的剩余估计均不变吗？确认／否／留空"), ("confirm_completion", "所选事项的完成状态均不变吗？确认／否／留空"), ("no_work", "这次是否动过所选事项？没做／做过／留空")]
        values = {key: input(prompt + " ") for key, prompt in prompts} if args.interactive else dict(confirm_estimate="确认", confirm_completion="确认", no_work="没做")
        raw.append(repr(values))
        batches.append(unchanged_reply(view, selected_numbers, batch_id="synthetic-explicit-batch", **values))
    for n, label in enumerate(view.task_labels, 1):
        if n in selected_numbers: continue
        if args.interactive:
            values = {key: input(label + "：" + prompt + " ") for key, prompt in [("completion", "完成了吗？"), ("remaining", "还需多久？"), ("worked", "这次做过吗？"), ("actual", "记录实际用时（可留空）"), ("actual_measure", "本次新增／累计（可留空）")]}
        else:
            values = dict(completion="完成了") if n == 1 else dict(completion="未完成", remaining="约40分钟", worked="做过", actual="20分钟", actual_measure="本次新增")
            print(label + "：" + "；".join(values.values()))
        raw.append(repr(values)); replies.append(task_reply(view, n, **values))
    answer = input("示例待确认事项：确认／拒绝／稍后决定 ") if args.interactive else "拒绝"
    candidates.append(candidate_reply(view, 1, answer)); raw.append(answer)
    submit = input("输入‘提交’来提交本次复核，也可以先留空：") if args.interactive else "提交"
    raw.append(submit)
    source_ref = "synthetic-statement-" + sha256("\n".join(raw).encode()).hexdigest()
    response, issues = prepare_response(view, current_frame=frame, submitted=submit == "提交", statement_ref=source_ref, task_replies=tuple(replies), batches=tuple(batches), candidate_replies=tuple(candidates))
    # Fixture identity is seeded independently; stdin never authenticates a real
    # account and this assessment never invokes a canonical commit adapter.
    coverage = assess_review(frame, response, caller=CallerIdentity("synthetic-fixture-user", "USER_COMMAND", True), response_at=now)
    print("\n演示结果：" + ("本次复核回答齐全。" if coverage.responses_complete else "本次复核尚有待处理的回答。"))
    if issues: print("有回答需要澄清，请核对完成状态、带单位的单个时间估计，以及实际用时是‘本次新增’还是‘累计’。")
    print("这是合成数据的交互演示。")
    return 0


if __name__ == "__main__": raise SystemExit(main())
