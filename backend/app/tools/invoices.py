import uuid
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.schemas.invoice import (
    DraftItem,
    InvoiceConfirm,
    InvoiceHeaderUpdate,
    InvoiceListQuery,
    InvoiceRef,
    ItemPosition,
    ItemUpdate,
)
from app.services import invoice as invoice_service


async def get_invoice(
    session: AsyncSession, user_id: uuid.UUID, raw_args: dict[str, Any]
) -> dict[str, Any]:
    ref = InvoiceRef.model_validate(raw_args)
    invoice = await invoice_service.get_invoice(session, user_id, ref.invoice_id)
    return invoice.model_dump(mode="json")


async def list_draft_invoices(
    session: AsyncSession, user_id: uuid.UUID, raw_args: dict[str, Any]
) -> dict[str, Any]:
    InvoiceListQuery.model_validate(raw_args)
    drafts = await invoice_service.list_drafts(session, user_id)
    items = [draft.model_dump(mode="json") for draft in drafts]
    return {"count": len(items), "invoices": items}


async def update_invoice(
    session: AsyncSession, user_id: uuid.UUID, raw_args: dict[str, Any]
) -> dict[str, Any]:
    changes = dict(raw_args)
    ref = InvoiceRef.model_validate({"invoice_id": changes.pop("invoice_id", None)})
    data = InvoiceHeaderUpdate.model_validate(changes)
    invoice = await invoice_service.update_header(session, user_id, ref.invoice_id, data)
    return invoice.model_dump(mode="json")


async def update_invoice_item(
    session: AsyncSession, user_id: uuid.UUID, raw_args: dict[str, Any]
) -> dict[str, Any]:
    changes = dict(raw_args)
    target = ItemPosition.model_validate(
        {"invoice_id": changes.pop("invoice_id", None), "position": changes.pop("position", None)}
    )
    data = ItemUpdate.model_validate(changes)
    invoice = await invoice_service.update_item(
        session, user_id, target.invoice_id, target.position, data
    )
    return invoice.model_dump(mode="json")


async def add_invoice_item(
    session: AsyncSession, user_id: uuid.UUID, raw_args: dict[str, Any]
) -> dict[str, Any]:
    fields = dict(raw_args)
    ref = InvoiceRef.model_validate({"invoice_id": fields.pop("invoice_id", None)})
    item = DraftItem.model_validate(fields)
    invoice = await invoice_service.add_item(session, user_id, ref.invoice_id, item)
    return invoice.model_dump(mode="json")


async def delete_invoice_item(
    session: AsyncSession, user_id: uuid.UUID, raw_args: dict[str, Any]
) -> dict[str, Any]:
    target = ItemPosition.model_validate(raw_args)
    invoice = await invoice_service.delete_item(
        session, user_id, target.invoice_id, target.position
    )
    return invoice.model_dump(mode="json")


async def confirm_invoice(
    session: AsyncSession, user_id: uuid.UUID, raw_args: dict[str, Any]
) -> dict[str, Any]:
    args = InvoiceConfirm.model_validate(raw_args)
    invoice = await invoice_service.confirm_invoice(session, user_id, args.invoice_id)
    return invoice.model_dump(mode="json")


async def discard_invoice(
    session: AsyncSession, user_id: uuid.UUID, raw_args: dict[str, Any]
) -> dict[str, Any]:
    ref = InvoiceRef.model_validate(raw_args)
    invoice = await invoice_service.discard_draft(session, user_id, ref.invoice_id)
    return {"discarded": True, "invoice": invoice.model_dump(mode="json")}
