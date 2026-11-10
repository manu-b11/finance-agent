import calendar
from collections.abc import Iterator
from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta
from zoneinfo import ZoneInfo

LAST_DAY = -1
QUINCENAL_DAYS = (15, LAST_DAY)
MAX_SCAN_DAYS = 800
MAX_SCAN_MONTHS = 600


@dataclass(frozen=True)
class Schedule:
    frequency: str
    interval_count: int | None = None
    interval_unit: str | None = None
    month_days: tuple[int, ...] = ()
    weekdays: tuple[int, ...] = ()


def _sorted_month_days(days: tuple[int, ...] | list[int]) -> tuple[int, ...]:
    return tuple(sorted(set(days), key=lambda day: (day == LAST_DAY, day)))


def build_schedule(
    frequency: str,
    interval_count: int | None,
    interval_unit: str | None,
    month_days: list[int],
    weekdays: list[int],
    start: date,
) -> Schedule:
    if frequency == "once":
        return Schedule("once")
    if frequency == "daily":
        return Schedule("daily", 1, "days")
    if frequency == "weekly":
        return Schedule("weekly", 1, "weeks", weekdays=tuple(sorted(set(weekdays))) or (start.weekday(),))
    if frequency == "biweekly":
        return Schedule("biweekly", 1, "months", month_days=_sorted_month_days(QUINCENAL_DAYS))
    if frequency == "monthly":
        return Schedule(
            "monthly", 1, "months", month_days=_sorted_month_days(month_days) or (start.day,)
        )
    if interval_unit == "days":
        return Schedule("custom", interval_count, "days")
    if interval_unit == "weeks":
        return Schedule(
            "custom",
            interval_count,
            "weeks",
            weekdays=tuple(sorted(set(weekdays))) or (start.weekday(),),
        )
    return Schedule(
        "custom",
        interval_count,
        "months",
        month_days=_sorted_month_days(month_days) or (start.day,),
    )


def resolve_month_days(year: int, month: int, month_days: tuple[int, ...]) -> list[date]:
    last = calendar.monthrange(year, month)[1]
    days = {last if day == LAST_DAY else min(day, last) for day in month_days}
    return [date(year, month, day) for day in sorted(days)]


def matching_dates(schedule: Schedule, start: date, from_date: date) -> Iterator[date]:
    if schedule.frequency == "once":
        if start >= from_date:
            yield start
        return
    first = max(start, from_date)
    step = schedule.interval_count or 1
    if schedule.interval_unit == "days":
        index = -((start - first).days // step)
        while True:
            yield start + timedelta(days=index * step)
            index += 1
    elif schedule.interval_unit == "weeks":
        base = start - timedelta(days=start.weekday())
        for offset in range(MAX_SCAN_DAYS):
            day = first + timedelta(days=offset)
            if ((day - base).days // 7) % step == 0 and day.weekday() in schedule.weekdays:
                yield day
    elif schedule.interval_unit == "months":
        year, month = first.year, first.month
        for _ in range(MAX_SCAN_MONTHS):
            if ((year - start.year) * 12 + (month - start.month)) % step == 0:
                for day in resolve_month_days(year, month, schedule.month_days):
                    if day >= first:
                        yield day
            month += 1
            if month > 12:
                month, year = 1, year + 1


def to_utc(local: datetime, zone: ZoneInfo) -> datetime:
    return local.replace(tzinfo=zone).astimezone(UTC)


def next_occurrence(
    schedule: Schedule, start: date, at: time, zone: ZoneInfo, after: datetime
) -> datetime | None:
    """Primera ejecución posterior a `after`, calculada en hora local y devuelta en UTC (RB-14)."""
    from_date = after.astimezone(zone).date() - timedelta(days=1)
    for day in matching_dates(schedule, start, from_date):
        moment = to_utc(datetime.combine(day, at), zone)
        if moment > after:
            return moment
    return None
