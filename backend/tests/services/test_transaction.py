from datetime import date
from decimal import Decimal

import pytest
from pydantic import ValidationError

from app.core.errors import NotFoundError
from app.schemas.transaction import (
    PeriodQuery,
    TransactionCreate,
    TransactionFilters,
    TransactionUpdate,
)
from app.schemas.user import UserCreate
from app.services import auth as auth_service
from app.services import transaction as transaction_service


async def make_user(session, email: str = "ana@example.com"):
    return await auth_service.register_user(
        session, UserCreate(email=email, password="clave-segura-1")
    )


def income(amount: str, day: date = date(2026, 11, 1), concept: str = "Salario") -> TransactionCreate:
    return TransactionCreate(type="income", amount=Decimal(amount), concept=concept, occurred_on=day)


def expense(
    amount: str,
    day: date = date(2026, 11, 2),
    concept: str = "Almuerzo",
    category: str = "alimentacion",
) -> TransactionCreate:
    return TransactionCreate(
        type="expense", amount=Decimal(amount), concept=concept, occurred_on=day, category=category
    )


async def test_create_expense_keeps_exact_decimal(session):
    user = await make_user(session)
    created = await transaction_service.create_transaction(session, user.id, expense("1234.50"))
    assert created.user_id == user.id
    assert created.amount == Decimal("1234.50")
    assert created.type == "expense"
    assert created.category == "alimentacion"


async def test_create_income_has_no_category(session):
    user = await make_user(session)
    data = TransactionCreate(
        type="income",
        amount=Decimal("100"),
        concept="Venta",
        occurred_on=date(2026, 11, 1),
        category="otros",
    )
    created = await transaction_service.create_transaction(session, user.id, data)
    assert created.category is None


async def test_balance_without_transactions_is_zero(session):
    user = await make_user(session)
    balance = await transaction_service.get_balance(session, user.id, PeriodQuery())
    assert balance.total_income == Decimal("0.00")
    assert balance.total_expenses == Decimal("0.00")
    assert balance.balance == Decimal("0.00")


async def test_balance_is_income_minus_expenses_without_float_errors(session):
    user = await make_user(session)
    await transaction_service.create_transaction(session, user.id, income("0.10"))
    await transaction_service.create_transaction(session, user.id, income("0.20"))
    await transaction_service.create_transaction(session, user.id, expense("0.05"))
    balance = await transaction_service.get_balance(session, user.id, PeriodQuery())
    assert balance.total_income == Decimal("0.30")
    assert balance.total_expenses == Decimal("0.05")
    assert balance.balance == Decimal("0.25")


async def test_balance_can_be_negative(session):
    user = await make_user(session)
    await transaction_service.create_transaction(session, user.id, income("100000"))
    await transaction_service.create_transaction(session, user.id, expense("150000"))
    balance = await transaction_service.get_balance(session, user.id, PeriodQuery())
    assert balance.balance == Decimal("-50000.00")


async def test_balance_filters_by_period_inclusive(session):
    user = await make_user(session)
    await transaction_service.create_transaction(session, user.id, income("500", date(2026, 10, 31)))
    await transaction_service.create_transaction(session, user.id, income("1000", date(2026, 11, 1)))
    await transaction_service.create_transaction(session, user.id, expense("200", date(2026, 11, 30)))
    await transaction_service.create_transaction(session, user.id, expense("999", date(2026, 12, 1)))
    period = PeriodQuery(start_date=date(2026, 11, 1), end_date=date(2026, 11, 30))
    balance = await transaction_service.get_balance(session, user.id, period)
    assert balance.total_income == Decimal("1000.00")
    assert balance.total_expenses == Decimal("200.00")
    assert balance.balance == Decimal("800.00")


async def test_list_orders_by_date_desc_and_applies_filters(session):
    user = await make_user(session)
    await transaction_service.create_transaction(session, user.id, income("1000", date(2026, 11, 1)))
    await transaction_service.create_transaction(
        session, user.id, expense("10", date(2026, 11, 2), "Bus", "transporte")
    )
    await transaction_service.create_transaction(
        session, user.id, expense("20", date(2026, 11, 3), "Cena", "alimentacion")
    )

    everything = await transaction_service.list_transactions(session, user.id, TransactionFilters())
    assert [t.concept for t in everything] == ["Cena", "Bus", "Salario"]

    only_food = await transaction_service.list_transactions(
        session, user.id, TransactionFilters(category="alimentacion")
    )
    assert [t.concept for t in only_food] == ["Cena"]

    only_income = await transaction_service.list_transactions(
        session, user.id, TransactionFilters(type="income")
    )
    assert [t.concept for t in only_income] == ["Salario"]

    ranged = await transaction_service.list_transactions(
        session, user.id, TransactionFilters(start_date=date(2026, 11, 2), end_date=date(2026, 11, 2))
    )
    assert [t.concept for t in ranged] == ["Bus"]

    limited = await transaction_service.list_transactions(
        session, user.id, TransactionFilters(limit=1)
    )
    assert [t.concept for t in limited] == ["Cena"]


