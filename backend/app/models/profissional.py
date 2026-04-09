"""Model SQLAlchemy 2.0 — Profissional.

Profissional (médico, esteticista, dentista, etc.) pertence a uma especialidade
e pode atender em múltiplos estabelecimentos via ProfissionalEstabelecimento (N:N).

`duracao_atendimento_min` é o padrão global do profissional.
Pode ser sobrescrito por unidade em ProfissionalEstabelecimento.duracao_atendimento_min.
"""

from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base


class Profissional(Base):
    __tablename__ = "profissionais"

    id: Mapped[int] = mapped_column(primary_key=True)
    registro_profissional: Mapped[str] = mapped_column(String(20), unique=True, nullable=False)
    nome: Mapped[str] = mapped_column(String(200), nullable=False)
    especialidade_id: Mapped[int] = mapped_column(
        ForeignKey("especialidades.id"), nullable=False
    )
    email: Mapped[str | None] = mapped_column(String(254), nullable=True)
    telefone: Mapped[str | None] = mapped_column(String(20), nullable=True)
    duracao_atendimento_min: Mapped[int] = mapped_column(
        Integer,
        default=30,
        nullable=False,
        comment="Duração padrão global. Pode variar por unidade em ProfissionalEstabelecimento.",
    )
    ativo: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    especialidade: Mapped["Especialidade"] = relationship(back_populates="profissionais")  # noqa: F821
    slots: Mapped[list["Slot"]] = relationship(back_populates="profissional")  # noqa: F821
    estabelecimento_vinculos: Mapped[list["ProfissionalEstabelecimento"]] = relationship(  # noqa: F821
        back_populates="profissional"
    )
    tipos_atendimento: Mapped[list["TipoAtendimento"]] = relationship(  # noqa: F821
        secondary="profissional_tipo_atendimentos",
        back_populates="profissionais",
    )
