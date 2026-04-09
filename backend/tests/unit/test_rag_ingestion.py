"""Testes de ingestao de documentos — chunking + indexacao (T23)."""

import pytest
from unittest.mock import MagicMock, AsyncMock, patch

from app.services.ia.rag import chunk_texto, indexar_documento, CHUNK_SIZE, CHUNK_OVERLAP


# ============================================================
# Chunking de texto
# ============================================================

def test_chunk_texto_simples():
    """RF: Texto curto retorna chunk unico."""
    texto = "Protocolo de atendimento para dor de cabeca."
    chunks = chunk_texto(texto, chunk_size=500)

    assert len(chunks) == 1
    assert chunks[0] == texto


def test_chunk_texto_longo():
    """RF: Texto longo e dividido em multiplos chunks."""
    texto = "A" * 1200  # 1200 caracteres
    chunks = chunk_texto(texto, chunk_size=500, overlap=50)

    assert len(chunks) >= 2
    # Cada chunk <= chunk_size
    for chunk in chunks:
        assert len(chunk) <= 500


def test_chunk_overlap_preserva_contexto():
    """RF: Overlap garante que contexto nao se perde entre chunks."""
    texto = "ABCDE" * 200  # 1000 chars
    chunks = chunk_texto(texto, chunk_size=500, overlap=100)

    # Segundo chunk deve comecar com texto que estava no final do primeiro
    assert len(chunks) >= 2
    # O inicio do segundo chunk deve ter overlap com o final do primeiro
    fim_primeiro = chunks[0][-100:]
    inicio_segundo = chunks[1][:100]
    assert fim_primeiro == inicio_segundo


def test_chunk_texto_vazio_retorna_lista_vazia():
    """Edge case: Texto vazio retorna lista vazia."""
    assert chunk_texto("") == []
    assert chunk_texto("   ") == []


def test_chunk_texto_none_retorna_lista_vazia():
    """Edge case: None retorna lista vazia."""
    assert chunk_texto(None) == []


# ============================================================
# Indexacao no Qdrant
# ============================================================

async def test_indexar_documento_cria_pontos():
    """RF: Documento indexado cria pontos no Qdrant."""
    mock_client = MagicMock()

    # Mock embeddings: retorna vetor de 1536 dimensoes para cada chunk
    async def mock_embeddings(textos):
        return [[0.1] * 1536 for _ in textos]

    texto = "Protocolo de atendimento " * 50  # texto longo para gerar chunks

    num_chunks = await indexar_documento(
        client=mock_client,
        embeddings_fn=mock_embeddings,
        documento_id="doc-001",
        titulo="Protocolo Dor de Cabeca",
        texto=texto,
    )

    assert num_chunks > 0
    mock_client.upsert.assert_called_once()

    # Verificar que os pontos tem payload correto
    call_args = mock_client.upsert.call_args
    points = call_args[1]["points"]
    assert len(points) == num_chunks
    assert points[0].payload["documento_id"] == "doc-001"
    assert points[0].payload["titulo"] == "Protocolo Dor de Cabeca"


async def test_indexar_documento_vazio_retorna_zero():
    """Edge case: Documento vazio nao indexa nada."""
    mock_client = MagicMock()

    async def mock_embeddings(textos):
        return [[0.1] * 1536 for _ in textos]

    num_chunks = await indexar_documento(
        client=mock_client,
        embeddings_fn=mock_embeddings,
        documento_id="doc-002",
        titulo="Vazio",
        texto="",
    )

    assert num_chunks == 0
    mock_client.upsert.assert_not_called()


async def test_indexar_documento_payload_tem_texto_chunk():
    """RF: Cada ponto no Qdrant contem o texto do chunk no payload."""
    mock_client = MagicMock()

    async def mock_embeddings(textos):
        return [[0.1] * 1536 for _ in textos]

    texto = "Protocolo importante sobre diagnostico."

    await indexar_documento(
        client=mock_client,
        embeddings_fn=mock_embeddings,
        documento_id="doc-003",
        titulo="Protocolo Diagnostico",
        texto=texto,
    )

    call_args = mock_client.upsert.call_args
    points = call_args[1]["points"]
    assert points[0].payload["texto"] == texto
