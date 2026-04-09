"""Model SQLAlchemy 2.0 — MedicoEstabelecimento (junction N:N).

Resolve o relacionamento muitos-para-muitos entre Medico e EstabelecimentoSaude.

Casos de uso cobertos:
- Médico que atende em múltiplas unidades da mesma rede
- Médico freelancer que presta serviços em estabelecimentos independentes
- Médico com duração de consulta diferente por unidade (ex: 30min no hospital, 45min na clínica)

Ciclo de vida:
- `ativo=False` desativa o médico naquele estabelecimento sem remover o histórico de consultas
"""

from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base


class MedicoEstabelecimento(Base):
    """Vínculo entre um médico e um estabelecimento de saúde."""

    __tablename__ = "medico_estabelecimentos"
    __table_args__ = (
        UniqueConstraint(
            "medico_id",
            "estabelecimento_id",
            name="uq_medico_estabelecimento",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    medico_id: Mapped[int] = mapped_column(
        ForeignKey("medicos.id"), nullable=False, index=True
    )
    estabelecimento_id: Mapped[int] = mapped_column(
        ForeignKey("estabelecimentos.id"), nullable=False, index=True
    )
    duracao_consulta_min: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=30,
        comment="Pode variar por unidade (ex: 30min no hospital, 45min na clinica)",
    )
    ativo: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    medico: Mapped["Medico"] = relationship(back_populates="estabelecimento_vinculos")  # noqa: F821
    estabelecimento: Mapped["EstabelecimentoSaude"] = relationship(  # noqa: F821
        back_populates="medico_vinculos"
    )
