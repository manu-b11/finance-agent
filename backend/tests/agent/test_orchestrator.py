import json

import pytest

from app.agent import orchestrator
from app.agent.llm_client import Message
from app.core.errors import ProcessingError
from app.schemas.user import UserCreate
from app.services import auth as auth_service
from app.tools import transactions as tools
from tests.agent.fakes import FakeChat, calls_response, text_response, tool_call

EXPENSE_ARGS = {
    "type": "expense",
    "amount": 25000,
    "concept": "Almuerzo",
    "occurred_on": "2026-11-05",
    "category": "alimentacion",
}


async def make_user(session, email: str = "ana@example.com"):
    return await auth_service.register_user(
        session, UserCreate(email=email, password="clave-segura-1")
    )


async def collect(chat, session, user_id, text: str = "hola"):
    return [
        event
        async for event in orchestrator.run(chat, session, user_id, [Message("user", text)])
    ]


async def test_runs_tool_and_returns_final_message(session):
    user = await make_user(session)
    chat = FakeChat(
        calls_response(tool_call("add_transaction", EXPENSE_ARGS)),
        text_response("Registré tu almuerzo."),
    )
    events = await collect(chat, session, user.id)
    assert [event.type for event in events] == ["tool_call", "tool_result", "message"]
    assert events[0].data == {"name": "add_transaction"}
    assert events[1].data["name"] == "add_transaction"
    assert events[1].data["result"]["concept"] == "Almuerzo"
    assert events[1].data["result"]["amount"] == "25000.00"
    assert events[2].data == {"text": "Registré tu almuerzo."}
    listed = await tools.list_transactions(session, user.id, {})
    assert listed["count"] == 1
    assert listed["transactions"][0]["concept"] == "Almuerzo"


async def test_tool_result_is_fed_back_to_model(session):
    user = await make_user(session)
    chat = FakeChat(
        calls_response(tool_call("add_transaction", EXPENSE_ARGS)),
        text_response("Listo."),
    )
    await collect(chat, session, user.id)
    second_call_messages, specs = chat.calls[1]
    assert second_call_messages[-2].role == "assistant"
    assert second_call_messages[-2].tool_calls[0].name == "add_transaction"
    tool_message = second_call_messages[-1]
    assert tool_message.role == "tool"
    assert tool_message.name == "add_transaction"
    assert json.loads(tool_message.content)["amount"] == "25000.00"
    names = {spec.name for spec in specs}
    assert {"add_transaction", "get_balance", "set_budget", "add_goal_contribution"} <= names


async def test_invalid_arguments_are_returned_to_model_without_side_effects(session):
    user = await make_user(session)
    user_id = user.id
    chat = FakeChat(
        calls_response(tool_call("add_transaction", {**EXPENSE_ARGS, "amount": 0})),
        text_response("El valor debe ser mayor que cero."),
    )
    events = await collect(chat, session, user.id)
    assert events[-1].type == "message"
    result = json.loads(chat.calls[1][0][-1].content)
    assert result["error"] == "invalid_arguments"
    assert result["details"][0]["field"] == "amount"
    assert (await tools.list_transactions(session, user_id, {}))["count"] == 0


async def test_user_id_in_model_arguments_is_rejected(session):
    ana = await make_user(session, "ana@example.com")
    beto = await make_user(session, "beto@example.com")
    ana_id, beto_id = ana.id, beto.id
    chat = FakeChat(
        calls_response(
            tool_call("add_transaction", {**EXPENSE_ARGS, "user_id": str(beto_id)})
        ),
        text_response("No pude registrarlo."),
    )
    await collect(chat, session, ana_id)
    result = json.loads(chat.calls[1][0][-1].content)
    assert result["error"] == "invalid_arguments"
    assert (await tools.list_transactions(session, beto_id, {}))["count"] == 0
    assert (await tools.list_transactions(session, ana_id, {}))["count"] == 0


async def test_unknown_tool_is_reported_to_model(session):
    user = await make_user(session)
    chat = FakeChat(
        calls_response(tool_call("drop_database", {})),
        text_response("No puedo hacer eso."),
    )
    await collect(chat, session, user.id)
    result = json.loads(chat.calls[1][0][-1].content)
    assert result["error"] == "unknown_tool"


async def test_domain_error_is_returned_to_model(session):
    user = await make_user(session)
    chat = FakeChat(
        calls_response(
            tool_call(
                "delete_transaction",
                {"transaction_id": "00000000-0000-0000-0000-000000000000"},
            )
        ),
        text_response("No encontré ese movimiento."),
    )
    events = await collect(chat, session, user.id)
    result = json.loads(chat.calls[1][0][-1].content)
    assert result == {"error": "not_found", "message": "No se encontró ese movimiento."}
    assert events[1].data == {"name": "delete_transaction", "result": result}


