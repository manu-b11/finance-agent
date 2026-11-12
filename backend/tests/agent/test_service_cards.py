from app.agent.service import _cards_from_tool_result


def test_invoice_tool_result_becomes_reference_card():
    cards = _cards_from_tool_result("confirm_invoice", {"id": "inv-1", "status": "confirmed"})
    assert len(cards) == 1
    assert cards[0].type == "invoice"
    assert cards[0].data == {"invoice_id": "inv-1"}


def test_invoice_error_does_not_produce_a_card():
    assert _cards_from_tool_result("confirm_invoice", {"error": "not_found"}) == []


def test_discard_invoice_reads_the_nested_invoice():
    cards = _cards_from_tool_result(
        "discard_invoice", {"discarded": True, "invoice": {"id": "inv-2"}}
    )
    assert cards[0].data == {"invoice_id": "inv-2"}


def test_list_draft_invoices_creates_one_card_per_invoice():
    cards = _cards_from_tool_result(
        "list_draft_invoices",
        {"count": 2, "invoices": [{"id": "a"}, {"id": "b"}, {"sin_id": True}]},
    )
    assert [card.data["invoice_id"] for card in cards] == ["a", "b"]


def test_unrelated_tool_result_is_ignored():
    assert _cards_from_tool_result("get_budget_status", {"amount": "10.00"}) == []


def test_query_tools_do_not_duplicate_data_as_cards():
    # Esta información ya está en las páginas de balance, movimientos,
    # categorías e informes; en el chat se responde con texto.
    assert _cards_from_tool_result("get_balance", {"balance": "60.00"}) == []
    assert _cards_from_tool_result("list_transactions", {"count": 1, "transactions": []}) == []
    assert _cards_from_tool_result(
        "get_expenses_by_category", {"total_expenses": "40.00", "categories": []}
    ) == []
    assert _cards_from_tool_result(
        "get_monthly_report", {"month": "2026-11", "pdf_url": "/reports/monthly/2026-11/pdf"}
    ) == []


def test_transaction_writes_are_confirmed_with_text():
    assert (
        _cards_from_tool_result(
            "add_transaction", {"id": "tx-1", "concept": "Almuerzo", "amount": "25000.00"}
        )
        == []
    )
    assert (
        _cards_from_tool_result(
            "delete_transaction", {"deleted": True, "transaction": {"id": "tx-2"}}
        )
        == []
    )
