"""Testes — Cache no Redis: módulo, licença, catálogo do chat e relatórios.

Regra geral: cache nunca derruba nada. Se o Redis cair, tudo volta a consultar o banco.
"""

from datetime import UTC, date, datetime, timedelta
from unittest.mock import AsyncMock

import pytest
from fastapi import HTTPException
from sqlalchemy import update

from app.api.v1.dependencies import validar_licenca_do_estabelecimento
from app.core import cache
from app.models.licenca import Licenca, LicencaStatus
from app.schemas.convenio import ConvenioCreate, ConvenioUpdate
from app.schemas.convenio_plano import ConvenioPlanoCreate
from app.schemas.especialidade import EspecialidadeCreate, EspecialidadeUpdate
from app.services.convenio_service import ConvenioService
from app.services.especialidade_service import EspecialidadeService
from app.services.ia.chat_service import ChatService
from app.services.licenca_service import LicencaService
from tests.fabrica import (
    RedisFalso,
    cabecalho,
    criar_especialidade,
    criar_estabelecimento,
    criar_profissional,
    criar_slot,
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


# ── Catálogo do chat (especialidades e convênios de cada sessão) ────────────

async def _sessao(db, est):
    servico = ChatService(db, RedisFalso())
    token = await servico.criar_sessao(estabelecimento_id=est.id)
    return await servico._carregar_sessao(token)


async def test_catalogo_do_chat_fica_em_cache(db_session):
    est = await criar_estabelecimento(db_session)
    await criar_especialidade(db_session, est, nome="Cardiologia")
    await _sessao(db_session, est)

    await criar_especialidade(db_session, est, nome="Ortopedia")   # direto no banco, sem invalidar

    assert (await _sessao(db_session, est))["especialidades"] == ["Cardiologia"]


@pytest.mark.parametrize("alteracao", ["criar", "atualizar", "desativar"])
async def test_mudar_especialidade_atualiza_o_chat(db_session, alteracao):
    est = await criar_estabelecimento(db_session)
    esp = await criar_especialidade(db_session, est, nome="Cardiologia")
    await _sessao(db_session, est)
    servico = EspecialidadeService(db_session)

    if alteracao == "criar":
        await servico.criar(EspecialidadeCreate(nome="Ortopedia"), est.id)
        esperado = ["Cardiologia", "Ortopedia"]
    elif alteracao == "atualizar":
        await servico.atualizar(esp.id, EspecialidadeUpdate(nome="Cardiologia Clínica"), est.id)
        esperado = ["Cardiologia Clínica"]
    else:
        await servico.desativar(esp.id, est.id)
        esperado = []

    assert (await _sessao(db_session, est))["especialidades"] == esperado


async def test_mudar_convenio_ou_plano_atualiza_o_chat(db_session):
    est = await criar_estabelecimento(db_session)
    await _sessao(db_session, est)
    servico = ConvenioService(db_session)

    convenio = await servico.criar(ConvenioCreate(nome="Unimed"), est.id)
    assert [c["nome"] for c in (await _sessao(db_session, est))["convenios"]] == ["Unimed"]

    plano = await servico.criar_plano(convenio.id, ConvenioPlanoCreate(nome="Especial"))
    assert (await _sessao(db_session, est))["convenios"][0]["planos"] == [{"id": plano.id, "nome": "Especial"}]

    await servico.atualizar(convenio.id, ConvenioUpdate(ativo=False))
    assert (await _sessao(db_session, est))["convenios"] == []


async def test_catalogo_e_por_unidade(db_session):
    a = await criar_estabelecimento(db_session)
    b = await criar_estabelecimento(db_session)
    await criar_especialidade(db_session, a, nome="Cardiologia")
    await criar_especialidade(db_session, b, nome="Dermatologia")

    assert (await _sessao(db_session, a))["especialidades"] == ["Cardiologia"]
    assert (await _sessao(db_session, b))["especialidades"] == ["Dermatologia"]


# ── Relatórios ──────────────────────────────────────────────────────────────

async def test_relatorio_fica_em_cache_e_atualizar_busca_de_novo(db_session, async_client):
    est = await criar_estabelecimento(db_session)
    esp = await criar_especialidade(db_session, est)
    prof = await criar_profissional(db_session, est, esp)
    await criar_slot(db_session, est, prof, data=date.today())
    gestor = cabecalho(est)
    periodo = {"inicio": str(date.today()), "fim": str(date.today())}

    primeiro = (await async_client.get("/v1/relatorios/ocupacao", params=periodo, headers=gestor)).json()
    await criar_slot(db_session, est, prof, data=date.today())
    do_cache = (await async_client.get("/v1/relatorios/ocupacao", params=periodo, headers=gestor)).json()
    atualizado = (
        await async_client.get("/v1/relatorios/ocupacao", params={**periodo, "atualizar": "true"}, headers=gestor)
    ).json()
    depois = (await async_client.get("/v1/relatorios/ocupacao", params=periodo, headers=gestor)).json()

    assert primeiro["geral"]["total_slots"] == do_cache["geral"]["total_slots"] == 1
    assert atualizado["geral"]["total_slots"] == depois["geral"]["total_slots"] == 2


async def test_relatorio_em_cache_nao_vaza_para_outra_unidade_nem_outro_periodo(db_session, async_client):
    a = await criar_estabelecimento(db_session)
    b = await criar_estabelecimento(db_session)
    esp = await criar_especialidade(db_session, a)
    prof = await criar_profissional(db_session, a, esp)
    await criar_slot(db_session, a, prof, data=date.today())
    hoje = {"inicio": str(date.today()), "fim": str(date.today())}
    ontem = {"inicio": str(date.today() - timedelta(days=1)), "fim": str(date.today() - timedelta(days=1))}

    da_a = (await async_client.get("/v1/relatorios/ocupacao", params=hoje, headers=cabecalho(a))).json()
    da_b = (await async_client.get("/v1/relatorios/ocupacao", params=hoje, headers=cabecalho(b))).json()
    outro_dia = (await async_client.get("/v1/relatorios/ocupacao", params=ontem, headers=cabecalho(a))).json()

    assert (da_a["geral"]["total_slots"], da_b["geral"]["total_slots"], outro_dia["geral"]["total_slots"]) == (1, 0, 0)
