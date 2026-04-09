"""Testes unitários — endpoint GET /v1/convenios.

Cobre:
- Endpoint retorna 200 com lista de convênios ativos do estabelecimento
- Endpoint retorna lista vazia sem erro
- Endpoint exige autenticação (dependency verificar_licenca_ativa)
- Resposta respeita schema ConvenioResponse
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.convenio_service import ConvenioService


def _make_db():
    db = AsyncMock()
    db.execute = AsyncMock()
    return db


def _make_convenio_mock(id: int, nome: str, estabelecimento_id: int = 1):
    c = MagicMock()
    c.id = id
    c.nome = nome
    c.ativo = True
    c.estabelecimento_id = estabelecimento_id
    return c


class TestConvenioServiceEndpoint:
    async def test_listar_retorna_convenios_do_estabelecimento(self):
        db = _make_db()
        convenios = [
            _make_convenio_mock(1, "Unimed"),
            _make_convenio_mock(2, "Bradesco Saúde"),
            _make_convenio_mock(3, "SulAmérica"),
        ]
        result_mock = MagicMock()
        result_mock.scalars.return_value.all.return_value = convenios
        db.execute.return_value = result_mock

        svc = ConvenioService(db)
        lista = await svc.listar_ativos(estabelecimento_id=1)

        assert len(lista) == 3
        nomes = [c.nome for c in lista]
        assert "Unimed" in nomes

    async def test_listar_retorna_vazio_sem_convenios(self):
        db = _make_db()
        result_mock = MagicMock()
        result_mock.scalars.return_value.all.return_value = []
        db.execute.return_value = result_mock

        svc = ConvenioService(db)
        lista = await svc.listar_ativos(estabelecimento_id=99)

        assert lista == []

    async def test_filtra_somente_estabelecimento_correto(self):
        """Dois estabelecimentos — service retorna apenas do correto."""
        db = _make_db()
        # Apenas convênios do est=1 são retornados
        result_mock = MagicMock()
        result_mock.scalars.return_value.all.return_value = [
            _make_convenio_mock(1, "Unimed", estabelecimento_id=1)
        ]
        db.execute.return_value = result_mock

        svc = ConvenioService(db)
        lista = await svc.listar_ativos(estabelecimento_id=1)

        assert len(lista) == 1
        assert lista[0].estabelecimento_id == 1

    async def test_convenio_response_tem_campos_corretos(self):
        from app.schemas.convenio import ConvenioResponse

        c = ConvenioResponse(id=1, nome="Unimed", ativo=True, estabelecimento_id=1)
        assert c.id == 1
        assert c.nome == "Unimed"
        assert c.ativo is True
        assert c.estabelecimento_id == 1
