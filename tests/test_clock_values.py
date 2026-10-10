"""Time/clock extension: real locale changes cannot reinterpret canonical dates."""
from datetime import date,datetime,timedelta,timezone
import unittest
from zoneinfo import ZoneInfo

from src.adapters.clocks import FrozenClock,SystemClock
from src.application.ports import Clock
from src.domain.time_values import DateOnly,ExplicitInstant,UtcInstant
from src.domain.time_windows import forecast_window


class ClockValueTests(unittest.TestCase):
    def test_system_and_frozen_clocks_satisfy_port_with_utc(self):
        for clock in (SystemClock(),FrozenClock(datetime(2026,1,1,tzinfo=timezone(timedelta(hours=8))))):
            self.assertIsInstance(clock,Clock)
            self.assertEqual(clock.now().utcoffset(),timedelta())
        self.assertEqual(FrozenClock(datetime(2026,1,1,tzinfo=timezone(timedelta(hours=8)))).now(),datetime(2025,12,31,16,tzinfo=timezone.utc))

    def test_beijing_year_rollover_and_three_day_forecast(self):
        clock=FrozenClock(datetime(2026,12,31,16,tzinfo=timezone.utc))
        self.assertEqual(UtcInstant(clock.now()).beijing_date,date(2027,1,1))
        window=forecast_window(clock.now(),3)
        self.assertEqual(window.end_date,date(2027,1,3))
        self.assertEqual(window.cutoff.isoformat(),'2027-01-03T23:59:00+08:00')

    def test_date_only_due_default_and_source_evidence(self):
        due=DateOnly.parse('2026-02-28').as_due(source_ref='synthetic-date')
        self.assertEqual(due.instant.isoformat(),'2026-02-28T23:59:00+08:00')
        self.assertEqual(due.original_value,'2026-02-28')
        self.assertEqual(due.default_policy_ref,'D-075-date-only-2359')

    def test_explicit_source_offset_and_microsecond_precision_survive(self):
        source=ExplicitInstant('2026-01-01T00:00:00.123456+05:30')
        self.assertEqual(source.original_value,'2026-01-01T00:00:00.123456+05:30')
        self.assertEqual(source.utc.isoformat(),'2025-12-31T18:30:00.123456+00:00')
        self.assertEqual(source.utc.value.microsecond,123456)

    def test_dst_fold_instants_are_distinct_after_utc_normalization(self):
        zone=ZoneInfo('America/New_York')
        first=UtcInstant(datetime(2026,11,1,1,30,tzinfo=zone,fold=0))
        second=UtcInstant(datetime(2026,11,1,1,30,tzinfo=zone,fold=1))
        self.assertEqual(second.value-first.value,timedelta(hours=1))
        self.assertLess(first,second)

    def test_naive_ambiguous_and_finer_precision_values_fail(self):
        for value in (datetime(2026,1,1),None,date(2026,1,1)):
            with self.assertRaises(ValueError):UtcInstant(value)
        for value in ('2026-01-01T00:00:00','2026-01-01T00:00:00.1234567Z','2026/01/01','2026-02-30T00:00:00Z'):
            with self.assertRaises(ValueError):ExplicitInstant(value)
        for value in ('20260101','01/01/2026','2026-02-30'):
            with self.assertRaises(ValueError):DateOnly.parse(value)
        with self.assertRaises(ValueError):DateOnly(datetime(2026,1,1,tzinfo=timezone.utc))


if __name__=='__main__':unittest.main()
