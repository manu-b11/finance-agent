import uuid
from typing import Any

from app.agent.llm_client import LLMResponse, Message, ToolCall, ToolSpec


def tool_call(name: str, arguments: dict[str, Any]) -> ToolCall:
    return ToolCall(id=uuid.uuid4().hex, name=name, arguments=arguments)


def calls_response(*calls: ToolCall) -> LLMResponse:
    return LLMResponse(tool_calls=tuple(calls))


def text_response(text: str) -> LLMResponse:
    return LLMResponse(text=text)


class FakeChat:
    def __init__(self, *responses: LLMResponse, default: LLMResponse | None = None):
        self.responses = list(responses)
        self.default = default
        self.calls: list[tuple[list[Message], list[ToolSpec]]] = []

    async def __call__(self, messages: list[Message], tools: list[ToolSpec]) -> LLMResponse:
        self.calls.append((list(messages), list(tools)))
        if self.responses:
            return self.responses.pop(0)
        if self.default is not None:
            return self.default
        raise AssertionError("FakeChat se quedó sin respuestas.")
