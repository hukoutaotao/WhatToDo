"""Goal setup/progress and independent Exam records, without generated workload.

Configuration references do not resolve authority, recurrence or course axes.
Numeric measurements never infer confirmed completion or a Task effort total.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from fractions import Fraction

from src.domain.time_windows import Interval, NormalizedDue


def _identity(value):
    if not isinstance(value, str) or not value.strip():
        raise ValueError("A nonblank identity is required")


def _revision(value):
    if type(value) is not int or value < 1:
        raise ValueError("A positive record revision is required")


def _acceptance(state, reference):
    if state not in ("DRAFT", "ACCEPTED"):
        raise ValueError("Configuration acceptance is explicit")
    if state == "ACCEPTED":
        _identity(reference)
    elif reference is not None:
        raise ValueError("Draft configuration has no complete acceptance grant")


@dataclass(frozen=True)
class Measure:
    amount: Decimal
    unit: str

    def __post_init__(self):
        _identity(self.unit)
        if not isinstance(self.amount, Decimal) or not self.amount.is_finite() or self.amount < 0:
            raise ValueError("A finite nonnegative decimal measurement is required")

    def as_record(self):
        return {"amount": format(self.amount if self.amount else Decimal(0), "f"), "unit": self.unit}


@dataclass(frozen=True)
class GoalTarget:
    description: str
    measure: Measure | None = None

    def __post_init__(self):
        _identity(self.description)
        if self.measure is not None and not isinstance(self.measure, Measure):
            raise ValueError("Target is a known outcome, with optional quantity")

    def as_record(self):
        return {"description": self.description, "measure": self.measure.as_record() if self.measure else None}


@dataclass(frozen=True)
class Cadence:
    kind: str
    description: str
    occurrences_per_period: int | None = None

    def __post_init__(self):
        _identity(self.description)
        if self.kind not in ("NONE", "DAILY", "WEEKLY", "CUSTOM"):
            raise ValueError("Explicit cadence meaning is required")
        if self.occurrences_per_period is not None and (type(self.occurrences_per_period) is not int or self.occurrences_per_period < 1):
            raise ValueError("Occurrence count is positive or unresolved/custom")
        if self.kind == "NONE" and self.occurrences_per_period is not None:
            raise ValueError("No cadence does not specify a recurring count")
        if self.kind in ("DAILY", "WEEKLY") and self.occurrences_per_period is None:
            raise ValueError("A regular cadence needs its explicit count")

    def as_record(self):
        return {"kind": self.kind, "description": self.description, "occurrences_per_period": self.occurrences_per_period}


@dataclass(frozen=True)
class RuleReference:
    rule_id: str
    version: str

    def __post_init__(self):
        _identity(self.rule_id)
        _identity(self.version)

    def as_record(self):
        return {"rule_id": self.rule_id, "version": self.version}


@dataclass(frozen=True)
class GoalPhase:
    phase_id: str
    title: str
    position: int
    target_due: NormalizedDue | None = None

    def __post_init__(self):
        _identity(self.phase_id)
        _identity(self.title)
        _revision(self.position)
        if self.target_due is not None and not isinstance(self.target_due, NormalizedDue):
            raise ValueError("Phase due preserves source-time meaning")

    def as_record(self):
        return {"phase_id": self.phase_id, "title": self.title, "position": self.position, "target_due": self.target_due.as_record() if self.target_due else None}


@dataclass(frozen=True)
class GoalConfig:
    goal_id: str
    revision: int
    title: str
    acceptance: str
    acceptance_ref: str | None
    target: GoalTarget | None
    workload: Measure | None
    progress_measure_kind: str | None
    progress_unit: str | None
    target_due_known: bool
    target_due: NormalizedDue | None
    cadence: Cadence | None
    phases: tuple[GoalPhase, ...] | None
    generation_rules: tuple[RuleReference, ...] | None

    def __post_init__(self):
        _identity(self.goal_id)
        _identity(self.title)
        _revision(self.revision)
        _acceptance(self.acceptance, self.acceptance_ref)
        if self.target is not None and not isinstance(self.target, GoalTarget) or self.workload is not None and not isinstance(self.workload, Measure):
            raise ValueError("Measured target/workload is explicit or unknown")
        if self.progress_measure_kind not in (None, "QUANTITY", "CONFIRMED_OUTCOME"):
            raise ValueError("Progress quantity and confirmed outcome are distinct")
        if self.progress_measure_kind == "QUANTITY":
            _identity(self.progress_unit)
        elif self.progress_unit is not None:
            raise ValueError("Only quantitative progress has a unit")
        if type(self.target_due_known) is not bool or not self.target_due_known and self.target_due is not None or self.target_due is not None and not isinstance(self.target_due, NormalizedDue):
            raise ValueError("Known no horizon differs from unknown horizon")
        if self.cadence is not None and not isinstance(self.cadence, Cadence):
            raise ValueError("Cadence must be an explicit setup object")
        for values, expected in ((self.phases, GoalPhase), (self.generation_rules, RuleReference)):
            if values is not None and (not isinstance(values, tuple) or not all(isinstance(value, expected) for value in values)):
                raise ValueError("Configuration membership must be immutable or unknown")
        if self.phases is not None and (len({phase.phase_id for phase in self.phases}) != len(self.phases) or len({phase.position for phase in self.phases}) != len(self.phases)):
            raise ValueError("Phase identity/position must be unique")
        if self.generation_rules is not None and len({rule.rule_id for rule in self.generation_rules}) != len(self.generation_rules):
            raise ValueError("Resolve duplicate rule versions before activation")
        if self.acceptance == "ACCEPTED" and _missing_setup(self):
            raise ValueError("Partial setup cannot be accepted as complete onboarding")

    def as_record(self):
        return {"schema_version": "0.1.0-draft", "goal_id": self.goal_id, "revision": self.revision, "title": self.title, "acceptance": self.acceptance, "acceptance_ref": self.acceptance_ref, "target": self.target.as_record() if self.target else None, "workload": self.workload.as_record() if self.workload else None, "progress_measure_kind": self.progress_measure_kind, "progress_unit": self.progress_unit, "target_due_known": self.target_due_known, "target_due": self.target_due.as_record() if self.target_due else None, "cadence": self.cadence.as_record() if self.cadence else None, "phases": [phase.as_record() for phase in self.phases] if self.phases is not None else None, "generation_rules": [rule.as_record() for rule in self.generation_rules] if self.generation_rules is not None else None}


def _missing_setup(goal):
    missing = []
    if goal.target is None:
        missing.append("target")
    if goal.workload is None and (goal.target is None or goal.target.measure is None):
        missing.append("workload_or_measured_target")
    if goal.progress_measure_kind is None:
        missing.append("progress_measure")
    if not goal.target_due_known:
        missing.append("target_due_or_explicit_none")
    if goal.cadence is None:
        missing.append("cadence_or_explicit_none")
    if goal.phases is None:
        missing.append("phases_or_explicit_none")
    if goal.generation_rules is None:
        missing.append("generation_rules_or_candidate_only")
    return tuple(missing)


@dataclass(frozen=True)
class GoalReadiness:
    goal_id: str
    goal_revision: int
    configuration_ready: bool
    missing_fields: tuple[str, ...]
    generation_state: str

    def as_record(self):
        return {"schema_version": "0.1.0-draft", "goal_id": self.goal_id, "goal_revision": self.goal_revision, "configuration_ready": self.configuration_ready, "missing_fields": list(self.missing_fields), "generation_state": self.generation_state}


def assess_onboarding(goal: GoalConfig):
    missing = _missing_setup(goal) + (("acceptance",) if goal.acceptance != "ACCEPTED" else ())
    generation = "PENDING" if missing else ("RULE_RESOLUTION_REQUIRED" if goal.generation_rules else "CANDIDATE_ONLY")
    return GoalReadiness(goal.goal_id, goal.revision, not missing, missing, generation)


@dataclass(frozen=True)
class GoalProgress:
    goal_id: str
    goal_revision: int
    observation_id: str
    observed_at: datetime
    source_ref: str
    reported: Measure | None
    completion: str

    def __post_init__(self):
        for value in (self.goal_id, self.observation_id, self.source_ref):
            _identity(value)
        _revision(self.goal_revision)
        if not isinstance(self.observed_at, datetime) or self.observed_at.utcoffset() is None or self.completion not in ("INCOMPLETE", "COMPLETE") or self.reported is not None and not isinstance(self.reported, Measure):
            raise ValueError("Progress observation and confirmed completion are independent")

    def as_record(self):
        return {"schema_version": "0.1.0-draft", "goal_id": self.goal_id, "goal_revision": self.goal_revision, "observation_id": self.observation_id, "observed_at": self.observed_at.isoformat(), "source_ref": self.source_ref, "reported": self.reported.as_record() if self.reported else None, "completion": self.completion}


def measured_target_fraction(goal: GoalConfig, progress: GoalProgress):
    """A display measurement only; do not infer COMPLETE or Task workload."""
    if (goal.goal_id, goal.revision) != (progress.goal_id, progress.goal_revision):
        raise ValueError("Progress belongs to another configuration revision")
    if goal.progress_measure_kind == "QUANTITY" and progress.reported is not None and progress.reported.unit != goal.progress_unit:
        raise ValueError("Progress unit does not match its accepted measure")
    target = goal.target.measure if goal.target else None
    if goal.progress_measure_kind != "QUANTITY" or target is None or progress.reported is None or target.unit != progress.reported.unit or target.amount == 0:
        return None
    # Fraction avoids ambient Decimal precision changing this exact ratio.
    return Fraction(progress.reported.amount) / Fraction(target.amount)


@dataclass(frozen=True)
class Milestone:
    milestone_id: str
    goal_id: str
    goal_revision: int
    title: str
    position: int
    phase_ref: str | None
    target: Measure | None
    target_due: NormalizedDue | None

    def __post_init__(self):
        for value in (self.milestone_id, self.goal_id, self.title):
            _identity(value)
        _revision(self.goal_revision)
        _revision(self.position)
        if self.phase_ref is not None:
            _identity(self.phase_ref)
        if self.target is not None and not isinstance(self.target, Measure) or self.target_due is not None and not isinstance(self.target_due, NormalizedDue):
            raise ValueError("Milestone target/due retains its own meaning")

    def as_record(self):
        return {"schema_version": "0.1.0-draft", "milestone_id": self.milestone_id, "goal_id": self.goal_id, "goal_revision": self.goal_revision, "title": self.title, "position": self.position, "phase_ref": self.phase_ref, "target": self.target.as_record() if self.target else None, "target_due": self.target_due.as_record() if self.target_due else None}


def validate_milestones(goal: GoalConfig, milestones: tuple[Milestone, ...]):
    """Check explicit scope/phase references without adding milestone workload."""
    if not isinstance(milestones, tuple) or not all(isinstance(item, Milestone) for item in milestones):
        raise ValueError("Immutable milestone scope is required")
    if len({item.milestone_id for item in milestones}) != len(milestones) or len({item.position for item in milestones}) != len(milestones):
        raise ValueError("Resolve duplicate milestone identity/position")
    phases = {phase.phase_id for phase in goal.phases} if goal.phases is not None else set()
    issues = []
    for item in milestones:
        if (item.goal_id, item.goal_revision) != (goal.goal_id, goal.revision):
            issues.append("STALE_MILESTONE_SCOPE:" + item.milestone_id)
        if item.phase_ref is not None and item.phase_ref not in phases:
            issues.append("UNRESOLVED_PHASE_REFERENCE:" + item.milestone_id)
    return tuple(issues)


@dataclass(frozen=True)
class ExamCoverage:
    axis_ref: str
    axis_version: str
    start_unit_ref: str
    end_unit_ref: str

    def __post_init__(self):
        for value in (self.axis_ref, self.axis_version, self.start_unit_ref, self.end_unit_ref):
            _identity(value)

    def as_record(self):
        return {"axis_ref": self.axis_ref, "axis_version": self.axis_version, "start_unit_ref": self.start_unit_ref, "end_unit_ref": self.end_unit_ref}


@dataclass(frozen=True)
class Exam:
    exam_id: str
    revision: int
    title: str
    course_ref: str | None
    acceptance: str
    acceptance_ref: str | None
    source_ref: str
    timing_kind: str
    exam_date: date | None
    interval: Interval | None
    coverage: ExamCoverage | None = None

    def __post_init__(self):
        for value in (self.exam_id, self.title, self.source_ref):
            _identity(value)
        _revision(self.revision)
        _acceptance(self.acceptance, self.acceptance_ref)
        if self.course_ref is not None:
            _identity(self.course_ref)
        if self.coverage is not None and not isinstance(self.coverage, ExamCoverage):
            raise ValueError("Exam coverage requires explicit axis/unit references")
        if self.timing_kind == "UNKNOWN":
            valid = self.exam_date is None and self.interval is None
        elif self.timing_kind == "DATE_ONLY":
            valid = type(self.exam_date) is date and self.interval is None
        elif self.timing_kind == "EXACT_EVENT":
            valid = self.exam_date is None and isinstance(self.interval, Interval)
        else:
            valid = False
        if not valid:
            raise ValueError("Exam date-only context must not invent an exact exam time")

    def as_record(self):
        return {"schema_version": "0.1.0-draft", "exam_id": self.exam_id, "revision": self.revision, "title": self.title, "course_ref": self.course_ref, "acceptance": self.acceptance, "acceptance_ref": self.acceptance_ref, "source_ref": self.source_ref, "timing_kind": self.timing_kind, "exam_date": self.exam_date.isoformat() if self.exam_date else None, "interval": self.interval.as_record() if self.interval else None, "coverage": self.coverage.as_record() if self.coverage else None}
