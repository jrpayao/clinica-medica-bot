"""Testes de confirmacao de agendamento pelo chat (T19)."""

import pytest
from unittest.mock import AsyncMock, MagicMock

from app.services.ia.confirmacao import confirmar_agendamento_chat


@pytest.fixture
def mock_db():
    db = AsyncMock()
    db.flush = AsyncMock()
    return db


@pytest.fixture
def mock_redis():
    redis = AsyncMock()
    redis.delete = AsyncMock(return_value=1)
    return redis


# ============================================================
# Confirmacao de agendamento pelo chat
# ============================================================

async def test_confirmar_agendamento_sucesso(mock_db, mock_redis):
    """RF: Cliente confirma slot no chat, consulta e criada."""
    # Mock slot disponivel
    mock_slot = MagicMock()
    mock_slot.id = 10
    mock_slot.profissional_id = 5
    mock_slot.status = "DISPONIVEL"

    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = mock_slot
    mock_db.execute = AsyncMock(return_value=mock_result)

    resultado = await confirmar_agendamento_chat(
        db=mock_db,
        redis=mock_redis,
        session_token="test-token",
        slot_id=10,
        cliente_id=1,
        especialidade_id=3,
        triagem_resumo={"sintomas": "dor de cabeca", "urgencia": "BAIXA"},
        canal="PORTAL",
    )

    assert resultado["sucesso"] is True
    assert resultado["erro"] is None
    mock_db.add.assert_called_once()
    mock_db.flush.assert_called_once()


async def test_confirmar_agendamento_slot_indisponivel(mock_db, mock_redis):
    """RF: Slot ocupado retorna erro."""
    mock_slot = MagicMock()
    mock_slot.id = 10
    mock_slot.status = "AGENDADO"

    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = mock_slot
    mock_db.execute = AsyncMock(return_value=mock_result)

    resultado = await confirmar_agendamento_chat(
        db=mock_db,
        redis=mock_redis,
        session_token="test-token",
        slot_id=10,
        cliente_id=1,
        especialidade_id=3,
    )

    assert resultado["sucesso"] is False
    assert "indisponivel" in resultado["erro"].lower()


async def test_confirmar_agendamento_slot_inexistente(mock_db, mock_redis):
    """Edge case: Slot nao encontrado retorna erro."""
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = None
    mock_db.execute = AsyncMock(return_value=mock_result)

    resultado = await confirmar_agendamento_chat(
        db=mock_db,
        redis=mock_redis,
        session_token="test-token",
        slot_id=999,
        cliente_id=1,
        especialidade_id=3,
    )

    assert resultado["sucesso"] is False
    assert "nao encontrado" in resultado["erro"].lower()


async def test_confirmar_agendamento_encerra_sessao(mock_db, mock_redis):
    """RF: Apos confirmacao, sessao encerrada com status AGENDOU."""
    mock_slot = MagicMock()
    mock_slot.id = 10
    mock_slot.profissional_id = 5
    mock_slot.status = "DISPONIVEL"

    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = mock_slot
    mock_db.execute = AsyncMock(return_value=mock_result)

    await confirmar_agendamento_chat(
        db=mock_db,
        redis=mock_redis,
        session_token="test-token",
        slot_id=10,
        cliente_id=1,
        especialidade_id=3,
    )

    mock_redis.delete.assert_called_once_with("chat:session:test-token")


async def test_confirmar_agendamento_salva_triagem(mock_db, mock_redis):
    """RF: Triagem resumo e salva na consulta."""
    mock_slot = MagicMock()
    mock_slot.id = 10
    mock_slot.profissional_id = 5
    mock_slot.status = "DISPONIVEL"

    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = mock_slot
    mock_db.execute = AsyncMock(return_value=mock_result)

    triagem = {"sintomas": "dor de cabeca", "urgencia": "MEDIA"}

    await confirmar_agendamento_chat(
        db=mock_db,
        redis=mock_redis,
        session_token="test-token",
        slot_id=10,
        cliente_id=1,
        especialidade_id=3,
        triagem_resumo=triagem,
    )

    # Verifica que o objeto adicionado ao DB tem a triagem
    consulta_adicionada = mock_db.add.call_args[0][0]
    assert consulta_adicionada.triagem_resumo == triagem
