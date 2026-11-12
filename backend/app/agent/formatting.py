from datetime import date, timedelta
from decimal import Decimal, InvalidOperation
from typing import Any

from app.core.categories import category_label
from app.core.clock import month_bounds
from app.core.money import format_cop

MAX_LISTED_EXPENSES = 20


def _parse_date(value: Any) -> date | None:
    if isinstance(value, date):
        return value
    if not isinstance(value, str) or not value:
        return None
    try:
        return date.fromisoformat(value)
    except ValueError:
        return None


def _amount(item: dict[str, Any]) -> Decimal:
    try:
        return Decimal(str(item.get("amount") or 0))
    except (InvalidOperation, ValueError):
        return Decimal("0")


def _period_phrases(filters: dict[str, Any], today: date) -> tuple[str, str]:
    start = _parse_date(filters.get("start_date"))
    end = _parse_date(filters.get("end_date"))
    if start == today and end == today:
        return "Hoy has gastado", "Hoy no tienes gastos registrados."
    yesterday = today - timedelta(days=1)
    if start == yesterday and end == yesterday:
        return "Ayer gastaste", "Ayer no registraste gastos."
    month_start, month_end = month_bounds(today.year, today.month)
    if start == month_start and end == month_end:
        return "Este mes has gastado", "Este mes no tienes gastos registrados."
    return "Has gastado", "No tienes gastos registrados."


def looks_like_expense_list(text: str) -> bool:
    """Detecta si la respuesta del modelo intentó enumerar gastos."""
    if "|" in text and "---" in text:
        return True
    if text.count("—") >= 2 or text.count("–") >= 2:
        return True
    return sum(1 for line in text.splitlines() if "$" in line) >= 2


NON_LISTING_HINTS = ("cuánto", "cuanto")
ACTION_HINTS = (
    "registra",
    "agrega",
    "añade",
    "crea",
    "elimina",
    "borra",
    "cambia",
    "modifica",
    "actualiza",
    "corrige",
    "guarda",
)


def is_action_question(text: str) -> bool:
    lowered = text.lower()
    return any(hint in lowered for hint in ACTION_HINTS)


def is_listing_question(text: str) -> bool:
    """¿El usuario pidió ver una lista de gastos o movimientos?"""
    lowered = text.lower()
    if any(hint in lowered for hint in NON_LISTING_HINTS):
        return False
    if is_action_question(lowered):
        return False
    return "gast" in lowered or "compr" in lowered or "movimiento" in lowered


def is_expense_list_result(result: dict[str, Any]) -> bool:
    filters = result.get("filters") or {}
    if filters.get("type") == "expense":
        return True
    if filters.get("type"):
        return False
    items = [item for item in (result.get("transactions") or []) if isinstance(item, dict)]
    return bool(items) and all(item.get("type") == "expense" for item in items)


def format_expense_list(result: dict[str, Any], today: date) -> str:
    """Arma la respuesta de gastos agrupada por categoría.

    Se genera desde el resultado real de la herramienta para que el formato no
    dependa de que el modelo siga las instrucciones al pie de la letra.
    """
    filters = result.get("filters") or {}
    transactions = [
        item for item in (result.get("transactions") or []) if isinstance(item, dict)
    ]
    has_phrase, empty_phrase = _period_phrases(filters, today)
    if not transactions:
        return empty_phrase

    try:
        total = Decimal(str(result.get("total") or 0))
    except (InvalidOperation, ValueError):
        total = sum((_amount(item) for item in transactions), Decimal("0"))

    shown = transactions[:MAX_LISTED_EXPENSES]
    groups: dict[str, list[dict[str, Any]]] = {}
    for item in shown:
        groups.setdefault(item.get("category") or "sin_categoria", []).append(item)

    lines = [f"{has_phrase} {format_cop(total)} en total.", ""]
    for category, items in groups.items():
        subtotal = sum((_amount(item) for item in items), Decimal("0"))
        lines.append(f"{category_label(category)}: {format_cop(subtotal)}")
        lines.extend(
            f"- {item.get('concept') or 'Gasto'}: {format_cop(_amount(item))}"
            for item in items
        )
        lines.append("")

    total_count = int(result.get("total_count") or len(transactions))
    if total_count > len(shown):
        lines.append(f"Mostrando los {len(shown)} gastos más recientes de {total_count}.")

    return "\n".join(lines).strip()
