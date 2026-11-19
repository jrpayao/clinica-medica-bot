"""Cache no Redis para leituras repetidas do banco.

Regra: o cache nunca derruba nada. Se o Redis estiver fora do ar ou devolver algo inesperado,
a leitura vai direto ao banco e o erro só aparece no log.

Os valores são guardados em JSON, sempre com validade (TTL). Quem altera o dado de origem apaga
a chave correspondente; a validade limita o tempo de um valor desatualizado se alguma alteração
escapar da invalidação.
"""

import json
from collections.abc import Awaitable, Callable
from typing import Any

import structlog

log = structlog.get_logger(__name__)

PREFIXO = "cache:"

TTL_LICENCA = 60            # consultada em toda requisição; suspensão invalida na hora
TTL_CATALOGO_CHAT = 600     # especialidades e convênios de cada sessão nova do chat
TTL_RELATORIO = 60          # agregações do painel; o botão Atualizar ignora o cache


def _cliente():
    from app.core.redis import get_redis_client

    return get_redis_client()


def chave_licenca(estabelecimento_id: int) -> str:
    return f"licenca:{estabelecimento_id}"


def chave_catalogo_chat(estabelecimento_id: int) -> str:
    return f"chat:catalogo:{estabelecimento_id}"


async def obter(chave: str) -> Any | None:
    try:
        bruto = await _cliente().get(PREFIXO + chave)
        return json.loads(bruto) if bruto else None
    except Exception as erro:  # Redis fora do ar, valor corrompido: segue sem cache
        log.warning("cache_leitura_falhou", chave=chave, erro=str(erro)[:200])
        return None


async def gravar(chave: str, valor: Any, ttl: int) -> None:
    try:
        await _cliente().set(PREFIXO + chave, json.dumps(valor, default=str), ex=ttl)
    except Exception as erro:
        log.warning("cache_gravacao_falhou", chave=chave, erro=str(erro)[:200])


async def apagar(*chaves: str) -> None:
    try:
        await _cliente().delete(*(PREFIXO + c for c in chaves))
    except Exception as erro:
        log.warning("cache_invalidacao_falhou", chaves=list(chaves), erro=str(erro)[:200])


async def lembrar(chave: str, ttl: int, carregar: Callable[[], Awaitable[Any]]) -> Any:
    """Devolve o valor em cache ou carrega, guarda e devolve."""
    valor = await obter(chave)
    if valor is not None:
        return valor
    valor = await carregar()
    await gravar(chave, valor, ttl)
    return valor
