import uuid
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.agent.llm_client import ToolSpec
from app.models.transaction import ExpenseCategory, TransactionType
from app.tools import budgets, goals, invoices, reminders, reports, transactions

ToolHandler = Callable[[AsyncSession, uuid.UUID, dict[str, Any]], Awaitable[dict[str, Any]]]


@dataclass(frozen=True)
class ToolDefinition:
    name: str
    description: str
    parameters: dict[str, Any]
    handler: ToolHandler


CATEGORIES = [category.value for category in ExpenseCategory]
TYPES = [type_.value for type_ in TransactionType]

DATE_FIELD = {"type": "string", "description": "Fecha en formato YYYY-MM-DD."}
TYPE_FIELD = {"type": "string", "enum": TYPES, "description": "income = ingreso, expense = gasto."}
AMOUNT_FIELD = {
    "type": "number",
    "description": "Valor mayor que cero, con máximo dos decimales.",
}
CONCEPT_FIELD = {"type": "string", "description": "Concepto o descripción breve del movimiento."}
CATEGORY_FIELD = {
    "type": "string",
    "enum": CATEGORIES,
    "description": "Categoría del gasto. Obligatoria para gastos; no aplica a ingresos.",
}
TRANSACTION_ID_FIELD = {"type": "string", "description": "Id (UUID) del movimiento."}
REMINDER_ID_FIELD = {"type": "string", "description": "Id (UUID) del recordatorio."}
REMINDER_CONCEPT_FIELD = {"type": "string", "description": "Texto del recordatorio."}
REMIND_ON_FIELD = {
    "type": "string",
    "description": (
        "Fecha YYYY-MM-DD de la ejecución, o desde la cual empieza a repetirse si es recurrente."
    ),
}
REMIND_AT_FIELD = {
    "type": "string",
    "description": "Hora local del usuario en formato 24 h HH:MM.",
}
FREQUENCY_FIELD = {
    "type": "string",
    "enum": ["once", "daily", "weekly", "biweekly", "monthly", "custom"],
    "description": (
        "once = una sola vez; daily = todos los días; weekly = cada semana; "
        "biweekly = quincenal, los días 15 y último de cada mes; monthly = cada mes; "
        "custom = cada N días, semanas o meses."
    ),
}
INTERVAL_COUNT_FIELD = {
    "type": "integer",
    "minimum": 1,
    "description": "Cada cuántas unidades se repite. Solo con frequency custom.",
}
INTERVAL_UNIT_FIELD = {
    "type": "string",
    "enum": ["days", "weeks", "months"],
    "description": "Unidad del intervalo. Solo con frequency custom.",
}
MONTH_DAYS_FIELD = {
    "type": "array",
    "items": {"type": "integer", "minimum": -1, "maximum": 31},
    "description": (
        "Días del mes en que se repite, por ejemplo [15] o [5, 20]. Usa -1 para el último día "
        "del mes. Si el mes no tiene ese día, se usa su último día. Solo con monthly o custom "
        "en meses."
    ),
}
WEEKDAYS_FIELD = {
    "type": "array",
    "items": {
        "type": "string",
        "enum": ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"],
    },
    "description": "Días de la semana en que se repite. Solo con weekly o custom en semanas.",
}
INVOICE_ID_FIELD = {"type": "string", "description": "Id (UUID) de la factura."}
ITEM_POSITION_FIELD = {
    "type": "integer",
    "minimum": 1,
    "description": "Posición del ítem en la factura, empezando en 1.",
}
ITEM_DESCRIPTION_FIELD = {"type": "string", "description": "Producto o servicio."}
ITEM_QUANTITY_FIELD = {
    "type": "number",
    "description": "Cantidad, mayor que cero, con máximo tres decimales.",
}
ITEM_UNIT_PRICE_FIELD = {
    "type": "number",
    "description": "Precio unitario, cero o mayor, con máximo dos decimales.",
}
GOAL_ID_FIELD = {"type": "string", "description": "Id (UUID) de la meta de ahorro."}
GOAL_NAME_FIELD = {"type": "string", "description": "Nombre de la meta de ahorro."}
GOAL_TARGET_FIELD = {
    "type": "number",
    "description": "Monto objetivo de la meta, mayor que cero, con máximo dos decimales.",
}
GOAL_DEADLINE_FIELD = {
    "type": "string",
    "description": "Fecha límite opcional en formato YYYY-MM-DD. En una modificación, null la quita.",
}

