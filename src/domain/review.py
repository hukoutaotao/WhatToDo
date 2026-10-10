"""Full-frame response coverage and unchanged-estimate verification.

Returned effects are proposed authenticated response data, not persisted Task
mutations. Cumulative actual reports retain their meaning and are not increments.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime
from hashlib import sha256
import json

from src.domain.authorization import CallerIdentity
from src.domain.effort import UserEstimate


def _identity(value):
    if not isinstance(value, str) or not value.strip():
        raise ValueError("A nonblank identity is required")


def _instant(value):
    if not isinstance(value, datetime) or value.utcoffset() is None:
        raise ValueError("An explicit timezone is required")


def _seconds(value):
    if type(value) is not int or value < 0:
        raise ValueError("Nonnegative integer seconds are required")


def _unique(values):
    if len(values) != len(set(values)):
        raise ValueError("Duplicate response/frame identity")


def _key(parts):
    return sha256(json.dumps(parts, separators=(",", ":")).encode()).hexdigest()


@dataclass(frozen=True)
class ReviewTask:
    task_id: str
    revision: int
    importance: int
    completion: str
    disposition: str
    future_relevant: bool
    user_estimate: UserEstimate | None
    work_status: str
    estimate_status: str

    def __post_init__(self):
        _identity(self.task_id)
        if type(self.revision) is not int or self.revision < 1 or type(self.importance) is not int or not 1 <= self.importance <= 5:
            raise ValueError("A current revision and task importance are required")
        if self.completion not in ("COMPLETE", "INCOMPLETE") or self.disposition not in ("ACTIVE", "EXPIRED", "CANCELLED"):
            raise ValueError("Task axes must remain separate")
        if type(self.future_relevant) is not bool or self.work_status not in ("WORKED", "UNTOUCHED", "UNKNOWN") or self.estimate_status not in ("CURRENT", "CHANGED", "UNCERTAIN", "MISSING"):
            raise ValueError("Review eligibility must be explicit")


@dataclass(frozen=True)
class ReviewFrame:
    review_id: str
    revision: int
    queue_snapshot_ref: str
    presented_at: datetime
    tasks: tuple[ReviewTask, ...]
    pending_candidate_ids: tuple[str, ...]

    def __post_init__(self):
        _identity(self.review_id)
        _identity(self.queue_snapshot_ref)
        _instant(self.presented_at)
        if type(self.revision) is not int or self.revision < 1:
            raise ValueError("A positive frame revision is required")
        if not isinstance(self.tasks, tuple) or not isinstance(self.pending_candidate_ids, tuple):
            raise ValueError("Frame membership must be immutable")
        _unique([task.task_id for task in self.tasks])
        _unique(self.pending_candidate_ids)
        for identity in self.pending_candidate_ids:
            _identity(identity)


def questionnaire(frame: ReviewFrame):
    """Keep every queue item; suggestions contain no submitted answer."""
    return {
        "review_id": frame.review_id, "frame_revision": frame.revision,
        "queue_snapshot_ref": frame.queue_snapshot_ref,
        "pending_candidates": [{"candidate_id": identity, "answer": None} for identity in frame.pending_candidate_ids],
        "tasks": [{"task_id": task.task_id, "expected_revision": task.revision, "suggested_completion": task.completion, "completion_answer": None, "remaining_seconds_answer": None, "worked_on_answer": None} for task in sorted(frame.tasks, key=lambda task: (-task.importance, task.task_id))],
    }


@dataclass(frozen=True)
class ActualReport:
    seconds: int
    measure: str

    def __post_init__(self):
        _seconds(self.seconds)
        if self.measure not in ("INCREMENT", "CUMULATIVE"):
            raise ValueError("Preserve actual-report measure rather than guessing")


@dataclass(frozen=True)
class TaskAnswer:
    task_id: str
    expected_revision: int
    completion: str | None = None
    worked_on: bool | None = None
    remaining_seconds: int | None = None
    actual_report: ActualReport | None = None

    def __post_init__(self):
        _identity(self.task_id)
        if type(self.expected_revision) is not int or self.expected_revision < 1:
            raise ValueError("A response must bind a current task revision")
        if self.completion not in (None, "COMPLETE", "INCOMPLETE") or (self.worked_on is not None and type(self.worked_on) is not bool):
            raise ValueError("Answers are explicit or unknown")
        if self.remaining_seconds is not None:
            _seconds(self.remaining_seconds)
        if self.actual_report is not None and not isinstance(self.actual_report, ActualReport):
            raise ValueError("Actual report must preserve measure")


@dataclass(frozen=True)
class EstimateBinding:
    task_id: str
    expected_revision: int
    observation_id: str
    seconds: int

    def __post_init__(self):
        _identity(self.task_id)
        _identity(self.observation_id)
        _seconds(self.seconds)
        if type(self.expected_revision) is not int or self.expected_revision < 1:
            raise ValueError("Estimate binding needs a current revision")


@dataclass(frozen=True)
class UnchangedBatch:
    batch_id: str
    confirmed: bool | None
    members: tuple[EstimateBinding, ...]
    confirm_existing_completion: bool | None = None
    no_work_statement: bool | None = None

    def __post_init__(self):
        _identity(self.batch_id)
        if not isinstance(self.members, tuple) or not self.members:
            raise ValueError("An immutable explicit batch is required")
        _unique([member.task_id for member in self.members])
        for value in (self.confirmed, self.confirm_existing_completion, self.no_work_statement):
            if value is not None and type(value) is not bool:
                raise ValueError("Batch answers are explicit booleans or unanswered")


@dataclass(frozen=True)
class CandidateAnswer:
    candidate_id: str
    resolution: str | None

    def __post_init__(self):
        _identity(self.candidate_id)
        if self.resolution not in (None, "CONFIRMED", "REJECTED"):
            raise ValueError("Candidate decisions are explicit or pending")


@dataclass(frozen=True)
class ReviewResponse:
    review_id: str
    frame_revision: int
    submitted: bool
    user_statement_ref: str | None
    task_answers: tuple[TaskAnswer, ...] = ()
    batches: tuple[UnchangedBatch, ...] = ()
    candidate_answers: tuple[CandidateAnswer, ...] = ()

    def __post_init__(self):
        _identity(self.review_id)
        if type(self.frame_revision) is not int or self.frame_revision < 1 or type(self.submitted) is not bool:
            raise ValueError("Submission/frame identity must be explicit")
        if self.submitted:
            _identity(self.user_statement_ref)
        elif self.user_statement_ref is not None:
            raise ValueError("An unsubmitted suggestion carries no user statement")
        if not all(isinstance(values, tuple) for values in (self.task_answers, self.batches, self.candidate_answers)):
            raise ValueError("Response membership must be immutable")
        _unique([answer.task_id for answer in self.task_answers])
        _unique([batch.batch_id for batch in self.batches])
        _unique([answer.candidate_id for answer in self.candidate_answers])
        _unique([member.task_id for batch in self.batches if batch.confirmed is True for member in batch.members])

    def as_record(self):
        # JSON conversion makes tuple membership arrays for structural checks.
        return {"schema_version": "0.1.0-draft", **json.loads(json.dumps(asdict(self)))}


@dataclass(frozen=True)
class BatchVerification:
    verification_id: str
    task_id: str
    task_revision: int
    batch_id: str
    user_statement_ref: str
    original_estimate: UserEstimate
    verified_at: datetime
    no_work_statement: bool | None

    @property
    def verified_estimate(self):
        original = self.original_estimate
        return UserEstimate(original.seconds, original.observation_id, original.observed_at, self.verified_at)


@dataclass(frozen=True)
class TaskResponseEffect:
    task_id: str
    task_revision: int
    completion: str | None
    user_estimate: UserEstimate | None
    worked_on: bool | None
    actual_report: ActualReport | None


@dataclass(frozen=True)
class ReviewCoverage:
    responses_complete: bool
    pending_task_ids: tuple[str, ...]
    pending_candidate_ids: tuple[str, ...]
    issues: tuple[str, ...]
    verifications: tuple[BatchVerification, ...]
    task_effects: tuple[TaskResponseEffect, ...]
    candidate_effects: tuple[CandidateAnswer, ...]


def assess_review(frame: ReviewFrame, response: ReviewResponse | None, *, caller: CallerIdentity, response_at: datetime) -> ReviewCoverage:
    """Assess all required answers; actual application/commit is separate."""
    _instant(response_at)
    all_tasks = tuple(task.task_id for task in frame.tasks)
    def untouched(issue):
        return ReviewCoverage(False, all_tasks, frame.pending_candidate_ids, (issue,) if issue else (), (), (), ())
    if response is None or not response.submitted:
        return untouched(None)
    if not caller.authenticated or caller.origin != "USER_COMMAND":
        return untouched("USER_SUBMISSION_REQUIRED")
    if response.review_id != frame.review_id or response.frame_revision != frame.revision or response_at < frame.presented_at:
        return untouched("STALE_REVIEW_FRAME")

    tasks = {task.task_id: task for task in frame.tasks}
    answers = {answer.task_id: answer for answer in response.task_answers}
    issues = []
    for answer in response.task_answers:
        if answer.task_id not in tasks:
            issues.append("UNKNOWN_TASK_ANSWER:" + answer.task_id)
    verified = {}
    batch_completion = set()
    for batch in response.batches:
        if batch.confirmed is not True:
            continue
        valid = True
        for binding in batch.members:
            task = tasks.get(binding.task_id)
            answer = answers.get(binding.task_id)
            estimate = task.user_estimate if task else None
            if task is None or task.revision != binding.expected_revision or estimate is None or estimate.observation_id != binding.observation_id or estimate.seconds != binding.seconds or estimate.verified_at > response_at:
                valid = False
            elif task.completion != "INCOMPLETE" or task.disposition != "ACTIVE" or not task.future_relevant or task.estimate_status != "CURRENT" or task.work_status == "WORKED":
                valid = False
            elif (task.work_status != "UNTOUCHED" and batch.no_work_statement is not True) or batch.no_work_statement is False:
                valid = False
            elif answer and (answer.expected_revision != task.revision or answer.worked_on is True or answer.remaining_seconds is not None or answer.completion == "COMPLETE" or (answer.actual_report is not None and answer.actual_report.measure == "INCREMENT" and answer.actual_report.seconds > 0)):
                valid = False
            if binding.task_id in verified:
                valid = False
        if not valid:
            issues.append("INVALID_UNCHANGED_BATCH:" + batch.batch_id)
            continue
        for binding in batch.members:
            task = tasks[binding.task_id]
            verification_id = "verification-" + _key([frame.review_id, frame.revision, batch.batch_id, binding.task_id, binding.observation_id, response.user_statement_ref])
            verified[binding.task_id] = BatchVerification(verification_id, binding.task_id, task.revision, batch.batch_id, response.user_statement_ref, task.user_estimate, response_at, batch.no_work_statement)
            if batch.confirm_existing_completion is True:
                batch_completion.add(binding.task_id)

    effects = []
    pending_tasks = []
    for task in frame.tasks:
        answer = answers.get(task.task_id)
        if answer and answer.expected_revision != task.revision:
            issues.append("STALE_TASK_ANSWER:" + task.task_id)
            pending_tasks.append(task.task_id)
            continue
        if answer and ((answer.completion == "COMPLETE" and answer.remaining_seconds not in (None, 0)) or (answer.worked_on is False and answer.actual_report and answer.actual_report.measure == "INCREMENT" and answer.actual_report.seconds > 0)):
            issues.append("CONFLICTING_TASK_ANSWER:" + task.task_id)
            pending_tasks.append(task.task_id)
            continue
        completion = answer.completion if answer else None
        if completion is None and task.task_id in batch_completion:
            completion = "INCOMPLETE"
        estimate = verified[task.task_id].verified_estimate if task.task_id in verified else None
        if answer and (answer.remaining_seconds is not None or answer.completion == "COMPLETE"):
            seconds = 0 if answer.completion == "COMPLETE" else answer.remaining_seconds
            estimate = UserEstimate(seconds, "estimate-" + _key([response.user_statement_ref, task.task_id, task.revision, seconds]), response_at, response_at)
        requires_remaining = task.future_relevant and task.disposition == "ACTIVE" and (completion or task.completion) == "INCOMPLETE"
        if completion is None or (requires_remaining and estimate is None):
            pending_tasks.append(task.task_id)
        if answer or task.task_id in verified:
            effects.append(TaskResponseEffect(task.task_id, task.revision, completion, estimate, answer.worked_on if answer else None, answer.actual_report if answer else None))

    candidates = {answer.candidate_id: answer for answer in response.candidate_answers}
    for identity in candidates.keys() - set(frame.pending_candidate_ids):
        issues.append("UNKNOWN_CANDIDATE_ANSWER:" + identity)
    pending_candidates = tuple(identity for identity in frame.pending_candidate_ids if identity not in candidates or candidates[identity].resolution is None)
    candidate_effects = tuple(candidates[identity] for identity in frame.pending_candidate_ids if identity in candidates and candidates[identity].resolution is not None)
    complete = not pending_tasks and not pending_candidates and not issues
    return ReviewCoverage(complete, tuple(pending_tasks), pending_candidates, tuple(issues), tuple(verified.values()), tuple(effects), candidate_effects)
