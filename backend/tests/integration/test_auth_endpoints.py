import pytest
from collections.abc import AsyncGenerator
from unittest.mock import AsyncMock

from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.core.config import settings
from app.core.database import get_db
from app.core.redis import get_redis
from app.core.security import create_access_token, create_refresh_token, hash_password
from app.main import app


@pytest.fixture
def mock_redis():
    """Redis mockado para testes de integracao."""
    redis = AsyncMock()
    redis.exists = AsyncMock(return_value=False)
    redis.get = AsyncMock(return_value=None)
    redis.set = AsyncMock(return_value=True)
    redis.delete = AsyncMock(return_value=1)
    return redis


@pytest.fixture
async def client(mock_redis):
    engine = create_async_engine(settings.database_url, pool_pre_ping=True)

    async def override_get_db() -> AsyncGenerator[AsyncSession, None]:
        session_factory = async_sessionmaker(engine, expire_on_commit=False)
        async with session_factory() as session:
            yield session

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_redis] = lambda: mock_redis
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c
    app.dependency_overrides.clear()
    await engine.dispose()


# ============================================================
# POST /v1/auth/sms/request
# ============================================================

async def test_sms_request_sucesso(client, mock_redis):
    """POST /v1/auth/sms/request com CPF valido retorna 200."""
    response = await client.post(
        "/v1/auth/sms/request",
        json={"cpf": "12345678901"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["mensagem"] == "Codigo SMS enviado com sucesso"
    assert data["ttl_segundos"] == 300


async def test_sms_request_cpf_invalido(client):
    """POST /v1/auth/sms/request com CPF invalido retorna 422."""
    response = await client.post(
        "/v1/auth/sms/request",
        json={"cpf": "123"},
    )
    assert response.status_code == 422


async def test_sms_request_rate_limit(client, mock_redis):
    """POST /v1/auth/sms/request com rate limit retorna 429."""
    mock_redis.exists.return_value = True

    response = await client.post(
        "/v1/auth/sms/request",
        json={"cpf": "12345678901"},
    )
    assert response.status_code == 429


# ============================================================
# POST /v1/auth/sms/verify
# ============================================================

async def test_sms_verify_sucesso(client, mock_redis):
    """POST /v1/auth/sms/verify com codigo correto retorna tokens."""
    mock_redis.get.return_value = "123456"

    response = await client.post(
        "/v1/auth/sms/verify",
        json={"cpf": "12345678901", "codigo": "123456"},
    )
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert "refresh_token" in data
    assert data["token_type"] == "bearer"


async def test_sms_verify_codigo_errado(client, mock_redis):
    """POST /v1/auth/sms/verify com codigo errado retorna 401."""
    mock_redis.get.return_value = "654321"

    response = await client.post(
        "/v1/auth/sms/verify",
        json={"cpf": "12345678901", "codigo": "123456"},
    )
    assert response.status_code == 401


# ============================================================
# POST /v1/auth/login
# ============================================================

async def test_login_email_inexistente(client):
    """POST /v1/auth/login com email inexistente retorna 401."""
    response = await client.post(
        "/v1/auth/login",
        json={"email": "naoexiste@x.com", "senha": "senha123"},
    )
    assert response.status_code == 401


# ============================================================
# POST /v1/auth/refresh
# ============================================================

async def test_refresh_token_sucesso(client):
    """POST /v1/auth/refresh com refresh valido retorna novos tokens."""
    refresh = create_refresh_token({"sub": "1", "role": "ADMIN"})

    response = await client.post(
        "/v1/auth/refresh",
        json={"refresh_token": refresh},
    )
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert "refresh_token" in data


async def test_refresh_token_invalido(client):
    """POST /v1/auth/refresh com token invalido retorna 401."""
    response = await client.post(
        "/v1/auth/refresh",
        json={"refresh_token": "invalido"},
    )
    assert response.status_code == 401


async def test_refresh_com_access_token_falha(client):
    """Seguranca: access token nao aceito como refresh."""
    access = create_access_token({"sub": "1", "role": "ADMIN"})

    response = await client.post(
        "/v1/auth/refresh",
        json={"refresh_token": access},
    )
    assert response.status_code == 401
