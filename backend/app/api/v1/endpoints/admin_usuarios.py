"""Endpoints de gestão de usuários internos por estabelecimento (T136).

POST  /v1/admin/usuarios      — criar RECEPCIONISTA ou MEDICO
GET   /v1/admin/usuarios      — listar usuários do estabelecimento
PATCH /v1/admin/usuarios/{id} — atualizar dados / desativar
"""

from typing import Annotated

import structlog
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.dependencies import require_estabelecimento, require_role
from app.core.database import get_db
from app.core.security import hash_password
from app.models.usuario import Usuario, UsuarioRole

log = structlog.get_logger(__name__)

router = APIRouter(prefix="/admin/usuarios", tags=["Admin Usuários"])

_ROLES_PERMITIDOS_CRIAR = {"RECEPCIONISTA", "MEDICO"}


def _validar_role_permitido(role: str) -> bool:
    """ADMIN_ESTABELECIMENTO só pode criar RECEPCIONISTA ou MEDICO."""
    return role in _ROLES_PERMITIDOS_CRIAR


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------


class UsuarioCreateSchema(BaseModel):
    nome: str = Field(min_length=2, max_length=200)
    email: EmailStr
    senha: str = Field(min_length=8)
    role: str = Field(pattern="^(RECEPCIONISTA|MEDICO)$")


class UsuarioUpdateSchema(BaseModel):
    nome: str | None = Field(None, min_length=2, max_length=200)
    ativo: bool | None = None


class UsuarioResponse(BaseModel):
    id: int
    nome: str
    email: str
    role: str
    ativo: bool
    estabelecimento_id: int | None

    model_config = {"from_attributes": True}


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.post(
    "/",
    response_model=UsuarioResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Criar usuário interno (RECEPCIONISTA ou MEDICO)",
)
async def criar_usuario(
    dados: UsuarioCreateSchema,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(require_role("ADMIN_ESTABELECIMENTO")),
    estabelecimento_id: Annotated[int, Depends(require_estabelecimento)] = ...,
) -> UsuarioResponse:
    """Cria um usuário RECEPCIONISTA ou MEDICO no estabelecimento do chamador.

    Somente ADMIN_ESTABELECIMENTO pode chamar este endpoint.
    O novo usuário fica vinculado ao mesmo estabelecimento_id do token.
    """
    if not _validar_role_permitido(dados.role):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Role '{dados.role}' não permitido. Use RECEPCIONISTA ou MEDICO.",
        )

    # Verificar e-mail duplicado
    stmt = select(Usuario).where(Usuario.email == dados.email)
    resultado = await db.execute(stmt)
    if resultado.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="E-mail já cadastrado.",
        )

    novo_usuario = Usuario(
        nome=dados.nome,
        email=dados.email,
        senha_hash=hash_password(dados.senha),
        role=UsuarioRole(dados.role),
        estabelecimento_id=estabelecimento_id,
        ativo=True,
    )
    db.add(novo_usuario)
    await db.commit()
    await db.refresh(novo_usuario)

    log.info(
        "usuario_interno_criado",
        novo_usuario_id=novo_usuario.id,
        role=dados.role,
        estabelecimento_id=estabelecimento_id,
        criado_por=current_user.get("sub"),
    )
    return novo_usuario


@router.get(
    "/",
    response_model=list[UsuarioResponse],
    summary="Listar usuários do estabelecimento",
)
async def listar_usuarios(
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(require_role("ADMIN_ESTABELECIMENTO")),
    estabelecimento_id: Annotated[int, Depends(require_estabelecimento)] = ...,
) -> list[UsuarioResponse]:
    """Lista todos os usuários vinculados ao estabelecimento do chamador.

    Exclui o próprio ADMIN_ESTABELECIMENTO da listagem (gerencia subordinados).
    """
    stmt = (
        select(Usuario)
        .where(
            Usuario.estabelecimento_id == estabelecimento_id,
            Usuario.role.in_([UsuarioRole.RECEPCIONISTA, UsuarioRole.MEDICO]),
        )
        .order_by(Usuario.nome)
    )
    resultado = await db.execute(stmt)
    usuarios = list(resultado.scalars().all())

    log.info(
        "usuarios_listados",
        total=len(usuarios),
        estabelecimento_id=estabelecimento_id,
        solicitado_por=current_user.get("sub"),
    )
    return usuarios


@router.patch(
    "/{usuario_id}",
    response_model=UsuarioResponse,
    summary="Atualizar dados ou desativar usuário",
)
async def atualizar_usuario(
    usuario_id: int,
    dados: UsuarioUpdateSchema,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(require_role("ADMIN_ESTABELECIMENTO")),
    estabelecimento_id: Annotated[int, Depends(require_estabelecimento)] = ...,
) -> UsuarioResponse:
    """Atualiza nome e/ou status ativo de um usuário do estabelecimento.

    Garante isolamento: só permite editar usuários do mesmo estabelecimento_id.
    Impede editar ADMIN_GLOBAL ou ADMIN_ESTABELECIMENTO.
    """
    stmt = select(Usuario).where(
        Usuario.id == usuario_id,
        Usuario.estabelecimento_id == estabelecimento_id,
    )
    resultado = await db.execute(stmt)
    usuario = resultado.scalar_one_or_none()

    if not usuario:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Usuário não encontrado neste estabelecimento.",
        )

    if not _validar_role_permitido(usuario.role.value):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Não é permitido editar usuários com este role.",
        )

    if dados.nome is not None:
        usuario.nome = dados.nome
    if dados.ativo is not None:
        usuario.ativo = dados.ativo

    await db.commit()
    await db.refresh(usuario)

    log.info(
        "usuario_interno_atualizado",
        usuario_id=usuario_id,
        alteracoes=dados.model_dump(exclude_none=True),
        estabelecimento_id=estabelecimento_id,
        alterado_por=current_user.get("sub"),
    )
    return usuario
