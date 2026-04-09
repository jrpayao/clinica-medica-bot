import redis.asyncio as aioredis

from app.core.config import settings

redis_client = aioredis.from_url(
    settings.redis_url,
    decode_responses=True,
)


async def get_redis() -> aioredis.Redis:
    """Dependency para injetar Redis client nos handlers."""
    return redis_client


def get_redis_client() -> aioredis.Redis:
    """Retorna o Redis client global (para uso fora de Depends)."""
    return redis_client


async def get_chat_session(session_token: str) -> dict | None:
    """Recupera sessao de chat do Redis."""
    data = await redis_client.get(f"chat:session:{session_token}")
    if data is None:
        return None
    import json
    return json.loads(data)


async def set_chat_session(session_token: str, data: dict, ttl_seconds: int = 1800) -> None:
    """Salva sessao de chat no Redis com TTL de 30 minutos."""
    import json
    await redis_client.set(
        f"chat:session:{session_token}",
        json.dumps(data),
        ex=ttl_seconds,
    )


async def delete_chat_session(session_token: str) -> None:
    """Remove sessao de chat do Redis."""
    await redis_client.delete(f"chat:session:{session_token}")
