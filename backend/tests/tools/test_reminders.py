import json

import pytest
from pydantic import ValidationError

from app.core.errors import ConflictError, DomainValidationError, NotFoundError
from app.schemas.push import PushSubscriptionCreate
from app.schemas.user import UserCreate
from app.services import auth as auth_service
from app.services import push as push_service
from app.tools import reminders as tools
from tests.services.fakes import FakePushSender

FUTURE = {"concept": "Pagar arriendo", "remind_on": "2030-03-05", "remind_at": "09:00"}
UNKNOWN = "00000000-0000-0000-0000-000000000000"


async def make_user(session, email: str = "ana@example.com"):
    return await auth_service.register_user(
        session, UserCreate(email=email, password="clave-segura-1")
    )


async def test_create_reminder_returns_json_and_notification_status(session):
    user = await make_user(session)
    result = await tools.create_reminder(session, user.id, FUTURE)
    assert result["status"] == "active"
    assert result["frequency"] == "once"
    assert result["next_run_local"] == "2030-03-05T09:00:00"
    assert result["next_run_at"].startswith("2030-03-05T14:00:00")
    assert result["notifications_enabled"] is False
    json.dumps(result)


async def test_notifications_enabled_reflects_push_subscriptions(session, monkeypatch):
    user = await make_user(session)
    user_id = user.id
    await push_service.subscribe(
        session,
        user_id,
        PushSubscriptionCreate(endpoint="https://push.example/a", keys={"p256dh": "k", "auth": "a"}),
        None,
    )
    fake = FakePushSender()
    monkeypatch.setattr(push_service, "web_push_sender", fake)
    result = await tools.create_reminder(session, user_id, FUTURE)
    assert result["notifications_enabled"] is True
    assert fake.calls[0][1]["title"] == "Recordatorio creado"
    assert fake.calls[0][1]["body"] == "Pagar arriendo"
    assert fake.calls[0][1]["url"] == "/recordatorios"


async def test_create_exact_day_of_month_reminders(session):
    user = await make_user(session)
    fifteenth = await tools.create_reminder(
        session,
        user.id,
        {**FUTURE, "remind_on": "2030-03-01", "frequency": "monthly", "month_days": [15]},
    )
    assert fifteenth["month_days"] == [15]
    assert fifteenth["next_run_local"] == "2030-03-15T09:00:00"
    last_day = await tools.create_reminder(
        session, user.id, {**FUTURE, "frequency": "monthly", "month_days": [-1]}
    )
    assert last_day["month_days"] == [-1]
    assert last_day["next_run_local"] == "2030-03-31T09:00:00"
    quincenal = await tools.create_reminder(
        session, user.id, {**FUTURE, "remind_on": "2030-03-01", "frequency": "biweekly"}
    )
    assert quincenal["month_days"] == [15, -1]
    assert quincenal["next_run_local"] == "2030-03-15T09:00:00"


async def test_list_update_and_cancel_flow(session):
    user = await make_user(session)
    user_id = user.id
    first = await tools.create_reminder(session, user_id, FUTURE)
    second = await tools.create_reminder(session, user_id, {**FUTURE, "concept": "Otro", "remind_on": "2030-04-01"})
    listed = await tools.list_reminders(session, user_id, {})
    assert listed["count"] == 2
    assert [r["concept"] for r in listed["reminders"]] == ["Pagar arriendo", "Otro"]
    json.dumps(listed)
    updated = await tools.update_reminder(
        session, user_id, {"reminder_id": first["id"], "remind_at": "10:30", "concept": "Arriendo"}
    )
    assert updated["concept"] == "Arriendo"
    assert updated["next_run_local"] == "2030-03-05T10:30:00"
    cancelled = await tools.cancel_reminder(session, user_id, {"reminder_id": first["id"]})
    assert cancelled["status"] == "cancelled"
    remaining = await tools.list_reminders(session, user_id, {})
    assert [r["id"] for r in remaining["reminders"]] == [second["id"]]


@pytest.mark.parametrize(
    "args",
    [
        {"concept": "Sin fecha", "remind_at": "09:00"},
        {"concept": "Sin hora", "remind_on": "2030-03-05"},
        {**FUTURE, "frequency": "monthly", "month_days": [0]},
        {**FUTURE, "frequency": "monthly", "month_days": [32]},
        {**FUTURE, "frequency": "daily", "month_days": [15]},
        {**FUTURE, "frequency": "custom"},
        {**FUTURE, "frequency": "yearly"},
        {**FUTURE, "remind_at": "9am"},
    ],
)
async def test_create_validates_arguments(session, args):
    user = await make_user(session)
    with pytest.raises(ValidationError):
        await tools.create_reminder(session, user.id, args)


async def test_create_in_the_past_raises_domain_error(session):
    user = await make_user(session)
    with pytest.raises(DomainValidationError):
        await tools.create_reminder(session, user.id, {**FUTURE, "remind_on": "2020-01-01"})


async def test_update_validates_arguments(session):
    user = await make_user(session)
    created = await tools.create_reminder(session, user.id, FUTURE)
    rid = created["id"]
    for args in (
        {"concept": "X"},
        {"reminder_id": rid},
        {"reminder_id": rid, "concept": None},
        {"reminder_id": rid, "frequency": "custom"},
        {"reminder_id": rid, "user_id": str(user.id)},
    ):
        with pytest.raises(ValidationError):
            await tools.update_reminder(session, user.id, args)


async def test_tools_reject_user_id_argument(session):
    user = await make_user(session)
    other = await make_user(session, "beto@example.com")
    smuggled = {"user_id": str(other.id)}
    with pytest.raises(ValidationError):
        await tools.create_reminder(session, user.id, {**FUTURE, **smuggled})
    with pytest.raises(ValidationError):
        await tools.list_reminders(session, user.id, smuggled)
    with pytest.raises(ValidationError):
        await tools.cancel_reminder(session, user.id, {"reminder_id": UNKNOWN, **smuggled})


async def test_tools_cannot_touch_other_users_reminders(session):
    ana = await make_user(session, "ana@example.com")
    beto = await make_user(session, "beto@example.com")
    ana_id, beto_id = ana.id, beto.id
    created = await tools.create_reminder(session, ana_id, FUTURE)
    with pytest.raises(NotFoundError):
        await tools.cancel_reminder(session, beto_id, {"reminder_id": created["id"]})
    with pytest.raises(NotFoundError):
        await tools.update_reminder(session, beto_id, {"reminder_id": created["id"], "concept": "X"})
    assert (await tools.list_reminders(session, beto_id, {}))["count"] == 0
    assert (await tools.list_reminders(session, ana_id, {}))["count"] == 1


async def test_cancelling_twice_raises_conflict(session):
    user = await make_user(session)
    created = await tools.create_reminder(session, user.id, FUTURE)
    await tools.cancel_reminder(session, user.id, {"reminder_id": created["id"]})
    with pytest.raises(ConflictError):
        await tools.cancel_reminder(session, user.id, {"reminder_id": created["id"]})
