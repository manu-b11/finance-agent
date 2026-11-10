import json
import uuid
from collections.abc import AsyncIterator
from dataclasses import dataclass
from typing import Any

from pydantic import ValidationError
from sqlalchemy.ext.asyncio import AsyncSession

from app.agent.llm_client import ChatFn, Message, ToolCall
from app.core.errors import AppError, ProcessingError
from app.tools import registry

MAX_ITERATIONS = 6


@dataclass(frozen=True)
class AgentEvent:
    type: str
    data: dict[str, Any]


async def _run_tool(session: AsyncSession, user_id: uuid.UUID, call: ToolCall) -> dict[str, Any]:
    tool = registry.get_tool(call.name)
    if tool is None:
        return {"error": "unknown_tool", "message": f"La herramienta {call.name} no existe."}
    try:
        return await tool.handler(session, user_id, dict(call.arguments))
    except ValidationError as exc:
        await session.rollback()
        details = [
            {"field": ".".join(str(part) for part in error["loc"]), "message": error["msg"]}
            for error in exc.errors()
        ]
        return {"error": "invalid_arguments", "details": details}
    except AppError as exc:
        await session.rollback()
        return {"error": exc.code, "message": exc.message}


async def run(
    chat: ChatFn,
    session: AsyncSession,
    user_id: uuid.UUID,
    messages: list[Message],
) -> AsyncIterator[AgentEvent]:
    conversation = list(messages)
    specs = registry.get_tool_specs()
    for _ in range(MAX_ITERATIONS):
        response = await chat(conversation, specs)
        if not response.tool_calls:
            if not response.text:
                raise ProcessingError("La IA no pudo generar una respuesta.")
            yield AgentEvent("message", {"text": response.text})
            return
        conversation.append(
            Message(role="assistant", content=response.text or "", tool_calls=response.tool_calls)
        )
        for call in response.tool_calls:
            yield AgentEvent("tool_call", {"name": call.name})
            result = await _run_tool(session, user_id, call)
            conversation.append(
                Message(
                    role="tool",
                    content=json.dumps(result, ensure_ascii=False),
                    tool_call_id=call.id,
                    name=call.name,
                )
            )
    raise ProcessingError("No pude completar la solicitud. Intenta reformularla.")
