import enum
from datetime import date, datetime

from sqlalchemy import Boolean, Date, DateTime, Enum, ForeignKey, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class TipoAtendimento(str, enum.Enum):
    CONVENIO = "CONVENIO"
    PARTICULAR = "PARTICULAR"


class Paciente(Base):
    __tablename__ = "pacientes"

    id: Mapped[int] = mapped_column(primary_key=True)
    cpf: Mapped[str] = mapped_column(String(11), index=True, nullable=False)
    nome: Mapped[str] = mapped_column(String(200), nullable=False)
    data_nascimento: Mapped[date | None] = mapped_column(Date, nullable=True)
    telefone: Mapped[str | None] = mapped_column(String(20), nullable=True)
    email: Mapped[str | None] = mapped_column(String(254), nullable=True)
    convenio: Mapped[str | None] = mapped_column(String(100), nullable=True)
    numero_carteirinha: Mapped[str | None] = mapped_column(String(50), nullable=True)
    tipo_atendimento: Mapped[TipoAtendimento | None] = mapped_column(
        Enum(TipoAtendimento, name="tipo_atendimento"), nullable=True
    )
    convenio_id: Mapped[int | None] = mapped_column(
        ForeignKey("convenios.id"), nullable=True, index=True
    )
    ativo: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    estabelecimento_id: Mapped[int] = mapped_column(
        ForeignKey("estabelecimentos.id"), nullable=False, index=True
    )
