"""Endpoints REST para gerenciamento de estabelecimentos de saúde.

Acesso:
- GET  /v1/estabelecimentos/          → ADMIN_GLOBAL
- POST /v1/estabelecimentos/          → ADMIN_GLOBAL
- GET  /v1/estabelecimentos/{id}      → ADMIN_GLOBAL
- PATCH /v1/estabelecimentos/{id}     → ADMIN_GLOBAL
- DELETE /v1/estabelecimentos/{id}    → ADMIN_GLOBAL

- POST /v1/admin/selecionar-estabelecimento → ADMIN_GLOBAL
  Gera token escopado para um estabelecimento específico.
"""


import structlog
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.dependencies import require_role
from app.core.database import get_db
from app.core.security import create_access_token
from app.schemas.estabelecimento import (
    EstabelecimentoCreate,
    EstabelecimentoResponse,
    EstabelecimentoUpdate,
)
from app.services.estabelecimento_service import EstabelecimentoService

log = structlog.get_logger(__name__)

router = APIRouter(tags=["Estabelecimentos"])


# ──────────────────────────────────────────────────────────
# CRUD /v1/estabelecimentos/
# ──────────────────────────────────────────────────────────

@router.get(
    "/estabelecimentos/",
    response_model=list[EstabelecimentoResponse],
    summary="Listar todos os estabelecimentos",
)
async def listar_estabelecimentos(
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(require_role("ADMIN_GLOBAL")),
) -> list[EstabelecimentoResponse]:
    """Lista todos os estabelecimentos ativos. Acesso: ADMIN_GLOBAL."""
    service = EstabelecimentoService(db)
    return await service.listar()


@router.post(
    "/estabelecimentos/",
    response_model=EstabelecimentoResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Criar estabelecimento",
)
async def criar_estabelecimento(
    dados: EstabelecimentoCreate,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(require_role("ADMIN_GLOBAL")),
) -> EstabelecimentoResponse:
    """Cria novo estabelecimento na plataforma. Acesso: ADMIN_GLOBAL."""
    service = EstabelecimentoService(db)
    return await service.criar(dados)


@router.get(
    "/estabelecimentos/{estabelecimento_id}",
    response_model=EstabelecimentoResponse,
    summary="Buscar estabelecimento por ID",
)
async def buscar_estabelecimento(
    estabelecimento_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(require_role("ADMIN_GLOBAL")),
) -> EstabelecimentoResponse:
    service = EstabelecimentoService(db)
    est = await service.buscar_por_id(estabelecimento_id)
    if not est:
        raise HTTPException(status_code=404, detail="Estabelecimento nao encontrado")
    return est


@router.patch(
    "/estabelecimentos/{estabelecimento_id}",
    response_model=EstabelecimentoResponse,
    summary="Atualizar estabelecimento",
)
async def atualizar_estabelecimento(
    estabelecimento_id: int,
    dados: EstabelecimentoUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(require_role("ADMIN_GLOBAL")),
) -> EstabelecimentoResponse:
    service = EstabelecimentoService(db)
    est = await service.atualizar(estabelecimento_id, dados)
    if not est:
        raise HTTPException(status_code=404, detail="Estabelecimento nao encontrado")
    return est


@router.delete(
    "/estabelecimentos/{estabelecimento_id}",
    response_model=EstabelecimentoResponse,
    summary="Desativar estabelecimento",
)
async def desativar_estabelecimento(
    estabelecimento_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(require_role("ADMIN_GLOBAL")),
) -> EstabelecimentoResponse:
    service = EstabelecimentoService(db)
    est = await service.desativar(estabelecimento_id)
    if not est:
        raise HTTPException(status_code=404, detail="Estabelecimento nao encontrado")
    return est


# ──────────────────────────────────────────────────────────
# POST /v1/admin/selecionar-estabelecimento
# ──────────────────────────────────────────────────────────

class SelecionarEstabelecimentoRequest:
    estabelecimento_id: int


from pydantic import BaseModel  # noqa: E402 (import após class stub)


class SelecionarEstabelecimentoSchema(BaseModel):
    estabelecimento_id: int


class TokenEstabelecimentoResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    estabelecimento_id: int


@router.post(
    "/admin/selecionar-estabelecimento",
    response_model=TokenEstabelecimentoResponse,
    summary="ADMIN_GLOBAL — obter token escopado para um estabelecimento",
)
async def selecionar_estabelecimento(
    dados: SelecionarEstabelecimentoSchema,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(require_role("ADMIN_GLOBAL")),
) -> TokenEstabelecimentoResponse:
    """Gera access token com estabelecimento_id para ADMIN_GLOBAL operar
    dentro de um estabelecimento específico.

    O token resultante contém role=ADMIN_GLOBAL + estabelecimento_id,
    permitindo acesso a todos os endpoints de domínio do estabelecimento selecionado.
    """
    service = EstabelecimentoService(db)
    est = await service.buscar_por_id(dados.estabelecimento_id)
    if not est:
        raise HTTPException(status_code=404, detail="Estabelecimento nao encontrado")
    if not est.ativo:
        raise HTTPException(status_code=422, detail="Estabelecimento inativo")

    # Gerar token escopado mantendo sub e role do ADMIN_GLOBAL
    token_data = {
        "sub": current_user["sub"],
        "email": current_user.get("email"),
        "role": "ADMIN_GLOBAL",
        "estabelecimento_id": dados.estabelecimento_id,
    }
    access_token = create_access_token(token_data)

    log.info(
        "admin_global_selecionou_estabelecimento",
        sub=current_user["sub"],
        estabelecimento_id=dados.estabelecimento_id,
        nome=est.nome,
    )

    return TokenEstabelecimentoResponse(
        access_token=access_token,
        estabelecimento_id=dados.estabelecimento_id,
    )


# ──────────────────────────────────────────────────────────
# POST /v1/admin/modo-global
# ──────────────────────────────────────────────────────────

class ModoGlobalResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


@router.post(
    "/admin/modo-global",
    response_model=ModoGlobalResponse,
    summary="ADMIN_GLOBAL — voltar ao token global (sem estabelecimento_id)",
)
async def voltar_modo_global(
    current_user: dict = Depends(require_role("ADMIN_GLOBAL")),
) -> ModoGlobalResponse:
    """Emite um novo token ADMIN_GLOBAL sem estabelecimento_id.

    Permite que um ADMIN_GLOBAL com token escopado volte ao modo global
    para visualizar todos os estabelecimentos.
    """
    token_data = {
        "sub": current_user["sub"],
        "email": current_user.get("email"),
        "role": "ADMIN_GLOBAL",
        # estabelecimento_id intencionalmente ausente
    }
    access_token = create_access_token(token_data)

    log.info("admin_global_voltou_modo_global", sub=current_user["sub"])

    return ModoGlobalResponse(access_token=access_token)
