"""Model SQLAlchemy 2.0 — EstabelecimentoSaude (tenant raiz do sistema).

Cada estabelecimento é um cliente independente da plataforma MedBot.
Pode ser um hospital, clínica, UBS, laboratório ou posto de saúde.

Isolamento de dados:
- Todos os recursos de domínio (pacientes, slots, consultas) carregam
  `estabelecimento_id` para garantir que cada cliente veja apenas os seus dados.

Multi-unidade:
- Estabelecimentos da mesma organização podem ser agrupados via `rede_id`.
- Médicos podem atender em múltiplos estabelecimentos via MedicoEstabelecimento.
"""

import enum
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base


class TipoEstabelecimento(str, enum.Enum):
    HOSPITAL = "HOSPITAL"
    CLINICA = "CLINICA"
    UBS = "UBS"
    LABORATORIO = "LABORATORIO"
    POSTO_SAUDE = "POSTO_SAUDE"
    OUTRO = "OUTRO"


class EstabelecimentoSaude(Base):
    __tablename__ = "estabelecimentos"

    id: Mapped[int] = mapped_column(primary_key=True)
    nome: Mapped[str] = mapped_column(String(200), nullable=False)
    cnpj: Mapped[str] = mapped_column(String(14), unique=True, nullable=False)
    slug: Mapped[str] = mapped_column(String(100), unique=True, nullable=False, index=True)
    tipo: Mapped[TipoEstabelecimento] = mapped_column(
        Enum(TipoEstabelecimento, name="tipo_estabelecimento"),
        nullable=False,
    )
    plano: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="basico",
        server_default="basico",
    )
    ativo: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    # Contato do estabelecimento
    email: Mapped[str | None] = mapped_column(String(254), nullable=True)
    telefone: Mapped[str | None] = mapped_column(String(20), nullable=True)
    endereco: Mapped[str | None] = mapped_column(String(500), nullable=True)
    cidade: Mapped[str | None] = mapped_column(String(100), nullable=True)
    estado: Mapped[str | None] = mapped_column(String(2), nullable=True)
    cep: Mapped[str | None] = mapped_column(String(8), nullable=True)

    # Responsável legal
    responsavel_nome: Mapped[str | None] = mapped_column(String(200), nullable=True)
    responsavel_cpf: Mapped[str | None] = mapped_column(String(11), nullable=True)
    responsavel_email: Mapped[str | None] = mapped_column(String(254), nullable=True)
    responsavel_telefone: Mapped[str | None] = mapped_column(String(20), nullable=True)
    responsavel_cargo: Mapped[str | None] = mapped_column(String(100), nullable=True)

    # Rede/holding — opcional. None = estabelecimento independente
    rede_id: Mapped[int | None] = mapped_column(
        ForeignKey("redes_estabelecimentos.id"),
        nullable=True,
        index=True,
    )

    rede: Mapped["RedeEstabelecimentos | None"] = relationship(  # noqa: F821
        back_populates="estabelecimentos"
    )
    profissional_vinculos: Mapped[list["ProfissionalEstabelecimento"]] = relationship(  # noqa: F821
        back_populates="estabelecimento"
    )
    licenca: Mapped["Licenca | None"] = relationship(  # noqa: F821
        back_populates="estabelecimento", uselist=False
    )
