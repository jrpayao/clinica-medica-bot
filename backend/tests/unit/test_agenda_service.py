import pytest
from unittest.mock import AsyncMock, MagicMock

from app.models.atendimento import AtendimentoStatus
from app.models.slot import SlotStatus
from app.schemas.atendimento import AtendimentoCreate
from app.services.agenda_service import (
    AgendaService,
    ConsultaJaCanceladaError,
    ConsultaJaRealizadaError,
    ConsultaNaoEncontradaError,
    SlotIndisponivelError,
    SlotNaoEncontradoError,
)


@pytest.fixture
def mock_db():
    db = AsyncMock()
    db.flush = AsyncMock()
    db.refresh = AsyncMock()
    result_mock = MagicMock()
    result_mock.scalars.return_value.all.return_value = []
    result_mock.scalar_one_or_none.return_value = None
    db.execute = AsyncMock(return_value=result_mock)
    return db


@pytest.fixture
def service(mock_db):
    return AgendaService(mock_db)


# ============================================================
# Disponibilidade
# ============================================================

async def test_buscar_disponibilidade_retorna_lista(service, mock_db):
    """RF: Buscar slots disponiveis retorna lista do estabelecimento."""
    resultado = await service.buscar_disponibilidade(estabelecimento_id=1)
    assert isinstance(resultado, list)


# ============================================================
# Agendar consulta
# ============================================================

async def test_agendar_consulta_sucesso(service, mock_db):
    """RF: Agendar consulta reserva o slot."""
    slot_mock = MagicMock()
    slot_mock.id = 1
    slot_mock.status = SlotStatus.DISPONIVEL
    mock_db.execute.return_value.scalar_one_or_none.return_value = slot_mock

    dados = AtendimentoCreate(
        slot_id=1,
        cliente_id=1,
        profissional_id=1,
        especialidade_id=1,
    )
    mock_db.refresh.side_effect = lambda obj: setattr(obj, "id", 1)

    resultado = await service.agendar_consulta(dados, estabelecimento_id=1)

    assert slot_mock.status == SlotStatus.AGENDADO
    mock_db.add.assert_called_once()


async def test_agendar_consulta_slot_inexistente(service, mock_db):
    """Edge case: slot inexistente lanca erro."""
    dados = AtendimentoCreate(
        slot_id=999, cliente_id=1, profissional_id=1, especialidade_id=1,
    )

    with pytest.raises(SlotNaoEncontradoError):
        await service.agendar_consulta(dados, estabelecimento_id=1)


async def test_agendar_consulta_slot_ja_ocupado(service, mock_db):
    """RF: Slot AGENDADO nao pode ser reservado por outro paciente."""
    slot_mock = MagicMock()
    slot_mock.id = 1
    slot_mock.status = SlotStatus.AGENDADO
    mock_db.execute.return_value.scalar_one_or_none.return_value = slot_mock

    dados = AtendimentoCreate(
        slot_id=1, cliente_id=2, profissional_id=1, especialidade_id=1,
    )

    with pytest.raises(SlotIndisponivelError):
        await service.agendar_consulta(dados, estabelecimento_id=1)


# ============================================================
# Cancelar consulta
# ============================================================

async def test_cancelar_consulta_libera_slot(service, mock_db):
    """RF: Cancelar consulta libera slot automaticamente."""
    consulta_mock = MagicMock()
    consulta_mock.id = 1
    consulta_mock.slot_id = 10
    consulta_mock.status = AtendimentoStatus.AGENDADA

    slot_mock = MagicMock()
    slot_mock.id = 10
    slot_mock.status = SlotStatus.AGENDADO

    # Primeira chamada retorna consulta, segunda retorna slot
    mock_db.execute.return_value.scalar_one_or_none.side_effect = [
        consulta_mock,
        slot_mock,
    ]

    resultado = await service.cancelar_consulta(1, "Cliente desistiu")

    assert consulta_mock.status == AtendimentoStatus.CANCELADA
    assert slot_mock.status == SlotStatus.DISPONIVEL
    assert "Cancelada: Cliente desistiu" in consulta_mock.observacoes


async def test_cancelar_consulta_inexistente(service, mock_db):
    """Edge case: consulta inexistente lanca erro."""
    with pytest.raises(ConsultaNaoEncontradaError):
        await service.cancelar_consulta(999, "motivo")


async def test_cancelar_consulta_ja_cancelada(service, mock_db):
    """Edge case: consulta ja cancelada lanca erro."""
    consulta_mock = MagicMock()
    consulta_mock.status = AtendimentoStatus.CANCELADA
    mock_db.execute.return_value.scalar_one_or_none.return_value = consulta_mock

    with pytest.raises(ConsultaJaCanceladaError):
        await service.cancelar_consulta(1, "motivo")


async def test_cancelar_consulta_ja_realizada(service, mock_db):
    """Edge case: consulta realizada nao pode ser cancelada."""
    consulta_mock = MagicMock()
    consulta_mock.status = AtendimentoStatus.REALIZADA
    mock_db.execute.return_value.scalar_one_or_none.return_value = consulta_mock

    with pytest.raises(ConsultaJaRealizadaError):
        await service.cancelar_consulta(1, "motivo")
