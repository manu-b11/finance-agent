from datetime import UTC, date, datetime, time
from zoneinfo import ZoneInfo

import pytest

from app.services import reminder_schedule as sched

BOGOTA = ZoneInfo("America/Bogota")
NEW_YORK = ZoneInfo("America/New_York")
NOW = datetime(2026, 11, 9, 15, 0, tzinfo=UTC)


def utc(year, month, day, hour=0, minute=0) -> datetime:
    return datetime(year, month, day, hour, minute, tzinfo=UTC)


def chain(schedule, start, at, zone, after, count):
    result = []
    for _ in range(count):
        after = sched.next_occurrence(schedule, start, at, zone, after)
        result.append(after)
    return result


def monthly(*days):
    return sched.Schedule("monthly", 1, "months", month_days=tuple(days))


def test_monthly_on_the_15th():
    result = chain(monthly(15), date(2026, 11, 9), time(9), BOGOTA, NOW, 3)
    assert result == [utc(2026, 11, 15, 14), utc(2026, 12, 15, 14), utc(2027, 1, 15, 14)]


def test_monthly_skips_the_day_if_todays_time_already_passed():
    after = utc(2026, 11, 15, 14, 30)
    assert sched.next_occurrence(monthly(15), date(2026, 11, 1), time(9), BOGOTA, after) == utc(2026, 12, 15, 14)


def test_monthly_on_two_days():
    result = chain(monthly(5, 20), date(2026, 11, 1), time(9), BOGOTA, NOW, 4)
    assert result == [
        utc(2026, 11, 20, 14),
        utc(2026, 12, 5, 14),
        utc(2026, 12, 20, 14),
        utc(2027, 1, 5, 14),
    ]


def test_day_31_falls_back_to_last_day_of_short_months():
    result = chain(monthly(31), date(2026, 11, 1), time(9), BOGOTA, NOW, 4)
    assert result == [
        utc(2026, 11, 30, 14),
        utc(2026, 12, 31, 14),
        utc(2027, 1, 31, 14),
        utc(2027, 2, 28, 14),
    ]


def test_last_day_of_month_including_leap_february():
    result = chain(monthly(sched.LAST_DAY), date(2026, 11, 1), time(9), BOGOTA, NOW, 4)
    assert result == [
        utc(2026, 11, 30, 14),
        utc(2026, 12, 31, 14),
        utc(2027, 1, 31, 14),
        utc(2027, 2, 28, 14),
    ]
    leap = sched.next_occurrence(
        monthly(sched.LAST_DAY), date(2026, 11, 1), time(9), BOGOTA, utc(2028, 1, 31, 14)
    )
    assert leap == utc(2028, 2, 29, 14)


def test_quincenal_is_the_15th_and_the_last_day():
    schedule = sched.build_schedule("biweekly", None, None, [], [], date(2026, 11, 9))
    assert schedule.month_days == (15, sched.LAST_DAY)
    result = chain(schedule, date(2026, 11, 9), time(9), BOGOTA, NOW, 6)
    assert result == [
        utc(2026, 11, 15, 14),
        utc(2026, 11, 30, 14),
        utc(2026, 12, 15, 14),
        utc(2026, 12, 31, 14),
        utc(2027, 1, 15, 14),
        utc(2027, 1, 31, 14),
    ]
    february = chain(schedule, date(2026, 11, 9), time(9), BOGOTA, utc(2027, 2, 1), 2)
    assert february == [utc(2027, 2, 15, 14), utc(2027, 2, 28, 14)]


def test_weekly_on_several_weekdays():
    schedule = sched.Schedule("weekly", 1, "weeks", weekdays=(0, 3))
    result = chain(schedule, date(2026, 11, 9), time(8), BOGOTA, NOW, 3)
    assert result == [utc(2026, 11, 12, 13), utc(2026, 11, 16, 13), utc(2026, 11, 19, 13)]


def test_every_two_weeks_on_monday_skips_the_alternate_weeks():
    schedule = sched.Schedule("custom", 2, "weeks", weekdays=(0,))
    result = chain(schedule, date(2026, 11, 9), time(8), BOGOTA, NOW, 2)
    assert result == [utc(2026, 11, 23, 13), utc(2026, 12, 7, 13)]


def test_every_three_days():
    schedule = sched.Schedule("custom", 3, "days")
    result = chain(schedule, date(2026, 11, 9), time(8), BOGOTA, NOW, 3)
    assert result == [utc(2026, 11, 12, 13), utc(2026, 11, 15, 13), utc(2026, 11, 18, 13)]


def test_every_two_months_on_the_15th_skips_alternate_months():
    schedule = sched.Schedule("custom", 2, "months", month_days=(15,))
    result = chain(schedule, date(2026, 11, 1), time(9), BOGOTA, NOW, 3)
    assert result == [utc(2026, 11, 15, 14), utc(2027, 1, 15, 14), utc(2027, 3, 15, 14)]


