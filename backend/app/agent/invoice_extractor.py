import json
import logging
import re
from datetime import date
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation
from typing import Any

from app.agent.llm_client import ChatFn, Message
from app.core.errors import IncompleteInformationError, ProcessingError
from app.core.media import ImagePart
from app.models.transaction import ExpenseCategory
from app.schemas.invoice import MAX_ITEMS, DraftItem, InvoiceDraft

logger = logging.getLogger(__name__)

CENTS = Decimal("0.01")
MILLIS = Decimal("0.001")
MAX_DIGITS_VALUE = Decimal("999999999999.99")

NOT_READABLE = (
    "No pude encontrar datos de factura en el archivo. "
    "Prueba con una imagen más nítida o con el documento completo."
)


def build_extraction_prompt() -> str:
    categories = ", ".join(category.value for category in ExpenseCategory)
    return f"""Eres un lector de facturas y recibos. Recibirás una o varias imágenes de una misma factura y debes extraer sus datos.

Responde únicamente con un objeto JSON, sin texto adicional ni bloques de código, con esta forma:
{{
  "readable": true,
  "merchant": "nombre del establecimiento o comercio, o null",
  "invoice_number": "número de factura, o null",
  "date": "fecha de emisión en formato YYYY-MM-DD, o null",
  "items": [
    {{"description": "producto o servicio", "quantity": 1, "unit_price": 0, "line_total": 0}}
  ],
  "total": 0,
  "category": "una de: {categories}, o null"
}}

Reglas:
- Usa null para todo dato que no aparezca o no sea legible. Nunca inventes ni estimes valores.
- Los montos y cantidades son números planos con punto decimal, sin símbolo de moneda ni separadores de miles.
- unit_price es el precio de una unidad. Si solo ves el valor de la línea, ponlo en line_total y deja unit_price en null.
- total es el valor total a pagar impreso en la factura. No lo calcules sumando ítems.
- Si la imagen no es una factura o no se puede leer, responde {{"readable": false}}."""


def _extract_json(text: str | None) -> dict[str, Any]:
    if not text:
        raise ProcessingError("No se pudo interpretar la factura. Intenta de nuevo.")
    cleaned = re.sub(r"```(?:json)?", "", text).strip()
    start, end = cleaned.find("{"), cleaned.rfind("}")
    if start == -1 or end <= start:
        raise ProcessingError("No se pudo interpretar la factura. Intenta de nuevo.")
    try:
        data = json.loads(cleaned[start : end + 1])
    except json.JSONDecodeError as exc:
        raise ProcessingError("No se pudo interpretar la factura. Intenta de nuevo.") from exc
    if not isinstance(data, dict):
        raise ProcessingError("No se pudo interpretar la factura. Intenta de nuevo.")
    return data


def to_decimal(value: Any, dot_is_thousands: bool = False) -> Decimal | None:
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        text = str(value)
    elif isinstance(value, str):
        text = re.sub(r"[^\d.,\-]", "", value)
    else:
        return None
    if not text:
        return None
    if dot_is_thousands and isinstance(value, str) and re.fullmatch(r"-?\d{1,3}(\.\d{3})+", text):
        text = text.replace(".", "")
    elif "," in text and "." in text:
        decimal_sep = "," if text.rfind(",") > text.rfind(".") else "."
        thousands_sep = "." if decimal_sep == "," else ","
        text = text.replace(thousands_sep, "").replace(decimal_sep, ".")
    elif "," in text:
        text = text.replace(",", ".")
    try:
        number = Decimal(text)
    except InvalidOperation:
        return None
    if not number.is_finite() or abs(number) > MAX_DIGITS_VALUE:
        return None
    return number


def _money(value: Any) -> Decimal | None:
    number = to_decimal(value, dot_is_thousands=True)
    return number.quantize(CENTS, rounding=ROUND_HALF_UP) if number is not None else None


def _text(value: Any, limit: int) -> str | None:
    if not isinstance(value, str):
        return None
    cleaned = value.strip()[:limit].strip()
    return cleaned or None


def _parse_date(value: Any) -> date | None:
    if not isinstance(value, str):
        return None
    try:
        return date.fromisoformat(value.strip()[:10])
    except ValueError:
        return None


def _parse_category(value: Any) -> ExpenseCategory | None:
    if not isinstance(value, str):
        return None
    try:
        return ExpenseCategory(value.strip().lower())
    except ValueError:
        return None


def _parse_item(raw: Any) -> DraftItem | None:
    if not isinstance(raw, dict):
        return None
    description = _text(raw.get("description"), 255)
    if description is None:
        return None
    quantity = to_decimal(raw.get("quantity"))
    quantity = quantity.quantize(MILLIS, rounding=ROUND_HALF_UP) if quantity else None
    if quantity is None or quantity <= 0:
        quantity = Decimal("1")
    unit_price = _money(raw.get("unit_price"))
    if unit_price is None:
        line_total = _money(raw.get("line_total"))
        if line_total is not None:
            unit_price = (line_total / quantity).quantize(CENTS, rounding=ROUND_HALF_UP)
    if unit_price is None or unit_price < 0:
        return None
    return DraftItem(description=description, quantity=quantity, unit_price=unit_price)


def parse_extraction(text: str | None) -> InvoiceDraft:
    data = _extract_json(text)
    if data.get("readable") is False:
        raise IncompleteInformationError(NOT_READABLE)
    raw_items = data.get("items")
    items = []
    if isinstance(raw_items, list):
        for raw in raw_items[:MAX_ITEMS]:
            item = _parse_item(raw)
            if item is not None:
                items.append(item)
    total = _money(data.get("total"))
    draft = InvoiceDraft(
        merchant=_text(data.get("merchant"), 255),
        invoice_number=_text(data.get("invoice_number"), 64),
        issued_on=_parse_date(data.get("date")),
        total=total if total is not None and total > 0 else None,
        category=_parse_category(data.get("category")),
        items=items,
    )
    if draft.merchant is None and draft.total is None and draft.issued_on is None and not items:
        raise IncompleteInformationError(NOT_READABLE)
    return draft


async def extract_invoice(chat: ChatFn, images: list[ImagePart]) -> InvoiceDraft:
    messages = [
        Message(role="system", content=build_extraction_prompt()),
        Message(
            role="user",
            content="Extrae los datos de esta factura.",
            images=tuple(images),
        ),
    ]
    response = await chat(messages, [])
    return parse_extraction(response.text)
