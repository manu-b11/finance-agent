import uuid
from decimal import ROUND_HALF_UP, Decimal

from fastapi.concurrency import run_in_threadpool
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.categories import CATEGORY_LABELS, UNCATEGORIZED
from app.core.clock import local_today, month_bounds
from app.core.errors import NotFoundError
from app.models.transaction import Transaction, TransactionType
from app.schemas.report import (
    CategoryTotal,
    ExpenseBreakdownRead,
    MonthlyReportQuery,
    MonthlyReportRead,
)
from app.schemas.transaction import PeriodQuery, TransactionFilters, TransactionRead
from app.services import auth as auth_service
from app.services import report_pdf
from app.services import transaction as transaction_service

CENTS = Decimal("0.01")
REPORT_EXPENSES_LIMIT = 100


def _period_conditions(user_id: uuid.UUID, period: PeriodQuery) -> list:
    conditions = [Transaction.user_id == user_id]
    if period.start_date:
        conditions.append(Transaction.occurred_on >= period.start_date)
    if period.end_date:
        conditions.append(Transaction.occurred_on <= period.end_date)
    return conditions


async def _category_totals(
    session: AsyncSession, user_id: uuid.UUID, period: PeriodQuery
) -> tuple[Decimal, list[CategoryTotal]]:
    """Gastos del periodo agrupados por categoría, de mayor a menor (RF-35, RF-36)."""
    category = func.coalesce(Transaction.category, UNCATEGORIZED)
    total = func.sum(Transaction.amount)
    result = await session.execute(
        select(category, total)
        .where(
            *_period_conditions(user_id, period),
            Transaction.type == TransactionType.EXPENSE.value,
        )
        .group_by(category)
        .order_by(total.desc(), category)
    )
    rows = [(name, Decimal(amount).quantize(CENTS)) for name, amount in result.all()]
    grand_total = sum((amount for _, amount in rows), Decimal("0")).quantize(CENTS)
    categories = [
        CategoryTotal(
            category=name,
            label=CATEGORY_LABELS.get(name, name.capitalize()),
            total=amount,
            percentage=(amount / grand_total * 100).quantize(CENTS, rounding=ROUND_HALF_UP),
        )
        for name, amount in rows
    ]
    return grand_total, categories


async def get_expense_breakdown(
    session: AsyncSession, user_id: uuid.UUID, period: PeriodQuery
) -> ExpenseBreakdownRead:
    grand_total, categories = await _category_totals(session, user_id, period)
    return ExpenseBreakdownRead(
        start_date=period.start_date,
        end_date=period.end_date,
        total_expenses=grand_total,
        categories=categories,
        top_category=categories[0].category if categories else None,
    )


async def _month_expenses(
    session: AsyncSession, user_id: uuid.UUID, period: PeriodQuery
) -> tuple[list[TransactionRead], int]:
    """Gastos individuales del periodo (los más recientes primero) y su total."""
    filters = TransactionFilters(
        start_date=period.start_date,
        end_date=period.end_date,
        type=TransactionType.EXPENSE,
        limit=REPORT_EXPENSES_LIMIT,
    )
    rows = await transaction_service.list_transactions(session, user_id, filters)
    expenses = [TransactionRead.model_validate(row) for row in rows]
    count = (
        await session.execute(
            select(func.count())
            .select_from(Transaction)
            .where(
                *_period_conditions(user_id, period),
                Transaction.type == TransactionType.EXPENSE.value,
            )
        )
    ).scalar_one()
    return expenses, count


async def get_monthly_report(
    session: AsyncSession,
    user_id: uuid.UUID,
    query: MonthlyReportQuery,
    *,
    include_expenses: bool = False,
) -> MonthlyReportRead:
    """Ingresos, gastos, balance y distribución por categoría de un mes (RF-37)."""
    user = await auth_service.get_user_by_id(session, user_id)
    if user is None:
        raise NotFoundError("No se encontró el usuario.")
    today = local_today(user.timezone)
    if query.month:
        year, month = (int(part) for part in query.month.split("-"))
    else:
        year, month = today.year, today.month
    start, end = month_bounds(year, month)
    period = PeriodQuery(start_date=start, end_date=end)
    balance = await transaction_service.get_balance(session, user_id, period)
    _, categories = await _category_totals(session, user_id, period)
    count = (
        await session.execute(
            select(func.count()).select_from(Transaction).where(*_period_conditions(user_id, period))
        )
    ).scalar_one()
    expenses: list[TransactionRead] = []
    expense_count = 0
    if include_expenses:
        expenses, expense_count = await _month_expenses(session, user_id, period)
    return MonthlyReportRead(
        month=f"{year:04d}-{month:02d}",
        start_date=start,
        end_date=end,
        total_income=balance.total_income,
        total_expenses=balance.total_expenses,
        balance=balance.balance,
        transaction_count=count,
        categories=categories,
        top_category=categories[0].category if categories else None,
        generated_on=today,
        expenses=expenses,
        expense_count=expense_count,
    )


async def generate_monthly_pdf(
    session: AsyncSession, user_id: uuid.UUID, query: MonthlyReportQuery
) -> tuple[MonthlyReportRead, bytes]:
    """Genera el PDF solo con datos reales de la base (RF-39, RF-40)."""
    report = await get_monthly_report(
        session, user_id, query, include_expenses=True
    )
    content = await run_in_threadpool(report_pdf.render_monthly_report, report)
    return report, content
