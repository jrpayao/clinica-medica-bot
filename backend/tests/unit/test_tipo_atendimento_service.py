import pytest
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.tipo_atendimento import TipoAtendimento
from app.services.tipo_atendimento_service import TipoAtendimentoService
from app.schemas.tipo_atendimento import TipoAtendimentoCreate, TipoAtendimentoUpdate


@pytest.fixture
def db():
    return AsyncMock(spec=AsyncSession)


@pytest.fixture
def svc(db):
    return TipoAtendimentoService(db)


async def test_listar_ativos(svc, db):
    tipo = MagicMock(spec=TipoAtendimento)
    result = MagicMock()
    result.scalars.return_value.all.return_value = [tipo]
    db.execute.return_value = result

    lista = await svc.listar_ativos(estabelecimento_id=1)

    assert len(lista) == 1
    assert lista[0] is tipo


async def test_criar_tipo(svc, db):
    dados = TipoAtendimentoCreate(
        nome="Botox",
        duracao_min=45,
        preco=Decimal("350.00"),
    )
    tipo = await svc.criar(dados, estabelecimento_id=1)

    db.add.assert_called_once()
    db.commit.assert_called_once()
    assert tipo.nome == "Botox"
    assert tipo.estabelecimento_id == 1
    assert tipo.duracao_min == 45


async def test_atualizar_tipo(svc, db):
    tipo_existente = MagicMock(spec=TipoAtendimento)
    db.get.return_value = tipo_existente

    dados = TipoAtendimentoUpdate(ativo=False)
    resultado = await svc.atualizar(tipo_id=1, dados=dados)

    db.commit.assert_called_once()
    assert resultado is tipo_existente


async def test_atualizar_tipo_nao_encontrado(svc, db):
    db.get.return_value = None

    dados = TipoAtendimentoUpdate(nome="Novo Nome")
    resultado = await svc.atualizar(tipo_id=999, dados=dados)

    assert resultado is None


async def test_vincular_profissional(svc, db):
    profissional = MagicMock()
    profissional.tipos_atendimento = []
    tipo = MagicMock(spec=TipoAtendimento)
    db.get.side_effect = [profissional, tipo]

    result = await svc.vincular_profissional(profissional_id=1, tipo_id=2)

    assert result is True
    assert tipo in profissional.tipos_atendimento
    db.commit.assert_called_once()
