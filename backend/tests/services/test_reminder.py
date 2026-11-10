from datetime import UTC, datetime, time

import pytest
from pydantic import ValidationError
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.core.errors import ConflictError, DomainValidationError, NotFoundError
from app.schemas.push import PushSubscriptionCreate
from app.schemas.reminder import ReminderCreate, ReminderUpdate
from app.schemas.user import UserCreate
from app.services import auth as auth_service
from app.services import push as push_service
from app.services import reminder as service
from app.services.push import DeliveryResult
from tests.services.fakes import FakePushSender

NOW = datetime(2026, 11, 9, 15, 0, tzinfo=UTC)


def utc(year, month, day, hour=0, minute=0) -> datetime:
    return datetime(year, month, day, hour, minute, tzinfo=UTC)


async def make_user(session, email: str = "ana@example.com", timezone: str = "America/Bogota"):
    return await auth_service.register_user(
        session, UserCreate(email=email, password="clave-segura-1", timezone=timezone)
    )


def data(**fields) -> ReminderCreate:
    base = {"concept": "Pagar arriendo", "remind_on": "2026-11-20", "remind_at": "09:00"}
    return ReminderCreate.model_validate({**base, **fields})


async def subscribe(session, user_id, endpoint="https://push.example/abc"):
    await push_service.subscribe(
        session,
        user_id,
        PushSubscriptionCreate(endpoint=endpoint, keys={"p256dh": "key", "auth": "auth"}),
        "pytest",
    )


async def fetch(engine, reminder_id):
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as other:
        from app.models.reminder import Reminder

        return await other.get(Reminder, reminder_id)


async def test_create_one_time_reminder_converts_local_time_to_utc(session):
    user = await make_user(session)
    reminder = await service.create_reminder(session, user.id, data(), now=NOW)
    assert reminder.status == "active"
    assert reminder.frequency == "once"
    assert reminder.timezone == "America/Bogota"
    assert reminder.next_run_at == utc(2026, 11, 20, 14)
    assert reminder.next_run_local == datetime(2026, 11, 20, 9, 0)
    assert reminder.remind_at == time(9, 0)


async def test_reminder_uses_the_users_timezone(session):
    user = await make_user(session, timezone="America/New_York")
    reminder = await service.create_reminder(session, user.id, data(), now=NOW)
    assert reminder.timezone == "America/New_York"
    assert reminder.next_run_at == utc(2026, 11, 20, 14)
    reminder = await service.create_reminder(session, user.id, data(remind_at="08:00"), now=NOW)
    assert reminder.next_run_at == utc(2026, 11, 20, 13)


async def test_reminder_in_the_past_is_rejected(session):
    user = await make_user(session)
    with pytest.raises(DomainValidationError):
        await service.create_reminder(session, user.id, data(remind_on="2026-11-09", remind_at="08:00"), now=NOW)
    assert await service.list_reminders(session, user.id) == []


async def test_monthly_on_the_15th_stores_exact_day_and_next_run(session):
    user = await make_user(session)
    reminder = await service.create_reminder(
        session,
        user.id,
        data(remind_on="2026-11-09", frequency="monthly", month_days=[15]),
        now=NOW,
    )
    assert reminder.month_days == [15]
    assert reminder.next_run_at == utc(2026, 11, 15, 14)
    assert reminder.next_run_local == datetime(2026, 11, 15, 9, 0)


async def test_monthly_without_days_uses_the_start_day(session):
    user = await make_user(session)
    reminder = await service.create_reminder(
        session, user.id, data(remind_on="2026-11-20", frequency="monthly"), now=NOW
    )
    assert reminder.month_days == [20]


async def test_quincenal_is_stored_as_15th_and_last_day(session):
    user = await make_user(session)
    reminder = await service.create_reminder(
        session, user.id, data(remind_on="2026-11-09", frequency="biweekly"), now=NOW
    )
    assert reminder.month_days == [15, -1]
    assert reminder.next_run_at == utc(2026, 11, 15, 14)


async def test_weekly_with_weekdays_and_custom_interval(session):
    user = await make_user(session)
    weekly = await service.create_reminder(
        session,
        user.id,
        data(remind_on="2026-11-09", remind_at="08:00", frequency="weekly", weekdays=["monday", "thursday"]),
        now=NOW,
    )
    assert [d.value for d in weekly.weekdays] == ["monday", "thursday"]
    assert weekly.next_run_at == utc(2026, 11, 12, 13)
    custom = await service.create_reminder(
        session,
        user.id,
        data(remind_on="2026-11-09", frequency="custom", interval_count=3, interval_unit="days"),
        now=NOW,
    )
    assert custom.interval_count == 3 and custom.interval_unit == "days"


