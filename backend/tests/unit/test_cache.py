"""Testes — Cache no Redis: módulo e licença (checada em toda requisição).

Regra geral: cache nunca derruba nada. Se o Redis cair, tudo volta a consultar o banco.
"""

from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock

import pytest
from fastapi import HTTPException
from sqlalchemy import update

from app.api.v1.dependencies import validar_licenca_do_estabelecimento
from app.core import cache
from app.models.licenca import Licenca, LicencaStatus
from app.services.licenca_service import LicencaService
from tests.fabrica import (
    criar_estabelecimento,
)

# ── Módulo de cache ─────────────────────────────────────────────────────────

async def test_lembrar_carrega_uma_vez_e_depois_usa_o_cache():
    carregar = AsyncMock(return_value={"valor": 1})

    primeiro = await cache.lembrar("teste:a", 60, carregar)
    segundo = await cache.lembrar("teste:a", 60, carregar)

    assert primeiro == segundo == {"valor": 1}
    carregar.assert_awaited_once()


async def test_cache_grava_com_validade_e_prefixo_proprio():
    redis = cache._cliente()
    await cache.gravar("teste:b", [1, 2], ttl=90)
    assert redis.ttl["cache:teste:b"] == 90
    assert await cache.obter("teste:b") == [1, 2]


async def test_apagar_faz_carregar_de_novo():
    carregar = AsyncMock(side_effect=[1, 2])
    await cache.lembrar("teste:c", 60, carregar)
    await cache.apagar("teste:c")
    assert await cache.lembrar("teste:c", 60, carregar) == 2


async def test_redis_fora_do_ar_nao_derruba_nada(monkeypatch):
    quebrado = AsyncMock()
    quebrado.get.side_effect = ConnectionError("redis caiu")
    quebrado.set.side_effect = ConnectionError("redis caiu")
    quebrado.delete.side_effect = ConnectionError("redis caiu")
    monkeypatch.setattr(cache, "_cliente", lambda: quebrado)
    carregar = AsyncMock(return_value="do banco")

    assert await cache.lembrar("teste:d", 60, carregar) == "do banco"
    assert await cache.obter("teste:d") is None
    await cache.apagar("teste:d")               # não levanta erro


# ── Licença (consultada em toda requisição) ─────────────────────────────────

async def _status(db, est_id, status):
    await db.execute(update(Licenca).where(Licenca.estabelecimento_id == est_id).values(status=status))


async def test_licenca_valida_fica_em_cache(db_session):
    est = await criar_estabelecimento(db_session)
    await validar_licenca_do_estabelecimento(db_session, est.id)

    await _status(db_session, est.id, LicencaStatus.SUSPENSA)   # mudança direta no banco, sem invalidar
    licenca = await validar_licenca_do_estabelecimento(db_session, est.id)

    assert licenca.estabelecimento_id == est.id and licenca.plano == "pro"


async def test_suspender_pela_plataforma_vale_na_hora(db_session):
    est = await criar_estabelecimento(db_session)
    await validar_licenca_do_estabelecimento(db_session, est.id)

    await LicencaService(db_session).suspender(est.id, admin_id=1, motivo="inadimplência")

    with pytest.raises(HTTPException) as erro:
        await validar_licenca_do_estabelecimento(db_session, est.id)
    assert erro.value.status_code == 403


async def test_licenca_invalida_nao_fica_em_cache(db_session):
    est = await criar_estabelecimento(db_session)
    await _status(db_session, est.id, LicencaStatus.SUSPENSA)
    with pytest.raises(HTTPException):
        await validar_licenca_do_estabelecimento(db_session, est.id)

    await _status(db_session, est.id, LicencaStatus.ATIVA)     # liberada: vale na próxima requisição

    assert (await validar_licenca_do_estabelecimento(db_session, est.id)).estabelecimento_id == est.id


async def test_licenca_em_cache_respeita_a_data_de_vencimento(db_session):
    est = await criar_estabelecimento(db_session)
    await validar_licenca_do_estabelecimento(db_session, est.id)
    await cache.gravar(
        cache.chave_licenca(est.id),
        {"plano": "pro", "valida_ate": (datetime.now(UTC) - timedelta(minutes=1)).isoformat()},
        ttl=60,
    )
    await _status(db_session, est.id, LicencaStatus.EXPIRADA)

    with pytest.raises(HTTPException) as erro:
        await validar_licenca_do_estabelecimento(db_session, est.id)
    assert erro.value.status_code == 402
