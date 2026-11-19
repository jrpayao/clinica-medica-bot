"""Fila de espera (T89–T91).

Quem não encontrou horário entra na fila. Quando um horário compatível abre, o primeiro da fila
recebe a oferta por WhatsApp e o horário fica guardado por PRAZO_RESPOSTA_MIN minutos. Sem resposta,
o horário volta para a agenda e a oferta passa ao próximo.
"""

from datetime import datetime, timedelta, timezone

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.atendimento import Atendimento, AtendimentoCanal, AtendimentoTipo
from app.models.cliente import Cliente
from app.models.convenio import Convenio
from app.models.especialidade import Especialidade
from app.models.estabelecimento import EstabelecimentoSaude
from app.models.fila_espera import FilaEspera, FilaEsperaStatus
from app.models.profissional import Profissional
from app.models.slot import Slot, SlotStatus
from app.services.agenda_service import AgendaService
from app.services.mensageria import enviar_whatsapp, mascarar_telefone, registrar_pendencia

log = structlog.get_logger(__name__)

PRAZO_RESPOSTA_MIN = 30
MAX_TENTATIVAS = 2  # ofertas sem resposta antes de tirar a pessoa da fila

_ATIVOS = (FilaEsperaStatus.AGUARDANDO, FilaEsperaStatus.NOTIFICADO)

OPCOES = (
    "Responda *1* para confirmar, *2* para continuar aguardando outro horário "
    "ou *0* para sair da lista de espera."
)


def mascarar_cpf(cpf: str | None) -> str:
    if not cpf or len(cpf) < 11:
        return "***"
    return f"{cpf[:3]}.***.***-{cpf[-2:]}"


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

    async def entrar_sem_duplicar(
        self,
        cliente_id: int,
        estabelecimento_id: int,
        especialidade_id: int | None,
        convenio_id: int | None,
    ) -> FilaEspera:
        """Entra na fila; se a pessoa já aguarda a mesma especialidade na unidade, devolve a entrada dela."""
        consulta = select(FilaEspera).where(
            FilaEspera.cliente_id == cliente_id,
            FilaEspera.estabelecimento_id == estabelecimento_id,
            FilaEspera.status.in_(_ATIVOS),
        )
        consulta = consulta.where(
            FilaEspera.especialidade_id.is_(None)
            if especialidade_id is None
            else FilaEspera.especialidade_id == especialidade_id
        )
        existente = (await self.db.execute(consulta.limit(1))).scalar_one_or_none()
        if existente is not None:
            return existente
        return await self.entrar(cliente_id, estabelecimento_id, especialidade_id, convenio_id)

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


async def listar_fila(db: AsyncSession, estabelecimento_id: int) -> list[dict]:
    """Quem está na fila da unidade (aguardando ou com oferta em aberto), em ordem de chegada."""
    linhas = (
        await db.execute(
            select(FilaEspera, Cliente, Especialidade.nome, Convenio.nome)
            .join(Cliente, FilaEspera.cliente_id == Cliente.id)
            .outerjoin(Especialidade, FilaEspera.especialidade_id == Especialidade.id)
            .outerjoin(Convenio, FilaEspera.convenio_id == Convenio.id)
            .where(
                FilaEspera.estabelecimento_id == estabelecimento_id,
                FilaEspera.status.in_(_ATIVOS),
            )
            .order_by(FilaEspera.created_at, FilaEspera.id)
        )
    ).all()
    return [
        {
            "id": entrada.id,
            "posicao": posicao,
            "cliente_id": cliente.id,
            "cliente_nome": cliente.nome,
            "cliente_cpf_mascarado": mascarar_cpf(cliente.cpf),
            "cliente_telefone": cliente.telefone,
            "especialidade_id": entrada.especialidade_id,
            "especialidade_nome": especialidade,
            "convenio_nome": convenio,
            "status": entrada.status.value,
            "tentativas": entrada.tentativas,
            "notificado_em": entrada.notificado_em.isoformat() if entrada.notificado_em else None,
            "created_at": entrada.created_at.isoformat() if entrada.created_at else None,
        }
        for posicao, (entrada, cliente, especialidade, convenio) in enumerate(linhas, start=1)
    ]


