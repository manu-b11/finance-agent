from datetime import date
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field


class MonthlyReportQuery(BaseModel):
    model_config = ConfigDict(extra="forbid")

    month: str | None = Field(default=None, pattern=r"^\d{4}-(0[1-9]|1[0-2])$")


class CategoryTotal(BaseModel):
    category: str
    label: str
    total: Decimal
    percentage: Decimal


class ExpenseBreakdownRead(BaseModel):
    start_date: date | None
    end_date: date | None
    total_expenses: Decimal
    categories: list[CategoryTotal]
    top_category: str | None


class MonthlyReportRead(BaseModel):
    month: str
    start_date: date
    end_date: date
    total_income: Decimal
    total_expenses: Decimal
    balance: Decimal
    transaction_count: int
    categories: list[CategoryTotal]
    top_category: str | None
    generated_on: date
