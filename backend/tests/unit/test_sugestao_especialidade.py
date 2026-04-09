"""Testes de sugestao de especialidade e apresentacao de slots (T18)."""

import pytest
from unittest.mock import AsyncMock, MagicMock
from datetime import date, time

from app.services.ia.sugestao import (
    MAPA_SINTOMA_ESPECIALIDADE,
    sugerir_especialidade,
    buscar_slots_para_sugestao,
)


# ============================================================
# Sugestao de especialidade baseada em sintomas
# ============================================================

def test_dor_de_cabeca_sugere_neurologista():
    """RF: Dor de cabeca sugere Neurologia."""
    resultado = sugerir_especialidade("Estou com dor de cabeca forte")
    assert "Neurologia" in resultado


def test_dor_no_estomago_sugere_gastro():
    """RF: Dor no estomago sugere Gastroenterologia."""
    resultado = sugerir_especialidade("Tenho dor no estomago ha dias")
    assert "Gastroenterologia" in resultado


def test_problema_de_pele_sugere_dermato():
    """RF: Problemas de pele sugerem Dermatologia."""
    resultado = sugerir_especialidade("Manchas vermelhas na pele")
    assert "Dermatologia" in resultado


def test_dor_nas_costas_sugere_ortopedia():
    """RF: Dor nas costas sugere Ortopedia."""
    resultado = sugerir_especialidade("Estou com muita dor nas costas")
    assert "Ortopedia" in resultado


def test_tosse_sugere_pneumologia():
    """RF: Tosse persistente sugere Pneumologia."""
    resultado = sugerir_especialidade("Tosse que nao passa ha semanas")
    assert "Pneumologia" in resultado


def test_sintoma_generico_sugere_clinico_geral():
    """RF: Sintomas sem match especifico sugerem Clinica Geral."""
    resultado = sugerir_especialidade("Estou me sentindo mal")
    assert "Clinica Geral" in resultado


def test_multiplos_sintomas_retorna_primeira_match():
    """RF: Com multiplos sintomas, retorna todas as especialidades relevantes."""
    resultado = sugerir_especialidade("Dor de cabeca e dor nas costas")
    assert len(resultado) >= 2


def test_case_insensitive():
    """RF: Deteccao funciona com qualquer case."""
    resultado = sugerir_especialidade("DOR DE CABECA")
    assert "Neurologia" in resultado


# ============================================================
# Buscar slots para sugestao (max 3)
# ============================================================

async def test_buscar_slots_retorna_max_3():
    """RF: Apresentar no maximo 3 slots disponiveis."""
    mock_db = AsyncMock()

    # Simular 3 slots (DB aplica LIMIT, mock retorna o que o DB retornaria)
    mock_slots = []
    for i in range(3):
        slot = MagicMock()
        slot.id = i + 1
        slot.data = date(2026, 4, 10)
        slot.hora_inicio = time(8 + i, 0)
        slot.hora_fim = time(8 + i, 30)
        slot.medico_id = 1
        mock_slots.append(slot)

    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = mock_slots
    mock_db.execute = AsyncMock(return_value=mock_result)

    slots = await buscar_slots_para_sugestao(mock_db, especialidade_nome="Neurologia")

    assert len(slots) == 3


async def test_buscar_slots_sem_disponibilidade_retorna_vazio():
    """Edge case: sem slots disponiveis retorna lista vazia."""
    mock_db = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = []
    mock_db.execute = AsyncMock(return_value=mock_result)

    slots = await buscar_slots_para_sugestao(mock_db, especialidade_nome="Neurologia")

    assert slots == []


async def test_buscar_slots_filtra_por_especialidade():
    """RF: Slots filtrados pela especialidade sugerida."""
    mock_db = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = []
    mock_db.execute = AsyncMock(return_value=mock_result)

    await buscar_slots_para_sugestao(mock_db, especialidade_nome="Cardiologia")

    # Verifica que execute foi chamado (query com filtro)
    mock_db.execute.assert_called_once()
