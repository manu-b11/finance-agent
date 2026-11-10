from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.database import get_session
from app.models.user import User
from app.schemas.dashboard import DashboardRead
from app.schemas.report import MonthlyReportQuery
from app.services import dashboard as dashboard_service

MONTH_PATTERN = r"^\d{4}-(0[1-9]|1[0-2])$"

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


@router.get("", response_model=DashboardRead)
async def dashboard(
    month: str | None = Query(default=None, pattern=MONTH_PATTERN),
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> DashboardRead:
    return await dashboard_service.get_dashboard(
        session, current_user.id, MonthlyReportQuery(month=month)
    )
