from collections.abc import AsyncIterator

from sqlalchemy.ext.asyncio import AsyncSession

from app.agent import orchestrator
from app.agent.llm_client import ChatFn, Message
from app.agent.orchestrator import AgentEvent
from app.agent.prompts import build_system_prompt
from app.core.clock import local_today
from app.models.user import User
from app.services import chat_message as chat_message_service


async def stream_reply(
    session: AsyncSession, chat: ChatFn, user: User, text: str
) -> AsyncIterator[AgentEvent]:
    user_id = user.id
    timezone = user.timezone
    history = await chat_message_service.get_recent_messages(session, user_id)
    messages = [
        Message(role="system", content=build_system_prompt(local_today(timezone), timezone)),
        *(Message(role=item.role, content=item.content) for item in history),
        Message(role="user", content=text),
    ]
    async for event in orchestrator.run(chat, session, user_id, messages):
        if event.type == "message":
            await chat_message_service.add_exchange(session, user_id, text, event.data["text"])
        yield event
