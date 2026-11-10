from datetime import date
from decimal import Decimal

import pytest

from app.core.clock import local_today
from app.models.transaction import Transaction
from app.schemas.report import MonthlyReportQuery
from app.schemas.transaction import PeriodQuery, TransactionCreate
from app.schemas.user import UserCreate
from app.services import auth as auth_service
from app.services import report as service
from app.services import transaction as transaction_service


async def make_user(session, email: str = "ana@example.com"):
    return await auth_service.register_user(
        session, UserCreate(email=email, password="clave-segura-1")
    )


async def add(session, user_id, type_, amount, day, category=None, concept="Movimiento"):
    await transaction_service.create_transaction(
        session,
        user_id,
        TransactionCreate(
            type=type_,
            amount=Decimal(amount),
            concept=concept,
            occurred_on=day,
            category=category,
        ),
    )


async def seed_november(session, user_id):
    await add(session, user_id, "income", "5000", "2026-11-01", concept="Salario")
    await add(session, user_id, "income", "500.50", "2026-11-20", concept="Extra")
    await add(session, user_id, "expense", "600", "2026-11-03", "alimentacion")
    await add(session, user_id, "expense", "200", "2026-11-10", "alimentacion")
    await add(session, user_id, "expense", "150.25", "2026-11-12", "transporte")
    await add(session, user_id, "expense", "49.75", "2026-11-30", "ropa")
    await add(session, user_id, "expense", "999", "2026-10-31", "salud")
    await add(session, user_id, "expense", "999", "2026-12-01", "salud")
    await add(session, user_id, "income", "777", "2026-12-01", concept="Fuera del mes")


async def test_breakdown_groups_sorts_and_computes_percentages(session):
    user = await make_user(session)
    await seed_november(session, user.id)
    period = PeriodQuery(start_date="2026-11-01", end_date="2026-11-30")
    breakdown = await service.get_expense_breakdown(session, user.id, period)
    assert breakdown.total_expenses == Decimal("1000.00")
    assert [c.category for c in breakdown.categories] == ["alimentacion", "transporte", "ropa"]
    assert [c.total for c in breakdown.categories] == [
        Decimal("800.00"),
        Decimal("150.25"),
        Decimal("49.75"),
    ]
    assert [c.percentage for c in breakdown.categories] == [
        Decimal("80.00"),
        Decimal("15.03"),
        Decimal("4.98"),
    ]
    assert breakdown.categories[0].label == "Alimentación"
    assert breakdown.top_category == "alimentacion"


async def test_breakdown_without_period_considers_all_expenses_and_ignores_income(session):
    user = await make_user(session)
    await seed_november(session, user.id)
    breakdown = await service.get_expense_breakdown(session, user.id, PeriodQuery())
    assert breakdown.total_expenses == Decimal("2998.00")
    assert breakdown.categories[0].category == "salud"
    assert breakdown.categories[0].total == Decimal("1998.00")


async def test_breakdown_without_expenses_is_empty(session):
    user = await make_user(session)
    await add(session, user.id, "income", "100", "2026-11-01")
    breakdown = await service.get_expense_breakdown(session, user.id, PeriodQuery())
    assert breakdown.total_expenses == Decimal("0.00")
    assert breakdown.categories == []
    assert breakdown.top_category is None


async def test_expense_without_category_is_reported_as_uncategorized(session):
    user = await make_user(session)
    user_id = user.id
    session.add(
        Transaction(
            user_id=user_id,
            type="expense",
            amount=Decimal("10"),
            concept="Viejo",
            category=None,
            occurred_on=date(2026, 11, 2),
        )
    )
    await session.commit()
    breakdown = await service.get_expense_breakdown(session, user_id, PeriodQuery())
    assert breakdown.categories[0].category == "sin_categoria"
    assert breakdown.categories[0].label == "Sin categoría"


