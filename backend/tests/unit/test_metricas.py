"""Testes — Métricas para o Prometheus (observabilidade).

Requisições HTTP, uso de IA (tokens, custo, latência, modelos sem preço), acertos do cache e fila do Celery.
"""

from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

from prometheus_client import REGISTRY

from app.core import cache, metricas
from app.services.ia import billing


def _valor(nome: str, **rotulos) -> float:
    return REGISTRY.get_sample_value(nome, rotulos) or 0.0


# ── Endpoint /metrics ───────────────────────────────────────────────────────

async def test_metrics_expoe_requisicoes_e_metricas_do_medbot(async_client):
    await async_client.get("/health")

    resposta = await async_client.get("/metrics")

    assert resposta.status_code == 200
    texto = resposta.text
    for nome in ("http_requests_total", "medbot_ia_tokens_total", "medbot_cache_total", "medbot_celery_fila_tamanho"):
        assert nome in texto


async def test_metrics_com_token_exige_o_token(async_client, monkeypatch):
    monkeypatch.setattr(metricas.settings, "metrics_token", "segredo-das-metricas")

    sem = await async_client.get("/metrics")
    errado = await async_client.get("/metrics", headers={"Authorization": "Bearer outro"})
    certo = await async_client.get("/metrics", headers={"Authorization": "Bearer segredo-das-metricas"})

    assert (sem.status_code, errado.status_code, certo.status_code) == (401, 401, 200)


async def test_metrics_nao_aparece_na_documentacao_da_api(async_client):
    assert "/metrics" not in (await async_client.get("/openapi.json")).json()["paths"]


# ── IA ──────────────────────────────────────────────────────────────────────

async def test_uso_de_ia_vira_metrica_de_tokens_chamadas_e_custo(monkeypatch):
    monkeypatch.setitem(billing.MODEL_PRICING, "modelo-teste", {"input": 0.000001, "output": 0.000002})
    db = MagicMock()
    db.flush = AsyncMock()
    antes = {
        "entrada": _valor("medbot_ia_tokens_total", modelo="modelo-teste", feature="TRIAGEM", tipo="entrada"),
        "saida": _valor("medbot_ia_tokens_total", modelo="modelo-teste", feature="TRIAGEM", tipo="saida"),
        "chamadas": _valor("medbot_ia_chamadas_total", modelo="modelo-teste", feature="TRIAGEM"),
        "custo": _valor("medbot_ia_custo_usd_total", modelo="modelo-teste", feature="TRIAGEM"),
    }

    await billing.registrar_uso(db, session_id=1, modelo="modelo-teste", feature="TRIAGEM",
                                prompt_tokens=1000, completion_tokens=200, estabelecimento_id=1)

    assert _valor("medbot_ia_tokens_total", modelo="modelo-teste", feature="TRIAGEM", tipo="entrada") - antes["entrada"] == 1000
    assert _valor("medbot_ia_tokens_total", modelo="modelo-teste", feature="TRIAGEM", tipo="saida") - antes["saida"] == 200
    assert _valor("medbot_ia_chamadas_total", modelo="modelo-teste", feature="TRIAGEM") - antes["chamadas"] == 1
    assert round(_valor("medbot_ia_custo_usd_total", modelo="modelo-teste", feature="TRIAGEM") - antes["custo"], 6) == 0.0014


async def test_modelo_sem_preco_e_contado():
    antes = _valor("medbot_ia_modelo_sem_preco_total", modelo="modelo-desconhecido")
    assert billing.calcular_custo("modelo-desconhecido", 10, 10) == Decimal("0")
    assert _valor("medbot_ia_modelo_sem_preco_total", modelo="modelo-desconhecido") - antes == 1


def test_precos_de_modelos_de_producao_vem_do_ambiente():
    precos = billing.precos_dos_modelos('{"openai/gpt-4o-mini": {"input": 0.00000015, "output": 0.0000006}}')
    assert precos["openai/gpt-4o-mini"] == {"input": 0.00000015, "output": 0.0000006}
    assert precos["llama3.1:8b"] == {"input": 0.0, "output": 0.0}         # os locais continuam


def test_precos_invalidos_no_ambiente_sao_ignorados():
    assert "x" not in billing.precos_dos_modelos("isto não é json")
    assert "x" not in billing.precos_dos_modelos('{"x": {"input": "caro"}}')


async def test_latencia_da_ia_e_medida():
    antes = _valor("medbot_ia_latencia_segundos_count", feature="teste")
    async with metricas.medir_ia("teste"):
        pass
    assert _valor("medbot_ia_latencia_segundos_count", feature="teste") - antes == 1


# ── Cache ───────────────────────────────────────────────────────────────────

async def test_cache_conta_acertos_e_faltas_por_area():
    antes_falta = _valor("medbot_cache_total", area="relatorio", resultado="falta")
    antes_acerto = _valor("medbot_cache_total", area="relatorio", resultado="acerto")

    await cache.lembrar("relatorio:x:1", 60, AsyncMock(return_value=1))
    await cache.lembrar("relatorio:x:1", 60, AsyncMock(return_value=1))

    assert _valor("medbot_cache_total", area="relatorio", resultado="falta") - antes_falta == 1
    assert _valor("medbot_cache_total", area="relatorio", resultado="acerto") - antes_acerto == 1


async def test_cache_conta_erro_do_redis(monkeypatch):
    quebrado = AsyncMock()
    quebrado.get.side_effect = ConnectionError("caiu")
    monkeypatch.setattr(cache, "_cliente", lambda: quebrado)
    antes = _valor("medbot_cache_total", area="licenca", resultado="erro")

    await cache.obter("licenca:9")

    assert _valor("medbot_cache_total", area="licenca", resultado="erro") - antes == 1


# ── Celery ──────────────────────────────────────────────────────────────────

def test_fila_do_celery_e_lida_do_redis():
    redis = MagicMock()
    redis.llen.return_value = 7
    with patch.object(metricas, "_redis_sincrono", return_value=redis):
        assert metricas.tamanho_da_fila_celery() == 7
    redis.llen.assert_called_once_with("celery")


def test_fila_do_celery_sem_redis_devolve_menos_um():
    redis = MagicMock()
    redis.llen.side_effect = ConnectionError("caiu")
    with patch.object(metricas, "_redis_sincrono", return_value=redis):
        assert metricas.tamanho_da_fila_celery() == -1
