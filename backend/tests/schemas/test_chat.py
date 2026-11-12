from app.schemas.chat import ChatMessageRead


def test_null_cards_are_read_as_an_empty_list():
    message = ChatMessageRead.model_validate(
        {
            "id": 1,
            "conversation_id": "6f1c1f9c-7b1c-4b1c-8b1c-1b1c1b1c1b1c",
            "role": "assistant",
            "content": "Hola",
            "cards": None,
            "created_at": "2026-11-11T10:00:00Z",
        }
    )
    assert message.cards == []


def test_cards_keep_only_type_and_data():
    message = ChatMessageRead.model_validate(
        {
            "id": 2,
            "conversation_id": "6f1c1f9c-7b1c-4b1c-8b1c-1b1c1b1c1b1c",
            "role": "assistant",
            "content": "Listo",
            "cards": [{"type": "invoice", "data": {"invoice_id": "inv-1"}}],
            "created_at": "2026-11-11T10:00:00Z",
        }
    )
    assert message.cards[0].type == "invoice"
    assert message.cards[0].data == {"invoice_id": "inv-1"}
