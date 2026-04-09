"""Model FilaEspera — Fila de espera inteligente (T89)."""

import enum
from datetime import datetime

from sqlalchemy import DateTime, Enum, ForeignKey, func
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class FilaEsperaStatus(str, enum.Enum):
    AGUARDANDO = "AGUARDANDO"
    NOTIFICADO = "NOTIFICADO"
    AGENDADO = "AGENDADO"
    CANCELADO = "CANCELADO"


class FilaEspera(Base):
    __tablename__ = "fila_espera"

    id: Mapped[int] = mapped_column(primary_key=True)
    cliente_id: Mapped[int] = mapped_column(
        ForeignKey("clientes.id"), nullable=False, index=True
    )
    estabelecimento_id: Mapped[int] = mapped_column(
        ForeignKey("estabelecimentos.id"), nullable=False, index=True
    )
    especialidade_id: Mapped[int | None] = mapped_column(
        ForeignKey("especialidades.id"), nullable=True
    )
    convenio_id: Mapped[int | None] = mapped_column(
        ForeignKey("convenios.id"), nullable=True
    )
    status: Mapped[FilaEsperaStatus] = mapped_column(
        Enum(FilaEsperaStatus, name="fila_espera_status"),
        default=FilaEsperaStatus.AGUARDANDO,
        nullable=False,
    )
    notificado_em: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
