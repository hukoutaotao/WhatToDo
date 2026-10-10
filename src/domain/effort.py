"""Pure model-first budget selection and one-parent effort accounting.

No persistence, reference resolution, user confirmation or model fitting occurs
here. Durations are integer seconds; stage allocations retain exact fractions.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from fractions import Fraction
from typing import Iterable


def _seconds(value: int) -> None:
    if type(value) is not int or value < 0:
        raise ValueError("Duration must be nonnegative integer seconds")


def _instant(value: datetime) -> None:
    if not isinstance(value, datetime) or value.utcoffset() is None:
        raise ValueError("An explicit timezone is required")


def _identity(value: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise ValueError("A nonblank identity is required")


@dataclass(frozen=True)
class UserEstimate:
    seconds: int
    observation_id: str
    observed_at: datetime
    verified_at: datetime

    def __post_init__(self):
        _seconds(self.seconds)
        _identity(self.observation_id)
        _instant(self.observed_at)
        _instant(self.verified_at)
        if self.verified_at < self.observed_at:
            raise ValueError("Verification cannot precede its estimate")


@dataclass(frozen=True)
class RemainingPrediction:
    seconds: int
    prediction_id: str
    model_id: str
    model_version: str
    task_revision: int
    computed_at: datetime
    valid_until: datetime
    valid: bool
    applicable: bool

    def __post_init__(self):
        _seconds(self.seconds)
        for identity in (self.prediction_id, self.model_id, self.model_version):
            _identity(identity)
        if type(self.task_revision) is not int or self.task_revision < 1:
            raise ValueError("A positive task revision is required")
        _instant(self.computed_at)
        _instant(self.valid_until)
        if self.valid_until <= self.computed_at:
            raise ValueError("Prediction validity must end after computation")
        if type(self.valid) is not bool or type(self.applicable) is not bool:
            raise ValueError("Prediction flags must be explicit booleans")


@dataclass(frozen=True)
class BudgetSelection:
    task_id: str
    task_revision: int
    seconds: int | None
    source: str
    reason: str
    user_seconds: int | None
    reference_id: str | None
    review_needed: bool

    def __post_init__(self):
        _identity(self.task_id)
        if type(self.task_revision) is not int or self.task_revision < 1:
            raise ValueError("A positive task revision is required")
        if self.seconds is not None:
            _seconds(self.seconds)
        if self.user_seconds is not None:
            _seconds(self.user_seconds)
        if self.source not in ("MODEL", "USER_FALLBACK", "UNKNOWN", "NOT_ACTIVE", "COMPLETED"):
            raise ValueError("Unsupported budget source")
        if type(self.review_needed) is not bool:
            raise ValueError("Review state must be explicit")
        if self.source in ("UNKNOWN", "NOT_ACTIVE") and self.seconds is not None:
            raise ValueError("Unresolved/excluded work is not a zero estimate")
        if self.source in ("MODEL", "USER_FALLBACK", "COMPLETED") and self.seconds is None:
            raise ValueError("A selected budget requires a value")


def select_budget(
    *, task_id: str, task_revision: int, snapshot_at: datetime,
    user_estimate: UserEstimate | None, prediction: RemainingPrediction | None,
    completion: str = "INCOMPLETE", disposition: str = "ACTIVE",
) -> BudgetSelection:
    """Use applicable B even below U; fall back to U without overwriting it."""
    _identity(task_id)
    _instant(snapshot_at)
    if type(task_revision) is not int or task_revision < 1:
        raise ValueError("A positive task revision is required")
    if completion not in ("INCOMPLETE", "COMPLETE"):
        raise ValueError("Completion is binary")
    if disposition not in ("ACTIVE", "CANCELLED", "EXPIRED"):
        raise ValueError("Unsupported disposition")
    canonical = user_estimate.seconds if user_estimate else None
    if completion == "COMPLETE":
        if canonical != 0 or disposition == "EXPIRED":
            raise ValueError("Complete tasks retain explicit zero remaining effort and do not expire")
        return BudgetSelection(task_id, task_revision, 0, "COMPLETED", "CONFIRMED_COMPLETE", canonical, user_estimate.observation_id, False)
    if disposition != "ACTIVE":
        # Excluded workload does not change canonical U to zero.
        return BudgetSelection(task_id, task_revision, None, "NOT_ACTIVE", disposition, canonical, None, False)

    usable_user = user_estimate is not None and user_estimate.verified_at <= snapshot_at
    if prediction is None:
        reason = "MODEL_MISSING"
    elif not prediction.valid:
        reason = "MODEL_INVALID"
    elif not prediction.applicable:
        reason = "MODEL_INAPPLICABLE"
    elif prediction.task_revision != task_revision:
        reason = "MODEL_REVISION_MISMATCH"
    elif prediction.computed_at > snapshot_at:
        reason = "MODEL_FROM_FUTURE"
    elif prediction.valid_until <= snapshot_at:
        reason = "MODEL_STALE"
    else:
        return BudgetSelection(task_id, task_revision, prediction.seconds, "MODEL", "MODEL_APPLICABLE", canonical, prediction.prediction_id, not usable_user)
    if usable_user:
        return BudgetSelection(task_id, task_revision, canonical, "USER_FALLBACK", reason, canonical, user_estimate.observation_id, False)
    unresolved = "USER_FROM_FUTURE" if user_estimate is not None else "USER_MISSING"
    return BudgetSelection(task_id, task_revision, None, "UNKNOWN", reason + ";" + unresolved, canonical, None, True)


@dataclass(frozen=True)
class Stage:
    stage_id: str
    completion: str
    weight: Fraction | None
    user_estimate: UserEstimate | None = None

    def __post_init__(self):
        _identity(self.stage_id)
        if self.completion not in ("INCOMPLETE", "COMPLETE"):
            raise ValueError("Stage completion is binary")
        if self.weight is not None and (not isinstance(self.weight, Fraction) or self.weight <= 0):
            raise ValueError("Stage weights must be positive exact fractions or unknown")


@dataclass(frozen=True)
class StageAllocation:
    stage_id: str
    seconds: Fraction


@dataclass(frozen=True)
class StagePartition:
    parent_seconds: int | None
    allocations: tuple[StageAllocation, ...] | None
    reason: str
    canonical_stage_sum: int | None
    canonical_disagreement: bool


def partition_stages(budget: BudgetSelection, stages: Iterable[Stage]) -> StagePartition:
    """Partition B once; uncertain weights retain the parent-level budget."""
    stage_list = tuple(stages)
    ids = [stage.stage_id for stage in stage_list]
    if len(ids) != len(set(ids)):
        raise ValueError("Duplicate stage identity")
    unfinished = tuple(stage for stage in stage_list if stage.completion == "INCOMPLETE")
    known_estimates = bool(unfinished) and all(stage.user_estimate is not None for stage in unfinished)
    canonical_sum = sum(stage.user_estimate.seconds for stage in unfinished) if known_estimates else None
    disagreement = canonical_sum is not None and budget.user_seconds is not None and canonical_sum != budget.user_seconds
    if budget.seconds is None or budget.source == "NOT_ACTIVE":
        return StagePartition(budget.seconds, None, "NO_ACTIVE_BUDGET", canonical_sum, disagreement)
    if not unfinished:
        return StagePartition(budget.seconds, None, "NO_UNFINISHED_STAGES", canonical_sum, disagreement)
    if any(stage.weight is None for stage in unfinished):
        return StagePartition(budget.seconds, None, "WEIGHTS_UNKNOWN", canonical_sum, disagreement)
    weight_sum = sum((stage.weight for stage in unfinished), Fraction())
    allocations = tuple(StageAllocation(stage.stage_id, Fraction(budget.seconds) * stage.weight / weight_sum) for stage in unfinished)
    return StagePartition(budget.seconds, allocations, "PARTITIONED", canonical_sum, disagreement)


@dataclass(frozen=True)
class BudgetTotal:
    seconds: int | None
    unresolved_task_ids: tuple[str, ...]


def sum_obligations(budgets: Iterable[BudgetSelection]) -> BudgetTotal:
    """Repeated parent references add no work; separate task IDs do."""
    unique: dict[str, BudgetSelection] = {}
    for budget in budgets:
        if not isinstance(budget, BudgetSelection):
            raise ValueError("Only parent obligation budgets may be totaled")
        if budget.task_id in unique and unique[budget.task_id] != budget:
            raise ValueError("Conflicting snapshots for one obligation")
        unique[budget.task_id] = budget
    unresolved = tuple(sorted(budget.task_id for budget in unique.values() if budget.source != "NOT_ACTIVE" and budget.seconds is None))
    if unresolved:
        return BudgetTotal(None, unresolved)
    return BudgetTotal(sum(budget.seconds for budget in unique.values() if budget.source != "NOT_ACTIVE"), ())


@dataclass(frozen=True)
class WorkObservation:
    observation_id: str
    task_id: str
    kind: str
    seconds: int | None
    observed_at: datetime
    recorded_at: datetime
    source_ref: str
    authority_ref: str
    batch_ref: str | None = None

    def __post_init__(self):
        for identity in (self.observation_id, self.task_id, self.source_ref, self.authority_ref):
            _identity(identity)
        _instant(self.observed_at)
        _instant(self.recorded_at)
        if self.recorded_at < self.observed_at:
            raise ValueError("Recording cannot precede observation")
        if self.kind == "UNCHANGED_VERIFICATION":
            if self.seconds is not None:
                raise ValueError("Unchanged verification is not a new numeric estimate")
            _identity(self.batch_ref)
        elif self.kind in ("ACTUAL_WORK", "USER_REMAINING"):
            _seconds(self.seconds)
            if self.batch_ref is not None:
                raise ValueError("Numeric observations are not unchanged batches")
        else:
            raise ValueError("Unsupported observation kind; planned work is not actual")


def append_observation(history: tuple[WorkObservation, ...], observation: WorkObservation) -> tuple[WorkObservation, ...]:
    """Return a new immutable history; exact replay adds no second sample."""
    for existing in history:
        if existing.observation_id == observation.observation_id:
            if existing != observation:
                raise ValueError("Observation identity conflict")
            return history
    return history + (observation,)


def actual_seconds(history: Iterable[WorkObservation], task_id: str) -> int:
    """Sum reported work increments once; estimates/verification add no work."""
    unique: dict[str, WorkObservation] = {}
    for observation in history:
        if observation.observation_id in unique and unique[observation.observation_id] != observation:
            raise ValueError("Observation identity conflict")
        unique[observation.observation_id] = observation
    return sum(observation.seconds for observation in unique.values() if observation.task_id == task_id and observation.kind == "ACTUAL_WORK")