_DEFINITIONS = (
    ToolDefinition(
        name="add_transaction",
        description=(
            "Registra un ingreso o un gasto del usuario. Si es un gasto sin categoría, "
            "se deduce del concepto; si no se indica fecha, se usa la fecha actual."
        ),
        parameters={
            "type": "object",
            "properties": {
                "type": TYPE_FIELD,
                "amount": AMOUNT_FIELD,
                "concept": CONCEPT_FIELD,
                "occurred_on": DATE_FIELD,
                "category": CATEGORY_FIELD,
            },
            "required": ["type", "amount", "concept", "occurred_on"],
        },
        handler=transactions.add_transaction,
    ),
    ToolDefinition(
        name="update_transaction",
        description="Modifica campos de un movimiento existente. Envía solo los campos que cambian.",
        parameters={
            "type": "object",
            "properties": {
                "transaction_id": TRANSACTION_ID_FIELD,
                "type": TYPE_FIELD,
                "amount": AMOUNT_FIELD,
                "concept": CONCEPT_FIELD,
                "occurred_on": DATE_FIELD,
                "category": CATEGORY_FIELD,
            },
            "required": ["transaction_id"],
        },
        handler=transactions.update_transaction,
    ),
    ToolDefinition(
        name="delete_transaction",
        description="Elimina un movimiento existente.",
        parameters={
            "type": "object",
            "properties": {"transaction_id": TRANSACTION_ID_FIELD},
            "required": ["transaction_id"],
        },
        handler=transactions.delete_transaction,
    ),
    ToolDefinition(
        name="list_transactions",
        description=(
            "Consulta movimientos del usuario, del más reciente al más antiguo, con filtros "
            "opcionales. Devuelve count, total (suma de los resultados) y la lista de "
            "movimientos. Usa type 'expense' para listar los gastos cuando pregunte en qué "
            "ha gastado."
        ),
        parameters={
            "type": "object",
            "properties": {
                "start_date": DATE_FIELD,
                "end_date": DATE_FIELD,
                "type": TYPE_FIELD,
                "category": CATEGORY_FIELD,
                "limit": {
                    "type": "integer",
                    "minimum": 1,
                    "maximum": 100,
                    "description": "Cantidad máxima de movimientos (por defecto 20).",
                },
            },
        },
        handler=transactions.list_transactions,
    ),
    ToolDefinition(
        name="get_balance",
        description="Calcula ingresos, gastos y balance del usuario, opcionalmente en un periodo.",
        parameters={
            "type": "object",
            "properties": {"start_date": DATE_FIELD, "end_date": DATE_FIELD},
        },
        handler=transactions.get_balance,
    ),
    ToolDefinition(
        name="set_budget",
        description="Establece o actualiza el presupuesto mensual general del usuario.",
        parameters={
            "type": "object",
            "properties": {
                "amount": {
                    "type": "number",
                    "description": "Presupuesto mensual, mayor que cero, con máximo dos decimales.",
                }
            },
            "required": ["amount"],
        },
        handler=budgets.set_budget,
    ),
    ToolDefinition(
        name="get_budget_status",
        description=(
            "Muestra cuánto del presupuesto mensual se ha usado, el porcentaje y lo que queda "
            "disponible. Sin month usa el mes actual."
        ),
        parameters={
            "type": "object",
            "properties": {
                "month": {
                    "type": "string",
                    "description": "Mes a consultar en formato YYYY-MM. Opcional.",
                }
            },
        },
        handler=budgets.get_budget_status,
    ),
    ToolDefinition(
        name="create_savings_goal",
        description="Crea una meta de ahorro con monto objetivo y fecha límite opcional.",
        parameters={
            "type": "object",
            "properties": {
                "name": GOAL_NAME_FIELD,
                "target_amount": GOAL_TARGET_FIELD,
                "deadline": GOAL_DEADLINE_FIELD,
            },
            "required": ["name", "target_amount"],
        },
        handler=goals.create_savings_goal,
    ),
    ToolDefinition(
        name="update_savings_goal",
        description="Modifica una meta de ahorro. Envía solo los campos que cambian.",
        parameters={
            "type": "object",
            "properties": {
                "goal_id": GOAL_ID_FIELD,
                "name": GOAL_NAME_FIELD,
                "target_amount": GOAL_TARGET_FIELD,
                "deadline": GOAL_DEADLINE_FIELD,
            },
            "required": ["goal_id"],
        },
        handler=goals.update_savings_goal,
    ),
    ToolDefinition(
        name="delete_savings_goal",
        description="Elimina una meta de ahorro junto con sus aportes.",
        parameters={
            "type": "object",
            "properties": {"goal_id": GOAL_ID_FIELD},
            "required": ["goal_id"],
        },
        handler=goals.delete_savings_goal,
    ),
    ToolDefinition(
        name="list_savings_goals",
        description=(
            "Lista las metas de ahorro con su progreso: ahorrado, pendiente, porcentaje, días "
            "restantes y aporte mensual sugerido."
        ),
        parameters={"type": "object", "properties": {}},
        handler=goals.list_savings_goals,
    ),
    ToolDefinition(
        name="add_goal_contribution",
        description=(
            "Registra un aporte a una meta de ahorro. No es un gasto y no afecta el balance."
        ),
        parameters={
            "type": "object",
            "properties": {
                "goal_id": GOAL_ID_FIELD,
                "amount": {
                    "type": "number",
                    "description": "Valor del aporte, mayor que cero, con máximo dos decimales.",
                },
                "contributed_on": {
                    "type": "string",
                    "description": "Fecha del aporte YYYY-MM-DD. Opcional; por defecto hoy.",
                },
            },
            "required": ["goal_id", "amount"],
        },
        handler=goals.add_goal_contribution,
    ),
    ToolDefinition(
        name="get_expenses_by_category",
        description=(
            "Agrupa los gastos por categoría, de mayor a menor, con total y porcentaje de cada una "
            "e indica la categoría con más gasto. Sin fechas considera todos los movimientos. "
            "Para enumerar gastos individuales usa list_transactions con type 'expense'."
        ),
        parameters={
            "type": "object",
            "properties": {"start_date": DATE_FIELD, "end_date": DATE_FIELD},
        },
        handler=reports.get_expenses_by_category,
    ),
    ToolDefinition(
        name="get_monthly_report",
        description=(
            "Informe financiero mensual: ingresos, gastos, balance, distribución de gastos por "
            "categoría y la lista de gastos individuales del mes. Incluye pdf_url, la ruta para "
            "descargar el informe en PDF. Sin month usa el mes actual."
        ),
        parameters={
            "type": "object",
            "properties": {
                "month": {
                    "type": "string",
                    "description": "Mes del informe en formato YYYY-MM. Opcional.",
                }
            },
        },
        handler=reports.get_monthly_report,
    ),
    ToolDefinition(
        name="create_reminder",
        description=(
            "Crea un recordatorio de una sola vez o recurrente que se enviará como notificación "
            "push. Devuelve notifications_enabled=false si el usuario aún no activó "
            "notificaciones en ningún dispositivo."
        ),
        parameters={
            "type": "object",
            "properties": {
                "concept": REMINDER_CONCEPT_FIELD,
                "remind_on": REMIND_ON_FIELD,
                "remind_at": REMIND_AT_FIELD,
                "frequency": FREQUENCY_FIELD,
                "interval_count": INTERVAL_COUNT_FIELD,
                "interval_unit": INTERVAL_UNIT_FIELD,
                "month_days": MONTH_DAYS_FIELD,
                "weekdays": WEEKDAYS_FIELD,
            },
            "required": ["concept", "remind_on", "remind_at"],
        },
        handler=reminders.create_reminder,
    ),
    ToolDefinition(
        name="update_reminder",
        description=(
            "Modifica un recordatorio activo. Envía solo los campos que cambian. Si cambias la "
            "frecuencia, reenvía también los días o el intervalo que apliquen."
        ),
        parameters={
            "type": "object",
            "properties": {
                "reminder_id": REMINDER_ID_FIELD,
                "concept": REMINDER_CONCEPT_FIELD,
                "remind_on": REMIND_ON_FIELD,
                "remind_at": REMIND_AT_FIELD,
                "frequency": FREQUENCY_FIELD,
                "interval_count": INTERVAL_COUNT_FIELD,
                "interval_unit": INTERVAL_UNIT_FIELD,
                "month_days": MONTH_DAYS_FIELD,
                "weekdays": WEEKDAYS_FIELD,
            },
            "required": ["reminder_id"],
        },
        handler=reminders.update_reminder,
    ),
    ToolDefinition(
        name="cancel_reminder",
        description="Cancela un recordatorio activo sin afectar los demás.",
        parameters={
            "type": "object",
            "properties": {"reminder_id": REMINDER_ID_FIELD},
            "required": ["reminder_id"],
        },
        handler=reminders.cancel_reminder,
    ),
    ToolDefinition(
        name="list_reminders",
        description=(
            "Lista los recordatorios pendientes (activos), del más próximo al más lejano, con su "
            "próxima ejecución en hora local."
        ),
        parameters={"type": "object", "properties": {}},
        handler=reminders.list_reminders,
    ),
    ToolDefinition(
        name="get_invoice",
        description=(
            "Consulta una factura subida por el usuario: establecimiento, fecha, número, ítems, "
            "total, categoría y datos faltantes. Úsala para presentar el borrador a revisión."
        ),
        parameters={
            "type": "object",
            "properties": {"invoice_id": INVOICE_ID_FIELD},
            "required": ["invoice_id"],
        },
        handler=invoices.get_invoice,
    ),
    ToolDefinition(
        name="list_draft_invoices",
        description="Lista las facturas en borrador pendientes de confirmar, la más reciente primero.",
        parameters={"type": "object", "properties": {}},
        handler=invoices.list_draft_invoices,
    ),
    ToolDefinition(
        name="update_invoice",
        description=(
            "Corrige datos generales de una factura en borrador. Envía solo los campos que cambian."
        ),
        parameters={
            "type": "object",
            "properties": {
                "invoice_id": INVOICE_ID_FIELD,
                "merchant": {"type": "string", "description": "Establecimiento o comercio."},
                "invoice_number": {
                    "type": "string",
                    "description": "Número de factura. null lo quita.",
                },
                "issued_on": DATE_FIELD,
                "total": {
                    "type": "number",
                    "description": "Total de la factura, mayor que cero, con máximo dos decimales.",
                },
                "category": CATEGORY_FIELD,
            },
            "required": ["invoice_id"],
        },
        handler=invoices.update_invoice,
    ),
    ToolDefinition(
        name="update_invoice_item",
        description="Corrige un ítem de una factura en borrador. Envía solo los campos que cambian.",
        parameters={
            "type": "object",
            "properties": {
                "invoice_id": INVOICE_ID_FIELD,
                "position": ITEM_POSITION_FIELD,
                "description": ITEM_DESCRIPTION_FIELD,
                "quantity": ITEM_QUANTITY_FIELD,
                "unit_price": ITEM_UNIT_PRICE_FIELD,
            },
            "required": ["invoice_id", "position"],
        },
        handler=invoices.update_invoice_item,
    ),
    ToolDefinition(
        name="add_invoice_item",
        description="Agrega un ítem al final de una factura en borrador.",
        parameters={
            "type": "object",
            "properties": {
                "invoice_id": INVOICE_ID_FIELD,
                "description": ITEM_DESCRIPTION_FIELD,
                "quantity": ITEM_QUANTITY_FIELD,
                "unit_price": ITEM_UNIT_PRICE_FIELD,
            },
            "required": ["invoice_id", "description", "unit_price"],
        },
        handler=invoices.add_invoice_item,
    ),
    ToolDefinition(
        name="delete_invoice_item",
        description="Elimina un ítem de una factura en borrador.",
        parameters={
            "type": "object",
            "properties": {"invoice_id": INVOICE_ID_FIELD, "position": ITEM_POSITION_FIELD},
            "required": ["invoice_id", "position"],
        },
        handler=invoices.delete_invoice_item,
    ),
    ToolDefinition(
        name="confirm_invoice",
        description=(
            "Confirma una factura en borrador: registra un gasto por el total de la factura y "
            "guarda sus ítems. Solo úsala después de que el usuario haya aprobado explícitamente "
            "los datos revisados."
        ),
        parameters={
            "type": "object",
            "properties": {
                "invoice_id": INVOICE_ID_FIELD,
                "user_confirmed": {
                    "type": "boolean",
                    "description": (
                        "true únicamente si el usuario confirmó de forma explícita, en su último "
                        "mensaje, que quiere guardar la factura."
                    ),
                },
            },
            "required": ["invoice_id", "user_confirmed"],
        },
        handler=invoices.confirm_invoice,
    ),
    ToolDefinition(
        name="discard_invoice",
        description="Descarta una factura en borrador sin registrar ningún gasto.",
        parameters={
            "type": "object",
            "properties": {"invoice_id": INVOICE_ID_FIELD},
            "required": ["invoice_id"],
        },
        handler=invoices.discard_invoice,
    ),
)

TOOLS: dict[str, ToolDefinition] = {definition.name: definition for definition in _DEFINITIONS}


def get_tool(name: str) -> ToolDefinition | None:
    return TOOLS.get(name)


def get_tool_specs() -> list[ToolSpec]:
    return [
        ToolSpec(name=tool.name, description=tool.description, parameters=tool.parameters)
        for tool in TOOLS.values()
    ]
