from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.dependencies import get_current_user, require_estabelecimento, require_role
from app.core.database import get_db
from app.schemas.cliente_convenio import ClienteConvenioCreate, ClienteConvenioOut, ClienteConvenioUpdate
from app.schemas.convenio import ConvenioCreate, ConvenioOut, ConvenioUpdate
from app.schemas.convenio_plano import ConvenioPlanoCreate, ConvenioPlanoOut, ConvenioPlanoUpdate
from app.services.convenio_service import ConvenioService

router = APIRouter(prefix="/convenios", tags=["Convênios"])

_ADMIN = ("ADMIN_GLOBAL", "ADMIN_ESTABELECIMENTO")


@router.get("", response_model=list[ConvenioOut])
async def listar_convenios(
    estabelecimento_id: Annotated[int, Depends(require_estabelecimento)],
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[dict, Depends(require_role("ADMIN_GLOBAL", "ADMIN_ESTABELECIMENTO", "RECEPCIONISTA"))],
):
    return await ConvenioService(db).listar_todos(estabelecimento_id)


@router.post("", response_model=ConvenioOut, status_code=status.HTTP_201_CREATED)
async def criar_convenio(
    dados: ConvenioCreate,
    estabelecimento_id: Annotated[int, Depends(require_estabelecimento)],
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[dict, Depends(require_role(*_ADMIN))],
):
    return await ConvenioService(db).criar(dados, estabelecimento_id)


@router.patch("/{convenio_id}", response_model=ConvenioOut)
async def atualizar_convenio(
    convenio_id: int,
    dados: ConvenioUpdate,
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[dict, Depends(require_role(*_ADMIN))],
):
    convenio = await ConvenioService(db).atualizar(convenio_id, dados)
    if not convenio:
        raise HTTPException(status_code=404, detail="Convênio não encontrado")
    return convenio


@router.get("/{convenio_id}/planos", response_model=list[ConvenioPlanoOut])
async def listar_planos(
    convenio_id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[dict, Depends(require_role("ADMIN_GLOBAL", "ADMIN_ESTABELECIMENTO", "RECEPCIONISTA"))],
):
    return await ConvenioService(db).listar_planos(convenio_id)


@router.post("/{convenio_id}/planos", response_model=ConvenioPlanoOut, status_code=status.HTTP_201_CREATED)
async def criar_plano(
    convenio_id: int,
    dados: ConvenioPlanoCreate,
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[dict, Depends(require_role(*_ADMIN))],
):
    return await ConvenioService(db).criar_plano(convenio_id, dados)


@router.patch("/{convenio_id}/planos/{plano_id}", response_model=ConvenioPlanoOut)
async def atualizar_plano(
    convenio_id: int,
    plano_id: int,
    dados: ConvenioPlanoUpdate,
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[dict, Depends(require_role(*_ADMIN))],
):
    plano = await ConvenioService(db).atualizar_plano(plano_id, dados)
    if not plano:
        raise HTTPException(status_code=404, detail="Plano não encontrado")
    return plano
