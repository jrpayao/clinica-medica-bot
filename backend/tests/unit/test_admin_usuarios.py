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
