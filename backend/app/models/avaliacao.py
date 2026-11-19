"""Model Avaliacao — nota do cliente após o atendimento (T99)."""

import enum
from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, Enum, ForeignKey, Integer, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class AvaliacaoCanal(str, enum.Enum):
    WHATSAPP = "WHATSAPP"
    PORTAL = "PORTAL"


class Avaliacao(Base):
    __tablename__ = "avaliacoes"
    __table_args__ = (CheckConstraint("nota BETWEEN 1 AND 5", name="ck_avaliacoes_nota"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    atendimento_id: Mapped[int] = mapped_column(
        ForeignKey("atendimentos.id", ondelete="CASCADE"), unique=True, nullable=False
    )
    cliente_id: Mapped[int] = mapped_column(ForeignKey("clientes.id"), nullable=False, index=True)
    profissional_id: Mapped[int] = mapped_column(
        ForeignKey("profissionais.id"), nullable=False, index=True
    )
    estabelecimento_id: Mapped[int] = mapped_column(
        ForeignKey("estabelecimentos.id"), nullable=False, index=True
    )
    nota: Mapped[int] = mapped_column(Integer, nullable=False)
    comentario: Mapped[str | None] = mapped_column(Text, nullable=True)
    canal: Mapped[AvaliacaoCanal] = mapped_column(
        Enum(AvaliacaoCanal, name="avaliacao_canal"), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
