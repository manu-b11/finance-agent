import uuid
from datetime import datetime

from sqlalchemy import DateTime, String, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    timezone: Mapped[str] = mapped_column(String(64), default="America/Bogota")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
