import pytest
from unittest.mock import AsyncMock

from fastapi import HTTPException
from fastapi.security import HTTPAuthorizationCredentials

from app.api.v1.dependencies import get_current_user, require_role
from app.core.security import create_access_token, create_refresh_token


# ============================================================
# T07: Middleware + Guards
# ============================================================

async def test_get_current_user_token_valido():
    """Dependency extrai payload de access token valido."""
    token = create_access_token({"sub": "1", "role": "ADMIN", "email": "a@b.com"})
    creds = HTTPAuthorizationCredentials(scheme="Bearer", credentials=token)

    user = await get_current_user(creds)

    assert user["sub"] == "1"
    assert user["role"] == "ADMIN"
    assert user["type"] == "access"


async def test_get_current_user_token_invalido():
    """Token invalido lanca 401."""
    creds = HTTPAuthorizationCredentials(scheme="Bearer", credentials="invalido")

    with pytest.raises(HTTPException) as exc_info:
        await get_current_user(creds)

    assert exc_info.value.status_code == 401


async def test_get_current_user_rejeita_refresh_token():
    """Seguranca: refresh token nao e aceito como access."""
    token = create_refresh_token({"sub": "1", "role": "ADMIN"})
    creds = HTTPAuthorizationCredentials(scheme="Bearer", credentials=token)

    with pytest.raises(HTTPException) as exc_info:
        await get_current_user(creds)

    assert exc_info.value.status_code == 401


async def test_require_role_permite_role_correto():
    """Guard permite acesso quando usuario tem role permitido."""
    checker = require_role("ADMIN", "RECEPCIONISTA")
    user = {"sub": "1", "role": "ADMIN", "type": "access"}

    result = await checker(user)
    assert result["role"] == "ADMIN"


async def test_require_role_bloqueia_role_incorreto():
    """Guard bloqueia acesso quando usuario nao tem role permitido."""
    checker = require_role("ADMIN")
    user = {"sub": "1", "role": "MEDICO", "type": "access"}

    with pytest.raises(HTTPException) as exc_info:
        await checker(user)

    assert exc_info.value.status_code == 403


async def test_require_role_paciente_externo_sem_acesso_admin():
    """RBAC: PACIENTE_EXTERNO nao acessa rotas internas."""
    checker = require_role("ADMIN", "RECEPCIONISTA", "MEDICO")
    user = {"sub": "12345678901", "role": "PACIENTE_EXTERNO", "type": "access"}

    with pytest.raises(HTTPException) as exc_info:
        await checker(user)

    assert exc_info.value.status_code == 403


async def test_require_role_medico_acessa_rota_medico():
    """RBAC: MEDICO acessa rotas que incluem MEDICO."""
    checker = require_role("MEDICO", "ADMIN")
    user = {"sub": "5", "role": "MEDICO", "profissional_id": 10, "type": "access"}

    result = await checker(user)
    assert result["role"] == "MEDICO"
    assert result["profissional_id"] == 10
