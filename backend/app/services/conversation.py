import uuid
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import NotFoundError
from app.models.conversation import Conversation

DEFAULT_TITLE = "Nuevo chat"
MAX_TITLE = 120


def title_from_text(text: str) -> str:
    """Título corto a partir del primer mensaje del usuario."""
    title = " ".join(text.split())
    return (title[:MAX_TITLE].rstrip() or DEFAULT_TITLE)


def event_payload(conversation: Conversation) -> dict[str, str]:
    return {"id": str(conversation.id), "title": conversation.title}


async def create_conversation(
    session: AsyncSession, user_id: uuid.UUID, title: str = DEFAULT_TITLE
) -> Conversation:
    conversation = Conversation(user_id=user_id, title=title_from_text(title))
    session.add(conversation)
    await session.commit()
    await session.refresh(conversation)
    return conversation


async def get_conversation(
    session: AsyncSession, user_id: uuid.UUID, conversation_id: uuid.UUID
) -> Conversation:
    result = await session.execute(
        select(Conversation).where(
            Conversation.id == conversation_id, Conversation.user_id == user_id
        )
    )
    conversation = result.scalar_one_or_none()
    if conversation is None:
        raise NotFoundError("No se encontró la conversación.")
    return conversation


async def list_conversations(
    session: AsyncSession, user_id: uuid.UUID, limit: int = 50
) -> list[Conversation]:
    result = await session.execute(
        select(Conversation)
        .where(Conversation.user_id == user_id)
        .order_by(Conversation.updated_at.desc(), Conversation.id.desc())
        .limit(limit)
    )
    return list(result.scalars().all())


async def get_latest_conversation(
    session: AsyncSession, user_id: uuid.UUID
) -> Conversation | None:
    result = await session.execute(
        select(Conversation)
        .where(Conversation.user_id == user_id)
        .order_by(Conversation.updated_at.desc(), Conversation.id.desc())
        .limit(1)
    )
    return result.scalar_one_or_none()


def apply_first_message_title(conversation: Conversation, text: str) -> None:
    if conversation.title == DEFAULT_TITLE:
        conversation.title = title_from_text(text)


def touch(conversation: Conversation) -> None:
    conversation.updated_at = datetime.now(UTC)
