"""Model SQLAlchemy 2.0 — Usuario (usuários internos da plataforma).

Roles:
- ADMIN_GLOBAL: acessa todos os estabelecimentos (equipe da plataforma)
- ADMIN_ESTABELECIMENTO: admin de um único estabelecimento (cliente)
- RECEPCIONISTA: vinculada a 1 estabelecimento
- MEDICO: vinculado a 1 estabelecimento principal (pode atender em outros
  via MedicoEstabelecimento)
"""

import enum
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class UsuarioRole(str, enum.Enum):
    ADMIN_GLOBAL = "ADMIN_GLOBAL"            # plataforma — acessa N estabelecimentos
    ADMIN_ESTABELECIMENTO = "ADMIN_ESTABELECIMENTO"  # cliente — limitado a 1
    RECEPCIONISTA = "RECEPCIONISTA"
    MEDICO = "MEDICO"


class Usuario(Base):
    __tablename__ = "usuarios"

    id: Mapped[int] = mapped_column(primary_key=True)
    nome: Mapped[str] = mapped_column(String(200), nullable=False)
    email: Mapped[str] = mapped_column(String(254), unique=True, nullable=False)
    senha_hash: Mapped[str] = mapped_column(String(300), nullable=False)
    role: Mapped[UsuarioRole] = mapped_column(
        Enum(UsuarioRole, name="usuario_role", create_constraint=True),
        nullable=False,
    )
    profissional_id: Mapped[int | None] = mapped_column(
        ForeignKey("profissionais.id"), nullable=True
    )
    # Null somente para ADMIN_GLOBAL (acessa todos os estabelecimentos)
    estabelecimento_id: Mapped[int | None] = mapped_column(
        ForeignKey("estabelecimentos.id"), nullable=True, index=True
    )
    ativo: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
