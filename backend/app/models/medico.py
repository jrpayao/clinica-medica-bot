"""Model SQLAlchemy 2.0 — Medico.

Médico pertence a uma especialidade (1:1) e pode atender em múltiplos
estabelecimentos de saúde via MedicoEstabelecimento (N:N).

`duracao_consulta_min` aqui é o padrão global do médico.
Pode ser sobrescrito por unidade em MedicoEstabelecimento.duracao_consulta_min.
"""

from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base


class Medico(Base):
    __tablename__ = "medicos"

    id: Mapped[int] = mapped_column(primary_key=True)
    crm: Mapped[str] = mapped_column(String(20), unique=True, nullable=False)
    nome: Mapped[str] = mapped_column(String(200), nullable=False)
    especialidade_id: Mapped[int] = mapped_column(
        ForeignKey("especialidades.id"), nullable=False
    )
    email: Mapped[str | None] = mapped_column(String(254), nullable=True)
    telefone: Mapped[str | None] = mapped_column(String(20), nullable=True)
    duracao_consulta_min: Mapped[int] = mapped_column(
        Integer,
        default=30,
        nullable=False,
        comment="Duração padrão global. Pode variar por unidade em MedicoEstabelecimento.",
    )
    ativo: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    especialidade: Mapped["Especialidade"] = relationship(back_populates="medicos")  # noqa: F821
    slots: Mapped[list["Slot"]] = relationship(back_populates="medico")  # noqa: F821
    estabelecimento_vinculos: Mapped[list["MedicoEstabelecimento"]] = relationship(  # noqa: F821
        back_populates="medico"
    )
