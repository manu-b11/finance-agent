import asyncio
import base64
import json
import logging
import time
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
OPENAI_CHAT_PATH = "/chat/completions"

# Un corte de red puntual (ReadError, ConnectError, timeout…) no debe tumbar el turno.
NETWORK_ATTEMPTS = 2
NETWORK_RETRY_DELAY_SECONDS = 0.4


async def _post_with_retry(
    client: httpx.AsyncClient, url: str, *, provider: str, **kwargs: Any
) -> httpx.Response:
    attempt = 0
    while True:
        attempt += 1
        try:
            return await client.post(url, **kwargs)
        except httpx.TransportError as exc:
            if attempt >= NETWORK_ATTEMPTS:
                raise
            logger.warning(
                "Fallo de red con %s (%s: %s); reintentando %d/%d.",
                provider,
                type(exc).__name__,
                exc,
                attempt + 1,
                NETWORK_ATTEMPTS,
            )
            await asyncio.sleep(NETWORK_RETRY_DELAY_SECONDS)


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


def _error_detail(response: httpx.Response) -> str:
    """Mensaje legible de un error HTTP del proveedor de IA."""
    try:
        payload = response.json()
    except ValueError:
        return response.text[:500] or "(sin cuerpo)"
    error = payload.get("error") if isinstance(payload, dict) else None
    if isinstance(error, dict):
        status = error.get("status")
        message = error.get("message")
        if message:
            return f"{status}: {message}" if status else str(message)
    if isinstance(error, str):
        return error[:500]
    return response.text[:500] or "(sin cuerpo)"


def _looks_like_quota(status_code: int, detail: str) -> bool:
    text = detail.lower()
    return (
        status_code in (402, 429)
        or "resource_exhausted" in text
        or "quota" in text
        or "credit" in text
        or "billing" in text
        or "insufficient" in text
    )


def is_local_ollama(base_url: str) -> bool:
    """Ollama local no necesita OLLAMA_API_KEY, el de la nube sí."""
    host = base_url.lower()
    return any(
        name in host for name in ("localhost", "127.0.0.1", "0.0.0.0", "[::1]")
    )


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
            logger.error(
                "GEMINI_API_KEY no está configurada: el chat y la extracción de "
                "facturas no pueden usar Gemini."
            )
            raise AIUnavailableError()
        started = time.perf_counter()
        try:
            async with httpx.AsyncClient(timeout=self._timeout, transport=self._transport) as client:
                response = await _post_with_retry(
                    client,
                    GEMINI_URL.format(model=self._model),
                    provider="Gemini",
                    json=to_gemini_request(messages, tools),
                    headers={"x-goog-api-key": self._api_key},
                )
        except httpx.HTTPError as exc:
            logger.exception(
                "No se pudo conectar con Gemini (modelo=%s): %s",
                self._model,
                exc,
            )
            raise AIUnavailableError() from exc
        if response.status_code >= 400:
            detail = _error_detail(response)
            logger.error(
                "Gemini respondió HTTP %s (modelo=%s): %s",
                response.status_code,
                self._model,
                detail,
            )
            if _looks_like_quota(response.status_code, detail):
                logger.error(
                    "Gemini sin créditos/cuota o límite de peticiones alcanzado. "
                    "Revisa el plan, la facturación y los límites de tu API key."
                )
            elif response.status_code in (401, 403):
                logger.error(
                    "Revisa GEMINI_API_KEY: la clave no es válida o no tiene permisos."
                )
            raise AIUnavailableError()
        try:
            data = response.json()
        except ValueError as exc:
            logger.error(
                "Gemini devolvió una respuesta que no es JSON: %s",
                response.text[:500],
            )
            raise AIUnavailableError() from exc
        try:
            result = parse_gemini_response(data)
        except ProcessingError as exc:
            logger.error("Gemini no generó una respuesta utilizable: %s", exc)
            raise
        logger.info(
            "Gemini respondió en %.1fs (modelo=%s, tools=%d): %d llamadas a herramientas.",
            time.perf_counter() - started,
            self._model,
            len(tools),
            len(result.tool_calls),
        )
        return result


