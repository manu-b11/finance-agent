import calendar
import uuid
from datetime import date
from decimal import ROUND_HALF_UP, Decimal

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.clock import local_today
from app.core.errors import NotFoundError
from app.models.budget import Budget
from app.models.transaction import Transaction, TransactionType
from app.schemas.budget import BudgetSet, BudgetStatusQuery, BudgetStatusRead
from app.services import auth as auth_service

CENTS = Decimal("0.01")


async def _get_budget(session: AsyncSession, user_id: uuid.UUID) -> Budget | None:
    result = await session.execute(select(Budget).where(Budget.user_id == user_id))
    return result.scalar_one_or_none()


async def set_budget(session: AsyncSession, user_id: uuid.UUID, data: BudgetSet) -> Budget:
    budget = await _get_budget(session, user_id)
    if budget is None:
        budget = Budget(user_id=user_id, amount=data.amount)
        session.add(budget)
    else:
        budget.amount = data.amount
    await session.commit()
    await session.refresh(budget)
    return budget


async def _resolve_month(
    session: AsyncSession, user_id: uuid.UUID, query: BudgetStatusQuery
) -> tuple[date, date]:
    if query.month:
        year, month = (int(part) for part in query.month.split("-"))
    else:
        user = await auth_service.get_user_by_id(session, user_id)
        if user is None:
            raise NotFoundError("No se encontró el usuario.")
        today = local_today(user.timezone)
        year, month = today.year, today.month
    last_day = calendar.monthrange(year, month)[1]
    return date(year, month, 1), date(year, month, last_day)


async def get_budget_status(
    session: AsyncSession, user_id: uuid.UUID, query: BudgetStatusQuery
) -> BudgetStatusRead:
    """Gasto del mes frente al presupuesto (RB-09). Los aportes a metas no cuentan (RB-11)."""
    budget = await _get_budget(session, user_id)
    if budget is None:
        raise NotFoundError("Aún no has definido un presupuesto mensual.")
    start, end = await _resolve_month(session, user_id, query)
    result = await session.execute(
        select(func.coalesce(func.sum(Transaction.amount), 0)).where(
            Transaction.user_id == user_id,
            Transaction.type == TransactionType.EXPENSE.value,
            Transaction.occurred_on >= start,
            Transaction.occurred_on <= end,
        )
    )
    spent = Decimal(result.scalar_one()).quantize(CENTS)
    amount = Decimal(budget.amount).quantize(CENTS)
    remaining = amount - spent
    percentage = (spent / amount * 100).quantize(CENTS, rounding=ROUND_HALF_UP)
    return BudgetStatusRead(
        month=start.strftime("%Y-%m"),
        budget=amount,
        spent=spent,
        remaining=remaining,
        percentage_used=percentage,
        over_budget=spent > amount,
    )
