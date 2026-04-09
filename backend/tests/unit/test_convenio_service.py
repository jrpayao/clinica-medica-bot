import pytest
from unittest.mock import AsyncMock, MagicMock
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.convenio import Convenio
from app.models.convenio_plano import ConvenioPlano
from app.models.cliente_convenio import ClienteConvenio
from app.services.convenio_service import ConvenioService
from app.schemas.convenio import ConvenioCreate, ConvenioUpdate
from app.schemas.convenio_plano import ConvenioPlanoCreate
from app.schemas.cliente_convenio import ClienteConvenioCreate


@pytest.fixture
def db():
    return AsyncMock(spec=AsyncSession)


@pytest.fixture
def svc(db):
    return ConvenioService(db)


async def test_listar_ativos_por_estabelecimento(svc, db):
    convenio = MagicMock(spec=Convenio)
    result = MagicMock()
    result.scalars.return_value.all.return_value = [convenio]
    db.execute.return_value = result

    lista = await svc.listar_ativos(estabelecimento_id=1)

    assert len(lista) == 1
    assert lista[0] is convenio


async def test_criar_convenio(svc, db):
    dados = ConvenioCreate(
        nome="Unimed",
        codigo_ans="123456",
        cnpj="12345678000100",
    )
    convenio = await svc.criar(dados, estabelecimento_id=1)

    db.add.assert_called_once()
    db.commit.assert_called_once()
    assert convenio.nome == "Unimed"
    assert convenio.estabelecimento_id == 1


async def test_criar_plano(svc, db):
    dados = ConvenioPlanoCreate(nome="Bronze")
    plano = await svc.criar_plano(convenio_id=1, dados=dados)

    db.add.assert_called_once()
    db.commit.assert_called_once()
    assert plano.nome == "Bronze"
    assert plano.convenio_id == 1


async def test_adicionar_carteirinha_cliente(svc, db):
    dados = ClienteConvenioCreate(
        convenio_id=1,
        plano_id=1,
        numero_carteirinha="123456789",
        principal=True,
    )
    carteirinha = await svc.adicionar_carteirinha(cliente_id=5, dados=dados)

    db.add.assert_called_once()
    db.commit.assert_called_once()
    assert carteirinha.cliente_id == 5
    assert carteirinha.principal is True


async def test_listar_carteirinhas_cliente(svc, db):
    carteirinha = MagicMock(spec=ClienteConvenio)
    result = MagicMock()
    result.scalars.return_value.all.return_value = [carteirinha]
    db.execute.return_value = result

    lista = await svc.listar_carteirinhas(cliente_id=5)
    assert len(lista) == 1
