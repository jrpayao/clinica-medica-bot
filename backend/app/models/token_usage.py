import enum
from datetime import datetime
from decimal import Decimal

from sqlalchemy import DateTime, Enum, ForeignKey, Integer, Numeric, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class TokenFeature(str, enum.Enum):
    TRIAGEM = "TRIAGEM"
    AGENDAMENTO = "AGENDAMENTO"
    RAG = "RAG"
    RESUMO = "RESUMO"
    GERAL = "GERAL"


class TokenUsage(Base):
    __tablename__ = "token_usage"

    id: Mapped[int] = mapped_column(primary_key=True)
    session_id: Mapped[int] = mapped_column(
        ForeignKey("sessoes_chat.id"), nullable=False
    )
    # Desnormalização: estabelecimento_id direto para queries de billing eficientes.
    # Nullable para retrocompatibilidade com registros históricos sem estabelecimento.
    estabelecimento_id: Mapped[int | None] = mapped_column(
        ForeignKey("estabelecimentos.id"),
        nullable=True,
        index=True,
    )
    modelo: Mapped[str] = mapped_column(String(100), nullable=False)
    feature: Mapped[TokenFeature] = mapped_column(
        Enum(TokenFeature, name="token_feature"),
        nullable=False,
    )
    prompt_tokens: Mapped[int] = mapped_column(Integer, nullable=False)
    completion_tokens: Mapped[int] = mapped_column(Integer, nullable=False)
    total_tokens: Mapped[int] = mapped_column(Integer, nullable=False)
    cost_usd: Mapped[Decimal] = mapped_column(Numeric(10, 6), nullable=False)
    user_type: Mapped[str] = mapped_column(String(20), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
