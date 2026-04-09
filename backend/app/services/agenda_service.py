from datetime import date, timedelta

import structlog
from sqlalchemy import outerjoin, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.atendimento import Atendimento, AtendimentoStatus
from app.models.especialidade import Especialidade
from app.models.profissional import Profissional
from app.models.cliente import Cliente
from app.models.slot import Slot, SlotStatus
from app.schemas.atendimento import AtendimentoCreate

log = structlog.get_logger(__name__)


class AgendaService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def buscar_disponibilidade(
        self,
        estabelecimento_id: int,
        especialidade_id: int | None = None,
        profissional_id: int | None = None,
        data_inicio: date | None = None,
        data_fim: date | None = None,
        convenio_id: int | None = None,
    ) -> list[Slot]:
        """Busca slots disponíveis do estabelecimento com filtros opcionais."""
        from app.models.profissional import Profissional

        if data_inicio is None:
            data_inicio = date.today()
        if data_fim is None:
            data_fim = data_inicio + timedelta(days=30)

        query = select(Slot).where(
            Slot.estabelecimento_id == estabelecimento_id,
            Slot.status == SlotStatus.DISPONIVEL,
            Slot.data >= data_inicio,
            Slot.data <= data_fim,
        )

        if profissional_id:
            query = query.where(Slot.profissional_id == profissional_id)

        if especialidade_id:
            query = query.join(Profissional, Slot.profissional_id == Profissional.id).where(
                Profissional.especialidade_id == especialidade_id,
                Profissional.ativo == True,  # noqa: E712
            )

        if convenio_id is not None:
            # Convênios são por estabelecimento — todos os profissionais do estabelecimento
            # atendem os convênios cadastrados para ele. Validar que o convenio_id
            # pertence ao estabelecimento via subquery.
            from app.models.convenio import Convenio as ConvenioModel
            from sqlalchemy import exists

            query = query.where(
                exists().where(
                    ConvenioModel.id == convenio_id,
                    ConvenioModel.estabelecimento_id == estabelecimento_id,
                    ConvenioModel.ativo == True,  # noqa: E712
                )
            )

        query = query.order_by(Slot.data, Slot.hora_inicio)
        result = await self.db.execute(query)
        return list(result.scalars().all())

    async def agendar_consulta(
        self,
        dados: AtendimentoCreate,
        estabelecimento_id: int,
    ) -> Atendimento:
        """Cria agendamento reservando o slot."""
        result = await self.db.execute(
            select(Slot).where(
                Slot.id == dados.slot_id,
                Slot.estabelecimento_id == estabelecimento_id,
            )
        )
        slot = result.scalar_one_or_none()

        if not slot:
            raise SlotNaoEncontradoError("Slot nao encontrado")

        if slot.status != SlotStatus.DISPONIVEL:
            raise SlotIndisponivelError("Slot nao esta disponivel para agendamento")

        slot.status = SlotStatus.AGENDADO

        data = dados.model_dump()
        data["estabelecimento_id"] = estabelecimento_id
        atendimento = Atendimento(**data)
        self.db.add(atendimento)
        await self.db.flush()
        await self.db.refresh(atendimento)

        log.info(
            "atendimento_agendado",
            atendimento_id=atendimento.id,
            slot_id=dados.slot_id,
            cliente_id=dados.cliente_id,
            estabelecimento_id=estabelecimento_id,
        )
        return atendimento

    async def cancelar_consulta(
        self,
        atendimento_id: int,
        motivo: str,
        estabelecimento_id: int | None = None,
    ) -> Atendimento:
        """Cancela atendimento e libera o slot."""
        query = select(Atendimento).where(Atendimento.id == atendimento_id)
        if estabelecimento_id is not None:
            query = query.where(Atendimento.estabelecimento_id == estabelecimento_id)

        result = await self.db.execute(query)
        atendimento = result.scalar_one_or_none()

        if not atendimento:
            raise ConsultaNaoEncontradaError("Atendimento nao encontrado")

        if atendimento.status == AtendimentoStatus.CANCELADA:
            raise ConsultaJaCanceladaError("Atendimento ja esta cancelado")

        if atendimento.status == AtendimentoStatus.REALIZADA:
            raise ConsultaJaRealizadaError("Nao e possivel cancelar atendimento ja realizado")

        atendimento.status = AtendimentoStatus.CANCELADA
        atendimento.observacoes = f"Cancelada: {motivo}"

        slot_result = await self.db.execute(
            select(Slot).where(Slot.id == atendimento.slot_id)
        )
        slot = slot_result.scalar_one_or_none()
        if slot:
            slot.status = SlotStatus.DISPONIVEL

        await self.db.flush()
        await self.db.refresh(atendimento)

        log.info("atendimento_cancelado", atendimento_id=atendimento_id, motivo=motivo)
        return atendimento

    async def buscar_consulta_por_id(
        self,
        atendimento_id: int,
        estabelecimento_id: int | None = None,
    ) -> Atendimento | None:
        """Busca atendimento por ID."""
        query = select(Atendimento).where(Atendimento.id == atendimento_id)
        if estabelecimento_id is not None:
            query = query.where(Atendimento.estabelecimento_id == estabelecimento_id)
        result = await self.db.execute(query)
        return result.scalar_one_or_none()

    async def listar_consultas_paciente(
        self,
        cliente_id: int,
        estabelecimento_id: int | None = None,
    ) -> list[Atendimento]:
        """Lista atendimentos de um cliente."""
        query = select(Atendimento).where(Atendimento.cliente_id == cliente_id)
        if estabelecimento_id is not None:
            query = query.where(Atendimento.estabelecimento_id == estabelecimento_id)
        result = await self.db.execute(
            query.order_by(Atendimento.created_at.desc())
        )
        return list(result.scalars().all())


