from datetime import date, datetime

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base


class ClienteConvenio(Base):
    """Carteirinha de convênio de um cliente.
    Um cliente pode ter múltiplas carteirinhas ativas.
    Apenas uma deve ter principal=True por cliente.
    """
    __tablename__ = "cliente_convenios"

    id: Mapped[int] = mapped_column(primary_key=True)
    cliente_id: Mapped[int] = mapped_column(
        ForeignKey("clientes.id", ondelete="CASCADE"), nullable=False, index=True
    )
    convenio_id: Mapped[int] = mapped_column(
        ForeignKey("convenios.id"), nullable=False, index=True
    )
    plano_id: Mapped[int | None] = mapped_column(
        ForeignKey("convenio_planos.id"), nullable=True
    )
    numero_carteirinha: Mapped[str] = mapped_column(String(50), nullable=False)
    nome_titular: Mapped[str | None] = mapped_column(String(200), nullable=True)
    validade: Mapped[date | None] = mapped_column(Date, nullable=True)
    principal: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    ativo: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    cliente: Mapped["Cliente"] = relationship()  # noqa: F821
    convenio: Mapped["Convenio"] = relationship()  # noqa: F821
    plano: Mapped["ConvenioPlano"] = relationship()  # noqa: F821
