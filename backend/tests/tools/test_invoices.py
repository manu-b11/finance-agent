import json

import pytest
from pydantic import ValidationError

from app.core.errors import ConflictError, IncompleteInformationError, NotFoundError
from app.schemas.invoice import DraftItem, InvoiceDraft
from app.schemas.user import UserCreate
from app.services import auth as auth_service
from app.services import invoice as invoice_service
from app.tools import invoices as tools
from app.tools import transactions as transaction_tools

DRAFT = InvoiceDraft(
    merchant="Éxito",
    issued_on="2026-11-05",
    total="9000",
    category="alimentacion",
    items=[DraftItem(description="Leche", quantity=2, unit_price=4500)],
)
UNKNOWN = "00000000-0000-0000-0000-000000000000"


async def make_user(session, email: str = "ana@example.com"):
    return await auth_service.register_user(
        session, UserCreate(email=email, password="clave-segura-1")
    )


async def make_draft(session, user_id):
    created = await invoice_service.create_draft(session, user_id, "f.png", DRAFT)
    return str(created.id)


async def test_get_and_list_tools_are_json_serializable(session):
    user = await make_user(session)
    invoice_id = await make_draft(session, user.id)
    result = await tools.get_invoice(session, user.id, {"invoice_id": invoice_id})
    assert result["status"] == "draft"
    assert result["items"][0]["line_total"] == "9000.00"
    assert result["total_matches_items"] is True
    json.dumps(result)
    listed = await tools.list_draft_invoices(session, user.id, {})
    assert listed["count"] == 1
    json.dumps(listed)


async def test_update_tools(session):
    user = await make_user(session)
    invoice_id = await make_draft(session, user.id)
    updated = await tools.update_invoice(
        session, user.id, {"invoice_id": invoice_id, "merchant": "Carulla", "total": 10000}
    )
    assert updated["merchant"] == "Carulla"
    assert updated["total"] == "10000.00"
    edited = await tools.update_invoice_item(
        session, user.id, {"invoice_id": invoice_id, "position": 1, "unit_price": 5000}
    )
    assert edited["items"][0]["line_total"] == "10000.00"
    added = await tools.add_invoice_item(
        session, user.id, {"invoice_id": invoice_id, "description": "Pan", "unit_price": 2000}
    )
    assert len(added["items"]) == 2
    removed = await tools.delete_invoice_item(
        session, user.id, {"invoice_id": invoice_id, "position": 2}
    )
    assert len(removed["items"]) == 1
    json.dumps(removed)


async def test_update_tools_validate_arguments(session):
    user = await make_user(session)
    invoice_id = await make_draft(session, user.id)
    bad_calls = [
        (tools.update_invoice, {"merchant": "X"}),
        (tools.update_invoice, {"invoice_id": invoice_id}),
        (tools.update_invoice, {"invoice_id": invoice_id, "total": 0}),
        (tools.update_invoice, {"invoice_id": invoice_id, "merchant": None}),
        (tools.update_invoice, {"invoice_id": invoice_id, "issued_on": "ayer"}),
        (tools.update_invoice, {"invoice_id": invoice_id, "category": "lujos"}),
        (tools.update_invoice_item, {"invoice_id": invoice_id, "unit_price": 1}),
        (tools.update_invoice_item, {"invoice_id": invoice_id, "position": 0, "unit_price": 1}),
        (tools.update_invoice_item, {"invoice_id": invoice_id, "position": 1}),
        (tools.update_invoice_item, {"invoice_id": invoice_id, "position": 1, "quantity": 0}),
        (tools.add_invoice_item, {"invoice_id": invoice_id, "description": "X"}),
        (tools.add_invoice_item, {"invoice_id": invoice_id, "description": "  ", "unit_price": 1}),
        (tools.add_invoice_item, {"invoice_id": invoice_id, "description": "X", "unit_price": -1}),
        (tools.delete_invoice_item, {"invoice_id": invoice_id}),
    ]
    for handler, args in bad_calls:
        with pytest.raises(ValidationError):
            await handler(session, user.id, args)


