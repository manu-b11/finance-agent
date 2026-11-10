import json
import logging
from collections.abc import AsyncIterator
from typing import Any

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.agent import service as agent_service
from app.agent.llm_client import ChatFn
from app.api.deps import get_chat_fn, get_current_user
from app.core.database import get_session
from app.core.errors import AppError
from app.models.user import User
from app.schemas.chat import ChatRequest

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/chat", tags=["chat"])


def _sse(event: str, data: dict[str, Any]) -> str:
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


@router.post("")
async def chat(
    data: ChatRequest,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
    chat_fn: ChatFn = Depends(get_chat_fn),
) -> StreamingResponse:
    async def stream() -> AsyncIterator[str]:
        try:
            async for event in agent_service.stream_reply(
                session, chat_fn, current_user, data.message
            ):
                yield _sse(event.type, event.data)
        except AppError as exc:
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
