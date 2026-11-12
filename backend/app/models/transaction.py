import uuid
from datetime import date, datetime
from decimal import Decimal
from enum import StrEnum

from sqlalchemy import CheckConstraint, Date, DateTime, ForeignKey, Index, Numeric, String, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class TransactionType(StrEnum):
    INCOME = "income"
    EXPENSE = "expense"


class ExpenseCategory(StrEnum):
    FOOD = "alimentacion"
    TRANSPORT = "transporte"
    HOUSING = "vivienda"
    UTILITIES = "servicios"
    HEALTH = "salud"
    EDUCATION = "educacion"
    ENTERTAINMENT = "entretenimiento"
    CLOTHING = "ropa"
    BEAUTY = "belleza"
    HOME = "hogar"
    PETS = "mascotas"
    GIFTS = "regalos"
    TRAVEL = "viajes"
    SUBSCRIPTIONS = "suscripciones"
    SPORTS = "deporte"
    TECHNOLOGY = "tecnologia"
    INSURANCE = "seguros"
    TAXES = "impuestos"
    OTHER = "otros"


class Transaction(Base):
    __tablename__ = "transactions"
    __table_args__ = (
        CheckConstraint("amount > 0", name="ck_transactions_amount_positive"),
        CheckConstraint("type IN ('income', 'expense')", name="ck_transactions_type"),
        Index("ix_transactions_user_id_occurred_on", "user_id", "occurred_on"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("users.id", ondelete="CASCADE"))
    type: Mapped[str] = mapped_column(String(10))
    amount: Mapped[Decimal] = mapped_column(Numeric(14, 2))
    concept: Mapped[str] = mapped_column(String(255))
    category: Mapped[str | None] = mapped_column(String(32), nullable=True)
    occurred_on: Mapped[date] = mapped_column(Date)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )