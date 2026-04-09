from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.dependencies import get_current_user, require_estabelecimento, require_role
from app.core.database import get_db
from app.schemas.paciente import PacienteCreate, PacienteResponse, PacienteUpdate
from app.services.paciente_service import PacienteService

router = APIRouter(prefix="/pacientes", tags=["Pacientes"])


@router.get(
    "/",
    response_model=list[PacienteResponse],
    summary="Listar pacientes",
)
async def listar_pacientes(
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(
        require_role("ADMIN_GLOBAL", "ADMIN_ESTABELECIMENTO", "RECEPCIONISTA")
    ),
    estabelecimento_id: Annotated[int, Depends(require_estabelecimento)] = ...,
) -> list[PacienteResponse]:
    service = PacienteService(db)
    return await service.listar(estabelecimento_id)


@router.get(
    "/{paciente_id}",
    response_model=PacienteResponse,
    summary="Buscar paciente",
)
async def buscar_paciente(
    paciente_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
    estabelecimento_id: Annotated[int, Depends(require_estabelecimento)] = ...,
) -> PacienteResponse:
    service = PacienteService(db)
    paciente = await service.buscar_por_id(paciente_id, estabelecimento_id)
    if not paciente:
        raise HTTPException(status_code=404, detail="Paciente nao encontrado")
    return paciente


@router.post(
    "/",
    response_model=PacienteResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Criar paciente",
)
async def criar_paciente(
    dados: PacienteCreate,
    db: AsyncSession = Depends(get_db),
    estabelecimento_id: Annotated[int, Depends(require_estabelecimento)] = ...,
) -> PacienteResponse:
    """Criar paciente. Requer token com estabelecimento_id (ex: via chat token)."""
    service = PacienteService(db)
    return await service.criar(dados, estabelecimento_id)


@router.patch(
    "/{paciente_id}",
    response_model=PacienteResponse,
    summary="Atualizar paciente",
)
async def atualizar_paciente(
    paciente_id: int,
    dados: PacienteUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
    estabelecimento_id: Annotated[int, Depends(require_estabelecimento)] = ...,
) -> PacienteResponse:
    service = PacienteService(db)
    paciente = await service.atualizar(paciente_id, dados, estabelecimento_id)
    if not paciente:
        raise HTTPException(status_code=404, detail="Paciente nao encontrado")
    return paciente