def test_daily():
    schedule = sched.Schedule("daily", 1, "days")
    result = chain(schedule, date(2026, 11, 9), time(9), BOGOTA, NOW, 2)
    assert result == [utc(2026, 11, 10, 14), utc(2026, 11, 11, 14)]


def test_once_returns_the_moment_only_while_in_the_future():
    once = sched.Schedule("once")
    assert sched.next_occurrence(once, date(2026, 11, 20), time(9), BOGOTA, NOW) == utc(2026, 11, 20, 14)
    assert sched.next_occurrence(once, date(2026, 11, 9), time(18), BOGOTA, NOW) == utc(2026, 11, 9, 23)
    assert sched.next_occurrence(once, date(2026, 11, 9), time(8), BOGOTA, NOW) is None
    assert sched.next_occurrence(once, date(2020, 1, 1), time(8), BOGOTA, NOW) is None
    assert sched.next_occurrence(once, date(2026, 11, 20), time(9), BOGOTA, utc(2026, 11, 20, 14)) is None


def test_series_does_not_start_before_its_start_date():
    result = sched.next_occurrence(monthly(15), date(2027, 3, 1), time(9), BOGOTA, NOW)
    assert result == utc(2027, 3, 15, 14)


def test_series_with_a_past_start_resumes_in_the_future():
    result = sched.next_occurrence(monthly(15), date(2025, 1, 1), time(9), BOGOTA, NOW)
    assert result == utc(2026, 11, 15, 14)
    far_past = sched.next_occurrence(
        sched.Schedule("daily", 1, "days"), date(2000, 1, 1), time(9), BOGOTA, NOW
    )
    assert far_past == utc(2026, 11, 10, 14)


def test_wall_clock_time_is_kept_across_daylight_saving_changes():
    daily = sched.Schedule("daily", 1, "days")
    before = utc(2027, 3, 13, 14)
    assert sched.next_occurrence(daily, date(2027, 3, 1), time(9), NEW_YORK, before) == utc(2027, 3, 14, 13)


def test_nonexistent_and_ambiguous_local_times_resolve_deterministically():
    daily = sched.Schedule("daily", 1, "days")
    gap = sched.next_occurrence(daily, date(2027, 3, 1), time(2, 30), NEW_YORK, utc(2027, 3, 13, 12))
    assert gap == utc(2027, 3, 14, 7, 30)
    fold = sched.next_occurrence(daily, date(2027, 10, 1), time(1, 30), NEW_YORK, utc(2027, 11, 6, 12))
    assert fold == utc(2027, 11, 7, 5, 30)


def test_local_date_can_differ_from_utc_date():
    tokyo = ZoneInfo("Asia/Tokyo")
    once = sched.Schedule("once")
    result = sched.next_occurrence(once, date(2026, 11, 10), time(7), tokyo, utc(2026, 11, 9, 12))
    assert result == utc(2026, 11, 9, 22)


def test_build_schedule_defaults_come_from_the_start_date():
    wednesday = date(2026, 11, 11)
    assert sched.build_schedule("weekly", None, None, [], [], wednesday).weekdays == (2,)
    assert sched.build_schedule("monthly", None, None, [], [], date(2026, 11, 20)).month_days == (20,)
    assert sched.build_schedule("custom", 2, "weeks", [], [], wednesday).weekdays == (2,)
    assert sched.build_schedule("custom", 2, "months", [], [], date(2026, 11, 20)).month_days == (20,)
    assert sched.build_schedule("custom", 3, "days", [], [], wednesday) == sched.Schedule("custom", 3, "days")
    assert sched.build_schedule("once", None, None, [], [], wednesday) == sched.Schedule("once")
    assert sched.build_schedule("daily", None, None, [], [], wednesday) == sched.Schedule("daily", 1, "days")


def test_build_schedule_sorts_and_dedupes_days():
    schedule = sched.build_schedule("monthly", None, None, [20, -1, 5, 5], [], date(2026, 11, 1))
    assert schedule.month_days == (5, 20, sched.LAST_DAY)
    weekly = sched.build_schedule("weekly", None, None, [], [3, 0, 3], date(2026, 11, 1))
    assert weekly.weekdays == (0, 3)


def test_resolve_month_days_clamps_and_dedupes():
    assert sched.resolve_month_days(2027, 2, (15, sched.LAST_DAY)) == [date(2027, 2, 15), date(2027, 2, 28)]
    assert sched.resolve_month_days(2028, 2, (29, 30, 31)) == [date(2028, 2, 29)]
    assert sched.resolve_month_days(2026, 4, (31,)) == [date(2026, 4, 30)]


def test_to_utc_uses_the_zone_offset():
    assert sched.to_utc(datetime(2026, 11, 9, 9, 0), BOGOTA) == utc(2026, 11, 9, 14)
