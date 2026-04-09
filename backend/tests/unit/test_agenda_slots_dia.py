"""Testes unitários — GET /agenda/slots/dia/{data} (T121).

Cobre:
- listar_slots_dia: retorna slots do dia com consulta embutida
- listar_slots_dia: retorna slots livres (consulta = None)
- listar_slots_dia: filtro por profissional_id
- listar_slots_dia: CPF mascarado no retorno
- listar_slots_dia: dia sem slots retorna lista vazia
"""

from datetime import date, time
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.services.agenda_service import listar_slots_dia


@pytest.fixture
def mock_db():
    return AsyncMock()


def _row(
    slot_id=1,
    profissional_id=10,
    medico_nome="Dr. Carlos",
    especialidade_nome="Cardiologia",
    data=date(2026, 4, 8),
    hora_inicio=time(9, 0),
    hora_fim=time(9, 30),
    slot_status="DISPONIVEL",
    consulta_id=None,
    paciente_nome=None,
    cpf=None,
    urgencia=None,
    consulta_status=None,
    canal_origem=None,
    triagem_resumo=None,
    observacoes=None,
    created_at=None,
):
    return (
        slot_id, profissional_id, medico_nome, especialidade_nome,
        data, hora_inicio, hora_fim, slot_status,
        consulta_id, paciente_nome, cpf,
        urgencia, consulta_status, canal_origem,
        triagem_resumo, observacoes, created_at,
    )


async def test_slots_dia_retorna_slot_com_consulta(mock_db):
    """RF-01: slot AGENDADO retorna dados da consulta embutidos."""
    mock_result = MagicMock()
    mock_result.all.return_value = [
        _row(
            slot_id=1, slot_status="AGENDADO",
            consulta_id=42, paciente_nome="João Silva",
            cpf="12345678901", urgencia="MEDIA",
            consulta_status="AGENDADA", canal_origem="PORTAL",
        )
    ]
    mock_db.execute = AsyncMock(return_value=mock_result)

    slots = await listar_slots_dia(mock_db, data=date(2026, 4, 8), estabelecimento_id=1)

    assert len(slots) == 1
    assert slots[0]["id"] == 1
    assert slots[0]["status"] == "AGENDADO"
    assert slots[0]["atendimento"] is not None
    assert slots[0]["atendimento"]["id"] == 42
    assert slots[0]["atendimento"]["cliente_nome"] == "João Silva"


async def test_slots_dia_retorna_slot_livre(mock_db):
    """RF-01: slot DISPONIVEL retorna consulta=None."""
    mock_result = MagicMock()
    mock_result.all.return_value = [
        _row(slot_id=2, slot_status="DISPONIVEL", consulta_id=None)
    ]
    mock_db.execute = AsyncMock(return_value=mock_result)

    slots = await listar_slots_dia(mock_db, data=date(2026, 4, 8), estabelecimento_id=1)

    assert slots[0]["atendimento"] is None


async def test_slots_dia_cpf_mascarado(mock_db):
    """Segurança: CPF não pode aparecer completo no retorno."""
    mock_result = MagicMock()
    mock_result.all.return_value = [
        _row(consulta_id=1, cpf="12345678901", consulta_status="AGENDADA")
    ]
    mock_db.execute = AsyncMock(return_value=mock_result)

    slots = await listar_slots_dia(mock_db, data=date(2026, 4, 8), estabelecimento_id=1)

    cpf_retornado = slots[0]["atendimento"]["cliente_cpf_mascarado"]
    assert "12345678901" not in cpf_retornado
    assert "*" in cpf_retornado


async def test_slots_dia_vazio(mock_db):
    """Edge case: dia sem slots retorna lista vazia."""
    mock_result = MagicMock()
    mock_result.all.return_value = []
    mock_db.execute = AsyncMock(return_value=mock_result)

    slots = await listar_slots_dia(mock_db, data=date(2026, 4, 8), estabelecimento_id=1)

    assert slots == []


async def test_slots_dia_filtro_medico(mock_db):
    """RF-01: ?profissional_id=N aplica filtro na query."""
    mock_result = MagicMock()
    mock_result.all.return_value = []
    mock_db.execute = AsyncMock(return_value=mock_result)

    await listar_slots_dia(
        mock_db, data=date(2026, 4, 8), estabelecimento_id=1, profissional_id=5
    )

    mock_db.execute.assert_called_once()


async def test_slots_dia_hora_formatada(mock_db):
    """RF-01: hora_inicio retornada como string HH:MM."""
    mock_result = MagicMock()
    mock_result.all.return_value = [
        _row(hora_inicio=time(14, 30), hora_fim=time(15, 0))
    ]
    mock_db.execute = AsyncMock(return_value=mock_result)

    slots = await listar_slots_dia(mock_db, data=date(2026, 4, 8), estabelecimento_id=1)

    assert slots[0]["hora_inicio"] == "14:30"
    assert slots[0]["hora_fim"] == "15:00"
