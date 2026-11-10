import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Annotated, Literal, Self

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator

from app.models.invoice import InvoiceStatus
from app.models.transaction import ExpenseCategory

Merchant = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=255)]
InvoiceNumber = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=64)]
ItemDescription = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=1, max_length=255)
]

MAX_ITEMS = 200


class DraftItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    description: ItemDescription
    quantity: Decimal = Field(default=Decimal("1"), gt=0, max_digits=12, decimal_places=3)
    unit_price: Decimal = Field(ge=0, max_digits=14, decimal_places=2)


class InvoiceDraft(BaseModel):
    model_config = ConfigDict(extra="forbid")

    merchant: Merchant | None = None
    invoice_number: InvoiceNumber | None = None
    issued_on: date | None = None
    total: Decimal | None = Field(default=None, gt=0, max_digits=14, decimal_places=2)
    category: ExpenseCategory | None = None
    items: list[DraftItem] = Field(default_factory=list, max_length=MAX_ITEMS)


class InvoiceRef(BaseModel):
    model_config = ConfigDict(extra="forbid")

    invoice_id: uuid.UUID


class InvoiceListQuery(BaseModel):
    model_config = ConfigDict(extra="forbid")


class InvoiceConfirm(InvoiceRef):
    user_confirmed: Literal[True]


class InvoiceHeaderUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    merchant: Merchant | None = None
    invoice_number: InvoiceNumber | None = None
    issued_on: date | None = None
    total: Decimal | None = Field(default=None, gt=0, max_digits=14, decimal_places=2)
    category: ExpenseCategory | None = None

    @model_validator(mode="after")
    def check_changes(self) -> Self:
        for name in ("merchant", "issued_on", "total", "category"):
            if name in self.model_fields_set and getattr(self, name) is None:
                raise ValueError(f"El campo {name} no puede ser nulo.")
        if not self.model_fields_set:
            raise ValueError("Indica al menos un campo para modificar.")
        return self


class ItemPosition(BaseModel):
    model_config = ConfigDict(extra="forbid")

    invoice_id: uuid.UUID
    position: int = Field(ge=1)


class ItemUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    description: ItemDescription | None = None
    quantity: Decimal | None = Field(default=None, gt=0, max_digits=12, decimal_places=3)
    unit_price: Decimal | None = Field(default=None, ge=0, max_digits=14, decimal_places=2)

    @model_validator(mode="after")
    def check_changes(self) -> Self:
        for name in ("description", "quantity", "unit_price"):
            if name in self.model_fields_set and getattr(self, name) is None:
                raise ValueError(f"El campo {name} no puede ser nulo.")
        if not self.model_fields_set:
            raise ValueError("Indica al menos un campo para modificar.")
        return self


class InvoiceItemRead(BaseModel):
    position: int
    description: str
    quantity: Decimal
    unit_price: Decimal
    line_total: Decimal


class InvoiceRead(BaseModel):
    id: uuid.UUID
    status: InvoiceStatus
    original_filename: str | None
    merchant: str | None
    invoice_number: str | None
    issued_on: date | None
    total: Decimal | None
    category: ExpenseCategory | None
    items: list[InvoiceItemRead]
    items_total: Decimal
    total_matches_items: bool | None
    missing_fields: list[str]
    transaction_id: uuid.UUID | None
    created_at: datetime
    confirmed_at: datetime | None
