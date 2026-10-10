"""Version/shape plus domain-consistency admission, without canonical effects."""
from dataclasses import dataclass
from typing import Protocol
from src.domain.task_aggregate import AggregateIssue, TaskAggregate, assess_semantics


class ShapeAdmission(Protocol):
    status: str
    raw_bytes: bytes

    @property
    def payload(self) -> dict: ...


class TaskCodec(Protocol):
    def admit(self, contract: str, raw: bytes) -> ShapeAdmission: ...


@dataclass(frozen=True)
class TaskAdmission:
    wire: ShapeAdmission
    status: str
    issues: tuple[AggregateIssue, ...]
    aggregate: TaskAggregate | None

    def __bool__(self): raise TypeError("Inspect consistency status; admission is not authority")


def admit_task(codec: TaskCodec, raw: bytes):
    wire = codec.admit("task-aggregate", raw)
    if wire.status != "SUPPORTED_SHAPE": return TaskAdmission(wire, "REJECTED", (), None)
    record = wire.payload
    issues = assess_semantics(record)
    if issues: return TaskAdmission(wire, "REJECTED", issues, None)
    return TaskAdmission(wire, "CONSISTENT_FACTS", (), TaskAggregate.from_record(record))
