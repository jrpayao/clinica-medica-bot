"""Testes de retrieval RAG no fluxo de triagem (T24)."""

import pytest
from unittest.mock import MagicMock, AsyncMock

from app.services.ia.rag import buscar_contexto


# ============================================================
# Busca de contexto RAG
# ============================================================

async def test_buscar_contexto_retorna_chunks_relevantes():
    """RF: Busca retorna chunks relevantes com score e metadata."""
    mock_client = MagicMock()

    # Simular resultado do Qdrant
    mock_point = MagicMock()
    mock_point.payload = {
        "texto": "Protocolo: dor de cabeca persistente requer avaliacao neurologica.",
        "titulo": "Protocolo Cefaleia",
        "documento_id": "doc-001",
    }
    mock_point.score = 0.85

    mock_result = MagicMock()
    mock_result.points = [mock_point]
    mock_client.query_points.return_value = mock_result

    async def mock_embeddings(textos):
        return [[0.1] * 1536 for _ in textos]

    contextos = await buscar_contexto(
        client=mock_client,
        embeddings_fn=mock_embeddings,
        query="dor de cabeca forte",
    )

    assert len(contextos) == 1
    assert "Protocolo" in contextos[0]["texto"]
    assert contextos[0]["score"] == 0.85
    assert contextos[0]["titulo"] == "Protocolo Cefaleia"


async def test_buscar_contexto_sem_resultados():
    """Edge case: Busca sem resultados retorna lista vazia."""
    mock_client = MagicMock()

    mock_result = MagicMock()
    mock_result.points = []
    mock_client.query_points.return_value = mock_result

    async def mock_embeddings(textos):
        return [[0.1] * 1536 for _ in textos]

    contextos = await buscar_contexto(
        client=mock_client,
        embeddings_fn=mock_embeddings,
        query="sintoma muito raro inexistente",
    )

    assert contextos == []


async def test_buscar_contexto_respeita_top_k():
    """RF: Busca respeita limite de resultados top_k."""
    mock_client = MagicMock()

    mock_points = []
    for i in range(5):
        point = MagicMock()
        point.payload = {
            "texto": f"Protocolo {i}",
            "titulo": f"Doc {i}",
            "documento_id": f"doc-{i}",
        }
        point.score = 0.9 - (i * 0.05)
        mock_points.append(point)

    mock_result = MagicMock()
    mock_result.points = mock_points[:3]  # Qdrant respeita limit
    mock_client.query_points.return_value = mock_result

    async def mock_embeddings(textos):
        return [[0.1] * 1536 for _ in textos]

    contextos = await buscar_contexto(
        client=mock_client,
        embeddings_fn=mock_embeddings,
        query="sintomas gerais",
        top_k=3,
    )

    assert len(contextos) <= 3


async def test_buscar_contexto_usa_score_threshold():
    """RF: Busca passa score_threshold para o Qdrant."""
    mock_client = MagicMock()
    mock_result = MagicMock()
    mock_result.points = []
    mock_client.query_points.return_value = mock_result

    async def mock_embeddings(textos):
        return [[0.1] * 1536 for _ in textos]

    await buscar_contexto(
        client=mock_client,
        embeddings_fn=mock_embeddings,
        query="teste",
        score_threshold=0.8,
    )

    call_kwargs = mock_client.query_points.call_args[1]
    assert call_kwargs["score_threshold"] == 0.8


async def test_buscar_contexto_retorna_documento_id():
    """RF: Cada resultado inclui documento_id para rastreabilidade."""
    mock_client = MagicMock()

    mock_point = MagicMock()
    mock_point.payload = {
        "texto": "Texto relevante",
        "titulo": "Doc Teste",
        "documento_id": "prot-123",
    }
    mock_point.score = 0.92

    mock_result = MagicMock()
    mock_result.points = [mock_point]
    mock_client.query_points.return_value = mock_result

    async def mock_embeddings(textos):
        return [[0.1] * 1536 for _ in textos]

    contextos = await buscar_contexto(
        client=mock_client,
        embeddings_fn=mock_embeddings,
        query="busca teste",
    )

    assert contextos[0]["documento_id"] == "prot-123"
