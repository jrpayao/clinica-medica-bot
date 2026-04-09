from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.dependencies import get_current_user, require_estabelecimento, require_role
from app.core.database import get_db
from app.schemas.cliente import ClienteCreate, ClienteOut, ClienteUpdate
from app.services.cliente_service import ClienteService

router = APIRouter(prefix="/clientes", tags=["Clientes"])


@router.get(
    "/",
    response_model=list[ClienteOut],
    summary="Listar clientes",
)
async def listar_clientes(
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(
        require_role("ADMIN_GLOBAL", "ADMIN_ESTABELECIMENTO", "RECEPCIONISTA")
    ),
    estabelecimento_id: Annotated[int, Depends(require_estabelecimento)] = ...,
) -> list[ClienteOut]:
    service = ClienteService(db)
    return await service.listar(estabelecimento_id)


@router.get(
    "/{cliente_id}",
    response_model=ClienteOut,
    summary="Buscar cliente",
)
async def buscar_cliente(
    cliente_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
    estabelecimento_id: Annotated[int, Depends(require_estabelecimento)] = ...,
) -> ClienteOut:
    service = ClienteService(db)
    cliente = await service.buscar_por_id(cliente_id, estabelecimento_id)
    if not cliente:
        raise HTTPException(status_code=404, detail="Cliente nao encontrado")
    return cliente


@router.post(
    "/",
    response_model=ClienteOut,
    status_code=status.HTTP_201_CREATED,
    summary="Criar cliente",
)
async def criar_cliente(
    dados: ClienteCreate,
    db: AsyncSession = Depends(get_db),
    estabelecimento_id: Annotated[int, Depends(require_estabelecimento)] = ...,
) -> ClienteOut:
    """Criar cliente. Requer token com estabelecimento_id (ex: via chat token)."""
    service = ClienteService(db)
    return await service.criar(dados, estabelecimento_id)


@router.patch(
    "/{cliente_id}",
    response_model=ClienteOut,
    summary="Atualizar cliente",
)
async def atualizar_cliente(
    cliente_id: int,
    dados: ClienteUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
    estabelecimento_id: Annotated[int, Depends(require_estabelecimento)] = ...,
) -> ClienteOut:
    service = ClienteService(db)
    cliente = await service.atualizar(cliente_id, dados, estabelecimento_id)
    if not cliente:
        raise HTTPException(status_code=404, detail="Cliente nao encontrado")
    return cliente
