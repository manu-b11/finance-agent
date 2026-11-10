from decimal import Decimal

import pytest
from sqlalchemy import func, select

from app.core.errors import ConflictError, IncompleteInformationError, NotFoundError
from app.models.invoice import InvoiceItem
from app.models.transaction import Transaction
from app.schemas.invoice import DraftItem, InvoiceDraft, InvoiceHeaderUpdate, ItemUpdate
from app.schemas.transaction import PeriodQuery
from app.schemas.user import UserCreate
from app.services import auth as auth_service
from app.services import invoice as service
from app.services import transaction as transaction_service

DRAFT = InvoiceDraft(
    merchant="Supermercado Éxito",
    invoice_number="FE-1023",
    issued_on="2026-11-05",
    total=Decimal("12200.50"),
    category="alimentacion",
    items=[
        DraftItem(description="Leche", quantity=Decimal("2"), unit_price=Decimal("4500")),
        DraftItem(description="Pan", quantity=Decimal("1"), unit_price=Decimal("3200.50")),
    ],
)


async def make_user(session, email: str = "ana@example.com"):
    return await auth_service.register_user(
        session, UserCreate(email=email, password="clave-segura-1")
    )


async def count_transactions(session, user_id) -> int:
    result = await session.execute(
        select(func.count()).select_from(Transaction).where(Transaction.user_id == user_id)
    )
    return result.scalar_one()


async def count_items(session) -> int:
    result = await session.execute(select(func.count()).select_from(InvoiceItem))
    return result.scalar_one()


async def test_draft_is_saved_without_creating_expense_or_items(session):
    user = await make_user(session)
    user_id = user.id
    invoice = await service.create_draft(session, user_id, "factura.png", DRAFT)
    assert invoice.status == "draft"
    assert invoice.merchant == "Supermercado Éxito"
    assert invoice.total == Decimal("12200.50")
    assert [item.line_total for item in invoice.items] == [Decimal("9000.00"), Decimal("3200.50")]
    assert invoice.items_total == Decimal("12200.50")
    assert invoice.total_matches_items is True
    assert invoice.missing_fields == []
    assert invoice.transaction_id is None
    assert await count_transactions(session, user_id) == 0
    assert await count_items(session) == 0


async def test_missing_fields_and_total_mismatch_are_reported(session):
    user = await make_user(session)
    draft = InvoiceDraft(
        merchant="Tienda",
        total=Decimal("20000"),
        items=[DraftItem(description="A", quantity=Decimal("1"), unit_price=Decimal("5000"))],
    )
    invoice = await service.create_draft(session, user.id, None, draft)
    assert invoice.missing_fields == ["issued_on", "category"]
    assert invoice.total_matches_items is False
    assert invoice.items_total == Decimal("5000.00")


async def test_total_matches_is_unknown_without_items_or_total(session):
    user = await make_user(session)
    no_items = await service.create_draft(
        session, user.id, None, InvoiceDraft(merchant="X", total=Decimal("10"))
    )
    no_total = await service.create_draft(
        session,
        user.id,
        None,
        InvoiceDraft(
            merchant="X", items=[DraftItem(description="A", unit_price=Decimal("5"))]
        ),
    )
    assert no_items.total_matches_items is None
    assert no_total.total_matches_items is None
    assert "total" in no_total.missing_fields


async def test_confirm_creates_single_expense_with_invoice_total_and_items(session):
    user = await make_user(session)
    user_id = user.id
    draft = await service.create_draft(session, user_id, "f.png", DRAFT)
    confirmed = await service.confirm_invoice(session, user_id, draft.id)
    assert confirmed.status == "confirmed"
    assert confirmed.confirmed_at is not None
    assert confirmed.transaction_id is not None
    assert [(i.position, i.description) for i in confirmed.items] == [(1, "Leche"), (2, "Pan")]
    assert await count_transactions(session, user_id) == 1
    assert await count_items(session) == 2
    balance = await transaction_service.get_balance(session, user_id, PeriodQuery())
    assert balance.total_expenses == Decimal("12200.50")
    transaction = (await session.execute(select(Transaction))).scalar_one()
    assert transaction.type == "expense"
    assert transaction.amount == Decimal("12200.50")
    assert transaction.category == "alimentacion"
    assert transaction.concept == "Supermercado Éxito (factura FE-1023)"
    assert transaction.occurred_on.isoformat() == "2026-11-05"
    assert confirmed.transaction_id == transaction.id