async def test_list_returns_only_active_reminders_sorted_by_next_run(session):
    user = await make_user(session)
    late = await service.create_reminder(session, user.id, data(remind_on="2026-12-01", concept="Tarde"), now=NOW)
    soon = await service.create_reminder(session, user.id, data(remind_on="2026-11-10", concept="Pronto"), now=NOW)
    gone = await service.create_reminder(session, user.id, data(remind_on="2026-11-11", concept="Cancelado"), now=NOW)
    await service.cancel_reminder(session, user.id, gone.id)
    listed = await service.list_reminders(session, user.id)
    assert [r.id for r in listed] == [soon.id, late.id]


async def test_update_recalculates_schedule(session):
    user = await make_user(session)
    created = await service.create_reminder(
        session, user.id, data(remind_on="2026-11-09", frequency="monthly", month_days=[15]), now=NOW
    )
    moved = await service.update_reminder(
        session, user.id, created.id, ReminderUpdate(month_days=[5, 20]), now=NOW
    )
    assert moved.month_days == [5, 20]
    assert moved.next_run_at == utc(2026, 11, 20, 14)
    renamed = await service.update_reminder(
        session, user.id, created.id, ReminderUpdate(concept="Pagar servicios", remind_at="10:30"), now=NOW
    )
    assert renamed.concept == "Pagar servicios"
    assert renamed.month_days == [5, 20]
    assert renamed.next_run_local == datetime(2026, 11, 20, 10, 30)


async def test_update_frequency_resets_the_previous_pattern(session):
    user = await make_user(session)
    created = await service.create_reminder(
        session, user.id, data(remind_on="2026-11-09", frequency="monthly", month_days=[15]), now=NOW
    )
    weekly = await service.update_reminder(
        session, user.id, created.id, ReminderUpdate(frequency="weekly", weekdays=["friday"]), now=NOW
    )
    assert weekly.frequency == "weekly"
    assert weekly.month_days == []
    assert [d.value for d in weekly.weekdays] == ["friday"]
    daily = await service.update_reminder(
        session, user.id, created.id, ReminderUpdate(frequency="daily"), now=NOW
    )
    assert daily.weekdays == [] and daily.month_days == []


async def test_update_to_custom_requires_interval_fields(session):
    user = await make_user(session)
    created = await service.create_reminder(session, user.id, data(), now=NOW)
    with pytest.raises(ValidationError):
        await service.update_reminder(session, user.id, created.id, ReminderUpdate(frequency="custom"), now=NOW)
    custom = await service.update_reminder(
        session,
        user.id,
        created.id,
        ReminderUpdate(frequency="custom", interval_count=2, interval_unit="months", month_days=[15]),
        now=NOW,
    )
    assert custom.interval_unit == "months" and custom.month_days == [15]


async def test_update_to_a_past_moment_is_rejected_and_changes_nothing(session):
    user = await make_user(session)
    user_id = user.id
    created = await service.create_reminder(session, user_id, data(), now=NOW)
    with pytest.raises(DomainValidationError):
        await service.update_reminder(
            session, user_id, created.id, ReminderUpdate(remind_on="2026-11-01", concept="Otro"), now=NOW
        )
    await session.commit()
    listed = await service.list_reminders(session, user_id)
    assert listed[0].next_run_at == utc(2026, 11, 20, 14)
    assert listed[0].concept == "Pagar arriendo"
    assert listed[0].remind_on.isoformat() == "2026-11-20"


async def test_cancel_only_affects_the_chosen_reminder(session):
    user = await make_user(session)
    keep = await service.create_reminder(session, user.id, data(concept="Mantener"), now=NOW)
    drop = await service.create_reminder(session, user.id, data(concept="Cancelar"), now=NOW)
    cancelled = await service.cancel_reminder(session, user.id, drop.id)
    assert cancelled.status == "cancelled"
    assert cancelled.next_run_at is None
    listed = await service.list_reminders(session, user.id)
    assert [r.id for r in listed] == [keep.id]
    assert listed[0].next_run_at == utc(2026, 11, 20, 14)


async def test_cancelled_reminders_cannot_be_cancelled_or_modified_again(session):
    user = await make_user(session)
    created = await service.create_reminder(session, user.id, data(), now=NOW)
    await service.cancel_reminder(session, user.id, created.id)
    with pytest.raises(ConflictError):
        await service.cancel_reminder(session, user.id, created.id)
    with pytest.raises(ConflictError):
        await service.update_reminder(session, user.id, created.id, ReminderUpdate(concept="X"), now=NOW)


async def test_reminders_are_isolated_between_users(session):
    ana = await make_user(session, "ana@example.com")
    beto = await make_user(session, "beto@example.com")
    ana_id, beto_id = ana.id, beto.id
    created = await service.create_reminder(session, ana_id, data(), now=NOW)
    with pytest.raises(NotFoundError):
        await service.cancel_reminder(session, beto_id, created.id)
    with pytest.raises(NotFoundError):
        await service.update_reminder(session, beto_id, created.id, ReminderUpdate(concept="X"), now=NOW)
    assert await service.list_reminders(session, beto_id) == []
    assert len(await service.list_reminders(session, ana_id)) == 1


