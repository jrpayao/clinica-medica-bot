"""Model SQLAlchemy 2.0 — AuditoriaAcao (log de ações administrativas)."""

import enum
from datetime import datetime

from sqlalchemy import DateTime, Enum, ForeignKey, Integer, String, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class TipoAuditoria(str, enum.Enum):
    ACESSO_CLINICA   = "ACESSO_CLINICA"
    LICENCA_ALTERADA = "LICENCA_ALTERADA"
    ESTAB_ALTERADO   = "ESTAB_ALTERADO"
    USUARIO_ALTERADO = "USUARIO_ALTERADO"
    LOGIN            = "LOGIN"
    LOGOUT           = "LOGOUT"


class AuditoriaAcao(Base):
    __tablename__ = "auditoria_acoes"

    id: Mapped[int] = mapped_column(primary_key=True)
    usuario_id: Mapped[int] = mapped_column(
        ForeignKey("usuarios.id"), nullable=False, index=True
    )
    usuario_role: Mapped[str] = mapped_column(String(50), nullable=False)
    acao: Mapped[TipoAuditoria] = mapped_column(
        Enum(TipoAuditoria, name="tipo_auditoria", create_constraint=True),
        nullable=False,
        index=True,
    )
    estabelecimento_id: Mapped[int | None] = mapped_column(
        ForeignKey("estabelecimentos.id"), nullable=True, index=True
    )
    entidade: Mapped[str | None] = mapped_column(String(50), nullable=True)
    entidade_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    detalhes: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    ip_origem: Mapped[str | None] = mapped_column(String(45), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
        index=True,
    )