def to_ollama_request(
    model: str,
    messages: list[Message],
    tools: list[ToolSpec],
    *,
    num_ctx: int | None = None,
    think: bool | None = None,
    keep_alive: str | None = None,
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
    options: dict[str, Any] = {"temperature": 0.2}
    if num_ctx:
        options["num_ctx"] = num_ctx
    body: dict[str, Any] = {
        "model": model,
        "messages": converted,
        "stream": False,
        "options": options,
    }
    if think is not None:
        body["think"] = think
    if keep_alive:
        body["keep_alive"] = keep_alive
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
        *,
        num_ctx: int | None = None,
        think: bool | None = None,
        keep_alive: str | None = None,
    ):
        self._api_key = api_key
        self._base_url = base_url.rstrip("/")
        self._model = model
        self._timeout = timeout
        self._transport = transport
        self._num_ctx = num_ctx
        self._think = think
        self._keep_alive = keep_alive

    async def chat(self, messages: list[Message], tools: list[ToolSpec]) -> LLMResponse:
        local = is_local_ollama(self._base_url)
        headers = {"Authorization": f"Bearer {self._api_key}"} if self._api_key else {}
        payload = to_ollama_request(
            self._model,
            messages,
            tools,
            # Los modelos en la nube gestionan su propio contexto/tiempo de vida.
            num_ctx=self._num_ctx if local else None,
            think=self._think,
            keep_alive=self._keep_alive if local else None,
        )
        started = time.perf_counter()
        try:
            async with httpx.AsyncClient(timeout=self._timeout, transport=self._transport) as client:
                response = await _post_with_retry(
                    client,
                    f"{self._base_url}{OLLAMA_CHAT_PATH}",
                    provider="Ollama",
                    json=payload,
                    headers=headers,
                )
        except httpx.HTTPError as exc:
            logger.exception(
                "No se pudo conectar con Ollama (%s, modelo=%s): %s",
                self._base_url,
                self._model,
                exc,
            )
            raise AIUnavailableError() from exc
        elapsed = time.perf_counter() - started
        if response.status_code >= 400:
            detail = _error_detail(response)
            logger.error(
                "Ollama respondió HTTP %s (%s, modelo=%s): %s",
                response.status_code,
                self._base_url,
                self._model,
                detail,
            )
            if _looks_like_quota(response.status_code, detail):
                logger.error(
                    "Ollama sin créditos/cuota o límite de peticiones alcanzado. "
                    "Revisa tu plan de Ollama Cloud."
                )
            elif response.status_code in (401, 403):
                logger.error(
                    "Revisa OLLAMA_API_KEY: la clave no es válida o no tiene permisos."
                )
            raise AIUnavailableError()
        try:
            data = response.json()
        except ValueError as exc:
            logger.error(
                "Ollama devolvió una respuesta que no es JSON: %s",
                response.text[:500],
            )
            raise AIUnavailableError() from exc
        try:
            result = parse_ollama_response(data)
        except ProcessingError as exc:
            logger.error("Ollama no generó una respuesta utilizable: %s", exc)
            raise
        logger.info(
            "Ollama respondió en %.1fs (%s, modelo=%s, num_ctx=%s, tools=%d): "
            "%d llamadas a herramientas.",
            elapsed,
            self._base_url,
            self._model,
            self._num_ctx if local else "auto",
            len(tools),
            len(result.tool_calls),
        )
        return result


