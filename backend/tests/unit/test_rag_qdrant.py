"""Testes do Qdrant client e collection de protocolos (T22)."""

import pytest
from unittest.mock import MagicMock, patch, AsyncMock

from app.services.ia.rag import (
    COLLECTION_NAME,
    VECTOR_SIZE,
    criar_collection_se_nao_existe,
    get_qdrant_client,
    health_check_qdrant,
)


# ============================================================
# Qdrant Client
# ============================================================

def test_get_qdrant_client_retorna_instancia():
    """RF: get_qdrant_client retorna QdrantClient configurado."""
    with patch("app.services.ia.rag.QdrantClient") as MockQdrant:
        mock_instance = MagicMock()
        MockQdrant.return_value = mock_instance

        client = get_qdrant_client()

        assert client is not None
        MockQdrant.assert_called_once()


def test_collection_name_e_protocolos_clinicos():
    """RF: Nome da collection e 'protocolos_clinicos'."""
    assert COLLECTION_NAME == "protocolos_clinicos"


def test_vector_size_compativel_com_embedding():
    """RF: VECTOR_SIZE compativel com modelo de embedding."""
    assert VECTOR_SIZE > 0
    assert isinstance(VECTOR_SIZE, int)


# ============================================================
# Criar collection
# ============================================================

def test_criar_collection_quando_nao_existe():
    """RF: Cria collection se nao existe no Qdrant."""
    mock_client = MagicMock()
    mock_client.collection_exists.return_value = False

    criar_collection_se_nao_existe(mock_client)

    mock_client.create_collection.assert_called_once()


def test_nao_recriar_collection_existente():
    """RF: Nao recria collection se ja existe."""
    mock_client = MagicMock()
    mock_client.collection_exists.return_value = True

    criar_collection_se_nao_existe(mock_client)

    mock_client.create_collection.assert_not_called()


# ============================================================
# Health check
# ============================================================

def test_health_check_ok():
    """RF: Health check retorna True quando Qdrant esta saudavel."""
    mock_client = MagicMock()
    mock_client.collection_exists.return_value = True

    result = health_check_qdrant(mock_client)

    assert result["status"] == "ok"
    assert result["collection"] == COLLECTION_NAME


def test_health_check_falha():
    """Edge case: Health check retorna False quando Qdrant falha."""
    mock_client = MagicMock()
    mock_client.collection_exists.side_effect = Exception("Connection refused")

    result = health_check_qdrant(mock_client)

    assert result["status"] == "erro"
    assert "Connection refused" in result["erro"]
