import pytest
from unittest.mock import AsyncMock, MagicMock

from app.services.especialidade_service import EspecialidadeService
from app.schemas.especialidade import EspecialidadeCreate, EspecialidadeUpdate


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
    return EspecialidadeService(mock_db)


async def test_criar_especialidade(service, mock_db):
    """RF: CRUD criar especialidade persiste no banco."""
    dados = EspecialidadeCreate(nome="Cardiologia", cor_hex="#FF0000")
    mock_db.refresh.side_effect = lambda obj: setattr(obj, "id", 1)

    resultado = await service.criar(dados, estabelecimento_id=1)

    mock_db.add.assert_called_once()
    mock_db.flush.assert_called_once()
    assert resultado.nome == "Cardiologia"
    assert resultado.cor_hex == "#FF0000"


async def test_listar_especialidades(service, mock_db):
    """RF: Listar retorna lista de especialidades do estabelecimento."""
    resultado = await service.listar(estabelecimento_id=1)
    assert isinstance(resultado, list)
    mock_db.execute.assert_called_once()


async def test_buscar_por_id_inexistente(service, mock_db):
    """Edge case: ID inexistente retorna None."""
    resultado = await service.buscar_por_id(999)
    assert resultado is None


async def test_atualizar_especialidade(service, mock_db):
    """RF: Atualizar altera campos da especialidade."""
    esp_mock = MagicMock()
    esp_mock.id = 1
    esp_mock.nome = "Cardiologia"
    mock_db.execute.return_value.scalar_one_or_none.return_value = esp_mock

    dados = EspecialidadeUpdate(nome="Cardiologia Geral")
    resultado = await service.atualizar(1, dados, estabelecimento_id=1)

    assert resultado is not None
    assert esp_mock.nome == "Cardiologia Geral"


async def test_atualizar_inexistente_retorna_none(service, mock_db):
    """Edge case: atualizar ID inexistente retorna None."""
    dados = EspecialidadeUpdate(nome="XY")
    resultado = await service.atualizar(999, dados, estabelecimento_id=1)
    assert resultado is None


async def test_desativar_especialidade(service, mock_db):
    """RF: Desativar faz soft delete."""
    esp_mock = MagicMock()
    esp_mock.id = 1
    esp_mock.ativo = True
    mock_db.execute.return_value.scalar_one_or_none.return_value = esp_mock

    resultado = await service.desativar(1, estabelecimento_id=1)

    assert resultado is not None
    assert esp_mock.ativo is False
