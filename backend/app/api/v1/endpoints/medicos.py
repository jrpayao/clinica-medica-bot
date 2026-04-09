from datetime import date, time
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.dependencies import require_estabelecimento, require_role
from app.core.database import get_db
from app.schemas.atendimento import SlotResponse
from app.schemas.profissional import (
    GerarSlotsRequest,
    ProfissionalCreate,
    ProfissionalResponse,
    ProfissionalUpdate,
)
from app.services.profissional_service import ProfissionalService

router = APIRouter(prefix="/medicos", tags=["Medicos"])


@router.get("/", response_model=list[ProfissionalResponse], summary="Listar profissionais")
async def listar_medicos(
    db: AsyncSession = Depends(get_db),
    estabelecimento_id: Annotated[int, Depends(require_estabelecimento)] = ...,
) -> list[ProfissionalResponse]:
    service = ProfissionalService(db)
    return await service.listar(estabelecimento_id)


@router.get("/{medico_id}", response_model=ProfissionalResponse, summary="Buscar profissional")
async def buscar_medico(
    medico_id: int,
    db: AsyncSession = Depends(get_db),
) -> ProfissionalResponse:
    service = ProfissionalService(db)
    profissional = await service.buscar_por_id(medico_id)
    if not profissional:
        raise HTTPException(status_code=404, detail="Profissional nao encontrado")
    return profissional


@router.post(
    "/",
    response_model=ProfissionalResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Criar profissional",
)
async def criar_medico(
    dados: ProfissionalCreate,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(
        require_role("ADMIN_GLOBAL", "ADMIN_ESTABELECIMENTO")
    ),
    estabelecimento_id: Annotated[int, Depends(require_estabelecimento)] = ...,
) -> ProfissionalResponse:
    service = ProfissionalService(db)
    return await service.criar(dados, estabelecimento_id)


@router.patch("/{medico_id}", response_model=ProfissionalResponse, summary="Atualizar profissional")
async def atualizar_medico(
    medico_id: int,
    dados: ProfissionalUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(
        require_role("ADMIN_GLOBAL", "ADMIN_ESTABELECIMENTO")
    ),
) -> ProfissionalResponse:
    service = ProfissionalService(db)
    profissional = await service.atualizar(medico_id, dados)
    if not profissional:
        raise HTTPException(status_code=404, detail="Profissional nao encontrado")
    return profissional


@router.delete("/{medico_id}", response_model=ProfissionalResponse, summary="Desativar profissional")
async def desativar_medico(
    medico_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(
        require_role("ADMIN_GLOBAL", "ADMIN_ESTABELECIMENTO")
    ),
) -> ProfissionalResponse:
    service = ProfissionalService(db)
    profissional = await service.desativar(medico_id)
    if not profissional:
        raise HTTPException(status_code=404, detail="Profissional nao encontrado")
    return profissional


@router.post(
    "/{medico_id}/slots",
    response_model=list[SlotResponse],
    status_code=status.HTTP_201_CREATED,
    summary="Gerar slots de agenda",
)
async def gerar_slots(
    medico_id: int,
    dados: GerarSlotsRequest,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(
        require_role("ADMIN_GLOBAL", "ADMIN_ESTABELECIMENTO", "RECEPCIONISTA")
    ),
    estabelecimento_id: Annotated[int, Depends(require_estabelecimento)] = ...,
) -> list[SlotResponse]:
    service = ProfissionalService(db)
    try:
        slots = await service.gerar_slots(
            profissional_id=medico_id,
            data_inicio=date.fromisoformat(dados.data_inicio),
            data_fim=date.fromisoformat(dados.data_fim),
            hora_inicio=time.fromisoformat(dados.hora_inicio),
            hora_fim=time.fromisoformat(dados.hora_fim),
            intervalo_almoco_inicio=(
                time.fromisoformat(dados.intervalo_almoco_inicio)
                if dados.intervalo_almoco_inicio
                else None
            ),
            intervalo_almoco_fim=(
                time.fromisoformat(dados.intervalo_almoco_fim)
                if dados.intervalo_almoco_fim
                else None
            ),
            dias_semana=dados.dias_semana,
            estabelecimento_id=estabelecimento_id,
        )
        return slots
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
