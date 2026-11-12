import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.chat_message import ChatMessage
from app.schemas.chat import ChatCard
from app.services import conversation as conversation_service

HISTORY_LIMIT = 20
HISTORY_PAGE_LIMIT = 50


async def get_recent_messages(
    session: AsyncSession,
    user_id: uuid.UUID,
    limit: int = HISTORY_LIMIT,
    conversation_id: uuid.UUID | None = None,
) -> list[ChatMessage]:
    query = select(ChatMessage).where(ChatMessage.user_id == user_id)
    if conversation_id is not None:
        query = query.where(ChatMessage.conversation_id == conversation_id)
    result = await session.execute(query.order_by(ChatMessage.id.desc()).limit(limit))
    messages = list(reversed(result.scalars().all()))
    while messages and messages[0].role != "user":
        messages.pop(0)
    return messages


async def add_exchange(
    session: AsyncSession,
    user_id: uuid.UUID,
    user_text: str,
    assistant_text: str,
    conversation_id: uuid.UUID | None = None,
    cards: list[ChatCard] | None = None,
) -> None:
    if conversation_id is None:
        conversation = await conversation_service.create_conversation(
            session, user_id, conversation_service.title_from_text(user_text)
        )
    else:
        conversation = await conversation_service.get_conversation(
            session, user_id, conversation_id
        )
    conversation_service.apply_first_message_title(conversation, user_text)
    conversation_service.touch(conversation)
    session.add(
        ChatMessage(
            user_id=user_id,
            conversation_id=conversation.id,
            role="user",
            content=user_text,
        )
    )
    await session.flush()
    session.add(
        ChatMessage(
            user_id=user_id,
            conversation_id=conversation.id,
            role="assistant",
            content=assistant_text,
            cards=[card.model_dump(mode="json") for card in cards or []],
        )
    )
    await session.commit()


async def list_history(
    session: AsyncSession,
    user_id: uuid.UUID,
    limit: int = HISTORY_PAGE_LIMIT,
    conversation_id: uuid.UUID | None = None,
) -> list[ChatMessage]:
    """Últimos `limit` mensajes del usuario, en orden cronológico.

    Sin `conversation_id` devuelve los más recientes de todas sus conversaciones.
    """
    query = select(ChatMessage).where(ChatMessage.user_id == user_id)
    if conversation_id is not None:
        query = query.where(ChatMessage.conversation_id == conversation_id)
    result = await session.execute(query.order_by(ChatMessage.id.desc()).limit(limit))
    return list(reversed(result.scalars().all()))
