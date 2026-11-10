import pytest

from app.agent import service as agent_service
from app.core.errors import AIUnavailableError
from app.schemas.user import UserCreate
from app.services import auth as auth_service
from app.services import chat_message as chat_message_service
from tests.agent.fakes import FakeChat, calls_response, text_response, tool_call


async def make_user(session, email: str = "ana@example.com"):
    return await auth_service.register_user(
        session, UserCreate(email=email, password="clave-segura-1")
    )


async def reply(chat, session, user, text: str):
    return [event async for event in agent_service.stream_reply(session, chat, user, text)]


async def test_system_prompt_contains_current_date_and_timezone(session):
    user = await make_user(session)
    chat = FakeChat(text_response("Hola"))
    await reply(chat, session, user, "Hola")
    system = chat.calls[0][0][0]
    assert system.role == "system"
    assert agent_service.local_today(user.timezone).isoformat() in system.content
    assert user.timezone in system.content


async def test_exchange_is_persisted_and_sent_as_history_next_turn(session):
    user = await make_user(session)
    first = FakeChat(text_response("¿Cuánto fue?"))
    await reply(first, session, user, "Gasté en almuerzo")

    second = FakeChat(text_response("Listo"))
    await reply(second, session, user, "25000")
    sent = second.calls[0][0]
    assert [(m.role, m.content) for m in sent[1:]] == [
        ("user", "Gasté en almuerzo"),
        ("assistant", "¿Cuánto fue?"),
        ("user", "25000"),
    ]


async def test_nothing_is_persisted_when_ai_fails(session):
    user = await make_user(session)

    async def failing_chat(messages, tools):
        raise AIUnavailableError()

    with pytest.raises(AIUnavailableError):
        await reply(failing_chat, session, user, "Hola")
    assert await chat_message_service.get_recent_messages(session, user.id) == []


async def test_history_is_isolated_between_users(session):
    ana = await make_user(session, "ana@example.com")
    beto = await make_user(session, "beto@example.com")
    await reply(FakeChat(text_response("Hola Ana")), session, ana, "Soy Ana")
    chat = FakeChat(text_response("Hola"))
    await reply(chat, session, beto, "Hola")
    assert [m.content for m in chat.calls[0][0][1:]] == ["Hola"]


async def test_stream_reply_uses_only_authenticated_user_for_tools(session):
    ana = await make_user(session, "ana@example.com")
    beto = await make_user(session, "beto@example.com")
    chat = FakeChat(
        calls_response(
            tool_call(
                "add_transaction",
                {
                    "type": "income",
                    "amount": 100,
                    "concept": "Salario",
                    "occurred_on": "2026-11-01",
                },
            )
        ),
        text_response("Listo"),
    )
    await reply(chat, session, ana, "Me pagaron 100")
    from app.tools import transactions as tools

    assert (await tools.list_transactions(session, ana.id, {}))["count"] == 1
    assert (await tools.list_transactions(session, beto.id, {}))["count"] == 0


async def test_stream_reply_persists_after_tool_error_rollback(session):
    user = await make_user(session)
    chat = FakeChat(
        calls_response(
            tool_call(
                "delete_transaction",
                {"transaction_id": "00000000-0000-0000-0000-000000000000"},
            )
        ),
        text_response("No encontré ese movimiento."),
    )
    user_id = user.id
    await reply(chat, session, user, "Borra el gasto")
    messages = await chat_message_service.get_recent_messages(session, user_id)
    assert [m.role for m in messages] == ["user", "assistant"]
