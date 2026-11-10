import calendar
from datetime import date, datetime
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError


def zone_for(timezone: str) -> ZoneInfo:
    try:
        return ZoneInfo(timezone)
    except ZoneInfoNotFoundError:
        return ZoneInfo("UTC")


def local_today(timezone: str) -> date:
    return datetime.now(zone_for(timezone)).date()


def month_bounds(year: int, month: int) -> tuple[date, date]:
    return date(year, month, 1), date(year, month, calendar.monthrange(year, month)[1])
