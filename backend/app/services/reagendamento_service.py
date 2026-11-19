"""Reagendamento após cancelamento pela unidade ou pelo profissional (T96–T98).

Quando quem cancela é a unidade ou o profissional, o cliente recebe por WhatsApp até três novos horários.
Ele responde com o número da opção (ou 0 para nenhuma). Sem resposta, sem horário ou sem telefone,
o caso vira pendência para a recepção.
"""

from datetime import datetime, timedelta, timezone

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.atendimento import Atendimento, AtendimentoCanal, MotivoCancelamento
from app.models.cliente import Cliente
from app.models.cliente_convenio import ClienteConvenio
from app.models.especialidade import Especialidade
from app.models.profissional import Profissional
from app.models.reagendamento import (
    STATUS_QUE_PEDEM_CONTATO,
    ReagendamentoOferta,
    ReagendamentoStatus,
)
from app.models.slot import Slot, SlotStatus
from app.services.agenda_service import AgendaService
from app.services.mensageria import enviar_whatsapp, notificar_recepcao, registrar_pendencia

log = structlog.get_logger(__name__)

PRAZO_RESPOSTA_MIN = 30
MAX_OPCOES = 3
ORIGENS_QUE_REAGENDAM = (MotivoCancelamento.MEDICO, MotivoCancelamento.ESTABELECIMENTO)

_MOTIVO_PENDENCIA = {
    ReagendamentoStatus.RECUSADA: "o cliente recusou os horários oferecidos",
    ReagendamentoStatus.EXPIRADA: "o cliente não respondeu à oferta de novos horários",
    ReagendamentoStatus.SEM_HORARIO: "não há horário livre para oferecer",
    ReagendamentoStatus.SEM_CONTATO: "não foi possível avisar o cliente pelo WhatsApp",
}


async def cancelar_com_motivo(
    db: AsyncSession,
    redis,
    atendimento_id: int,
    texto_motivo: str,
    origem: MotivoCancelamento,
    estabelecimento_id: int | None = None,
    enviar=enviar_whatsapp,
    avisar=notificar_recepcao,
) -> Atendimento:
    """Cancela registrando quem originou. Unidade e profissional disparam a oferta de reagendamento."""
    atendimento = await AgendaService(db).cancelar_consulta(atendimento_id, texto_motivo, estabelecimento_id)
    atendimento.motivo_cancelamento = origem

    if origem == MotivoCancelamento.MEDICO:
        slot = (await db.execute(select(Slot).where(Slot.id == atendimento.slot_id))).scalar_one_or_none()
        if slot is not None:
            slot.status = SlotStatus.BLOQUEADO
            slot.motivo_bloqueio = f"Cancelado pelo profissional: {texto_motivo}"[:500]

    await db.flush()
    if origem in ORIGENS_QUE_REAGENDAM:
        await oferecer_reagendamento(db, redis, atendimento, enviar=enviar, avisar=avisar)
    await db.refresh(atendimento)  # updated_at muda no flush; sem recarregar, a resposta da API falha
    return atendimento


async def _descrever_slots(db: AsyncSession, slot_ids: list[int]) -> list[tuple[Slot, str]]:
    if not slot_ids:
        return []
    linhas = (
        await db.execute(
            select(Slot, Profissional.nome)
            .join(Profissional, Slot.profissional_id == Profissional.id)
            .where(Slot.id.in_(slot_ids))
        )
    ).all()
    por_id = {slot.id: (slot, nome) for slot, nome in linhas}
    return [por_id[i] for i in slot_ids if i in por_id]


def _linhas_de_opcoes(slots: list[tuple[Slot, str]]) -> str:
    return "\n".join(
        f"{n} - {slot.data.strftime('%d/%m/%Y')} às {slot.hora_inicio.strftime('%H:%M')} com {profissional}"
        for n, (slot, profissional) in enumerate(slots, start=1)
    )


def _instrucao(total: int) -> str:
    numeros = " ou ".join(str(n) for n in range(1, total + 1)) if total <= 2 else f"de 1 a {total}"
    return f"Responda com o número do horário ({numeros}) ou *0* se nenhum servir."


async def _avisar_recepcao(db: AsyncSession, oferta: ReagendamentoOferta, avisar) -> None:
    cliente = (await db.execute(select(Cliente).where(Cliente.id == oferta.cliente_id))).scalar_one()
    motivo = _MOTIVO_PENDENCIA.get(oferta.status, "é preciso contato")
    await avisar(
        db,
        oferta.estabelecimento_id,
        "Remarcação pendente — contato com o cliente",
        f"<p>O atendimento de <strong>{cliente.nome}</strong> foi cancelado pela unidade e {motivo}.</p>"
        f"<p>Telefone: {cliente.telefone or 'não informado'}.</p>"
        "<p>Veja as remarcações pendentes no painel, em Lista de espera.</p>",
    )


