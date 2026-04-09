"""Service para EstabelecimentoSaude — lógica de negócio do tenant."""

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.estabelecimento import EstabelecimentoSaude
from app.schemas.estabelecimento import EstabelecimentoCreate, EstabelecimentoUpdate

log = structlog.get_logger(__name__)


class EstabelecimentoService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def criar(self, dados: EstabelecimentoCreate) -> EstabelecimentoSaude:
        from app.services.licenca_service import LicencaService

        log.info("criando_estabelecimento", nome=dados.nome, tipo=dados.tipo.value)
        est = EstabelecimentoSaude(**dados.model_dump())
        self.db.add(est)
        await self.db.flush()
        await self.db.refresh(est)

        # Criar licença trial automaticamente na mesma transação
        licenca_svc = LicencaService(self.db)
        await licenca_svc.ativar_trial(est.id, plano=dados.plano)

        return est

    async def listar(self) -> list[EstabelecimentoSaude]:
        result = await self.db.execute(
            select(EstabelecimentoSaude).where(EstabelecimentoSaude.ativo == True).order_by(EstabelecimentoSaude.nome)  # noqa: E712
        )
        return list(result.scalars().all())

    async def buscar_por_id(self, est_id: int) -> EstabelecimentoSaude | None:
        result = await self.db.execute(
            select(EstabelecimentoSaude).where(EstabelecimentoSaude.id == est_id)
        )
        return result.scalar_one_or_none()

    async def buscar_por_slug(self, slug: str) -> EstabelecimentoSaude | None:
        result = await self.db.execute(
            select(EstabelecimentoSaude).where(EstabelecimentoSaude.slug == slug)
        )
        return result.scalar_one_or_none()

    async def atualizar(
        self, est_id: int, dados: EstabelecimentoUpdate
    ) -> EstabelecimentoSaude | None:
        est = await self.buscar_por_id(est_id)
        if not est:
            return None

        for campo, valor in dados.model_dump(exclude_none=True).items():
            setattr(est, campo, valor)

        await self.db.flush()
        await self.db.refresh(est)
        log.info("estabelecimento_atualizado", id=est_id)
        return est

    async def desativar(self, est_id: int) -> EstabelecimentoSaude | None:
        est = await self.buscar_por_id(est_id)
        if not est:
            return None
        est.ativo = False
        await self.db.flush()
        log.info("estabelecimento_desativado", id=est_id)
        return est
