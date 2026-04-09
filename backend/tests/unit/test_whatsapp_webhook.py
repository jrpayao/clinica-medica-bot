"""Testes do webhook WhatsApp — Evolution API (T21)."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.services.whatsapp_service import (
    extrair_mensagem_evolution,
    enviar_mensagem_whatsapp,
)


# ============================================================
# Parsing do payload Evolution API
# ============================================================

def test_extrair_mensagem_texto():
    """RF: Extrair mensagem de texto do payload Evolution API."""
    payload = {
        "event": "messages.upsert",
        "data": {
            "key": {
                "remoteJid": "5511999998888@s.whatsapp.net",
                "fromMe": False,
                "id": "msg-id-123",
            },
            "message": {
                "conversation": "Ola, quero agendar uma consulta",
            },
            "messageType": "conversation",
        },
    }

    resultado = extrair_mensagem_evolution(payload)

    assert resultado["telefone"] == "5511999998888"
    assert resultado["mensagem"] == "Ola, quero agendar uma consulta"
    assert resultado["from_me"] is False


def test_extrair_mensagem_extended_text():
    """RF: Extrair mensagem de extendedTextMessage."""
    payload = {
        "event": "messages.upsert",
        "data": {
            "key": {
                "remoteJid": "5511888887777@s.whatsapp.net",
                "fromMe": False,
                "id": "msg-id-456",
            },
            "message": {
                "extendedTextMessage": {
                    "text": "Estou com dor de cabeca",
                },
            },
            "messageType": "extendedTextMessage",
        },
    }

    resultado = extrair_mensagem_evolution(payload)

    assert resultado["telefone"] == "5511888887777"
    assert resultado["mensagem"] == "Estou com dor de cabeca"


def test_extrair_mensagem_from_me_ignorada():
    """RF: Mensagens enviadas pelo bot sao ignoradas."""
    payload = {
        "event": "messages.upsert",
        "data": {
            "key": {
                "remoteJid": "5511999998888@s.whatsapp.net",
                "fromMe": True,
                "id": "msg-id-789",
            },
            "message": {"conversation": "resposta do bot"},
            "messageType": "conversation",
        },
    }

    resultado = extrair_mensagem_evolution(payload)

    assert resultado is None


def test_extrair_mensagem_evento_nao_mensagem():
    """Edge case: Evento que nao e mensagem retorna None."""
    payload = {
        "event": "connection.update",
        "data": {"state": "open"},
    }

    resultado = extrair_mensagem_evolution(payload)

    assert resultado is None


def test_extrair_telefone_sem_sufixo():
    """RF: Telefone extraido sem @s.whatsapp.net."""
    payload = {
        "event": "messages.upsert",
        "data": {
            "key": {
                "remoteJid": "5521977776666@s.whatsapp.net",
                "fromMe": False,
                "id": "msg-id",
            },
            "message": {"conversation": "teste"},
            "messageType": "conversation",
        },
    }

    resultado = extrair_mensagem_evolution(payload)

    assert "@" not in resultado["telefone"]


# ============================================================
# Envio de mensagem via Evolution API
# ============================================================

async def test_enviar_mensagem_whatsapp():
    """RF: Enviar mensagem via Evolution API com payload correto."""
    with patch("app.services.whatsapp_service.httpx.AsyncClient") as MockClient:
        mock_client = AsyncMock()
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"key": {"id": "sent-msg-id"}}
        mock_client.post = AsyncMock(return_value=mock_response)
        MockClient.return_value.__aenter__ = AsyncMock(return_value=mock_client)
        MockClient.return_value.__aexit__ = AsyncMock(return_value=False)

        resultado = await enviar_mensagem_whatsapp(
            telefone="5511999998888",
            mensagem="Sua consulta foi agendada!",
        )

        assert resultado is True
        mock_client.post.assert_called_once()
