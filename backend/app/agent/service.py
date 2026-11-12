import uuid
from collections.abc import AsyncIterator

from sqlalchemy.ext.asyncio import AsyncSession

from app.agent import orchestrator
from app.agent.formatting import (
    format_expense_list,
    is_action_question,
    is_expense_list_result,
    is_listing_question,
    looks_like_expense_list,
)
from app.agent.llm_client import ChatFn, Message
from app.agent.orchestrator import AgentEvent
from app.agent.prompts import build_demo_prompt, build_system_prompt
from app.core.clock import local_today
from app.core.errors import ProcessingError
from app.models.user import User
from app.schemas.chat import ChatCard
from app.services import chat_message as chat_message_service
from app.services import conversation as conversation_service

DEMO_HISTORY_LIMIT = 8

# Herramientas cuyo resultado es (o contiene) una factura.
INVOICE_CARD_TOOLS = {
    "get_invoice",
    "confirm_invoice",
    "update_invoice",
    "update_invoice_item",
    "add_invoice_item",
    "delete_invoice_item",
    "discard_invoice",
}


def _card_key(card: ChatCard) -> str:
    if card.type == "invoice":
        return f"invoice:{card.data.get('invoice_id')}"
    return card.type


def _changes_data(name: str) -> bool:
    return name.startswith(
        ("add_", "update_", "delete_", "set_", "create_", "confirm_", "cancel_", "discard_")
    )


def _cards_from_tool_result(name: str, result: dict) -> list[ChatCard]:
    """Traduce resultados de herramientas a tarjetas del chat.

    Solo las facturas se guardan como referencia (id) para refrescarlas al abrir
    la conversación. El resto de consultas se responden con texto: la misma
    información ya está en las páginas de balance, movimientos, categorías e
    informes, así que no se duplica con tarjetas.
    """
    if not isinstance(result, dict) or result.get("error"):
        return []

    if name == "list_draft_invoices":
        invoices = result.get("invoices") or []
        return [
            ChatCard(type="invoice", data={"invoice_id": invoice["id"]})
            for invoice in invoices
            if invoice.get("id")
        ]

    invoice = result.get("invoice") if name == "discard_invoice" else result
    if name in INVOICE_CARD_TOOLS and isinstance(invoice, dict) and invoice.get("id"):
        return [ChatCard(type="invoice", data={"invoice_id": invoice["id"]})]
    return []


async def stream_demo_reply(
    chat: ChatFn,
    text: str,
    history: list[Message],
    timezone: str,
) -> AsyncIterator[AgentEvent]:
    """Respuesta de la demo pública: sin herramientas y sin datos del usuario."""
    messages = [
        Message(role="system", content=build_demo_prompt(local_today(timezone), timezone)),
        *history[-DEMO_HISTORY_LIMIT:],
        Message(role="user", content=text),
    ]
    response = await chat(messages, [])
    if not response.text:
        raise ProcessingError("La IA no pudo generar una respuesta.")
    yield AgentEvent("message", {"text": response.text})


async def stream_reply(
    session: AsyncSession,
    chat: ChatFn,
    user: User,
    text: str,
    conversation_id: uuid.UUID | None = None,
) -> AsyncIterator[AgentEvent]:
    user_id = user.id
    timezone = user.timezone
    conversation = None
    if conversation_id is not None:
        conversation = await conversation_service.get_conversation(
            session, user_id, conversation_id
        )
    else:
        # Compatibilidad: sin conversation_id se continúa la conversación más reciente.
        conversation = await conversation_service.get_latest_conversation(session, user_id)
    history = (
        await chat_message_service.get_recent_messages(
            session, user_id, conversation_id=conversation.id
        )
        if conversation is not None
        else []
    )
    messages = [
        Message(role="system", content=build_system_prompt(local_today(timezone), timezone)),
        *(Message(role=item.role, content=item.content) for item in history),
        Message(role="user", content=text),
    ]
    cards_by_key: dict[str, ChatCard] = {}
    expense_list_result: dict = {}
    async for event in orchestrator.run(chat, session, user_id, messages):
        if event.type == "tool_result":
            name = event.data.get("name", "")
            result = event.data.get("result")
            if name == "list_transactions" and is_expense_list_result(
                result if isinstance(result, dict) else {}
            ):
                expense_list_result = result
            elif _changes_data(name):
                # Una consulta previa para modificar o eliminar no debe reemplazar
                # la confirmación final por una lista.
                expense_list_result = {}
            for card in _cards_from_tool_result(name, result):
                cards_by_key[_card_key(card)] = card
        if event.type == "message":
            message_text = event.data["text"]
            # La lista de gastos se arma con los datos reales de la herramienta:
            # así el formato agrupado por categoría es siempre el mismo.
            if expense_list_result and (
                is_listing_question(text)
                or not expense_list_result.get("transactions")
                or (
                    not is_action_question(text)
                    and looks_like_expense_list(message_text)
                )
            ):
                message_text = format_expense_list(
                    expense_list_result, local_today(timezone)
                )
                event = AgentEvent("message", {**event.data, "text": message_text})
            cards = list(cards_by_key.values())
            created = None
            if conversation is None:
                conversation = await conversation_service.create_conversation(
                    session, user_id, conversation_service.title_from_text(text)
                )
                created = conversation
            await chat_message_service.add_exchange(
                session,
                user_id,
                text,
                message_text,
                conversation_id=conversation.id,
                cards=cards,
            )
            if created is not None:
                yield AgentEvent(
                    "conversation", conversation_service.event_payload(created)
                )
        yield event
