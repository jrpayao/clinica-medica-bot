"""Testes dos jobs de lembretes D-1 e H-2 (T32)."""

import pytest
from datetime import date, time, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

from app.workers.lembretes import (
    buscar_consultas_para_lembrete_d1,
    buscar_consultas_para_lembrete_h2,
    enviar_lembrete,
)


@pytest.fixture
def mock_db():
    return AsyncMock()


def _mock_consulta(
    consulta_id=1,
    paciente_nome="Maria",
    paciente_telefone="5511999990000",
    paciente_email="maria@email.com",
    medico_nome="Dr. Carlos",
    especialidade="Neurologia",
    slot_data=date(2026, 4, 10),
    slot_hora=time(14, 30),
):
    c = MagicMock()
    c.id = consulta_id
    c.paciente = MagicMock()
    c.paciente.nome = paciente_nome
    c.paciente.telefone = paciente_telefone
    c.paciente.email = paciente_email
    c.medico = MagicMock()
    c.medico.nome = medico_nome
    c.especialidade = MagicMock()
    c.especialidade.nome = especialidade
    c.slot = MagicMock()
    c.slot.data = slot_data
    c.slot.hora_inicio = slot_hora
    return c


# ============================================================
# Buscar consultas para lembrete
# ============================================================

async def test_buscar_consultas_d1(mock_db):
    """RF: Busca consultas de amanha para lembrete D-1."""
    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = [_mock_consulta()]
    mock_db.execute = AsyncMock(return_value=mock_result)

    consultas = await buscar_consultas_para_lembrete_d1(mock_db)

    assert len(consultas) == 1
    mock_db.execute.assert_called_once()


async def test_buscar_consultas_h2(mock_db):
    """RF: Busca consultas nas proximas 2 horas para lembrete H-2."""
    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = [_mock_consulta()]
    mock_db.execute = AsyncMock(return_value=mock_result)

    consultas = await buscar_consultas_para_lembrete_h2(mock_db)

    assert len(consultas) == 1


# ============================================================
# Enviar lembrete
# ============================================================

async def test_enviar_lembrete_whatsapp_e_email():
    """RF: Lembrete envia tanto WhatsApp quanto email."""
    consulta = _mock_consulta()

    with (
        patch("app.workers.lembretes.enviar_mensagem_whatsapp", new_callable=AsyncMock) as mock_wa,
        patch("app.workers.lembretes.enviar_email", new_callable=AsyncMock) as mock_email,
    ):
        mock_wa.return_value = True
        mock_email.return_value = True

        await enviar_lembrete(consulta, tipo="D-1")

        mock_wa.assert_called_once()
        mock_email.assert_called_once()


async def test_enviar_lembrete_falha_whatsapp_nao_impede_email():
    """RF: Falha no WhatsApp nao impede envio do email."""
    consulta = _mock_consulta()

    with (
        patch("app.workers.lembretes.enviar_mensagem_whatsapp", new_callable=AsyncMock) as mock_wa,
        patch("app.workers.lembretes.enviar_email", new_callable=AsyncMock) as mock_email,
    ):
        mock_wa.return_value = False
        mock_email.return_value = True

        await enviar_lembrete(consulta, tipo="D-1")

        # Ambos sao chamados independentemente
        mock_wa.assert_called_once()
        mock_email.assert_called_once()
