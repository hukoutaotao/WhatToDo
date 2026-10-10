"""Exact forecast classification with separately bound placement evidence.

These functions validate trusted projections/evidence, not a placement solver.
Data quality and proof status remain separate from the three accepted risk labels.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime
from fractions import Fraction
from hashlib import sha256
import json

from src.domain.effort import BudgetSelection
from src.domain.time_windows import AvailabilityFrame, ForecastWindow


def identity(value):
    if not isinstance(value, str) or not value.strip():
        raise ValueError("A nonblank identity is required")


def instant(value):
    if not isinstance(value, datetime) or value.utcoffset() is None:
        raise ValueError("An explicit timezone is required")


def quantity(value):
    if type(value) not in (int, Fraction) or value < 0:
        raise ValueError("Nonnegative exact seconds are required")
    return Fraction(value)


def exact_record(value):
    if value is None:
        return None
    number = Fraction(value)
    return {"numerator": number.numerator, "denominator": number.denominator}


@dataclass(frozen=True)
class RequiredProjection:
    budget: BudgetSelection
    requiredness: str
    seconds: Fraction | int | None
    basis: str
    projection_ref: str
    protected_required_tasks: tuple[str, ...] = ()
    dependency_ref: str | None = None

    def __post_init__(self):
        identity(self.projection_ref)
        if not isinstance(self.budget, BudgetSelection) or self.budget.source in ("NOT_ACTIVE", "COMPLETED"):
            raise ValueError("A projection counts an active parent obligation")
        if self.requiredness not in ("REQUIRED", "OPTIONAL", "EXPIRING") or self.basis not in ("FULL_DUE", "NECESSARY_EARLY", "HARD_PREREQUISITE"):
            raise ValueError("Required projection meaning must be explicit")
        if not isinstance(self.protected_required_tasks, tuple) or len(set(self.protected_required_tasks)) != len(self.protected_required_tasks):
            raise ValueError("Protected task references must be immutable and unique")
        for task in self.protected_required_tasks:
            identity(task)
        if self.basis == "HARD_PREREQUISITE":
            identity(self.dependency_ref)
            if not self.protected_required_tasks:
                raise ValueError("A prerequisite must name the REQUIRED work it protects")
        elif self.requiredness != "REQUIRED" or self.dependency_ref is not None or self.protected_required_tasks:
            raise ValueError("Discretionary work does not become REQUIRED by inclusion")
        if self.budget.seconds is None:
            if self.seconds is not None:
                raise ValueError("Missing work budget is not an invented allocation")
        else:
            amount = quantity(self.seconds)
            if amount > self.budget.seconds or self.basis == "FULL_DUE" and amount != self.budget.seconds:
                raise ValueError("Projection is part of B; full due work counts all of B")

    def as_record(self):
        return {"budget": asdict(self.budget), "requiredness": self.requiredness, "seconds": exact_record(self.seconds), "basis": self.basis, "projection_ref": self.projection_ref, "protected_required_tasks": list(self.protected_required_tasks), "dependency_ref": self.dependency_ref}


def unique_projections(projections):
    if not isinstance(projections, tuple) or not all(isinstance(item, RequiredProjection) for item in projections):
        raise ValueError("An immutable resolved projection is required")
    records = {}
    for item in projections:
        previous = records.get(item.budget.task_id)
        if previous is not None and previous != item:
            raise ValueError("Resolve conflicting allocations/revisions of one parent")
        records[item.budget.task_id] = item
    return tuple(records[key] for key in sorted(records))


def forecast_fingerprint(window, *, snapshot_ref, availability, projections, hard_constraints_ref):
    identity(snapshot_ref)
    identity(hard_constraints_ref)
    if not isinstance(window, ForecastWindow) or not isinstance(availability, AvailabilityFrame):
        raise ValueError("Resolved time and availability contracts are required")
    if availability.snapshot_ref != snapshot_ref or availability.snapshot_at != window.snapshot_at or availability.cutoff != window.cutoff:
        raise ValueError("Forecast capacity must bind the same snapshot and cutoff")
    payload = {"window": window.as_record(), "snapshot_ref": snapshot_ref, "availability": availability.as_record(), "projections": [item.as_record() for item in unique_projections(projections)], "hard_constraints_ref": hard_constraints_ref}
    return sha256(json.dumps(payload, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()).hexdigest()


@dataclass(frozen=True)
class PlacementEvidence:
    input_fingerprint: str
    solver_id: str
    solver_version: str
    outcome: str
    computed_at: datetime
    evidence_ref: str | None
    placement_deficit_seconds: Fraction | int | None = None

    def __post_init__(self):
        for value in (self.input_fingerprint, self.solver_id, self.solver_version):
            identity(value)
        instant(self.computed_at)
        if self.outcome not in ("FEASIBLE", "INFEASIBLE", "TIMEOUT", "UNKNOWN", "ERROR"):
            raise ValueError("A heuristic failure is not proven infeasibility")
        if self.outcome in ("FEASIBLE", "INFEASIBLE"):
            identity(self.evidence_ref)
        elif self.evidence_ref is not None:
            identity(self.evidence_ref)
        if self.placement_deficit_seconds is not None:
            quantity(self.placement_deficit_seconds)
            if self.outcome != "INFEASIBLE":
                raise ValueError("A quantified placement deficit needs an infeasibility proof")

    def as_record(self):
        return {"input_fingerprint": self.input_fingerprint, "solver_id": self.solver_id, "solver_version": self.solver_version, "outcome": self.outcome, "computed_at": self.computed_at.isoformat(), "evidence_ref": self.evidence_ref, "placement_deficit_seconds": exact_record(self.placement_deficit_seconds)}


@dataclass(frozen=True)
class HorizonAssessment:
    snapshot_ref: str
    window: ForecastWindow
    input_fingerprint: str
    assessed_at: datetime
    capacity_seconds: Fraction | None
    required_seconds: Fraction | None
    reserve_seconds: Fraction
    margin_seconds: Fraction | None
    aggregate_deficit_seconds: Fraction | None
    risk: str | None
    data_quality: str
    verification: str
    diagnostics: tuple[str, ...]
    projections: tuple[RequiredProjection, ...]
    placement: PlacementEvidence | None

    def as_record(self):
        return {"snapshot_ref": self.snapshot_ref, "window": self.window.as_record(), "input_fingerprint": self.input_fingerprint, "assessed_at": self.assessed_at.isoformat(), "capacity_seconds": exact_record(self.capacity_seconds), "required_seconds": exact_record(self.required_seconds), "reserve_seconds": exact_record(self.reserve_seconds), "margin_seconds": exact_record(self.margin_seconds), "aggregate_deficit_seconds": exact_record(self.aggregate_deficit_seconds), "risk": self.risk, "data_quality": self.data_quality, "verification": self.verification, "diagnostics": list(self.diagnostics), "projections": [item.as_record() for item in self.projections], "placement": self.placement.as_record() if self.placement else None}


def assess_forecast(window: ForecastWindow, *, snapshot_ref: str, availability: AvailabilityFrame, projections: tuple[RequiredProjection, ...], hard_constraints_ref: str, placement: PlacementEvidence | None, assessed_at: datetime):
    instant(assessed_at)
    if assessed_at < window.snapshot_at:
        raise ValueError("Assessment cannot precede its snapshot")
    fingerprint = forecast_fingerprint(window, snapshot_ref=snapshot_ref, availability=availability, projections=projections, hard_constraints_ref=hard_constraints_ref)
    contributions = unique_projections(projections)
    capacity = availability.evaluate().seconds
    required = None if any(item.seconds is None for item in contributions) else sum((Fraction(item.seconds) for item in contributions), Fraction())
    reserve = Fraction(window.horizon_days * 3600)
    margin = capacity - required if capacity is not None and required is not None else None
    deficit = max(-margin, Fraction()) if margin is not None else None
    quality, diagnostics = availability.data_quality, list(availability.unresolved_refs)
    for item in contributions:
        if item.seconds is None or item.budget.review_needed:
            diagnostics.append("TASK_REVIEW_REQUIRED:" + item.budget.task_id)
            if quality == "READY":
                quality = "UNRESOLVED"
    if placement is not None:
        if not isinstance(placement, PlacementEvidence):
            raise ValueError("Trusted placement evidence must remain separate from JSON claims")
        if placement.input_fingerprint != fingerprint or not window.snapshot_at <= placement.computed_at <= assessed_at:
            quality = "CONFLICTED"
            diagnostics.append("PLACEMENT_SCOPE_OR_TIME_MISMATCH")
        elif placement.outcome == "FEASIBLE" and margin is not None and margin < 0:
            quality = "CONFLICTED"
            diagnostics.append("PLACEMENT_AGGREGATE_CONTRADICTION")
    risk, verification = None, "INCOMPLETE"
    if quality == "READY" and margin is not None:
        if margin < 0:
            risk, verification = "EMERGENCY", "PROVEN_DEFICIT"
        elif placement is not None and placement.outcome == "INFEASIBLE":
            risk, verification = "EMERGENCY", "PROVEN_DEFICIT"
        elif placement is not None and placement.outcome == "FEASIBLE":
            risk = "SAFE" if margin >= reserve else "DANGER"
            verification = "VERIFIED_PLACEMENT"
        else:
            diagnostics.append("PLACEMENT_NOT_VERIFIED")
    return HorizonAssessment(snapshot_ref, window, fingerprint, assessed_at, capacity, required, reserve, margin, deficit, risk, quality, verification, tuple(diagnostics), contributions, placement)


def overall_risk(horizons: tuple[HorizonAssessment, ...]):
    if not isinstance(horizons, tuple) or len(horizons) != 3 or not all(isinstance(item, HorizonAssessment) for item in horizons) or {item.window.horizon_days for item in horizons} != {1, 3, 7}:
        raise ValueError("Exactly the 1/3/7-day horizons are required")
    if len({(item.snapshot_ref, item.window.snapshot_at) for item in horizons}) != 1:
        raise ValueError("Overlapping horizons must share one snapshot")
    risks = {item.risk for item in horizons}
    if "EMERGENCY" in risks:
        return "EMERGENCY"
    if None in risks:
        return None
    return "DANGER" if "DANGER" in risks else "SAFE"


def safe_discretionary_budget(*, capacity_seconds, required_seconds, reserve_seconds):
    """Apply <=40 minutes to the day's aggregate remainder after R and reserve."""
    remainder = quantity(capacity_seconds) - quantity(required_seconds) - quantity(reserve_seconds)
    if remainder < 0:
        raise ValueError("SAFE discretionary selection requires protected reserve")
    return Fraction() if remainder <= 2400 else remainder