async def test_tools_reject_user_id_argument(session):
    user = await make_user(session)
    other = await make_user(session, "beto@example.com")
    invoice_id = await make_draft(session, user.id)
    smuggled = {"user_id": str(other.id)}
    calls = [
        (tools.get_invoice, {"invoice_id": invoice_id, **smuggled}),
        (tools.list_draft_invoices, smuggled),
        (tools.update_invoice, {"invoice_id": invoice_id, "merchant": "X", **smuggled}),
        (tools.discard_invoice, {"invoice_id": invoice_id, **smuggled}),
        (
            tools.confirm_invoice,
            {"invoice_id": invoice_id, "user_confirmed": True, **smuggled},
        ),
    ]
    for handler, args in calls:
        with pytest.raises(ValidationError):
            await handler(session, user.id, args)


@pytest.mark.parametrize("flag", [False, None, "yes", 0])
async def test_confirm_requires_explicit_user_confirmation(session, flag):
    user = await make_user(session)
    user_id = user.id
    invoice_id = await make_draft(session, user_id)
    with pytest.raises(ValidationError):
        await tools.confirm_invoice(
            session, user_id, {"invoice_id": invoice_id, "user_confirmed": flag}
        )
    with pytest.raises(ValidationError):
        await tools.confirm_invoice(session, user_id, {"invoice_id": invoice_id})
    balance = await transaction_tools.get_balance(session, user_id, {})
    assert balance["total_expenses"] == "0.00"


async def test_confirm_tool_registers_one_expense(session):
    user = await make_user(session)
    user_id = user.id
    invoice_id = await make_draft(session, user_id)
    result = await tools.confirm_invoice(
        session, user_id, {"invoice_id": invoice_id, "user_confirmed": True}
    )
    assert result["status"] == "confirmed"
    assert result["transaction_id"]
    json.dumps(result)
    balance = await transaction_tools.get_balance(session, user_id, {})
    assert balance["total_expenses"] == "9000.00"
    listed = await transaction_tools.list_transactions(session, user_id, {})
    assert listed["count"] == 1
    with pytest.raises(ConflictError):
        await tools.confirm_invoice(
            session, user_id, {"invoice_id": invoice_id, "user_confirmed": True}
        )


async def test_confirm_incomplete_invoice_raises_domain_error(session):
    user = await make_user(session)
    created = await invoice_service.create_draft(
        session, user.id, None, InvoiceDraft(merchant="X", total="10")
    )
    with pytest.raises(IncompleteInformationError):
        await tools.confirm_invoice(
            session, user.id, {"invoice_id": str(created.id), "user_confirmed": True}
        )


async def test_discard_tool(session):
    user = await make_user(session)
    invoice_id = await make_draft(session, user.id)
    result = await tools.discard_invoice(session, user.id, {"invoice_id": invoice_id})
    assert result["discarded"] is True
    json.dumps(result)
    with pytest.raises(NotFoundError):
        await tools.get_invoice(session, user.id, {"invoice_id": invoice_id})


async def test_tools_cannot_touch_other_users_invoices(session):
    ana = await make_user(session, "ana@example.com")
    beto = await make_user(session, "beto@example.com")
    ana_id, beto_id = ana.id, beto.id
    invoice_id = await make_draft(session, ana_id)
    for handler, args in (
        (tools.get_invoice, {"invoice_id": invoice_id}),
        (tools.discard_invoice, {"invoice_id": invoice_id}),
        (tools.update_invoice, {"invoice_id": invoice_id, "merchant": "X"}),
        (tools.confirm_invoice, {"invoice_id": invoice_id, "user_confirmed": True}),
    ):
        with pytest.raises(NotFoundError):
            await handler(session, beto_id, args)
    with pytest.raises(NotFoundError):
        await tools.get_invoice(session, ana_id, {"invoice_id": UNKNOWN})
    assert (await tools.get_invoice(session, ana_id, {"invoice_id": invoice_id}))["status"] == "draft"
