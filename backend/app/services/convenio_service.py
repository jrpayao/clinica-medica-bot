import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.convenio import Convenio

log = structlog.get_logger(__name__)


class ConvenioService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def listar_ativos(self, estabelecimento_id: int) -> list[Convenio]:
        result = await self.db.execute(
            select(Convenio)
            .where(Convenio.estabelecimento_id == estabelecimento_id, Convenio.ativo == True)  # noqa: E712
            .order_by(Convenio.nome)
        )
        return result.scalars().all()
