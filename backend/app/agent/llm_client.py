import base64
import json
import logging
import uuid
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any, Literal

import httpx

from app.core.config import settings
from app.core.errors import AIUnavailableError, ProcessingError
from app.core.media import ImagePart

logger = logging.getLogger(__name__)

GEMINI_URL = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
OLLAMA_CHAT_PATH = "/api/chat"


@dataclass(frozen=True)
class ToolCall:
    id: str
    name: str
    arguments: dict[str, Any]
    signature: str | None = None


@dataclass(frozen=True)
class ToolSpec:
    name: str
    description: str
    parameters: dict[str, Any]


@dataclass(frozen=True)
class Message:
    role: Literal["system", "user", "assistant", "tool"]
    content: str = ""
    tool_calls: tuple[ToolCall, ...] = ()
    tool_call_id: str | None = None
    name: str | None = None
    images: tuple[ImagePart, ...] = ()


@dataclass(frozen=True)
class LLMResponse:
    text: str | None = None
    tool_calls: tuple[ToolCall, ...] = ()


ChatFn = Callable[[list[Message], list[ToolSpec]], Awaitable[LLMResponse]]


def _tool_response_part(message: Message) -> dict[str, Any]:
    try:
        payload = json.loads(message.content)
    except json.JSONDecodeError:
        payload = {"result": message.content}
    if not isinstance(payload, dict):
        payload = {"result": payload}
    return {"functionResponse": {"name": message.name, "response": payload}}


def to_gemini_request(messages: list[Message], tools: list[ToolSpec]) -> dict[str, Any]:
    system_parts: list[dict[str, Any]] = []
    contents: list[dict[str, Any]] = []
    for message in messages:
        if message.role == "system":
            system_parts.append({"text": message.content})
        elif message.role == "user":
            user_parts: list[dict[str, Any]] = [
                {
                    "inlineData": {
                        "mimeType": image.mime_type,
                        "data": base64.b64encode(image.data).decode("ascii"),
                    }
                }
                for image in message.images
            ]
            user_parts.append({"text": message.content})
            contents.append({"role": "user", "parts": user_parts})
        elif message.role == "assistant":
            parts: list[dict[str, Any]] = []
            if message.content:
                parts.append({"text": message.content})
            for call in message.tool_calls:
                part: dict[str, Any] = {
                    "functionCall": {"name": call.name, "args": call.arguments}
                }
                if call.signature:
                    part["thoughtSignature"] = call.signature
                parts.append(part)
            if parts:
                contents.append({"role": "model", "parts": parts})
        else:
            part = _tool_response_part(message)
            last = contents[-1] if contents else None
            if last and last["role"] == "user" and "functionResponse" in last["parts"][0]:
                last["parts"].append(part)
            else:
                contents.append({"role": "user", "parts": [part]})
    body: dict[str, Any] = {
        "contents": contents,
        "generationConfig": {"temperature": 0.2},
    }
    if system_parts:
        body["systemInstruction"] = {"parts": system_parts}
    if tools:
        body["tools"] = [
            {
                "functionDeclarations": [
                    {
                        "name": tool.name,
                        "description": tool.description,
                        "parametersJsonSchema": tool.parameters,
                    }
                    for tool in tools
                ]
            }
        ]
    return body


def parse_gemini_response(data: dict[str, Any]) -> LLMResponse:
    candidates = data.get("candidates") or []
    if not candidates:
        raise ProcessingError("La IA no pudo generar una respuesta.")
    parts = (candidates[0].get("content") or {}).get("parts") or []
    texts: list[str] = []
    calls: list[ToolCall] = []
    for part in parts:
        if part.get("thought"):
            continue
        if "functionCall" in part:
            function_call = part["functionCall"]
            calls.append(
                ToolCall(
                    id=function_call.get("id") or uuid.uuid4().hex,
                    name=function_call["name"],
                    arguments=function_call.get("args") or {},
                    signature=part.get("thoughtSignature"),
                )
            )
        elif part.get("text"):
            texts.append(part["text"])
    text = "".join(texts).strip() or None
    return LLMResponse(text=text, tool_calls=tuple(calls))


