import uuid
from datetime import datetime
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator


class UserCreate(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    timezone: str = "America/Bogota"

    @field_validator("timezone")
    @classmethod
    def validate_timezone(cls, value: str) -> str:
        try:
            ZoneInfo(value)
        except (ZoneInfoNotFoundError, ValueError) as exc:
            raise ValueError("Zona horaria no válida.") from exc
        return value


class UserLogin(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=128)


class UserRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    email: EmailStr
    timezone: str
    created_at: datetime


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
