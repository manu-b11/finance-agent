from fastapi import APIRouter, Depends, Request, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_push_sender
from app.core.config import settings
from app.core.database import get_session
from app.core.errors import ProcessingError
from app.models.user import User
from app.schemas.push import (
    PushPublicKey,
    PushSubscriptionCreate,
    PushSubscriptionRead,
    PushTestResult,
    PushUnsubscribe,
)
from app.services import push as push_service

router = APIRouter(prefix="/push", tags=["push"])


@router.get("/public-key", response_model=PushPublicKey)
async def public_key(current_user: User = Depends(get_current_user)) -> PushPublicKey:
    if not settings.vapid_public_key:
        raise ProcessingError("Las notificaciones push no están configuradas en el servidor.")
    return PushPublicKey(public_key=settings.vapid_public_key)


@router.post(
    "/subscriptions", response_model=PushSubscriptionRead, status_code=status.HTTP_201_CREATED
)
async def subscribe(
    data: PushSubscriptionCreate,
    request: Request,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> PushSubscriptionRead:
    subscription = await push_service.subscribe(
        session, current_user.id, data, request.headers.get("user-agent")
    )
    return PushSubscriptionRead.model_validate(subscription)


@router.delete("/subscriptions", status_code=status.HTTP_204_NO_CONTENT)
async def unsubscribe(
    data: PushUnsubscribe,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> Response:
    await push_service.unsubscribe(session, current_user.id, data.endpoint)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/test", response_model=PushTestResult)
async def send_test(
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
    sender: push_service.PushSender = Depends(get_push_sender),
) -> PushTestResult:
    summary = await push_service.send_test(session, current_user.id, sender)
    return PushTestResult(
        delivered=summary.delivered, failed=summary.failed, gone=summary.gone
    )
