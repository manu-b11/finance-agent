"""Tools del agente para movimientos y balance.

Cada tool valida los argumentos del modelo con Pydantic y llama al service.
`user_id` lo entrega quien ejecuta la tool (viene del token), nunca los argumentos.
Si los argumentos son inválidos se propaga `pydantic.ValidationError`; el
orquestador (paso 4) la devuelve al modelo para que corrija o pregunte al usuario.
"""
import uuid
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.schemas.transaction import (
    BalanceRead,
    PeriodQuery,
    TransactionCreate,
    TransactionFilters,
    TransactionRead,
    TransactionRef,
    TransactionUpdate,
)
from app.services import transaction as transaction_service


async def add_transaction(
    session: AsyncSession, user_id: uuid.UUID, raw_args: dict[str, Any]
) -> dict[str, Any]:
    args = TransactionCreate.model_validate(raw_args)
    transaction = await transaction_service.create_transaction(session, user_id, args)
    return TransactionRead.model_validate(transaction).model_dump(mode="json")


async def update_transaction(
    session: AsyncSession, user_id: uuid.UUID, raw_args: dict[str, Any]
) -> dict[str, Any]:
    changes = dict(raw_args)
    ref = TransactionRef.model_validate({"transaction_id": changes.pop("transaction_id", None)})
    data = TransactionUpdate.model_validate(changes)
    transaction = await transaction_service.update_transaction(
        session, user_id, ref.transaction_id, data
    )
    return TransactionRead.model_validate(transaction).model_dump(mode="json")


async def delete_transaction(
    session: AsyncSession, user_id: uuid.UUID, raw_args: dict[str, Any]
) -> dict[str, Any]:
    ref = TransactionRef.model_validate(raw_args)
    deleted = await transaction_service.delete_transaction(session, user_id, ref.transaction_id)
    return {"deleted": True, "transaction": deleted.model_dump(mode="json")}


async def list_transactions(
    session: AsyncSession, user_id: uuid.UUID, raw_args: dict[str, Any]
) -> dict[str, Any]:
    args = TransactionFilters.model_validate(raw_args)
    transactions = await transaction_service.list_transactions(session, user_id, args)
    items = [TransactionRead.model_validate(t).model_dump(mode="json") for t in transactions]
    return {"count": len(items), "transactions": items}


async def get_balance(
    session: AsyncSession, user_id: uuid.UUID, raw_args: dict[str, Any]
) -> dict[str, Any]:
    args = PeriodQuery.model_validate(raw_args)
    balance: BalanceRead = await transaction_service.get_balance(session, user_id, args)
    return balance.model_dump(mode="json")