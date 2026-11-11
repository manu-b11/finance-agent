import uuid
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime
from decimal import ROUND_HALF_UP, Decimal
from typing import Any

from fastapi.concurrency import run_in_threadpool
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.errors import (
    ConflictError,
    IncompleteInformationError,
    InvalidFileError,
    NotFoundError,
)
from app.core.media import ImagePart
from app.models.invoice import Invoice, InvoiceItem, InvoiceStatus
from app.models.transaction import Transaction, TransactionType
from app.schemas.invoice import (
    DraftItem,
    InvoiceDraft,
    InvoiceHeaderUpdate,
    InvoiceItemRead,
    InvoiceRead,
    ItemUpdate,
)
from app.schemas.transaction import TransactionCreate
from app.services import invoice_file

CENTS = Decimal("0.01")
MILLIS = Decimal("0.001")
REQUIRED_FIELDS = ("merchant", "issued_on", "total", "category")
FIELD_LABELS = {
    "merchant": "establecimiento",
    "issued_on": "fecha",
    "total": "total",
    "category": "categoría",
}
DRAFT_LIST_LIMIT = 10
INVOICE_LIST_LIMIT = 50

InvoiceExtractor = Callable[[list[ImagePart]], Awaitable[InvoiceDraft]]


def _item_read(position: int, description: str, quantity: Decimal, unit_price: Decimal) -> InvoiceItemRead:
    return InvoiceItemRead(
        position=position,
        description=description,
        quantity=quantity.quantize(MILLIS),
        unit_price=unit_price.quantize(CENTS),
        line_total=(quantity * unit_price).quantize(CENTS, rounding=ROUND_HALF_UP),
    )


def _compose(
    invoice: Invoice,
    merchant: str | None,
    invoice_number: str | None,
    issued_on: Any,
    total: Decimal | None,
    category: Any,
    items: list[InvoiceItemRead],
    missing: list[str],
) -> InvoiceRead:
    items_total = sum((item.line_total for item in items), Decimal("0")).quantize(CENTS)
    total = Decimal(total).quantize(CENTS) if total is not None else None
    matches = None
    if total is not None and items:
        matches = total == items_total
    return InvoiceRead(
        id=invoice.id,
        status=InvoiceStatus(invoice.status),
        original_filename=invoice.original_filename,
        merchant=merchant,
        invoice_number=invoice_number,
        issued_on=issued_on,
        total=total,
        category=category,
        items=items,
        items_total=items_total,
        total_matches_items=matches,
        missing_fields=missing,
        transaction_id=invoice.transaction_id,
        created_at=invoice.created_at,
        confirmed_at=invoice.confirmed_at,
    )


def _read_draft(invoice: Invoice) -> InvoiceRead:
    draft = InvoiceDraft.model_validate(invoice.draft)
    items = [
        _item_read(position, item.description, item.quantity, item.unit_price)
        for position, item in enumerate(draft.items, start=1)
    ]
    missing = [name for name in REQUIRED_FIELDS if getattr(draft, name) is None]
    return _compose(
        invoice,
        draft.merchant,
        draft.invoice_number,
        draft.issued_on,
        draft.total,
        draft.category,
        items,
        missing,
    )


def _read_confirmed(invoice: Invoice, rows: list[InvoiceItem]) -> InvoiceRead:
    items = [
        _item_read(row.position, row.description, Decimal(row.quantity), Decimal(row.unit_price))
        for row in rows
    ]
    return _compose(
        invoice,
        invoice.merchant,
        invoice.invoice_number,
        invoice.issued_on,
        invoice.total,
        invoice.category,
        items,
        [],
    )


async def _read(session: AsyncSession, invoice: Invoice) -> InvoiceRead:
    if invoice.status == InvoiceStatus.DRAFT.value:
        return _read_draft(invoice)
    result = await session.execute(
        select(InvoiceItem)
        .where(InvoiceItem.invoice_id == invoice.id)
        .order_by(InvoiceItem.position)
    )
    return _read_confirmed(invoice, list(result.scalars().all()))


