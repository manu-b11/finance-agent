import logging
import uuid
from datetime import UTC, date, datetime, time, timedelta
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.clock import zone_for
from app.core.config import settings
from app.core.errors import ConflictError, DomainValidationError, NotFoundError
from app.models.reminder import Reminder, ReminderStatus
from app.schemas.reminder import (
    Frequency,
    IntervalUnit,
    ReminderCreate,
    ReminderRead,
    ReminderUpdate,
    Weekday,
)
from app.services import auth as auth_service
from app.services import push as push_service
from app.services import reminder_schedule as schedule_math

logger = logging.getLogger(__name__)

PAST_MESSAGE = "La fecha y hora del recordatorio ya pasó. Indica una fecha y hora futuras."
WEEKDAYS = list(Weekday)


def _schedule_of(reminder: Reminder) -> schedule_math.Schedule:
    return schedule_math.Schedule(
        frequency=reminder.frequency,
        interval_count=reminder.interval_count,
        interval_unit=reminder.interval_unit,
        month_days=tuple(reminder.month_days or ()),
        weekdays=tuple(reminder.weekdays or ()),
    )


def _next_run(reminder: Reminder, after: datetime) -> datetime | None:
    return schedule_math.next_occurrence(
        _schedule_of(reminder),
        reminder.start_local.date(),
        reminder.start_local.time(),
        zone_for(reminder.timezone),
        after,
    )


def to_read(reminder: Reminder) -> ReminderRead:
    next_local = None
    if reminder.next_run_at is not None:
        next_local = reminder.next_run_at.astimezone(zone_for(reminder.timezone)).replace(
            tzinfo=None
        )
    return ReminderRead(
        id=reminder.id,
        concept=reminder.concept,
        status=ReminderStatus(reminder.status),
        frequency=Frequency(reminder.frequency),
        interval_count=reminder.interval_count,
        interval_unit=IntervalUnit(reminder.interval_unit) if reminder.interval_unit else None,
        month_days=list(reminder.month_days or []),
        weekdays=[WEEKDAYS[index] for index in (reminder.weekdays or [])],
        remind_on=reminder.start_local.date(),
        remind_at=reminder.start_local.time(),
        timezone=reminder.timezone,
        next_run_at=reminder.next_run_at,
        next_run_local=next_local,
        last_run_at=reminder.last_run_at,
        created_at=reminder.created_at,
    )


def _apply(reminder: Reminder, data: ReminderCreate, now: datetime) -> None:
    schedule = schedule_math.build_schedule(
        data.frequency.value,
        data.interval_count,
        data.interval_unit.value if data.interval_unit else None,
        data.month_days,
        [day.index for day in data.weekdays],
        data.remind_on,
    )
    next_run = schedule_math.next_occurrence(
        schedule, data.remind_on, data.remind_at, zone_for(reminder.timezone), now
    )
    if next_run is None:
        raise DomainValidationError(PAST_MESSAGE)
    reminder.concept = data.concept
    reminder.start_local = datetime.combine(data.remind_on, data.remind_at)
    reminder.frequency = schedule.frequency
    reminder.interval_count = schedule.interval_count
    reminder.interval_unit = schedule.interval_unit
    reminder.month_days = list(schedule.month_days)
    reminder.weekdays = list(schedule.weekdays)
    reminder.next_run_at = next_run
    reminder.attempts = 0


async def create_reminder(
    session: AsyncSession,
    user_id: uuid.UUID,
    data: ReminderCreate,
    now: datetime | None = None,
) -> ReminderRead:
    user = await auth_service.get_user_by_id(session, user_id)
    if user is None:
        raise NotFoundError("No se encontró el usuario.")
    reminder = Reminder(
        user_id=user_id,
        timezone=user.timezone,
        status=ReminderStatus.ACTIVE.value,
    )
    _apply(reminder, data, now or datetime.now(UTC))
    session.add(reminder)
    await session.commit()
    await session.refresh(reminder)
    return to_read(reminder)


async def _get_active_owned(
    session: AsyncSession, user_id: uuid.UUID, reminder_id: uuid.UUID
) -> Reminder:
    result = await session.execute(
        select(Reminder).where(Reminder.id == reminder_id, Reminder.user_id == user_id)
    )
    reminder = result.scalar_one_or_none()
    if reminder is None:
        raise NotFoundError("No se encontró ese recordatorio.")
    if reminder.status == ReminderStatus.CANCELLED.value:
        raise ConflictError("Ese recordatorio ya fue cancelado.")
    if reminder.status == ReminderStatus.COMPLETED.value:
        raise ConflictError("Ese recordatorio ya se envió y no se puede modificar.")
    return reminder


