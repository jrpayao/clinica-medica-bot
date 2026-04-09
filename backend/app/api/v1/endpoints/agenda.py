from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.dependencies import get_current_user, require_estabelecimento
from app.core.database import get_db
from app.schemas.consulta import (
    ConsultaCancelar,
    ConsultaCreate,
    ConsultaResponse,
    SlotResponse,
)
from app.services.agenda_service import (
    AgendaService,
    ConsultaJaCanceladaError,
    ConsultaJaRealizadaError,
    ConsultaNaoEncontradaError,
    SlotIndisponivelError,
    SlotNaoEncontradoError,
    listar_slots_dia,
)

router = APIRouter(prefix="/agenda", tags=["Agenda"])


@router.get(
    "/slots/dia/{data}",
    summary="Listar slots do dia com consultas embutidas (admin)",
)
async def slots_do_dia(
    data: date,
    medico_id: int | None = Query(None, description="Filtrar por médico"),
    db: AsyncSession = Depends(get_db),
    estabelecimento_id: Annotated[int, Depends(require_estabelecimento)] = ...,
) -> list[dict]:
    """Retorna todos os slots do dia com consulta embutida via LEFT JOIN.

    Slots livres retornam consulta=null.
    CPF do paciente é sempre mascarado.
    RBAC: require_estabelecimento garante isolamento por tenant.
    """
    return await listar_slots_dia(
        db,
        data=data,
        estabelecimento_id=estabelecimento_id,
        medico_id=medico_id,
    )


@router.get(
    "/disponivel",
    response_model=list[SlotResponse],
    summary="Buscar slots disponiveis",
)
async def buscar_disponibilidade(
    especialidade_id: int | None = Query(None),
    medico_id: int | None = Query(None),
    data_inicio: date | None = Query(None),
    data_fim: date | None = Query(None),
    db: AsyncSession = Depends(get_db),
    estabelecimento_id: Annotated[int, Depends(require_estabelecimento)] = ...,
) -> list[SlotResponse]:
    """Busca slots disponíveis do estabelecimento."""
    service = AgendaService(db)
    return await service.buscar_disponibilidade(
        estabelecimento_id=estabelecimento_id,
        especialidade_id=especialidade_id,
        medico_id=medico_id,
        data_inicio=data_inicio,
        data_fim=data_fim,
    )


@router.post(
    "/consultas",
    response_model=ConsultaResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Agendar consulta",
)
async def agendar_consulta(
    dados: ConsultaCreate,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
    estabelecimento_id: Annotated[int, Depends(require_estabelecimento)] = ...,
) -> ConsultaResponse:
    service = AgendaService(db)
    try:
        return await service.agendar_consulta(dados, estabelecimento_id)
    except SlotNaoEncontradoError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except SlotIndisponivelError as e:
        raise HTTPException(status_code=409, detail=str(e))


@router.patch(
    "/consultas/{consulta_id}/cancelar",
    response_model=ConsultaResponse,
    summary="Cancelar consulta",
)
async def cancelar_consulta(
    consulta_id: int,
    dados: ConsultaCancelar,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
    estabelecimento_id: Annotated[int, Depends(require_estabelecimento)] = ...,
) -> ConsultaResponse:
    service = AgendaService(db)
    try:
        return await service.cancelar_consulta(consulta_id, dados.motivo, estabelecimento_id)
    except ConsultaNaoEncontradaError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except (ConsultaJaCanceladaError, ConsultaJaRealizadaError) as e:
        raise HTTPException(status_code=409, detail=str(e))


@router.get(
    "/consultas/{consulta_id}",
    response_model=ConsultaResponse,
    summary="Buscar consulta por ID",
)
async def buscar_consulta(
    consulta_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
    estabelecimento_id: Annotated[int, Depends(require_estabelecimento)] = ...,
) -> ConsultaResponse:
    service = AgendaService(db)
    consulta = await service.buscar_consulta_por_id(consulta_id, estabelecimento_id)
    if not consulta:
        raise HTTPException(status_code=404, detail="Consulta nao encontrada")
    return consulta


@router.get(
    "/consultas/paciente/{paciente_id}",
    response_model=list[ConsultaResponse],
    summary="Listar consultas do paciente",
)
async def listar_consultas_paciente(
    paciente_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
    estabelecimento_id: Annotated[int, Depends(require_estabelecimento)] = ...,
) -> list[ConsultaResponse]:
    service = AgendaService(db)
    return await service.listar_consultas_paciente(paciente_id, estabelecimento_id)
