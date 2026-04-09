"""Testes unitários — Dashboard Gerencial (T118).

Cobre:
- obter_proximas_consultas: retorna apenas consultas AGENDADA futuras, máx 5
- obter_taxa_ocupacao: percentual correto, sem divisão por zero
- calcular_alertas: alerta de urgência ALTA/EMERGENCIA, custo alto, sem alertas
"""

from datetime import date, time
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.api.v1.endpoints.admin_dashboard import (
    calcular_alertas,
    obter_proximas_consultas,
    obter_taxa_ocupacao,
)


@pytest.fixture
def mock_db():
    return AsyncMock()


# ============================================================
# obter_proximas_consultas
# ============================================================

async def test_proximas_consultas_retorna_formato_correto(mock_db):
    """RF-03: próximas consultas incluem hora, paciente, médico, especialidade, urgência."""
    mock_result = MagicMock()
    mock_result.all.return_value = [
        (42, time(14, 30), "João Silva", "Dr. Carlos", "Cardiologia", "MEDIA", "AGENDADA"),
        (43, time(15, 0),  "Maria Souza", "Dra. Ana",  "Clínica Geral", "BAIXA", "AGENDADA"),
    ]
    mock_db.execute = AsyncMock(return_value=mock_result)

    resultado = await obter_proximas_consultas(
        mock_db, data=date(2026, 4, 8), hora_atual=time(13, 0), estabelecimento_id=1
    )

    assert len(resultado) == 2
    assert resultado[0]["atendimento_id"] == 42
    assert resultado[0]["hora_inicio"] == "14:30"
    assert resultado[0]["cliente_nome"] == "João Silva"
    assert resultado[0]["profissional_nome"] == "Dr. Carlos"
    assert resultado[0]["especialidade_nome"] == "Cardiologia"
    assert resultado[0]["urgencia"] == "MEDIA"
    assert resultado[0]["status"] == "AGENDADA"


async def test_proximas_consultas_sem_dados_retorna_lista_vazia(mock_db):
    """Edge case: sem consultas futuras → lista vazia."""
    mock_result = MagicMock()
    mock_result.all.return_value = []
    mock_db.execute = AsyncMock(return_value=mock_result)

    resultado = await obter_proximas_consultas(
        mock_db, data=date(2026, 4, 8), hora_atual=time(23, 0), estabelecimento_id=None
    )

    assert resultado == []


async def test_proximas_consultas_filtra_por_estabelecimento(mock_db):
    """RF-RNF02: filtro de estabelecimento aplicado na query."""
    mock_result = MagicMock()
    mock_result.all.return_value = []
    mock_db.execute = AsyncMock(return_value=mock_result)

    await obter_proximas_consultas(
        mock_db, data=date(2026, 4, 8), hora_atual=time(8, 0), estabelecimento_id=5
    )

    mock_db.execute.assert_called_once()


# ============================================================
# obter_taxa_ocupacao
# ============================================================

async def test_taxa_ocupacao_calcula_percentual(mock_db):
    """RF-04: taxa = slots_ocupados / total_slots * 100."""
    mock_result = MagicMock()
    # retorna [(status, contagem), ...]
    mock_result.all.return_value = [
        ("DISPONIVEL", 4),
        ("AGENDADO",   6),
        ("BLOQUEADO",  2),
    ]
    mock_db.execute = AsyncMock(return_value=mock_result)

    taxa = await obter_taxa_ocupacao(mock_db, data=date(2026, 4, 8), estabelecimento_id=None)

    # total_slots = DISPONIVEL + AGENDADO = 10 (BLOQUEADO não conta)
    # slots_ocupados = AGENDADO = 6
    assert taxa["total_slots"] == 10
    assert taxa["slots_ocupados"] == 6
    assert taxa["percentual"] == 60.0


async def test_taxa_ocupacao_sem_slots_retorna_zero(mock_db):
    """Edge case: sem slots no dia → percentual 0, sem divisão por zero."""
    mock_result = MagicMock()
    mock_result.all.return_value = []
    mock_db.execute = AsyncMock(return_value=mock_result)

    taxa = await obter_taxa_ocupacao(mock_db, data=date(2026, 4, 8), estabelecimento_id=None)

    assert taxa["total_slots"] == 0
    assert taxa["slots_ocupados"] == 0
    assert taxa["percentual"] == 0.0


# ============================================================
# calcular_alertas
# ============================================================

def test_alertas_urgencia_alta_gera_alerta():
    """RF-02: urgências ALTA/EMERGENCIA geram alerta."""
    alertas = calcular_alertas(
        urgencias_criticas=3,
        pendentes_confirmacao=0,
        custo_atual=0.5,
        daily_limit=10.0,
    )

    tipos = [a["tipo"] for a in alertas]
    assert "urgencia_alta" in tipos
    alerta = next(a for a in alertas if a["tipo"] == "urgencia_alta")
    assert alerta["contagem"] == 3
    assert "/consultas" in alerta["link"]


def test_alertas_custo_alto_gera_alerta():
    """RF-02: custo >= 80% do limite diário gera alerta de billing."""
    alertas = calcular_alertas(
        urgencias_criticas=0,
        pendentes_confirmacao=0,
        custo_atual=8.5,
        daily_limit=10.0,
    )

    tipos = [a["tipo"] for a in alertas]
    assert "custo_alto" in tipos
    alerta = next(a for a in alertas if a["tipo"] == "custo_alto")
    assert "/billing" in alerta["link"]


def test_alertas_pendentes_gera_alerta():
    """RF-02: consultas pendentes de confirmação geram alerta."""
    alertas = calcular_alertas(
        urgencias_criticas=0,
        pendentes_confirmacao=4,
        custo_atual=1.0,
        daily_limit=10.0,
    )

    tipos = [a["tipo"] for a in alertas]
    assert "pendente_confirmacao" in tipos


def test_alertas_sem_problemas_retorna_lista_vazia():
    """RF-02: sem alertas → lista vazia (seção não exibida no frontend)."""
    alertas = calcular_alertas(
        urgencias_criticas=0,
        pendentes_confirmacao=0,
        custo_atual=1.0,
        daily_limit=10.0,
    )

    assert alertas == []


def test_alertas_custo_exatamente_80pct_gera_alerta():
    """Edge case: exatamente 80% do limite já dispara alerta."""
    alertas = calcular_alertas(
        urgencias_criticas=0,
        pendentes_confirmacao=0,
        custo_atual=8.0,
        daily_limit=10.0,
    )

    tipos = [a["tipo"] for a in alertas]
    assert "custo_alto" in tipos


async def test_proximas_consultas_modo_global_sem_pii(mock_db):
    """Segurança: est_id=None não expõe paciente_nome nem medico_nome."""
    mock_result = MagicMock()
    mock_result.all.return_value = [
        (42, time(14, 30), "João Silva", "Dr. Carlos", "Cardiologia", "MEDIA", "AGENDADA"),
    ]
    mock_db.execute = AsyncMock(return_value=mock_result)

    resultado = await obter_proximas_consultas(
        mock_db, data=date(2026, 4, 8), hora_atual=time(13, 0), estabelecimento_id=None
    )

    assert resultado == [], "modo global deve retornar lista vazia — sem PII"
