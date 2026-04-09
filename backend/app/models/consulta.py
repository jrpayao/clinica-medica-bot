import enum

from sqlalchemy import Enum, ForeignKey, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin


class ConsultaTipo(str, enum.Enum):
    EXTERNO = "EXTERNO"
    INTERNO = "INTERNO"
    ENCAIXE = "ENCAIXE"
    RETORNO = "RETORNO"


class ConsultaStatus(str, enum.Enum):
    AGENDADA = "AGENDADA"
    CONFIRMADA = "CONFIRMADA"
    CANCELADA = "CANCELADA"
    REALIZADA = "REALIZADA"
    FALTA = "FALTA"


class ConsultaUrgencia(str, enum.Enum):
    BAIXA = "BAIXA"
    MEDIA = "MEDIA"
    ALTA = "ALTA"
    EMERGENCIA = "EMERGENCIA"


class ConsultaCanal(str, enum.Enum):
    PORTAL = "PORTAL"
    WHATSAPP = "WHATSAPP"
    INTERNO = "INTERNO"


class Consulta(Base, TimestampMixin):
    __tablename__ = "consultas"

    id: Mapped[int] = mapped_column(primary_key=True)
    slot_id: Mapped[int] = mapped_column(ForeignKey("slots.id"), nullable=False)
    paciente_id: Mapped[int] = mapped_column(ForeignKey("pacientes.id"), nullable=False)
    medico_id: Mapped[int] = mapped_column(ForeignKey("medicos.id"), nullable=False)
    especialidade_id: Mapped[int] = mapped_column(
        ForeignKey("especialidades.id"), nullable=False
    )
    tipo: Mapped[ConsultaTipo] = mapped_column(
        Enum(ConsultaTipo, name="consulta_tipo"),
        nullable=False,
    )
    status: Mapped[ConsultaStatus] = mapped_column(
        Enum(ConsultaStatus, name="consulta_status"),
        default=ConsultaStatus.AGENDADA,
        nullable=False,
    )
    triagem_resumo: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    urgencia: Mapped[ConsultaUrgencia] = mapped_column(
        Enum(ConsultaUrgencia, name="consulta_urgencia"),
        default=ConsultaUrgencia.BAIXA,
        nullable=False,
    )
    canal_origem: Mapped[ConsultaCanal] = mapped_column(
        Enum(ConsultaCanal, name="consulta_canal"),
        nullable=False,
    )
    observacoes: Mapped[str | None] = mapped_column(Text, nullable=True)
    estabelecimento_id: Mapped[int] = mapped_column(
        ForeignKey("estabelecimentos.id"), nullable=False, index=True
    )

    slot: Mapped["Slot"] = relationship()  # noqa: F821
    paciente: Mapped["Paciente"] = relationship()  # noqa: F821
    medico: Mapped["Medico"] = relationship()  # noqa: F821
    especialidade: Mapped["Especialidade"] = relationship()  # noqa: F821