async def oferecer_reagendamento(
    db: AsyncSession, redis, atendimento: Atendimento, enviar=enviar_whatsapp, avisar=notificar_recepcao
) -> ReagendamentoOferta:
    """Busca até três horários da mesma especialidade e os envia numerados ao cliente."""
    cliente = (await db.execute(select(Cliente).where(Cliente.id == atendimento.cliente_id))).scalar_one()
    convenio_id = cliente.convenio_id
    if atendimento.cliente_convenio_id:
        convenio_id = (
            await db.execute(
                select(ClienteConvenio.convenio_id).where(ClienteConvenio.id == atendimento.cliente_convenio_id)
            )
        ).scalar_one_or_none() or convenio_id

    livres = await AgendaService(db).buscar_disponibilidade(
        estabelecimento_id=atendimento.estabelecimento_id,
        especialidade_id=atendimento.especialidade_id,
        convenio_id=convenio_id,
    )
    slot_ids = [s.id for s in livres if s.id != atendimento.slot_id][:MAX_OPCOES]

    oferta = ReagendamentoOferta(
        atendimento_id=atendimento.id,
        cliente_id=cliente.id,
        estabelecimento_id=atendimento.estabelecimento_id,
        slot_ids=slot_ids,
        status=ReagendamentoStatus.PENDENTE,
    )
    db.add(oferta)

    primeiro_nome = (cliente.nome or "").split()[0] if cliente.nome else ""
    slot_original = (await db.execute(select(Slot).where(Slot.id == atendimento.slot_id))).scalar_one()
    abertura = (
        f"Olá, {primeiro_nome}. Precisamos cancelar o seu atendimento de "
        f"{slot_original.data.strftime('%d/%m/%Y')} às {slot_original.hora_inicio.strftime('%H:%M')}. "
        "Pedimos desculpas pelo transtorno."
    )

    if not slot_ids:
        oferta.status = ReagendamentoStatus.SEM_HORARIO
        await enviar(
            cliente.telefone,
            f"{abertura}\n\nNo momento não temos outro horário livre. A recepção vai entrar em contato para remarcar.",
        )
    else:
        opcoes = await _descrever_slots(db, slot_ids)
        texto = (
            f"{abertura}\n\nTemos estes horários para remarcar:\n{_linhas_de_opcoes(opcoes)}\n\n"
            f"{_instrucao(len(opcoes))}"
        )
        if cliente.telefone and await enviar(cliente.telefone, texto):
            oferta.enviado_em = datetime.now(timezone.utc)
            await db.flush()
            await registrar_pendencia(
                redis,
                cliente.telefone,
                {"tipo": "reagendamento", "oferta_id": oferta.id},
                ttl=PRAZO_RESPOSTA_MIN * 60,
            )
        else:
            oferta.status = ReagendamentoStatus.SEM_CONTATO

    await db.flush()
    if oferta.status != ReagendamentoStatus.PENDENTE:
        await _avisar_recepcao(db, oferta, avisar)
    log.info(
        "reagendamento_oferta", atendimento_id=atendimento.id, oferta_id=oferta.id,
        status=oferta.status.value, opcoes=len(slot_ids),
    )
    return oferta


async def responder_reagendamento(
    db: AsyncSession, oferta_id: int, mensagem: str, avisar=notificar_recepcao
) -> tuple[str, bool]:
    """Trata a resposta do cliente. Devolve (texto de resposta, conversa encerrada?)."""
    oferta = (
        await db.execute(select(ReagendamentoOferta).where(ReagendamentoOferta.id == oferta_id))
    ).scalar_one_or_none()
    if oferta is None or oferta.status != ReagendamentoStatus.PENDENTE:
        return ("Essa oferta de horários não está mais válida. A recepção vai falar com você para remarcar.", True)

    opcao = mensagem.strip().strip(".! ")
    if opcao == "0" or opcao.lower() in ("nenhum", "nenhuma", "nao", "não"):
        oferta.status = ReagendamentoStatus.RECUSADA
        oferta.respondido_em = datetime.now(timezone.utc)
        await db.flush()
        await _avisar_recepcao(db, oferta, avisar)
        return ("Tudo bem. A recepção vai entrar em contato para encontrar outro horário.", True)

    if not opcao.isdigit() or not (1 <= int(opcao) <= len(oferta.slot_ids)):
        opcoes = await _descrever_slots(db, oferta.slot_ids)
        return (f"Não entendi.\n{_linhas_de_opcoes(opcoes)}\n\n{_instrucao(len(opcoes))}", False)

    slot_id = oferta.slot_ids[int(opcao) - 1]
    slot = (await db.execute(select(Slot).where(Slot.id == slot_id))).scalar_one_or_none()
    if slot is None or slot.status != SlotStatus.DISPONIVEL:
        restantes = [
            s.id for s, _ in await _descrever_slots(db, oferta.slot_ids)
            if s.id != slot_id and s.status == SlotStatus.DISPONIVEL
        ]
        oferta.slot_ids = restantes
        if not restantes:
            oferta.status = ReagendamentoStatus.SEM_HORARIO
            oferta.respondido_em = datetime.now(timezone.utc)
            await db.flush()
            await _avisar_recepcao(db, oferta, avisar)
            return ("Esses horários acabaram de ser ocupados. A recepção vai entrar em contato para remarcar.", True)
        await db.flush()
        opcoes = await _descrever_slots(db, restantes)
        return (
            "Esse horário acabou de ser ocupado. Ainda temos:\n"
            f"{_linhas_de_opcoes(opcoes)}\n\n{_instrucao(len(opcoes))}",
            False,
        )

    original = (
        await db.execute(select(Atendimento).where(Atendimento.id == oferta.atendimento_id))
    ).scalar_one()
    especialidade_id = (
        await db.execute(select(Profissional.especialidade_id).where(Profissional.id == slot.profissional_id))
    ).scalar_one()
    novo = Atendimento(
        slot_id=slot.id,
        cliente_id=original.cliente_id,
        profissional_id=slot.profissional_id,
        especialidade_id=especialidade_id,
        tipo=original.tipo,
        urgencia=original.urgencia,
        canal_origem=AtendimentoCanal.WHATSAPP,
        triagem_resumo=original.triagem_resumo,
        cliente_convenio_id=original.cliente_convenio_id,
        observacoes=f"Reagendado pelo cliente por WhatsApp (substitui o atendimento {original.id}).",
        estabelecimento_id=original.estabelecimento_id,
    )
    db.add(novo)
    slot.status = SlotStatus.AGENDADO
    await db.flush()
    oferta.status = ReagendamentoStatus.ACEITA
    oferta.novo_atendimento_id = novo.id
    oferta.respondido_em = datetime.now(timezone.utc)
    await db.flush()
    log.info("reagendamento_aceito", oferta_id=oferta.id, atendimento_id=novo.id)
    return (
        f"Remarcação confirmada para {slot.data.strftime('%d/%m/%Y')} às "
        f"{slot.hora_inicio.strftime('%H:%M')}. Protocolo PROTO-{novo.id:06d}. Obrigado pela compreensão!",
        True,
    )