class GeminiClient:
    def __init__(
        self,
        api_key: str,
        model: str,
        timeout: float,
        transport: httpx.AsyncBaseTransport | None = None,
    ):
        self._api_key = api_key
        self._model = model
        self._timeout = timeout
        self._transport = transport

    async def chat(self, messages: list[Message], tools: list[ToolSpec]) -> LLMResponse:
        if not self._api_key:
            logger.error("GEMINI_API_KEY no está configurada.")
            raise AIUnavailableError()
        try:
            async with httpx.AsyncClient(timeout=self._timeout, transport=self._transport) as client:
                response = await client.post(
                    GEMINI_URL.format(model=self._model),
                    json=to_gemini_request(messages, tools),
                    headers={"x-goog-api-key": self._api_key},
                )
        except httpx.HTTPError as exc:
            logger.exception("Fallo de red al llamar a Gemini.")
            raise AIUnavailableError() from exc
        if response.status_code >= 400:
            logger.error("Gemini respondió %s: %s", response.status_code, response.text[:500])
            raise AIUnavailableError()
        return parse_gemini_response(response.json())


def to_ollama_request(
    model: str, messages: list[Message], tools: list[ToolSpec]
) -> dict[str, Any]:
    converted: list[dict[str, Any]] = []
    for message in messages:
        if message.role == "tool":
            converted.append(
                {"role": "tool", "content": message.content, "tool_name": message.name}
            )
            continue
        item: dict[str, Any] = {"role": message.role, "content": message.content}
        if message.role == "user" and message.images:
            item["images"] = [
                base64.b64encode(image.data).decode("ascii") for image in message.images
            ]
        if message.role == "assistant" and message.tool_calls:
            item["tool_calls"] = [
                {"function": {"name": call.name, "arguments": call.arguments}}
                for call in message.tool_calls
            ]
        converted.append(item)
    body: dict[str, Any] = {
        "model": model,
        "messages": converted,
        "stream": False,
        "options": {"temperature": 0.2},
    }
    if tools:
        body["tools"] = [
            {
                "type": "function",
                "function": {
                    "name": tool.name,
                    "description": tool.description,
                    "parameters": tool.parameters,
                },
            }
            for tool in tools
        ]
    return body


def parse_ollama_response(data: dict[str, Any]) -> LLMResponse:
    message = data.get("message") or {}
    calls: list[ToolCall] = []
    for raw in message.get("tool_calls") or []:
        function = raw.get("function") or {}
        arguments = function.get("arguments") or {}
        if isinstance(arguments, str):
            try:
                arguments = json.loads(arguments)
            except json.JSONDecodeError:
                arguments = {}
        calls.append(
            ToolCall(
                id=raw.get("id") or uuid.uuid4().hex,
                name=function["name"],
                arguments=arguments,
            )
        )
    text = (message.get("content") or "").strip() or None
    if text is None and not calls:
        raise ProcessingError("La IA no pudo generar una respuesta.")
    return LLMResponse(text=text, tool_calls=tuple(calls))


class OllamaClient:
    def __init__(
        self,
        api_key: str,
        base_url: str,
        model: str,
        timeout: float,
        transport: httpx.AsyncBaseTransport | None = None,
    ):
        self._api_key = api_key
        self._base_url = base_url.rstrip("/")
        self._model = model
        self._timeout = timeout
        self._transport = transport

    async def chat(self, messages: list[Message], tools: list[ToolSpec]) -> LLMResponse:
        headers = {"Authorization": f"Bearer {self._api_key}"} if self._api_key else {}
        try:
            async with httpx.AsyncClient(timeout=self._timeout, transport=self._transport) as client:
                response = await client.post(
                    f"{self._base_url}{OLLAMA_CHAT_PATH}",
                    json=to_ollama_request(self._model, messages, tools),
                    headers=headers,
                )
        except httpx.HTTPError as exc:
            logger.exception("Fallo de red al llamar a Ollama.")
            raise AIUnavailableError() from exc
        if response.status_code >= 400:
            logger.error("Ollama respondió %s: %s", response.status_code, response.text[:500])
            raise AIUnavailableError()
        return parse_ollama_response(response.json())


async def chat(messages: list[Message], tools: list[ToolSpec]) -> LLMResponse:
    gemini = GeminiClient(
        settings.gemini_api_key, settings.gemini_model, settings.llm_timeout_seconds
    )
    try:
        return await gemini.chat(messages, tools)
    except (AIUnavailableError, ProcessingError):
        if not settings.ollama_api_key:
            raise
        logger.warning("Gemini no disponible; usando Ollama como alternativa.")
    ollama = OllamaClient(
        settings.ollama_api_key,
        settings.ollama_base_url,
        settings.ollama_model,
        settings.llm_timeout_seconds,
    )
    return await ollama.chat(messages, tools)
