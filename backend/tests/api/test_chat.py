import json

from app.api.deps import get_chat_fn
from app.core.errors import AIUnavailableError
from app.main import app
from app.tools import transactions as tools
from tests.agent.fakes import FakeChat, calls_response, text_response, tool_call

PAYLOAD = {"email": "ana@example.com", "password": "clave-segura-1"}


async def auth_headers(client, payload=PAYLOAD) -> dict[str, str]:
    await client.post("/auth/register", json=payload)
    response = await client.post("/auth/login", json=payload)
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def parse_sse(body: str) -> list[tuple[str, dict]]:
    events = []
    for block in body.strip().split("\n\n"):
        event_line, data_line = block.split("\n")
        events.append(
            (event_line.removeprefix("event: "), json.loads(data_line.removeprefix("data: ")))
        )
    return events


def use_chat(fake) -> None:
    app.dependency_overrides[get_chat_fn] = lambda: fake


async def test_chat_requires_authentication(client):
    response = await client.post("/chat", json={"message": "hola"})
    assert response.status_code == 401


async def test_chat_rejects_empty_message(client):
    headers = await auth_headers(client)
    response = await client.post("/chat", json={"message": "   "}, headers=headers)
    assert response.status_code == 422


async def test_chat_rejects_extra_fields(client):
    headers = await auth_headers(client)
    response = await client.post(
        "/chat", json={"message": "hola", "user_id": "x"}, headers=headers
    )
    assert response.status_code == 422


async def test_chat_streams_events_and_executes_tools(client, session):
    headers = await auth_headers(client)
    use_chat(
        FakeChat(
            calls_response(
                tool_call(
                    "add_transaction",
                    {
                        "type": "expense",
                        "amount": 25000,
                        "concept": "Almuerzo",
                        "occurred_on": "2026-11-05",
                        "category": "alimentacion",
                    },
                )
            ),
            text_response("Registré tu almuerzo por 25.000."),
        )
    )
    response = await client.post("/chat", json={"message": "Gasté 25000 en almuerzo"}, headers=headers)
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/event-stream")
    events = parse_sse(response.text)
    assert [name for name, _ in events] == [
        "tool_call",
        "tool_result",
        "conversation",
        "message",
        "done",
    ]
    assert events[0][1] == {"name": "add_transaction"}
    assert events[1][1]["name"] == "add_transaction"
    assert events[1][1]["result"]["concept"] == "Almuerzo"
    assert events[2][1]["title"] == "Gasté 25000 en almuerzo"
    assert events[3][1] == {"text": "Registré tu almuerzo por 25.000."}
    assert events[4][1] == {}
    user_id = (await client.get("/auth/me", headers=headers)).json()["id"]
    import uuid

    listed = await tools.list_transactions(session, uuid.UUID(user_id), {})
    assert listed["count"] == 1


async def test_chat_reports_ai_unavailable_as_error_event(client):
    headers = await auth_headers(client)

    async def failing_chat(messages, tools):
        raise AIUnavailableError()

    use_chat(failing_chat)
    response = await client.post("/chat", json={"message": "hola"}, headers=headers)
    assert response.status_code == 200
    events = parse_sse(response.text)
    assert events == [
        (
            "error",
            {"code": "ai_unavailable", "message": "El servicio de IA no está disponible en este momento."},
        )
    ]


async def test_chat_reports_unexpected_errors_without_leaking_details(client):
    headers = await auth_headers(client)

    async def broken_chat(messages, tools):
        raise RuntimeError("secreto interno")

    use_chat(broken_chat)
    response = await client.post("/chat", json={"message": "hola"}, headers=headers)
    assert "secreto interno" not in response.text
    assert parse_sse(response.text)[0][0] == "error"


async def test_history_requires_authentication(client):
    response = await client.get("/chat/history")
    assert response.status_code == 401


async def test_history_returns_saved_messages(client):
    headers = await auth_headers(client)
    use_chat(FakeChat(text_response("Hola, ¿en qué te ayudo?")))
    await client.post("/chat", json={"message": "hola"}, headers=headers)
    response = await client.get("/chat/history", headers=headers)
    assert response.status_code == 200
    body = response.json()
    assert [(m["role"], m["content"]) for m in body] == [
        ("user", "hola"),
        ("assistant", "Hola, ¿en qué te ayudo?"),
    ]


async def test_history_is_empty_for_new_user_and_isolated(client):
    ana = await auth_headers(client)
    use_chat(FakeChat(text_response("Hola ana")))
    await client.post("/chat", json={"message": "hola"}, headers=ana)
    beto = await auth_headers(client, {"email": "beto@example.com", "password": "clave-segura-1"})
    response = await client.get("/chat/history", headers=beto)
    assert response.status_code == 200
    assert response.json() == []


async def test_history_rejects_invalid_limit(client):
    headers = await auth_headers(client)
    response = await client.get("/chat/history?limit=0", headers=headers)
    assert response.status_code == 422


async def test_chat_creates_conversation_and_lists_it_with_title(client):
    headers = await auth_headers(client)
    use_chat(FakeChat(text_response("Hola, ¿en qué te ayudo?")))
    response = await client.post("/chat", json={"message": "Hola"}, headers=headers)
    events = parse_sse(response.text)
    conversation_event = next(data for name, data in events if name == "conversation")
    assert conversation_event["title"] == "Hola"

    response = await client.get("/chat/conversations", headers=headers)
    assert response.status_code == 200
    body = response.json()
    assert len(body) == 1
    assert body[0]["id"] == conversation_event["id"]
    assert body[0]["title"] == "Hola"


async def test_conversation_messages_are_separated_by_conversation(client):
    headers = await auth_headers(client)
    first = await client.post("/chat/conversations", headers=headers)
    second = await client.post("/chat/conversations", headers=headers)
    assert first.status_code == 201
    assert second.status_code == 201

    use_chat(FakeChat(text_response("Respuesta uno")))
    await client.post(
        "/chat",
        json={"message": "Mensaje uno", "conversation_id": first.json()["id"]},
        headers=headers,
    )
    use_chat(FakeChat(text_response("Respuesta dos")))
    await client.post(
        "/chat",
        json={"message": "Mensaje dos", "conversation_id": second.json()["id"]},
        headers=headers,
    )

    one = await client.get(
        f"/chat/conversations/{first.json()['id']}/messages", headers=headers
    )
    two = await client.get(
        f"/chat/conversations/{second.json()['id']}/messages", headers=headers
    )
    assert [m["content"] for m in one.json()] == ["Mensaje uno", "Respuesta uno"]
    assert [m["content"] for m in two.json()] == ["Mensaje dos", "Respuesta dos"]

    conversations = (await client.get("/chat/conversations", headers=headers)).json()
    assert {c["title"] for c in conversations} == {"Mensaje uno", "Mensaje dos"}


async def test_conversations_are_isolated_between_users(client):
    ana = await auth_headers(client)
    beto = await auth_headers(
        client, {"email": "beto@example.com", "password": "clave-segura-1"}
    )
    created = await client.post("/chat/conversations", headers=ana)
    conversation_id = created.json()["id"]

    assert (await client.get("/chat/conversations", headers=beto)).json() == []
    response = await client.get(
        f"/chat/conversations/{conversation_id}/messages", headers=beto
    )
    assert response.status_code == 404
    response = await client.post(
        "/chat",
        json={"message": "Hola", "conversation_id": conversation_id},
        headers=beto,
    )
    assert response.status_code == 404

