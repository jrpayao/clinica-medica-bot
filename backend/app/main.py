from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

import httpx
import structlog
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1.router import api_router
from app.core.config import settings
from app.core.logging import setup_logging

log = structlog.get_logger(__name__)


def _obter_tags_url_ollama(base_url: str) -> str:
    normalized = base_url.rstrip("/")
    if normalized.endswith("/v1"):
        normalized = normalized[:-3]
    return f"{normalized}/api/tags"


async def validar_modelos_ollama() -> dict[str, object]:
    """Valida modelos configurados quando usando endpoint local do Ollama.

    Nao interrompe startup: apenas loga alertas operacionais.
    """
    if "localhost:11434" not in settings.openrouter_base_url:
        return {"status": "skipped", "missing": []}

    modelos_requeridos = {
        settings.model_economico,
        settings.model_medico,
        settings.model_premium,
        settings.model_rag,
    }
    tags_url = _obter_tags_url_ollama(settings.openrouter_base_url)

    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.get(tags_url)
            response.raise_for_status()
            payload = response.json()
    except Exception as exc:
        log.warning(
            "ollama_validacao_indisponivel",
            erro=str(exc),
            tags_url=tags_url,
        )
        return {"status": "unavailable", "missing": sorted(modelos_requeridos)}

    modelos_disponiveis = {
        item.get("name")
        for item in payload.get("models", [])
        if isinstance(item, dict) and item.get("name")
    }
    modelos_faltando = sorted(modelos_requeridos - modelos_disponiveis)

    if modelos_faltando:
        log.warning(
            "ollama_modelos_ausentes",
            modelos_faltando=modelos_faltando,
            comando_pull="ollama pull <modelo>",
        )
        return {"status": "missing", "missing": modelos_faltando}

    log.info(
        "ollama_modelos_ok",
        quantidade_modelos=len(modelos_requeridos),
    )
    return {"status": "ok", "missing": []}


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Startup e shutdown do app — NUNCA usar @app.on_event (deprecated)."""
    setup_logging(debug=settings.debug)
    log.info("medbot_api_starting", debug=settings.debug)
    await validar_modelos_ollama()
    yield
    log.info("medbot_api_shutting_down")


app = FastAPI(
    title=settings.app_name,
    version="0.1.0",
    lifespan=lifespan,
    docs_url="/docs" if settings.debug else None,
    redoc_url="/redoc" if settings.debug else None,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router, prefix="/v1")


@app.get("/health", tags=["Health"])
async def health_check() -> dict[str, str]:
    return {"status": "ok"}