def _mascarar_cpf(cpf: str | None) -> str:
    """Retorna CPF mascarado: 123.***.***-01"""
    if not cpf or len(cpf) < 11:
        return "***"
    return f"{cpf[:3]}.***.***-{cpf[-2:]}"


async def listar_slots_dia(
    db: AsyncSession,
    data: date,
    estabelecimento_id: int,
    profissional_id: int | None = None,
) -> list[dict]:
    """Lista todos os slots de um dia com atendimento embutido (LEFT JOIN).

    Retorna slots DISPONÍVEIS, AGENDADOS, BLOQUEADOS, ENCAIXES e RESERVADOS.
    Atendimento é None para slots livres.
    CPF do cliente é sempre mascarado.
    """
    q = (
        select(
            Slot.id,
            Slot.profissional_id,
            Profissional.nome,
            Especialidade.nome,
            Slot.data,
            Slot.hora_inicio,
            Slot.hora_fim,
            Slot.status,
            # Atendimento (nullable — LEFT JOIN)
            Atendimento.id,
            Cliente.nome,
            Cliente.cpf,
            Atendimento.urgencia,
            Atendimento.status,
            Atendimento.canal_origem,
            Atendimento.triagem_resumo,
            Atendimento.observacoes,
            Atendimento.created_at,
        )
        .select_from(
            outerjoin(Slot, Profissional,   Slot.profissional_id       == Profissional.id)
            .outerjoin(Especialidade,       Profissional.especialidade_id == Especialidade.id)
            .outerjoin(Atendimento,         Atendimento.slot_id        == Slot.id)
            .outerjoin(Cliente,             Atendimento.cliente_id     == Cliente.id)
        )
        .where(
            Slot.data == data,
            Slot.estabelecimento_id == estabelecimento_id,
        )
        .order_by(Slot.hora_inicio, Profissional.nome)
    )
    if profissional_id is not None:
        q = q.where(Slot.profissional_id == profissional_id)

    result = await db.execute(q)
    rows = result.all()

    slots: list[dict] = []
    for row in rows:
        (
            slot_id, prof_id, prof_nome, esp_nome,
            slot_data, hora_ini, hora_fim, slot_status,
            atendimento_id, cli_nome, cpf,
            urgencia, atend_status, canal, triagem, obs, created_at,
        ) = row

        atendimento = None
        if atendimento_id is not None:
            atendimento = {
                "id":                    atendimento_id,
                "cliente_nome":          cli_nome or "",
                "cliente_cpf_mascarado": _mascarar_cpf(cpf),
                "urgencia":              urgencia.value if hasattr(urgencia, "value") else urgencia,
                "status":                atend_status.value if hasattr(atend_status, "value") else atend_status,
                "canal_origem":          canal.value if hasattr(canal, "value") else canal,
                "triagem_resumo":        triagem,
                "observacoes":           obs,
                "created_at":            created_at.isoformat() if created_at else None,
            }

        slots.append({
            "id":                  slot_id,
            "profissional_id":     prof_id,
            "profissional_nome":   prof_nome or "",
            "especialidade_nome":  esp_nome or "",
            "data":                str(slot_data),
            "hora_inicio":         hora_ini.strftime("%H:%M") if hora_ini else "",
            "hora_fim":            hora_fim.strftime("%H:%M") if hora_fim else "",
            "status":              slot_status.value if hasattr(slot_status, "value") else slot_status,
            "atendimento":         atendimento,
        })

    return slots


# Exceções de domínio
class SlotNaoEncontradoError(Exception):
    pass


class SlotIndisponivelError(Exception):
    pass


class ConsultaNaoEncontradaError(Exception):
    pass


class ConsultaJaCanceladaError(Exception):
    pass


class ConsultaJaRealizadaError(Exception):
    pass
