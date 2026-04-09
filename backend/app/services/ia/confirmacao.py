"""Servico de confirmacao de agendamento pelo chat.

RF: Paciente confirma slot no chat, consulta e criada,
sessao encerrada com status AGENDOU.
"""

import redis.asyncio as aioredis
import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.consulta import (
    Consulta,
    ConsultaCanal,
    ConsultaTipo,
    ConsultaUrgencia,
)
from app.models.slot import Slot, SlotStatus

log = structlog.get_logger(__name__)


async def confirmar_agendamento_chat(
    db: AsyncSession,
    redis: aioredis.Redis,
    session_token: str,
    slot_id: int,
    paciente_id: int,
    especialidade_id: int,
    triagem_resumo: dict | None = None,
    canal: str = "PORTAL",
) -> dict:
    """Confirma agendamento a partir do chat.

    Fluxo:
    1. Verificar slot disponivel
    2. Criar consulta
    3. Marcar slot como AGENDADO
    4. Encerrar sessao de chat
    """
    # Buscar slot
    result = await db.execute(select(Slot).where(Slot.id == slot_id))
    slot = result.scalar_one_or_none()

    if not slot:
        return {"sucesso": False, "erro": "Slot nao encontrado", "consulta_id": None}

    if slot.status != SlotStatus.DISPONIVEL.value and slot.status != SlotStatus.DISPONIVEL:
        return {
            "sucesso": False,
            "erro": "Slot indisponivel para agendamento",
            "consulta_id": None,
        }

    # Reservar slot
    slot.status = SlotStatus.AGENDADO

    # Mapear canal
    canal_enum = ConsultaCanal.WHATSAPP if canal == "WHATSAPP" else ConsultaCanal.PORTAL

    # Criar consulta
    consulta = Consulta(
        slot_id=slot_id,
        paciente_id=paciente_id,
        medico_id=slot.medico_id,
        especialidade_id=especialidade_id,
        tipo=ConsultaTipo.EXTERNO,
        canal_origem=canal_enum,
        triagem_resumo=triagem_resumo,
        urgencia=ConsultaUrgencia.BAIXA,
    )
    db.add(consulta)
    await db.flush()

    # Encerrar sessao de chat
    await redis.delete(f"chat:session:{session_token}")

    log.info(
        "agendamento_confirmado_chat",
        slot_id=slot_id,
        paciente_id=paciente_id,
        session_token=session_token[:8] + "...",
    )

    return {
        "sucesso": True,
        "consulta_id": consulta.id,
        "erro": None,
    }
