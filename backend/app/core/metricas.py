"""Métricas para o Prometheus (observabilidade).

Expostas em GET /metrics (fora da documentação da API). Com METRICS_TOKEN definido, o endpoint exige
`Authorization: Bearer <token>`; em produção ele deve ficar acessível só à rede interna do Prometheus.

Além das métricas HTTP (requisições, erros, latência por rota), o MedBot publica:
- uso de IA: tokens, chamadas, custo, latência e modelos sem preço cadastrado;
- cache: acertos, faltas e erros por área (licença, catálogo do chat, relatórios);
- tamanho da fila do Celery.

Os contadores vivem na memória do processo: com mais de um worker do uvicorn, cada worker teria os seus
(seria preciso o modo multiprocesso do prometheus_client). Hoje a API roda com um worker.
"""

import time
from contextlib import asynccontextmanager
from functools import lru_cache

import structlog
from fastapi import FastAPI, Request, Response
from prometheus_client import CONTENT_TYPE_LATEST, REGISTRY, Counter, Gauge, Histogram, generate_latest
from prometheus_fastapi_instrumentator import Instrumentator

from app.core.config import settings

log = structlog.get_logger(__name__)

IA_TOKENS = Counter(
    "medbot_ia_tokens", "Tokens enviados e recebidos dos modelos de IA", ["modelo", "feature", "tipo"]
)
IA_CHAMADAS = Counter("medbot_ia_chamadas", "Chamadas aos modelos de IA", ["modelo", "feature"])
IA_CUSTO = Counter("medbot_ia_custo_usd", "Custo estimado das chamadas de IA, em dólares", ["modelo", "feature"])
IA_SEM_PRECO = Counter(
    "medbot_ia_modelo_sem_preco", "Chamadas a modelos sem preço cadastrado (custo aparece zerado)", ["modelo"]
)
IA_LATENCIA = Histogram(
    "medbot_ia_latencia_segundos",
    "Tempo de resposta dos modelos de IA",
    ["feature"],
    buckets=(0.25, 0.5, 1, 2, 4, 8, 15, 30, 60),
)
CACHE = Counter("medbot_cache", "Leituras do cache no Redis", ["area", "resultado"])
CELERY_FILA = Gauge("medbot_celery_fila_tamanho", "Tarefas esperando na fila do Celery (-1: Redis fora do ar)")


def registrar_ia(modelo: str, feature: str, entrada: int, saida: int, custo_usd: float) -> None:
    IA_TOKENS.labels(modelo, feature, "entrada").inc(entrada)
    IA_TOKENS.labels(modelo, feature, "saida").inc(saida)
    IA_CHAMADAS.labels(modelo, feature).inc()
    IA_CUSTO.labels(modelo, feature).inc(custo_usd)


@asynccontextmanager
async def medir_ia(feature: str):
    """Mede o tempo de uma chamada à IA (inclusive quando ela falha)."""
    inicio = time.perf_counter()
    try:
        yield
    finally:
        IA_LATENCIA.labels(feature).observe(time.perf_counter() - inicio)


def registrar_cache(chave: str, resultado: str) -> None:
    CACHE.labels(chave.split(":", 1)[0], resultado).inc()


@lru_cache(maxsize=1)
def _redis_sincrono():
    import redis

    return redis.Redis.from_url(settings.redis_url, socket_timeout=0.5, socket_connect_timeout=0.5)


def tamanho_da_fila_celery() -> int:
    try:
        return int(_redis_sincrono().llen("celery"))
    except Exception:  # Redis fora do ar: o painel mostra -1 em vez de esconder o problema
        return -1


CELERY_FILA.set_function(tamanho_da_fila_celery)


def instalar(app: FastAPI) -> None:
    """Mede todas as rotas e publica GET /metrics."""
    Instrumentator(excluded_handlers=["/metrics", "/health"]).instrument(app)

    @app.get("/metrics", include_in_schema=False)
    async def metrics(request: Request) -> Response:
        if settings.metrics_token and request.headers.get("authorization") != f"Bearer {settings.metrics_token}":
            return Response(status_code=401)
        return Response(generate_latest(REGISTRY), media_type=CONTENT_TYPE_LATEST)