def _merged_fields(reminder: Reminder, changes: dict[str, Any]) -> dict[str, Any]:
    current: dict[str, Any] = {
        "concept": reminder.concept,
        "remind_on": reminder.start_local.date(),
        "remind_at": reminder.start_local.time(),
        "frequency": reminder.frequency,
        "interval_count": None,
        "interval_unit": None,
        "month_days": [],
        "weekdays": [],
    }
    is_custom = reminder.frequency == "custom"
    if is_custom:
        current["interval_count"] = reminder.interval_count
        current["interval_unit"] = reminder.interval_unit
    if reminder.frequency == "monthly" or (is_custom and reminder.interval_unit == "months"):
        current["month_days"] = list(reminder.month_days or [])
    if reminder.frequency == "weekly" or (is_custom and reminder.interval_unit == "weeks"):
        current["weekdays"] = [WEEKDAYS[index] for index in (reminder.weekdays or [])]
    if "frequency" in changes or "interval_unit" in changes:
        current.update(interval_count=None, interval_unit=None, month_days=[], weekdays=[])
    return {**current, **changes}


async def update_reminder(
    session: AsyncSession,
    user_id: uuid.UUID,
    reminder_id: uuid.UUID,
    data: ReminderUpdate,
    now: datetime | None = None,
) -> ReminderRead:
    reminder = await _get_active_owned(session, user_id, reminder_id)
    merged = _merged_fields(reminder, data.model_dump(exclude_unset=True))
    _apply(reminder, ReminderCreate.model_validate(merged), now or datetime.now(UTC))
    await session.commit()
    await session.refresh(reminder)
    return to_read(reminder)


async def cancel_reminder(
    session: AsyncSession, user_id: uuid.UUID, reminder_id: uuid.UUID
) -> ReminderRead:
    reminder = await _get_active_owned(session, user_id, reminder_id)
    reminder.status = ReminderStatus.CANCELLED.value
    reminder.next_run_at = None
    await session.commit()
    await session.refresh(reminder)
    return to_read(reminder)


async def list_reminders(session: AsyncSession, user_id: uuid.UUID) -> list[ReminderRead]:
    result = await session.execute(
        select(Reminder)
        .where(Reminder.user_id == user_id, Reminder.status == ReminderStatus.ACTIVE.value)
        .order_by(Reminder.next_run_at, Reminder.created_at)
    )
    return [to_read(reminder) for reminder in result.scalars().all()]


async def _fire(
    session: AsyncSession,
    reminder: Reminder,
    now: datetime,
    sender: push_service.PushSender,
) -> None:
    payload = push_service.PushPayload(
        title="Recordatorio", body=reminder.concept, tag=f"reminder-{reminder.id}"
    )
    summary = await push_service.send_to_user(session, reminder.user_id, payload, sender)
    if summary.failed and not summary.delivered:
        reminder.attempts += 1
        if reminder.attempts < settings.reminder_max_attempts:
            reminder.next_run_at = now + timedelta(
                minutes=settings.reminder_retry_minutes * reminder.attempts
            )
            return
        logger.warning("Recordatorio %s: se agotaron los reintentos de envío.", reminder.id)
    reminder.attempts = 0
    reminder.last_run_at = now
    following = None if reminder.frequency == "once" else _next_run(reminder, now)
    if following is None:
        reminder.status = ReminderStatus.COMPLETED.value
        reminder.next_run_at = None
    else:
        reminder.next_run_at = following


async def process_due_reminders(
    session_factory: async_sessionmaker[AsyncSession],
    sender: push_service.PushSender,
    now: datetime | None = None,
    max_batch: int = 50,
) -> int:
    """Envía los recordatorios vencidos. Cada uno se procesa en su propia transacción con bloqueo."""
    moment = now or datetime.now(UTC)
    processed = 0
    for _ in range(max_batch):
        async with session_factory() as session:
            result = await session.execute(
                select(Reminder)
                .where(
                    Reminder.status == ReminderStatus.ACTIVE.value,
                    Reminder.next_run_at <= moment,
                )
                .order_by(Reminder.next_run_at)
                .limit(1)
                .with_for_update(skip_locked=True)
            )
            reminder = result.scalar_one_or_none()
            if reminder is None:
                break
            await _fire(session, reminder, moment, sender)
            await session.commit()
        processed += 1
    return processed
