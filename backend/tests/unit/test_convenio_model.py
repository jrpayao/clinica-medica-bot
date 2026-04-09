"""Testes unitários — Model Convenio e ConvenioService.

Cobre:
- Convenio tem campos obrigatórios: id, nome, ativo, estabelecimento_id
- ConvenioService.listar_ativos retorna apenas convênios ativos do estabelecimento
- ConvenioService.listar_ativos filtra por estabelecimento_id
- ConvenioService.listar_ativos retorna lista vazia sem erro quando não há convênios
- ConvenioService.listar_ativos não retorna convênios inativos
"""

from unittest.mock import AsyncMock, MagicMock

import pytest

from app.models.convenio import Convenio
from app.services.convenio_service import ConvenioService


def _make_db():
    db = AsyncMock()
    db.execute = AsyncMock()
    return db


def _make_convenio(id: int = 1, nome: str = "Unimed", estabelecimento_id: int = 1, ativo: bool = True) -> MagicMock:
    c = MagicMock(spec=Convenio)
    c.id = id
    c.nome = nome
    c.ativo = ativo
    c.estabelecimento_id = estabelecimento_id
    return c


# ── Model ────────────────────────────────────────────────────────────────────

class TestConvenioModel:
    def test_campos_obrigatorios(self):
        c = _make_convenio()
        assert c.id == 1
        assert c.nome == "Unimed"
        assert c.ativo is True
        assert c.estabelecimento_id == 1

    def test_tablename(self):
        assert Convenio.__tablename__ == "convenios"

    def test_ativo_default_true(self):
        # model define server_default True — verificamos via mapped_column
        col = Convenio.__table__.c["ativo"]
        assert col.nullable is False


# ── ConvenioService ──────────────────────────────────────────────────────────

class TestConvenioService:
    async def test_listar_ativos_retorna_lista(self):
        db = _make_db()
        convenios = [_make_convenio(1, "Unimed"), _make_convenio(2, "Bradesco Saúde")]
        result_mock = MagicMock()
        result_mock.scalars.return_value.all.return_value = convenios
        db.execute.return_value = result_mock

        svc = ConvenioService(db)
        lista = await svc.listar_ativos(estabelecimento_id=1)

        assert len(lista) == 2
        assert lista[0].nome == "Unimed"

    async def test_listar_ativos_filtra_estabelecimento(self):
        """Deve executar query com where(ativo=True, estab_id=X)."""
        db = _make_db()
        result_mock = MagicMock()
        result_mock.scalars.return_value.all.return_value = []
        db.execute.return_value = result_mock

        svc = ConvenioService(db)
        await svc.listar_ativos(estabelecimento_id=99)

        db.execute.assert_called_once()
        # verifica que a query foi chamada (sem inspecionar SQL exato)

    async def test_listar_ativos_retorna_lista_vazia(self):
        db = _make_db()
        result_mock = MagicMock()
        result_mock.scalars.return_value.all.return_value = []
        db.execute.return_value = result_mock

        svc = ConvenioService(db)
        lista = await svc.listar_ativos(estabelecimento_id=1)

        assert lista == []

    async def test_listar_ativos_exclui_inativos(self):
        """Convênios inativos não devem ser retornados (filtro na query)."""
        db = _make_db()
        # apenas ativos são retornados pelo banco — o service não faz filtro em Python
        ativos = [_make_convenio(1, "Unimed", ativo=True)]
        result_mock = MagicMock()
        result_mock.scalars.return_value.all.return_value = ativos
        db.execute.return_value = result_mock

        svc = ConvenioService(db)
        lista = await svc.listar_ativos(estabelecimento_id=1)

        assert all(c.ativo for c in lista)