async def test_confirm_uses_invoice_total_even_if_items_do_not_add_up(session):
    user = await make_user(session)
    user_id = user.id
    draft = InvoiceDraft(
        merchant="Tienda",
        issued_on="2026-11-05",
        total=Decimal("20000"),
        category="otros",
        items=[DraftItem(description="A", unit_price=Decimal("5000"))],
    )
    created = await service.create_draft(session, user_id, None, draft)
    await service.confirm_invoice(session, user_id, created.id)
    balance = await transaction_service.get_balance(session, user_id, PeriodQuery())
    assert balance.total_expenses == Decimal("20000.00")


async def test_confirming_twice_does_not_duplicate_the_expense(session):
    user = await make_user(session)
    user_id = user.id
    draft = await service.create_draft(session, user_id, None, DRAFT)
    await service.confirm_invoice(session, user_id, draft.id)
    with pytest.raises(ConflictError):
        await service.confirm_invoice(session, user_id, draft.id)
    assert await count_transactions(session, user_id) == 1
    assert await count_items(session) == 2


async def test_confirm_without_required_data_fails_and_creates_nothing(session):
    user = await make_user(session)
    user_id = user.id
    created = await service.create_draft(
        session, user_id, None, InvoiceDraft(merchant="Tienda", total=Decimal("100"))
    )
    with pytest.raises(IncompleteInformationError) as error:
        await service.confirm_invoice(session, user_id, created.id)
    assert "fecha" in error.value.message and "categoría" in error.value.message
    await session.rollback()
    assert await count_transactions(session, user_id) == 0
    assert (await service.get_invoice(session, user_id, created.id)).status == "draft"


async def test_corrections_make_a_draft_confirmable(session):
    user = await make_user(session)
    user_id = user.id
    created = await service.create_draft(
        session, user_id, None, InvoiceDraft(merchant="Tienda", total=Decimal("100"))
    )
    updated = await service.update_header(
        session,
        user_id,
        created.id,
        InvoiceHeaderUpdate(issued_on="2026-11-06", category="otros"),
    )
    assert updated.missing_fields == []
    confirmed = await service.confirm_invoice(session, user_id, created.id)
    assert confirmed.issued_on.isoformat() == "2026-11-06"


async def test_header_update_changes_only_sent_fields_and_can_clear_number(session):
    user = await make_user(session)
    created = await service.create_draft(session, user.id, None, DRAFT)
    updated = await service.update_header(
        session, user.id, created.id, InvoiceHeaderUpdate(total=Decimal("15000"))
    )
    assert updated.total == Decimal("15000.00")
    assert updated.merchant == "Supermercado Éxito"
    cleared = await service.update_header(
        session, user.id, created.id, InvoiceHeaderUpdate(invoice_number=None)
    )
    assert cleared.invoice_number is None


async def test_item_edit_add_and_delete(session):
    user = await make_user(session)
    user_id = user.id
    created = await service.create_draft(session, user_id, None, DRAFT)
    edited = await service.update_item(
        session, user_id, created.id, 1, ItemUpdate(quantity=Decimal("3"))
    )
    assert edited.items[0].quantity == Decimal("3.000")
    assert edited.items[0].line_total == Decimal("13500.00")
    added = await service.add_item(
        session, user_id, created.id, DraftItem(description="Jugo", unit_price=Decimal("2500"))
    )
    assert [i.position for i in added.items] == [1, 2, 3]
    assert added.items[2].quantity == Decimal("1.000")
    removed = await service.delete_item(session, user_id, created.id, 2)
    assert [i.description for i in removed.items] == ["Leche", "Jugo"]
    assert [i.position for i in removed.items] == [1, 2]


async def test_item_position_out_of_range_raises_not_found(session):
    user = await make_user(session)
    created = await service.create_draft(session, user.id, None, DRAFT)
    with pytest.raises(NotFoundError):
        await service.update_item(session, user.id, created.id, 3, ItemUpdate(description="X"))
    with pytest.raises(NotFoundError):
        await service.delete_item(session, user.id, created.id, 9)