async def _get_owned(
    session: AsyncSession, user_id: uuid.UUID, invoice_id: uuid.UUID, lock: bool = False
) -> Invoice:
    query = select(Invoice).where(Invoice.id == invoice_id, Invoice.user_id == user_id)
    if lock:
        query = query.with_for_update()
    invoice = (await session.execute(query)).scalar_one_or_none()
    if invoice is None:
        raise NotFoundError("No se encontró esa factura.")
    return invoice


def _ensure_draft(invoice: Invoice) -> None:
    if invoice.status != InvoiceStatus.DRAFT.value:
        raise ConflictError("La factura ya fue confirmada y no se puede modificar.")


async def create_draft(
    session: AsyncSession, user_id: uuid.UUID, filename: str | None, extracted: InvoiceDraft
) -> InvoiceRead:
    invoice = Invoice(
        user_id=user_id,
        status=InvoiceStatus.DRAFT.value,
        original_filename=filename[:255] if filename else None,
        draft=extracted.model_dump(mode="json"),
    )
    session.add(invoice)
    await session.commit()
    await session.refresh(invoice)
    return _read_draft(invoice)


async def create_draft_from_file(
    session: AsyncSession,
    user_id: uuid.UUID,
    content: bytes,
    filename: str | None,
    extractor: InvoiceExtractor,
) -> InvoiceRead:
    """Valida el archivo, extrae sus datos y los guarda solo como borrador (RB-06)."""
    if len(content) > settings.invoice_max_bytes:
        limit_mb = settings.invoice_max_bytes // (1024 * 1024)
        raise InvalidFileError(f"El archivo supera el tamaño máximo de {limit_mb} MB.")
    images = await run_in_threadpool(invoice_file.prepare_images, content, filename)
    extracted = await extractor(images)
    return await create_draft(session, user_id, filename, extracted)


async def get_invoice(
    session: AsyncSession, user_id: uuid.UUID, invoice_id: uuid.UUID
) -> InvoiceRead:
    return await _read(session, await _get_owned(session, user_id, invoice_id))


async def list_invoices(session: AsyncSession, user_id: uuid.UUID) -> list[InvoiceRead]:
    result = await session.execute(
        select(Invoice)
        .where(Invoice.user_id == user_id)
        .order_by(Invoice.created_at.desc())
        .limit(INVOICE_LIST_LIMIT)
    )
    return [await _read(session, invoice) for invoice in result.scalars().all()]


async def list_drafts(session: AsyncSession, user_id: uuid.UUID) -> list[InvoiceRead]:
    result = await session.execute(
        select(Invoice)
        .where(Invoice.user_id == user_id, Invoice.status == InvoiceStatus.DRAFT.value)
        .order_by(Invoice.created_at.desc())
        .limit(DRAFT_LIST_LIMIT)
    )
    return [_read_draft(invoice) for invoice in result.scalars().all()]


async def _mutate_draft(
    session: AsyncSession,
    user_id: uuid.UUID,
    invoice_id: uuid.UUID,
    mutate: Callable[[dict[str, Any]], None],
) -> InvoiceRead:
    invoice = await _get_owned(session, user_id, invoice_id, lock=True)
    _ensure_draft(invoice)
    payload = InvoiceDraft.model_validate(invoice.draft).model_dump()
    mutate(payload)
    invoice.draft = InvoiceDraft.model_validate(payload).model_dump(mode="json")
    await session.commit()
    await session.refresh(invoice)
    return _read_draft(invoice)


def _item_index(payload: dict[str, Any], position: int) -> int:
    if position > len(payload["items"]):
        raise NotFoundError(f"La factura no tiene el ítem {position}.")
    return position - 1


