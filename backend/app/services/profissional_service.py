from datetime import date, datetime, time, timedelta

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.profissional import Profissional
from app.models.profissional_estabelecimento import ProfissionalEstabelecimento
from app.models.slot import Slot, SlotStatus
from app.schemas.profissional import ProfissionalCreate, ProfissionalUpdate

log = structlog.get_logger(__name__)


class ProfissionalService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def listar(
        self,
        estabelecimento_id: int,
        apenas_ativos: bool = True,
    ) -> list[Profissional]:
        """Lista profissionais que atendem no estabelecimento (via junction N:N)."""
        query = (
            select(Profissional)
            .join(
                ProfissionalEstabelecimento,
                ProfissionalEstabelecimento.profissional_id == Profissional.id,
            )
            .where(ProfissionalEstabelecimento.estabelecimento_id == estabelecimento_id)
            .order_by(Profissional.nome)
        )
        if apenas_ativos:
            query = query.where(
                Profissional.ativo == True,  # noqa: E712
                ProfissionalEstabelecimento.ativo == True,  # noqa: E712
            )
        result = await self.db.execute(query)
        return list(result.scalars().all())

    async def buscar_por_id(self, profissional_id: int) -> Profissional | None:
        """Busca profissional por ID global (sem filtro de tenant)."""
        result = await self.db.execute(
            select(Profissional).where(Profissional.id == profissional_id)
        )
        return result.scalar_one_or_none()

    async def criar(
        self,
        dados: ProfissionalCreate,
        estabelecimento_id: int,
    ) -> Profissional:
        """Cria profissional e vincula ao estabelecimento via junction."""
        profissional = Profissional(**dados.model_dump())
        self.db.add(profissional)
        await self.db.flush()

        vinculo = ProfissionalEstabelecimento(
            profissional_id=profissional.id,
            estabelecimento_id=estabelecimento_id,
            duracao_atendimento_min=profissional.duracao_atendimento_min,
            ativo=True,
        )
        self.db.add(vinculo)
        await self.db.flush()
        await self.db.refresh(profissional)
        log.info(
            "profissional_criado",
            nome=profissional.nome,
            registro_profissional=profissional.registro_profissional,
            id=profissional.id,
            estabelecimento_id=estabelecimento_id,
        )
        return profissional

    async def atualizar(self, profissional_id: int, dados: ProfissionalUpdate) -> Profissional | None:
        """Atualiza dados globais do profissional."""
        profissional = await self.buscar_por_id(profissional_id)
        if not profissional:
            return None

        update_data = dados.model_dump(exclude_unset=True)
        for campo, valor in update_data.items():
            setattr(profissional, campo, valor)

        await self.db.flush()
        await self.db.refresh(profissional)
        log.info("profissional_atualizado", id=profissional_id)
        return profissional

    async def desativar(self, profissional_id: int) -> Profissional | None:
        """Desativa profissional globalmente (soft delete)."""
        profissional = await self.buscar_por_id(profissional_id)
        if not profissional:
            return None

        profissional.ativo = False
        await self.db.flush()
        await self.db.refresh(profissional)
        log.info("profissional_desativado", id=profissional_id)
        return profissional

    async def gerar_slots(
        self,
        profissional_id: int,
        data_inicio: date,
        data_fim: date,
        hora_inicio: time = time(8, 0),
        hora_fim: time = time(18, 0),
        intervalo_almoco_inicio: time | None = time(12, 0),
        intervalo_almoco_fim: time | None = time(13, 0),
        dias_semana: list[int] | None = None,
        estabelecimento_id: int | None = None,
    ) -> list[Slot]:
        """Gera slots de agenda para o profissional no período especificado."""
        if dias_semana is None:
            dias_semana = [0, 1, 2, 3, 4]  # seg-sex

        profissional = await self.buscar_por_id(profissional_id)
        if not profissional:
            raise ValueError("Profissional nao encontrado")

        duracao = timedelta(minutes=profissional.duracao_atendimento_min)
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
                        profissional_id=profissional_id,
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
            profissional_id=profissional_id,
            quantidade=len(slots_criados),
            periodo=f"{data_inicio} a {data_fim}",
            estabelecimento_id=estabelecimento_id,
        )
        return slots_criados
