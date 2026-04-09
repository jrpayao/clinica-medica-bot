from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.dependencies import require_estabelecimento, require_role
from app.core.database import get_db
from app.schemas.especialidade import (
    EspecialidadeCreate,
    EspecialidadeResponse,
    EspecialidadeUpdate,
)
from app.services.especialidade_service import EspecialidadeService

router = APIRouter(prefix="/especialidades", tags=["Especialidades"])


@router.get(
    "/",
    response_model=list[EspecialidadeResponse],
    summary="Listar especialidades",
)
async def listar_especialidades(
    db: AsyncSession = Depends(get_db),
    estabelecimento_id: Annotated[int, Depends(require_estabelecimento)] = ...,
) -> list[EspecialidadeResponse]:
    """Lista especialidades ativas do estabelecimento logado."""
    service = EspecialidadeService(db)
    return await service.listar(estabelecimento_id)


@router.get(
    "/{especialidade_id}",
    response_model=EspecialidadeResponse,
    summary="Buscar especialidade por ID",
)
async def buscar_especialidade(
    especialidade_id: int,
    db: AsyncSession = Depends(get_db),
    estabelecimento_id: Annotated[int, Depends(require_estabelecimento)] = ...,
) -> EspecialidadeResponse:
    service = EspecialidadeService(db)
    especialidade = await service.buscar_por_id(especialidade_id, estabelecimento_id)
    if not especialidade:
        raise HTTPException(status_code=404, detail="Especialidade nao encontrada")
    return especialidade


@router.post(
    "/",
    response_model=EspecialidadeResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Criar especialidade",
)
async def criar_especialidade(
    dados: EspecialidadeCreate,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(
        require_role("ADMIN_GLOBAL", "ADMIN_ESTABELECIMENTO")
    ),
    estabelecimento_id: Annotated[int, Depends(require_estabelecimento)] = ...,
) -> EspecialidadeResponse:
    service = EspecialidadeService(db)
    return await service.criar(dados, estabelecimento_id)


@router.patch(
    "/{especialidade_id}",
    response_model=EspecialidadeResponse,
    summary="Atualizar especialidade",
)
async def atualizar_especialidade(
    especialidade_id: int,
    dados: EspecialidadeUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(
        require_role("ADMIN_GLOBAL", "ADMIN_ESTABELECIMENTO")
    ),
    estabelecimento_id: Annotated[int, Depends(require_estabelecimento)] = ...,
) -> EspecialidadeResponse:
    service = EspecialidadeService(db)
    especialidade = await service.atualizar(especialidade_id, dados, estabelecimento_id)
    if not especialidade:
        raise HTTPException(status_code=404, detail="Especialidade nao encontrada")
    return especialidade


@router.delete(
    "/{especialidade_id}",
    response_model=EspecialidadeResponse,
    summary="Desativar especialidade",
)
async def desativar_especialidade(
    especialidade_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(
        require_role("ADMIN_GLOBAL", "ADMIN_ESTABELECIMENTO")
    ),
    estabelecimento_id: Annotated[int, Depends(require_estabelecimento)] = ...,
) -> EspecialidadeResponse:
    service = EspecialidadeService(db)
    especialidade = await service.desativar(especialidade_id, estabelecimento_id)
    if not especialidade:
        raise HTTPException(status_code=404, detail="Especialidade nao encontrada")
    return especialidade
