import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.cliente import Cliente
from app.schemas.cliente import ClienteCreate, ClienteUpdate

log = structlog.get_logger(__name__)


class ClienteService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def listar(
        self,
        estabelecimento_id: int,
        apenas_ativos: bool = True,
    ) -> list[Cliente]:
        """Lista clientes do estabelecimento."""
        query = (
            select(Cliente)
            .where(Cliente.estabelecimento_id == estabelecimento_id)
            .order_by(Cliente.nome)
        )
        if apenas_ativos:
            query = query.where(Cliente.ativo == True)  # noqa: E712
        result = await self.db.execute(query)
        return list(result.scalars().all())

    async def buscar_por_id(
        self,
        cliente_id: int,
        estabelecimento_id: int | None = None,
    ) -> Cliente | None:
        """Busca cliente por ID, opcionalmente filtrando pelo estabelecimento."""
        query = select(Cliente).where(Cliente.id == cliente_id)
        if estabelecimento_id is not None:
            query = query.where(Cliente.estabelecimento_id == estabelecimento_id)
        result = await self.db.execute(query)
        return result.scalar_one_or_none()

    async def buscar_por_cpf(
        self,
        cpf: str,
        estabelecimento_id: int | None = None,
    ) -> Cliente | None:
        """Busca cliente por CPF no estabelecimento."""
        query = select(Cliente).where(Cliente.cpf == cpf)
        if estabelecimento_id is not None:
            query = query.where(Cliente.estabelecimento_id == estabelecimento_id)
        result = await self.db.execute(query)
        return result.scalar_one_or_none()

    async def criar(
        self,
        dados: ClienteCreate,
        estabelecimento_id: int,
    ) -> Cliente:
        """Cria novo cliente no estabelecimento."""
        data = dados.model_dump()
        data["estabelecimento_id"] = estabelecimento_id
        cliente = Cliente(**data)
        self.db.add(cliente)
        await self.db.flush()
        await self.db.refresh(cliente)
        log.info(
            "cliente_criado",
            cpf_prefixo=dados.cpf[:3] + "***",
            id=cliente.id,
            estabelecimento_id=estabelecimento_id,
        )
        return cliente

    async def atualizar(
        self,
        cliente_id: int,
        dados: ClienteUpdate,
        estabelecimento_id: int | None = None,
    ) -> Cliente | None:
        """Atualiza cliente existente."""
        cliente = await self.buscar_por_id(cliente_id, estabelecimento_id)
        if not cliente:
            return None

        update_data = dados.model_dump(exclude_unset=True)
        for campo, valor in update_data.items():
            setattr(cliente, campo, valor)

        await self.db.flush()
        await self.db.refresh(cliente)
        log.info("cliente_atualizado", id=cliente_id)
        return cliente

    async def desativar(
        self,
        cliente_id: int,
        estabelecimento_id: int | None = None,
    ) -> Cliente | None:
        """Desativa cliente (soft delete)."""
        cliente = await self.buscar_por_id(cliente_id, estabelecimento_id)
        if not cliente:
            return None

        cliente.ativo = False
        await self.db.flush()
        await self.db.refresh(cliente)
        log.info("cliente_desativado", id=cliente_id)
        return cliente