async def test_other_users_transaction_cannot_be_deleted_through_agent(session):
    ana = await make_user(session, "ana@example.com")
    beto = await make_user(session, "beto@example.com")
    ana_id, beto_id = ana.id, beto.id
    created = await tools.add_transaction(session, ana_id, EXPENSE_ARGS)
    chat = FakeChat(
        calls_response(tool_call("delete_transaction", {"transaction_id": created["id"]})),
        text_response("No encontré ese movimiento."),
    )
    await collect(chat, session, beto_id)
    assert json.loads(chat.calls[1][0][-1].content)["error"] == "not_found"
    assert (await tools.list_transactions(session, ana_id, {}))["count"] == 1


async def test_multiple_tool_calls_in_one_turn(session):
    user = await make_user(session)
    chat = FakeChat(
        calls_response(
            tool_call("add_transaction", EXPENSE_ARGS),
            tool_call("add_transaction", {**EXPENSE_ARGS, "concept": "Cena"}),
        ),
        text_response("Registré ambos gastos."),
    )
    events = await collect(chat, session, user.id)
    assert [event.type for event in events] == [
        "tool_call",
        "tool_result",
        "tool_call",
        "tool_result",
        "message",
    ]
    assert [event.data["result"]["concept"] for event in events if event.type == "tool_result"] == [
        "Almuerzo",
        "Cena",
    ]
    assert (await tools.list_transactions(session, user.id, {}))["count"] == 2
    assert [m.role for m in chat.calls[1][0][-3:]] == ["assistant", "tool", "tool"]


async def test_direct_answer_without_tools(session):
    user = await make_user(session)
    chat = FakeChat(text_response("¿De cuánto fue el gasto?"))
    events = await collect(chat, session, user.id)
    assert [event.type for event in events] == ["message"]


async def test_empty_model_response_raises_processing_error(session):
    user = await make_user(session)
    chat = FakeChat(calls_response())
    with pytest.raises(ProcessingError):
        await collect(chat, session, user.id)


async def test_tool_loop_is_bounded(session):
    user = await make_user(session)
    chat = FakeChat(default=calls_response(tool_call("get_balance", {})))
    with pytest.raises(ProcessingError):
        await collect(chat, session, user.id)
    assert len(chat.calls) == orchestrator.MAX_ITERATIONS


async def test_agent_creates_goal_and_registers_contribution_in_one_turn(session):
    user = await make_user(session)
    user_id = user.id
    chat = FakeChat(
        calls_response(
            tool_call("create_savings_goal", {"name": "Moto", "target_amount": 8000000})
        ),
        text_response("Creé tu meta Moto."),
    )
    await collect(chat, session, user_id, "Quiero ahorrar 8 millones para una moto")
    goal_id = json.loads(chat.calls[1][0][-1].content)["id"]

    chat = FakeChat(
        calls_response(
            tool_call("add_goal_contribution", {"goal_id": goal_id, "amount": 200000})
        ),
        text_response("Aporte registrado."),
    )
    events = await collect(chat, session, user_id, "Aporté 200 mil a la moto")
    assert events[-1].type == "message"
    result = json.loads(chat.calls[1][0][-1].content)
    assert result["progress"]["accumulated"] == "200000.00"
    assert (await tools.get_balance(session, user_id, {}))["total_expenses"] == "0.00"


INVOICE_DRAFT = {
    "merchant": "Éxito",
    "issued_on": "2026-11-05",
    "total": "9000",
    "category": "alimentacion",
    "items": [{"description": "Leche", "quantity": "2", "unit_price": "4500"}],
}


async def make_invoice_draft(session, user_id) -> str:
    from app.schemas.invoice import InvoiceDraft
    from app.services import invoice as invoice_service

    created = await invoice_service.create_draft(
        session, user_id, "f.png", InvoiceDraft.model_validate(INVOICE_DRAFT)
    )
    return str(created.id)


async def test_agent_reviews_corrects_and_confirms_invoice_across_turns(session):
    user = await make_user(session)
    user_id = user.id
    invoice_id = await make_invoice_draft(session, user_id)

    review = FakeChat(
        calls_response(tool_call("get_invoice", {"invoice_id": invoice_id})),
        text_response("Éxito, 2 x Leche, total 9.000. ¿Confirmas?"),
    )
    await collect(review, session, user_id, f"Subí una factura (id: {invoice_id})")
    assert json.loads(review.calls[1][0][-1].content)["status"] == "draft"
    assert (await tools.get_balance(session, user_id, {}))["total_expenses"] == "0.00"

    correct = FakeChat(
        calls_response(
            tool_call(
                "update_invoice_item",
                {"invoice_id": invoice_id, "position": 1, "unit_price": 5000},
            ),
            tool_call("update_invoice", {"invoice_id": invoice_id, "total": 10000}),
        ),
        text_response("Corregido. ¿Confirmas?"),
    )
    await collect(correct, session, user_id, "El precio de la leche es 5000")
    assert (await tools.get_balance(session, user_id, {}))["total_expenses"] == "0.00"

    confirm = FakeChat(
        calls_response(
            tool_call("confirm_invoice", {"invoice_id": invoice_id, "user_confirmed": True})
        ),
        text_response("Registré un gasto de 10.000."),
    )
    await collect(confirm, session, user_id, "Sí, confírmala")
    result = json.loads(confirm.calls[1][0][-1].content)
    assert result["status"] == "confirmed"
    balance = await tools.get_balance(session, user_id, {})
    assert balance["total_expenses"] == "10000.00"
    listed = await tools.list_transactions(session, user_id, {})
    assert listed["count"] == 1


