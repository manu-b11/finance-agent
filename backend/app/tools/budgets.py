import uuid
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.schemas.budget import BudgetRead, BudgetSet, BudgetStatusQuery, BudgetStatusRead
from app.services import budget as budget_service


async def set_budget(
    session: AsyncSession, user_id: uuid.UUID, raw_args: dict[str, Any]
) -> dict[str, Any]:
    args = BudgetSet.model_validate(raw_args)
    budget = await budget_service.set_budget(session, user_id, args)
    return BudgetRead.model_validate(budget).model_dump(mode="json")


async def get_budget_status(
    session: AsyncSession, user_id: uuid.UUID, raw_args: dict[str, Any]
) -> dict[str, Any]:
    args = BudgetStatusQuery.model_validate(raw_args)
    status: BudgetStatusRead = await budget_service.get_budget_status(session, user_id, args)
    return status.model_dump(mode="json")
