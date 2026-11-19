"""Model ReagendamentoOferta — novos horários oferecidos após cancelamento pela unidade (T96–T98)."""

import enum
from datetime import datetime

from sqlalchemy import DateTime, Enum, ForeignKey, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class ReagendamentoStatus(str, enum.Enum):
    PENDENTE = "PENDENTE"          # opções enviadas, aguardando resposta do cliente
    ACEITA = "ACEITA"              # cliente escolheu um horário e foi reagendado
    RECUSADA = "RECUSADA"          # cliente respondeu que não quer nenhum dos horários
    EXPIRADA = "EXPIRADA"          # sem resposta no prazo
    SEM_HORARIO = "SEM_HORARIO"    # não havia horário para oferecer
    SEM_CONTATO = "SEM_CONTATO"    # cliente sem telefone ou envio falhou
    RESOLVIDA = "RESOLVIDA"        # recepção tratou manualmente


# Situações em que a recepção precisa falar com o cliente
STATUS_QUE_PEDEM_CONTATO = (
    ReagendamentoStatus.RECUSADA,
    ReagendamentoStatus.EXPIRADA,
    ReagendamentoStatus.SEM_HORARIO,
    ReagendamentoStatus.SEM_CONTATO,
)


class ReagendamentoOferta(Base):
    __tablename__ = "reagendamento_ofertas"

    id: Mapped[int] = mapped_column(primary_key=True)
    atendimento_id: Mapped[int] = mapped_column(
        ForeignKey("atendimentos.id", ondelete="CASCADE"), nullable=False, index=True
    )
    cliente_id: Mapped[int] = mapped_column(ForeignKey("clientes.id"), nullable=False)
    estabelecimento_id: Mapped[int] = mapped_column(
        ForeignKey("estabelecimentos.id"), nullable=False, index=True
    )
    slot_ids: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    status: Mapped[ReagendamentoStatus] = mapped_column(
        Enum(ReagendamentoStatus, name="reagendamento_status"),
        default=ReagendamentoStatus.PENDENTE,
        nullable=False,
    )
    novo_atendimento_id: Mapped[int | None] = mapped_column(
        ForeignKey("atendimentos.id", ondelete="SET NULL"), nullable=True
    )
    enviado_em: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    respondido_em: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
