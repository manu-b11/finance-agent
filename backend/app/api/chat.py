import json
import logging
import uuid
from collections.abc import AsyncIterator
from typing import Any

from fastapi import APIRouter, Depends, Query, Request, Response, status
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.agent import service as agent_service
from app.agent.llm_client import ChatFn, Message
from app.api.deps import get_chat_fn, get_current_user
from app.core.database import get_session
from app.core.errors import AppError, RateLimitError
from app.core.ratelimit import SlidingWindowLimiter
from app.models.chat_message import ChatMessage
from app.models.conversation import Conversation
from app.models.user import User
from app.schemas.chat import (
    ChatMessageRead,
    ChatRequest,
    ConversationCreate,
    ConversationRead,
    DemoChatRequest,
    ExchangeCreate,
)
from app.services import chat_message as chat_message_service
from app.services import conversation as conversation_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/chat", tags=["chat"])

# La demo pública no requiere cuenta: se limita por IP para proteger el costo de la IA.
demo_limiter = SlidingWindowLimiter(limit=12, window_seconds=3600)


def _sse(event: str, data: dict[str, Any]) -> str:
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


@router.post("/demo")
async def chat_demo(
    data: DemoChatRequest,
    request: Request,
    chat_fn: ChatFn = Depends(get_chat_fn),
) -> StreamingResponse:
    """Vista previa para invitados: IA real, sin herramientas ni datos guardados."""
    client_key = request.client.host if request.client else "unknown"
    if not demo_limiter.allow(client_key):
        raise RateLimitError()

    async def stream() -> AsyncIterator[str]:
        try:
            history = [
                Message(role=turn.role, content=turn.content) for turn in data.history
            ]
            async for event in agent_service.stream_demo_reply(
                chat_fn, data.message, history, data.timezone
            ):
                yield _sse(event.type, event.data)
        except AppError as exc:
            logger.error("Chat demo falló (%s): %s", exc.code, exc.message)
            yield _sse("error", {"code": exc.code, "message": exc.message})
            return
        except Exception:
            logger.exception("Error inesperado en la demo del chat.")
            yield _sse(
                "error",
                {"code": "processing_error", "message": "No se pudo procesar la solicitud."},
            )
            return
        yield _sse("done", {})

    return StreamingResponse(
        stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.post("")
async def chat(
    data: ChatRequest,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
    chat_fn: ChatFn = Depends(get_chat_fn),
) -> StreamingResponse:
    if data.conversation_id is not None:
        await conversation_service.get_conversation(
            session, current_user.id, data.conversation_id
        )

    async def stream() -> AsyncIterator[str]:
        try:
            async for event in agent_service.stream_reply(
                session,
                chat_fn,
                current_user,
                data.message,
                data.conversation_id,
            ):
                yield _sse(event.type, event.data)
        except AppError as exc:
            logger.error(
                "Chat falló (user=%s, %s): %s",
                current_user.id,
                exc.code,
                exc.message,
            )
            yield _sse("error", {"code": exc.code, "message": exc.message})
            return
        except Exception:
            logger.exception("Error inesperado en el chat.")
            yield _sse(
                "error",
                {"code": "processing_error", "message": "No se pudo procesar la solicitud."},
            )
            return
        yield _sse("done", {})

    return StreamingResponse(
        stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.post(
    "/conversations", response_model=ConversationRead, status_code=status.HTTP_201_CREATED
)
async def create_conversation(
    data: ConversationCreate | None = None,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> Conversation:
    title = data.title if data and data.title else conversation_service.DEFAULT_TITLE
    return await conversation_service.create_conversation(
        session, current_user.id, title
    )


@router.get("/conversations", response_model=list[ConversationRead])
async def conversations(
    limit: int = Query(default=50, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> list[Conversation]:
    return await conversation_service.list_conversations(
        session, current_user.id, limit
    )


@router.get(
    "/conversations/{conversation_id}/messages", response_model=list[ChatMessageRead]
)
async def conversation_messages(
    conversation_id: uuid.UUID,
    limit: int = Query(default=chat_message_service.HISTORY_PAGE_LIMIT, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> list[ChatMessage]:
    await conversation_service.get_conversation(
        session, current_user.id, conversation_id
    )
    return await chat_message_service.list_history(
        session, current_user.id, limit=limit, conversation_id=conversation_id
    )


@router.post(
    "/conversations/{conversation_id}/messages",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def save_exchange(
    conversation_id: uuid.UUID,
    data: ExchangeCreate,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> Response:
    await conversation_service.get_conversation(
        session, current_user.id, conversation_id
    )
    await chat_message_service.add_exchange(
        session,
        current_user.id,
        data.user_text,
        data.assistant_text,
        conversation_id=conversation_id,
        cards=data.cards,
    )
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/history", response_model=list[ChatMessageRead])
async def history(
    limit: int = Query(default=chat_message_service.HISTORY_PAGE_LIMIT, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> list[ChatMessage]:
    """Historial global reciente (compatibilidad). El sidebar usa /conversations."""
    return await chat_message_service.list_history(session, current_user.id, limit)
