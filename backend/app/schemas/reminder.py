import uuid
from datetime import date, datetime, time
from enum import StrEnum
from typing import Annotated, Self

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, field_validator, model_validator

from app.models.reminder import ReminderStatus

Concept = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=255)]

INTERVAL_LIMITS = {"days": 365, "weeks": 52, "months": 24}


class Frequency(StrEnum):
    ONCE = "once"
    DAILY = "daily"
    WEEKLY = "weekly"
    BIWEEKLY = "biweekly"
    MONTHLY = "monthly"
    CUSTOM = "custom"


class IntervalUnit(StrEnum):
    DAYS = "days"
    WEEKS = "weeks"
    MONTHS = "months"


class Weekday(StrEnum):
    MONDAY = "monday"
    TUESDAY = "tuesday"
    WEDNESDAY = "wednesday"
    THURSDAY = "thursday"
    FRIDAY = "friday"
    SATURDAY = "saturday"
    SUNDAY = "sunday"

    @property
    def index(self) -> int:
        return list(Weekday).index(self)


def _check_month_days(values: list[int]) -> list[int]:
    for value in values:
        if value != -1 and not 1 <= value <= 31:
            raise ValueError("Los días del mes deben estar entre 1 y 31, o -1 para el último día.")
    return sorted(set(values), key=lambda day: (day == -1, day))


class ReminderCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    concept: Concept
    remind_on: date
    remind_at: time
    frequency: Frequency = Frequency.ONCE
    interval_count: int | None = Field(default=None, ge=1)
    interval_unit: IntervalUnit | None = None
    month_days: list[int] = Field(default_factory=list, max_length=31)
    weekdays: list[Weekday] = Field(default_factory=list, max_length=7)

    @field_validator("remind_at")
    @classmethod
    def normalize_time(cls, value: time) -> time:
        return value.replace(second=0, microsecond=0, tzinfo=None)

    @field_validator("month_days")
    @classmethod
    def validate_month_days(cls, value: list[int]) -> list[int]:
        return _check_month_days(value)

    @field_validator("weekdays")
    @classmethod
    def dedupe_weekdays(cls, value: list[Weekday]) -> list[Weekday]:
        return sorted(set(value), key=lambda day: day.index)

    @model_validator(mode="after")
    def check_recurrence(self) -> Self:
        frequency = self.frequency
        has_interval = self.interval_count is not None or self.interval_unit is not None
        if frequency != Frequency.CUSTOM and has_interval:
            raise ValueError("Solo la frecuencia custom admite interval_count e interval_unit.")
        if frequency == Frequency.CUSTOM:
            if self.interval_count is None or self.interval_unit is None:
                raise ValueError("La frecuencia custom requiere interval_count e interval_unit.")
            limit = INTERVAL_LIMITS[self.interval_unit.value]
            if self.interval_count > limit:
                raise ValueError(
                    f"El intervalo máximo en {self.interval_unit.value} es {limit}."
                )
        allows_month_days = frequency == Frequency.MONTHLY or (
            frequency == Frequency.CUSTOM and self.interval_unit == IntervalUnit.MONTHS
        )
        allows_weekdays = frequency == Frequency.WEEKLY or (
            frequency == Frequency.CUSTOM and self.interval_unit == IntervalUnit.WEEKS
        )
        if self.month_days and not allows_month_days:
            raise ValueError("month_days solo aplica a frecuencia monthly o custom en meses.")
        if self.weekdays and not allows_weekdays:
            raise ValueError("weekdays solo aplica a frecuencia weekly o custom en semanas.")
        return self


class ReminderUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    concept: Concept | None = None
    remind_on: date | None = None
    remind_at: time | None = None
    frequency: Frequency | None = None
    interval_count: int | None = Field(default=None, ge=1)
    interval_unit: IntervalUnit | None = None
    month_days: list[int] | None = Field(default=None, max_length=31)
    weekdays: list[Weekday] | None = Field(default=None, max_length=7)

    @model_validator(mode="after")
    def check_changes(self) -> Self:
        for name in self.model_fields_set:
            if getattr(self, name) is None:
                raise ValueError(f"El campo {name} no puede ser nulo.")
        if not self.model_fields_set:
            raise ValueError("Indica al menos un campo para modificar.")
        return self


class ReminderRef(BaseModel):
    model_config = ConfigDict(extra="forbid")

    reminder_id: uuid.UUID


class ReminderListQuery(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ReminderRead(BaseModel):
    id: uuid.UUID
    concept: str
    status: ReminderStatus
    frequency: Frequency
    interval_count: int | None
    interval_unit: IntervalUnit | None
    month_days: list[int]
    weekdays: list[Weekday]
    remind_on: date
    remind_at: time
    timezone: str
    next_run_at: datetime | None
    next_run_local: datetime | None
    last_run_at: datetime | None
    created_at: datetime
