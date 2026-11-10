import uuid
from datetime import datetime
from enum import StrEnum

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, Integer, String, Uuid, func
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class ReminderStatus(StrEnum):
    ACTIVE = "active"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class Reminder(Base):
    __tablename__ = "reminders"
    __table_args__ = (
        CheckConstraint(
            "frequency IN ('once', 'daily', 'weekly', 'biweekly', 'monthly', 'custom')",
            name="ck_reminders_frequency",
        ),
        CheckConstraint(
            "status IN ('active', 'completed', 'cancelled')", name="ck_reminders_status"
        ),
        CheckConstraint(
            "interval_unit IS NULL OR interval_unit IN ('days', 'weeks', 'months')",
            name="ck_reminders_interval_unit",
        ),
        CheckConstraint(
            "interval_count IS NULL OR interval_count >= 1", name="ck_reminders_interval_count"
        ),
        Index("ix_reminders_status_next_run_at", "status", "next_run_at"),
        Index("ix_reminders_user_id_status", "user_id", "status"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("users.id", ondelete="CASCADE"))
    concept: Mapped[str] = mapped_column(String(255))
    timezone: Mapped[str] = mapped_column(String(64))
    start_local: Mapped[datetime] = mapped_column(DateTime(timezone=False))
    frequency: Mapped[str] = mapped_column(String(10), default="once")
    interval_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    interval_unit: Mapped[str | None] = mapped_column(String(10), nullable=True)
    month_days: Mapped[list[int]] = mapped_column(ARRAY(Integer), default=list)
    weekdays: Mapped[list[int]] = mapped_column(ARRAY(Integer), default=list)
    status: Mapped[str] = mapped_column(String(10), default=ReminderStatus.ACTIVE.value)
    next_run_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_run_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
