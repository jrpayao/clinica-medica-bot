"""Testes do WebSocket de chat (T20)."""

import json
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from httpx import ASGITransport, AsyncClient
from starlette.testclient import TestClient

from app.main import app


@pytest.fixture
def mock_redis():
    redis = AsyncMock()
    redis.get = AsyncMock(return_value=None)
    redis.set = AsyncMock(return_value=True)
    redis.delete = AsyncMock(return_value=1)
    return redis


# ============================================================
# WebSocket endpoint
# ============================================================

def test_websocket_conexao_e_mensagem(mock_redis):
    """RF: WS /v1/chat/ws/{token} aceita conexao e processa mensagem."""
    session_data = json.dumps({
        "token": "test-token-ws",
        "canal": "PORTAL",
        "mensagens": [],
        "etapa": "saudacao",
        "dados_coletados": {},
    })
    mock_redis.get = AsyncMock(return_value=session_data)

    mock_response = MagicMock()
    mock_response.content = "Ola! Como posso ajudar?"
    mock_response.response_metadata = {
        "token_usage": {"prompt_tokens": 50, "completion_tokens": 20}
    }

    with (
        patch("app.api.v1.endpoints.chat.get_redis_client", return_value=mock_redis),
        patch("app.api.v1.endpoints.chat.ChatService") as MockChatService,
    ):
        mock_service = AsyncMock()
        mock_service.processar_mensagem = AsyncMock(return_value={
            "resposta": "Ola! Como posso ajudar?",
            "etapa": "saudacao",
            "modelo_usado": "meta-llama/llama-3.3-70b-instruct",
            "sessao_expirada": False,
        })
        MockChatService.return_value = mock_service

        client = TestClient(app)
        with client.websocket_connect("/v1/chat/ws/test-token-ws") as ws:
            ws.send_json({"mensagem": "Ola"})
            data = ws.receive_json()

            assert data["resposta"] == "Ola! Como posso ajudar?"
            assert data["sessao_expirada"] is False


def test_websocket_sessao_expirada(mock_redis):
    """RF: Sessao expirada retorna aviso e fecha conexao."""
    mock_redis.get = AsyncMock(return_value=None)

    with (
        patch("app.api.v1.endpoints.chat.get_redis_client", return_value=mock_redis),
        patch("app.api.v1.endpoints.chat.ChatService") as MockChatService,
    ):
        mock_service = AsyncMock()
        mock_service.processar_mensagem = AsyncMock(return_value={
            "resposta": "Sessao expirada. Por favor, inicie uma nova conversa.",
            "sessao_expirada": True,
        })
        MockChatService.return_value = mock_service

        client = TestClient(app)
        with client.websocket_connect("/v1/chat/ws/token-expirado") as ws:
            ws.send_json({"mensagem": "Ola"})
            data = ws.receive_json()

            assert data["sessao_expirada"] is True


def test_websocket_criar_sessao():
    """RF: POST /v1/chat/sessao cria nova sessao e retorna token."""
    from unittest.mock import MagicMock
    from app.api.v1.dependencies import verificar_licenca_ativa

    mock_redis = AsyncMock()
    mock_redis.set = AsyncMock(return_value=True)

    # chat.router tem _LICENCA_DEP (verificar_licenca_ativa) no nível do router.
    # O endpoint /sessao é público (pacientes anônimos), então sobrescrevemos a
    # dependency de licença para não exigir JWT nos testes de unidade do endpoint.
    mock_licenca = MagicMock()
    app.dependency_overrides[verificar_licenca_ativa] = lambda: mock_licenca

    try:
        with (
            patch("app.api.v1.endpoints.chat.get_redis_client", return_value=mock_redis),
            patch("app.api.v1.endpoints.chat.ChatService") as MockChatService,
        ):
            mock_service = AsyncMock()
            mock_service.criar_sessao = AsyncMock(return_value="uuid-test-token")
            MockChatService.return_value = mock_service

            client = TestClient(app)
            response = client.post(
                "/v1/chat/sessao",
                json={"canal": "PORTAL", "estabelecimento_id": 1},
            )

            assert response.status_code == 201
            assert response.json()["session_token"] == "uuid-test-token"
    finally:
        app.dependency_overrides.pop(verificar_licenca_ativa, None)
