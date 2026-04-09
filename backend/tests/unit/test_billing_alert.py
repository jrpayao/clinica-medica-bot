"""Testes do job de alertas de billing (T28)."""

import pytest
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

from app.workers.billing_alert import (
    verificar_limites_custo,
    ALERTA_80_MSG,
    ALERTA_100_MSG,
)


# ============================================================
# Verificacao de limites de custo
# ============================================================

async def test_custo_abaixo_80_sem_alerta():
    """RF: Custo abaixo de 80% nao gera alerta."""
    resultado = await verificar_limites_custo(
        custo_atual=Decimal("5.00"),
        limite_diario=Decimal("10.00"),
    )

    assert resultado["alerta"] is False
    assert resultado["acao"] is None


async def test_custo_em_80_gera_alerta():
    """RF: Custo em 80% do limite gera alerta de warning."""
    resultado = await verificar_limites_custo(
        custo_atual=Decimal("8.00"),
        limite_diario=Decimal("10.00"),
    )

    assert resultado["alerta"] is True
    assert resultado["nivel"] == "warning"
    assert "80%" in resultado["mensagem"]


async def test_custo_em_100_gera_alerta_critico():
    """RF: Custo em 100% gera alerta critico."""
    resultado = await verificar_limites_custo(
        custo_atual=Decimal("10.00"),
        limite_diario=Decimal("10.00"),
    )

    assert resultado["alerta"] is True
    assert resultado["nivel"] == "critical"
    assert resultado["desativar_premium"] is True


async def test_custo_acima_100_desativa_premium():
    """RF: Custo acima de 100% tambem desativa premium."""
    resultado = await verificar_limites_custo(
        custo_atual=Decimal("12.50"),
        limite_diario=Decimal("10.00"),
    )

    assert resultado["desativar_premium"] is True
    assert resultado["percentual"] > 100


async def test_custo_entre_80_e_100_nao_desativa():
    """RF: Custo entre 80-100% alerta mas NAO desativa premium."""
    resultado = await verificar_limites_custo(
        custo_atual=Decimal("9.00"),
        limite_diario=Decimal("10.00"),
    )

    assert resultado["alerta"] is True
    assert resultado["desativar_premium"] is False


async def test_limite_zero_nao_divide_por_zero():
    """Edge case: Limite zero nao causa erro."""
    resultado = await verificar_limites_custo(
        custo_atual=Decimal("1.00"),
        limite_diario=Decimal("0"),
    )

    assert resultado["alerta"] is False
