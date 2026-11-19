"""Job: envia ao profissional o resumo da triagem 30 minutos antes do atendimento (T93).

Roda a cada 15 minutos. Cada atendimento recebe o resumo uma vez (`atendimentos.resumo_enviado_em`).
"""

from datetime import datetime, timedelta, timezone

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.tempo import agora_local
from app.models.atendimento import Atendimento, AtendimentoStatus
from app.models.cliente import Cliente
from app.models.estabelecimento import EstabelecimentoSaude
from app.models.profissional import Profissional
from app.models.slot import Slot
from app.services.ia.resumo_triagem import texto_do_resumo
from app.services.mensageria import enviar_whatsapp
from app.services.notificacao_service import enviar_email
from app.workers.celery_app import celery_app

log = structlog.get_logger(__name__)

ANTECEDENCIA_MIN = 30

_ENCERRADOS = (
    AtendimentoStatus.CANCELADA,
    AtendimentoStatus.REALIZADA,
    AtendimentoStatus.FALTA,
    AtendimentoStatus.EM_ATENDIMENTO,
)


async def _email(destinatario: str, assunto: str, corpo: str) -> bool:
    return await enviar_email(destinatario=destinatario, assunto=assunto, corpo_html=corpo)


async def enviar_resumos_pendentes(
    db: AsyncSession,
    agora=agora_local,
    enviar_wa=enviar_whatsapp,
    enviar_mail=_email,
    estabelecimento_id: int | None = None,
) -> dict:
    """Envia por WhatsApp e e-mail o resumo dos atendimentos que começam nos próximos 30 minutos.

    `agora(fuso)` devolve a hora local da unidade (injetável para teste).
    """
    hoje = agora(None).date()  # um dia de folga para cada lado cobre qualquer fuso
    restricao = (
        (Atendimento.estabelecimento_id == estabelecimento_id,) if estabelecimento_id is not None else ()
    )
    linhas = (
        await db.execute(
            select(Atendimento, Slot, Cliente.nome, Profissional, EstabelecimentoSaude.timezone)
            .join(Slot, Atendimento.slot_id == Slot.id)
            .join(Cliente, Atendimento.cliente_id == Cliente.id)
            .join(Profissional, Atendimento.profissional_id == Profissional.id)
            .join(EstabelecimentoSaude, Atendimento.estabelecimento_id == EstabelecimentoSaude.id)
            .where(
                Atendimento.resumo_enviado_em.is_(None),
                Atendimento.triagem_resumo.isnot(None),
                Atendimento.status.notin_(_ENCERRADOS),
                Slot.data.between(hoje - timedelta(days=1), hoje + timedelta(days=1)),
                *restricao,
            )
            .order_by(Slot.data, Slot.hora_inicio)
        )
    ).all()

    enviados = 0
    for atendimento, slot, cliente_nome, profissional, fuso in linhas:
        resumo = texto_do_resumo(atendimento.triagem_resumo)
        if resumo is None:
            continue
        local = agora(fuso)
        falta = datetime.combine(slot.data, slot.hora_inicio) - local
        if not (timedelta(0) < falta <= timedelta(minutes=ANTECEDENCIA_MIN)):
            continue

        hora = slot.hora_inicio.strftime("%H:%M")
        texto = (
            f"Próximo atendimento às {hora}: {cliente_nome}.\n\n"
            f"Resumo da triagem pelo chat:\n{resumo}\n\n"
            "Este resumo traz apenas o relato do paciente e não substitui a sua avaliação."
        )
        ok_wa = bool(profissional.telefone) and await enviar_wa(profissional.telefone, texto)
        ok_mail = bool(profissional.email) and await enviar_mail(
            profissional.email,
            f"Resumo de triagem — atendimento das {hora}",
            texto.replace("\n", "<br>"),
        )
        if ok_wa or ok_mail:
            atendimento.resumo_enviado_em = datetime.now(timezone.utc)
            enviados += 1
        log.info("resumo_medico", atendimento_id=atendimento.id, whatsapp=ok_wa, email=ok_mail)

    await db.flush()
    return {"enviados": enviados}


@celery_app.task(name="enviar_resumos_triagem")
def enviar_resumos_triagem() -> dict:
    from app.workers.base import executar

    return executar(lambda db, _redis: enviar_resumos_pendentes(db))
