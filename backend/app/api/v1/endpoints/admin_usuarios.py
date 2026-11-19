"""Endpoints de gestão de usuários internos por estabelecimento (T136).

POST  /v1/admin/usuarios      — criar RECEPCIONISTA ou MEDICO
GET   /v1/admin/usuarios      — listar usuários do estabelecimento (ADMIN_GLOBAL: toda a plataforma)
PATCH /v1/admin/usuarios/{id} — atualizar dados / desativar
"""

from typing import Annotated

import structlog
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, EmailStr, Field, model_validator
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.dependencies import (
    get_estabelecimento_id_opcional,
    require_estabelecimento,
    require_role,
)
from app.core.database import get_db
from app.core.security import hash_password
from app.models.estabelecimento import EstabelecimentoSaude
from app.models.profissional_estabelecimento import ProfissionalEstabelecimento
from app.models.usuario import Usuario, UsuarioRole

log = structlog.get_logger(__name__)

router = APIRouter(prefix="/admin/usuarios", tags=["Admin Usuários"])

_ROLES_PERMITIDOS_CRIAR = {"RECEPCIONISTA", "MEDICO"}


def _validar_role_permitido(role: str) -> bool:
    """ADMIN_ESTABELECIMENTO só pode criar RECEPCIONISTA ou MEDICO."""
    return role in _ROLES_PERMITIDOS_CRIAR


def _escopo_listagem(role: str, estabelecimento_id: int | None) -> tuple[int | None, bool]:
    """Define o que cada perfil enxerga na listagem de usuários.

    Retorna (filtro_estabelecimento_id, somente_subordinados):
    - ADMIN_ESTABELECIMENTO: só RECEPCIONISTA/MEDICO da própria unidade.
    - ADMIN_GLOBAL: todos os perfis; da unidade selecionada ou da plataforma inteira.
    """
    if role == "ADMIN_GLOBAL":
        return estabelecimento_id, False
    return estabelecimento_id, True


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------


class UsuarioCreateSchema(BaseModel):
    nome: str = Field(min_length=2, max_length=200)
    email: EmailStr
    senha: str = Field(min_length=8)
    role: str = Field(pattern="^(RECEPCIONISTA|MEDICO)$")
    profissional_id: int | None = Field(None, description="Obrigatório para MEDICO: profissional da agenda")

    @model_validator(mode="after")
    def validar_vinculo(self) -> "UsuarioCreateSchema":
        if self.role == "MEDICO" and self.profissional_id is None:
            raise ValueError("Informe o profissional da agenda ao qual este acesso pertence.")
        if self.role != "MEDICO":
            self.profissional_id = None
        return self


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
    estabelecimento_nome: str | None = None

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

    if dados.profissional_id is not None:
        vinculo = await db.execute(
            select(ProfissionalEstabelecimento.id).where(
                ProfissionalEstabelecimento.profissional_id == dados.profissional_id,
                ProfissionalEstabelecimento.estabelecimento_id == estabelecimento_id,
                ProfissionalEstabelecimento.ativo == True,  # noqa: E712
            )
        )
        if vinculo.scalar_one_or_none() is None:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Profissional não atende nesta unidade.",
            )
        ja_tem = await db.execute(
            select(Usuario.id).where(Usuario.profissional_id == dados.profissional_id)
        )
        if ja_tem.scalar_one_or_none() is not None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Este profissional já tem um acesso cadastrado.",
            )

    novo_usuario = Usuario(
        nome=dados.nome,
        email=dados.email,
        senha_hash=hash_password(dados.senha),
        role=UsuarioRole(dados.role),
        profissional_id=dados.profissional_id,
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
    summary="Listar usuários do estabelecimento (ou da plataforma, para ADMIN_GLOBAL)",
)
async def listar_usuarios(
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(require_role("ADMIN_ESTABELECIMENTO", "ADMIN_GLOBAL")),
    estabelecimento_id: Annotated[int | None, Depends(get_estabelecimento_id_opcional)] = None,
) -> list[UsuarioResponse]:
    """Lista usuários internos conforme o perfil do chamador.

    ADMIN_ESTABELECIMENTO vê os subordinados (RECEPCIONISTA/MEDICO) da própria unidade.
    ADMIN_GLOBAL vê todos os perfis — da unidade selecionada ou da plataforma inteira.
    """
    filtro_est_id, somente_subordinados = _escopo_listagem(
        current_user.get("role", ""), estabelecimento_id
    )

    stmt = (
        select(Usuario, EstabelecimentoSaude.nome)
        .outerjoin(EstabelecimentoSaude, EstabelecimentoSaude.id == Usuario.estabelecimento_id)
        .order_by(EstabelecimentoSaude.nome.nulls_first(), Usuario.nome)
    )
    if filtro_est_id is not None:
        stmt = stmt.where(Usuario.estabelecimento_id == filtro_est_id)
    if somente_subordinados:
        stmt = stmt.where(Usuario.role.in_([UsuarioRole.RECEPCIONISTA, UsuarioRole.MEDICO]))

    linhas = (await db.execute(stmt)).all()
    usuarios = [
        UsuarioResponse(
            id=usuario.id,
            nome=usuario.nome,
            email=usuario.email,
            role=usuario.role.value,
            ativo=usuario.ativo,
            estabelecimento_id=usuario.estabelecimento_id,
            estabelecimento_nome=est_nome,
        )
        for usuario, est_nome in linhas
    ]

    log.info(
        "usuarios_listados",
        total=len(usuarios),
        estabelecimento_id=filtro_est_id,
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
