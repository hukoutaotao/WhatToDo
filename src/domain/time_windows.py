"""Explicit source time, Beijing user days and finite occupancy arithmetic.

Domain helpers do not fetch a Calendar, expand recurrence or guess availability.
Interval arithmetic uses UTC so DST folds do not create or remove usable time.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time, timedelta, timezone
from fractions import Fraction
import re
from zoneinfo import ZoneInfo


UTC = timezone.utc
PLANNING_ZONE = "Asia/Shanghai"
BEIJING = ZoneInfo(PLANNING_ZONE)


def _identity(value):
    if not isinstance(value, str) or not value.strip():
        raise ValueError("A nonblank identity is required")


def _instant(value):
    if not isinstance(value, datetime) or value.utcoffset() is None:
        raise ValueError("An explicit timezone is required")
    return value.astimezone(UTC)


@dataclass(frozen=True)
class NormalizedDue:
    input_kind: str
    original_value: str
    source_ref: str
    instant: datetime
    default_policy_ref: str | None

    def __post_init__(self):
        _identity(self.source_ref)
        _instant(self.instant)
        if self.input_kind == "DATE_ONLY":
            original_date = date.fromisoformat(self.original_value)
            _identity(self.default_policy_ref)
            if self.instant != datetime.combine(original_date, time(23, 59), BEIJING):
                raise ValueError("Date-only due means Beijing 23:59")
        elif self.input_kind == "EXPLICIT_INSTANT":
            original = datetime.fromisoformat(self.original_value)
            if self.default_policy_ref is not None or _instant(original) != _instant(self.instant):
                raise ValueError("Explicit source instant must be preserved")
        else:
            raise ValueError("Date-only and explicit instants are distinct")

    def as_record(self):
        return {"schema_version": "0.1.0-draft", "input_kind": self.input_kind, "original_value": self.original_value, "source_ref": self.source_ref, "instant": self.instant.isoformat(), "default_policy_ref": self.default_policy_ref}


def normalize_due(value: date | datetime | str, *, source_ref: str):
    _identity(source_ref)
    if not isinstance(value, (date, datetime, str)):
        raise ValueError("A date or explicit instant is required")
    original = value if isinstance(value, str) else value.isoformat()
    if isinstance(value, str):
        if re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
            value = date.fromisoformat(value)
        elif re.fullmatch(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:\d{2})", value):
            value = datetime.fromisoformat(value)
        else:
            raise ValueError("A date or explicit RFC3339 instant is required")
    if isinstance(value, datetime):
        _instant(value)
        return NormalizedDue("EXPLICIT_INSTANT", original, source_ref, value, None)
    if type(value) is date:
        return NormalizedDue("DATE_ONLY", original, source_ref, datetime.combine(value, time(23, 59), BEIJING), "D-075-date-only-2359")
    raise ValueError("A date or explicit instant is required")


@dataclass(frozen=True)
class Interval:
    start: datetime
    end: datetime

    def __post_init__(self):
        if _instant(self.start) >= _instant(self.end):
            raise ValueError("A finite nonempty interval is required")

    @property
    def seconds(self):
        delta = _instant(self.end) - _instant(self.start)
        microseconds = (delta.days * 86400 + delta.seconds) * 1000000 + delta.microseconds
        return Fraction(microseconds, 1000000)

    def as_record(self):
        return {"start": self.start.isoformat(), "end": self.end.isoformat()}


@dataclass(frozen=True)
class ForecastWindow:
    snapshot_at: datetime
    horizon_days: int
    start_date: date
    end_date: date
    cutoff: datetime

    def __post_init__(self):
        _instant(self.snapshot_at)
        if type(self.horizon_days) is not int or self.horizon_days not in (1, 3, 7):
            raise ValueError("Accepted horizons are 1/3/7 natural days")
        anchor = self.snapshot_at.astimezone(BEIJING).date()
        if self.start_date != anchor or self.end_date != anchor + timedelta(days=self.horizon_days - 1) or self.cutoff != datetime.combine(self.end_date, time(23, 59), BEIJING):
            raise ValueError("Forecast bounds must include today's Beijing date")

    @property
    def remaining_interval(self):
        return Interval(self.snapshot_at, self.cutoff) if _instant(self.snapshot_at) < _instant(self.cutoff) else None

    def as_record(self):
        return {"schema_version": "0.1.0-draft", "snapshot_at": self.snapshot_at.isoformat(), "timezone": PLANNING_ZONE, "window_mode": "NATURAL_DAY_INCLUDING_TODAY", "horizon_days": self.horizon_days, "start_date": self.start_date.isoformat(), "end_date": self.end_date.isoformat(), "cutoff": self.cutoff.isoformat()}


def forecast_window(snapshot_at: datetime, horizon_days: int):
    _instant(snapshot_at)
    if type(horizon_days) is not int or horizon_days not in (1, 3, 7):
        raise ValueError("Accepted horizons are 1/3/7 natural days")
    anchor = snapshot_at.astimezone(BEIJING).date()
    end = anchor + timedelta(days=horizon_days - 1)
    return ForecastWindow(snapshot_at, horizon_days, anchor, end, datetime.combine(end, time(23, 59), BEIJING))


@dataclass(frozen=True)
class TodayLock:
    lock_id: str
    task_id: str
    task_revision: int
    intent: str
    authority_ref: str
    created_at: datetime
    expires_at: datetime

    def __post_init__(self):
        for value in (self.lock_id, self.task_id, self.authority_ref):
            _identity(value)
        _instant(self.created_at)
        _instant(self.expires_at)
        if type(self.task_revision) is not int or self.task_revision < 1 or self.intent not in ("COMPLETE", "ADVANCE"):
            raise ValueError("A today lock binds task revision and explicit intent")
        next_date = self.created_at.astimezone(BEIJING).date() + timedelta(days=1)
        if self.expires_at != datetime.combine(next_date, time.min, BEIJING):
            raise ValueError("Today lock ends at next Beijing midnight")

    def active_at(self, now: datetime):
        return _instant(self.created_at) <= _instant(now) < _instant(self.expires_at)

    def as_record(self):
        return {"schema_version": "0.1.0-draft", "lock_id": self.lock_id, "task_id": self.task_id, "task_revision": self.task_revision, "intent": self.intent, "authority_ref": self.authority_ref, "created_at": self.created_at.isoformat(), "expires_at": self.expires_at.isoformat(), "timezone": PLANNING_ZONE}


def today_lock(lock_id, task_id, task_revision, intent, authority_ref, *, created_at):
    _instant(created_at)
    next_date = created_at.astimezone(BEIJING).date() + timedelta(days=1)
    return TodayLock(lock_id, task_id, task_revision, intent, authority_ref, created_at, datetime.combine(next_date, time.min, BEIJING))


def merge_intervals(intervals: tuple[Interval, ...]):
    result = []
    for interval in sorted(intervals, key=lambda item: (_instant(item.start), _instant(item.end))):
        start, end = _instant(interval.start), _instant(interval.end)
        if result and start <= result[-1].end:
            result[-1] = Interval(result[-1].start, max(result[-1].end, end))
        else:
            result.append(Interval(start, end))
    return tuple(result)


def usable_intervals(availability: tuple[Interval, ...], occupancy: tuple[Interval, ...], *, snapshot_at: datetime, cutoff: datetime):
    """Union availability, clip elapsed time/horizon, subtract occupied union."""
    start, end = _instant(snapshot_at), _instant(cutoff)
    if start >= end:
        return ()
    windows = tuple(Interval(max(item.start, start), min(item.end, end)) for item in merge_intervals(availability) if max(item.start, start) < min(item.end, end))
    blocked = merge_intervals(occupancy)
    result = []
    for window in windows:
        cursor = window.start
        for item in blocked:
            if item.end <= cursor:
                continue
            if item.start >= window.end:
                break
            if item.start > cursor:
                result.append(Interval(cursor, min(item.start, window.end)))
            cursor = max(cursor, item.end)
            if cursor >= window.end:
                break
        if cursor < window.end:
            result.append(Interval(cursor, window.end))
    return tuple(result)


def all_day_interval(start_date: date, exclusive_end_date: date, *, source_timezone: str):
    """Calendar date ranges use their own zone and exclusive end, not due 23:59."""
    if type(start_date) is not date or type(exclusive_end_date) is not date:
        raise ValueError("Explicit calendar dates are required")
    zone = ZoneInfo(source_timezone)
    return Interval(datetime.combine(start_date, time.min, zone), datetime.combine(exclusive_end_date, time.min, zone))


@dataclass(frozen=True)
class CalendarEvent:
    event_id: str
    revision: int
    provider: str
    scope_ref: str
    external_id: str
    source_record_ref: str
    kind: str
    timing_kind: str
    interval: Interval
    occupancy: str
    state: str
    task_ref: str | None = None
    authority_ref: str | None = None

    def __post_init__(self):
        for value in (self.event_id, self.provider, self.scope_ref, self.external_id, self.source_record_ref):
            _identity(value)
        if type(self.revision) is not int or self.revision < 1:
            raise ValueError("A positive event revision is required")
        if self.kind not in ("EXTERNAL_FIXED", "PLANNED_WORK", "REMINDER") or self.timing_kind not in ("TIMED", "ALL_DAY") or not isinstance(self.interval, Interval):
            raise ValueError("Explicit event meaning and finite interval are required")
        if self.occupancy not in ("BLOCKING", "NON_BLOCKING", "UNKNOWN") or self.state not in ("CONFIRMED", "TENTATIVE", "CANCELLED"):
            raise ValueError("Do not guess calendar occupancy from event presence")
        if self.timing_kind == "ALL_DAY" and (self.interval.start.time() != time.min or self.interval.end.time() != time.min or self.interval.end.date() <= self.interval.start.date()):
            raise ValueError("All-day events retain explicit local midnight date bounds")
        for value in (self.task_ref, self.authority_ref):
            if value is not None:
                _identity(value)
        if self.kind == "PLANNED_WORK" and (self.task_ref is None or self.authority_ref is None):
            raise ValueError("A planned work event needs accepted task/ownership references")

    @property
    def source_identity(self):
        return self.provider, self.scope_ref, self.external_id

    def as_record(self):
        return {"schema_version": "0.1.0-draft", "event_id": self.event_id, "revision": self.revision, "provider": self.provider, "scope_ref": self.scope_ref, "external_id": self.external_id, "source_record_ref": self.source_record_ref, "kind": self.kind, "timing_kind": self.timing_kind, "interval": self.interval.as_record(), "occupancy": self.occupancy, "state": self.state, "task_ref": self.task_ref, "authority_ref": self.authority_ref}


@dataclass(frozen=True)
class OccupancySnapshot:
    intervals: tuple[Interval, ...]
    unresolved_event_ids: tuple[str, ...]


def event_occupancy(events: tuple[CalendarEvent, ...]):
    identities, sources, blocked, unknown = {}, {}, [], []
    for event in events:
        previous = identities.get(event.event_id)
        if previous is not None:
            if previous != event:
                raise ValueError("Resolve conflicting event revisions before planning")
            continue
        if event.source_identity in sources:
            raise ValueError("One source occurrence cannot be two canonical events")
        identities[event.event_id] = event
        sources[event.source_identity] = event.event_id
        if event.state == "CANCELLED" or event.occupancy == "NON_BLOCKING":
            continue
        if event.occupancy == "UNKNOWN" or event.state == "TENTATIVE":
            unknown.append(event.event_id)
        else:
            blocked.append(event.interval)
    return OccupancySnapshot(merge_intervals(tuple(blocked)), tuple(sorted(unknown)))


@dataclass(frozen=True)
class UsableCapacity:
    intervals: tuple[Interval, ...]
    seconds: Fraction | None
    data_quality: str
    unresolved_refs: tuple[str, ...]


@dataclass(frozen=True)
class AvailabilityFrame:
    snapshot_ref: str
    snapshot_at: datetime
    cutoff: datetime
    availability: tuple[Interval, ...]
    occupancy: tuple[Interval, ...]
    data_quality: str
    unresolved_refs: tuple[str, ...] = ()

    def __post_init__(self):
        _identity(self.snapshot_ref)
        _instant(self.snapshot_at)
        _instant(self.cutoff)
        if not all(isinstance(items, tuple) for items in (self.availability, self.occupancy, self.unresolved_refs)) or not all(isinstance(item, Interval) for item in self.availability + self.occupancy):
            raise ValueError("Availability must have explicit immutable finite bounds")
        if self.data_quality not in ("READY", "UNRESOLVED", "STALE") or (self.data_quality == "READY") != (not self.unresolved_refs):
            raise ValueError("Missing/stale capacity cannot become verified zero or free time")
        if len(set(self.unresolved_refs)) != len(self.unresolved_refs):
            raise ValueError("Duplicate unresolved reference")
        for reference in self.unresolved_refs:
            _identity(reference)

    def evaluate(self):
        intervals = usable_intervals(self.availability, self.occupancy, snapshot_at=self.snapshot_at, cutoff=self.cutoff)
        seconds = sum((item.seconds for item in intervals), Fraction()) if self.data_quality == "READY" else None
        return UsableCapacity(intervals, seconds, self.data_quality, self.unresolved_refs)

    def as_record(self):
        return {"schema_version": "0.1.0-draft", "snapshot_ref": self.snapshot_ref, "snapshot_at": self.snapshot_at.isoformat(), "cutoff": self.cutoff.isoformat(), "availability": [item.as_record() for item in self.availability], "occupancy": [item.as_record() for item in self.occupancy], "data_quality": self.data_quality, "unresolved_refs": list(self.unresolved_refs)}
