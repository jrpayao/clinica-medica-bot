from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base


class ConvenioPlano(Base):
    __tablename__ = "convenio_planos"

    id: Mapped[int] = mapped_column(primary_key=True)
    convenio_id: Mapped[int] = mapped_column(
        ForeignKey("convenios.id", ondelete="CASCADE"), nullable=False, index=True
    )
    nome: Mapped[str] = mapped_column(String(100), nullable=False)
    ativo: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    convenio: Mapped["Convenio"] = relationship(back_populates="planos")  # noqa: F821
