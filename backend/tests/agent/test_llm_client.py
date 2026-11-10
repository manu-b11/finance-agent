import json

import httpx
import pytest

from app.agent.llm_client import (
    GeminiClient,
    Message,
    ToolCall,
    ToolSpec,
    parse_gemini_response,
    to_gemini_request,
)
from app.core.errors import AIUnavailableError, ProcessingError

SPEC = ToolSpec(
    name="get_balance",
    description="Balance",
    parameters={"type": "object", "properties": {}},
)


def test_request_translates_roles_and_tools():
    call = ToolCall(id="1", name="get_balance", arguments={}, signature="sig")
    messages = [
        Message("system", "reglas"),
        Message("user", "¿cuánto tengo?"),
        Message("assistant", "", tool_calls=(call,)),
        Message("tool", json.dumps({"balance": "10.00"}), tool_call_id="1", name="get_balance"),
    ]
    body = to_gemini_request(messages, [SPEC])
    assert body["systemInstruction"] == {"parts": [{"text": "reglas"}]}
    roles = [content["role"] for content in body["contents"]]
    assert roles == ["user", "model", "user"]
    model_part = body["contents"][1]["parts"][0]
    assert model_part["functionCall"] == {"name": "get_balance", "args": {}}
    assert model_part["thoughtSignature"] == "sig"
    assert body["contents"][2]["parts"][0]["functionResponse"] == {
        "name": "get_balance",
        "response": {"balance": "10.00"},
    }
    declaration = body["tools"][0]["functionDeclarations"][0]
    assert declaration["name"] == "get_balance"
    assert declaration["parametersJsonSchema"] == SPEC.parameters


def test_request_groups_consecutive_tool_results_in_one_turn():
    calls = (
        ToolCall(id="1", name="get_balance", arguments={}),
        ToolCall(id="2", name="list_transactions", arguments={}),
    )
    messages = [
        Message("user", "resumen"),
        Message("assistant", "", tool_calls=calls),
        Message("tool", "{}", tool_call_id="1", name="get_balance"),
        Message("tool", "{}", tool_call_id="2", name="list_transactions"),
    ]
    body = to_gemini_request(messages, [])
    assert "tools" not in body
    assert len(body["contents"]) == 3
    assert len(body["contents"][2]["parts"]) == 2


def test_parse_text_response():
    data = {"candidates": [{"content": {"parts": [{"text": "Hola"}]}}]}
    response = parse_gemini_response(data)
    assert response.text == "Hola"
    assert response.tool_calls == ()


def test_parse_function_call_keeps_signature_and_skips_thoughts():
    data = {
        "candidates": [
            {
                "content": {
                    "parts": [
                        {"text": "pensando", "thought": True},
                        {
                            "functionCall": {"name": "get_balance", "args": {"start_date": "2026-11-01"}},
                            "thoughtSignature": "abc",
                        },
                    ]
                }
            }
        ]
    }
    response = parse_gemini_response(data)
    assert response.text is None
    assert response.tool_calls[0].name == "get_balance"
    assert response.tool_calls[0].arguments == {"start_date": "2026-11-01"}
    assert response.tool_calls[0].signature == "abc"
    assert response.tool_calls[0].id


def test_parse_without_candidates_raises_processing_error():
    with pytest.raises(ProcessingError):
        parse_gemini_response({"promptFeedback": {"blockReason": "SAFETY"}})


async def test_client_sends_key_header_and_parses_response():
    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["key"] = request.headers["x-goog-api-key"]
        seen["url"] = str(request.url)
        return httpx.Response(200, json={"candidates": [{"content": {"parts": [{"text": "ok"}]}}]})

    client = GeminiClient("k", "modelo-x", 5, transport=httpx.MockTransport(handler))
    response = await client.chat([Message("user", "hola")], [])
    assert response.text == "ok"
    assert seen["key"] == "k"
    assert "modelo-x:generateContent" in seen["url"]


async def test_client_maps_http_errors_to_ai_unavailable():
    transport = httpx.MockTransport(lambda request: httpx.Response(500, text="boom"))
    client = GeminiClient("k", "m", 5, transport=transport)
    with pytest.raises(AIUnavailableError):
        await client.chat([Message("user", "hola")], [])


async def test_client_maps_network_errors_to_ai_unavailable():
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("sin red")

    client = GeminiClient("k", "m", 5, transport=httpx.MockTransport(handler))
    with pytest.raises(AIUnavailableError):
        await client.chat([Message("user", "hola")], [])


async def test_client_without_api_key_raises_ai_unavailable():
    client = GeminiClient("", "m", 5)
    with pytest.raises(AIUnavailableError):
        await client.chat([Message("user", "hola")], [])


def test_user_message_images_are_sent_as_inline_data_before_text():
    import base64

    from app.core.media import ImagePart

    image = ImagePart("image/jpeg", b"\xff\xd8\xff-bytes")
    body = to_gemini_request([Message("user", "Extrae", images=(image,))], [])
    parts = body["contents"][0]["parts"]
    assert parts[0] == {
        "inlineData": {
            "mimeType": "image/jpeg",
            "data": base64.b64encode(b"\xff\xd8\xff-bytes").decode("ascii"),
        }
    }
    assert parts[1] == {"text": "Extrae"}
