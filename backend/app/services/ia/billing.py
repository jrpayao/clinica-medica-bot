"""Servico de billing para rastreamento de tokens e custos.

REGRA INVIOLAVEL: Toda chamada LLM DEVE passar por este servico.
"""

from datetime import date
from decimal import Decimal

import structlog
from sqlalchemy import Date, cast, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import MODEL_PRICING
from app.models.estabelecimento import EstabelecimentoSaude
from app.models.token_usage import TokenFeature, TokenUsage

log = structlog.get_logger(__name__)


def calcular_custo(
    modelo: str, prompt_tokens: int, completion_tokens: int
) -> Decimal:
    """Calcula custo em USD baseado no modelo e quantidade de tokens."""
    pricing = MODEL_PRICING.get(modelo)
    if not pricing:
        log.warning("modelo_sem_pricing", modelo=modelo)
        return Decimal("0")

    custo_input = Decimal(str(pricing["input"])) * prompt_tokens
    custo_output = Decimal(str(pricing["output"])) * completion_tokens
    return custo_input + custo_output


async def registrar_uso(
    db: AsyncSession,
    session_id: int,
    modelo: str,
    feature: str,
    prompt_tokens: int,
    completion_tokens: int,
    user_type: str = "EXTERNO",
    estabelecimento_id: int | None = None,
) -> TokenUsage:
    """Registra uso de tokens no banco.

    OBRIGATORIO apos toda chamada LLM.
    Passar estabelecimento_id sempre que disponivel para habilitar billing por tenant.
    """
    total_tokens = prompt_tokens + completion_tokens
    cost_usd = calcular_custo(modelo, prompt_tokens, completion_tokens)

    try:
        feature_enum = TokenFeature(feature.upper())
    except ValueError:
        feature_enum = TokenFeature.GERAL

    registro = TokenUsage(
        session_id=session_id,
        estabelecimento_id=estabelecimento_id,
        modelo=modelo,
        feature=feature_enum,
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
        total_tokens=total_tokens,
        cost_usd=cost_usd,
        user_type=user_type,
    )
    db.add(registro)
    await db.flush()

    log.info(
        "token_usage_registrado",
        session_id=session_id,
        estabelecimento_id=estabelecimento_id,
        modelo=modelo,
        feature=feature,
        total_tokens=total_tokens,
        cost_usd=str(cost_usd),
    )
    return registro


def _aplicar_filtro_estabelecimento(
    query,
    estabelecimento_id: int | None,
) :
    """Aplica filtro de estabelecimento_id na query se fornecido."""
    if estabelecimento_id is not None:
        query = query.where(TokenUsage.estabelecimento_id == estabelecimento_id)
    return query


async def obter_resumo_diario(
    db: AsyncSession,
    data: date | None = None,
    estabelecimento_id: int | None = None,
) -> dict:
    """Retorna total de tokens e custo para um dia."""
    if data is None:
        data = date.today()

    query = select(
        func.sum(TokenUsage.total_tokens),
        func.sum(TokenUsage.cost_usd),
    ).where(cast(TokenUsage.created_at, Date) == data)
    query = _aplicar_filtro_estabelecimento(query, estabelecimento_id)

    result = await db.execute(query)
    row = result.one()

    return {
        "data": data.isoformat(),
        "total_tokens": row[0] or 0,
        "total_custo_usd": row[1] or Decimal("0"),
    }


async def obter_resumo_por_modelo(
    db: AsyncSession,
    data: date | None = None,
    estabelecimento_id: int | None = None,
) -> list[dict]:
    """Retorna uso agrupado por modelo para um dia."""
    if data is None:
        data = date.today()

    query = (
        select(
            TokenUsage.modelo,
            func.count(TokenUsage.id),
            func.sum(TokenUsage.total_tokens),
            func.sum(TokenUsage.cost_usd),
        )
        .where(cast(TokenUsage.created_at, Date) == data)
        .group_by(TokenUsage.modelo)
        .order_by(func.sum(TokenUsage.cost_usd).desc())
    )
    query = _aplicar_filtro_estabelecimento(query, estabelecimento_id)

    result = await db.execute(query)
    return [
        {
            "modelo": row[0],
            "total_chamadas": row[1],
            "total_tokens": row[2],
            "custo_total": float(row[3] or 0),
        }
        for row in result.all()
    ]


