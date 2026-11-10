import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import auth as auth_router
from app.api import chat as chat_router
from app.api import dashboard as dashboard_router
from app.api import invoices as invoices_router
from app.api import push as push_router
from app.api import reports as reports_router
from app.core.config import settings
from app.core.database import SessionLocal
from app.core.errors import register_error_handlers
from app.jobs.scheduler import create_scheduler
from app.services import push as push_service

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    scheduler = None
    if settings.scheduler_enabled:
        if not settings.vapid_private_key:
            logger.warning("VAPID_PRIVATE_KEY no está configurada: no se enviarán notificaciones.")
        scheduler = create_scheduler(SessionLocal, push_service.web_push_sender)
        scheduler.start()
    yield
    if scheduler is not None:
        scheduler.shutdown(wait=False)


app = FastAPI(title="Agente de Finanzas Personales", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

register_error_handlers(app)
app.include_router(auth_router.router)
app.include_router(chat_router.router)
app.include_router(invoices_router.router)
app.include_router(reports_router.router)
app.include_router(dashboard_router.router)
app.include_router(push_router.router)


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}
