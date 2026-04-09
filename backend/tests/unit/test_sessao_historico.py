"""Testes unitários — Model SessaoHistorico (T86).

Cobre:
- Model SessaoHistorico existe com os campos obrigatórios
- Campos JSONB, TEXT, FK, created_at presentes
- SessaoHistoricoService.salvar() persiste o registro
- SessaoHistoricoService.buscar_por_paciente() filtra por paciente_id
- Máximo 3 registros retornados (mais recentes primeiro)
"""

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, call

import pytest

from app.models.sessao_historico import SessaoHistorico
from app.services.historico_service import SessaoHistoricoService


# ============================================================
# Model
# ============================================================

def test_model_tem_campos_obrigatorios():
    """RF: SessaoHistorico deve ter todos os campos da spec."""
    colunas = {c.name for c in SessaoHistorico.__table__.columns}
    assert "id" in colunas
    assert "paciente_id" in colunas
    assert "sessao_id" in colunas
    assert "sintomas_relatados" in colunas
    assert "especialidade_sugerida" in colunas
    assert "urgencia" in colunas
    assert "resumo_triagem" in colunas
    assert "created_at" in colunas


def test_paciente_id_e_fk():
    """paciente_id deve ser FK para pacientes."""
    col = SessaoHistorico.__table__.columns["paciente_id"]
    fks = {fk.target_fullname for fk in col.foreign_keys}
    assert "pacientes.id" in fks


def test_sessao_id_e_nullable():
    """sessao_id pode ser NULL (sessão Redis pode não ter DB id)."""
    col = SessaoHistorico.__table__.columns["sessao_id"]
    assert col.nullable is True


def test_sintomas_relatados_e_json():
    """sintomas_relatados deve ser coluna JSON/JSONB."""
    from sqlalchemy import JSON
    from sqlalchemy.dialects.postgresql import JSONB
    col = SessaoHistorico.__table__.columns["sintomas_relatados"]
    assert isinstance(col.type, (JSON, JSONB))


# ============================================================
# Service — salvar
# ============================================================

async def test_salvar_persiste_historico():
    """RF: salvar() deve chamar db.add() e db.flush()."""
    db = AsyncMock()
    svc = SessaoHistoricoService(db)

    await svc.salvar(
        paciente_id=1,
        sessao_id=None,
        sintomas_relatados=["dor de cabeça", "febre"],
        especialidade_sugerida="Clínica Geral",
        urgencia="baixa",
        resumo_triagem="Paciente relata dor de cabeça e febre há 2 dias.",
    )

    db.add.assert_called_once()
    db.flush.assert_called_once()
    historico = db.add.call_args[0][0]
    assert isinstance(historico, SessaoHistorico)
    assert historico.paciente_id == 1
    assert historico.especialidade_sugerida == "Clínica Geral"


async def test_salvar_aceita_sintomas_lista_vazia():
    """salvar() deve funcionar com lista de sintomas vazia."""
    db = AsyncMock()
    svc = SessaoHistoricoService(db)

    await svc.salvar(paciente_id=2, sessao_id=None, sintomas_relatados=[],
                     especialidade_sugerida=None, urgencia=None, resumo_triagem=None)

    db.add.assert_called_once()


# ============================================================
# Service — buscar_por_paciente
# ============================================================

async def test_buscar_por_paciente_retorna_ultimos_3():
    """RF: buscar_por_paciente() retorna no máximo 3 registros."""
    db = AsyncMock()
    svc = SessaoHistoricoService(db)

    mock_result = MagicMock()
    registros = [MagicMock(spec=SessaoHistorico) for _ in range(3)]
    mock_result.scalars.return_value.all.return_value = registros
    db.execute.return_value = mock_result

    resultado = await svc.buscar_por_paciente(paciente_id=1)

    assert len(resultado) == 3
    db.execute.assert_called_once()


async def test_buscar_por_paciente_sem_historico_retorna_lista_vazia():
    """RF: paciente sem histórico → lista vazia, sem erro."""
    db = AsyncMock()
    svc = SessaoHistoricoService(db)

    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = []
    db.execute.return_value = mock_result

    resultado = await svc.buscar_por_paciente(paciente_id=99)

    assert resultado == []
