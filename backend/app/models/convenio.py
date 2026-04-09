from sqlalchemy import Boolean, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin


class Convenio(Base, TimestampMixin):
    __tablename__ = "convenios"

    id: Mapped[int] = mapped_column(primary_key=True)
    nome: Mapped[str] = mapped_column(String(100), nullable=False)
    codigo_ans: Mapped[str | None] = mapped_column(String(20), nullable=True)
    cnpj: Mapped[str | None] = mapped_column(String(14), nullable=True)
    telefone_autorizacao: Mapped[str | None] = mapped_column(String(20), nullable=True)
    email: Mapped[str | None] = mapped_column(String(254), nullable=True)
    website: Mapped[str | None] = mapped_column(String(500), nullable=True)
    ativo: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    estabelecimento_id: Mapped[int] = mapped_column(
        ForeignKey("estabelecimentos.id"), nullable=False, index=True
    )

    planos: Mapped[list["ConvenioPlano"]] = relationship(  # noqa: F821
        back_populates="convenio", cascade="all, delete-orphan"
    )