def to_openai_request(
    model: str,
    messages: list[Message],
    tools: list[ToolSpec],
    *,
    max_tokens: int = 2048,
    disable_reasoning: bool = False,
) -> dict[str, Any]:
    """Traduce al formato de chat completions compatible con OpenAI."""
    converted: list[dict[str, Any]] = []
    for message in messages:
        if message.role == "tool":
            converted.append(
                {
                    "role": "tool",
                    "tool_call_id": message.tool_call_id or message.name or "",
                    "content": message.content,
                }
            )
            continue
        item: dict[str, Any] = {"role": message.role}
        if message.role == "user" and message.images:
            parts: list[dict[str, Any]] = []
            if message.content:
                parts.append({"type": "text", "text": message.content})
            for image in message.images:
                encoded = base64.b64encode(image.data).decode("ascii")
                parts.append(
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:{image.mime_type};base64,{encoded}"
                        },
                    }
                )
            item["content"] = parts
        else:
            item["content"] = message.content or None
        if message.role == "assistant" and message.tool_calls:
            item["tool_calls"] = [
                {
                    "id": call.id,
                    "type": "function",
                    "function": {
                        "name": call.name,
                        "arguments": json.dumps(call.arguments, ensure_ascii=False),
                    },
                }
                for call in message.tool_calls
            ]
        converted.append(item)
    body: dict[str, Any] = {
        "model": model,
        "messages": converted,
        "temperature": 0.2,
        "max_tokens": max_tokens,
    }
    if disable_reasoning:
        # OpenRouter: evita que el modelo gaste tokens "pensando" antes de responder.
        body["reasoning"] = {"enabled": False}
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
        body["tool_choice"] = "auto"
    return body


def parse_openai_response(data: dict[str, Any]) -> LLMResponse:
    choices = data.get("choices") or []
    if not choices:
        raise ProcessingError("La IA no pudo generar una respuesta.")
    message = choices[0].get("message") or {}
    calls: list[ToolCall] = []
    for raw in message.get("tool_calls") or []:
        function = raw.get("function") or {}
        name = function.get("name")
        if not name:
            continue
        arguments = function.get("arguments") or {}
        if isinstance(arguments, str):
            try:
                arguments = json.loads(arguments)
            except json.JSONDecodeError:
                arguments = {}
        calls.append(
            ToolCall(
                id=raw.get("id") or uuid.uuid4().hex,
                name=name,
                arguments=arguments,
            )
        )
    text = (message.get("content") or "").strip() or None
    if text is None and not calls:
        raise ProcessingError("La IA no pudo generar una respuesta.")
    return LLMResponse(text=text, tool_calls=tuple(calls))


class OpenAICompatClient:
    """Cliente para proveedores con API compatible con OpenAI (OpenRouter, Groq).

    Se usa como respaldo de Qwen cuando Gemini agota su cuota.
    """

    def __init__(
        self,
        api_key: str,
        base_url: str,
        model: str,
        timeout: float,
        transport: httpx.AsyncBaseTransport | None = None,
        provider: str = "Qwen",
    ):
        self._api_key = api_key
        self._base_url = base_url.rstrip("/")
        self._model = model
        self._timeout = timeout
        self._transport = transport
        self._provider = provider

    async def chat(self, messages: list[Message], tools: list[ToolSpec]) -> LLMResponse:
        if not self._api_key:
            logger.error(
                "%s no está configurado: falta QWEN_API_KEY.", self._provider
            )
            raise AIUnavailableError()
        started = time.perf_counter()
        try:
            async with httpx.AsyncClient(timeout=self._timeout, transport=self._transport) as client:
                response = await _post_with_retry(
                    client,
                    f"{self._base_url}{OPENAI_CHAT_PATH}",
                    provider=self._provider,
                    json=to_openai_request(
                        self._model,
                        messages,
                        tools,
                        disable_reasoning="openrouter.ai" in self._base_url,
                    ),
                    headers={
                        "Authorization": f"Bearer {self._api_key}",
                        "Content-Type": "application/json",
                    },
                )
        except httpx.HTTPError as exc:
            logger.exception(
                "No se pudo conectar con %s (%s, modelo=%s): %s",
                self._provider,
                self._base_url,
                self._model,
                exc,
            )
            raise AIUnavailableError() from exc
        elapsed = time.perf_counter() - started
        if response.status_code >= 400:
            detail = _error_detail(response)
            logger.error(
                "%s respondió HTTP %s (%s, modelo=%s): %s",
                self._provider,
                response.status_code,
                self._base_url,
                self._model,
                detail,
            )
            if _looks_like_quota(response.status_code, detail):
                logger.error(
                    "%s sin créditos/cuota o límite de peticiones alcanzado. "
                    "Revisa el saldo en tu proveedor.",
                    self._provider,
                )
            elif response.status_code in (401, 403):
                logger.error(
                    "Revisa QWEN_API_KEY: la clave no es válida o no tiene permisos."
                )
            raise AIUnavailableError()
        try:
            data = response.json()
        except ValueError as exc:
            logger.error(
                "%s devolvió una respuesta que no es JSON: %s",
                self._provider,
                response.text[:500],
            )
            raise AIUnavailableError() from exc
        try:
            result = parse_openai_response(data)
        except ProcessingError as exc:
            logger.error("%s no generó una respuesta utilizable: %s", self._provider, exc)
            raise
        logger.info(
            "%s respondió en %.1fs (%s, modelo=%s, tools=%d): "
            "%d llamadas a herramientas.",
            self._provider,
            elapsed,
            self._base_url,
            self._model,
            len(tools),
            len(result.tool_calls),
        )
        return result


