"""Testes do servico de billing (T14/T25)."""

import pytest
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock

from app.services.ia.billing import calcular_custo, registrar_uso


def test_calcular_custo_llama():
    """RF: Em Ollama local, custo do llama e zero."""
    custo = calcular_custo(
        "llama3.1:8b",
        prompt_tokens=1000,
        completion_tokens=500,
    )
    assert custo == Decimal("0")


def test_calcular_custo_biomistral():
    """RF: Em Ollama local, custo do biomistral e zero."""
    custo = calcular_custo(
        "cniongolo/biomistral:latest",
        prompt_tokens=500,
        completion_tokens=200,
    )
    assert custo == Decimal("0")


def test_calcular_custo_nomic_embed():
    """RF: Embeddings locais tambem devem custar zero em dev."""
    custo = calcular_custo(
        "nomic-embed-text",
        prompt_tokens=1000,
        completion_tokens=500,
    )
    assert custo == Decimal("0")


def test_calcular_custo_modelo_desconhecido():
    """Edge case: modelo sem pricing retorna 0."""
    custo = calcular_custo("modelo/inexistente", prompt_tokens=1000, completion_tokens=500)
    assert custo == Decimal("0")


async def test_registrar_uso_persiste_no_banco():
    """RF: TODA chamada LLM registra tokens no banco."""
    db = AsyncMock()
    db.flush = AsyncMock()

    registro = await registrar_uso(
        db=db,
        session_id=1,
        modelo="llama3.1:8b",
        feature="TRIAGEM",
        prompt_tokens=100,
        completion_tokens=50,
    )

    db.add.assert_called_once()
    db.flush.assert_called_once()
    assert registro.total_tokens == 150
    assert registro.cost_usd == Decimal("0")


async def test_registrar_uso_feature_invalida_usa_geral():
    """Edge case: feature invalida mapeia para GERAL."""
    db = AsyncMock()
    db.flush = AsyncMock()

    registro = await registrar_uso(
        db=db,
        session_id=1,
        modelo="llama3.1:8b",
        feature="feature_invalida",
        prompt_tokens=100,
        completion_tokens=50,
    )

    assert registro.feature.value == "GERAL"