async def test_due_one_time_reminder_is_sent_and_completed(engine, session):
    user = await make_user(session)
    user_id = user.id
    await subscribe(session, user_id)
    created = await service.create_reminder(session, user_id, data(concept="Pagar arriendo"), now=NOW)
    sender = FakePushSender()
    factory = async_sessionmaker(engine, expire_on_commit=False)
    due = utc(2026, 11, 20, 14, 0)
    assert await service.process_due_reminders(factory, sender, now=due) == 1
    assert len(sender.calls) == 1
    subscription, payload = sender.calls[0]
    assert subscription.endpoint == "https://push.example/abc"
    assert payload["title"] == "Recordatorio"
    assert payload["body"] == "Pagar arriendo"
    stored = await fetch(engine, created.id)
    assert stored.status == "completed"
    assert stored.next_run_at is None
    assert stored.last_run_at == due
    assert await service.process_due_reminders(factory, sender, now=due) == 0
    assert len(sender.calls) == 1


async def test_reminder_not_yet_due_is_left_alone(engine, session):
    user = await make_user(session)
    await subscribe(session, user.id)
    await service.create_reminder(session, user.id, data(), now=NOW)
    sender = FakePushSender()
    factory = async_sessionmaker(engine, expire_on_commit=False)
    assert await service.process_due_reminders(factory, sender, now=utc(2026, 11, 20, 13, 59)) == 0
    assert sender.calls == []


async def test_recurring_reminder_advances_to_the_next_exact_date(engine, session):
    user = await make_user(session)
    user_id = user.id
    await subscribe(session, user_id)
    created = await service.create_reminder(
        session, user_id, data(remind_on="2026-11-09", frequency="monthly", month_days=[15]), now=NOW
    )
    sender = FakePushSender()
    factory = async_sessionmaker(engine, expire_on_commit=False)
    await service.process_due_reminders(factory, sender, now=utc(2026, 11, 15, 14, 0, ))
    stored = await fetch(engine, created.id)
    assert stored.status == "active"
    assert stored.next_run_at == utc(2026, 12, 15, 14)
    assert stored.attempts == 0
    assert len(sender.calls) == 1


async def test_missed_periods_are_not_replayed(engine, session):
    user = await make_user(session)
    user_id = user.id
    await subscribe(session, user_id)
    created = await service.create_reminder(
        session, user_id, data(remind_on="2026-11-10", frequency="daily"), now=NOW
    )
    sender = FakePushSender()
    factory = async_sessionmaker(engine, expire_on_commit=False)
    late = utc(2026, 11, 15, 20, 0)
    assert await service.process_due_reminders(factory, sender, now=late) == 1
    assert len(sender.calls) == 1
    stored = await fetch(engine, created.id)
    assert stored.next_run_at == utc(2026, 11, 16, 14)


async def test_user_without_devices_does_not_block_the_reminder(engine, session):
    user = await make_user(session)
    created = await service.create_reminder(session, user.id, data(), now=NOW)
    sender = FakePushSender()
    factory = async_sessionmaker(engine, expire_on_commit=False)
    await service.process_due_reminders(factory, sender, now=utc(2026, 11, 20, 14))
    assert sender.calls == []
    assert (await fetch(engine, created.id)).status == "completed"


async def test_expired_subscription_is_removed(engine, session):
    user = await make_user(session)
    user_id = user.id
    await subscribe(session, user_id)
    await service.create_reminder(session, user_id, data(), now=NOW)
    sender = FakePushSender(default=DeliveryResult.GONE)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    await service.process_due_reminders(factory, sender, now=utc(2026, 11, 20, 14))
    async with factory() as other:
        assert await push_service.has_subscription(other, user_id) is False


async def test_transient_failures_are_retried_with_backoff_then_given_up(engine, session, monkeypatch):
    monkeypatch.setattr(service.settings, "reminder_max_attempts", 3)
    monkeypatch.setattr(service.settings, "reminder_retry_minutes", 5)
    user = await make_user(session)
    await subscribe(session, user.id)
    created = await service.create_reminder(session, user.id, data(), now=NOW)
    sender = FakePushSender(default=DeliveryResult.FAILED)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    first = utc(2026, 11, 20, 14)
    await service.process_due_reminders(factory, sender, now=first)
    stored = await fetch(engine, created.id)
    assert (stored.status, stored.attempts, stored.next_run_at) == ("active", 1, utc(2026, 11, 20, 14, 5))
    second = utc(2026, 11, 20, 14, 5)
    await service.process_due_reminders(factory, sender, now=second)
    stored = await fetch(engine, created.id)
    assert (stored.status, stored.attempts, stored.next_run_at) == ("active", 2, utc(2026, 11, 20, 14, 15))
    third = utc(2026, 11, 20, 14, 15)
    await service.process_due_reminders(factory, sender, now=third)
    stored = await fetch(engine, created.id)
    assert (stored.status, stored.attempts, stored.next_run_at) == ("completed", 0, None)
    assert len(sender.calls) == 3


