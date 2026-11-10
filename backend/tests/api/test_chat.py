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
    assert parse_sse(response.text) == [
        ("tool_call", {"name": "add_transaction"}),
        ("message", {"text": "Registré tu almuerzo por 25.000."}),
        ("done", {}),
    ]
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
