from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.dependencies import require_estabelecimento, require_role
from app.core.database import get_db
from app.schemas.tipo_atendimento import TipoAtendimentoCreate, TipoAtendimentoOut, TipoAtendimentoUpdate
from app.services.tipo_atendimento_service import TipoAtendimentoService

router = APIRouter(prefix="/tipo-atendimentos", tags=["Catálogo de Serviços"])

_ADMIN = ("ADMIN_GLOBAL", "ADMIN_ESTABELECIMENTO")


@router.get("", response_model=list[TipoAtendimentoOut])
async def listar_tipos(
    estabelecimento_id: Annotated[int, Depends(require_estabelecimento)],
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[dict, Depends(require_role("ADMIN_GLOBAL", "ADMIN_ESTABELECIMENTO", "RECEPCIONISTA"))],
):
    return await TipoAtendimentoService(db).listar_todos(estabelecimento_id)


@router.post("", response_model=TipoAtendimentoOut, status_code=status.HTTP_201_CREATED)
async def criar_tipo(
    dados: TipoAtendimentoCreate,
    estabelecimento_id: Annotated[int, Depends(require_estabelecimento)],
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[dict, Depends(require_role(*_ADMIN))],
):
    return await TipoAtendimentoService(db).criar(dados, estabelecimento_id)


@router.patch("/{tipo_id}", response_model=TipoAtendimentoOut)
async def atualizar_tipo(
    tipo_id: int,
    dados: TipoAtendimentoUpdate,
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[dict, Depends(require_role(*_ADMIN))],
):
    tipo = await TipoAtendimentoService(db).atualizar(tipo_id, dados)
    if not tipo:
        raise HTTPException(status_code=404, detail="Tipo de atendimento não encontrado")
    return tipo


@router.get("/{tipo_id}/profissionais", response_model=list[int])
async def listar_profissionais_do_tipo(
    tipo_id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[dict, Depends(require_role("ADMIN_GLOBAL", "ADMIN_ESTABELECIMENTO", "RECEPCIONISTA"))],
):
    """Retorna IDs dos profissionais vinculados a este tipo de atendimento."""
    from sqlalchemy import select

    from app.models.tipo_atendimento import profissional_tipo_atendimentos

    result = await db.execute(
        select(profissional_tipo_atendimentos.c.profissional_id).where(
            profissional_tipo_atendimentos.c.tipo_atendimento_id == tipo_id
        )
    )
    return [row[0] for row in result.fetchall()]
