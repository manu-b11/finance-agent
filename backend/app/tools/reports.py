import uuid
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.schemas.report import MonthlyReportQuery
from app.schemas.transaction import PeriodQuery
from app.services import report as report_service


def pdf_path(month: str) -> str:
    return f"/reports/monthly/{month}/pdf"


async def get_expenses_by_category(
    session: AsyncSession, user_id: uuid.UUID, raw_args: dict[str, Any]
) -> dict[str, Any]:
    period = PeriodQuery.model_validate(raw_args)
    breakdown = await report_service.get_expense_breakdown(session, user_id, period)
    return breakdown.model_dump(mode="json")


async def get_monthly_report(
    session: AsyncSession, user_id: uuid.UUID, raw_args: dict[str, Any]
) -> dict[str, Any]:
    query = MonthlyReportQuery.model_validate(raw_args)
    report = await report_service.get_monthly_report(session, user_id, query)
    return {**report.model_dump(mode="json"), "pdf_url": pdf_path(report.month)}
