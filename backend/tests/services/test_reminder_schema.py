from datetime import date, time

import pytest
from pydantic import ValidationError

from app.schemas.reminder import Frequency, ReminderCreate, ReminderUpdate, Weekday

BASE = {"concept": "Pagar arriendo", "remind_on": "2026-11-09", "remind_at": "09:00"}


def make(**fields) -> ReminderCreate:
    return ReminderCreate.model_validate({**BASE, **fields})


def test_defaults_to_a_single_reminder():
    reminder = make()
    assert reminder.frequency == Frequency.ONCE
    assert reminder.remind_on == date(2026, 11, 9)
    assert reminder.remind_at == time(9, 0)
    assert reminder.month_days == [] and reminder.weekdays == []


def test_seconds_are_dropped_from_the_time():
    assert make(remind_at="09:00:45").remind_at == time(9, 0)


def test_month_days_are_sorted_with_last_day_at_the_end():
    reminder = make(frequency="monthly", month_days=[-1, 31, 15, 15])
    assert reminder.month_days == [15, 31, -1]


def test_weekdays_are_sorted_and_deduped():
    reminder = make(frequency="weekly", weekdays=["thursday", "monday", "thursday"])
    assert reminder.weekdays == [Weekday.MONDAY, Weekday.THURSDAY]


@pytest.mark.parametrize(
    "fields",
    [
        {"frequency": "daily"},
        {"frequency": "weekly"},
        {"frequency": "weekly", "weekdays": ["friday"]},
        {"frequency": "biweekly"},
        {"frequency": "monthly"},
        {"frequency": "monthly", "month_days": [15]},
        {"frequency": "custom", "interval_count": 3, "interval_unit": "days"},
        {"frequency": "custom", "interval_count": 2, "interval_unit": "weeks", "weekdays": ["monday"]},
        {"frequency": "custom", "interval_count": 1, "interval_unit": "months", "month_days": [-1]},
        {"frequency": "custom", "interval_count": 365, "interval_unit": "days"},
        {"frequency": "custom", "interval_count": 52, "interval_unit": "weeks"},
        {"frequency": "custom", "interval_count": 24, "interval_unit": "months"},
    ],
)
def test_valid_recurrences(fields):
    make(**fields)


@pytest.mark.parametrize(
    "fields",
    [
        {"frequency": "monthly", "month_days": [0]},
        {"frequency": "monthly", "month_days": [32]},
        {"frequency": "monthly", "month_days": [-2]},
        {"frequency": "once", "month_days": [15]},
        {"frequency": "daily", "month_days": [15]},
        {"frequency": "weekly", "month_days": [15]},
        {"frequency": "biweekly", "month_days": [10]},
        {"frequency": "monthly", "weekdays": ["monday"]},
        {"frequency": "once", "weekdays": ["monday"]},
        {"frequency": "daily", "interval_count": 2, "interval_unit": "days"},
        {"frequency": "monthly", "interval_count": 2},
        {"frequency": "custom"},
        {"frequency": "custom", "interval_count": 3},
        {"frequency": "custom", "interval_unit": "days"},
        {"frequency": "custom", "interval_count": 366, "interval_unit": "days"},
        {"frequency": "custom", "interval_count": 53, "interval_unit": "weeks"},
        {"frequency": "custom", "interval_count": 25, "interval_unit": "months"},
        {"frequency": "custom", "interval_count": 0, "interval_unit": "days"},
        {"frequency": "custom", "interval_count": 3, "interval_unit": "days", "weekdays": ["monday"]},
        {"frequency": "custom", "interval_count": 3, "interval_unit": "days", "month_days": [1]},
        {"frequency": "custom", "interval_count": 2, "interval_unit": "months", "weekdays": ["monday"]},
        {"frequency": "custom", "interval_count": 2, "interval_unit": "weeks", "month_days": [1]},
        {"frequency": "yearly"},
        {"concept": "   "},
        {"remind_at": "25:00"},
        {"remind_on": "mañana"},
        {"user_id": "x"},
    ],
)
def test_invalid_recurrences_are_rejected(fields):
    with pytest.raises(ValidationError):
        make(**fields)


def test_update_requires_at_least_one_field_and_no_nulls():
    with pytest.raises(ValidationError):
        ReminderUpdate()
    with pytest.raises(ValidationError):
        ReminderUpdate(concept=None)
    with pytest.raises(ValidationError):
        ReminderUpdate(month_days=None)
    with pytest.raises(ValidationError):
        ReminderUpdate(user_id="x")
    assert ReminderUpdate(month_days=[]).month_days == []
    assert ReminderUpdate(remind_at="10:30").remind_at == time(10, 30)
