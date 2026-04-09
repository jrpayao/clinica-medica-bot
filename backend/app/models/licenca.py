"""Model SQLAlchemy 2.0 — Licenca (ciclo de vida da assinatura do tenant).

Cada EstabelecimentoSaude possui exatamente uma Licenca ativa.
A licença é criada automaticamente em status TRIAL ao criar o estabelecimento.

Ciclo de vida:
  TRIAL (14 dias) → ATIVA (após ativação manual pelo ADMIN_GLOBAL)
  ATIVA → EXPIRADA (licenca_expira_em ultrapassada)
  ATIVA | TRIAL → SUSPENSA (bloqueio manual pelo ADMIN_GLOBAL)
  SUSPENSA → ATIVA (reativação manual)
"""

import enum
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin


class LicencaStatus(str, enum.Enum):
    TRIAL = "TRIAL"        # criado automaticamente, 14 dias grátis
    ATIVA = "ATIVA"        # ativado manualmente pelo ADMIN_GLOBAL
    EXPIRADA = "EXPIRADA"  # trial ou licença vencida
    SUSPENSA = "SUSPENSA"  # bloqueio manual pelo ADMIN_GLOBAL


class Licenca(Base, TimestampMixin):
    __tablename__ = "licencas"

    id: Mapped[int] = mapped_column(primary_key=True)

    # Tenant — 1:1 com estabelecimento
    estabelecimento_id: Mapped[int] = mapped_column(
        ForeignKey("estabelecimentos.id"),
        nullable=False,
        unique=True,
        index=True,
    )

    # Plano contratado (cache sincronizado ao ativar plano)
    plano: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="basico",
        server_default="basico",
    )

    status: Mapped[LicencaStatus] = mapped_column(
        Enum(LicencaStatus, name="licenca_status"),
        nullable=False,
        default=LicencaStatus.TRIAL,
        server_default="TRIAL",
    )

    # "mensal" | "anual" — informativo, usado ao calcular licenca_expira_em
    modalidade: Mapped[str] = mapped_column(
        String(10),
        nullable=False,
        default="mensal",
        server_default="mensal",
    )

    # Datas de validade
    trial_expira_em: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    licenca_expira_em: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # Controle manual pelo ADMIN_GLOBAL
    suspensa_por: Mapped[int | None] = mapped_column(
        ForeignKey("usuarios.id"), nullable=True
    )
    suspensa_em: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    motivo_suspensao: Mapped[str | None] = mapped_column(String(500), nullable=True)

    # Reservados para integração futura com gateway de pagamento
    gateway_customer_id: Mapped[str | None] = mapped_column(
        String(100), nullable=True, index=True
    )
    gateway_subscription_id: Mapped[str | None] = mapped_column(
        String(100), nullable=True, index=True
    )

    estabelecimento: Mapped["EstabelecimentoSaude"] = relationship(  # noqa: F821
        back_populates="licenca"
    )
