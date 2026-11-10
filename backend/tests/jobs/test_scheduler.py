from datetime import UTC, datetime, timedelta

from sqlalchemy.ext.asyncio import async_sessionmaker

from app.core.config import settings
from app.jobs import scheduler as jobs
from app.main import lifespan
from app.main import app as fastapi_app
from app.models.reminder import Reminder
from app.schemas.push import PushSubscriptionCreate
from app.schemas.reminder import ReminderCreate
from app.schemas.user import UserCreate
from app.services import auth as auth_service
from app.services import push as push_service
from app.services import reminder as reminder_service
from tests.services.fakes import FakePushSender


async def seed_due_reminder(session):
    user = await auth_service.register_user(
        session, UserCreate(email="ana@example.com", password="clave-segura-1")
    )
    user_id = user.id
    await push_service.subscribe(
        session,
        user_id,
        PushSubscriptionCreate(endpoint="https://push.example/a", keys={"p256dh": "k", "auth": "a"}),
        None,
    )
    created = await reminder_service.create_reminder(
        session,
        user_id,
        ReminderCreate(concept="Pagar", remind_on="2030-01-01", remind_at="09:00"),
        now=datetime(2029, 12, 31, tzinfo=UTC),
    )
    stored = await session.get(Reminder, created.id)
    stored.next_run_at = datetime.now(UTC) - timedelta(minutes=1)
    await session.commit()
    return created.id


def test_scheduler_registers_a_single_polling_job():
    scheduler = jobs.create_scheduler(None, FakePushSender())
    job = scheduler.get_job(jobs.JOB_ID)
    assert job is not None
    assert job.trigger.interval.total_seconds() == settings.reminder_poll_seconds
    assert job.max_instances == 1
    assert job.coalesce is True
    assert len(scheduler.get_jobs()) == 1


async def test_run_due_reminders_processes_pending_work(engine, session):
    reminder_id = await seed_due_reminder(session)
    sender = FakePushSender()
    factory = async_sessionmaker(engine, expire_on_commit=False)
    await jobs.run_due_reminders(factory, sender)
    assert len(sender.calls) == 1
    async with factory() as other:
        assert (await other.get(Reminder, reminder_id)).status == "completed"


async def test_run_due_reminders_never_raises(engine, session):
    await seed_due_reminder(session)

    async def exploding_sender(subscription, payload):
        raise RuntimeError("fallo inesperado")

    factory = async_sessionmaker(engine, expire_on_commit=False)
    await jobs.run_due_reminders(factory, exploding_sender)


async def test_lifespan_starts_and_stops_the_scheduler_when_enabled(monkeypatch):
    events = []

    class FakeScheduler:
        def start(self):
            events.append("start")

        def shutdown(self, wait=True):
            events.append(("shutdown", wait))

    import app.main as main_module

    monkeypatch.setattr(main_module.settings, "scheduler_enabled", True)
    monkeypatch.setattr(main_module, "create_scheduler", lambda factory, sender: FakeScheduler())
    async with lifespan(fastapi_app):
        assert events == ["start"]
    assert events == ["start", ("shutdown", False)]


async def test_lifespan_does_nothing_when_disabled(monkeypatch):
    import app.main as main_module

    called = []
    monkeypatch.setattr(main_module.settings, "scheduler_enabled", False)
    monkeypatch.setattr(main_module, "create_scheduler", lambda *args: called.append(1))
    async with lifespan(fastapi_app):
        pass
    assert called == []
