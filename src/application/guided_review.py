"""Offline guided review input/presentation; never authenticates or writes state.

The adapter supplies a resolved frame and captures original user statements.
These helpers emit proposed response data. Independent caller/domain checks and
transactional commit remain mandatory, even when every field parses.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime
from decimal import Decimal
from hashlib import sha256
import json
import re
import unicodedata

from src.domain.review import ActualReport, CandidateAnswer, EstimateBinding, ReviewFrame, ReviewResponse, TaskAnswer, UnchangedBatch

UNKNOWN = frozenset(("", "不知道", "不确定", "跳过", "暂不回答"))


def text(value):
    if not isinstance(value, str) or len(value) > 128:
        raise ValueError("Guided field must be short text")
    return value.strip()


def frame_fingerprint(frame):
    def encode(value):
        if isinstance(value, datetime): return value.isoformat()
        raise TypeError("Unsupported review-frame value")
    return sha256(json.dumps(asdict(frame), sort_keys=True, ensure_ascii=False, default=encode).encode()).hexdigest()


def line_label(value):
    if not isinstance(value, str) or not value.strip() or len(value) > 500:
        raise ValueError("A short readable label is required")
    value = " ".join(value.split())
    return "".join(c if not unicodedata.category(c).startswith("C") else f"\\u{ord(c):04x}" for c in value)


@dataclass(frozen=True)
class GuidedView:
    frame: ReviewFrame
    task_order: tuple[str, ...]
    task_labels: tuple[str, ...]
    candidate_labels: tuple[str, ...]
    scope_fingerprint: str

    def __post_init__(self):
        if not isinstance(self.frame, ReviewFrame) or self.scope_fingerprint != frame_fingerprint(self.frame):
            raise ValueError("View must bind its actual review frame")
        if not all(isinstance(v, tuple) for v in (self.task_order, self.task_labels, self.candidate_labels)) or len(set(self.task_order)) != len(self.task_order) or set(self.task_order) != {t.task_id for t in self.frame.tasks}:
            raise ValueError("View must retain exact full-frame membership")
        if len(self.task_labels) != len(self.task_order) or len(self.candidate_labels) != len(self.frame.pending_candidate_ids):
            raise ValueError("View must label every member")

    def task(self, number):
        if type(number) is not int or not 1 <= number <= len(self.task_order):
            raise ValueError("Unknown task selection")
        identity = self.task_order[number - 1]
        return next(task for task in self.frame.tasks if task.task_id == identity)

    def candidate(self, number):
        if type(number) is not int or not 1 <= number <= len(self.frame.pending_candidate_ids):
            raise ValueError("Unknown candidate selection")
        return self.frame.pending_candidate_ids[number - 1]


def present_review(frame, *, task_labels=None, candidate_labels=None):
    if not isinstance(frame, ReviewFrame): raise ValueError("A resolved review frame is required")
    tasks = tuple(t.task_id for t in sorted(frame.tasks, key=lambda t: (-t.importance, t.task_id)))
    def labels(keys, provided, prefix):
        if provided is None: return tuple(f"{prefix}{i}" for i in range(1, len(keys) + 1))
        if not isinstance(provided, dict) or set(provided) != set(keys):
            raise ValueError("Labels must cover the exact full frame")
        return tuple(line_label(provided[key]) for key in keys)
    return GuidedView(frame, tasks, labels(tasks, task_labels, "任务"), labels(frame.pending_candidate_ids, candidate_labels, "待确认事项"), frame_fingerprint(frame))


def render_review(view):
    lines = ["请核对下面的全部事项。显示的现状是供你参考的，留空表示尚未回答。"]
    for n, title in enumerate(view.task_labels, 1):
        task = view.task(n)
        status = "已完成" if task.completion == "COMPLETE" else "未完成"
        disposition = {"ACTIVE": "进行中", "EXPIRED": "已失效", "CANCELLED": "已取消"}[task.disposition]
        estimate = task.user_estimate
        if estimate is None: remaining = "尚不清楚"
        elif estimate.seconds and estimate.seconds % 3600 == 0: remaining = str(estimate.seconds // 3600) + "小时"
        elif estimate.seconds and estimate.seconds % 60 == 0: remaining = str(estimate.seconds // 60) + "分钟"
        else: remaining = str(estimate.seconds) + "秒"
        lines.append(f"{n}. {title}｜现状：{status}，{disposition}｜上次剩余估计：{remaining}")
    for n, title in enumerate(view.candidate_labels, 1):
        lines.append(f"待确认 {n}. {title}｜尚未采纳")
    lines += ["逐项回答：完成了吗？还需多久？这次做过吗？如记录用时，请另选‘本次新增’或‘累计’。",
              "可以回答‘完成了’、‘未完成’、‘约40分钟’、‘不确定’，也可以先留空。",
              "批量保持不变时，先明确选择事项，再分别确认剩余估计、完成状态和这次没做。",
              "待确认事项可以选择‘确认’、‘拒绝’或稍后决定。最后明确提交本次复核。"]
    return "\n".join(lines)


def _choice(raw, options, field, issues):
    raw = text(raw)
    if raw in UNKNOWN: return None
    if raw not in options:
        issues.append(field + "_NEEDS_CLARIFICATION"); return None
    return options[raw]


def _duration(raw, field, issues):
    raw = text(raw)
    if raw in UNKNOWN: return None
    match = re.fullmatch(r"(?:大约|约)?\s*(\d{1,8}(?:\.\d{1,6})?)\s*(秒|分钟|分|小时)", raw)
    if not match:
        issues.append(field + "_NEEDS_UNIT_OR_SINGLE_ESTIMATE"); return None
    value = Decimal(match[1]) * {"秒": 1, "分钟": 60, "分": 60, "小时": 3600}[match[2]]
    if value != value.to_integral_value():
        issues.append(field + "_NEEDS_WHOLE_SECONDS"); return None
    return int(value)


@dataclass(frozen=True)
class ParsedTask:
    answer: TaskAnswer
    issues: tuple[str, ...]


def task_reply(view, number, *, completion="", remaining="", worked="", actual="", actual_measure=""):
    task, issues = view.task(number), []
    completion = _choice(completion, {"完成": "COMPLETE", "已完成": "COMPLETE", "完成了": "COMPLETE", "未完成": "INCOMPLETE", "没完成": "INCOMPLETE", "还没完成": "INCOMPLETE"}, "COMPLETION", issues)
    remaining = _duration(remaining, "REMAINING", issues)
    worked = _choice(worked, {"做过": True, "做了": True, "是": True, "没做": False, "没做过": False, "否": False}, "WORKED", issues)
    seconds = _duration(actual, "ACTUAL", issues)
    measure = _choice(actual_measure, {"本次新增": "INCREMENT", "累计": "CUMULATIVE"}, "ACTUAL_MEASURE", issues)
    report = None
    if seconds is not None and measure is not None: report = ActualReport(seconds, measure)
    elif seconds is not None or measure is not None: issues.append("ACTUAL_REQUIRES_QUANTITY_AND_MEASURE")
    if completion == "COMPLETE" and remaining not in (None, 0): issues.append("COMPLETE_CONFLICTS_WITH_REMAINING")
    if worked is False and report and report.measure == "INCREMENT" and report.seconds > 0: issues.append("NO_WORK_CONFLICTS_WITH_INCREMENT")
    return ParsedTask(TaskAnswer(task.task_id, task.revision, completion, worked, remaining, report), tuple(issues))


def candidate_reply(view, number, reply):
    issues = []
    value = _choice(reply, {"确认": "CONFIRMED", "拒绝": "REJECTED", "稍后决定": None}, "CANDIDATE", issues)
    return CandidateAnswer(view.candidate(number), value), tuple(issues)


def unchanged_reply(view, numbers, *, batch_id, confirm_estimate="", confirm_completion="", no_work=""):
    if not isinstance(numbers, tuple) or not numbers or len(set(numbers)) != len(numbers):
        raise ValueError("Explicit unique full batch selection is required")
    tasks = tuple(view.task(n) for n in numbers)
    # Do not filter out missing/worked/stale members and silently narrow scope.
    if any(t.user_estimate is None for t in tasks): return None, ("BATCH_ESTIMATE_MISSING",)
    issues = []
    yes = {"是": True, "确认": True, "否": False}
    confirmed = _choice(confirm_estimate, yes, "BATCH_ESTIMATE", issues)
    completion = _choice(confirm_completion, yes, "BATCH_COMPLETION", issues)
    untouched = _choice(no_work, {"没做": True, "做过": False, "做了": False}, "BATCH_NO_WORK", issues)
    members = tuple(EstimateBinding(t.task_id, t.revision, t.user_estimate.observation_id, t.user_estimate.seconds) for t in tasks)
    return UnchangedBatch(batch_id, confirmed, members, completion, untouched), tuple(issues)


def prepare_response(view, *, current_frame, submitted, statement_ref, task_replies=(), batches=(), candidate_replies=()):
    if frame_fingerprint(current_frame) != view.scope_fingerprint:
        raise ValueError("Review frame changed; present the full current frame again")
    if type(submitted) is not bool: raise ValueError("Submission must be an explicit action")
    issues = tuple(i for reply in task_replies for i in reply.issues) + tuple(i for _, notes in batches for i in notes) + tuple(i for _, notes in candidate_replies for i in notes)
    accepted_submission = submitted and not issues
    response = ReviewResponse(view.frame.review_id, view.frame.revision, accepted_submission, statement_ref if accepted_submission else None,
                              tuple(reply.answer for reply in task_replies), tuple(batch for batch, _ in batches if batch is not None), tuple(answer for answer, _ in candidate_replies))
    return response, issues
