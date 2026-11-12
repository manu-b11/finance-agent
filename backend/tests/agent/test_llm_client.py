import json

import httpx
import pytest

from app.agent.llm_client import (
    GeminiClient,
    LLMResponse,
    Message,
    OllamaClient,
    OpenAICompatClient,
    ToolCall,
    ToolSpec,
    parse_gemini_response,
    parse_openai_response,
    to_gemini_request,
    to_ollama_request,
    to_openai_request,
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


async def test_transient_network_error_is_retried(monkeypatch):
    from app.agent import llm_client

    monkeypatch.setattr(llm_client, "NETWORK_RETRY_DELAY_SECONDS", 0)
    calls = {"count": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["count"] += 1
        if calls["count"] == 1:
            raise httpx.ReadError("corte puntual")
        return httpx.Response(200, json={"choices": [{"message": {"content": "ok"}}]})

    client = OpenAICompatClient(
        "k",
        "https://openrouter.ai/api/v1",
        "qwen/x",
        5,
        transport=httpx.MockTransport(handler),
    )
    response = await client.chat([Message("user", "hola")], [])
    assert response.text == "ok"
    assert calls["count"] == 2


async def test_persistent_network_error_stops_after_retry(monkeypatch):
    from app.agent import llm_client

    monkeypatch.setattr(llm_client, "NETWORK_RETRY_DELAY_SECONDS", 0)
    calls = {"count": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["count"] += 1
        raise httpx.ReadError("sin conexión")

    client = OpenAICompatClient(
        "k",
        "https://openrouter.ai/api/v1",
        "qwen/x",
        5,
        transport=httpx.MockTransport(handler),
    )
    with pytest.raises(AIUnavailableError):
        await client.chat([Message("user", "hola")], [])
    assert calls["count"] == llm_client.NETWORK_ATTEMPTS


async def test_client_without_api_key_raises_ai_unavailable():
    client = GeminiClient("", "m", 5)
    with pytest.raises(AIUnavailableError):
        await client.chat([Message("user", "hola")], [])


def test_ollama_request_includes_context_think_and_keep_alive():
    body = to_ollama_request(
        "m", [Message("user", "hola")], [], num_ctx=8192, think=False, keep_alive="30m"
    )
    assert body["options"]["num_ctx"] == 8192
    assert body["think"] is False
    assert body["keep_alive"] == "30m"


async def test_local_ollama_sends_options_without_key():
    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["auth"] = request.headers.get("authorization")
        seen["body"] = json.loads(request.content)
        return httpx.Response(200, json={"message": {"content": "ok"}})

    client = OllamaClient(
        "",
        "http://localhost:11434",
        "qwen3-vl:8b",
        5,
        transport=httpx.MockTransport(handler),
        num_ctx=8192,
        think=False,
        keep_alive="30m",
    )
    response = await client.chat([Message("user", "hola")], [])
    assert response.text == "ok"
    assert seen["auth"] is None
    assert seen["body"]["options"]["num_ctx"] == 8192
    assert seen["body"]["think"] is False
    assert seen["body"]["keep_alive"] == "30m"


async def test_chat_uses_local_ollama_as_fallback_without_api_key(monkeypatch):
    from app.agent import llm_client

    monkeypatch.setattr(llm_client.settings, "gemini_api_key", "")
    monkeypatch.setattr(llm_client.settings, "qwen_api_key", "")
    monkeypatch.setattr(llm_client.settings, "ollama_api_key", "")
    monkeypatch.setattr(llm_client.settings, "ollama_base_url", "http://localhost:11434")
    seen = {}

    class FakeOllama:
        def __init__(self, *args, **kwargs):
            seen["kwargs"] = kwargs

        async def chat(self, messages, tools):
            return LLMResponse(text="respaldo")

    monkeypatch.setattr(llm_client, "OllamaClient", FakeOllama)
    response = await llm_client.chat([Message("user", "hola")], [])
    assert response.text == "respaldo"
    assert seen["kwargs"]["num_ctx"] == llm_client.settings.ollama_num_ctx
    assert seen["kwargs"]["think"] is llm_client.settings.ollama_think


def test_openai_request_translates_tools_and_tool_results():
    call = ToolCall(
        id="call_1", name="get_balance", arguments={"start_date": "2026-11-01"}
    )
    messages = [
        Message("system", "reglas"),
        Message("user", "¿cuánto tengo?"),
        Message("assistant", "", tool_calls=(call,)),
        Message("tool", '{"balance": "10.00"}', tool_call_id="call_1", name="get_balance"),
    ]
    body = to_openai_request("qwen/x", messages, [SPEC])
    assert body["model"] == "qwen/x"
    assert body["tool_choice"] == "auto"
    assert body["tools"][0]["function"]["name"] == "get_balance"
    assistant = body["messages"][2]
    assert assistant["tool_calls"][0]["id"] == "call_1"
    assert json.loads(assistant["tool_calls"][0]["function"]["arguments"]) == {
        "start_date": "2026-11-01"
    }
    result = body["messages"][3]
    assert result["role"] == "tool"
    assert result["tool_call_id"] == "call_1"


def test_openai_request_sends_images_as_data_urls():
    from app.core.media import ImagePart

    image = ImagePart("image/jpeg", b"abc")
    body = to_openai_request("m", [Message("user", "Extrae", images=(image,))], [])
    parts = body["messages"][0]["content"]
    assert parts[0] == {"type": "text", "text": "Extrae"}
    assert parts[1]["image_url"]["url"].startswith("data:image/jpeg;base64,")


def test_parse_openai_tool_call_with_string_arguments():
    data = {
        "choices": [
            {
                "message": {
                    "content": None,
                    "tool_calls": [
                        {
                            "id": "call_1",
                            "type": "function",
                            "function": {
                                "name": "get_balance",
                                "arguments": '{"start_date": "2026-11-01"}',
                            },
                        }
                    ],
                }
            }
        ]
    }
    response = parse_openai_response(data)
    assert response.text is None
    assert response.tool_calls[0].id == "call_1"
    assert response.tool_calls[0].name == "get_balance"
    assert response.tool_calls[0].arguments == {"start_date": "2026-11-01"}


async def test_openai_client_sends_bearer_and_parses_response():
    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["auth"] = request.headers["authorization"]
        seen["url"] = str(request.url)
        seen["body"] = json.loads(request.content)
        return httpx.Response(200, json={"choices": [{"message": {"content": "ok"}}]})

    client = OpenAICompatClient(
        "k",
        "https://openrouter.ai/api/v1",
        "qwen/qwen3.7-flash",
        5,
        transport=httpx.MockTransport(handler),
    )
    response = await client.chat([Message("user", "hola")], [])
    assert response.text == "ok"
    assert seen["auth"] == "Bearer k"
    assert seen["url"] == "https://openrouter.ai/api/v1/chat/completions"
    assert seen["body"]["model"] == "qwen/qwen3.7-flash"


async def test_chat_uses_qwen_when_gemini_fails(monkeypatch):
    from app.agent import llm_client

    monkeypatch.setattr(llm_client.settings, "gemini_api_key", "")
    monkeypatch.setattr(llm_client.settings, "qwen_api_key", "k")
    seen = {}

    class FakeQwen:
        def __init__(self, *args, **kwargs):
            seen["args"] = args

        async def chat(self, messages, tools):
            return LLMResponse(text="qwen")

    monkeypatch.setattr(llm_client, "OpenAICompatClient", FakeQwen)
    response = await llm_client.chat([Message("user", "hola")], [])
    assert response.text == "qwen"
    assert seen["args"][1] == llm_client.settings.qwen_base_url
    assert seen["args"][2] == llm_client.settings.qwen_model


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
