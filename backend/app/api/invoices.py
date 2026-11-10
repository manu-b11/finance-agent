import uuid
from functools import partial

from fastapi import APIRouter, Depends, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.agent import invoice_extractor
from app.agent.llm_client import ChatFn
from app.api.deps import get_chat_fn, get_current_user
from app.core.config import settings
from app.core.database import get_session
from app.models.user import User
from app.schemas.invoice import InvoiceRead
from app.services import invoice as invoice_service

router = APIRouter(prefix="/invoices", tags=["invoices"])


@router.post("", response_model=InvoiceRead, status_code=status.HTTP_201_CREATED)
async def upload_invoice(
    file: UploadFile,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
    chat_fn: ChatFn = Depends(get_chat_fn),
) -> InvoiceRead:
    content = await file.read(settings.invoice_max_bytes + 1)
    return await invoice_service.create_draft_from_file(
        session,
        current_user.id,
        content,
        file.filename,
        partial(invoice_extractor.extract_invoice, chat_fn),
    )


@router.get("/{invoice_id}", response_model=InvoiceRead)
async def get_invoice(
    invoice_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> InvoiceRead:
    return await invoice_service.get_invoice(session, current_user.id, invoice_id)
