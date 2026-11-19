import os

# Os testes não usam a observabilidade da máquina: sem envio de erros ao GlitchTip local e sem
# token no /metrics. Variável de ambiente vale mais que o backend/.env, e precisa vir antes de importar a app.
os.environ["SENTRY_DSN"] = ""
os.environ["METRICS_TOKEN"] = ""

from collections.abc import AsyncGenerator  # noqa: E402
from unittest.mock import AsyncMock

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.core.config import settings
from app.core.database import get_db
from app.main import app
from app.models.base import Base


@pytest.fixture
async def db_engine():
    """Engine de teste apontando para o mesmo banco local."""
    engine = create_async_engine(
        settings.database_url,
        echo=False,
        pool_pre_ping=True,
    )
    yield engine
    await engine.dispose()


@pytest.fixture
async def db_session(db_engine) -> AsyncGenerator[AsyncSession, None]:
    """Sessao de banco com rollback automatico apos cada teste."""
    async with db_engine.connect() as conn:
        trans = await conn.begin()
        session_factory = async_sessionmaker(bind=conn, expire_on_commit=False)
        async with session_factory() as session:
            yield session
        await trans.rollback()


@pytest.fixture
async def async_client(db_session) -> AsyncGenerator[AsyncClient, None]:
    """HTTP client de teste com override de dependencia do banco."""

    async def override_get_db() -> AsyncGenerator[AsyncSession, None]:
        yield db_session

    app.dependency_overrides[get_db] = override_get_db

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client

    app.dependency_overrides.clear()


@pytest.fixture
def redis_client() -> AsyncMock:
    """Redis mockado para testes unitarios."""
    mock = AsyncMock()
    mock.get = AsyncMock(return_value=None)
    mock.set = AsyncMock(return_value=True)
    mock.delete = AsyncMock(return_value=1)
    return mock


@pytest.fixture(autouse=True)
def _sem_ia_no_resumo_de_triagem(monkeypatch):
    """Nenhum teste chama o modelo de verdade para o resumo de triagem: sem isto, o agendamento pelo
    chat tentaria a rede. Testes do resumo injetam o proprio `invocar`."""

    async def _indisponivel(_sistema: str, _usuario: str):
        raise RuntimeError("IA desligada nos testes")

    monkeypatch.setattr("app.services.ia.resumo_triagem._invocar_llm", _indisponivel)


@pytest.fixture(autouse=True)
def _unidades_do_teste():
    from tests.fabrica import UNIDADES_DO_TESTE

    UNIDADES_DO_TESTE.clear()
    yield
    UNIDADES_DO_TESTE.clear()


@pytest.fixture(autouse=True)
def _jitsi_padrao(monkeypatch):
    """Os testes nao dependem do Jitsi configurado no .env da maquina: valem o servidor publico e sala sem JWT."""
    monkeypatch.setattr(settings, "jitsi_base_url", "https://meet.jit.si")
    monkeypatch.setattr(settings, "jitsi_app_id", "")
    monkeypatch.setattr(settings, "jitsi_app_secret", "")
    monkeypatch.setattr(settings, "portal_url", "http://localhost:4200")


@pytest.fixture(autouse=True)
def _cache_em_memoria(monkeypatch):
    """Cada teste tem o seu cache vazio: nada do Redis de desenvolvimento vaza entre testes."""
    from tests.fabrica import RedisFalso

    redis = RedisFalso()
    monkeypatch.setattr("app.core.cache._cliente", lambda: redis)
    return redis
