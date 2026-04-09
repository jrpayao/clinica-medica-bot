import pytest
from datetime import date, time
from unittest.mock import AsyncMock, MagicMock

from app.services.profissional_service import ProfissionalService
from app.schemas.profissional import ProfissionalCreate, ProfissionalUpdate


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
    return ProfissionalService(mock_db)


async def test_criar_medico(service, mock_db):
    """RF: CRUD criar medico."""
    dados = ProfissionalCreate(
        registro_profissional="12345-SP", nome="Dr. Carlos", especialidade_id=1
    )
    mock_db.refresh.side_effect = lambda obj: setattr(obj, "id", 1)

    resultado = await service.criar(dados, estabelecimento_id=1)

    assert mock_db.add.call_count == 2  # medico + vinculo ProfissionalEstabelecimento
    assert resultado.nome == "Dr. Carlos"
    assert resultado.registro_profissional == "12345-SP"


async def test_gerar_slots_um_dia_sem_almoco(service, mock_db):
    """RF: Gerar slots para 1 dia, sem almoco, consulta de 30min."""
    medico_mock = MagicMock()
    medico_mock.id = 1
    medico_mock.duracao_atendimento_min = 30
    mock_db.execute.return_value.scalar_one_or_none.return_value = medico_mock

    slots = await service.gerar_slots(
        profissional_id=1,
        data_inicio=date(2026, 4, 6),  # segunda-feira
        data_fim=date(2026, 4, 6),
        hora_inicio=time(8, 0),
        hora_fim=time(12, 0),
        intervalo_almoco_inicio=None,
        intervalo_almoco_fim=None,
        dias_semana=[0],  # segunda
    )

    # 4 horas / 30min = 8 slots
    assert len(slots) == 8
    assert mock_db.add.call_count == 8


async def test_gerar_slots_pula_almoco(service, mock_db):
    """RF: Gerar slots pulando almoco 12-13h."""
    medico_mock = MagicMock()
    medico_mock.id = 1
    medico_mock.duracao_atendimento_min = 30
    mock_db.execute.return_value.scalar_one_or_none.return_value = medico_mock

    slots = await service.gerar_slots(
        profissional_id=1,
        data_inicio=date(2026, 4, 6),
        data_fim=date(2026, 4, 6),
        hora_inicio=time(8, 0),
        hora_fim=time(18, 0),
        intervalo_almoco_inicio=time(12, 0),
        intervalo_almoco_fim=time(13, 0),
        dias_semana=[0],
    )

    # 8-12 = 8 slots + 13-18 = 10 slots = 18 slots
    assert len(slots) == 18


async def test_gerar_slots_pula_fim_de_semana(service, mock_db):
    """RF: Gerar slots seg-sex, pular sabado e domingo."""
    medico_mock = MagicMock()
    medico_mock.id = 1
    medico_mock.duracao_atendimento_min = 60
    mock_db.execute.return_value.scalar_one_or_none.return_value = medico_mock

    # seg 6 a dom 12 = 7 dias, mas so seg-sex (5 dias)
    slots = await service.gerar_slots(
        profissional_id=1,
        data_inicio=date(2026, 4, 6),   # segunda
        data_fim=date(2026, 4, 12),      # domingo
        hora_inicio=time(8, 0),
        hora_fim=time(10, 0),
        intervalo_almoco_inicio=None,
        intervalo_almoco_fim=None,
        dias_semana=[0, 1, 2, 3, 4],
    )

    # 2 horas / 60min = 2 slots/dia * 5 dias = 10
    assert len(slots) == 10


async def test_gerar_slots_medico_inexistente(service, mock_db):
    """Edge case: medico inexistente lanca erro."""
    with pytest.raises(ValueError, match="Profissional nao encontrado"):
        await service.gerar_slots(
            profissional_id=999,
            data_inicio=date(2026, 4, 6),
            data_fim=date(2026, 4, 6),
        )
