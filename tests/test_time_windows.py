from dataclasses import replace
from datetime import date, datetime, timedelta, timezone
from fractions import Fraction
import random
import unittest
from zoneinfo import ZoneInfo

from src.domain.time_windows import (
    AvailabilityFrame, BEIJING, CalendarEvent, Interval, all_day_interval,
    event_occupancy, forecast_window, merge_intervals, normalize_due,
    today_lock, usable_intervals,
)
from tools.check_contracts import validate_contract
from tools.validate_task_core import ROOT, load_json


DAY = date(2026, 1, 1)
NOW = datetime(2026, 1, 1, 15, tzinfo=BEIJING)


def at(hour, minute=0):
    return datetime(2026, 1, 1, hour, minute, tzinfo=BEIJING)


class TimeWindowTests(unittest.TestCase):
    def event(self, **values):
        result = CalendarEvent("synthetic-event", 1, "synthetic-calendar", "synthetic-account", "synthetic-external", "synthetic-source-record", "EXTERNAL_FIXED", "TIMED", Interval(at(16), at(17)), "BLOCKING", "CONFIRMED")
        return replace(result, **values)

    def test_date_only_due_uses_beijing_2359_with_policy_provenance(self):
        for source in (DAY, DAY.isoformat()):
            due = normalize_due(source, source_ref="synthetic-user-date")
            self.assertEqual(due.instant, at(23, 59))
            self.assertEqual(due.input_kind, "DATE_ONLY")
            self.assertEqual(due.default_policy_ref, "D-075-date-only-2359")
            self.assertEqual(due.original_value, "2026-01-01")

    def test_explicit_instant_offset_precision_and_original_text_are_preserved(self):
        for source in ("2026-01-01T21:45:12.123456-07:00", "2026-01-01T13:00:00Z"):
            due = normalize_due(source, source_ref="synthetic-external-date")
            self.assertEqual(due.original_value, source)
            self.assertEqual(due.instant, datetime.fromisoformat(source))
            self.assertEqual(due.instant.utcoffset(), datetime.fromisoformat(source).utcoffset())
            self.assertEqual(due.input_kind, "EXPLICIT_INSTANT")
            self.assertIsNone(due.default_policy_ref)
        source = datetime(2026, 1, 1, 8, tzinfo=timezone(timedelta(hours=-7)))
        self.assertIs(normalize_due(source, source_ref="synthetic-user-time").instant, source)

    def test_naive_invalid_or_ambiguous_due_is_not_guessed(self):
        for source in (datetime(2026, 1, 1, 20), "2026-01-01T20:00:00", "20:00", "2026-02-30", "tomorrow", 12):
            with self.subTest(source=source), self.assertRaises(ValueError):
                normalize_due(source, source_ref="synthetic-ambiguous")

    def test_natural_day_forecasts_include_today_and_exact_cutoff(self):
        for horizon in (1, 3, 7):
            window = forecast_window(NOW, horizon)
            self.assertEqual(window.start_date, DAY)
            self.assertEqual(window.end_date, DAY + timedelta(days=horizon - 1))
            self.assertEqual(window.cutoff.hour, 23)
            self.assertEqual(window.cutoff.minute, 59)
            self.assertEqual(window.remaining_interval.start, NOW)
        self.assertEqual(forecast_window(NOW, 1).remaining_interval.seconds, 8 * 3600 + 59 * 60)
        for horizon in (True, 2, 3.0):
            with self.assertRaises(ValueError):
                forecast_window(NOW, horizon)

    def test_beijing_midnight_changes_anchor_independent_of_server_day(self):
        before = datetime(2026, 1, 1, 15, 59, tzinfo=timezone.utc)
        after = before + timedelta(minutes=1)
        self.assertEqual(forecast_window(before, 3).start_date, DAY)
        self.assertEqual(forecast_window(after, 3).start_date, DAY + timedelta(days=1))
        self.assertEqual(after.date(), DAY)

    def test_cutoff_passed_has_no_remaining_capacity_but_retains_covered_dates(self):
        for snapshot in (at(23, 59), at(23, 59) + timedelta(seconds=30)):
            window = forecast_window(snapshot, 1)
            self.assertIsNone(window.remaining_interval)
            self.assertEqual(window.start_date, DAY)
            self.assertEqual(window.end_date, DAY)
            self.assertEqual(usable_intervals((Interval(at(8), at(23, 59)),), (), snapshot_at=snapshot, cutoff=window.cutoff), ())

    def test_today_locks_keep_advance_and_complete_separate_and_expire_at_midnight(self):
        for intent in ("ADVANCE", "COMPLETE"):
            lock = today_lock("synthetic-lock", "synthetic-task", 2, intent, "synthetic-user-statement", created_at=NOW)
            self.assertEqual(lock.intent, intent)
            self.assertEqual(lock.expires_at, datetime(2026, 1, 2, tzinfo=BEIJING))
            self.assertFalse(lock.active_at(NOW - timedelta(seconds=1)))
            self.assertTrue(lock.active_at(at(23, 59) + timedelta(seconds=59)))
            self.assertFalse(lock.active_at(lock.expires_at))
            self.assertEqual(lock.task_revision, 2)

    def test_lock_user_day_comes_from_beijing_not_source_offset(self):
        created = datetime(2026, 1, 1, 20, tzinfo=timezone(timedelta(hours=-7)))
        lock = today_lock("synthetic-lock", "synthetic-task", 1, "ADVANCE", "synthetic-user", created_at=created)
        self.assertEqual(lock.expires_at.date(), date(2026, 1, 3))
        self.assertEqual(lock.created_at, created)

    def test_union_and_adjacency_do_not_double_count_capacity(self):
        intervals = (Interval(at(10), at(12)), Interval(at(9), at(11)), Interval(at(12), at(13)), Interval(at(9), at(11)))
        merged = merge_intervals(intervals)
        self.assertEqual(len(merged), 1)
        self.assertEqual(merged[0].seconds, 4 * 3600)
        self.assertEqual(merge_intervals(merged), merged)
        self.assertEqual(merge_intervals(tuple(reversed(intervals))), merged)

    def test_elapsed_time_and_horizon_are_clipped_before_occupancy(self):
        available = (Interval(at(8), at(20)), Interval(at(14), at(22)))
        blocked = (Interval(at(7), at(9)), Interval(at(16), at(17)), Interval(at(16, 30), at(18)), Interval(at(20), at(23)))
        result = usable_intervals(available, blocked, snapshot_at=NOW, cutoff=at(21))
        self.assertEqual([(item.start.astimezone(BEIJING).hour, item.end.astimezone(BEIJING).hour) for item in result], [(15, 16), (18, 20)])
        self.assertEqual(sum(item.seconds for item in result), 3 * 3600)

    def test_full_occupancy_and_verified_empty_availability_are_zero(self):
        self.assertEqual(usable_intervals((Interval(at(8), at(20)),), (Interval(at(7), at(21)),), snapshot_at=NOW, cutoff=at(23)), ())
        frame = AvailabilityFrame("synthetic-known-empty", NOW, at(23, 59), (), (), "READY")
        self.assertEqual(frame.evaluate().seconds, 0)

    def test_partial_second_precision_is_exact(self):
        interval = Interval(NOW, NOW + timedelta(microseconds=123456))
        self.assertEqual(interval.seconds, Fraction(123456, 1000000))
        self.assertEqual(merge_intervals((interval,))[0].seconds, interval.seconds)

    def test_dst_fold_arithmetic_uses_actual_instants(self):
        zone = ZoneInfo("America/New_York")
        start = datetime(2026, 11, 1, 1, 30, tzinfo=zone, fold=0)
        end = datetime(2026, 11, 1, 1, 30, tzinfo=zone, fold=1)
        interval = Interval(start, end)
        self.assertEqual(interval.seconds, 3600)
        self.assertEqual(usable_intervals((interval,), (), snapshot_at=start, cutoff=end)[0].seconds, 3600)

    def test_all_day_events_preserve_exclusive_calendar_end_and_source_zone(self):
        spring = all_day_interval(date(2026, 3, 8), date(2026, 3, 9), source_timezone="America/New_York")
        fall = all_day_interval(date(2026, 11, 1), date(2026, 11, 2), source_timezone="America/New_York")
        self.assertEqual(spring.seconds, 23 * 3600)
        self.assertEqual(fall.seconds, 25 * 3600)
        self.assertEqual(spring.start.hour, 0)
        self.assertEqual(spring.end.hour, 0)
        event = self.event(timing_kind="ALL_DAY", interval=spring, occupancy="NON_BLOCKING")
        self.assertEqual(event_occupancy((event,)).intervals, ())

    def test_duplicate_events_and_overlaps_count_occupancy_once(self):
        first = self.event()
        second = self.event(event_id="synthetic-other", external_id="synthetic-other", interval=Interval(at(16, 30), at(18)))
        snapshot = event_occupancy((first, first, second))
        self.assertEqual(len(snapshot.intervals), 1)
        self.assertEqual(snapshot.intervals[0].seconds, 2 * 3600)
        self.assertEqual(snapshot.unresolved_event_ids, ())

    def test_unknown_and_tentative_occupancy_are_unresolved_not_free(self):
        events = (self.event(occupancy="UNKNOWN"), self.event(event_id="synthetic-tentative", external_id="synthetic-tentative", state="TENTATIVE"))
        snapshot = event_occupancy(events)
        self.assertEqual(snapshot.intervals, ())
        self.assertEqual(snapshot.unresolved_event_ids, ("synthetic-event", "synthetic-tentative"))
        frame = AvailabilityFrame("synthetic-snapshot", NOW, at(20), (Interval(at(15), at(20)),), snapshot.intervals, "UNRESOLVED", snapshot.unresolved_event_ids)
        self.assertIsNone(frame.evaluate().seconds)
        self.assertEqual(frame.evaluate().data_quality, "UNRESOLVED")

    def test_cancelled_or_transparent_events_do_not_cancel_or_complete_tasks(self):
        for event in (self.event(state="CANCELLED"), self.event(occupancy="NON_BLOCKING"), self.event(kind="REMINDER", occupancy="NON_BLOCKING")):
            self.assertEqual(event_occupancy((event,)).intervals, ())
            self.assertIsNone(event.task_ref)

    def test_event_revision_conflicts_and_scoped_source_identity(self):
        event = self.event()
        with self.assertRaises(ValueError):
            event_occupancy((event, replace(event, revision=2)))
        with self.assertRaises(ValueError):
            event_occupancy((event, replace(event, event_id="synthetic-duplicate-source")))
        other_account = replace(event, event_id="synthetic-other-account", scope_ref="synthetic-other-account")
        self.assertEqual(event_occupancy((event, other_account)).intervals[0].seconds, 3600)

    def test_unresolved_or_stale_frame_cannot_supply_canonical_capacity(self):
        for quality in ("UNRESOLVED", "STALE"):
            frame = AvailabilityFrame("synthetic-frame", NOW, at(20), (), (), quality, ("synthetic-source-gap",))
            self.assertIsNone(frame.evaluate().seconds)
        with self.assertRaises(ValueError):
            AvailabilityFrame("synthetic-false-ready", NOW, at(20), (), (), "READY", ("synthetic-gap",))

    def test_capacity_does_not_subtract_reserve_or_modify_source_windows(self):
        original = (Interval(at(15), at(17)),)
        frame = AvailabilityFrame("synthetic-frame", NOW, at(23), original, (), "READY")
        self.assertEqual(frame.evaluate().seconds, 7200)
        self.assertIs(frame.availability, original)
        self.assertEqual(original, (Interval(at(15), at(17)),))

    def test_integer_grid_oracle_matches_interval_union_minus_occupancy(self):
        rng = random.Random(175)
        origin = at(0)
        for _ in range(80):
            pairs = [tuple(sorted(rng.sample(range(61), 2))) for _ in range(10)]
            available, occupied = pairs[:5], pairs[5:]
            intervals = lambda items: tuple(Interval(origin + timedelta(minutes=start), origin + timedelta(minutes=end)) for start, end in items)
            usable = usable_intervals(intervals(available), intervals(occupied), snapshot_at=origin + timedelta(minutes=10), cutoff=origin + timedelta(minutes=50))
            expected = {minute for minute in range(10, 50) if any(start <= minute < end for start, end in available) and not any(start <= minute < end for start, end in occupied)}
            self.assertEqual(sum(item.seconds for item in usable), len(expected) * 60)
            self.assertTrue(all(left.end <= right.start for left, right in zip(usable, usable[1:])))

    def test_records_satisfy_structural_contracts(self):
        records = (("normalized-due", normalize_due(DAY, source_ref="synthetic-user").as_record()), ("forecast-window", forecast_window(NOW, 3).as_record()), ("today-lock", today_lock("synthetic-lock", "synthetic-task", 1, "ADVANCE", "synthetic-user", created_at=NOW).as_record()), ("calendar-event", self.event().as_record()), ("availability", AvailabilityFrame("synthetic-frame", NOW, at(23), (), (), "READY").as_record()))
        for contract, record in records:
            self.assertEqual(validate_contract(contract, record), (), contract)

    def test_invalid_intervals_and_unscoped_planned_events_are_rejected(self):
        for start, end in ((NOW, NOW), (NOW + timedelta(minutes=1), NOW), (datetime(2026, 1, 1), NOW)):
            with self.assertRaises(ValueError):
                Interval(start, end)
        with self.assertRaises(ValueError):
            self.event(kind="PLANNED_WORK")
        with self.assertRaises(ValueError):
            self.event(timing_kind="ALL_DAY")

    def test_schema_cases(self):
        fixture = load_json(ROOT / "tests/fixtures/time_windows/cases.json")
        self.assertIs(fixture["synthetic"], True)
        for case in fixture["cases"]:
            with self.subTest(case=case["id"]):
                self.assertEqual(not validate_contract(case["contract"], case["payload"]), case["valid"])


if __name__ == "__main__":
    unittest.main()
