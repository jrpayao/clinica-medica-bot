"""Testes do dashboard billing — agregacoes (T27)."""

import pytest
from decimal import Decimal
from datetime import date, datetime
from unittest.mock import AsyncMock, MagicMock

from app.services.ia.billing import (
    obter_resumo_diario,
    obter_resumo_por_modelo,
    obter_resumo_por_feature,
)


@pytest.fixture
def mock_db():
    return AsyncMock()


# ============================================================
# Resumo diario
# ============================================================

async def test_resumo_diario_retorna_totais(mock_db):
    """RF: Dashboard mostra total de tokens e custo do dia."""
    mock_result = MagicMock()
    mock_result.one.return_value = (1500, Decimal("0.005000"))
    mock_db.execute = AsyncMock(return_value=mock_result)

    resumo = await obter_resumo_diario(mock_db, data=date(2026, 4, 3))

    assert resumo["total_tokens"] == 1500
    assert resumo["total_custo_usd"] == Decimal("0.005000")
    assert resumo["data"] == "2026-04-03"


async def test_resumo_diario_sem_uso(mock_db):
    """Edge case: Dia sem uso retorna zeros."""
    mock_result = MagicMock()
    mock_result.one.return_value = (None, None)
    mock_db.execute = AsyncMock(return_value=mock_result)

    resumo = await obter_resumo_diario(mock_db, data=date(2026, 4, 3))

    assert resumo["total_tokens"] == 0
    assert resumo["total_custo_usd"] == Decimal("0")


# ============================================================
# Resumo por modelo
# ============================================================

async def test_resumo_por_modelo(mock_db):
    """RF: Dashboard mostra uso agrupado por modelo."""
    mock_result = MagicMock()
    mock_result.all.return_value = [
        ("llama3.1:8b", 8, 1000, Decimal("0.000000")),
        ("cniongolo/biomistral:latest", 3, 500, Decimal("0.000000")),
    ]
    mock_db.execute = AsyncMock(return_value=mock_result)

    resumos = await obter_resumo_por_modelo(mock_db, data=date(2026, 4, 3))

    assert len(resumos) == 2
    assert resumos[0]["modelo"] == "llama3.1:8b"
    assert resumos[0]["total_chamadas"] == 8
    assert resumos[0]["total_tokens"] == 1000
    assert resumos[1]["modelo"] == "cniongolo/biomistral:latest"


# ============================================================
# Resumo por feature
# ============================================================

async def test_resumo_por_feature(mock_db):
    """RF: Dashboard mostra uso agrupado por feature."""
    mock_result = MagicMock()
    mock_result.all.return_value = [
        ("TRIAGEM", 12, 800, Decimal("0.002000")),
        ("GERAL", 4, 200, Decimal("0.000500")),
    ]
    mock_db.execute = AsyncMock(return_value=mock_result)

    resumos = await obter_resumo_por_feature(mock_db, data=date(2026, 4, 3))

    assert len(resumos) == 2
    assert resumos[0]["feature"] == "TRIAGEM"
    assert resumos[0]["total_chamadas"] == 12
    assert resumos[0]["total_tokens"] == 800
