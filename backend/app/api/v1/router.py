from fastapi import APIRouter, Depends

from app.api.v1.dependencies import verificar_licenca_ativa
from app.api.v1.endpoints import (
    acoes,
    admin_dashboard,
    admin_plataforma,
    admin_usuarios,
    agenda,
    auth,
    billing,
    chat,
    convenios,
    especialidades,
    estabelecimentos,
    licenca,
    medicos,
    pacientes,
    rag,
)

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
api_router.include_router(medicos.router,        dependencies=_LICENCA_DEP)
api_router.include_router(pacientes.router,      dependencies=_LICENCA_DEP)
api_router.include_router(agenda.router,         dependencies=_LICENCA_DEP)
api_router.include_router(chat.router,           dependencies=_LICENCA_DEP)

# WebSocket sem dependency de licença (HTTPBearer é incompatível com WebSocket)
api_router.include_router(chat.ws_router)