async def test_confirmed_invoice_cannot_be_modified_or_discarded(session):
    user = await make_user(session)
    user_id = user.id
    created = await service.create_draft(session, user_id, None, DRAFT)
    await service.confirm_invoice(session, user_id, created.id)
    with pytest.raises(ConflictError):
        await service.update_header(
            session, user_id, created.id, InvoiceHeaderUpdate(merchant="Otro")
        )
    with pytest.raises(ConflictError):
        await service.add_item(
            session, user_id, created.id, DraftItem(description="X", unit_price=Decimal("1"))
        )
    with pytest.raises(ConflictError):
        await service.discard_draft(session, user_id, created.id)


async def test_discard_removes_draft_without_side_effects(session):
    user = await make_user(session)
    user_id = user.id
    created = await service.create_draft(session, user_id, None, DRAFT)
    discarded = await service.discard_draft(session, user_id, created.id)
    assert discarded.merchant == "Supermercado Éxito"
    with pytest.raises(NotFoundError):
        await service.get_invoice(session, user_id, created.id)
    assert await count_transactions(session, user_id) == 0


async def test_list_drafts_returns_only_pending_ones_newest_first(session):
    user = await make_user(session)
    user_id = user.id
    first = await service.create_draft(session, user_id, "a.png", DRAFT)
    second = await service.create_draft(session, user_id, "b.png", DRAFT)
    third = await service.create_draft(session, user_id, "c.png", DRAFT)
    await service.confirm_invoice(session, user_id, first.id)
    drafts = await service.list_drafts(session, user_id)
    assert [d.id for d in drafts] == [third.id, second.id]


async def test_invoices_are_isolated_between_users(session):
    ana = await make_user(session, "ana@example.com")
    beto = await make_user(session, "beto@example.com")
    ana_id, beto_id = ana.id, beto.id
    created = await service.create_draft(session, ana_id, None, DRAFT)
    with pytest.raises(NotFoundError):
        await service.get_invoice(session, beto_id, created.id)
    with pytest.raises(NotFoundError):
        await service.confirm_invoice(session, beto_id, created.id)
    with pytest.raises(NotFoundError):
        await service.update_header(
            session, beto_id, created.id, InvoiceHeaderUpdate(merchant="Mía")
        )
    with pytest.raises(NotFoundError):
        await service.discard_draft(session, beto_id, created.id)
    assert await service.list_drafts(session, beto_id) == []
    assert await count_transactions(session, beto_id) == 0
    assert (await service.get_invoice(session, ana_id, created.id)).status == "draft"


async def test_create_draft_from_file_rejects_oversized_files(session, monkeypatch):
    from app.core.errors import InvalidFileError

    monkeypatch.setattr(service.settings, "invoice_max_bytes", 10)
    user = await make_user(session)

    async def extractor(images):
        raise AssertionError("no debe llamarse")

    with pytest.raises(InvalidFileError):
        await service.create_draft_from_file(session, user.id, b"x" * 11, "f.png", extractor)


async def test_failed_extraction_leaves_no_draft(session):
    from app.core.errors import IncompleteInformationError as Incomplete
    import io

    from PIL import Image

    user = await make_user(session)
    user_id = user.id
    buffer = io.BytesIO()
    Image.new("RGB", (50, 50), "white").save(buffer, format="PNG")

    async def extractor(images):
        raise Incomplete("ilegible")

    with pytest.raises(Incomplete):
        await service.create_draft_from_file(session, user_id, buffer.getvalue(), "f.png", extractor)
    assert await service.list_drafts(session, user_id) == []


async def test_concurrent_confirmations_create_a_single_expense(engine, session):
    import asyncio

    from sqlalchemy.ext.asyncio import async_sessionmaker

    user = await make_user(session)
    user_id = user.id
    draft = await service.create_draft(session, user_id, None, DRAFT)
    invoice_id = draft.id
    factory = async_sessionmaker(engine, expire_on_commit=False)

    async def attempt() -> str:
        async with factory() as other:
            try:
                await service.confirm_invoice(other, user_id, invoice_id)
            except ConflictError:
                return "conflict"
            return "confirmed"

    results = await asyncio.gather(attempt(), attempt(), attempt())
    assert sorted(results) == ["confirmed", "conflict", "conflict"]
    assert await count_transactions(session, user_id) == 1
    assert await count_items(session) == 2
