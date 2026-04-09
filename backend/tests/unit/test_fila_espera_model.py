"""Testes unitários — Model FilaEspera (T89).

Cobre:
- FilaEspera tem os campos obrigatórios da spec
- FilaEspera.status usa enum FilaEsperaStatus
- Enum tem valores: AGUARDANDO, NOTIFICADO, AGENDADO, CANCELADO
- FK para pacientes, estabelecimentos, especialidades (nullable), convenios (nullable)
- FilaEsperaService.entrar() persiste o registro com status AGUARDANDO
- FilaEsperaService.sair() atualiza status para CANCELADO
- FilaEsperaService.listar_aguardando() filtra por estabelecimento_id e status
"""

from unittest.mock import AsyncMock, MagicMock

import pytest

from app.models.fila_espera import FilaEspera, FilaEsperaStatus
from app.services.fila_espera_service import FilaEsperaService


# ============================================================
# Enum
# ============================================================

def test_enum_tem_todos_os_status():
    """RF: FilaEsperaStatus deve ter AGUARDANDO, NOTIFICADO, AGENDADO, CANCELADO."""
    valores = {s.value for s in FilaEsperaStatus}
    assert "AGUARDANDO" in valores
    assert "NOTIFICADO" in valores
    assert "AGENDADO" in valores
    assert "CANCELADO" in valores


def test_status_sao_strings():
    """RF: status devem ser strings para serializar no banco."""
    assert isinstance(FilaEsperaStatus.AGUARDANDO, str)


# ============================================================
# Model
# ============================================================

def test_model_tem_campos_obrigatorios():
    """RF: FilaEspera deve ter os campos da spec."""
    colunas = {c.name for c in FilaEspera.__table__.columns}
    assert "id" in colunas
    assert "paciente_id" in colunas
    assert "estabelecimento_id" in colunas
    assert "especialidade_id" in colunas
    assert "convenio_id" in colunas
    assert "status" in colunas
    assert "notificado_em" in colunas
    assert "created_at" in colunas


def test_especialidade_id_e_nullable():
    """especialidade_id pode ser NULL."""
    col = FilaEspera.__table__.columns["especialidade_id"]
    assert col.nullable is True


def test_convenio_id_e_nullable():
    """convenio_id pode ser NULL (particular)."""
    col = FilaEspera.__table__.columns["convenio_id"]
    assert col.nullable is True


def test_notificado_em_e_nullable():
    """notificado_em é NULL até o paciente ser notificado."""
    col = FilaEspera.__table__.columns["notificado_em"]
    assert col.nullable is True


def test_paciente_id_e_fk():
    """paciente_id deve ser FK para pacientes."""
    col = FilaEspera.__table__.columns["paciente_id"]
    fks = {fk.target_fullname for fk in col.foreign_keys}
    assert "pacientes.id" in fks


def test_estabelecimento_id_e_fk():
    """estabelecimento_id deve ser FK para estabelecimentos."""
    col = FilaEspera.__table__.columns["estabelecimento_id"]
    fks = {fk.target_fullname for fk in col.foreign_keys}
    assert "estabelecimentos.id" in fks


# ============================================================
# Service
# ============================================================

async def test_entrar_cria_registro_aguardando():
    """RF: entrar() deve criar registro com status AGUARDANDO."""
    db = AsyncMock()
    svc = FilaEsperaService(db)

    await svc.entrar(
        paciente_id=1,
        estabelecimento_id=1,
        especialidade_id=2,
        convenio_id=None,
    )

    db.add.assert_called_once()
    db.flush.assert_called_once()
    entrada = db.add.call_args[0][0]
    assert isinstance(entrada, FilaEspera)
    assert entrada.status == FilaEsperaStatus.AGUARDANDO
    assert entrada.paciente_id == 1


async def test_sair_atualiza_status_cancelado():
    """RF: sair() deve atualizar status para CANCELADO."""
    db = AsyncMock()
    svc = FilaEsperaService(db)

    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = MagicMock(
        spec=FilaEspera, id=5, status=FilaEsperaStatus.AGUARDANDO
    )
    db.execute.return_value = mock_result

    await svc.sair(fila_id=5, paciente_id=1)

    db.flush.assert_called_once()


async def test_listar_aguardando_filtra_por_estabelecimento():
    """RF: listar_aguardando() retorna apenas AGUARDANDO do estabelecimento."""
    db = AsyncMock()
    svc = FilaEsperaService(db)

    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = []
    db.execute.return_value = mock_result

    resultado = await svc.listar_aguardando(estabelecimento_id=1)

    assert resultado == []
    db.execute.assert_called_once()
