"""Testes do servico de chat (T14, T16)."""

import json
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.services.ia.chat_service import ChatService, CHAT_SESSION_TTL


@pytest.fixture
def mock_db():
    db = AsyncMock()
    db.flush = AsyncMock()
    return db


@pytest.fixture
def mock_redis():
    redis = AsyncMock()
    redis.get = AsyncMock(return_value=None)
    redis.set = AsyncMock(return_value=True)
    redis.delete = AsyncMock(return_value=1)
    return redis


@pytest.fixture
def service(mock_db, mock_redis):
    return ChatService(mock_db, mock_redis)


# ============================================================
# Criar sessao (T14)
# ============================================================

async def test_criar_sessao_retorna_token(service, mock_redis):
    """RF: Criar sessao retorna session_token unico."""
    token = await service.criar_sessao()

    assert len(token) == 36  # UUID format
    mock_redis.set.assert_called_once()

    # Verificar TTL de 30 minutos
    call_kwargs = mock_redis.set.call_args[1]
    assert call_kwargs["ex"] == CHAT_SESSION_TTL


async def test_criar_sessao_salva_dados_iniciais(service, mock_redis):
    """RF: Sessao criada com dados iniciais corretos."""
    token = await service.criar_sessao(canal="WHATSAPP")

    call_args = mock_redis.set.call_args[0]
    session_data = json.loads(call_args[1])

    assert session_data["canal"] == "WHATSAPP"
    assert session_data["estado"] == "START"  # ChatEstado.START
    assert session_data["mensagens"] == []
    # dados_coletados agora tem campos estruturados
    assert "sintomas" in session_data["dados_coletados"]
    assert "especialidade" in session_data["dados_coletados"]


# ============================================================
# Memoria de sessao Redis (T16)
# ============================================================

async def test_sessao_expirada_retorna_aviso(service, mock_redis):
    """RF: Sessao expirada retorna mensagem de aviso."""
    mock_redis.get.return_value = None  # sessao nao existe

    resultado = await service.processar_mensagem("token-expirado", "ola")

    assert resultado["sessao_expirada"] is True
    assert "expirada" in resultado["resposta"].lower()


async def test_sessao_preserva_historico(service, mock_redis):
    """RF: Mensagens anteriores sao preservadas na sessao."""
    session_data = {
        "token": "test-token",
        "canal": "PORTAL",
        "mensagens": [
            {"role": "user", "content": "ola"},
            {"role": "assistant", "content": "Ola! Como posso ajudar?"},
        ],
        "estado": "COLETANDO_SINTOMAS",
        "dados_coletados": {
            "sintomas": [],
            "especialidade": None,
            "medico": None,
            "horario": None,
            "perguntas_coleta": 0,
        },
    }
    mock_redis.get.return_value = json.dumps(session_data)

    # Mockar LLM para nao fazer chamada real
    mock_response = MagicMock()
    mock_response.content = "Entendi seus sintomas."
    mock_response.response_metadata = {
        "token_usage": {"prompt_tokens": 100, "completion_tokens": 50}
    }

    with patch.object(service, "_criar_llm") as mock_llm:
        mock_llm.return_value.ainvoke = AsyncMock(return_value=mock_response)
        resultado = await service.processar_mensagem("test-token", "dor de cabeca")

    assert resultado["resposta"] == "Entendi seus sintomas."
    assert resultado["sessao_expirada"] is False

    # Verificar que sessao foi salva com historico atualizado
    saved_data = json.loads(mock_redis.set.call_args[0][1])
    assert len(saved_data["mensagens"]) == 4  # 2 anteriores + 2 novas


# ============================================================
# Encerrar sessao
# ============================================================

async def test_encerrar_sessao_remove_do_redis(service, mock_redis):
    """RF: Encerrar sessao remove dados do Redis."""
    await service.encerrar_sessao("test-token", status="AGENDOU")

    mock_redis.delete.assert_called_once_with("chat:session:test-token")
