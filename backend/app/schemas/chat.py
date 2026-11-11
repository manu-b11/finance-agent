import uuid
from datetime import datetime
from typing import Annotated, Literal
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, field_validator

ChatText = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=2000)]
ConversationTitle = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=1, max_length=120)
]
DEMO_HISTORY_TURNS = 8


class ChatRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    message: ChatText
    conversation_id: uuid.UUID | None = None


class DemoTurn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    role: Literal["user", "assistant"]
    content: ChatText


class DemoChatRequest(BaseModel):
    """Chat de demostración para visitantes sin cuenta (sin herramientas)."""

    model_config = ConfigDict(extra="forbid")

    message: ChatText
    history: list[DemoTurn] = Field(default_factory=list, max_length=DEMO_HISTORY_TURNS)
    timezone: str = "America/Bogota"

    @field_validator("timezone")
    @classmethod
    def validate_timezone(cls, value: str) -> str:
        try:
            ZoneInfo(value)
        except (ZoneInfoNotFoundError, ValueError) as exc:
            raise ValueError("Zona horaria no válida.") from exc
        return value


class ExchangeCreate(BaseModel):
    """Intercambio ya resuelto en el cliente (p. ej. una factura revisada)."""

    model_config = ConfigDict(extra="forbid")

    user_text: ChatText
    assistant_text: ChatText


class ConversationCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: ConversationTitle | None = None


class ChatMessageRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    conversation_id: uuid.UUID
    role: Literal["user", "assistant"]
    content: str
    created_at: datetime


class ConversationRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    title: str
    created_at: datetime
    updated_at: datetime
