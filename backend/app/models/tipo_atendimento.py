"""Models SQLAlchemy 2.0 — TipoAtendimento e ProfissionalTipoAtendimento.

TipoAtendimento: catálogo de serviços por estabelecimento.
  Ex: "Botox", "Limpeza de Pele", "Consulta de Retorno"

ProfissionalTipoAtendimento: junction N:N — quais serviços um profissional oferece.
"""

from datetime import datetime
from decimal import Decimal

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, Numeric, String, Table, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base

# Tabela de associação N:N (sem model próprio — apenas chaves)
profissional_tipo_atendimentos = Table(
    "profissional_tipo_atendimentos",
    Base.metadata,
    Column("profissional_id", Integer, ForeignKey("profissionais.id", ondelete="CASCADE"), primary_key=True),
    Column("tipo_atendimento_id", Integer, ForeignKey("tipo_atendimentos.id", ondelete="CASCADE"), primary_key=True),
)


class TipoAtendimento(Base):
    __tablename__ = "tipo_atendimentos"

    id: Mapped[int] = mapped_column(primary_key=True)
    estabelecimento_id: Mapped[int] = mapped_column(
        ForeignKey("estabelecimentos.id", ondelete="CASCADE"), nullable=False, index=True
    )
    nome: Mapped[str] = mapped_column(String(100), nullable=False)
    descricao: Mapped[str | None] = mapped_column(Text, nullable=True)
    duracao_min: Mapped[int] = mapped_column(Integer, default=30, nullable=False)
    preco: Mapped[Decimal | None] = mapped_column(Numeric(10, 2), nullable=True)
    ativo: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    profissionais: Mapped[list["Profissional"]] = relationship(  # noqa: F821
        secondary=profissional_tipo_atendimentos,
        back_populates="tipos_atendimento",
    )
