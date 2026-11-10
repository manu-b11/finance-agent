import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import NotFoundError
from app.schemas.budget import BudgetStatusQuery, BudgetStatusRead
from app.schemas.dashboard import DashboardRead
from app.schemas.report import MonthlyReportQuery
from app.schemas.transaction import TransactionFilters, TransactionRead
from app.services import budget as budget_service
from app.services import reminder as reminder_service
from app.services import report as report_service
from app.services import savings_goal as goal_service
from app.services import transaction as transaction_service

UPCOMING_REMINDERS_LIMIT = 5
RECENT_TRANSACTIONS_LIMIT = 5


async def _budget_or_none(
    session: AsyncSession, user_id: uuid.UUID, month: str
) -> BudgetStatusRead | None:
    try:
        return await budget_service.get_budget_status(
            session, user_id, BudgetStatusQuery(month=month)
        )
    except NotFoundError:
        return None


async def get_dashboard(
    session: AsyncSession, user_id: uuid.UUID, query: MonthlyReportQuery
) -> DashboardRead:
    summary = await report_service.get_monthly_report(session, user_id, query)
    budget = await _budget_or_none(session, user_id, summary.month)
    goals = await goal_service.list_goals(session, user_id)
    reminders = await reminder_service.list_reminders(session, user_id)
    recent = await transaction_service.list_transactions(
        session,
        user_id,
        TransactionFilters(
            start_date=summary.start_date,
            end_date=summary.end_date,
            limit=RECENT_TRANSACTIONS_LIMIT,
        ),
    )
    return DashboardRead(
        month=summary.month,
        summary=summary,
        budget=budget,
        goals=goals,
        upcoming_reminders=reminders[:UPCOMING_REMINDERS_LIMIT],
        recent_transactions=[TransactionRead.model_validate(item) for item in recent],
    )
