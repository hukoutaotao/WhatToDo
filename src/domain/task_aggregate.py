"""Lossless composed Task facts; no provider, schema SDK or mutation authority.

Inputs to assess_semantics have passed the version/shape contract separately.
Historical estimates and predictions remain present even when not selected.
"""
from dataclasses import dataclass
from datetime import datetime, timezone
from fractions import Fraction
import json
import re

from src.domain.effort import RemainingPrediction, Stage, UserEstimate, partition_stages, select_budget
from src.domain.time_windows import NormalizedDue


INSTANT = re.compile(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d{1,6})?(?:Z|[+-]\d{2}:\d{2})\Z")


def instant(value):
    if not isinstance(value, str) or not INSTANT.fullmatch(value):
        raise ValueError("Explicit microsecond-or-coarser RFC3339 time required")
    result = datetime.fromisoformat(value)
    if result.utcoffset() is None: raise ValueError("Explicit timezone required")
    return result


def user_estimate(value):
    if value is None: return None
    return UserEstimate(value["seconds"], value["observation_id"], instant(value["observed_at"]), instant(value["verified_at"]))


def prediction(value):
    if value is None: return None
    return RemainingPrediction(value["seconds"], value["prediction_id"], value["model_ref"]["id"], value["model_ref"]["version"], value["task_revision"], instant(value["computed_at"]), instant(value["valid_until"]), value["valid"], value["applicable"])


def stages(record):
    return tuple(Stage(s["stage_id"], s["completion"], Fraction(str(s["weight"])) if s["weight"] is not None else None, user_estimate(s["user_remaining"])) for s in record["effort"]["stages"])


@dataclass(frozen=True, order=True)
class AggregateIssue:
    path: str
    constraint: str


def _pointer(record, path):
    if not isinstance(path, str) or not path.startswith("/"): raise ValueError("Field pointer required")
    current = record
    for encoded in path[1:].split("/"):
        if re.search(r"~(?![01])", encoded): raise ValueError("Invalid pointer escape")
        key = encoded.replace("~1", "/").replace("~0", "~")
        if isinstance(current, list):
            if not re.fullmatch(r"0|[1-9][0-9]*", key): raise ValueError("Explicit array index required")
            current = current[int(key)]
        elif isinstance(current, dict): current = current[key]
        else: raise ValueError("Pointer crosses a scalar")
    return current


