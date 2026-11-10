import json

import pytest
from pydantic import ValidationError

from app.core.errors import NotFoundError
from app.schemas.user import UserCreate
from app.services import auth as auth_service
from app.tools import budgets, goals
from app.tools import transactions as transaction_tools


async def make_user(session, email: str = "ana@example.com"):
    return await auth_service.register_user(
        session, UserCreate(email=email, password="clave-segura-1")
    )


async def test_set_budget_and_status_tools_are_json_serializable(session):
    user = await make_user(session)
    saved = await budgets.set_budget(session, user.id, {"amount": 1000000})
    assert saved["amount"] == "1000000.00"
    json.dumps(saved)
    await transaction_tools.add_transaction(
        session,
        user.id,
        {
            "type": "expense",
            "amount": 250000,
            "concept": "Mercado",
            "occurred_on": "2026-11-03",
            "category": "alimentacion",
        },
    )
    status = await budgets.get_budget_status(session, user.id, {"month": "2026-11"})
    assert status == {
        "month": "2026-11",
        "budget": "1000000.00",
        "spent": "250000.00",
        "remaining": "750000.00",
        "percentage_used": "25.00",
        "over_budget": False,
    }
    json.dumps(status)


@pytest.mark.parametrize("args", [{"amount": 0}, {"amount": -5}, {}, {"amount": "10.999"}])
async def test_set_budget_validates_amount(session, args):
    user = await make_user(session)
    with pytest.raises(ValidationError):
        await budgets.set_budget(session, user.id, args)


@pytest.mark.parametrize("month", ["2026-13", "2026-1", "noviembre", "2026-11-01"])
async def test_budget_status_validates_month(session, month):
    user = await make_user(session)
    with pytest.raises(ValidationError):
        await budgets.get_budget_status(session, user.id, {"month": month})


async def test_budget_tools_reject_user_id_argument(session):
    user = await make_user(session)
    other = await make_user(session, "beto@example.com")
    with pytest.raises(ValidationError):
        await budgets.set_budget(session, user.id, {"amount": 10, "user_id": str(other.id)})
    with pytest.raises(ValidationError):
        await budgets.get_budget_status(session, user.id, {"user_id": str(other.id)})


async def test_budget_status_without_budget_raises_not_found(session):
    user = await make_user(session)
    with pytest.raises(NotFoundError):
        await budgets.get_budget_status(session, user.id, {})


async def test_goal_tools_full_flow(session):
    user = await make_user(session)
    user_id = user.id
    created = await goals.create_savings_goal(
        session, user_id, {"name": "Viaje", "target_amount": 2000000}
    )
    assert created["accumulated"] == "0.00"
    json.dumps(created)

    added = await goals.add_goal_contribution(
        session, user_id, {"goal_id": created["id"], "amount": 500000, "contributed_on": "2026-11-05"}
    )
    assert added["contribution"]["amount"] == "500000.00"
    assert added["progress"]["percentage"] == "25.00"
    json.dumps(added)

    listed = await goals.list_savings_goals(session, user_id, {})
    assert listed["count"] == 1
    assert listed["goals"][0]["remaining"] == "1500000.00"

    updated = await goals.update_savings_goal(
        session, user_id, {"goal_id": created["id"], "name": "Viaje a Cartagena"}
    )
    assert updated["name"] == "Viaje a Cartagena"
    assert updated["accumulated"] == "500000.00"

    deleted = await goals.delete_savings_goal(session, user_id, {"goal_id": created["id"]})
    assert deleted["deleted"] is True
    assert (await goals.list_savings_goals(session, user_id, {}))["count"] == 0


@pytest.mark.parametrize(
    "args",
    [
        {"name": "Viaje"},
        {"target_amount": 100},
        {"name": "   ", "target_amount": 100},
        {"name": "Viaje", "target_amount": 0},
        {"name": "Viaje", "target_amount": 100, "deadline": "pronto"},
    ],
)
async def test_create_goal_validates_arguments(session, args):
    user = await make_user(session)
    with pytest.raises(ValidationError):
        await goals.create_savings_goal(session, user.id, args)


async def test_update_goal_validates_arguments(session):
    user = await make_user(session)
    user_id = user.id
    created = await goals.create_savings_goal(
        session, user_id, {"name": "Viaje", "target_amount": 100}
    )
    gid = created["id"]
    for args in (
        {"name": "X"},
        {"goal_id": gid},
        {"goal_id": gid, "target_amount": 0},
        {"goal_id": gid, "name": None},
        {"goal_id": gid, "target_amount": None},
        {"goal_id": gid, "user_id": str(user_id)},
    ):
        with pytest.raises(ValidationError):
            await goals.update_savings_goal(session, user_id, args)


async def test_goal_tools_reject_user_id_and_unknown_args(session):
    user = await make_user(session)
    with pytest.raises(ValidationError):
        await goals.create_savings_goal(
            session, user.id, {"name": "Viaje", "target_amount": 100, "user_id": str(user.id)}
        )
    with pytest.raises(ValidationError):
        await goals.list_savings_goals(session, user.id, {"user_id": str(user.id)})
    with pytest.raises(ValidationError):
        await goals.add_goal_contribution(
            session,
            user.id,
            {"goal_id": "00000000-0000-0000-0000-000000000000", "amount": 0},
        )


async def test_goal_tool_unknown_id_raises_not_found(session):
    user = await make_user(session)
    unknown = "00000000-0000-0000-0000-000000000000"
    with pytest.raises(NotFoundError):
        await goals.delete_savings_goal(session, user.id, {"goal_id": unknown})
    with pytest.raises(NotFoundError):
        await goals.add_goal_contribution(session, user.id, {"goal_id": unknown, "amount": 10})


async def test_contribution_tool_does_not_change_balance(session):
    user = await make_user(session)
    user_id = user.id
    await transaction_tools.add_transaction(
        session,
        user_id,
        {"type": "income", "amount": 1000, "concept": "Salario", "occurred_on": "2026-11-01"},
    )
    created = await goals.create_savings_goal(
        session, user_id, {"name": "Viaje", "target_amount": 500}
    )
    await goals.add_goal_contribution(session, user_id, {"goal_id": created["id"], "amount": 300})
    balance = await transaction_tools.get_balance(session, user_id, {})
    assert balance["total_expenses"] == "0.00"
    assert balance["balance"] == "1000.00"
