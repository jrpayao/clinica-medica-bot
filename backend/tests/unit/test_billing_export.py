"""Testes de exportacao CSV de billing (T29)."""

import pytest
from datetime import date
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock

from app.services.ia.billing import listar_registros


@pytest.fixture
def mock_db():
    return AsyncMock()


# ============================================================
# Listar registros para export
# ============================================================

async def test_listar_registros_sem_filtro(mock_db):
    """RF: Listar todos os registros sem filtro de data."""
    mock_records = [MagicMock(), MagicMock()]
    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = mock_records
    mock_db.execute = AsyncMock(return_value=mock_result)

    registros = await listar_registros(mock_db)

    assert len(registros) == 2
    mock_db.execute.assert_called_once()


async def test_listar_registros_com_filtro_datas(mock_db):
    """RF: Listar registros filtrados por periodo."""
    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = []
    mock_db.execute = AsyncMock(return_value=mock_result)

    registros = await listar_registros(
        mock_db,
        data_inicio=date(2026, 4, 1),
        data_fim=date(2026, 4, 30),
    )

    assert registros == []
    mock_db.execute.assert_called_once()


async def test_listar_registros_retorna_lista_vazia_quando_sem_dados(mock_db):
    """Edge case: Sem dados retorna lista vazia."""
    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = []
    mock_db.execute = AsyncMock(return_value=mock_result)

    registros = await listar_registros(mock_db)

    assert registros == []