def assess_semantics(record):
    """Checks cross-field consistency; reference identity is not resolution."""
    issues = []
    def reject(path, constraint): issues.append(AggregateIssue(path, constraint))
    core, effort = record["core"], record["effort"]
    integer_fields = [("/core/revision", core["revision"]), ("/effort/task_revision", effort["task_revision"]), ("/core/importance", core["importance"])]
    integer_fields += [("/core/difficulty/"+key, value) for key,value in core["difficulty"].items()]
    integer_fields += [("/stage_details/"+str(i)+"/revision", s["revision"]) for i,s in enumerate(record["stage_details"])]
    integer_fields.append(("/work/minimum_session_seconds", record["work"]["minimum_session_seconds"]))
    if record["work"]["total_estimate"] is not None: integer_fields.append(("/work/total_estimate/seconds", record["work"]["total_estimate"]["seconds"]))
    for path,value in integer_fields:
        if value is not None and type(value) is not int: reject(path, "INTEGER_REPRESENTATION")
    for field, other in (("task_id", "task_id"), ("revision", "task_revision"), ("completion", "completion"), ("disposition", "disposition")):
        if core[field] != effort[other]: reject("/effort/" + other, "CORE_EFFORT_SCOPE")
    for path, value in [("/effort/user_remaining", effort["user_remaining"])]+[("/effort/stages/"+str(i)+"/user_remaining", s["user_remaining"]) for i,s in enumerate(effort["stages"])]:
        try: user_estimate(value)
        except (ValueError, OverflowError): reject(path, "ESTIMATE_TIME_OR_ORDER")
    try: prediction(effort["prediction"])
    except (ValueError, OverflowError): reject("/effort/prediction", "PREDICTION_TIME_OR_ORDER")
    # Stale predictions are retained and rejected by select_budget at use time.
    try: stages(record)
    except (ValueError, OverflowError): reject("/effort/stages", "STAGE_VALUE")
    stage_ids = [s["stage_id"] for s in effort["stages"]]
    detail_ids = [s["stage_id"] for s in record["stage_details"]]
    if len(set(stage_ids)) != len(stage_ids): reject("/effort/stages", "DUPLICATE_STAGE")
    if len(set(detail_ids)) != len(detail_ids): reject("/stage_details", "DUPLICATE_STAGE")
    if set(stage_ids) != set(detail_ids): reject("/stage_details", "STAGE_SCOPE")
    timing = record["timing"]
    for field in ("created_at", "completed_at"):
        if timing[field] is not None:
            try: instant(timing[field])
            except ValueError: reject("/timing/" + field, "TIME_PRECISION")
    if core["completion"] == "INCOMPLETE" and timing["completed_at"] is not None: reject("/timing/completed_at", "INCOMPLETE_CURRENT_COMPLETION_TIME")
    release = timing["release"]
    if release is not None:
        try:
            if instant(release["instant"]).astimezone(timezone.utc) != instant(release["original_value"]).astimezone(timezone.utc):
                reject("/timing/release", "RELEASE_SOURCE_TIME")
        except ValueError: reject("/timing/release", "TIME_PRECISION")
    deadline = timing["deadline"]
    if deadline is not None:
        due = deadline["value"]
        try:
            if due["input_kind"] == "EXPLICIT_INSTANT": instant(due["original_value"])
            NormalizedDue(due["input_kind"], due["original_value"], due["source_ref"], instant(due["instant"]), due["default_policy_ref"])
        except ValueError: reject("/timing/deadline", "DEADLINE_SOURCE_TIME")
    total = record["work"]["total_estimate"]
    if total is not None:
        try: instant(total["observed_at"])
        except ValueError: reject("/work/total_estimate", "TIME_PRECISION")
    # No comparisons between original total, current U, actual increments or B.
    seen = set()
    for i, item in enumerate(record["provenance"]):
        path = "/provenance/" + str(i)
        if item["field"] in seen: reject(path, "DUPLICATE_FIELD_PROVENANCE")
        seen.add(item["field"])
        try:
            if item["field"].startswith("/provenance") or item["field"].startswith("/schema_version"):
                raise ValueError("Evidence describes facts rather than itself or a wire version")
            _pointer(record, item["field"])
        except (KeyError, IndexError, ValueError): reject(path, "FIELD_POINTER")
    return tuple(sorted(set(issues)))


@dataclass(frozen=True)
class TaskAggregate:
    """Validated immutable facts. Construction does not resolve or authorize them."""
    _snapshot_json: str

    def __post_init__(self):
        try:
            value = json.loads(self._snapshot_json)
            if assess_semantics(value): raise ValueError("Inconsistent Task aggregate")
        except (KeyError, TypeError, IndexError, ValueError):
            raise ValueError("Inconsistent Task aggregate") from None

    @classmethod
    def from_record(cls, record):
        return cls(json.dumps(record, ensure_ascii=False, allow_nan=False, separators=(",", ":")))

    def as_record(self): return json.loads(self._snapshot_json)

    def budget(self, *, at):
        value = self.as_record();core, effort = value["core"], value["effort"]
        return select_budget(task_id=core["task_id"], task_revision=core["revision"], snapshot_at=at, user_estimate=user_estimate(effort["user_remaining"]), prediction=prediction(effort["prediction"]), completion=core["completion"], disposition=core["disposition"])

    def stage_partition(self, *, at):
        return partition_stages(self.budget(at=at), stages(self.as_record()))

    @property
    def release_due_window(self):
        """Preserve impossible explicit facts; this is not a solver verdict."""
        timing = self.as_record()["timing"]
        if timing["release"] is None or timing["deadline"] is None: return "UNKNOWN"
        release = instant(timing["release"]["instant"]).astimezone(timezone.utc)
        due = instant(timing["deadline"]["value"]["instant"]).astimezone(timezone.utc)
        if due < release: return "REVERSED"
        if due == release: return "ZERO_WIDTH"
        return "ORDERED"
