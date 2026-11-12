import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Annotated, Self

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator

GoalName = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=120)]


class GoalCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: GoalName
    target_amount: Decimal = Field(gt=0, max_digits=14, decimal_places=2)
    deadline: date | None = None


class GoalListQuery(BaseModel):
    model_config = ConfigDict(extra="forbid")


class GoalRef(BaseModel):
    model_config = ConfigDict(extra="forbid")

    goal_id: uuid.UUID


class GoalUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: GoalName | None = None
    target_amount: Decimal | None = Field(default=None, gt=0, max_digits=14, decimal_places=2)
    deadline: date | None = None

    @model_validator(mode="after")
    def check_changes(self) -> Self:
        for name in ("name", "target_amount"):
            if name in self.model_fields_set and getattr(self, name) is None:
                raise ValueError(f"El campo {name} no puede ser nulo.")
        if not self.model_fields_set:
            raise ValueError("Indica al menos un campo para modificar.")
        return self


class ContributionCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    goal_id: uuid.UUID
    amount: Decimal = Field(gt=0, max_digits=14, decimal_places=2)
    contributed_on: date | None = None


class ContributionBody(BaseModel):
    """Aporte enviado desde la página de metas; la meta va en la ruta."""

    model_config = ConfigDict(extra="forbid")

    amount: Decimal = Field(gt=0, max_digits=14, decimal_places=2)
    contributed_on: date | None = None


class GoalRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    target_amount: Decimal
    deadline: date | None
    created_at: datetime


class ContributionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    goal_id: uuid.UUID
    amount: Decimal
    contributed_on: date
    created_at: datetime


class GoalProgressRead(BaseModel):
    id: uuid.UUID
    name: str
    target_amount: Decimal
    deadline: date | None
    accumulated: Decimal
    remaining: Decimal
    percentage: Decimal
    completed: bool
    days_remaining: int | None
    suggested_monthly_contribution: Decimal | None
