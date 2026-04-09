import asyncio
from datetime import datetime, timedelta, timezone

import structlog
from sqlalchemy import and_, select, update

from app.core.database import AsyncSessionLocal
from app.models.consulta import Consulta, ConsultaStatus
from app.models.slot import Slot, SlotStatus
from app.workers.celery_app import celery_app

log = structlog.get_logger(__name__)

TIMEOUT_CONFIRMACAO_MINUTOS = 10


async def _limpar_slots_expirados() -> int:
    """Libera slots agendados sem confirmacao apos 10 minutos.

    RF: SE o paciente nao confirmar em 10 minutos, liberar slot automaticamente.
    """
    limite = datetime.now(timezone.utc) - timedelta(minutes=TIMEOUT_CONFIRMACAO_MINUTOS)

    async with AsyncSessionLocal() as session:
        # Buscar consultas AGENDADAS (nao confirmadas) criadas ha mais de 10min
        result = await session.execute(
            select(Consulta).where(
                and_(
                    Consulta.status == ConsultaStatus.AGENDADA,
                    Consulta.created_at < limite,
                )
            )
        )
        consultas_expiradas = result.scalars().all()

        count = 0
        for consulta in consultas_expiradas:
            # Cancelar consulta
            consulta.status = ConsultaStatus.CANCELADA
            consulta.observacoes = "Cancelada automaticamente: timeout de confirmacao"

            # Liberar slot
            await session.execute(
                update(Slot)
                .where(Slot.id == consulta.slot_id)
                .values(status=SlotStatus.DISPONIVEL)
            )
            count += 1

        await session.commit()

        if count > 0:
            log.info("slots_expirados_liberados", quantidade=count)

        return count


@celery_app.task(name="app.workers.slot_cleanup.limpar_slots_expirados")
def limpar_slots_expirados() -> int:
    """Task Celery que limpa slots expirados."""
    return asyncio.run(_limpar_slots_expirados())


async def _limpar_slots_reservados() -> int:
    """Libera slots RESERVADO com mais de 10 minutos sem confirmacao.

    RF: SE o paciente nao confirmar o slot reservado em 10 minutos,
    slot volta para DISPONIVEL automaticamente.
    """
    limite = datetime.now(timezone.utc) - timedelta(minutes=TIMEOUT_CONFIRMACAO_MINUTOS)

    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(Slot).where(
                and_(
                    Slot.status == SlotStatus.RESERVADO,
                    Slot.reservado_em < limite,
                )
            )
        )
        slots_expirados = result.scalars().all()

        count = 0
        for slot in slots_expirados:
            await session.execute(
                update(Slot)
                .where(Slot.id == slot.id)
                .values(status=SlotStatus.DISPONIVEL, reservado_em=None)
            )
            count += 1

        await session.commit()

        if count > 0:
            log.info("slots_reservados_liberados", quantidade=count)

        return count


@celery_app.task(name="app.workers.slot_cleanup.limpar_slots_reservados")
def limpar_slots_reservados() -> int:
    """Task Celery que libera slots RESERVADO expirados."""
    return asyncio.run(_limpar_slots_reservados())
