import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.estabelecimento import EstabelecimentoSaude
from app.models.profissional import Profissional
from app.models.tipo_atendimento import TipoAtendimento
from app.schemas.tipo_atendimento import TipoAtendimentoCreate, TipoAtendimentoUpdate
from app.schemas.vocabulario import VocabularioUpdate

log = structlog.get_logger(__name__)


class TipoAtendimentoService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    # ── Catálogo de serviços ─────────────────────────────────────

    async def listar_ativos(self, estabelecimento_id: int) -> list[TipoAtendimento]:
        result = await self.db.execute(
            select(TipoAtendimento)
            .where(
                TipoAtendimento.estabelecimento_id == estabelecimento_id,
                TipoAtendimento.ativo == True,  # noqa: E712
            )
            .order_by(TipoAtendimento.nome)
        )
        return result.scalars().all()

    async def listar_todos(self, estabelecimento_id: int) -> list[TipoAtendimento]:
        result = await self.db.execute(
            select(TipoAtendimento)
            .where(TipoAtendimento.estabelecimento_id == estabelecimento_id)
            .order_by(TipoAtendimento.nome)
        )
        return result.scalars().all()

    async def criar(self, dados: TipoAtendimentoCreate, estabelecimento_id: int) -> TipoAtendimento:
        tipo = TipoAtendimento(**dados.model_dump(), estabelecimento_id=estabelecimento_id)
        self.db.add(tipo)
        await self.db.commit()
        await self.db.refresh(tipo)
        log.info("tipo_atendimento_criado", nome=tipo.nome, estabelecimento_id=estabelecimento_id)
        return tipo

    async def atualizar(self, tipo_id: int, dados: TipoAtendimentoUpdate) -> TipoAtendimento | None:
        tipo = await self.db.get(TipoAtendimento, tipo_id)
        if not tipo:
            return None
        for campo, valor in dados.model_dump(exclude_unset=True).items():
            setattr(tipo, campo, valor)
        await self.db.commit()
        await self.db.refresh(tipo)
        return tipo

    # ── Vínculo profissional ↔ tipo ──────────────────────────────

    async def vincular_profissional(self, profissional_id: int, tipo_id: int) -> bool:
        profissional = await self.db.get(Profissional, profissional_id)
        tipo = await self.db.get(TipoAtendimento, tipo_id)
        if not profissional or not tipo:
            return False
        if tipo not in profissional.tipos_atendimento:
            profissional.tipos_atendimento.append(tipo)
            await self.db.commit()
        return True

    async def desvincular_profissional(self, profissional_id: int, tipo_id: int) -> bool:
        profissional = await self.db.get(Profissional, profissional_id)
        tipo = await self.db.get(TipoAtendimento, tipo_id)
        if not profissional or not tipo:
            return False
        if tipo in profissional.tipos_atendimento:
            profissional.tipos_atendimento.remove(tipo)
            await self.db.commit()
        return True

    async def listar_tipos_do_profissional(self, profissional_id: int) -> list[TipoAtendimento]:
        profissional = await self.db.get(Profissional, profissional_id)
        if not profissional:
            return []
        return profissional.tipos_atendimento

    # ── Vocabulário do estabelecimento ───────────────────────────

    async def atualizar_vocabulario(
        self, estabelecimento_id: int, dados: VocabularioUpdate
    ) -> EstabelecimentoSaude | None:
        est = await self.db.get(EstabelecimentoSaude, estabelecimento_id)
        if not est:
            return None
        for campo, valor in dados.model_dump(exclude_unset=True).items():
            setattr(est, campo, valor)
        await self.db.commit()
        await self.db.refresh(est)
        return est
