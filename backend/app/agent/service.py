import uuid
from collections.abc import AsyncIterator

from sqlalchemy.ext.asyncio import AsyncSession

from app.agent import orchestrator
from app.agent.llm_client import ChatFn, Message
from app.agent.orchestrator import AgentEvent
from app.agent.prompts import build_demo_prompt, build_system_prompt
from app.core.clock import local_today
from app.core.errors import ProcessingError
from app.models.user import User
from app.services import chat_message as chat_message_service
from app.services import conversation as conversation_service

DEMO_HISTORY_LIMIT = 8


async def stream_demo_reply(
    chat: ChatFn,
    text: str,
    history: list[Message],
    timezone: str,
) -> AsyncIterator[AgentEvent]:
    """Respuesta de la demo pública: sin herramientas y sin datos del usuario."""
    messages = [
        Message(role="system", content=build_demo_prompt(local_today(timezone), timezone)),
        *history[-DEMO_HISTORY_LIMIT:],
        Message(role="user", content=text),
    ]
    response = await chat(messages, [])
    if not response.text:
        raise ProcessingError("La IA no pudo generar una respuesta.")
    yield AgentEvent("message", {"text": response.text})


async def stream_reply(
    session: AsyncSession,
    chat: ChatFn,
    user: User,
    text: str,
    conversation_id: uuid.UUID | None = None,
) -> AsyncIterator[AgentEvent]:
    user_id = user.id
    timezone = user.timezone
    conversation = None
    if conversation_id is not None:
        conversation = await conversation_service.get_conversation(
            session, user_id, conversation_id
        )
    else:
        # Compatibilidad: sin conversation_id se continúa la conversación más reciente.
        conversation = await conversation_service.get_latest_conversation(session, user_id)
    history = (
        await chat_message_service.get_recent_messages(
            session, user_id, conversation_id=conversation.id
        )
        if conversation is not None
        else []
    )
    messages = [
        Message(role="system", content=build_system_prompt(local_today(timezone), timezone)),
        *(Message(role=item.role, content=item.content) for item in history),
        Message(role="user", content=text),
    ]
    async for event in orchestrator.run(chat, session, user_id, messages):
        if event.type == "message":
            created = None
            if conversation is None:
                conversation = await conversation_service.create_conversation(
                    session, user_id, conversation_service.title_from_text(text)
                )
                created = conversation
            await chat_message_service.add_exchange(
                session,
                user_id,
                text,
                event.data["text"],
                conversation_id=conversation.id,
            )
            if created is not None:
                yield AgentEvent(
                    "conversation", conversation_service.event_payload(created)
                )
        yield event
