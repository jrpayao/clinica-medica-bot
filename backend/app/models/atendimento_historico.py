"""Model SQLAlchemy 2.0 — AtendimentoStatusHistorico.

Registra cada transição de status de um atendimento.
O campo `atendimentos.status` é sempre o espelho do último registro desta tabela.
"""

from datetime import datetime

from sqlalchemy import DateTime, Enum, ForeignKey, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base
from app.models.atendimento import AtendimentoStatus


class AtendimentoStatusHistorico(Base):
    __tablename__ = "atendimento_status_historico"

    id: Mapped[int] = mapped_column(primary_key=True)
    atendimento_id: Mapped[int] = mapped_column(
        ForeignKey("atendimentos.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    status_anterior: Mapped[AtendimentoStatus | None] = mapped_column(
        Enum(AtendimentoStatus, name="atendimento_status", create_type=False),
        nullable=True,
    )
    status_novo: Mapped[AtendimentoStatus] = mapped_column(
        Enum(AtendimentoStatus, name="atendimento_status", create_type=False),
        nullable=False,
    )
    usuario_id: Mapped[int | None] = mapped_column(
        ForeignKey("usuarios.id", ondelete="SET NULL"), nullable=True
    )
    observacao: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    atendimento: Mapped["Atendimento"] = relationship(back_populates="historico")  # noqa: F821
