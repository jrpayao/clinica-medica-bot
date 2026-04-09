import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.especialidade import Especialidade
from app.schemas.especialidade import EspecialidadeCreate, EspecialidadeUpdate

log = structlog.get_logger(__name__)


class EspecialidadeService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def listar(
        self,
        estabelecimento_id: int,
        apenas_ativas: bool = True,
    ) -> list[Especialidade]:
        """Lista especialidades do estabelecimento."""
        query = (
            select(Especialidade)
            .where(Especialidade.estabelecimento_id == estabelecimento_id)
            .order_by(Especialidade.nome)
        )
        if apenas_ativas:
            query = query.where(Especialidade.ativo == True)  # noqa: E712
        result = await self.db.execute(query)
        return list(result.scalars().all())

    async def buscar_por_id(
        self,
        especialidade_id: int,
        estabelecimento_id: int | None = None,
    ) -> Especialidade | None:
        """Busca especialidade por ID, opcionalmente filtrando pelo estabelecimento."""
        query = select(Especialidade).where(Especialidade.id == especialidade_id)
        if estabelecimento_id is not None:
            query = query.where(Especialidade.estabelecimento_id == estabelecimento_id)
        result = await self.db.execute(query)
        return result.scalar_one_or_none()

    async def criar(
        self,
        dados: EspecialidadeCreate,
        estabelecimento_id: int,
    ) -> Especialidade:
        """Cria nova especialidade no estabelecimento."""
        data = dados.model_dump()
        data["estabelecimento_id"] = estabelecimento_id
        especialidade = Especialidade(**data)
        self.db.add(especialidade)
        await self.db.flush()
        await self.db.refresh(especialidade)
        log.info(
            "especialidade_criada",
            nome=especialidade.nome,
            id=especialidade.id,
            estabelecimento_id=estabelecimento_id,
        )
        return especialidade

    async def atualizar(
        self,
        especialidade_id: int,
        dados: EspecialidadeUpdate,
        estabelecimento_id: int,
    ) -> Especialidade | None:
        """Atualiza especialidade existente (somente do estabelecimento)."""
        especialidade = await self.buscar_por_id(especialidade_id, estabelecimento_id)
        if not especialidade:
            return None

        update_data = dados.model_dump(exclude_unset=True)
        for campo, valor in update_data.items():
            setattr(especialidade, campo, valor)

        await self.db.flush()
        await self.db.refresh(especialidade)
        log.info("especialidade_atualizada", id=especialidade_id)
        return especialidade

    async def desativar(
        self,
        especialidade_id: int,
        estabelecimento_id: int,
    ) -> Especialidade | None:
        """Desativa especialidade (soft delete, somente do estabelecimento)."""
        especialidade = await self.buscar_por_id(especialidade_id, estabelecimento_id)
        if not especialidade:
            return None

        especialidade.ativo = False
        await self.db.flush()
        await self.db.refresh(especialidade)
        log.info("especialidade_desativada", id=especialidade_id)
        return especialidade
