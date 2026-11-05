import uuid
from decimal import Decimal

from sqlalchemy import case, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import NotFoundError
from app.models.transaction import Transaction, TransactionType
from app.schemas.transaction import (
    BalanceRead,
    PeriodQuery,
    TransactionCreate,
    TransactionFilters,
    TransactionRead,
    TransactionUpdate,
)

CENTS = Decimal("0.01")


async def create_transaction(
    session: AsyncSession, user_id: uuid.UUID, data: TransactionCreate
) -> Transaction:
    transaction = Transaction(
        user_id=user_id,
        type=data.type.value,
        amount=data.amount,
        concept=data.concept,
        category=data.category.value if data.category else None,
        occurred_on=data.occurred_on,
    )
    session.add(transaction)
    await session.commit()
    await session.refresh(transaction)
    return transaction


async def _get_owned(
    session: AsyncSession, user_id: uuid.UUID, transaction_id: uuid.UUID
) -> Transaction:
    result = await session.execute(
        select(Transaction).where(
            Transaction.id == transaction_id, Transaction.user_id == user_id
        )
    )
    transaction = result.scalar_one_or_none()
    if transaction is None:
        raise NotFoundError("No se encontró ese movimiento.")
    return transaction


async def update_transaction(
    session: AsyncSession,
    user_id: uuid.UUID,
    transaction_id: uuid.UUID,
    data: TransactionUpdate,
) -> Transaction:
    """Aplica cambios parciales y revalida el movimiento resultante completo."""
    transaction = await _get_owned(session, user_id, transaction_id)
    merged = {
        "type": transaction.type,
        "amount": transaction.amount,
        "concept": transaction.concept,
        "occurred_on": transaction.occurred_on,
        "category": transaction.category,
    }
    merged.update(data.model_dump(exclude_unset=True))
    valid = TransactionCreate.model_validate(merged)
    transaction.type = valid.type.value
    transaction.amount = valid.amount
    transaction.concept = valid.concept
    transaction.occurred_on = valid.occurred_on
    transaction.category = valid.category.value if valid.category else None
    await session.commit()
    await session.refresh(transaction)
    return transaction


async def delete_transaction(
    session: AsyncSession, user_id: uuid.UUID, transaction_id: uuid.UUID
) -> TransactionRead:
    transaction = await _get_owned(session, user_id, transaction_id)
    snapshot = TransactionRead.model_validate(transaction)
    await session.delete(transaction)
    await session.commit()
    return snapshot


async def list_transactions(
    session: AsyncSession, user_id: uuid.UUID, filters: TransactionFilters
) -> list[Transaction]:
    query = select(Transaction).where(Transaction.user_id == user_id)
    if filters.start_date:
        query = query.where(Transaction.occurred_on >= filters.start_date)
    if filters.end_date:
        query = query.where(Transaction.occurred_on <= filters.end_date)
    if filters.type:
        query = query.where(Transaction.type == filters.type.value)
    if filters.category:
        query = query.where(Transaction.category == filters.category.value)
    query = query.order_by(Transaction.occurred_on.desc(), Transaction.created_at.desc()).limit(
        filters.limit
    )
    result = await session.execute(query)
    return list(result.scalars().all())


async def get_balance(
    session: AsyncSession, user_id: uuid.UUID, period: PeriodQuery
) -> BalanceRead:
    """Balance = ingresos − gastos (RB-05), calculado en la base con Decimal."""
    income = func.coalesce(
        func.sum(case((Transaction.type == TransactionType.INCOME.value, Transaction.amount), else_=0)),
        0,
    )
    expenses = func.coalesce(
        func.sum(case((Transaction.type == TransactionType.EXPENSE.value, Transaction.amount), else_=0)),
        0,
    )
    query = select(income, expenses).where(Transaction.user_id == user_id)
    if period.start_date:
        query = query.where(Transaction.occurred_on >= period.start_date)
    if period.end_date:
        query = query.where(Transaction.occurred_on <= period.end_date)
    total_income, total_expenses = (await session.execute(query)).one()
    total_income = Decimal(total_income).quantize(CENTS)
    total_expenses = Decimal(total_expenses).quantize(CENTS)
    return BalanceRead(
        total_income=total_income,
        total_expenses=total_expenses,
        balance=total_income - total_expenses,
        start_date=period.start_date,
        end_date=period.end_date,
    )