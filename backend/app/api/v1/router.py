from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.dependencies import require_role, verificar_licenca_ativa
from app.api.v1.endpoints import (
    acoes,
    admin_dashboard,
    admin_plataforma,
    admin_usuarios,
    agenda,
    auth,
    billing,
    chat,
    clientes,
    convenios,
    especialidades,
    estabelecimentos,
    licenca,
    profissionais,
    rag,
    tipo_atendimentos,
)
from app.core.database import get_db
from app.schemas.cliente_convenio import ClienteConvenioCreate, ClienteConvenioOut, ClienteConvenioUpdate
from app.services.convenio_service import ConvenioService

api_router = APIRouter()

# Dependency aplicada em todos os routers de domínio (requer licença ativa)
_LICENCA_DEP = [Depends(verificar_licenca_ativa)]

# Routers públicos / de gestão — sem verificação de licença
api_router.include_router(auth.router)
api_router.include_router(estabelecimentos.router)
api_router.include_router(licenca.router)
api_router.include_router(acoes.router)
api_router.include_router(billing.router)
api_router.include_router(admin_dashboard.router)
api_router.include_router(admin_plataforma.router)
api_router.include_router(admin_usuarios.router)
api_router.include_router(rag.router)

# Routers de domínio — exigem licença ativa
api_router.include_router(convenios.router,      dependencies=_LICENCA_DEP)
api_router.include_router(especialidades.router, dependencies=_LICENCA_DEP)
api_router.include_router(profissionais.router,  dependencies=_LICENCA_DEP)
api_router.include_router(clientes.router,       dependencies=_LICENCA_DEP)
api_router.include_router(agenda.router,         dependencies=_LICENCA_DEP)
api_router.include_router(chat.router,           dependencies=_LICENCA_DEP)
api_router.include_router(tipo_atendimentos.router, dependencies=_LICENCA_DEP)

# WebSocket sem dependency de licença (HTTPBearer é incompatível com WebSocket)
api_router.include_router(chat.ws_router)

# Carteirinhas de clientes — /v1/clientes/{cliente_id}/convenios
_cc_router = APIRouter(prefix="/clientes/{cliente_id}/convenios", tags=["Carteirinhas"])


@_cc_router.get("", response_model=list[ClienteConvenioOut])
async def listar_carteirinhas(
    cliente_id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[dict, Depends(require_role("ADMIN_GLOBAL", "ADMIN_ESTABELECIMENTO", "RECEPCIONISTA"))],
):
    return await ConvenioService(db).listar_carteirinhas(cliente_id)


@_cc_router.post("", response_model=ClienteConvenioOut, status_code=status.HTTP_201_CREATED)
async def adicionar_carteirinha(
    cliente_id: int,
    dados: ClienteConvenioCreate,
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[dict, Depends(require_role("ADMIN_GLOBAL", "ADMIN_ESTABELECIMENTO", "RECEPCIONISTA"))],
):
    return await ConvenioService(db).adicionar_carteirinha(cliente_id, dados)


@_cc_router.patch("/{cc_id}", response_model=ClienteConvenioOut)
async def atualizar_carteirinha(
    cliente_id: int,
    cc_id: int,
    dados: ClienteConvenioUpdate,
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[dict, Depends(require_role("ADMIN_GLOBAL", "ADMIN_ESTABELECIMENTO", "RECEPCIONISTA"))],
):
    cc = await ConvenioService(db).atualizar_carteirinha(cc_id, dados)
    if not cc:
        raise HTTPException(status_code=404, detail="Carteirinha não encontrada")
    return cc


api_router.include_router(_cc_router, dependencies=_LICENCA_DEP)

# ── Vínculos profissional ↔ tipo-atendimento ──────────────────────────
from app.services.tipo_atendimento_service import TipoAtendimentoService as _TASvc
from app.schemas.tipo_atendimento import TipoAtendimentoOut as _TAOut

_prof_ta_router = APIRouter(
    prefix="/profissionais/{profissional_id}/tipo-atendimentos",
    tags=["Vínculos Profissional↔Catálogo"],
)


@_prof_ta_router.get("", response_model=list[_TAOut])
async def listar_tipos_profissional(
    profissional_id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[dict, Depends(require_role("ADMIN_GLOBAL", "ADMIN_ESTABELECIMENTO", "RECEPCIONISTA"))],
):
    return await _TASvc(db).listar_tipos_do_profissional(profissional_id)


@_prof_ta_router.post("/{tipo_id}", status_code=status.HTTP_204_NO_CONTENT)
async def vincular_tipo_profissional(
    profissional_id: int,
    tipo_id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[dict, Depends(require_role("ADMIN_GLOBAL", "ADMIN_ESTABELECIMENTO"))],
):
    ok = await _TASvc(db).vincular_profissional(profissional_id, tipo_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Profissional ou tipo não encontrado")


@_prof_ta_router.delete("/{tipo_id}", status_code=status.HTTP_204_NO_CONTENT)
async def desvincular_tipo_profissional(
    profissional_id: int,
    tipo_id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[dict, Depends(require_role("ADMIN_GLOBAL", "ADMIN_ESTABELECIMENTO"))],
):
    ok = await _TASvc(db).desvincular_profissional(profissional_id, tipo_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Profissional ou tipo não encontrado")


api_router.include_router(_prof_ta_router, dependencies=_LICENCA_DEP)
