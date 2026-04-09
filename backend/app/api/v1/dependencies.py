"""Dependencies FastAPI para autenticação, RBAC, isolamento de tenant e licenciamento.

Hierarquia:
  get_current_user → valida JWT
  require_role(...)→ garante roles permitidos
  get_estabelecimento_id → extrai tenant do token (row-level isolation)
  require_estabelecimento → alias tipado para uso em endpoints
  verificar_licenca_ativa → bloqueia acesso se licença expirada/suspensa
  require_quota_medico → bloqueia criação se quota de médicos atingida
  require_quota_consulta → bloqueia criação se quota de consultas/mês atingida
"""

from typing import Annotated

import structlog
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import verify_token
from app.models.licenca import Licenca, LicencaStatus

log = structlog.get_logger(__name__)

security_scheme = HTTPBearer()
security_scheme_opcional = HTTPBearer(auto_error=False)


async def get_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials, Depends(security_scheme)],
) -> dict:
    """Extrai e valida usuario do token JWT.

    Retorna o payload do token com sub, role, e dados adicionais.
    """
    payload = verify_token(credentials.credentials)
    if payload is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token invalido ou expirado",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if payload.get("type") != "access":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Tipo de token invalido",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return payload


def require_role(*roles: str):
    """Factory de dependency que verifica se o usuario tem um dos roles permitidos.

    Uso: Depends(require_role("ADMIN_ESTABELECIMENTO", "RECEPCIONISTA"))
    """

    async def check_role(
        current_user: Annotated[dict, Depends(get_current_user)],
    ) -> dict:
        user_role = current_user.get("role", "")
        if user_role not in roles:
            log.warning(
                "acesso_negado_role",
                role_usuario=user_role,
                roles_requeridos=roles,
                sub=current_user.get("sub"),
            )
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Acesso restrito. Roles permitidos: {', '.join(roles)}",
            )
        return current_user

    return check_role


async def get_estabelecimento_id(
    request: Request,
    current_user: Annotated[dict, Depends(get_current_user)],
) -> int:
    """Extrai o estabelecimento_id para isolamento row-level.

    Resolução em ordem de prioridade:
    1. JWT token (ADMIN_ESTABELECIMENTO ou ADMIN_GLOBAL com token escopado)
    2. Header X-Estabelecimento-ID (ADMIN_GLOBAL em modo global com filtro)
    3. HTTP 400 (ADMIN_GLOBAL sem nenhum contexto de tenant)
    4. HTTP 403 (outros roles sem estabelecimento_id — bug de token)
    """
    est_id = current_user.get("estabelecimento_id")
    if est_id is not None:
        return int(est_id)

    role = current_user.get("role", "")
    if role == "ADMIN_GLOBAL":
        header_id = request.headers.get("X-Estabelecimento-ID")
        if header_id:
            try:
                return int(header_id)
            except ValueError:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Header X-Estabelecimento-ID deve ser um inteiro",
                )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Selecione um estabelecimento para acessar este recurso",
        )

    log.error(
        "token_sem_estabelecimento_id",
        role=role,
        sub=current_user.get("sub"),
    )
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="Token nao possui estabelecimento_id. Faça login novamente.",
    )


async def get_estabelecimento_id_chat(
    credentials: Annotated[
        HTTPAuthorizationCredentials | None, Depends(security_scheme_opcional)
    ],
) -> int | None:
    """Dependency opcional para o endpoint de criação de sessão de chat.

    Pacientes anônimos não têm token → retorna None (est_id virá do request body).
    Usuário autenticado com est_id no token → retorna est_id do token.
    ADMIN_GLOBAL sem est_id → retorna None (est_id virá do request body para testes).
    Token inválido → HTTP 401.
    """
    if credentials is None:
        return None

    payload = verify_token(credentials.credentials)
    if payload is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token invalido ou expirado",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return payload.get("estabelecimento_id")


async def require_estabelecimento(
    est_id: Annotated[int, Depends(get_estabelecimento_id)],
) -> int:
    """Alias tipado de get_estabelecimento_id para uso em endpoints.

    Uso: estabelecimento_id: Annotated[int, Depends(require_estabelecimento)]
    """
    return est_id


