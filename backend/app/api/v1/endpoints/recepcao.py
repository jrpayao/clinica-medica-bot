"""Painel da recepção (G23).

GET   /v1/recepcao/painel                         — resumo e fila do dia da unidade
PATCH /v1/recepcao/atendimentos/{id}/status       — check-in e avanço de status

RBAC: RECEPCIONISTA, ADMIN_ESTABELECIMENTO e ADMIN_GLOBAL (com unidade selecionada).
Isolamento: sempre pelo estabelecimento do token (require_estabelecimento).
"""

from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.dependencies import require_estabelecimento, require_role
from app.core.database import get_db
from app.core.tempo import fuso_do_estabelecimento, hoje_local
from app.schemas.atendimento import TransicaoStatusRequest
from app.services.recepcao_service import (
    AtendimentoNaoEncontradoError,
    TransicaoInvalidaError,
    listar_atendimentos_do_dia,
    montar_resumo,
    mudar_status,
    proximas_acoes,
)

ROLES_RECEPCAO = ("ADMIN_GLOBAL", "ADMIN_ESTABELECIMENTO", "RECEPCIONISTA")

router = APIRouter(prefix="/recepcao", tags=["Recepção"])


@router.get("/painel", summary="Resumo e fila de atendimentos do dia")
async def painel_da_recepcao(
    data: date | None = Query(None, description="Dia consultado (padrão: hoje)"),
    db: AsyncSession = Depends(get_db),
    _: dict = Depends(require_role(*ROLES_RECEPCAO)),
    estabelecimento_id: Annotated[int, Depends(require_estabelecimento)] = ...,
) -> dict:
    dia = data or hoje_local(await fuso_do_estabelecimento(db, estabelecimento_id))
    atendimentos = await listar_atendimentos_do_dia(db, data=dia, estabelecimento_id=estabelecimento_id)
    return {"data": str(dia), "resumo": montar_resumo(atendimentos), "atendimentos": atendimentos}


@router.patch("/atendimentos/{atendimento_id}/status", summary="Check-in e avanço de status")
async def alterar_status_do_atendimento(
    atendimento_id: int,
    dados: TransicaoStatusRequest,
    db: AsyncSession = Depends(get_db),
    usuario: dict = Depends(require_role(*ROLES_RECEPCAO)),
    estabelecimento_id: Annotated[int, Depends(require_estabelecimento)] = ...,
) -> dict:
    try:
        atendimento = await mudar_status(
            db,
            atendimento_id=atendimento_id,
            status_novo=dados.status_novo,
            estabelecimento_id=estabelecimento_id,
            usuario_id=int(usuario["sub"]) if usuario.get("sub") else None,
            observacao=dados.observacao,
        )
    except AtendimentoNaoEncontradoError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except TransicaoInvalidaError as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))

    await db.commit()
    return {
        "atendimento_id": atendimento.id,
        "status": atendimento.status.value,
        "acoes": proximas_acoes(atendimento.status),
    }
