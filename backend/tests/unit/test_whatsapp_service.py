"""Testes do servico WhatsApp — templates de mensagem (T30)."""

from datetime import date, time

from app.services.whatsapp_service import (
    template_confirmacao_consulta,
    template_lembrete_consulta,
    template_cancelamento_consulta,
)


# ============================================================
# Templates de mensagem
# ============================================================

def test_template_confirmacao():
    """RF: Template de confirmacao inclui dados da consulta."""
    msg = template_confirmacao_consulta(
        paciente_nome="Maria Silva",
        medico_nome="Dr. Carlos",
        especialidade="Neurologia",
        data=date(2026, 4, 10),
        hora=time(14, 30),
        link_cancelamento="https://medbot.app/a/token123",
    )

    assert "Maria Silva" in msg
    assert "Dr. Carlos" in msg
    assert "Neurologia" in msg
    assert "10/04/2026" in msg
    assert "14:30" in msg
    assert "token123" in msg


def test_template_lembrete():
    """RF: Template de lembrete inclui data/hora e link de acao."""
    msg = template_lembrete_consulta(
        paciente_nome="Joao Santos",
        medico_nome="Dra. Ana",
        especialidade="Cardiologia",
        data=date(2026, 4, 11),
        hora=time(9, 0),
        link_confirmacao="https://medbot.app/a/conf456",
        link_cancelamento="https://medbot.app/a/canc789",
    )

    assert "Joao Santos" in msg
    assert "Dra. Ana" in msg
    assert "11/04/2026" in msg
    assert "09:00" in msg
    assert "conf456" in msg
    assert "canc789" in msg


def test_template_cancelamento():
    """RF: Template de cancelamento confirma o cancelamento."""
    msg = template_cancelamento_consulta(
        paciente_nome="Pedro Lima",
        medico_nome="Dr. Bruno",
        data=date(2026, 4, 12),
        hora=time(16, 0),
    )

    assert "Pedro Lima" in msg
    assert "Dr. Bruno" in msg
    assert "12/04/2026" in msg
    assert "cancelada" in msg.lower()


def test_template_confirmacao_sem_link_opcional():
    """Edge case: Template funciona sem link de cancelamento."""
    msg = template_confirmacao_consulta(
        paciente_nome="Ana",
        medico_nome="Dr. X",
        especialidade="Clinica Geral",
        data=date(2026, 4, 10),
        hora=time(8, 0),
    )

    assert "Ana" in msg
    assert "Dr. X" in msg
