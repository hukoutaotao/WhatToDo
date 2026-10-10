"""Trusted injectable clocks; the domain never reads machine wall time."""
from dataclasses import dataclass
from datetime import datetime,timezone

from src.domain.time_values import UtcInstant


class SystemClock:
    def now(self):return datetime.now(timezone.utc)


@dataclass(frozen=True)
class FrozenClock:
    instant:datetime

    def __post_init__(self):object.__setattr__(self,'instant',UtcInstant(self.instant).value)

    def now(self):return self.instant