async def test_agent_cannot_confirm_invoice_without_user_confirmation_flag(session):
    user = await make_user(session)
    user_id = user.id
    invoice_id = await make_invoice_draft(session, user_id)
    chat = FakeChat(
        calls_response(
            tool_call("confirm_invoice", {"invoice_id": invoice_id, "user_confirmed": False})
        ),
        text_response("¿Quieres que la guarde?"),
    )
    await collect(chat, session, user_id, "Subí una factura")
    assert json.loads(chat.calls[1][0][-1].content)["error"] == "invalid_arguments"
    assert (await tools.get_balance(session, user_id, {}))["total_expenses"] == "0.00"


async def test_incomplete_invoice_error_reaches_the_model(session):
    from app.schemas.invoice import InvoiceDraft
    from app.services import invoice as invoice_service

    user = await make_user(session)
    user_id = user.id
    created = await invoice_service.create_draft(
        session, user_id, None, InvoiceDraft(merchant="Tienda", total="100")
    )
    chat = FakeChat(
        calls_response(
            tool_call("confirm_invoice", {"invoice_id": str(created.id), "user_confirmed": True})
        ),
        text_response("Me falta la fecha y la categoría."),
    )
    await collect(chat, session, user_id, "Confírmala")
    result = json.loads(chat.calls[1][0][-1].content)
    assert result["error"] == "incomplete_information"
    assert "fecha" in result["message"]
    assert (await tools.get_balance(session, user_id, {}))["total_expenses"] == "0.00"


async def test_agent_answers_with_category_data_and_report_link(session):
    user = await make_user(session)
    user_id = user.id
    await tools.add_transaction(session, user_id, EXPENSE_ARGS)
    await tools.add_transaction(
        session,
        user_id,
        {**EXPENSE_ARGS, "amount": 5000, "concept": "Bus", "category": "transporte"},
    )
    chat = FakeChat(
        calls_response(
            tool_call("get_expenses_by_category", {}),
            tool_call("get_monthly_report", {"month": "2026-11"}),
        ),
        text_response("Gastas más en alimentación. Tu informe está listo."),
    )
    events = await collect(chat, session, user_id, "¿En qué gasto más? Dame el informe de noviembre")
    assert [e.type for e in events] == [
        "tool_call",
        "tool_result",
        "tool_call",
        "tool_result",
        "message",
    ]
    breakdown = events[1].data["result"]
    report = events[3].data["result"]
    assert breakdown["top_category"] == "alimentacion"
    assert report["pdf_url"] == "/reports/monthly/2026-11/pdf"
    assert report["total_expenses"] == "30000.00"


async def test_agent_creates_exact_day_reminder_and_lists_and_cancels_it(session):
    user = await make_user(session)
    user_id = user.id
    chat = FakeChat(
        calls_response(
            tool_call(
                "create_reminder",
                {
                    "concept": "Pagar arriendo",
                    "remind_on": "2030-03-01",
                    "remind_at": "09:00",
                    "frequency": "monthly",
                    "month_days": [15],
                },
            )
        ),
        text_response("Listo, te recordaré el 15 de cada mes a las 9:00."),
    )
    await collect(chat, session, user_id, "Recuérdame pagar el arriendo el 15 de cada mes a las 9am")
    created = json.loads(chat.calls[1][0][-1].content)
    assert created["month_days"] == [15]
    assert created["next_run_local"] == "2030-03-15T09:00:00"
    assert created["notifications_enabled"] is False

    listing = FakeChat(
        calls_response(tool_call("list_reminders", {})), text_response("Tienes 1 recordatorio.")
    )
    await collect(listing, session, user_id, "¿Qué recordatorios tengo?")
    assert json.loads(listing.calls[1][0][-1].content)["count"] == 1

    cancel = FakeChat(
        calls_response(tool_call("cancel_reminder", {"reminder_id": created["id"]})),
        text_response("Cancelado."),
    )
    await collect(cancel, session, user_id, "Cancela ese recordatorio")
    assert json.loads(cancel.calls[1][0][-1].content)["status"] == "cancelled"
    relist = FakeChat(calls_response(tool_call("list_reminders", {})), text_response("Ninguno."))
    await collect(relist, session, user_id, "¿Y ahora?")
    assert json.loads(relist.calls[1][0][-1].content)["count"] == 0


async def test_invalid_reminder_arguments_reach_the_model_as_errors(session):
    user = await make_user(session)
    chat = FakeChat(
        calls_response(
            tool_call(
                "create_reminder",
                {"concept": "X", "remind_on": "2030-03-01", "remind_at": "09:00", "frequency": "monthly", "month_days": [40]},
            )
        ),
        text_response("Ese día del mes no existe."),
    )
    await collect(chat, session, user.id, "Recuérdame el día 40")
    result = json.loads(chat.calls[1][0][-1].content)
    assert result["error"] == "invalid_arguments"
    assert result["details"][0]["field"] == "month_days"
