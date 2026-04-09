import enum
from datetime import date, datetime, time

from sqlalchemy import Date, DateTime, Enum, ForeignKey, String, Time, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base


class SlotStatus(str, enum.Enum):
    DISPONIVEL = "DISPONIVEL"
    BLOQUEADO = "BLOQUEADO"
    AGENDADO = "AGENDADO"
    ENCAIXE = "ENCAIXE"
    RESERVADO = "RESERVADO"


class Slot(Base):
    __tablename__ = "slots"

    id: Mapped[int] = mapped_column(primary_key=True)
    profissional_id: Mapped[int] = mapped_column(ForeignKey("profissionais.id"), nullable=False)
    data: Mapped[date] = mapped_column(Date, nullable=False)
    hora_inicio: Mapped[time] = mapped_column(Time, nullable=False)
    hora_fim: Mapped[time] = mapped_column(Time, nullable=False)
    status: Mapped[SlotStatus] = mapped_column(
        Enum(SlotStatus, name="slot_status"),
        default=SlotStatus.DISPONIVEL,
        nullable=False,
    )
    motivo_bloqueio: Mapped[str | None] = mapped_column(String(500), nullable=True)
    reservado_em: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    estabelecimento_id: Mapped[int] = mapped_column(
        ForeignKey("estabelecimentos.id"), nullable=False, index=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    profissional: Mapped["Profissional"] = relationship(back_populates="slots")  # noqa: F821
