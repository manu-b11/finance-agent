import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.agent.llm_client import is_local_ollama
from app.api import auth as auth_router
from app.api import chat as chat_router
from app.api import dashboard as dashboard_router
from app.api import invoices as invoices_router
from app.api import push as push_router
from app.api import reminders as reminders_router
from app.api import reports as reports_router
from app.api import savings_goals as savings_goals_router
from app.core.config import settings
from app.core.database import SessionLocal
from app.core.errors import register_error_handlers
from app.jobs.scheduler import create_scheduler
from app.services import push as push_service

logger = logging.getLogger(__name__)

# Sin esto, los logger.info/error de la app pueden no verse en la consola.
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
)


class _DropModelProbeFilter(logging.Filter):
    """Oculta los 404 de clientes que sondean /v1/models.

    Herramientas locales (OpenCode, clientes OpenAI-compatibles) prueban si el
    backend es un servidor de modelos. Finly no expone esa ruta, así que esos
    404 son ruido y no indican un fallo de la aplicación.
    """

    def filter(self, record: logging.LogRecord) -> bool:
        return "/v1/models" not in record.getMessage()


logging.getLogger("uvicorn.access").addFilter(_DropModelProbeFilter())
# El job de recordatorios corre cada 30 s: su INFO no aporta nada en consola.
logging.getLogger("apscheduler").setLevel(logging.WARNING)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    ollama_local = is_local_ollama(settings.ollama_base_url)
    logger.info(
        "Proveedores de IA → Gemini: %s (%s) · Qwen: %s (%s, %s) · "
        "Ollama: %s (%s, %s, num_ctx=%s)",
        "configurado" if settings.gemini_api_key else "sin clave",
        settings.gemini_model,
        "configurado" if settings.qwen_api_key else "sin clave",
        settings.qwen_model,
        settings.qwen_base_url,
        "configurado" if settings.ollama_api_key or ollama_local else "sin clave",
        settings.ollama_model,
        "local" if ollama_local else settings.ollama_base_url,
        settings.ollama_num_ctx if ollama_local else "auto",
    )
    if not settings.qwen_api_key:
        logger.warning(
            "QWEN_API_KEY está vacía: el respaldo Qwen no funcionará. "
            "Crea una clave en https://openrouter.ai/settings/keys."
        )
    if not ollama_local and not settings.ollama_api_key:
        logger.warning(
            "OLLAMA_API_KEY está vacía: el respaldo en Ollama Cloud no funcionará. "
            "Crea una clave en https://ollama.com/settings/keys."
        )
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
app.include_router(reminders_router.router)
app.include_router(savings_goals_router.router)


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}
