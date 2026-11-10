import uuid

from app.tools import budgets, goals, reminders
from app.tools import transactions as transaction_tools

PAYLOAD = {"email": "ana@example.com", "password": "clave-segura-1"}
OTHER = {"email": "beto@example.com", "password": "clave-segura-1"}


async def auth_headers(client, payload=PAYLOAD) -> dict[str, str]:
    await client.post("/auth/register", json=payload)
    response = await client.post("/auth/login", json=payload)
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


async def user_id_of(client, headers) -> uuid.UUID:
    return uuid.UUID((await client.get("/auth/me", headers=headers)).json()["id"])


async def add(session, user_id, type_, amount, day, concept="Movimiento", category=None):
    args = {"type": type_, "amount": amount, "concept": concept, "occurred_on": day}
    if category:
        args["category"] = category
    await transaction_tools.add_transaction(session, user_id, args)


async def test_dashboard_requires_authentication(client):
    assert (await client.get("/dashboard")).status_code == 401


async def test_empty_dashboard_for_a_new_user(client):
    headers = await auth_headers(client)
    response = await client.get("/dashboard?month=2026-11", headers=headers)
    assert response.status_code == 200
    body = response.json()
    assert body["month"] == "2026-11"
    assert body["summary"]["total_income"] == "0.00"
    assert body["summary"]["balance"] == "0.00"
    assert body["summary"]["categories"] == []
    assert body["budget"] is None
    assert body["goals"] == []
    assert body["upcoming_reminders"] == []
    assert body["recent_transactions"] == []


async def test_dashboard_without_month_uses_the_current_month(client):
    from app.core.clock import local_today

    headers = await auth_headers(client)
    timezone = (await client.get("/auth/me", headers=headers)).json()["timezone"]
    body = (await client.get("/dashboard", headers=headers)).json()
    assert body["month"] == local_today(timezone).strftime("%Y-%m")
    assert body["summary"]["month"] == body["month"]


async def test_dashboard_combines_all_sections(client, session):
    headers = await auth_headers(client)
    uid = await user_id_of(client, headers)
    await add(session, uid, "income", 5000, "2026-11-01", "Salario")
    await add(session, uid, "expense", 400, "2026-11-05", "Mercado", "alimentacion")
    await add(session, uid, "expense", 100, "2026-11-06", "Bus", "transporte")
    await budgets.set_budget(session, uid, {"amount": 1000})
    goal = await goals.create_savings_goal(session, uid, {"name": "Viaje", "target_amount": 2000})
    await goals.add_goal_contribution(session, uid, {"goal_id": goal["id"], "amount": 500})
    await reminders.create_reminder(
        session, uid, {"concept": "Pagar arriendo", "remind_on": "2030-03-05", "remind_at": "09:00"}
    )
    body = (await client.get("/dashboard?month=2026-11", headers=headers)).json()
    assert body["summary"]["total_income"] == "5000.00"
    assert body["summary"]["total_expenses"] == "500.00"
    assert body["summary"]["balance"] == "4500.00"
    assert body["summary"]["top_category"] == "alimentacion"
    assert body["budget"] == {
        "month": "2026-11",
        "budget": "1000.00",
        "spent": "500.00",
        "remaining": "500.00",
        "percentage_used": "50.00",
        "over_budget": False,
    }
    assert [g["name"] for g in body["goals"]] == ["Viaje"]
    assert body["goals"][0]["percentage"] == "25.00"
    assert [r["concept"] for r in body["upcoming_reminders"]] == ["Pagar arriendo"]
    assert [t["concept"] for t in body["recent_transactions"]] == ["Bus", "Mercado", "Salario"]