async def update_header(
    session: AsyncSession, user_id: uuid.UUID, invoice_id: uuid.UUID, data: InvoiceHeaderUpdate
) -> InvoiceRead:
    changes = data.model_dump(exclude_unset=True)
    return await _mutate_draft(session, user_id, invoice_id, lambda payload: payload.update(changes))


async def update_item(
    session: AsyncSession,
    user_id: uuid.UUID,
    invoice_id: uuid.UUID,
    position: int,
    data: ItemUpdate,
) -> InvoiceRead:
    changes = data.model_dump(exclude_unset=True)

    def mutate(payload: dict[str, Any]) -> None:
        payload["items"][_item_index(payload, position)].update(changes)

    return await _mutate_draft(session, user_id, invoice_id, mutate)


async def add_item(
    session: AsyncSession, user_id: uuid.UUID, invoice_id: uuid.UUID, item: DraftItem
) -> InvoiceRead:
    return await _mutate_draft(
        session, user_id, invoice_id, lambda payload: payload["items"].append(item.model_dump())
    )


async def delete_item(
    session: AsyncSession, user_id: uuid.UUID, invoice_id: uuid.UUID, position: int
) -> InvoiceRead:
    def mutate(payload: dict[str, Any]) -> None:
        del payload["items"][_item_index(payload, position)]

    return await _mutate_draft(session, user_id, invoice_id, mutate)


async def confirm_invoice(
    session: AsyncSession, user_id: uuid.UUID, invoice_id: uuid.UUID
) -> InvoiceRead:
    """Crea el gasto con el total de la factura y sus ítems en una sola transacción (RB-06, RB-08)."""
    invoice = await _get_owned(session, user_id, invoice_id, lock=True)
    if invoice.status == InvoiceStatus.CONFIRMED.value:
        raise ConflictError("La factura ya fue confirmada.")
    draft = InvoiceDraft.model_validate(invoice.draft)
    missing = [name for name in REQUIRED_FIELDS if getattr(draft, name) is None]
    if missing:
        labels = ", ".join(FIELD_LABELS[name] for name in missing)
        raise IncompleteInformationError(f"Faltan datos para confirmar la factura: {labels}.")
    concept = draft.merchant
    if draft.invoice_number:
        concept = f"{draft.merchant} (factura {draft.invoice_number})"
    expense = TransactionCreate(
        type=TransactionType.EXPENSE,
        amount=draft.total,
        concept=concept[:255],
        occurred_on=draft.issued_on,
        category=draft.category,
    )
    transaction = Transaction(
        user_id=user_id,
        type=expense.type.value,
        amount=expense.amount,
        concept=expense.concept,
        category=expense.category.value if expense.category else None,
        occurred_on=expense.occurred_on,
    )
    session.add(transaction)
    await session.flush()
    rows = [
        InvoiceItem(
            invoice_id=invoice.id,
            position=position,
            description=item.description,
            quantity=item.quantity,
            unit_price=item.unit_price,
        )
        for position, item in enumerate(draft.items, start=1)
    ]
    session.add_all(rows)
    invoice.status = InvoiceStatus.CONFIRMED.value
    invoice.merchant = draft.merchant
    invoice.invoice_number = draft.invoice_number
    invoice.issued_on = draft.issued_on
    invoice.total = draft.total
    invoice.category = draft.category.value if draft.category else None
    invoice.transaction_id = transaction.id
    invoice.confirmed_at = datetime.now(UTC)
    invoice.draft = None
    await session.commit()
    await session.refresh(invoice)
    return await _read(session, invoice)


async def discard_draft(
    session: AsyncSession, user_id: uuid.UUID, invoice_id: uuid.UUID
) -> InvoiceRead:
    invoice = await _get_owned(session, user_id, invoice_id, lock=True)
    _ensure_draft(invoice)
    snapshot = _read_draft(invoice)
    await session.delete(invoice)
    await session.commit()
    return snapshot
