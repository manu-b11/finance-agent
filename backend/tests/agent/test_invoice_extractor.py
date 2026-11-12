import json
from decimal import Decimal

import pytest

from app.agent import invoice_extractor
from app.core.errors import IncompleteInformationError, ProcessingError
from app.core.media import ImagePart
from tests.agent.fakes import FakeChat, text_response

FULL = {
    "readable": True,
    "merchant": "Supermercado Éxito",
    "invoice_number": "FE-1023",
    "date": "2026-11-05",
    "items": [
        {"description": "Leche", "quantity": 2, "unit_price": 4500},
        {"description": "Pan", "quantity": 1, "unit_price": 3200.5},
    ],
    "total": 12200.5,
    "category": "alimentacion",
}


def parse(payload) -> object:
    text = payload if isinstance(payload, str) else json.dumps(payload)
    return invoice_extractor.parse_extraction(text)


def test_full_extraction():
    draft = parse(FULL)
    assert draft.merchant == "Supermercado Éxito"
    assert draft.invoice_number == "FE-1023"
    assert draft.issued_on.isoformat() == "2026-11-05"
    assert draft.total == Decimal("12200.50")
    assert draft.category.value == "alimentacion"
    assert [(i.description, i.quantity, i.unit_price) for i in draft.items] == [
        ("Leche", Decimal("2.000"), Decimal("4500.00")),
        ("Pan", Decimal("1.000"), Decimal("3200.50")),
    ]


def test_json_in_code_fence_and_surrounding_text_is_accepted():
    text = "Aquí está:\n```json\n" + json.dumps(FULL) + "\n```"
    assert parse(text).merchant == "Supermercado Éxito"


def test_missing_fields_stay_none_and_nothing_is_invented():
    draft = parse({"readable": True, "merchant": "Tienda", "items": [], "total": None})
    assert draft.merchant == "Tienda"
    assert draft.total is None
    assert draft.issued_on is None
    assert draft.category is None
    assert draft.items == []


def test_total_is_not_inferred_from_items():
    draft = parse({"merchant": "X", "items": [{"description": "A", "quantity": 2, "unit_price": 10}]})
    assert draft.total is None


def test_unknown_category_and_bad_date_become_none():
    draft = parse({"merchant": "X", "date": "5 de noviembre", "category": "lujos", "total": 10})
    assert draft.issued_on is None
    assert draft.category is None


def test_item_price_can_be_derived_from_line_total():
    draft = parse({"merchant": "X", "items": [{"description": "Arroz", "quantity": 4, "line_total": 10000}]})
    assert draft.items[0].unit_price == Decimal("2500.00")


def test_unusable_items_are_skipped_and_quantity_defaults_to_one():
    draft = parse(
        {
            "merchant": "X",
            "items": [
                {"description": "", "unit_price": 5},
                {"description": "Sin precio"},
                {"description": "Agua", "unit_price": 1500, "quantity": 0},
                "basura",
            ],
        }
    )
    assert len(draft.items) == 1
    assert draft.items[0].quantity == Decimal("1.000")


@pytest.mark.parametrize(
    "value,expected",
    [
        ("12500", Decimal("12500")),
        ("$ 12.500", Decimal("12500")),
        ("1.234.567", Decimal("1234567")),
        ("1.234,56", Decimal("1234.56")),
        ("1,234.56", Decimal("1234.56")),
        ("12,5", Decimal("12.5")),
        (19.9, Decimal("19.9")),
        (7, Decimal("7")),
    ],
)
def test_money_parsing(value, expected):
    assert invoice_extractor._money(value) == expected.quantize(Decimal("0.01"))


@pytest.mark.parametrize(
    "value", [None, True, "abc", "", [], {}, float("inf"), float("nan"), "9" * 20]
)
def test_money_parsing_rejects_garbage(value):
    assert invoice_extractor._money(value) is None


def test_quantity_with_dot_keeps_decimals():
    draft = parse({"merchant": "X", "items": [{"description": "Carne", "quantity": "1.500", "unit_price": 20000}]})
    assert draft.items[0].quantity == Decimal("1.500")


def test_zero_or_negative_total_is_discarded():
    assert parse({"merchant": "X", "total": 0}).total is None
    assert parse({"merchant": "X", "total": -5}).total is None


def test_not_readable_raises_incomplete_information():
    with pytest.raises(IncompleteInformationError):
        parse({"readable": False})


def test_empty_extraction_raises_incomplete_information():
    with pytest.raises(IncompleteInformationError):
        parse({"readable": True, "merchant": None, "items": [], "total": None, "date": None})


@pytest.mark.parametrize("text", [None, "", "no es json", "{roto", "[1, 2]"])
def test_unparseable_response_raises_processing_error(text):
    with pytest.raises(ProcessingError):
        invoice_extractor.parse_extraction(text)


async def test_extract_invoice_sends_images_and_no_tools():
    chat = FakeChat(text_response(json.dumps(FULL)))
    image = ImagePart("image/jpeg", b"\xff\xd8\xff-fake")
    draft = await invoice_extractor.extract_invoice(chat, [image])
    assert draft.merchant == "Supermercado Éxito"
    messages, tools = chat.calls[0]
    assert tools == []
    assert messages[0].role == "system"
    assert messages[1].images == (image,)


def test_prompt_explains_colombian_thousands_separator():
    prompt = invoice_extractor.build_extraction_prompt()
    assert "20.500" in prompt and "20500" in prompt
    assert "1.234.567" in prompt and "1234567" in prompt
    assert "20.500,50" in prompt and "20500.50" in prompt
    assert "separador de miles" in prompt
