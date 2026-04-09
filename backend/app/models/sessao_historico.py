"""Model SessaoHistorico — Histórico clínico de triagens anteriores (T86)."""

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class SessaoHistorico(Base):
    __tablename__ = "sessoes_historico"

    id: Mapped[int] = mapped_column(primary_key=True)
    cliente_id: Mapped[int] = mapped_column(
        ForeignKey("clientes.id"), nullable=False, index=True
    )
    sessao_id: Mapped[int | None] = mapped_column(
        ForeignKey("sessoes_chat.id"), nullable=True
    )
    sintomas_relatados: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    especialidade_sugerida: Mapped[str | None] = mapped_column(String(100), nullable=True)
    urgencia: Mapped[str | None] = mapped_column(String(50), nullable=True)
    resumo_triagem: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
