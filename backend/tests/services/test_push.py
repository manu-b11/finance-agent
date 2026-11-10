import json

import pytest
from sqlalchemy import func, select

from app.core.errors import NotFoundError
from app.models.push_subscription import PushSubscription
from app.schemas.push import PushSubscriptionCreate
from app.schemas.user import UserCreate
from app.services import auth as auth_service
from app.services import push as service
from app.services.push import DeliveryResult, PushPayload
from tests.services.fakes import FakePushSender


async def make_user(session, email: str = "ana@example.com"):
    return await auth_service.register_user(
        session, UserCreate(email=email, password="clave-segura-1")
    )


def sub(endpoint="https://push.example/abc", p256dh="key", auth="auth") -> PushSubscriptionCreate:
    return PushSubscriptionCreate(endpoint=endpoint, keys={"p256dh": p256dh, "auth": auth})


async def count(session) -> int:
    return (await session.execute(select(func.count()).select_from(PushSubscription))).scalar_one()


async def test_subscribe_creates_and_updates_the_same_endpoint(session):
    user = await make_user(session)
    first = await service.subscribe(session, user.id, sub(), "Chrome")
    second = await service.subscribe(session, user.id, sub(p256dh="nueva"), "Chrome 2")
    assert first.id == second.id
    assert second.p256dh == "nueva"
    assert await count(session) == 1


async def test_endpoint_moves_to_the_latest_user_on_a_shared_browser(session):
    ana = await make_user(session, "ana@example.com")
    beto = await make_user(session, "beto@example.com")
    ana_id, beto_id = ana.id, beto.id
    await service.subscribe(session, ana_id, sub(), None)
    await service.subscribe(session, beto_id, sub(), None)
    assert await count(session) == 1
    assert await service.has_subscription(session, beto_id) is True
    assert await service.has_subscription(session, ana_id) is False


async def test_unsubscribe_only_removes_the_users_own_endpoint(session):
    ana = await make_user(session, "ana@example.com")
    beto = await make_user(session, "beto@example.com")
    ana_id, beto_id = ana.id, beto.id
    await service.subscribe(session, ana_id, sub("https://push.example/ana"), None)
    await service.unsubscribe(session, beto_id, "https://push.example/ana")
    assert await service.has_subscription(session, ana_id) is True
    await service.unsubscribe(session, ana_id, "https://push.example/ana")
    assert await service.has_subscription(session, ana_id) is False


async def test_send_to_user_summarizes_and_removes_expired_endpoints(session):
    user = await make_user(session)
    user_id = user.id
    for name in ("a", "b", "c"):
        await service.subscribe(session, user_id, sub(f"https://push.example/{name}"), None)
    sender = FakePushSender(DeliveryResult.DELIVERED, DeliveryResult.GONE, DeliveryResult.FAILED)
    summary = await service.send_to_user(
        session, user_id, PushPayload("Título", "Cuerpo con ñ", "tag"), sender
    )
    await session.commit()
    assert (summary.delivered, summary.gone, summary.failed) == (1, 1, 1)
    assert await count(session) == 2
    payload = sender.calls[0][1]
    assert payload == {"title": "Título", "body": "Cuerpo con ñ", "tag": "tag", "url": "/"}


async def test_send_to_user_only_reaches_that_users_devices(session):
    ana = await make_user(session, "ana@example.com")
    beto = await make_user(session, "beto@example.com")
    ana_id, beto_id = ana.id, beto.id
    await service.subscribe(session, ana_id, sub("https://push.example/ana"), None)
    await service.subscribe(session, beto_id, sub("https://push.example/beto"), None)
    sender = FakePushSender()
    await service.send_to_user(session, ana_id, PushPayload("t", "b", "x"), sender)
    assert [call[0].endpoint for call in sender.calls] == ["https://push.example/ana"]


async def test_send_test_requires_a_subscription(session):
    user = await make_user(session)
    with pytest.raises(NotFoundError):
        await service.send_test(session, user.id, FakePushSender())


async def test_send_test_sends_a_notification(session):
    user = await make_user(session)
    user_id = user.id
    await service.subscribe(session, user_id, sub(), None)
    sender = FakePushSender()
    summary = await service.send_test(session, user_id, sender)
    assert summary.delivered == 1
    assert json.loads(json.dumps(sender.calls[0][1]))["tag"] == "push-test"
