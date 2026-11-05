import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Annotated, Self

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator

from app.models.transaction import ExpenseCategory, TransactionType

Concept = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=255)]


class TransactionCreate(BaseModel):
    """Datos para registrar un movimiento. Sin `user_id`: siempre sale del token."""

    model_config = ConfigDict(extra="forbid")

    type: TransactionType
    amount: Decimal = Field(gt=0, max_digits=14, decimal_places=2)
    concept: Concept
    occurred_on: date
    category: ExpenseCategory | None = None

    @model_validator(mode="after")
    def check_category(self) -> Self:
        if self.type == TransactionType.EXPENSE and self.category is None:
            raise ValueError("Los gastos requieren una categoría.")
        if self.type == TransactionType.INCOME:
            self.category = None
        return self


class TransactionRef(BaseModel):
    model_config = ConfigDict(extra="forbid")

    transaction_id: uuid.UUID


class TransactionUpdate(BaseModel):
    """Cambios parciales (RF-14). Solo se aplican los campos enviados."""

    model_config = ConfigDict(extra="forbid")

    type: TransactionType | None = None
    amount: Decimal | None = Field(default=None, gt=0, max_digits=14, decimal_places=2)
    concept: Concept | None = None
    occurred_on: date | None = None
    category: ExpenseCategory | None = None

    @model_validator(mode="after")
    def check_changes(self) -> Self:
        for name in ("type", "amount", "concept", "occurred_on"):
            if name in self.model_fields_set and getattr(self, name) is None:
                raise ValueError(f"El campo {name} no puede ser nulo.")
        if not self.model_fields_set:
            raise ValueError("Indica al menos un campo para modificar.")
        return self


class PeriodQuery(BaseModel):
    model_config = ConfigDict(extra="forbid")

    start_date: date | None = None
    end_date: date | None = None

    @model_validator(mode="after")
    def check_period(self) -> Self:
        if self.start_date and self.end_date and self.start_date > self.end_date:
            raise ValueError("La fecha inicial no puede ser posterior a la final.")
        return self


class TransactionFilters(PeriodQuery):
    type: TransactionType | None = None
    category: ExpenseCategory | None = None
    limit: int = Field(default=20, ge=1, le=100)


class TransactionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    type: TransactionType
    amount: Decimal
    concept: str
    category: ExpenseCategory | None
    occurred_on: date
    created_at: datetime


class BalanceRead(BaseModel):
    total_income: Decimal
    total_expenses: Decimal
    balance: Decimal
    start_date: date | None = None
    end_date: date | None = None