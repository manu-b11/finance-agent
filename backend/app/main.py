from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import auth as auth_router
from app.api import chat as chat_router
from app.api import invoices as invoices_router
from app.api import reports as reports_router
from app.core.config import settings
from app.core.errors import register_error_handlers

app = FastAPI(title="Agente de Finanzas Personales")

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


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}
