"""Service de fila de espera inteligente (T89)."""

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.fila_espera import FilaEspera, FilaEsperaStatus

log = structlog.get_logger(__name__)


class FilaEsperaService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def entrar(
        self,
        cliente_id: int,
        estabelecimento_id: int,
        especialidade_id: int | None,
        convenio_id: int | None,
    ) -> FilaEspera:
        """Adiciona cliente à fila de espera com status AGUARDANDO."""
        entrada = FilaEspera(
            cliente_id=cliente_id,
            estabelecimento_id=estabelecimento_id,
            especialidade_id=especialidade_id,
            convenio_id=convenio_id,
            status=FilaEsperaStatus.AGUARDANDO,
        )
        self.db.add(entrada)
        await self.db.flush()
        log.info("fila_espera_entrada", cliente_id=cliente_id, id=entrada.id)
        return entrada

    async def sair(self, fila_id: int, cliente_id: int) -> None:
        """Remove cliente da fila (status → CANCELADO)."""
        result = await self.db.execute(
            select(FilaEspera).where(
                FilaEspera.id == fila_id,
                FilaEspera.cliente_id == cliente_id,
            )
        )
        entrada = result.scalar_one_or_none()
        if entrada:
            entrada.status = FilaEsperaStatus.CANCELADO
            await self.db.flush()
            log.info("fila_espera_saida", fila_id=fila_id, cliente_id=cliente_id)

    async def listar_aguardando(self, estabelecimento_id: int) -> list[FilaEspera]:
        """Retorna entradas com status AGUARDANDO para o estabelecimento."""
        result = await self.db.execute(
            select(FilaEspera)
            .where(
                FilaEspera.estabelecimento_id == estabelecimento_id,
                FilaEspera.status == FilaEsperaStatus.AGUARDANDO,
            )
            .order_by(FilaEspera.created_at.asc())
        )
        return result.scalars().all()
