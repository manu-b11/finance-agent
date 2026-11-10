from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field


class BudgetSet(BaseModel):
    model_config = ConfigDict(extra="forbid")

    amount: Decimal = Field(gt=0, max_digits=14, decimal_places=2)


class BudgetStatusQuery(BaseModel):
    model_config = ConfigDict(extra="forbid")

    month: str | None = Field(default=None, pattern=r"^\d{4}-(0[1-9]|1[0-2])$")


class BudgetRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    amount: Decimal
    updated_at: datetime


class BudgetStatusRead(BaseModel):
    month: str
    budget: Decimal
    spent: Decimal
    remaining: Decimal
    percentage_used: Decimal
    over_budget: bool