async def get_estabelecimento_id_opcional(
    request: Request,
    current_user: Annotated[dict, Depends(get_current_user)],
) -> int | None:
    """Variante opcional de get_estabelecimento_id para endpoints que suportam modo global.

    Resolução em ordem de prioridade:
    1. JWT token (ADMIN_ESTABELECIMENTO ou ADMIN_GLOBAL com token escopado)
    2. Header X-Estabelecimento-ID (ADMIN_GLOBAL em modo global com filtro)
    3. None → ADMIN_GLOBAL sem filtro (modo "todas as clínicas")
    4. HTTP 403 (outros roles sem estabelecimento_id — bug de token)
    """
    est_id = current_user.get("estabelecimento_id")
    if est_id is not None:
        return int(est_id)

    role = current_user.get("role", "")
    if role == "ADMIN_GLOBAL":
        header_id = request.headers.get("X-Estabelecimento-ID")
        if header_id:
            try:
                return int(header_id)
            except ValueError:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Header X-Estabelecimento-ID deve ser um inteiro",
                )
        return None  # modo "todas as clínicas" — sem filtro

    log.error(
        "token_sem_estabelecimento_id",
        role=role,
        sub=current_user.get("sub"),
    )
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="Token nao possui estabelecimento_id. Faça login novamente.",
    )


async def verificar_licenca_ativa(
    estabelecimento_id: Annotated[int, Depends(get_estabelecimento_id)],
    db: AsyncSession = Depends(get_db),
) -> Licenca:
    """Verifica se a licença do tenant está válida.

    HTTP 402 → TRIAL expirado ou EXPIRADA
    HTTP 403 → SUSPENSA

    Injetado via dependencies=[] nos routers de domínio.
    """
    from app.services.licenca_service import LicencaService

    service = LicencaService(db)
    licenca = await service.buscar_por_estabelecimento(estabelecimento_id)

    if not licenca:
        raise HTTPException(
            status_code=status.HTTP_402_PAYMENT_REQUIRED,
            detail="Sem licença ativa. Contate o suporte.",
        )

    status_efetivo, valida = service.verificar_validade(licenca)

    if status_efetivo == LicencaStatus.SUSPENSA:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Licença suspensa. Motivo: {licenca.motivo_suspensao or 'não informado'}. Contate o suporte.",
        )

    if not valida:
        raise HTTPException(
            status_code=status.HTTP_402_PAYMENT_REQUIRED,
            detail="Licença expirada. Contate o administrador para renovar.",
        )

    return licenca


async def require_quota_medico(
    licenca: Annotated[Licenca, Depends(verificar_licenca_ativa)],
    db: AsyncSession = Depends(get_db),
) -> None:
    """Bloqueia criação de médico se quota do plano foi atingida."""
    from app.services.licenca_service import LicencaService, QuotaMedicosExcedidaError

    service = LicencaService(db)
    try:
        await service.verificar_quota_medicos(licenca.estabelecimento_id, licenca.plano)
    except QuotaMedicosExcedidaError as e:
        raise HTTPException(
            status_code=status.HTTP_402_PAYMENT_REQUIRED,
            detail=f"Quota de médicos atingida ({e.atual}/{e.limite}) para o plano '{licenca.plano}'. Faça upgrade.",
        )


async def require_quota_consulta(
    licenca: Annotated[Licenca, Depends(verificar_licenca_ativa)],
    db: AsyncSession = Depends(get_db),
) -> None:
    """Bloqueia criação de consulta se quota mensal do plano foi atingida."""
    from app.services.licenca_service import LicencaService, QuotaConsultasExcedidaError

    service = LicencaService(db)
    try:
        await service.verificar_quota_consultas_mes(licenca.estabelecimento_id, licenca.plano)
    except QuotaConsultasExcedidaError as e:
        raise HTTPException(
            status_code=status.HTTP_402_PAYMENT_REQUIRED,
            detail=f"Quota de consultas mensais atingida ({e.atual}/{e.limite}) para o plano '{licenca.plano}'. Faça upgrade.",
        )


async def registrar_acesso_clinica(
    request: Request,
    current_user: Annotated[dict, Depends(get_current_user)],
    db: AsyncSession = Depends(get_db),
) -> None:
    """Registra evento de auditoria quando ADMIN_GLOBAL acessa uma clínica via header.

    Deve ser adicionado como dependency em endpoints de plataforma que aceitam
    X-Estabelecimento-ID de ADMIN_GLOBAL.
    """
    from app.services.auditoria_service import AuditoriaService
    from app.models.auditoria import TipoAuditoria

    role = current_user.get("role", "")
    if role != "ADMIN_GLOBAL":
        return

    header_id = request.headers.get("X-Estabelecimento-ID")
    if not header_id:
        return

    try:
        est_id = int(header_id)
    except ValueError:
        return

    ip = request.client.host if request.client else None
    service = AuditoriaService(db)
    await service.registrar(
        acao=TipoAuditoria.ACESSO_CLINICA,
        usuario_id=int(current_user.get("sub", 0)),
        usuario_role=role,
        estabelecimento_id=est_id,
        detalhes={"path": str(request.url.path), "method": request.method},
        ip_origem=ip,
    )
