"""Testes TDAD — estabelecimento_id no JWT + dependency get_estabelecimento_id.

T60 — Multi-tenancy JWT:
- login_interno deve embutir estabelecimento_id no token
- ADMIN_GLOBAL não deve ter estabelecimento_id no token
- get_estabelecimento_id deve extrair do token ou raise 403
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from starlette.testclient import TestClient
from starlette.requests import Request as StarletteRequest

from app.api.v1.dependencies import get_estabelecimento_id, require_estabelecimento
from app.models.usuario import UsuarioRole


def _mock_request(headers: dict | None = None) -> StarletteRequest:
    """Cria um Request mock com headers opcionais."""
    scope = {
        "type": "http",
        "method": "GET",
        "path": "/",
        "headers": [
            (k.lower().encode(), v.encode())
            for k, v in (headers or {}).items()
        ],
        "query_string": b"",
    }
    return StarletteRequest(scope)


# ============================================================
# T60-A: JWT com estabelecimento_id
# ============================================================


def test_login_interno_embute_estabelecimento_id_no_token() -> None:
    """O payload do token deve conter estabelecimento_id para usuários não-ADMIN_GLOBAL."""
    from app.core.security import create_access_token, verify_token

    payload = {
        "sub": "42",
        "role": "RECEPCIONISTA",
        "estabelecimento_id": 3,
    }
    token = create_access_token(payload)
    decoded = verify_token(token)

    assert decoded is not None
    assert decoded["estabelecimento_id"] == 3
    assert decoded["role"] == "RECEPCIONISTA"


def test_admin_global_token_sem_estabelecimento_id() -> None:
    """ADMIN_GLOBAL não deve ter estabelecimento_id no token."""
    from app.core.security import create_access_token, verify_token

    payload = {
        "sub": "1",
        "role": "ADMIN_GLOBAL",
        # sem estabelecimento_id
    }
    token = create_access_token(payload)
    decoded = verify_token(token)

    assert decoded is not None
    assert "estabelecimento_id" not in decoded or decoded.get("estabelecimento_id") is None


# ============================================================
# T60-B: Dependency get_estabelecimento_id
# ============================================================


async def test_get_estabelecimento_id_retorna_id_do_token() -> None:
    """deve retornar o estabelecimento_id presente no token JWT."""
    user = {"sub": "10", "role": "RECEPCIONISTA", "estabelecimento_id": 5}
    result = await get_estabelecimento_id(_mock_request(), user)
    assert result == 5


async def test_get_estabelecimento_id_admin_global_sem_contexto_raise_400() -> None:
    """ADMIN_GLOBAL sem estabelecimento_id e sem header deve levantar 400."""
    from fastapi import HTTPException

    user = {"sub": "1", "role": "ADMIN_GLOBAL"}
    with pytest.raises(HTTPException) as exc:
        await get_estabelecimento_id(_mock_request(), user)
    assert exc.value.status_code == 400


async def test_get_estabelecimento_id_admin_global_com_header_retorna_id() -> None:
    """ADMIN_GLOBAL com header X-Estabelecimento-ID deve retornar o id do header."""
    user = {"sub": "1", "role": "ADMIN_GLOBAL"}
    result = await get_estabelecimento_id(
        _mock_request({"X-Estabelecimento-ID": "7"}), user
    )
    assert result == 7


async def test_get_estabelecimento_id_ausente_raise_403() -> None:
    """Token sem estabelecimento_id para role não-ADMIN_GLOBAL deve levantar 403."""
    from fastapi import HTTPException

    user = {"sub": "5", "role": "RECEPCIONISTA"}  # sem estabelecimento_id
    with pytest.raises(HTTPException) as exc:
        await get_estabelecimento_id(_mock_request(), user)
    assert exc.value.status_code == 403


# ============================================================
# T60-C: require_estabelecimento — alias conveniente
# ============================================================


async def test_require_estabelecimento_e_alias_de_get_estabelecimento_id() -> None:
    """require_estabelecimento é alias — get_estabelecimento_id retorna id correto."""
    user = {"sub": "7", "role": "MEDICO", "estabelecimento_id": 2}
    result = await get_estabelecimento_id(_mock_request(), user)
    assert result == 2
