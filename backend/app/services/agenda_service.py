from datetime import date, timedelta

import structlog
from sqlalchemy import outerjoin, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.consulta import Consulta, ConsultaStatus
from app.models.especialidade import Especialidade
from app.models.medico import Medico
from app.models.paciente import Paciente
from app.models.slot import Slot, SlotStatus
from app.schemas.consulta import ConsultaCreate

log = structlog.get_logger(__name__)


class AgendaService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def buscar_disponibilidade(
        self,
        estabelecimento_id: int,
        especialidade_id: int | None = None,
        medico_id: int | None = None,
        data_inicio: date | None = None,
        data_fim: date | None = None,
        convenio_id: int | None = None,
    ) -> list[Slot]:
        """Busca slots disponíveis do estabelecimento com filtros opcionais."""
        from app.models.medico import Medico

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

        if medico_id:
            query = query.where(Slot.medico_id == medico_id)

        if especialidade_id:
            query = query.join(Medico, Slot.medico_id == Medico.id).where(
                Medico.especialidade_id == especialidade_id,
                Medico.ativo == True,  # noqa: E712
            )

        if convenio_id is not None:
            # Convênios são por estabelecimento — todos os médicos do estabelecimento
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
        dados: ConsultaCreate,
        estabelecimento_id: int,
    ) -> Consulta:
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
        consulta = Consulta(**data)
        self.db.add(consulta)
        await self.db.flush()
        await self.db.refresh(consulta)

        log.info(
            "consulta_agendada",
            consulta_id=consulta.id,
            slot_id=dados.slot_id,
            paciente_id=dados.paciente_id,
            estabelecimento_id=estabelecimento_id,
        )
        return consulta

    async def cancelar_consulta(
        self,
        consulta_id: int,
        motivo: str,
        estabelecimento_id: int | None = None,
    ) -> Consulta:
        """Cancela consulta e libera o slot."""
        query = select(Consulta).where(Consulta.id == consulta_id)
        if estabelecimento_id is not None:
            query = query.where(Consulta.estabelecimento_id == estabelecimento_id)

        result = await self.db.execute(query)
        consulta = result.scalar_one_or_none()

        if not consulta:
            raise ConsultaNaoEncontradaError("Consulta nao encontrada")

        if consulta.status == ConsultaStatus.CANCELADA:
            raise ConsultaJaCanceladaError("Consulta ja esta cancelada")

        if consulta.status == ConsultaStatus.REALIZADA:
            raise ConsultaJaRealizadaError("Nao e possivel cancelar consulta ja realizada")

        consulta.status = ConsultaStatus.CANCELADA
        consulta.observacoes = f"Cancelada: {motivo}"

        slot_result = await self.db.execute(
            select(Slot).where(Slot.id == consulta.slot_id)
        )
        slot = slot_result.scalar_one_or_none()
        if slot:
            slot.status = SlotStatus.DISPONIVEL

        await self.db.flush()
        await self.db.refresh(consulta)

        log.info("consulta_cancelada", consulta_id=consulta_id, motivo=motivo)
        return consulta

    async def buscar_consulta_por_id(
        self,
        consulta_id: int,
        estabelecimento_id: int | None = None,
    ) -> Consulta | None:
        """Busca consulta por ID."""
        query = select(Consulta).where(Consulta.id == consulta_id)
        if estabelecimento_id is not None:
            query = query.where(Consulta.estabelecimento_id == estabelecimento_id)
        result = await self.db.execute(query)
        return result.scalar_one_or_none()

    async def listar_consultas_paciente(
        self,
        paciente_id: int,
        estabelecimento_id: int | None = None,
    ) -> list[Consulta]:
        """Lista consultas de um paciente."""
        query = select(Consulta).where(Consulta.paciente_id == paciente_id)
        if estabelecimento_id is not None:
            query = query.where(Consulta.estabelecimento_id == estabelecimento_id)
        result = await self.db.execute(
            query.order_by(Consulta.created_at.desc())
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
    medico_id: int | None = None,
) -> list[dict]:
    """Lista todos os slots de um dia com consulta embutida (LEFT JOIN).

    Retorna slots DISPONÍVEIS, AGENDADOS, BLOQUEADOS, ENCAIXES e RESERVADOS.
    Consulta é None para slots livres.
    CPF do paciente é sempre mascarado.
    """
    q = (
        select(
            Slot.id,
            Slot.medico_id,
            Medico.nome,
            Especialidade.nome,
            Slot.data,
            Slot.hora_inicio,
            Slot.hora_fim,
            Slot.status,
            # Consulta (nullable — LEFT JOIN)
            Consulta.id,
            Paciente.nome,
            Paciente.cpf,
            Consulta.urgencia,
            Consulta.status,
            Consulta.canal_origem,
            Consulta.triagem_resumo,
            Consulta.observacoes,
            Consulta.created_at,
        )
        .select_from(
            outerjoin(Slot, Medico,        Slot.medico_id       == Medico.id)
            .outerjoin(Especialidade,      Medico.especialidade_id == Especialidade.id)
            .outerjoin(Consulta,           Consulta.slot_id     == Slot.id)
            .outerjoin(Paciente,           Consulta.paciente_id == Paciente.id)
        )
        .where(
            Slot.data == data,
            Slot.estabelecimento_id == estabelecimento_id,
        )
        .order_by(Slot.hora_inicio, Medico.nome)
    )
    if medico_id is not None:
        q = q.where(Slot.medico_id == medico_id)

    result = await db.execute(q)
    rows = result.all()

    slots: list[dict] = []
    for row in rows:
        (
            slot_id, med_id, med_nome, esp_nome,
            slot_data, hora_ini, hora_fim, slot_status,
            consulta_id, pac_nome, cpf,
            urgencia, cons_status, canal, triagem, obs, created_at,
        ) = row

        consulta = None
        if consulta_id is not None:
            consulta = {
                "id":                    consulta_id,
                "paciente_nome":         pac_nome or "",
                "paciente_cpf_mascarado": _mascarar_cpf(cpf),
                "urgencia":              urgencia.value if hasattr(urgencia, "value") else urgencia,
                "status":                cons_status.value if hasattr(cons_status, "value") else cons_status,
                "canal_origem":          canal.value if hasattr(canal, "value") else canal,
                "triagem_resumo":        triagem,
                "observacoes":           obs,
                "created_at":            created_at.isoformat() if created_at else None,
            }

        slots.append({
            "id":                slot_id,
            "medico_id":         med_id,
            "medico_nome":       med_nome or "",
            "especialidade_nome": esp_nome or "",
            "data":              str(slot_data),
            "hora_inicio":       hora_ini.strftime("%H:%M") if hora_ini else "",
            "hora_fim":          hora_fim.strftime("%H:%M") if hora_fim else "",
            "status":            slot_status.value if hasattr(slot_status, "value") else slot_status,
            "consulta":          consulta,
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
