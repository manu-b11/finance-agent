from fastapi import APIRouter, Depends, Path, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.database import get_session
from app.models.user import User
from app.schemas.report import MonthlyReportQuery, MonthlyReportRead
from app.services import report as report_service

MONTH_PATTERN = r"^\d{4}-(0[1-9]|1[0-2])$"

router = APIRouter(prefix="/reports", tags=["reports"])


@router.get("/monthly/{month}", response_model=MonthlyReportRead)
async def monthly_report(
    month: str = Path(pattern=MONTH_PATTERN),
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> MonthlyReportRead:
    return await report_service.get_monthly_report(
        session, current_user.id, MonthlyReportQuery(month=month)
    )


@router.get("/monthly/{month}/pdf")
async def monthly_report_pdf(
    month: str = Path(pattern=MONTH_PATTERN),
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> Response:
    report, content = await report_service.generate_monthly_pdf(
        session, current_user.id, MonthlyReportQuery(month=month)
    )
    return Response(
        content=content,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'attachment; filename="informe-financiero-{report.month}.pdf"'
        },
    )
