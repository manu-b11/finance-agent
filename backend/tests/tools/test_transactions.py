import json

import pytest
from pydantic import ValidationError

from app.core.errors import NotFoundError
from app.schemas.user import UserCreate
from app.services import auth as auth_service
from app.tools import transactions as tools


async def make_user(session, email: str = "ana@example.com"):
    return await auth_service.register_user(
        session, UserCreate(email=email, password="clave-segura-1")
    )


EXPENSE_ARGS = {
    "type": "expense",
    "amount": 25000,
    "concept": "Almuerzo",
    "occurred_on": "2026-11-05",
    "category": "alimentacion",
}


async def test_add_transaction_returns_json_serializable_result(session):
    user = await make_user(session)
    result = await tools.add_transaction(session, user.id, EXPENSE_ARGS)
    assert result["amount"] == "25000.00"
    assert result["type"] == "expense"
    assert result["category"] == "alimentacion"
    json.dumps(result)


async def test_add_transaction_accepts_float_amount_without_drift(session):
    user = await make_user(session)
    result = await tools.add_transaction(session, user.id, {**EXPENSE_ARGS, "amount": 19.9})
    assert result["amount"] == "19.90"


@pytest.mark.parametrize("amount", [0, -5])
async def test_add_transaction_rejects_non_positive_amount(session, amount):
    user = await make_user(session)
    with pytest.raises(ValidationError):
        await tools.add_transaction(session, user.id, {**EXPENSE_ARGS, "amount": amount})


async def test_add_transaction_rejects_more_than_two_decimals(session):
    user = await make_user(session)
    with pytest.raises(ValidationError):
        await tools.add_transaction(session, user.id, {**EXPENSE_ARGS, "amount": "10.999"})


async def test_add_expense_requires_category(session):
    user = await make_user(session)
    args = {k: v for k, v in EXPENSE_ARGS.items() if k != "category"}
    with pytest.raises(ValidationError):
        await tools.add_transaction(session, user.id, args)


async def test_add_transaction_requires_date_and_concept(session):
    user = await make_user(session)
    for missing in ("occurred_on", "concept"):
        args = {k: v for k, v in EXPENSE_ARGS.items() if k != missing}
        with pytest.raises(ValidationError):
            await tools.add_transaction(session, user.id, args)


async def test_add_transaction_rejects_blank_concept(session):
    user = await make_user(session)
    with pytest.raises(ValidationError):
        await tools.add_transaction(session, user.id, {**EXPENSE_ARGS, "concept": "   "})


async def test_tool_rejects_user_id_in_arguments(session):
    user = await make_user(session)
    other = await make_user(session, "beto@example.com")
    with pytest.raises(ValidationError):
        await tools.add_transaction(session, user.id, {**EXPENSE_ARGS, "user_id": str(other.id)})
    with pytest.raises(ValidationError):
        await tools.get_balance(session, user.id, {"user_id": str(other.id)})


async def test_list_and_balance_tools(session):
    user = await make_user(session)
    await tools.add_transaction(
        session,
        user.id,
        {"type": "income", "amount": 100000, "concept": "Salario", "occurred_on": "2026-11-01"},
    )
    await tools.add_transaction(session, user.id, EXPENSE_ARGS)

    listed = await tools.list_transactions(session, user.id, {"type": "expense"})
    assert listed["count"] == 1
    assert listed["transactions"][0]["concept"] == "Almuerzo"

    balance = await tools.get_balance(session, user.id, {})
    assert balance == {
        "total_income": "100000.00",
        "total_expenses": "25000.00",
        "balance": "75000.00",
        "start_date": None,
        "end_date": None,
    }
    json.dumps(balance)


async def test_balance_rejects_inverted_period(session):
    user = await make_user(session)
    with pytest.raises(ValidationError):
        await tools.get_balance(
            session, user.id, {"start_date": "2026-11-30", "end_date": "2026-11-01"}
        )


async def test_update_transaction_tool(session):
    user = await make_user(session)
    created = await tools.add_transaction(session, user.id, EXPENSE_ARGS)
    result = await tools.update_transaction(
        session, user.id, {"transaction_id": created["id"], "amount": 30000, "concept": "Cena"}
    )
    assert result["id"] == created["id"]
    assert result["amount"] == "30000.00"
    assert result["concept"] == "Cena"
    assert result["category"] == "alimentacion"
    json.dumps(result)


async def test_update_transaction_tool_validates_arguments(session):
    user = await make_user(session)
    created = await tools.add_transaction(session, user.id, EXPENSE_ARGS)
    tid = created["id"]
    with pytest.raises(ValidationError):
        await tools.update_transaction(session, user.id, {"amount": 100})  # sin id
    with pytest.raises(ValidationError):
        await tools.update_transaction(session, user.id, {"transaction_id": tid})  # sin cambios
    with pytest.raises(ValidationError):
        await tools.update_transaction(session, user.id, {"transaction_id": tid, "amount": 0})
    with pytest.raises(ValidationError):
        await tools.update_transaction(session, user.id, {"transaction_id": tid, "amount": None})
    with pytest.raises(ValidationError):
        await tools.update_transaction(
            session, user.id, {"transaction_id": tid, "user_id": str(user.id)}
        )


async def test_update_transaction_tool_unknown_id_raises_not_found(session):
    user = await make_user(session)
    with pytest.raises(NotFoundError):
        await tools.update_transaction(
            session,
            user.id,
            {"transaction_id": "00000000-0000-0000-0000-000000000000", "concept": "X"},
        )


async def test_delete_transaction_tool(session):
    user = await make_user(session)
    created = await tools.add_transaction(session, user.id, EXPENSE_ARGS)
    result = await tools.delete_transaction(session, user.id, {"transaction_id": created["id"]})
    assert result["deleted"] is True
    assert result["transaction"]["concept"] == "Almuerzo"
    json.dumps(result)
    listed = await tools.list_transactions(session, user.id, {})
    assert listed["count"] == 0


async def test_delete_transaction_tool_rejects_other_users_transaction(session):
    ana = await make_user(session, "ana@example.com")
    beto = await make_user(session, "beto@example.com")
    created = await tools.add_transaction(session, ana.id, EXPENSE_ARGS)
    with pytest.raises(NotFoundError):
        await tools.delete_transaction(session, beto.id, {"transaction_id": created["id"]})
    assert (await tools.list_transactions(session, ana.id, {}))["count"] == 1