import uuid
from datetime import datetime
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, field_validator

Key = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=255)]


class PushKeys(BaseModel):
    model_config = ConfigDict(extra="forbid")

    p256dh: Key
    auth: Key


class PushSubscriptionCreate(BaseModel):
    model_config = ConfigDict(extra="ignore")

    endpoint: str = Field(min_length=10, max_length=2048)
    keys: PushKeys

    @field_validator("endpoint")
    @classmethod
    def validate_endpoint(cls, value: str) -> str:
        if not value.startswith("https://"):
            raise ValueError("El endpoint de la suscripción debe usar https.")
        return value


class PushUnsubscribe(BaseModel):
    model_config = ConfigDict(extra="forbid")

    endpoint: str = Field(min_length=10, max_length=2048)


class PushSubscriptionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    endpoint: str
    created_at: datetime


class PushPublicKey(BaseModel):
    public_key: str


class PushTestResult(BaseModel):
    delivered: int
    failed: int
    gone: int