async def test_recurring_reminder_still_advances_after_giving_up(engine, session, monkeypatch):
    monkeypatch.setattr(service.settings, "reminder_max_attempts", 1)
    user = await make_user(session)
    await subscribe(session, user.id)
    created = await service.create_reminder(
        session, user.id, data(remind_on="2026-11-10", frequency="daily"), now=NOW
    )
    sender = FakePushSender(default=DeliveryResult.FAILED)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    await service.process_due_reminders(factory, sender, now=utc(2026, 11, 20, 14))
    stored = await fetch(engine, created.id)
    assert stored.status == "active"
    assert stored.next_run_at == utc(2026, 11, 21, 14)


async def test_one_delivery_among_several_devices_is_enough(engine, session):
    user = await make_user(session)
    await subscribe(session, user.id, "https://push.example/phone")
    await subscribe(session, user.id, "https://push.example/laptop")
    created = await service.create_reminder(session, user.id, data(), now=NOW)
    sender = FakePushSender(DeliveryResult.FAILED, DeliveryResult.DELIVERED)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    await service.process_due_reminders(factory, sender, now=utc(2026, 11, 20, 14))
    assert len(sender.calls) == 2
    stored = await fetch(engine, created.id)
    assert (stored.status, stored.attempts) == ("completed", 0)


async def test_cancelled_reminders_are_never_sent(engine, session):
    user = await make_user(session)
    await subscribe(session, user.id)
    created = await service.create_reminder(session, user.id, data(), now=NOW)
    await service.cancel_reminder(session, user.id, created.id)
    sender = FakePushSender()
    factory = async_sessionmaker(engine, expire_on_commit=False)
    assert await service.process_due_reminders(factory, sender, now=utc(2026, 11, 21)) == 0
    assert sender.calls == []


async def test_batch_limit_and_each_reminder_goes_to_its_own_user(engine, session):
    ana = await make_user(session, "ana@example.com")
    beto = await make_user(session, "beto@example.com")
    ana_id, beto_id = ana.id, beto.id
    await subscribe(session, ana_id, "https://push.example/ana")
    await subscribe(session, beto_id, "https://push.example/beto")
    for index in range(2):
        await service.create_reminder(session, ana_id, data(concept=f"Ana {index}"), now=NOW)
    await service.create_reminder(session, beto_id, data(concept="Beto"), now=NOW)
    sender = FakePushSender()
    factory = async_sessionmaker(engine, expire_on_commit=False)
    due = utc(2026, 11, 20, 14)
    assert await service.process_due_reminders(factory, sender, now=due, max_batch=2) == 2
    assert await service.process_due_reminders(factory, sender, now=due) == 1
    delivered = {(call[0].endpoint, call[1]["body"]) for call in sender.calls}
    assert delivered == {
        ("https://push.example/ana", "Ana 0"),
        ("https://push.example/ana", "Ana 1"),
        ("https://push.example/beto", "Beto"),
    }


async def test_concurrent_workers_send_each_reminder_once(engine, session):
    import asyncio

    user = await make_user(session)
    await subscribe(session, user.id)
    created = await service.create_reminder(session, user.id, data(), now=NOW)
    sender = FakePushSender(delay=0.3)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    due = utc(2026, 11, 20, 14)
    counts = await asyncio.gather(
        service.process_due_reminders(factory, sender, now=due),
        service.process_due_reminders(factory, sender, now=due),
        service.process_due_reminders(factory, sender, now=due),
    )
    assert sorted(counts) == [0, 0, 1]
    assert len(sender.calls) == 1
    assert (await fetch(engine, created.id)).status == "completed"


async def test_predefined_frequencies_store_their_normalized_interval(session):
    user = await make_user(session)
    daily = await service.create_reminder(session, user.id, data(remind_on="2026-11-10", frequency="daily"), now=NOW)
    weekly = await service.create_reminder(session, user.id, data(remind_on="2026-11-10", frequency="weekly"), now=NOW)
    assert (daily.interval_count, daily.interval_unit) == (1, "days")
    assert (weekly.interval_count, weekly.interval_unit) == (1, "weeks")
    assert [d.value for d in weekly.weekdays] == ["tuesday"]
    assert weekly.next_run_at == utc(2026, 11, 10, 14)
