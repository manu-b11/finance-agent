import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.chat_message import ChatMessage

HISTORY_LIMIT = 20


async def get_recent_messages(
    session: AsyncSession, user_id: uuid.UUID, limit: int = HISTORY_LIMIT
) -> list[ChatMessage]:
    result = await session.execute(
        select(ChatMessage)
        .where(ChatMessage.user_id == user_id)
        .order_by(ChatMessage.id.desc())
        .limit(limit)
    )
    messages = list(reversed(result.scalars().all()))
    while messages and messages[0].role != "user":
        messages.pop(0)
    return messages


async def add_exchange(
    session: AsyncSession, user_id: uuid.UUID, user_text: str, assistant_text: str
) -> None:
    session.add(ChatMessage(user_id=user_id, role="user", content=user_text))
    await session.flush()
    session.add(ChatMessage(user_id=user_id, role="assistant", content=assistant_text))
    await session.commit()
