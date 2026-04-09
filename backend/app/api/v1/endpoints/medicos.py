from datetime import date, time
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.dependencies import require_estabelecimento, require_role
from app.core.database import get_db
from app.schemas.consulta import SlotResponse
from app.schemas.medico import (
    GerarSlotsRequest,
    MedicoCreate,
    MedicoResponse,
    MedicoUpdate,
)
from app.services.medico_service import MedicoService

router = APIRouter(prefix="/medicos", tags=["Medicos"])


@router.get("/", response_model=list[MedicoResponse], summary="Listar medicos")
async def listar_medicos(
    db: AsyncSession = Depends(get_db),
    estabelecimento_id: Annotated[int, Depends(require_estabelecimento)] = ...,
) -> list[MedicoResponse]:
    service = MedicoService(db)
    return await service.listar(estabelecimento_id)


@router.get("/{medico_id}", response_model=MedicoResponse, summary="Buscar medico")
async def buscar_medico(
    medico_id: int,
    db: AsyncSession = Depends(get_db),
) -> MedicoResponse:
    service = MedicoService(db)
    medico = await service.buscar_por_id(medico_id)
    if not medico:
        raise HTTPException(status_code=404, detail="Medico nao encontrado")
    return medico


@router.post(
    "/",
    response_model=MedicoResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Criar medico",
)
async def criar_medico(
    dados: MedicoCreate,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(
        require_role("ADMIN_GLOBAL", "ADMIN_ESTABELECIMENTO")
    ),
    estabelecimento_id: Annotated[int, Depends(require_estabelecimento)] = ...,
) -> MedicoResponse:
    service = MedicoService(db)
    return await service.criar(dados, estabelecimento_id)


@router.patch("/{medico_id}", response_model=MedicoResponse, summary="Atualizar medico")
async def atualizar_medico(
    medico_id: int,
    dados: MedicoUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(
        require_role("ADMIN_GLOBAL", "ADMIN_ESTABELECIMENTO")
    ),
) -> MedicoResponse:
    service = MedicoService(db)
    medico = await service.atualizar(medico_id, dados)
    if not medico:
        raise HTTPException(status_code=404, detail="Medico nao encontrado")
    return medico


@router.delete("/{medico_id}", response_model=MedicoResponse, summary="Desativar medico")
async def desativar_medico(
    medico_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(
        require_role("ADMIN_GLOBAL", "ADMIN_ESTABELECIMENTO")
    ),
) -> MedicoResponse:
    service = MedicoService(db)
    medico = await service.desativar(medico_id)
    if not medico:
        raise HTTPException(status_code=404, detail="Medico nao encontrado")
    return medico


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
    service = MedicoService(db)
    try:
        slots = await service.gerar_slots(
            medico_id=medico_id,
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
