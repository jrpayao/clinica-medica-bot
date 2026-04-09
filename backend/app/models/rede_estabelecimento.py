"""Model SQLAlchemy 2.0 — RedeEstabelecimentos (holding/rede de filiais).

Agrupa múltiplos estabelecimentos de saúde da mesma organização.
Ex: "Clínica Vida S/A" possui unidades na Asa Sul e Asa Norte.

Regras:
- Um estabelecimento pode pertencer a no máximo 1 rede (rede_id nullable)
- Estabelecimentos sem rede operam de forma completamente independente
- Recursos como médicos podem ser compartilhados entre unidades da mesma rede
"""

from datetime import datetime

from sqlalchemy import Boolean, DateTime, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base


class RedeEstabelecimentos(Base):
    __tablename__ = "redes_estabelecimentos"

    id: Mapped[int] = mapped_column(primary_key=True)
    nome: Mapped[str] = mapped_column(String(200), nullable=False)
    cnpj_holding: Mapped[str | None] = mapped_column(String(14), unique=True, nullable=True)
    ativo: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    estabelecimentos: Mapped[list["EstabelecimentoSaude"]] = relationship(  # noqa: F821
        back_populates="rede"
    )
