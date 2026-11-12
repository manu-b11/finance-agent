import uuid
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.schemas.reminder import (
    ReminderCreate,
    ReminderListQuery,
    ReminderRef,
    ReminderUpdate,
)
from app.services import push as push_service
from app.services import reminder as reminder_service


async def create_reminder(
    session: AsyncSession, user_id: uuid.UUID, raw_args: dict[str, Any]
) -> dict[str, Any]:
    args = ReminderCreate.model_validate(raw_args)
    reminder = await reminder_service.create_reminder(session, user_id, args)
    await reminder_service.notify_created(session, user_id, reminder)
    return {
        **reminder.model_dump(mode="json"),
        "notifications_enabled": await push_service.has_subscription(session, user_id),
    }


async def update_reminder(
    session: AsyncSession, user_id: uuid.UUID, raw_args: dict[str, Any]
) -> dict[str, Any]:
    changes = dict(raw_args)
    ref = ReminderRef.model_validate({"reminder_id": changes.pop("reminder_id", None)})
    data = ReminderUpdate.model_validate(changes)
    reminder = await reminder_service.update_reminder(session, user_id, ref.reminder_id, data)
    return reminder.model_dump(mode="json")


async def cancel_reminder(
    session: AsyncSession, user_id: uuid.UUID, raw_args: dict[str, Any]
) -> dict[str, Any]:
    ref = ReminderRef.model_validate(raw_args)
    reminder = await reminder_service.cancel_reminder(session, user_id, ref.reminder_id)
    return reminder.model_dump(mode="json")


async def list_reminders(
    session: AsyncSession, user_id: uuid.UUID, raw_args: dict[str, Any]
) -> dict[str, Any]:
    ReminderListQuery.model_validate(raw_args)
    reminders = await reminder_service.list_reminders(session, user_id)
    items = [reminder.model_dump(mode="json") for reminder in reminders]
    return {"count": len(items), "reminders": items}