async def remover_da_fila(db: AsyncSession, fila_id: int, estabelecimento_id: int) -> bool:
    """Tira a pessoa da fila da unidade. Se havia horário guardado para ela, ele volta para a agenda."""
    entrada = (
        await db.execute(
            select(FilaEspera).where(
                FilaEspera.id == fila_id,
                FilaEspera.estabelecimento_id == estabelecimento_id,
                FilaEspera.status.in_(_ATIVOS),
            )
        )
    ).scalar_one_or_none()
    if entrada is None:
        return False
    if entrada.status == FilaEsperaStatus.NOTIFICADO:
        await _liberar_slot(db, entrada.slot_ofertado_id)
    entrada.status = FilaEsperaStatus.CANCELADO
    await db.flush()
    log.info("fila_espera_removida", fila_id=fila_id, estabelecimento_id=estabelecimento_id)
    return True


async def _liberar_slot(db: AsyncSession, slot_id: int | None) -> None:
    if slot_id is None:
        return
    slot = (await db.execute(select(Slot).where(Slot.id == slot_id))).scalar_one_or_none()
    if slot is not None and slot.status == SlotStatus.RESERVADO:
        slot.status = SlotStatus.DISPONIVEL
        slot.reservado_em = None


async def _expirar_ofertas(db: AsyncSession, agora_utc: datetime) -> int:
    limite = agora_utc - timedelta(minutes=PRAZO_RESPOSTA_MIN)
    vencidas = (
        await db.execute(
            select(FilaEspera).where(
                FilaEspera.status == FilaEsperaStatus.NOTIFICADO,
                FilaEspera.notificado_em < limite,
            )
        )
    ).scalars().all()
    for entrada in vencidas:
        await _liberar_slot(db, entrada.slot_ofertado_id)
        entrada.tentativas += 1
        entrada.status = (
            FilaEsperaStatus.CANCELADO
            if entrada.tentativas >= MAX_TENTATIVAS
            else FilaEsperaStatus.AGUARDANDO
        )
    await db.flush()
    return len(vencidas)


def _texto_oferta(cliente: Cliente, slot: Slot, profissional: str, especialidade: str | None, unidade: str) -> str:
    primeiro_nome = (cliente.nome or "").split()[0] if cliente.nome else ""
    assunto = f" de {especialidade}" if especialidade else ""
    return (
        f"Olá, {primeiro_nome}! Abriu um horário{assunto} na {unidade}: "
        f"{slot.data.strftime('%d/%m/%Y')} às {slot.hora_inicio.strftime('%H:%M')} com {profissional}.\n\n"
        f"{OPCOES}\n\nGuardamos este horário para você por {PRAZO_RESPOSTA_MIN} minutos."
    )


async def processar_fila(
    db: AsyncSession,
    redis,
    agora_utc: datetime | None = None,
    enviar=enviar_whatsapp,
) -> dict:
    """Vence as ofertas sem resposta e oferece os horários livres a quem aguarda, em ordem de chegada."""
    agora_utc = agora_utc or datetime.now(timezone.utc)
    expirados = await _expirar_ofertas(db, agora_utc)

    aguardando = (
        await db.execute(
            select(FilaEspera, Cliente)
            .join(Cliente, FilaEspera.cliente_id == Cliente.id)
            .where(FilaEspera.status == FilaEsperaStatus.AGUARDANDO)
            .order_by(FilaEspera.created_at, FilaEspera.id)
        )
    ).all()

    agenda = AgendaService(db)
    disponiveis: dict[tuple, list[Slot]] = {}
    usados: set[int] = set()
    notificados = 0

    for entrada, cliente in aguardando:
        if not cliente.telefone:
            continue
        chave = (entrada.estabelecimento_id, entrada.especialidade_id, entrada.convenio_id)
        if chave not in disponiveis:
            disponiveis[chave] = await agenda.buscar_disponibilidade(
                estabelecimento_id=entrada.estabelecimento_id,
                especialidade_id=entrada.especialidade_id,
                convenio_id=entrada.convenio_id,
            )
        slot = next(
            (
                s for s in disponiveis[chave]
                if s.id not in usados and s.id != entrada.slot_ofertado_id
                and s.status == SlotStatus.DISPONIVEL
            ),
            None,
        )
        if slot is None:
            continue

        profissional, especialidade = (
            await db.execute(
                select(Profissional.nome, Especialidade.nome)
                .join(Especialidade, Profissional.especialidade_id == Especialidade.id)
                .where(Profissional.id == slot.profissional_id)
            )
        ).one()
        unidade = (
            await db.execute(
                select(EstabelecimentoSaude.nome).where(
                    EstabelecimentoSaude.id == entrada.estabelecimento_id
                )
            )
        ).scalar_one()

        if not await enviar(cliente.telefone, _texto_oferta(cliente, slot, profissional, especialidade, unidade)):
            log.warning("fila_espera_envio_falhou", fila_id=entrada.id, telefone=mascarar_telefone(cliente.telefone))
            continue

        usados.add(slot.id)
        slot.status = SlotStatus.RESERVADO
        slot.reservado_em = agora_utc
        entrada.status = FilaEsperaStatus.NOTIFICADO
        entrada.notificado_em = agora_utc
        entrada.slot_ofertado_id = slot.id
        await registrar_pendencia(
            redis, cliente.telefone, {"tipo": "fila", "fila_id": entrada.id}, ttl=PRAZO_RESPOSTA_MIN * 60
        )
        notificados += 1
        log.info("fila_espera_oferta_enviada", fila_id=entrada.id, slot_id=slot.id)

    await db.flush()
    return {"expirados": expirados, "notificados": notificados}


