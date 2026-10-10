"""Explicit instants/date-only values, independent of machine locale and clocks."""
from dataclasses import dataclass
from datetime import date,datetime,timezone
import re

from src.domain.time_windows import BEIJING,normalize_due

RFC3339=re.compile(r'\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d{1,6})?(?:Z|[+-]\d{2}:\d{2})\Z')
DATE_ONLY=re.compile(r'\d{4}-\d{2}-\d{2}\Z')


@dataclass(frozen=True,order=True)
class UtcInstant:
    value:datetime

    def __post_init__(self):
        if not isinstance(self.value,datetime) or self.value.utcoffset() is None:raise ValueError('An explicit timezone-aware instant is required')
        object.__setattr__(self,'value',self.value.astimezone(timezone.utc))

    @property
    def beijing_date(self):return self.value.astimezone(BEIJING).date()

    def isoformat(self):return self.value.isoformat()


@dataclass(frozen=True)
class ExplicitInstant:
    original_value:str

    def __post_init__(self):
        if not isinstance(self.original_value,str) or not RFC3339.fullmatch(self.original_value):raise ValueError('Explicit RFC3339 at microsecond-or-coarser precision is required')
        UtcInstant(datetime.fromisoformat(self.original_value))

    @property
    def utc(self):return UtcInstant(datetime.fromisoformat(self.original_value))


@dataclass(frozen=True,order=True)
class DateOnly:
    value:date

    def __post_init__(self):
        if type(self.value) is not date:raise ValueError('An explicit date-only value is required')

    @classmethod
    def parse(cls,text):
        if not isinstance(text,str) or not DATE_ONLY.fullmatch(text):raise ValueError('An explicit ISO date is required')
        return cls(date.fromisoformat(text))

    def as_due(self,*,source_ref):return normalize_due(self.value,source_ref=source_ref)
