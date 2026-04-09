import pytest
from unittest.mock import AsyncMock, MagicMock

from app.services.cliente_service import ClienteService
from app.schemas.cliente import ClienteCreate, ClienteUpdate


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
    return ClienteService(mock_db)


async def test_criar_paciente(service, mock_db):
    """RF: CRUD criar paciente."""
    dados = ClienteCreate(nome="Maria Silva", cpf="12345678901")
    mock_db.refresh.side_effect = lambda obj: setattr(obj, "id", 1)

    resultado = await service.criar(dados, estabelecimento_id=1)

    mock_db.add.assert_called_once()
    assert resultado.nome == "Maria Silva"


async def test_buscar_por_cpf(service, mock_db):
    """RF: Buscar paciente por CPF."""
    resultado = await service.buscar_por_cpf("12345678901")
    assert resultado is None
    mock_db.execute.assert_called_once()


async def test_desativar_paciente(service, mock_db):
    """RF: Desativar paciente (soft delete)."""
    pac_mock = MagicMock()
    pac_mock.id = 1
    pac_mock.ativo = True
    mock_db.execute.return_value.scalar_one_or_none.return_value = pac_mock

    resultado = await service.desativar(1)

    assert pac_mock.ativo is False


async def test_nao_expoe_cpf_completo_em_log(service, mock_db, caplog):
    """Seguranca: CPF completo nao aparece nos logs."""
    dados = ClienteCreate(nome="Teste", cpf="98765432100")
    mock_db.refresh.side_effect = lambda obj: setattr(obj, "id", 1)

    await service.criar(dados, estabelecimento_id=1)

    assert "98765432100" not in caplog.text


async def test_cpf_mascarado_no_response():
    """Seguranca: CPF mascarado na resposta da API."""
    from app.schemas.cliente import ClienteOut as PacienteResponse
    from datetime import datetime

    resp = PacienteResponse(
        id=1,
        nome="Teste",
        cpf="12345678901",
        data_nascimento=None,
        telefone=None,
        email=None,
        convenio=None,
        numero_carteirinha=None,
        modalidade_pagamento=None,
        convenio_id=None,
        estabelecimento_id=1,
        ativo=True,
        created_at=datetime.now(),
    )
    assert resp.cpf == "123.***.***-01"
