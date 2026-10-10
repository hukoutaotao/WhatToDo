"""Single-count Plan handoff, with references separate from daily allocations."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime
from fractions import Fraction

from src.domain.effort import BudgetSelection, StagePartition
from src.domain.forecast import HorizonAssessment, exact_record, identity, instant, overall_risk, quantity
from src.domain.time_windows import CalendarEvent, PLANNING_ZONE


@dataclass(frozen=True)
class PlanTask:
    budget: BudgetSelection
    title: str
    requiredness: str
    stage_partition: StagePartition | None = None

    def __post_init__(self):
        identity(self.title)
        if not isinstance(self.budget, BudgetSelection) or self.requiredness not in ("REQUIRED", "OPTIONAL", "EXPIRING"):
            raise ValueError("Task-level meaning and parent budget are required")
        if self.stage_partition is not None:
            part = self.stage_partition
            if not isinstance(part, StagePartition) or part.parent_seconds != self.budget.seconds:
                raise ValueError("Stage partition must bind the effective parent B")
            if part.allocations is not None and (len({item.stage_id for item in part.allocations}) != len(part.allocations) or sum((quantity(item.seconds) for item in part.allocations), Fraction()) != self.budget.seconds):
                raise ValueError("Stages partition B exactly once")

    def as_record(self):
        part = self.stage_partition
        return {"budget": asdict(self.budget), "title": self.title, "requiredness": self.requiredness, "stage_partition": {"reason": part.reason, "canonical_disagreement": part.canonical_disagreement, "allocations": [{"stage_id": item.stage_id, "seconds": exact_record(item.seconds)} for item in part.allocations] if part.allocations is not None else None} if part else None}


@dataclass(frozen=True)
class WorkAllocation:
    allocation_id: str
    task_id: str
    task_revision: int
    stage_id: str | None
    seconds: Fraction | int
    objective: str
    work_style: str

    def __post_init__(self):
        for value in (self.allocation_id, self.task_id, self.objective):
            identity(value)
        if type(self.task_revision) is not int or self.task_revision < 1 or quantity(self.seconds) <= 0 or self.work_style not in ("CONTINUOUS", "FRAGMENTABLE", "EITHER"):
            raise ValueError("A concrete positive allocation and work style are required")
        if self.stage_id is not None:
            identity(self.stage_id)

    def as_record(self):
        return {"allocation_id": self.allocation_id, "task_id": self.task_id, "task_revision": self.task_revision, "stage_id": self.stage_id, "seconds": exact_record(self.seconds), "objective": self.objective, "work_style": self.work_style}


@dataclass(frozen=True)
class PlanItem:
    item_id: str
    allocation_ref: str
    role: str
    reason: str | None = None

    def __post_init__(self):
        identity(self.item_id)
        identity(self.allocation_ref)
        if self.role not in ("PROTECT_TODAY", "ADVANCE", "OPTIONAL_ADDON", "FRAGMENTABLE_REFERENCE"):
            raise ValueError("Plan role is separate from Task requiredness")
        if self.reason is not None:
            identity(self.reason)


@dataclass(frozen=True)
class CompletedEmergencyReview:
    initial_plan_ref: str
    review_id: str
    review_commit_ref: str
    user_statement_ref: str
    recomputed_snapshot_ref: str
    recompute_ref: str
    completed_at: datetime

    def __post_init__(self):
        for name, value in asdict(self).items():
            if name != "completed_at":
                identity(value)
        instant(self.completed_at)

    def as_record(self):
        return {**asdict(self), "completed_at": self.completed_at.isoformat()}


@dataclass(frozen=True)
class PlanSnapshot:
    plan_id: str
    snapshot_ref: str
    state_revision: int
    config_version_ref: str
    generated_at: datetime
    horizons: tuple[HorizonAssessment, ...]
    tasks: tuple[PlanTask, ...]
    allocations: tuple[WorkAllocation, ...]
    items: tuple[PlanItem, ...]
    fixed_events: tuple[CalendarEvent, ...] = ()
    emergency_review: CompletedEmergencyReview | None = None

    def __post_init__(self):
        for value in (self.plan_id, self.snapshot_ref, self.config_version_ref):
            identity(value)
        instant(self.generated_at)
        if type(self.state_revision) is not int or self.state_revision < 1:
            raise ValueError("Plan binds a current state revision")
        overall_risk(self.horizons)
        if any(item.snapshot_ref != self.snapshot_ref or not item.window.snapshot_at <= item.assessed_at <= self.generated_at for item in self.horizons):
            raise ValueError("Plan horizons must bind current snapshot/time")
        for values, expected, key in ((self.tasks, PlanTask, lambda item: item.budget.task_id), (self.allocations, WorkAllocation, lambda item: item.allocation_id), (self.items, PlanItem, lambda item: item.item_id), (self.fixed_events, CalendarEvent, lambda item: item.event_id)):
            if not isinstance(values, tuple) or not all(isinstance(item, expected) for item in values) or len({key(item) for item in values}) != len(values):
                raise ValueError("Plan membership must be typed, immutable and unique")
        tasks = {item.budget.task_id: item for item in self.tasks}
        totals, stages, allocation_refs = {}, {}, {item.allocation_id for item in self.allocations}
        for allocation in self.allocations:
            task = tasks.get(allocation.task_id)
            if task is None or task.budget.task_revision != allocation.task_revision or task.budget.seconds is None or task.budget.source in ("COMPLETED", "NOT_ACTIVE"):
                raise ValueError("Allocation requires a known active current parent budget")
            totals[allocation.task_id] = totals.get(allocation.task_id, Fraction()) + quantity(allocation.seconds)
            stages.setdefault(allocation.task_id, set()).add(allocation.stage_id)
            if allocation.stage_id is not None:
                partition = task.stage_partition
                caps = {item.stage_id: item.seconds for item in partition.allocations} if partition and partition.allocations is not None else {}
                consumed = sum((Fraction(item.seconds) for item in self.allocations if item.task_id == allocation.task_id and item.stage_id == allocation.stage_id), Fraction())
                if allocation.stage_id not in caps or consumed > caps[allocation.stage_id]:
                    raise ValueError("Selected stages are part of their derived parent partition")
        for task_id, amount in totals.items():
            if amount > tasks[task_id].budget.seconds or None in stages[task_id] and len(stages[task_id]) > 1:
                raise ValueError("Parent/stage view must not create another allocation")
        if any(item.allocation_ref not in allocation_refs for item in self.items) or {item.allocation_ref for item in self.items} != allocation_refs:
            raise ValueError("Every counted allocation must have a concrete recommendation")
        for horizon in self.horizons:
            for projection in horizon.projections:
                task = tasks.get(projection.budget.task_id)
                if task is None or task.budget != projection.budget or task.requiredness != projection.requiredness:
                    raise ValueError("Forecast work must bind the same Plan task catalogue")
        if self.emergency_review is not None:
            review = self.emergency_review
            if not isinstance(review, CompletedEmergencyReview) or review.initial_plan_ref == self.plan_id or review.recomputed_snapshot_ref != self.snapshot_ref or review.completed_at > self.horizons[0].window.snapshot_at or any(item.risk is None for item in self.horizons):
                raise ValueError("Final emergency needs committed review and known recomputed results")
        today = next(item for item in self.horizons if item.window.horizon_days == 1)
        if self.phase in ("NORMAL", "FINAL_EMERGENCY") and today.capacity_seconds is not None and self.selected_seconds > today.capacity_seconds:
            raise ValueError("A publishable selection cannot exceed today's usable capacity")

    @property
    def risk(self):
        return overall_risk(self.horizons)

    @property
    def phase(self):
        if self.emergency_review is not None:
            return "FINAL_EMERGENCY"
        if self.risk == "EMERGENCY":
            return "PROVISIONAL_EMERGENCY"
        return "UNVERIFIED" if self.risk is None else "NORMAL"

    @property
    def selected_seconds(self):
        return sum((Fraction(item.seconds) for item in self.allocations), Fraction())

    def as_record(self):
        return {"schema_version": "0.1.0-draft", "plan_id": self.plan_id, "snapshot_ref": self.snapshot_ref, "state_revision": self.state_revision, "config_version_ref": self.config_version_ref, "generated_at": self.generated_at.isoformat(), "timezone": PLANNING_ZONE, "overall_risk": self.risk, "phase": self.phase, "horizons": [item.as_record() for item in sorted(self.horizons, key=lambda item: item.window.horizon_days)], "tasks": [item.as_record() for item in self.tasks], "allocations": [item.as_record() for item in self.allocations], "items": [asdict(item) for item in self.items], "selected_seconds": exact_record(self.selected_seconds), "fixed_events": [item.as_record() for item in self.fixed_events], "emergency_review": self.emergency_review.as_record() if self.emergency_review else None}