async def obter_resumo_por_feature(
    db: AsyncSession,
    data: date | None = None,
    estabelecimento_id: int | None = None,
) -> list[dict]:
    """Retorna uso agrupado por feature para um dia."""
    if data is None:
        data = date.today()

    query = (
        select(
            TokenUsage.feature,
            func.count(TokenUsage.id),
            func.sum(TokenUsage.total_tokens),
            func.sum(TokenUsage.cost_usd),
        )
        .where(cast(TokenUsage.created_at, Date) == data)
        .group_by(TokenUsage.feature)
        .order_by(func.sum(TokenUsage.cost_usd).desc())
    )
    query = _aplicar_filtro_estabelecimento(query, estabelecimento_id)

    result = await db.execute(query)
    return [
        {
            "feature": row[0] if isinstance(row[0], str) else row[0].value,
            "total_chamadas": row[1],
            "total_tokens": row[2],
            "custo_total": float(row[3] or 0),
        }
        for row in result.all()
    ]


async def obter_custo_diario_total(
    db: AsyncSession,
    data: date | None = None,
    estabelecimento_id: int | None = None,
) -> Decimal:
    """Retorna custo total do dia."""
    if data is None:
        data = date.today()

    query = select(func.sum(TokenUsage.cost_usd)).where(
        cast(TokenUsage.created_at, Date) == data
    )
    query = _aplicar_filtro_estabelecimento(query, estabelecimento_id)
    result = await db.execute(query)
    return result.scalar() or Decimal("0")


async def obter_ranking_por_estabelecimento(
    db: AsyncSession,
    data: date | None = None,
) -> list[dict]:
    """Retorna custo agregado por estabelecimento para um dia. Apenas ADMIN_GLOBAL."""
    if data is None:
        data = date.today()

    query = (
        select(
            TokenUsage.estabelecimento_id,
            EstabelecimentoSaude.nome,
            func.count(TokenUsage.id),
            func.sum(TokenUsage.total_tokens),
            func.sum(TokenUsage.cost_usd),
        )
        .join(
            EstabelecimentoSaude,
            TokenUsage.estabelecimento_id == EstabelecimentoSaude.id,
            isouter=True,
        )
        .where(cast(TokenUsage.created_at, Date) == data)
        .where(TokenUsage.estabelecimento_id.isnot(None))
        .group_by(TokenUsage.estabelecimento_id, EstabelecimentoSaude.nome)
        .order_by(func.sum(TokenUsage.cost_usd).desc())
    )

    result = await db.execute(query)
    return [
        {
            "estabelecimento_id": row[0],
            "nome": row[1] or f"Estabelecimento #{row[0]}",
            "total_chamadas": row[2],
            "total_tokens": row[3],
            "custo_total": float(row[4] or 0),
        }
        for row in result.all()
    ]


async def listar_registros(
    db: AsyncSession,
    data_inicio: date | None = None,
    data_fim: date | None = None,
    estabelecimento_id: int | None = None,
) -> list[TokenUsage]:
    """Lista registros de token_usage com filtros de data e estabelecimento."""
    query = select(TokenUsage).order_by(TokenUsage.created_at.desc())

    if data_inicio:
        query = query.where(cast(TokenUsage.created_at, Date) >= data_inicio)
    if data_fim:
        query = query.where(cast(TokenUsage.created_at, Date) <= data_fim)
    query = _aplicar_filtro_estabelecimento(query, estabelecimento_id)

    result = await db.execute(query)
    return list(result.scalars().all())
