from decimal import Decimal

import pytest

from app.core.errors import NotFoundError
from app.schemas.budget import BudgetSet, BudgetStatusQuery
from app.schemas.savings_goal import ContributionCreate, GoalCreate
from app.schemas.transaction import PeriodQuery, TransactionCreate
from app.schemas.user import UserCreate
from app.services import auth as auth_service
from app.services import budget as budget_service
from app.services import savings_goal as goal_service
from app.services import transaction as transaction_service


async def make_user(session, email: str = "ana@example.com"):
    return await auth_service.register_user(
        session, UserCreate(email=email, password="clave-segura-1")
    )


async def add_expense(session, user_id, amount, day: str, category: str = "alimentacion"):
    await transaction_service.create_transaction(
        session,
        user_id,
        TransactionCreate(
            type="expense",
            amount=Decimal(amount),
            concept="Gasto",
            occurred_on=day,
            category=category,
        ),
    )


async def test_set_budget_creates_and_then_updates_single_row(session):
    user = await make_user(session)
    first = await budget_service.set_budget(session, user.id, BudgetSet(amount=Decimal("1000000")))
    second = await budget_service.set_budget(session, user.id, BudgetSet(amount=Decimal("1500000")))
    assert first.id == second.id
    assert second.amount == Decimal("1500000.00")


async def test_status_uses_only_expenses_of_the_month(session):
    user = await make_user(session)
    await budget_service.set_budget(session, user.id, BudgetSet(amount=Decimal("1000.00")))
    await add_expense(session, user.id, "250.50", "2026-11-01")
    await add_expense(session, user.id, "100.00", "2026-11-30")
    await add_expense(session, user.id, "999.00", "2026-10-31")
    await add_expense(session, user.id, "999.00", "2026-12-01")
    await transaction_service.create_transaction(
        session,
        user.id,
        TransactionCreate(
            type="income", amount=Decimal("5000"), concept="Salario", occurred_on="2026-11-15"
        ),
    )
    status = await budget_service.get_budget_status(
        session, user.id, BudgetStatusQuery(month="2026-11")
    )
    assert status.month == "2026-11"
    assert status.spent == Decimal("350.50")
    assert status.remaining == Decimal("649.50")
    assert status.percentage_used == Decimal("35.05")
    assert status.over_budget is False


async def test_status_reports_overspending(session):
    user = await make_user(session)
    await budget_service.set_budget(session, user.id, BudgetSet(amount=Decimal("100")))
    await add_expense(session, user.id, "150", "2026-11-10")
    status = await budget_service.get_budget_status(
        session, user.id, BudgetStatusQuery(month="2026-11")
    )
    assert status.remaining == Decimal("-50.00")
    assert status.percentage_used == Decimal("150.00")
    assert status.over_budget is True


async def test_status_without_month_uses_current_month_of_user(session):
    from app.core.clock import local_today

    user = await make_user(session)
    await budget_service.set_budget(session, user.id, BudgetSet(amount=Decimal("100")))
    status = await budget_service.get_budget_status(session, user.id, BudgetStatusQuery())
    assert status.month == local_today(user.timezone).strftime("%Y-%m")


async def test_status_without_budget_raises_not_found(session):
    user = await make_user(session)
    with pytest.raises(NotFoundError):
        await budget_service.get_budget_status(session, user.id, BudgetStatusQuery(month="2026-11"))


async def test_budget_is_isolated_between_users(session):
    ana = await make_user(session, "ana@example.com")
    beto = await make_user(session, "beto@example.com")
    await budget_service.set_budget(session, ana.id, BudgetSet(amount=Decimal("100")))
    await add_expense(session, ana.id, "40", "2026-11-10")
    with pytest.raises(NotFoundError):
        await budget_service.get_budget_status(session, beto.id, BudgetStatusQuery(month="2026-11"))


async def test_goal_contributions_do_not_count_as_expenses(session):
    user = await make_user(session)
    user_id = user.id
    await budget_service.set_budget(session, user_id, BudgetSet(amount=Decimal("1000")))
    await add_expense(session, user_id, "100", "2026-11-10")
    goal = await goal_service.create_goal(
        session, user_id, GoalCreate(name="Viaje", target_amount=Decimal("5000"))
    )
    await goal_service.add_contribution(
        session,
        user_id,
        ContributionCreate(goal_id=goal.id, amount=Decimal("700"), contributed_on="2026-11-11"),
    )
    status = await budget_service.get_budget_status(
        session, user_id, BudgetStatusQuery(month="2026-11")
    )
    balance = await transaction_service.get_balance(session, user_id, PeriodQuery())
    assert status.spent == Decimal("100.00")
    assert balance.total_expenses == Decimal("100.00")
    assert balance.balance == Decimal("-100.00")
