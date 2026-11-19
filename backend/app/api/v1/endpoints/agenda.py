from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.dependencies import get_current_user, get_profissional_restrito, require_estabelecimento
from app.core.database import get_db
from app.core.redis import get_redis_client
from app.models.atendimento import MotivoCancelamento
from app.schemas.atendimento import (
    AtendimentoCancelar,
    AtendimentoCreate,
    AtendimentoOut,
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
from app.services.reagendamento_service import cancelar_com_motivo

router = APIRouter(prefix="/agenda", tags=["Agenda"])


def profissional_efetivo(restrito: int | None, pedido: int | None) -> int | None:
    """MEDICO enxerga sempre a própria agenda, qualquer que seja o filtro pedido."""
    return restrito if restrito is not None else pedido


def garantir_atendimento_proprio(atendimento, restrito: int | None) -> None:
    """Para MEDICO, atendimento de outro profissional se comporta como inexistente."""
    if restrito is not None and atendimento.profissional_id != restrito:
        raise HTTPException(status_code=404, detail="Atendimento nao encontrado")


def origem_do_cancelamento(
    informada: MotivoCancelamento | None, role: str | None
) -> MotivoCancelamento | None:
    """Quem originou o cancelamento.

    Sem informação, o profissional que cancela a própria agenda é a origem; para os demais perfis fica
    em branco e o cliente não recebe oferta de novos horários. SISTEMA não pode ser informado pela API.
    """
    if informada is not None and informada != MotivoCancelamento.SISTEMA:
        return informada
    return MotivoCancelamento.MEDICO if role == "MEDICO" else None


@router.get(
    "/slots/dia/{data}",
    summary="Listar slots do dia com atendimentos embutidos (admin)",
)
async def slots_do_dia(
    data: date,
    profissional_id: int | None = Query(None, description="Filtrar por profissional"),
    db: AsyncSession = Depends(get_db),
    estabelecimento_id: Annotated[int, Depends(require_estabelecimento)] = ...,
    restrito: Annotated[int | None, Depends(get_profissional_restrito)] = None,
) -> list[dict]:
    """Retorna todos os slots do dia com atendimento embutido via LEFT JOIN.

    Slots livres retornam atendimento=null.
    CPF do cliente é sempre mascarado.
    RBAC: require_estabelecimento garante isolamento por tenant.
    """
    return await listar_slots_dia(
        db,
        data=data,
        estabelecimento_id=estabelecimento_id,
        profissional_id=profissional_efetivo(restrito, profissional_id),
    )


@router.get(
    "/disponivel",
    response_model=list[SlotResponse],
    summary="Buscar slots disponiveis",
)
async def buscar_disponibilidade(
    especialidade_id: int | None = Query(None),
    profissional_id: int | None = Query(None),
    data_inicio: date | None = Query(None),
    data_fim: date | None = Query(None),
    db: AsyncSession = Depends(get_db),
    estabelecimento_id: Annotated[int, Depends(require_estabelecimento)] = ...,
    restrito: Annotated[int | None, Depends(get_profissional_restrito)] = None,
) -> list[SlotResponse]:
    """Busca slots disponíveis do estabelecimento."""
    service = AgendaService(db)
    return await service.buscar_disponibilidade(
        estabelecimento_id=estabelecimento_id,
        especialidade_id=especialidade_id,
        profissional_id=profissional_efetivo(restrito, profissional_id),
        data_inicio=data_inicio,
        data_fim=data_fim,
    )


@router.post(
    "/atendimentos",
    response_model=AtendimentoOut,
    status_code=status.HTTP_201_CREATED,
    summary="Agendar atendimento",
)
async def agendar_atendimento(
    dados: AtendimentoCreate,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
    estabelecimento_id: Annotated[int, Depends(require_estabelecimento)] = ...,
    restrito: Annotated[int | None, Depends(get_profissional_restrito)] = None,
) -> AtendimentoOut:
    garantir_atendimento_proprio(dados, restrito)
    service = AgendaService(db)
    try:
        return await service.agendar_consulta(dados, estabelecimento_id)
    except SlotNaoEncontradoError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except SlotIndisponivelError as e:
        raise HTTPException(status_code=409, detail=str(e))


@router.patch(
    "/atendimentos/{atendimento_id}/cancelar",
    response_model=AtendimentoOut,
    summary="Cancelar atendimento",
)
async def cancelar_atendimento(
    atendimento_id: int,
    dados: AtendimentoCancelar,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
    estabelecimento_id: Annotated[int, Depends(require_estabelecimento)] = ...,
    restrito: Annotated[int | None, Depends(get_profissional_restrito)] = None,
) -> AtendimentoOut:
    service = AgendaService(db)
    origem = origem_do_cancelamento(dados.origem, current_user.get("role"))
    if restrito is not None:
        existente = await service.buscar_consulta_por_id(atendimento_id, estabelecimento_id)
        if not existente:
            raise HTTPException(status_code=404, detail="Atendimento nao encontrado")
        garantir_atendimento_proprio(existente, restrito)
    try:
        if origem is None:
            return await service.cancelar_consulta(atendimento_id, dados.motivo, estabelecimento_id)
        return await cancelar_com_motivo(
            db,
            get_redis_client(),
            atendimento_id=atendimento_id,
            texto_motivo=dados.motivo,
            origem=origem,
            estabelecimento_id=estabelecimento_id,
        )
    except ConsultaNaoEncontradaError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except (ConsultaJaCanceladaError, ConsultaJaRealizadaError) as e:
        raise HTTPException(status_code=409, detail=str(e))


@router.get(
    "/atendimentos/{atendimento_id}",
    response_model=AtendimentoOut,
    summary="Buscar atendimento por ID",
)
async def buscar_atendimento(
    atendimento_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
    estabelecimento_id: Annotated[int, Depends(require_estabelecimento)] = ...,
    restrito: Annotated[int | None, Depends(get_profissional_restrito)] = None,
) -> AtendimentoOut:
    service = AgendaService(db)
    atendimento = await service.buscar_consulta_por_id(atendimento_id, estabelecimento_id)
    if not atendimento:
        raise HTTPException(status_code=404, detail="Atendimento nao encontrado")
    garantir_atendimento_proprio(atendimento, restrito)
    return atendimento


@router.get(
    "/atendimentos/cliente/{cliente_id}",
    response_model=list[AtendimentoOut],
    summary="Listar atendimentos do cliente",
)
async def listar_atendimentos_cliente(
    cliente_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
    estabelecimento_id: Annotated[int, Depends(require_estabelecimento)] = ...,
    restrito: Annotated[int | None, Depends(get_profissional_restrito)] = None,
) -> list[AtendimentoOut]:
    service = AgendaService(db)
    atendimentos = await service.listar_consultas_paciente(cliente_id, estabelecimento_id)
    return [a for a in atendimentos if restrito is None or a.profissional_id == restrito]
