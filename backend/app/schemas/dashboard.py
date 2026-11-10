from pydantic import BaseModel

from app.schemas.budget import BudgetStatusRead
from app.schemas.reminder import ReminderRead
from app.schemas.report import MonthlyReportRead
from app.schemas.savings_goal import GoalProgressRead
from app.schemas.transaction import TransactionRead


class DashboardRead(BaseModel):
    month: str
    summary: MonthlyReportRead
    budget: BudgetStatusRead | None
    goals: list[GoalProgressRead]
    upcoming_reminders: list[ReminderRead]
    recent_transactions: list[TransactionRead]
