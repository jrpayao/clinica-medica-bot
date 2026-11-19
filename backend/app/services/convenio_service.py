import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.cliente_convenio import ClienteConvenio
from app.models.convenio import Convenio
from app.models.convenio_plano import ConvenioPlano
from app.schemas.cliente_convenio import ClienteConvenioCreate, ClienteConvenioUpdate
from app.schemas.convenio import ConvenioCreate, ConvenioUpdate
from app.schemas.convenio_plano import ConvenioPlanoCreate, ConvenioPlanoUpdate

log = structlog.get_logger(__name__)


class ConvenioService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    # ── Operadoras ──────────────────────────────────────────────

    async def listar_ativos(self, estabelecimento_id: int) -> list[Convenio]:
        result = await self.db.execute(
            select(Convenio)
            .where(Convenio.estabelecimento_id == estabelecimento_id, Convenio.ativo == True)  # noqa: E712
            .order_by(Convenio.nome)
        )
        return result.scalars().all()

    async def listar_todos(self, estabelecimento_id: int) -> list[Convenio]:
        result = await self.db.execute(
            select(Convenio)
            .where(Convenio.estabelecimento_id == estabelecimento_id)
            .order_by(Convenio.nome)
        )
        return result.scalars().all()

    async def criar(self, dados: ConvenioCreate, estabelecimento_id: int) -> Convenio:
        convenio = Convenio(**dados.model_dump(), estabelecimento_id=estabelecimento_id)
        self.db.add(convenio)
        await self.db.commit()
        await self.db.refresh(convenio)
        return convenio

    async def atualizar(self, convenio_id: int, dados: ConvenioUpdate) -> Convenio | None:
        convenio = await self.db.get(Convenio, convenio_id)
        if not convenio:
            return None
        for campo, valor in dados.model_dump(exclude_unset=True).items():
            setattr(convenio, campo, valor)
        await self.db.commit()
        await self.db.refresh(convenio)
        return convenio

    # ── Planos ───────────────────────────────────────────────────

    async def listar_planos(self, convenio_id: int) -> list[ConvenioPlano]:
        result = await self.db.execute(
            select(ConvenioPlano)
            .where(ConvenioPlano.convenio_id == convenio_id)
            .order_by(ConvenioPlano.nome)
        )
        return result.scalars().all()

    async def criar_plano(self, convenio_id: int, dados: ConvenioPlanoCreate) -> ConvenioPlano:
        plano = ConvenioPlano(**dados.model_dump(), convenio_id=convenio_id)
        self.db.add(plano)
        await self.db.commit()
        await self.db.refresh(plano)
        return plano

    async def atualizar_plano(self, plano_id: int, dados: ConvenioPlanoUpdate) -> ConvenioPlano | None:
        plano = await self.db.get(ConvenioPlano, plano_id)
        if not plano:
            return None
        for campo, valor in dados.model_dump(exclude_unset=True).items():
            setattr(plano, campo, valor)
        await self.db.commit()
        await self.db.refresh(plano)
        return plano

    # ── Carteirinhas do Cliente ──────────────────────────────────

    async def listar_carteirinhas(self, cliente_id: int) -> list[ClienteConvenio]:
        result = await self.db.execute(
            select(ClienteConvenio)
            .where(ClienteConvenio.cliente_id == cliente_id, ClienteConvenio.ativo == True)  # noqa: E712
            .order_by(ClienteConvenio.principal.desc(), ClienteConvenio.created_at)
        )
        return result.scalars().all()

    async def adicionar_carteirinha(self, cliente_id: int, dados: ClienteConvenioCreate) -> ClienteConvenio:
        carteirinha = ClienteConvenio(**dados.model_dump(), cliente_id=cliente_id)
        self.db.add(carteirinha)
        await self.db.commit()
        await self.db.refresh(carteirinha)
        log.info("carteirinha_adicionada", cliente_id=cliente_id, convenio_id=dados.convenio_id)
        return carteirinha

    async def atualizar_carteirinha(self, cc_id: int, dados: ClienteConvenioUpdate) -> ClienteConvenio | None:
        cc = await self.db.get(ClienteConvenio, cc_id)
        if not cc:
            return None
        for campo, valor in dados.model_dump(exclude_unset=True).items():
            setattr(cc, campo, valor)
        await self.db.commit()
        await self.db.refresh(cc)
        return cc
