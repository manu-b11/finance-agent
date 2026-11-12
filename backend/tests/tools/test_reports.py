import json

import pytest
from pydantic import ValidationError

from app.schemas.user import UserCreate
from app.services import auth as auth_service
from app.tools import reports
from app.tools import transactions as transaction_tools


async def make_user(session, email: str = "ana@example.com"):
    return await auth_service.register_user(
        session, UserCreate(email=email, password="clave-segura-1")
    )


async def seed(session, user_id):
    await transaction_tools.add_transaction(
        session,
        user_id,
        {"type": "income", "amount": 3000, "concept": "Salario", "occurred_on": "2026-11-01"},
    )
    for concept, amount, category in (
        ("Mercado", 400, "alimentacion"),
        ("Bus", 100, "transporte"),
    ):
        await transaction_tools.add_transaction(
            session,
            user_id,
            {
                "type": "expense",
                "amount": amount,
                "concept": concept,
                "occurred_on": "2026-11-05",
                "category": category,
            },
        )


async def test_expenses_by_category_tool_is_json_serializable(session):
    user = await make_user(session)
    await seed(session, user.id)
    result = await reports.get_expenses_by_category(
        session, user.id, {"start_date": "2026-11-01", "end_date": "2026-11-30"}
    )
    assert result["total_expenses"] == "500.00"
    assert result["top_category"] == "alimentacion"
    assert result["categories"][0] == {
        "category": "alimentacion",
        "label": "Alimentación",
        "total": "400.00",
        "percentage": "80.00",
    }
    json.dumps(result)


async def test_monthly_report_tool_includes_pdf_path_and_expenses(session):
    user = await make_user(session)
    await seed(session, user.id)
    result = await reports.get_monthly_report(session, user.id, {"month": "2026-11"})
    assert result["total_income"] == "3000.00"
    assert result["total_expenses"] == "500.00"
    assert result["balance"] == "2500.00"
    assert result["pdf_url"] == "/reports/monthly/2026-11/pdf"
    assert result["expense_count"] == 2
    assert {item["concept"] for item in result["expenses"]} == {"Mercado", "Bus"}
    json.dumps(result)


async def test_report_tools_validate_arguments(session):
    user = await make_user(session)
    with pytest.raises(ValidationError):
        await reports.get_monthly_report(session, user.id, {"month": "2026-13"})
    with pytest.raises(ValidationError):
        await reports.get_expenses_by_category(
            session, user.id, {"start_date": "2026-11-30", "end_date": "2026-11-01"}
        )


async def test_report_tools_reject_user_id_argument(session):
    user = await make_user(session)
    other = await make_user(session, "beto@example.com")
    with pytest.raises(ValidationError):
        await reports.get_monthly_report(session, user.id, {"user_id": str(other.id)})
    with pytest.raises(ValidationError):
        await reports.get_expenses_by_category(session, user.id, {"user_id": str(other.id)})
