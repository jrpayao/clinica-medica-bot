"""Relógio da aplicação no fuso de operação de cada unidade.

Slots guardam data e hora locais (DATE/TIME sem fuso). Comparar com o relógio do servidor
quebra em produção, onde o VPS roda em UTC: às 21h de Brasília o servidor já está no dia seguinte.
Cada estabelecimento tem o seu fuso (`estabelecimentos.timezone`); APP_TIMEZONE é o padrão.
"""

from datetime import date, datetime
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings


def fuso_valido(fuso: object) -> str:
    """Devolve o fuso informado se existir na base IANA; senão o padrão da plataforma."""
    if isinstance(fuso, str) and fuso:
        try:
            ZoneInfo(fuso)
            return fuso
        except (ZoneInfoNotFoundError, ValueError):
            pass
    return settings.app_timezone


def agora_local(fuso: str | None = None) -> datetime:
    """Data e hora atuais no fuso da unidade (ou no padrão da plataforma), sem tzinfo."""
    return datetime.now(ZoneInfo(fuso_valido(fuso))).replace(tzinfo=None)


def hoje_local(fuso: str | None = None) -> date:
    return agora_local(fuso).date()


async def fuso_do_estabelecimento(db: AsyncSession, estabelecimento_id: int | None) -> str:
    """Fuso cadastrado na unidade; padrão da plataforma quando não há unidade ou cadastro."""
    if estabelecimento_id is None:
        return settings.app_timezone
    from app.models.estabelecimento import EstabelecimentoSaude

    resultado = await db.execute(
        select(EstabelecimentoSaude.timezone).where(EstabelecimentoSaude.id == estabelecimento_id)
    )
    return fuso_valido(resultado.scalar_one_or_none())
