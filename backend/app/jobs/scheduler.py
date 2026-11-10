import logging

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.config import settings
from app.services import push as push_service
from app.services import reminder as reminder_service

logger = logging.getLogger(__name__)

JOB_ID = "process_due_reminders"


async def run_due_reminders(
    session_factory: async_sessionmaker[AsyncSession], sender: push_service.PushSender
) -> None:
    try:
        processed = await reminder_service.process_due_reminders(session_factory, sender)
    except Exception:
        logger.exception("Falló el procesamiento de recordatorios vencidos.")
        return
    if processed:
        logger.info("Recordatorios procesados: %s", processed)


def create_scheduler(
    session_factory: async_sessionmaker[AsyncSession], sender: push_service.PushSender
) -> AsyncIOScheduler:
    scheduler = AsyncIOScheduler(timezone="UTC")
    scheduler.add_job(
        run_due_reminders,
        trigger="interval",
        seconds=settings.reminder_poll_seconds,
        id=JOB_ID,
        args=[session_factory, sender],
        max_instances=1,
        coalesce=True,
        replace_existing=True,
    )
    return scheduler
