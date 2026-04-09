"""Testes do servico de notificacao por e-mail (T31)."""

import pytest
from datetime import date, time
from unittest.mock import AsyncMock, MagicMock, patch

from app.services.notificacao_service import (
    enviar_email,
    template_email_confirmacao,
    template_email_lembrete,
)


# ============================================================
# Templates de email
# ============================================================

def test_template_email_confirmacao():
    """RF: Email de confirmacao inclui dados da consulta."""
    assunto, corpo = template_email_confirmacao(
        paciente_nome="Maria Silva",
        medico_nome="Dr. Carlos",
        especialidade="Neurologia",
        data=date(2026, 4, 10),
        hora=time(14, 30),
        link_cancelamento="https://medbot.app/a/token123",
    )

    assert "confirmada" in assunto.lower() or "confirmação" in assunto.lower() or "confirmacao" in assunto.lower()
    assert "Maria Silva" in corpo
    assert "Dr. Carlos" in corpo
    assert "Neurologia" in corpo
    assert "10/04/2026" in corpo
    assert "14:30" in corpo


def test_template_email_lembrete():
    """RF: Email de lembrete inclui dados e links."""
    assunto, corpo = template_email_lembrete(
        paciente_nome="Joao Santos",
        medico_nome="Dra. Ana",
        especialidade="Cardiologia",
        data=date(2026, 4, 11),
        hora=time(9, 0),
        link_confirmacao="https://medbot.app/a/conf456",
        link_cancelamento="https://medbot.app/a/canc789",
    )

    assert "lembrete" in assunto.lower()
    assert "Joao Santos" in corpo
    assert "conf456" in corpo
    assert "canc789" in corpo


# ============================================================
# Envio de email via SendGrid
# ============================================================

async def test_enviar_email_sucesso():
    """RF: Email enviado via SendGrid com payload correto."""
    with patch("app.services.notificacao_service.httpx.AsyncClient") as MockClient:
        mock_client = AsyncMock()
        mock_response = MagicMock()
        mock_response.status_code = 202
        mock_client.post = AsyncMock(return_value=mock_response)
        MockClient.return_value.__aenter__ = AsyncMock(return_value=mock_client)
        MockClient.return_value.__aexit__ = AsyncMock(return_value=False)

        resultado = await enviar_email(
            destinatario="paciente@email.com",
            assunto="Atendimento confirmada",
            corpo_html="<p>Sua consulta foi confirmada</p>",
        )

        assert resultado is True
        mock_client.post.assert_called_once()

        # Verificar que o payload tem a estrutura do SendGrid
        call_args = mock_client.post.call_args
        payload = call_args[1].get("json", {})
        assert "personalizations" in payload
        assert "subject" in payload


async def test_enviar_email_falha():
    """Edge case: Falha no envio retorna False."""
    with patch("app.services.notificacao_service.httpx.AsyncClient") as MockClient:
        mock_client = AsyncMock()
        mock_response = MagicMock()
        mock_response.status_code = 400
        mock_response.text = "Bad Request"
        mock_client.post = AsyncMock(return_value=mock_response)
        MockClient.return_value.__aenter__ = AsyncMock(return_value=mock_client)
        MockClient.return_value.__aexit__ = AsyncMock(return_value=False)

        resultado = await enviar_email(
            destinatario="invalido",
            assunto="Teste",
            corpo_html="<p>teste</p>",
        )

        assert resultado is False