async def test_users_only_see_their_own_transactions(session):
    ana = await make_user(session, "ana@example.com")
    beto = await make_user(session, "beto@example.com")
    await transaction_service.create_transaction(session, ana.id, income("1000"))
    await transaction_service.create_transaction(session, beto.id, expense("300"))

    ana_list = await transaction_service.list_transactions(session, ana.id, TransactionFilters())
    assert len(ana_list) == 1
    assert ana_list[0].user_id == ana.id

    beto_balance = await transaction_service.get_balance(session, beto.id, PeriodQuery())
    assert beto_balance.total_income == Decimal("0.00")
    assert beto_balance.balance == Decimal("-300.00")


async def test_update_changes_only_sent_fields(session):
    user = await make_user(session)
    created = await transaction_service.create_transaction(session, user.id, expense("1000"))
    updated = await transaction_service.update_transaction(
        session, user.id, created.id, TransactionUpdate(amount=Decimal("1500.50"))
    )
    assert updated.amount == Decimal("1500.50")
    assert updated.concept == "Almuerzo"
    assert updated.category == "alimentacion"
    assert updated.occurred_on == date(2026, 11, 2)


async def test_update_balance_reflects_change(session):
    user = await make_user(session)
    created = await transaction_service.create_transaction(session, user.id, expense("1000"))
    await transaction_service.update_transaction(
        session, user.id, created.id, TransactionUpdate(amount=Decimal("400"))
    )
    balance = await transaction_service.get_balance(session, user.id, PeriodQuery())
    assert balance.total_expenses == Decimal("400.00")


async def test_update_expense_to_income_clears_category(session):
    user = await make_user(session)
    created = await transaction_service.create_transaction(session, user.id, expense("1000"))
    updated = await transaction_service.update_transaction(
        session, user.id, created.id, TransactionUpdate(type="income")
    )
    assert updated.type == "income"
    assert updated.category is None


async def test_update_income_to_expense_requires_category(session):
    user = await make_user(session)
    created = await transaction_service.create_transaction(session, user.id, income("1000"))
    with pytest.raises(ValidationError):
        await transaction_service.update_transaction(
            session, user.id, created.id, TransactionUpdate(type="expense")
        )
    updated = await transaction_service.update_transaction(
        session, user.id, created.id, TransactionUpdate(type="expense", category="otros")
    )
    assert updated.type == "expense"
    assert updated.category == "otros"


async def test_update_unknown_or_foreign_transaction_raises_not_found(session):
    ana = await make_user(session, "ana@example.com")
    beto = await make_user(session, "beto@example.com")
    created = await transaction_service.create_transaction(session, ana.id, expense("1000"))
    with pytest.raises(NotFoundError):
        await transaction_service.update_transaction(
            session, beto.id, created.id, TransactionUpdate(concept="Robado")
        )
    unchanged = await transaction_service.list_transactions(session, ana.id, TransactionFilters())
    assert unchanged[0].concept == "Almuerzo"


async def test_delete_removes_transaction_and_updates_balance(session):
    user = await make_user(session)
    created = await transaction_service.create_transaction(session, user.id, expense("1000"))
    deleted = await transaction_service.delete_transaction(session, user.id, created.id)
    assert deleted.id == created.id
    assert await transaction_service.list_transactions(session, user.id, TransactionFilters()) == []
    balance = await transaction_service.get_balance(session, user.id, PeriodQuery())
    assert balance.balance == Decimal("0.00")


async def test_delete_foreign_transaction_raises_not_found(session):
    ana = await make_user(session, "ana@example.com")
    beto = await make_user(session, "beto@example.com")
    created = await transaction_service.create_transaction(session, ana.id, expense("1000"))
    with pytest.raises(NotFoundError):
        await transaction_service.delete_transaction(session, beto.id, created.id)
    assert len(await transaction_service.list_transactions(session, ana.id, TransactionFilters())) == 1