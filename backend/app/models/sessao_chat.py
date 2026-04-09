import enum
from datetime import datetime

from sqlalchemy import DateTime, Enum, ForeignKey, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class SessaoCanal(str, enum.Enum):
    PORTAL = "PORTAL"
    WHATSAPP = "WHATSAPP"


class SessaoStatus(str, enum.Enum):
    ATIVA = "ATIVA"
    ENCERRADA = "ENCERRADA"
    AGENDOU = "AGENDOU"
    ABANDONOU = "ABANDONOU"


class SessaoChat(Base):
    __tablename__ = "sessoes_chat"

    id: Mapped[int] = mapped_column(primary_key=True)
    session_token: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    paciente_id: Mapped[int | None] = mapped_column(
        ForeignKey("pacientes.id"), nullable=True
    )
    canal: Mapped[SessaoCanal] = mapped_column(
        Enum(SessaoCanal, name="sessao_canal"),
        nullable=False,
    )
    status: Mapped[SessaoStatus] = mapped_column(
        Enum(SessaoStatus, name="sessao_status"),
        default=SessaoStatus.ATIVA,
        nullable=False,
    )
    modelo_ia_usado: Mapped[str | None] = mapped_column(String(100), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    encerrada_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    estabelecimento_id: Mapped[int] = mapped_column(
        ForeignKey("estabelecimentos.id"), nullable=False, index=True
    )
