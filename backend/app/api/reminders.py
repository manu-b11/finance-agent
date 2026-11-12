import uuid

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.database import get_session
from app.models.user import User
from app.schemas.reminder import ReminderCreate, ReminderRead
from app.services import reminder as reminder_service

router = APIRouter(prefix="/reminders", tags=["reminders"])


@router.get("", response_model=list[ReminderRead])
async def list_reminders(
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> list[ReminderRead]:
    return await reminder_service.list_reminders(session, current_user.id)


@router.post("", response_model=ReminderRead, status_code=status.HTTP_201_CREATED)
async def create_reminder(
    payload: ReminderCreate,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> ReminderRead:
    reminder = await reminder_service.create_reminder(session, current_user.id, payload)
    await reminder_service.notify_created(session, current_user.id, reminder)
    return reminder


@router.delete("/{reminder_id}", response_model=ReminderRead)
async def cancel_reminder(
    reminder_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> ReminderRead:
    return await reminder_service.cancel_reminder(session, current_user.id, reminder_id)