def _ollama_available() -> bool:
    """Ollama local no lleva clave; el de la nube sí la exige."""
    return bool(settings.ollama_api_key) or is_local_ollama(settings.ollama_base_url)


def _qwen_available() -> bool:
    return bool(settings.qwen_api_key)


async def chat(messages: list[Message], tools: list[ToolSpec]) -> LLMResponse:
    started = time.perf_counter()
    errors: list[Exception] = []

    gemini = GeminiClient(
        settings.gemini_api_key, settings.gemini_model, settings.llm_timeout_seconds
    )
    try:
        response = await gemini.chat(messages, tools)
        logger.info(
            "Proveedor de IA: Gemini (%.1fs en total).",
            time.perf_counter() - started,
        )
        return response
    except (AIUnavailableError, ProcessingError) as exc:
        errors.append(exc)
        logger.warning("Gemini no respondió (%s); buscando respaldo.", type(exc).__name__)

    if _qwen_available():
        logger.warning(
            "Probando respaldo Qwen (%s, modelo=%s, timeout=%.0fs).",
            settings.qwen_base_url,
            settings.qwen_model,
            settings.qwen_timeout_seconds,
        )
        qwen = OpenAICompatClient(
            settings.qwen_api_key,
            settings.qwen_base_url,
            settings.qwen_model,
            settings.qwen_timeout_seconds,
            provider="Qwen",
        )
        qwen_started = time.perf_counter()
        try:
            response = await qwen.chat(messages, tools)
            logger.warning(
                "Proveedor de IA: Qwen respondió en %.1fs (%.1fs en total).",
                time.perf_counter() - qwen_started,
                time.perf_counter() - started,
            )
            return response
        except (AIUnavailableError, ProcessingError) as exc:
            errors.append(exc)
            logger.error(
                "Qwen también falló (%s) tras %.1fs.",
                type(exc).__name__,
                time.perf_counter() - qwen_started,
            )
    else:
        logger.warning(
            "QWEN_API_KEY no está configurada: no hay respaldo Qwen. "
            "Crea una clave en https://openrouter.ai/settings/keys."
        )

    if _ollama_available():
        logger.warning(
            "Probando último respaldo Ollama (%s, modelo=%s, num_ctx=%s, timeout=%.0fs).",
            settings.ollama_base_url,
            settings.ollama_model,
            settings.ollama_num_ctx,
            settings.ollama_timeout_seconds,
        )
        ollama = OllamaClient(
            settings.ollama_api_key,
            settings.ollama_base_url,
            settings.ollama_model,
            settings.ollama_timeout_seconds,
            num_ctx=settings.ollama_num_ctx,
            think=settings.ollama_think,
            keep_alive=settings.ollama_keep_alive,
        )
        ollama_started = time.perf_counter()
        try:
            response = await ollama.chat(messages, tools)
            logger.warning(
                "Proveedor de IA: Ollama respondió en %.1fs (%.1fs en total).",
                time.perf_counter() - ollama_started,
                time.perf_counter() - started,
            )
            return response
        except (AIUnavailableError, ProcessingError) as exc:
            errors.append(exc)
            logger.error(
                "Ollama también falló (%s) tras %.1fs.",
                type(exc).__name__,
                time.perf_counter() - ollama_started,
            )

    logger.error(
        "No hay proveedor de IA disponible tras %.1fs. Errores: %s.",
        time.perf_counter() - started,
        " → ".join(type(error).__name__ for error in errors) or "ninguno",
    )
    raise errors[-1]

