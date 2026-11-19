"""Execução de rotinas assíncronas dentro de tasks Celery.

Cada execução abre o próprio engine (sem pool) e o próprio cliente Redis: as conexões do engine
global ficam presas ao event loop em que foram criadas, e `asyncio.run` cria um loop novo por task.
"""

import asyncio
from collections.abc import Awaitable, Callable
from typing import Any

import redis.asyncio as aioredis
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.core.config import settings


async def _com_sessao(rotina: Callable[[AsyncSession, aioredis.Redis], Awaitable[Any]]) -> Any:
    engine = create_async_engine(settings.database_url, poolclass=NullPool)
    redis = aioredis.from_url(settings.redis_url, decode_responses=True)
    try:
        async with async_sessionmaker(engine, expire_on_commit=False)() as db:
            resultado = await rotina(db, redis)
            await db.commit()
            return resultado
    finally:
        await redis.aclose()
        await engine.dispose()


def executar(rotina: Callable[[AsyncSession, aioredis.Redis], Awaitable[Any]]) -> Any:
    """Roda `rotina(db, redis)` em um event loop novo e confirma a transação."""
    return asyncio.run(_com_sessao(rotina))