async def expirar_ofertas(
    db: AsyncSession, agora_utc: datetime | None = None, avisar=notificar_recepcao
) -> int:
    """Ofertas sem resposta há mais de 30 minutos viram pendência da recepção."""
    limite = (agora_utc or datetime.now(timezone.utc)) - timedelta(minutes=PRAZO_RESPOSTA_MIN)
    vencidas = (
        await db.execute(
            select(ReagendamentoOferta).where(
                ReagendamentoOferta.status == ReagendamentoStatus.PENDENTE,
                ReagendamentoOferta.enviado_em < limite,
            )
        )
    ).scalars().all()
    for oferta in vencidas:
        oferta.status = ReagendamentoStatus.EXPIRADA
    await db.flush()
    for oferta in vencidas:
        await _avisar_recepcao(db, oferta, avisar)
    return len(vencidas)


async def listar_pendencias(db: AsyncSession, estabelecimento_id: int) -> list[dict]:
    """Cancelamentos da unidade em que o cliente ainda não foi remarcado e precisa de contato."""
    linhas = (
        await db.execute(
            select(ReagendamentoOferta, Cliente, Slot, Profissional.nome, Especialidade.nome)
            .join(Cliente, ReagendamentoOferta.cliente_id == Cliente.id)
            .join(Atendimento, ReagendamentoOferta.atendimento_id == Atendimento.id)
            .join(Slot, Atendimento.slot_id == Slot.id)
            .join(Profissional, Atendimento.profissional_id == Profissional.id)
            .join(Especialidade, Atendimento.especialidade_id == Especialidade.id)
            .where(
                ReagendamentoOferta.estabelecimento_id == estabelecimento_id,
                ReagendamentoOferta.status.in_(STATUS_QUE_PEDEM_CONTATO),
            )
            .order_by(ReagendamentoOferta.created_at)
        )
    ).all()
    return [
        {
            "id": oferta.id,
            "status": oferta.status.value,
            "motivo": _MOTIVO_PENDENCIA.get(oferta.status, ""),
            "cliente_id": cliente.id,
            "cliente_nome": cliente.nome,
            "cliente_telefone": cliente.telefone,
            "atendimento_id": oferta.atendimento_id,
            "data_original": str(slot.data),
            "hora_original": slot.hora_inicio.strftime("%H:%M"),
            "profissional_nome": profissional,
            "especialidade_nome": especialidade,
            "created_at": oferta.created_at.isoformat() if oferta.created_at else None,
        }
        for oferta, cliente, slot, profissional, especialidade in linhas
    ]


async def resolver_pendencia(db: AsyncSession, oferta_id: int, estabelecimento_id: int) -> bool:
    """A recepção marca que já falou com o cliente."""
    oferta = (
        await db.execute(
            select(ReagendamentoOferta).where(
                ReagendamentoOferta.id == oferta_id,
                ReagendamentoOferta.estabelecimento_id == estabelecimento_id,
                ReagendamentoOferta.status.in_(STATUS_QUE_PEDEM_CONTATO),
            )
        )
    ).scalar_one_or_none()
    if oferta is None:
        return False
    oferta.status = ReagendamentoStatus.RESOLVIDA
    await db.flush()
    return True
