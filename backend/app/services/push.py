import json
import logging
import uuid
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from enum import StrEnum

from fastapi.concurrency import run_in_threadpool
from pywebpush import WebPushException, webpush
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.errors import NotFoundError
from app.models.push_subscription import PushSubscription
from app.schemas.push import PushSubscriptionCreate

logger = logging.getLogger(__name__)

GONE_STATUS_CODES = {404, 410}
PUSH_TIMEOUT_SECONDS = 10
PUSH_TTL_SECONDS = 24 * 60 * 60


class DeliveryResult(StrEnum):
    DELIVERED = "delivered"
    GONE = "gone"
    FAILED = "failed"


@dataclass(frozen=True)
class SubscriptionInfo:
    endpoint: str
    p256dh: str
    auth: str


@dataclass(frozen=True)
class PushPayload:
    title: str
    body: str
    tag: str
    url: str = "/"

    def to_json(self) -> str:
        return json.dumps(
            {"title": self.title, "body": self.body, "tag": self.tag, "url": self.url},
            ensure_ascii=False,
        )


@dataclass
class DeliverySummary:
    delivered: int = 0
    gone: int = 0
    failed: int = 0


PushSender = Callable[[SubscriptionInfo, str], Awaitable[DeliveryResult]]


def _send_blocking(subscription: SubscriptionInfo, payload: str) -> None:
    webpush(
        subscription_info={
            "endpoint": subscription.endpoint,
            "keys": {"p256dh": subscription.p256dh, "auth": subscription.auth},
        },
        data=payload,
        vapid_private_key=settings.vapid_private_key,
        vapid_claims={"sub": settings.vapid_subject},
        ttl=PUSH_TTL_SECONDS,
        timeout=PUSH_TIMEOUT_SECONDS,
    )


async def web_push_sender(subscription: SubscriptionInfo, payload: str) -> DeliveryResult:
    if not settings.vapid_private_key:
        logger.error("VAPID_PRIVATE_KEY no está configurada; no se puede enviar push.")
        return DeliveryResult.FAILED
    try:
        await run_in_threadpool(_send_blocking, subscription, payload)
    except WebPushException as exc:
        status = getattr(exc.response, "status_code", None)
        if status in GONE_STATUS_CODES:
            return DeliveryResult.GONE
        logger.warning("Fallo al enviar push (estado %s): %s", status, exc)
        return DeliveryResult.FAILED
    except Exception:
        logger.exception("Error inesperado al enviar push.")
        return DeliveryResult.FAILED
    return DeliveryResult.DELIVERED


async def subscribe(
    session: AsyncSession,
    user_id: uuid.UUID,
    data: PushSubscriptionCreate,
    user_agent: str | None,
) -> PushSubscription:
    """Un endpoint pertenece a un solo usuario: si cambia de cuenta en el navegador, se reasigna."""
    result = await session.execute(
        select(PushSubscription).where(PushSubscription.endpoint == data.endpoint)
    )
    subscription = result.scalar_one_or_none()
    agent = user_agent[:255] if user_agent else None
    if subscription is None:
        subscription = PushSubscription(
            user_id=user_id,
            endpoint=data.endpoint,
            p256dh=data.keys.p256dh,
            auth=data.keys.auth,
            user_agent=agent,
        )
        session.add(subscription)
    else:
        subscription.user_id = user_id
        subscription.p256dh = data.keys.p256dh
        subscription.auth = data.keys.auth
        subscription.user_agent = agent
    await session.commit()
    await session.refresh(subscription)
    return subscription


async def unsubscribe(session: AsyncSession, user_id: uuid.UUID, endpoint: str) -> None:
    await session.execute(
        delete(PushSubscription).where(
            PushSubscription.user_id == user_id, PushSubscription.endpoint == endpoint
        )
    )
    await session.commit()


async def has_subscription(session: AsyncSession, user_id: uuid.UUID) -> bool:
    result = await session.execute(
        select(PushSubscription.id).where(PushSubscription.user_id == user_id).limit(1)
    )
    return result.first() is not None


async def send_to_user(
    session: AsyncSession, user_id: uuid.UUID, payload: PushPayload, sender: PushSender
) -> DeliverySummary:
    """Envía a todos los dispositivos del usuario. No hace commit: el llamador decide."""
    result = await session.execute(
        select(PushSubscription).where(PushSubscription.user_id == user_id)
    )
    summary = DeliverySummary()
    body = payload.to_json()
    for subscription in result.scalars().all():
        outcome = await sender(
            SubscriptionInfo(subscription.endpoint, subscription.p256dh, subscription.auth), body
        )
        if outcome == DeliveryResult.DELIVERED:
            summary.delivered += 1
        elif outcome == DeliveryResult.GONE:
            summary.gone += 1
            await session.delete(subscription)
        else:
            summary.failed += 1
    return summary


async def send_test(
    session: AsyncSession, user_id: uuid.UUID, sender: PushSender
) -> DeliverySummary:
    if not await has_subscription(session, user_id):
        raise NotFoundError("No tienes notificaciones activadas en ningún dispositivo.")
    payload = PushPayload(
        title="Notificación de prueba",
        body="Las notificaciones de tus recordatorios están funcionando.",
        tag="push-test",
    )
    summary = await send_to_user(session, user_id, payload, sender)
    await session.commit()
    return summary
