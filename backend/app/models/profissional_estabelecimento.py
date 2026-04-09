"""Model SQLAlchemy 2.0 — ProfissionalEstabelecimento (junction N:N).

Resolve o relacionamento muitos-para-muitos entre Profissional e EstabelecimentoSaude.
"""

from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base


class ProfissionalEstabelecimento(Base):
    __tablename__ = "profissional_estabelecimentos"
    __table_args__ = (
        UniqueConstraint(
            "profissional_id",
            "estabelecimento_id",
            name="uq_profissional_estabelecimento",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    profissional_id: Mapped[int] = mapped_column(
        ForeignKey("profissionais.id"), nullable=False, index=True
    )
    estabelecimento_id: Mapped[int] = mapped_column(
        ForeignKey("estabelecimentos.id"), nullable=False, index=True
    )
    duracao_atendimento_min: Mapped[int] = mapped_column(
        Integer, nullable=False, default=30,
    )
    ativo: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False,
    )

    profissional: Mapped["Profissional"] = relationship(back_populates="estabelecimento_vinculos")  # noqa: F821
    estabelecimento: Mapped["EstabelecimentoSaude"] = relationship(  # noqa: F821
        back_populates="profissional_vinculos"
    )
