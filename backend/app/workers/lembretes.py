"""Jobs Celery para envio de lembretes de consulta.

D-1: Lembrete 24 horas antes da consulta.
H-2: Lembrete 2 horas antes da consulta.
"""

from datetime import date, datetime, timedelta

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from app.models.atendimento import Atendimento, AtendimentoStatus
from app.models.slot import Slot
from app.services.notificacao_service import enviar_email, template_email_lembrete
from app.services.whatsapp_service import (
    enviar_mensagem_whatsapp,
    template_lembrete_consulta,
)
from app.workers.celery_app import celery_app

log = structlog.get_logger(__name__)


async def buscar_consultas_para_lembrete_d1(db: AsyncSession) -> list[Atendimento]:
    """Busca atendimentos agendados para amanha (D-1)."""
    amanha = date.today() + timedelta(days=1)

    query = (
        select(Atendimento)
        .join(Slot, Atendimento.slot_id == Slot.id)
        .where(
            Atendimento.status == AtendimentoStatus.AGENDADA,
            Slot.data == amanha,
        )
        .options(
            joinedload(Atendimento.cliente),
            joinedload(Atendimento.profissional),
            joinedload(Atendimento.especialidade),
            joinedload(Atendimento.slot),
        )
    )

    result = await db.execute(query)
    return list(result.scalars().all())


async def buscar_consultas_para_lembrete_h2(db: AsyncSession) -> list[Atendimento]:
    """Busca atendimentos nas proximas 2 horas (H-2)."""
    agora = datetime.now()
    limite = agora + timedelta(hours=2)
    hoje = date.today()

    query = (
        select(Atendimento)
        .join(Slot, Atendimento.slot_id == Slot.id)
        .where(
            Atendimento.status == AtendimentoStatus.AGENDADA,
            Slot.data == hoje,
            Slot.hora_inicio >= agora.time(),
            Slot.hora_inicio <= limite.time(),
        )
        .options(
            joinedload(Atendimento.cliente),
            joinedload(Atendimento.profissional),
            joinedload(Atendimento.especialidade),
            joinedload(Atendimento.slot),
        )
    )

    result = await db.execute(query)
    return list(result.scalars().all())


async def enviar_lembrete(atendimento, tipo: str = "D-1") -> None:
    """Envia lembrete via WhatsApp e email para um atendimento.

    Falha em um canal nao impede envio no outro.
    """
    paciente = atendimento.cliente
    medico = atendimento.profissional
    especialidade = atendimento.especialidade
    slot = atendimento.slot

    # WhatsApp
    msg_wa = template_lembrete_consulta(
        paciente_nome=paciente.nome,
        medico_nome=medico.nome,
        especialidade=especialidade.nome,
        data=slot.data,
        hora=slot.hora_inicio,
    )
    wa_ok = await enviar_mensagem_whatsapp(
        telefone=paciente.telefone,
        mensagem=msg_wa,
    )

    # Email
    assunto, corpo = template_email_lembrete(
        paciente_nome=paciente.nome,
        medico_nome=medico.nome,
        especialidade=especialidade.nome,
        data=slot.data,
        hora=slot.hora_inicio,
    )
    email_ok = await enviar_email(
        destinatario=paciente.email,
        assunto=assunto,
        corpo_html=corpo,
    )

    log.info(
        "lembrete_enviado",
        atendimento_id=atendimento.id,
        tipo=tipo,
        whatsapp=wa_ok,
        email=email_ok,
    )


@celery_app.task(name="enviar_lembretes_d1")
def enviar_lembretes_d1() -> dict:
    """Task Celery: envia lembretes D-1 (24h antes)."""
    import asyncio

    from app.core.database import AsyncSessionLocal

    async def _run():
        async with AsyncSessionLocal() as db:
            atendimentos = await buscar_consultas_para_lembrete_d1(db)
            for atendimento in atendimentos:
                await enviar_lembrete(atendimento, tipo="D-1")
            return {"enviados": len(atendimentos)}

    return asyncio.get_event_loop().run_until_complete(_run())


@celery_app.task(name="enviar_lembretes_h2")
def enviar_lembretes_h2() -> dict:
    """Task Celery: envia lembretes H-2 (2h antes)."""
    import asyncio

    from app.core.database import AsyncSessionLocal

    async def _run():
        async with AsyncSessionLocal() as db:
            atendimentos = await buscar_consultas_para_lembrete_h2(db)
            for atendimento in atendimentos:
                await enviar_lembrete(atendimento, tipo="H-2")
            return {"enviados": len(atendimentos)}

    return asyncio.get_event_loop().run_until_complete(_run())
