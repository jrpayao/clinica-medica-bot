import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.paciente import Paciente
from app.schemas.paciente import PacienteCreate, PacienteUpdate

log = structlog.get_logger(__name__)


class PacienteService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def listar(
        self,
        estabelecimento_id: int,
        apenas_ativos: bool = True,
    ) -> list[Paciente]:
        """Lista pacientes do estabelecimento."""
        query = (
            select(Paciente)
            .where(Paciente.estabelecimento_id == estabelecimento_id)
            .order_by(Paciente.nome)
        )
        if apenas_ativos:
            query = query.where(Paciente.ativo == True)  # noqa: E712
        result = await self.db.execute(query)
        return list(result.scalars().all())

    async def buscar_por_id(
        self,
        paciente_id: int,
        estabelecimento_id: int | None = None,
    ) -> Paciente | None:
        """Busca paciente por ID, opcionalmente filtrando pelo estabelecimento."""
        query = select(Paciente).where(Paciente.id == paciente_id)
        if estabelecimento_id is not None:
            query = query.where(Paciente.estabelecimento_id == estabelecimento_id)
        result = await self.db.execute(query)
        return result.scalar_one_or_none()

    async def buscar_por_cpf(
        self,
        cpf: str,
        estabelecimento_id: int | None = None,
    ) -> Paciente | None:
        """Busca paciente por CPF no estabelecimento."""
        query = select(Paciente).where(Paciente.cpf == cpf)
        if estabelecimento_id is not None:
            query = query.where(Paciente.estabelecimento_id == estabelecimento_id)
        result = await self.db.execute(query)
        return result.scalar_one_or_none()

    async def criar(
        self,
        dados: PacienteCreate,
        estabelecimento_id: int,
    ) -> Paciente:
        """Cria novo paciente no estabelecimento."""
        data = dados.model_dump()
        data["estabelecimento_id"] = estabelecimento_id
        paciente = Paciente(**data)
        self.db.add(paciente)
        await self.db.flush()
        await self.db.refresh(paciente)
        log.info(
            "paciente_criado",
            cpf_prefixo=dados.cpf[:3] + "***",
            id=paciente.id,
            estabelecimento_id=estabelecimento_id,
        )
        return paciente

    async def atualizar(
        self,
        paciente_id: int,
        dados: PacienteUpdate,
        estabelecimento_id: int | None = None,
    ) -> Paciente | None:
        """Atualiza paciente existente."""
        paciente = await self.buscar_por_id(paciente_id, estabelecimento_id)
        if not paciente:
            return None

        update_data = dados.model_dump(exclude_unset=True)
        for campo, valor in update_data.items():
            setattr(paciente, campo, valor)

        await self.db.flush()
        await self.db.refresh(paciente)
        log.info("paciente_atualizado", id=paciente_id)
        return paciente

    async def desativar(
        self,
        paciente_id: int,
        estabelecimento_id: int | None = None,
    ) -> Paciente | None:
        """Desativa paciente (soft delete)."""
        paciente = await self.buscar_por_id(paciente_id, estabelecimento_id)
        if not paciente:
            return None

        paciente.ativo = False
        await self.db.flush()
        await self.db.refresh(paciente)
        log.info("paciente_desativado", id=paciente_id)
        return paciente
