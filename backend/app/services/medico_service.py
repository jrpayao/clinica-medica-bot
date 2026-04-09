from datetime import date, datetime, time, timedelta

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.medico import Medico
from app.models.medico_estabelecimento import MedicoEstabelecimento
from app.models.slot import Slot, SlotStatus
from app.schemas.medico import MedicoCreate, MedicoUpdate

log = structlog.get_logger(__name__)


class MedicoService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def listar(
        self,
        estabelecimento_id: int,
        apenas_ativos: bool = True,
    ) -> list[Medico]:
        """Lista médicos que atendem no estabelecimento (via junction N:N)."""
        query = (
            select(Medico)
            .join(
                MedicoEstabelecimento,
                MedicoEstabelecimento.medico_id == Medico.id,
            )
            .where(MedicoEstabelecimento.estabelecimento_id == estabelecimento_id)
            .order_by(Medico.nome)
        )
        if apenas_ativos:
            query = query.where(
                Medico.ativo == True,  # noqa: E712
                MedicoEstabelecimento.ativo == True,  # noqa: E712
            )
        result = await self.db.execute(query)
        return list(result.scalars().all())

    async def buscar_por_id(self, medico_id: int) -> Medico | None:
        """Busca medico por ID global (sem filtro de tenant)."""
        result = await self.db.execute(
            select(Medico).where(Medico.id == medico_id)
        )
        return result.scalar_one_or_none()

    async def criar(
        self,
        dados: MedicoCreate,
        estabelecimento_id: int,
    ) -> Medico:
        """Cria médico e vincula ao estabelecimento via junction."""
        medico = Medico(**dados.model_dump())
        self.db.add(medico)
        await self.db.flush()

        vinculo = MedicoEstabelecimento(
            medico_id=medico.id,
            estabelecimento_id=estabelecimento_id,
            duracao_consulta_min=medico.duracao_consulta_min,
            ativo=True,
        )
        self.db.add(vinculo)
        await self.db.flush()
        await self.db.refresh(medico)
        log.info(
            "medico_criado",
            nome=medico.nome,
            crm=medico.crm,
            id=medico.id,
            estabelecimento_id=estabelecimento_id,
        )
        return medico

    async def atualizar(self, medico_id: int, dados: MedicoUpdate) -> Medico | None:
        """Atualiza dados globais do médico."""
        medico = await self.buscar_por_id(medico_id)
        if not medico:
            return None

        update_data = dados.model_dump(exclude_unset=True)
        for campo, valor in update_data.items():
            setattr(medico, campo, valor)

        await self.db.flush()
        await self.db.refresh(medico)
        log.info("medico_atualizado", id=medico_id)
        return medico

    async def desativar(self, medico_id: int) -> Medico | None:
        """Desativa médico globalmente (soft delete)."""
        medico = await self.buscar_por_id(medico_id)
        if not medico:
            return None

        medico.ativo = False
        await self.db.flush()
        await self.db.refresh(medico)
        log.info("medico_desativado", id=medico_id)
        return medico

    async def gerar_slots(
        self,
        medico_id: int,
        data_inicio: date,
        data_fim: date,
        hora_inicio: time = time(8, 0),
        hora_fim: time = time(18, 0),
        intervalo_almoco_inicio: time | None = time(12, 0),
        intervalo_almoco_fim: time | None = time(13, 0),
        dias_semana: list[int] | None = None,
        estabelecimento_id: int | None = None,
    ) -> list[Slot]:
        """Gera slots de agenda para o médico no período especificado."""
        if dias_semana is None:
            dias_semana = [0, 1, 2, 3, 4]  # seg-sex

        medico = await self.buscar_por_id(medico_id)
        if not medico:
            raise ValueError("Medico nao encontrado")

        duracao = timedelta(minutes=medico.duracao_consulta_min)
        slots_criados: list[Slot] = []
        dia_atual = data_inicio

        while dia_atual <= data_fim:
            if dia_atual.weekday() in dias_semana:
                slot_hora = datetime.combine(dia_atual, hora_inicio)
                fim_dia = datetime.combine(dia_atual, hora_fim)

                while slot_hora + duracao <= fim_dia:
                    slot_hora_fim = slot_hora + duracao
                    slot_time = slot_hora.time()
                    slot_time_fim = slot_hora_fim.time()

                    # Pular intervalo de almoço
                    if (
                        intervalo_almoco_inicio
                        and intervalo_almoco_fim
                        and slot_time >= intervalo_almoco_inicio
                        and slot_time < intervalo_almoco_fim
                    ):
                        slot_hora = datetime.combine(dia_atual, intervalo_almoco_fim)
                        continue

                    slot = Slot(
                        medico_id=medico_id,
                        data=dia_atual,
                        hora_inicio=slot_time,
                        hora_fim=slot_time_fim,
                        status=SlotStatus.DISPONIVEL,
                        estabelecimento_id=estabelecimento_id,
                    )
                    self.db.add(slot)
                    slots_criados.append(slot)

                    slot_hora = slot_hora_fim

            dia_atual += timedelta(days=1)

        await self.db.flush()
        log.info(
            "slots_gerados",
            medico_id=medico_id,
            quantidade=len(slots_criados),
            periodo=f"{data_inicio} a {data_fim}",
            estabelecimento_id=estabelecimento_id,
        )
        return slots_criados