async def test_monthly_report_totals_only_cover_the_month(session):
    user = await make_user(session)
    await seed_november(session, user.id)
    report = await service.get_monthly_report(
        session, user.id, MonthlyReportQuery(month="2026-11")
    )
    assert report.month == "2026-11"
    assert report.start_date.isoformat() == "2026-11-01"
    assert report.end_date.isoformat() == "2026-11-30"
    assert report.total_income == Decimal("5500.50")
    assert report.total_expenses == Decimal("1000.00")
    assert report.balance == Decimal("4500.50")
    assert report.transaction_count == 6
    assert report.top_category == "alimentacion"
    assert sum(c.total for c in report.categories) == report.total_expenses


async def test_monthly_report_handles_february_in_leap_and_common_years(session):
    user = await make_user(session)
    leap = await service.get_monthly_report(session, user.id, MonthlyReportQuery(month="2028-02"))
    common = await service.get_monthly_report(session, user.id, MonthlyReportQuery(month="2027-02"))
    assert leap.end_date.day == 29
    assert common.end_date.day == 28


async def test_monthly_report_defaults_to_current_month_of_user(session):
    user = await make_user(session)
    today = local_today(user.timezone)
    report = await service.get_monthly_report(session, user.id, MonthlyReportQuery())
    assert report.month == today.strftime("%Y-%m")
    assert report.generated_on == today


async def test_empty_month_returns_zeros(session):
    user = await make_user(session)
    report = await service.get_monthly_report(
        session, user.id, MonthlyReportQuery(month="2026-01")
    )
    assert report.total_income == Decimal("0.00")
    assert report.total_expenses == Decimal("0.00")
    assert report.balance == Decimal("0.00")
    assert report.transaction_count == 0
    assert report.categories == []
    assert report.top_category is None


async def test_negative_balance_is_reported(session):
    user = await make_user(session)
    await add(session, user.id, "income", "100", "2026-11-01")
    await add(session, user.id, "expense", "250", "2026-11-02", "vivienda")
    report = await service.get_monthly_report(
        session, user.id, MonthlyReportQuery(month="2026-11")
    )
    assert report.balance == Decimal("-150.00")


async def test_reports_are_isolated_between_users(session):
    ana = await make_user(session, "ana@example.com")
    beto = await make_user(session, "beto@example.com")
    ana_id, beto_id = ana.id, beto.id
    await seed_november(session, ana_id)
    await add(session, beto_id, "expense", "40", "2026-11-05", "salud")
    report = await service.get_monthly_report(
        session, beto_id, MonthlyReportQuery(month="2026-11")
    )
    assert report.total_income == Decimal("0.00")
    assert report.total_expenses == Decimal("40.00")
    assert [c.category for c in report.categories] == ["salud"]
    breakdown = await service.get_expense_breakdown(session, beto_id, PeriodQuery())
    assert breakdown.total_expenses == Decimal("40.00")


async def test_goal_contributions_do_not_appear_in_reports(session):
    from app.schemas.savings_goal import ContributionCreate, GoalCreate
    from app.services import savings_goal as goal_service

    user = await make_user(session)
    user_id = user.id
    await add(session, user_id, "expense", "100", "2026-11-05", "alimentacion")
    goal = await goal_service.create_goal(
        session, user_id, GoalCreate(name="Viaje", target_amount=Decimal("5000"))
    )
    await goal_service.add_contribution(
        session,
        user_id,
        ContributionCreate(goal_id=goal.id, amount=Decimal("700"), contributed_on="2026-11-06"),
    )
    report = await service.get_monthly_report(
        session, user_id, MonthlyReportQuery(month="2026-11")
    )
    assert report.total_expenses == Decimal("100.00")
    assert report.transaction_count == 1


async def test_generate_monthly_pdf_returns_report_and_pdf_bytes(session):
    user = await make_user(session)
    await seed_november(session, user.id)
    report, content = await service.generate_monthly_pdf(
        session, user.id, MonthlyReportQuery(month="2026-11")
    )
    assert report.total_expenses == Decimal("1000.00")
    assert content.startswith(b"%PDF")


@pytest.mark.parametrize("month", ["2026-13", "2026-00", "26-11", "noviembre", "2026-11-01"])
def test_month_query_validates_format(month):
    from pydantic import ValidationError

    with pytest.raises(ValidationError):
        MonthlyReportQuery(month=month)