async def responder_oferta_fila(db: AsyncSession, fila_id: int, mensagem: str) -> tuple[str, bool]:
    """Trata a resposta do cliente à oferta. Devolve (texto de resposta, conversa encerrada?)."""
    entrada = (await db.execute(select(FilaEspera).where(FilaEspera.id == fila_id))).scalar_one_or_none()
    if entrada is None or entrada.status != FilaEsperaStatus.NOTIFICADO:
        return (
            "Esse horário não está mais guardado para você. "
            "Se você continua na lista de espera, avisaremos quando abrir outro.",
            True,
        )

    opcao = mensagem.strip().lower().strip(".! ")
    if opcao in ("1", "sim", "confirmar", "confirmo"):
        slot = (await db.execute(select(Slot).where(Slot.id == entrada.slot_ofertado_id))).scalar_one_or_none()
        if slot is None or slot.status != SlotStatus.RESERVADO:
            entrada.status = FilaEsperaStatus.AGUARDANDO
            await db.flush()
            return ("Esse horário não está mais disponível. Você continua na lista de espera.", True)

        especialidade_id = (
            await db.execute(
                select(Profissional.especialidade_id).where(Profissional.id == slot.profissional_id)
            )
        ).scalar_one()
        atendimento = Atendimento(
            slot_id=slot.id,
            cliente_id=entrada.cliente_id,
            profissional_id=slot.profissional_id,
            especialidade_id=especialidade_id,
            tipo=AtendimentoTipo.EXTERNO,
            canal_origem=AtendimentoCanal.WHATSAPP,
            observacoes="Agendado pela lista de espera (confirmado por WhatsApp).",
            estabelecimento_id=entrada.estabelecimento_id,
        )
        db.add(atendimento)
        slot.status = SlotStatus.AGENDADO
        slot.reservado_em = None
        entrada.status = FilaEsperaStatus.AGENDADO
        await db.flush()
        log.info("fila_espera_agendou", fila_id=entrada.id, atendimento_id=atendimento.id)
        return (
            f"Agendamento confirmado para {slot.data.strftime('%d/%m/%Y')} às "
            f"{slot.hora_inicio.strftime('%H:%M')}. Protocolo PROTO-{atendimento.id:06d}. Até lá!",
            True,
        )

    if opcao in ("2", "outro", "outro horario", "outro horário"):
        await _liberar_slot(db, entrada.slot_ofertado_id)
        entrada.status = FilaEsperaStatus.AGUARDANDO
        await db.flush()
        return ("Tudo bem. Você continua na lista de espera e avisaremos quando abrir outro horário.", True)

    if opcao in ("0", "sair", "nao", "não", "cancelar"):
        await _liberar_slot(db, entrada.slot_ofertado_id)
        entrada.status = FilaEsperaStatus.CANCELADO
        await db.flush()
        return ("Você saiu da lista de espera. Quando quiser, é só falar com a gente de novo.", True)

    return (f"Não entendi. {OPCOES}", False)
