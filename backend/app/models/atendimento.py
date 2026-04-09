import enum

from sqlalchemy import Enum, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin


class AtendimentoTipo(str, enum.Enum):
    EXTERNO  = "EXTERNO"
    INTERNO  = "INTERNO"
    ENCAIXE  = "ENCAIXE"
    RETORNO  = "RETORNO"


class AtendimentoStatus(str, enum.Enum):
    AGENDADA              = "AGENDADA"
    CONFIRMADA            = "CONFIRMADA"
    CANCELADA             = "CANCELADA"
    PRESENTE              = "PRESENTE"
    AGUARDANDO_ANAMNESE   = "AGUARDANDO_ANAMNESE"
    ANAMNESE_PREENCHIDA   = "ANAMNESE_PREENCHIDA"
    FICHA_CONCLUIDA       = "FICHA_CONCLUIDA"
    AGUARDANDO_PAGAMENTO  = "AGUARDANDO_PAGAMENTO"
    PAGO                  = "PAGO"
    AGUARDANDO_PROFISSIONAL = "AGUARDANDO_PROFISSIONAL"
    EM_ATENDIMENTO        = "EM_ATENDIMENTO"
    REALIZADA             = "REALIZADA"
    FALTA                 = "FALTA"


class AtendimentoUrgencia(str, enum.Enum):
    BAIXA      = "BAIXA"
    MEDIA      = "MEDIA"
    ALTA       = "ALTA"
    EMERGENCIA = "EMERGENCIA"


class AtendimentoCanal(str, enum.Enum):
    PORTAL    = "PORTAL"
    WHATSAPP  = "WHATSAPP"
    INTERNO   = "INTERNO"


class Atendimento(Base, TimestampMixin):
    __tablename__ = "atendimentos"

    id: Mapped[int] = mapped_column(primary_key=True)
    slot_id: Mapped[int] = mapped_column(ForeignKey("slots.id"), nullable=False)
    cliente_id: Mapped[int] = mapped_column(ForeignKey("clientes.id"), nullable=False)
    profissional_id: Mapped[int] = mapped_column(ForeignKey("profissionais.id"), nullable=False)
    especialidade_id: Mapped[int] = mapped_column(
        ForeignKey("especialidades.id"), nullable=False
    )
    tipo: Mapped[AtendimentoTipo] = mapped_column(
        Enum(AtendimentoTipo, name="atendimento_tipo"),
        nullable=False,
    )
    status: Mapped[AtendimentoStatus] = mapped_column(
        Enum(AtendimentoStatus, name="atendimento_status"),
        default=AtendimentoStatus.AGENDADA,
        nullable=False,
    )
    triagem_resumo: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    urgencia: Mapped[AtendimentoUrgencia] = mapped_column(
        Enum(AtendimentoUrgencia, name="atendimento_urgencia"),
        default=AtendimentoUrgencia.BAIXA,
        nullable=False,
    )
    canal_origem: Mapped[AtendimentoCanal] = mapped_column(
        Enum(AtendimentoCanal, name="atendimento_canal"),
        nullable=False,
    )
    observacoes: Mapped[str | None] = mapped_column(Text, nullable=True)
    cliente_convenio_id: Mapped[int | None] = mapped_column(
        ForeignKey("cliente_convenios.id", ondelete="SET NULL"), nullable=True
    )
    numero_autorizacao: Mapped[str | None] = mapped_column(String(50), nullable=True)
    estabelecimento_id: Mapped[int] = mapped_column(
        ForeignKey("estabelecimentos.id"), nullable=False, index=True
    )

    slot: Mapped["Slot"] = relationship()  # noqa: F821
    cliente: Mapped["Cliente"] = relationship()  # noqa: F821
    profissional: Mapped["Profissional"] = relationship()  # noqa: F821
    especialidade: Mapped["Especialidade"] = relationship()  # noqa: F821
    cliente_convenio: Mapped["ClienteConvenio | None"] = relationship()  # noqa: F821
    historico: Mapped[list["AtendimentoStatusHistorico"]] = relationship(  # noqa: F821
        back_populates="atendimento", order_by="AtendimentoStatusHistorico.created_at"
    )