async def test_goal_contributions_do_not_change_the_dashboard_balance(client, session):
    headers = await auth_headers(client)
    uid = await user_id_of(client, headers)
    await add(session, uid, "income", 1000, "2026-11-01")
    goal = await goals.create_savings_goal(session, uid, {"name": "Moto", "target_amount": 900})
    await goals.add_goal_contribution(
        session, uid, {"goal_id": goal["id"], "amount": 300, "contributed_on": "2026-11-02"}
    )
    body = (await client.get("/dashboard?month=2026-11", headers=headers)).json()
    assert body["summary"]["total_expenses"] == "0.00"
    assert body["summary"]["balance"] == "1000.00"
    assert body["goals"][0]["accumulated"] == "300.00"


async def test_month_filters_summary_budget_and_recent_but_not_goals(client, session):
    headers = await auth_headers(client)
    uid = await user_id_of(client, headers)
    await add(session, uid, "expense", 100, "2026-10-15", "Octubre", "salud")
    await add(session, uid, "expense", 300, "2026-11-15", "Noviembre", "salud")
    await budgets.set_budget(session, uid, {"amount": 1000})
    await goals.create_savings_goal(session, uid, {"name": "Meta", "target_amount": 100})
    october = (await client.get("/dashboard?month=2026-10", headers=headers)).json()
    assert october["summary"]["total_expenses"] == "100.00"
    assert october["budget"]["spent"] == "100.00"
    assert [t["concept"] for t in october["recent_transactions"]] == ["Octubre"]
    assert len(october["goals"]) == 1


async def test_recent_transactions_and_reminders_are_capped_at_five(client, session):
    headers = await auth_headers(client)
    uid = await user_id_of(client, headers)
    for day in range(1, 9):
        await add(session, uid, "expense", 10, f"2026-11-{day:02d}", f"Gasto {day}", "otros")
    for month in range(1, 8):
        await reminders.create_reminder(
            session,
            uid,
            {"concept": f"Recordatorio {month}", "remind_on": f"2030-{month:02d}-10", "remind_at": "09:00"},
        )
    body = (await client.get("/dashboard?month=2026-11", headers=headers)).json()
    assert [t["concept"] for t in body["recent_transactions"]] == [
        "Gasto 8",
        "Gasto 7",
        "Gasto 6",
        "Gasto 5",
        "Gasto 4",
    ]
    assert [r["concept"] for r in body["upcoming_reminders"]] == [f"Recordatorio {m}" for m in range(1, 6)]


async def test_cancelled_reminders_are_not_shown(client, session):
    headers = await auth_headers(client)
    uid = await user_id_of(client, headers)
    created = await reminders.create_reminder(
        session, uid, {"concept": "Cancelado", "remind_on": "2030-03-05", "remind_at": "09:00"}
    )
    await reminders.cancel_reminder(session, uid, {"reminder_id": created["id"]})
    body = (await client.get("/dashboard?month=2026-11", headers=headers)).json()
    assert body["upcoming_reminders"] == []


async def test_dashboard_only_shows_the_authenticated_users_data(client, session):
    ana = await auth_headers(client)
    beto = await auth_headers(client, OTHER)
    ana_id = await user_id_of(client, ana)
    await add(session, ana_id, "income", 9999, "2026-11-01", "Secreto")
    await budgets.set_budget(session, ana_id, {"amount": 100})
    await goals.create_savings_goal(session, ana_id, {"name": "Privada", "target_amount": 50})
    await reminders.create_reminder(
        session, ana_id, {"concept": "Privado", "remind_on": "2030-03-05", "remind_at": "09:00"}
    )
    body = (await client.get("/dashboard?month=2026-11", headers=beto)).json()
    assert body["summary"]["total_income"] == "0.00"
    assert body["budget"] is None
    assert body["goals"] == []
    assert body["upcoming_reminders"] == []
    assert body["recent_transactions"] == []


async def test_invalid_month_returns_422(client):
    headers = await auth_headers(client)
    for month in ("2026-13", "26-11", "noviembre", "2026-11-01"):
        assert (await client.get(f"/dashboard?month={month}", headers=headers)).status_code == 422
