import uuid
from datetime import datetime
from typing import Annotated, Any, Literal
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, field_validator

ChatText = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=2000)]
CardType = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=1, max_length=40)
]
ConversationTitle = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=1, max_length=120)
]
DEMO_HISTORY_TURNS = 8
MAX_CARDS = 20


class ChatCard(BaseModel):
    """Tarjeta del chat. `data` solo lleva referencias (ids), no datos completos."""

    model_config = ConfigDict(extra="forbid")

    type: CardType
    data: dict[str, Any] = Field(default_factory=dict)



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
    cards: list[ChatCard] = Field(default_factory=list, max_length=MAX_CARDS)


class ConversationCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: ConversationTitle | None = None


class ChatMessageRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    conversation_id: uuid.UUID
    role: Literal["user", "assistant"]
    content: str
    cards: list[ChatCard] = Field(default_factory=list)
    created_at: datetime

    @field_validator("cards", mode="before")
    @classmethod
    def _empty_cards_when_null(cls, value: Any) -> list[Any]:
        # Los mensajes anteriores a esta columna tienen cards = NULL.
        return value or []


class ConversationRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    title: str
    created_at: datetime
    updated_at: datetime
