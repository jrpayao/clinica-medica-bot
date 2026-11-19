"""Testes unitários — admin_usuarios endpoints (T136)."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from app.api.v1.endpoints.admin_usuarios import _validar_role_permitido


def test_validar_role_permitido_aceita_recepcionista():
    assert _validar_role_permitido("RECEPCIONISTA") is True


def test_validar_role_permitido_aceita_medico():
    assert _validar_role_permitido("MEDICO") is True


def test_validar_role_permitido_rejeita_admin_global():
    assert _validar_role_permitido("ADMIN_GLOBAL") is False


def test_validar_role_permitido_rejeita_admin_estabelecimento():
    assert _validar_role_permitido("ADMIN_ESTABELECIMENTO") is False


# ---------------------------------------------------------------------------
# Escopo da listagem — ADMIN_GLOBAL enxerga a plataforma inteira
# ---------------------------------------------------------------------------


def test_escopo_admin_estabelecimento_ve_apenas_subordinados_da_unidade():
    from app.api.v1.endpoints.admin_usuarios import _escopo_listagem

    assert _escopo_listagem("ADMIN_ESTABELECIMENTO", 2) == (2, True)


def test_escopo_admin_global_sem_filtro_ve_todos_os_usuarios():
    from app.api.v1.endpoints.admin_usuarios import _escopo_listagem

    assert _escopo_listagem("ADMIN_GLOBAL", None) == (None, False)


def test_escopo_admin_global_escopado_ve_todos_da_unidade():
    from app.api.v1.endpoints.admin_usuarios import _escopo_listagem

    assert _escopo_listagem("ADMIN_GLOBAL", 1) == (1, False)
