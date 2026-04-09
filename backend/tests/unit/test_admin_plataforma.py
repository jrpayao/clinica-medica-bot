"""Testes unitários — endpoints admin_plataforma (T134, T135, T137)."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.api.v1.endpoints.admin_plataforma import (
    _contagem_licencas_por_status,
    _contagem_usuarios_por_role,
    _total_consultas_hoje,
)


@pytest.fixture
def mock_db():
    return AsyncMock()


async def test_contagem_licencas_por_status(mock_db):
    """Deve retornar dict com contagens por status."""
    mock_result = MagicMock()
    mock_result.all.return_value = [
        ("TRIAL", 3),
        ("ATIVA", 10),
        ("EXPIRADA", 2),
    ]
    mock_db.execute = AsyncMock(return_value=mock_result)

    resultado = await _contagem_licencas_por_status(mock_db)

    assert resultado["TRIAL"] == 3
    assert resultado["ATIVA"] == 10
    assert resultado["EXPIRADA"] == 2
    assert resultado.get("SUSPENSA", 0) == 0


async def test_contagem_usuarios_por_role(mock_db):
    """Deve retornar dict com contagem por role."""
    mock_result = MagicMock()
    mock_result.all.return_value = [
        ("ADMIN_ESTABELECIMENTO", 5),
        ("RECEPCIONISTA", 8),
        ("MEDICO", 12),
    ]
    mock_db.execute = AsyncMock(return_value=mock_result)

    resultado = await _contagem_usuarios_por_role(mock_db)

    assert resultado["ADMIN_ESTABELECIMENTO"] == 5
    assert resultado["RECEPCIONISTA"] == 8
    assert resultado["MEDICO"] == 12


async def test_total_consultas_hoje_sem_pii(mock_db):
    """Retorna contagens agregadas — sem campos de nome."""
    from datetime import date

    mock_result = MagicMock()
    mock_result.all.return_value = [
        ("AGENDADA", 15),
        ("REALIZADA", 7),
        ("CANCELADA", 3),
    ]
    mock_db.execute = AsyncMock(return_value=mock_result)

    resultado = await _total_consultas_hoje(mock_db, date.today())

    assert resultado["agendadas"] == 15
    assert resultado["realizadas"] == 7
    assert resultado["canceladas"] == 3
    assert "paciente_nome" not in resultado
    assert "medico_nome" not in resultado
