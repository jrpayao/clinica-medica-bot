"""Painel do profissional (G24) — tudo restrito ao profissional_id do token.

GET   /v1/profissional/painel                       — resumo e fila do dia do profissional
PATCH /v1/profissional/atendimentos/{id}/status     — iniciar e concluir o próprio atendimento
GET   /v1/profissional/clientes                     — pacientes que ele já atendeu na unidade
GET   /v1/profissional/unidades                     — unidades onde atende
POST  /v1/profissional/selecionar-unidade           — troca a unidade do token (só onde há vínculo)

RBAC: somente MEDICO. Isolamento: estabelecimento do token + profissional do token.
"""

from datetime import date
from typing import Annotated

import structlog
from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.dependencies import profissional_do_token, require_estabelecimento, require_role
from app.core.database import get_db
from app.core.security import create_access_token
from app.core.tempo import fuso_do_estabelecimento, hoje_local
from app.schemas.atendimento import TransicaoStatusRequest
from app.services.painel_profissional_service import (
    listar_clientes_do_profissional,
    unidades_do_profissional,
)
from app.services.recepcao_service import (
    AtendimentoNaoEncontradoError,
    TransicaoInvalidaError,
    listar_atendimentos_do_dia,
    montar_resumo,
    mudar_status,
    proximas_acoes,
)

log = structlog.get_logger(__name__)

PERFIL = "MEDICO"

router = APIRouter(prefix="/profissional", tags=["Painel do Profissional"])


async def _profissional(usuario: Annotated[dict, Depends(require_role(PERFIL))]) -> int:
    return profissional_do_token(usuario)  # type: ignore[return-value]  # MEDICO nunca devolve None


@router.get("/painel", summary="Resumo e fila do dia do profissional")
async def painel_do_profissional(
    data: date | None = Query(None, description="Dia consultado (padrão: hoje)"),
    db: AsyncSession = Depends(get_db),
    profissional_id: int = Depends(_profissional),
    estabelecimento_id: Annotated[int, Depends(require_estabelecimento)] = ...,
) -> dict:
    dia = data or hoje_local(await fuso_do_estabelecimento(db, estabelecimento_id))
    atendimentos = await listar_atendimentos_do_dia(
        db, data=dia, estabelecimento_id=estabelecimento_id, profissional_id=profissional_id, perfil=PERFIL,
    )
    return {"data": str(dia), "resumo": montar_resumo(atendimentos), "atendimentos": atendimentos}


@router.patch("/atendimentos/{atendimento_id}/status", summary="Iniciar ou concluir o próprio atendimento")
async def alterar_status_do_proprio_atendimento(
    atendimento_id: int,
    dados: TransicaoStatusRequest,
    db: AsyncSession = Depends(get_db),
    usuario: dict = Depends(require_role(PERFIL)),
    profissional_id: int = Depends(_profissional),
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
            profissional_id=profissional_id,
            perfil=PERFIL,
        )
    except AtendimentoNaoEncontradoError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except TransicaoInvalidaError as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))

    await db.commit()
    return {
        "atendimento_id": atendimento.id,
        "status": atendimento.status.value,
        "acoes": proximas_acoes(atendimento.status, PERFIL),
    }


@router.get("/clientes", summary="Pacientes que o profissional já atendeu na unidade")
async def meus_clientes(
    db: AsyncSession = Depends(get_db),
    profissional_id: int = Depends(_profissional),
    estabelecimento_id: Annotated[int, Depends(require_estabelecimento)] = ...,
) -> list[dict]:
    return await listar_clientes_do_profissional(
        db, profissional_id=profissional_id, estabelecimento_id=estabelecimento_id
    )


@router.get("/unidades", summary="Unidades onde o profissional atende")
async def minhas_unidades(
    db: AsyncSession = Depends(get_db),
    profissional_id: int = Depends(_profissional),
) -> list[dict]:
    return await unidades_do_profissional(db, profissional_id)


class SelecionarUnidadeRequest(BaseModel):
    estabelecimento_id: int


@router.post("/selecionar-unidade", summary="Trocar a unidade ativa do profissional")
async def selecionar_unidade(
    dados: SelecionarUnidadeRequest,
    db: AsyncSession = Depends(get_db),
    usuario: dict = Depends(require_role(PERFIL)),
    profissional_id: int = Depends(_profissional),
) -> dict:
    """Emite um token para outra unidade — somente onde o profissional tem vínculo ativo."""
    unidades = await unidades_do_profissional(db, profissional_id)
    if dados.estabelecimento_id not in {u["id"] for u in unidades}:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Você não atende nesta unidade.",
        )
    token = create_access_token({
        "sub": usuario["sub"],
        "email": usuario.get("email"),
        "nome": usuario.get("nome"),
        "role": PERFIL,
        "profissional_id": profissional_id,
        "estabelecimento_id": dados.estabelecimento_id,
    })
    log.info("profissional_trocou_unidade", sub=usuario["sub"], estabelecimento_id=dados.estabelecimento_id)
    return {"access_token": token, "token_type": "bearer", "estabelecimento_id": dados.estabelecimento_id}
