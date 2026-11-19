"""Models da telemedicina (G29): sala de teleconsulta, registro do atendimento e documentos clínicos."""

import enum
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, LargeBinary, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin


class Modalidade(str, enum.Enum):
    PRESENCIAL = "PRESENCIAL"
    ONLINE = "ONLINE"


class Teleconsulta(Base):
    """Sala de vídeo de um atendimento online.

    `token_paciente` é o segredo do link que o paciente recebe; `sala` é o nome da sala no servidor
    de vídeo e só é entregue ao paciente depois que o profissional inicia o atendimento.
    """

    __tablename__ = "teleconsultas"

    id: Mapped[int] = mapped_column(primary_key=True)
    atendimento_id: Mapped[int] = mapped_column(
        ForeignKey("atendimentos.id", ondelete="CASCADE"), unique=True, nullable=False
    )
    sala: Mapped[str] = mapped_column(String(80), unique=True, nullable=False)
    token_paciente: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    termo_versao: Mapped[str | None] = mapped_column(String(20), nullable=True)
    consentimento_em: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    consentimento_ip: Mapped[str | None] = mapped_column(String(64), nullable=True)
    paciente_entrou_em: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    paciente_visto_em: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    link_enviado_em: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class RegistroClinico(Base, TimestampMixin):
    """Anotações do profissional sobre o atendimento (presencial ou online). Um por atendimento."""

    __tablename__ = "registros_clinicos"

    id: Mapped[int] = mapped_column(primary_key=True)
    atendimento_id: Mapped[int] = mapped_column(
        ForeignKey("atendimentos.id", ondelete="CASCADE"), unique=True, nullable=False
    )
    profissional_id: Mapped[int] = mapped_column(ForeignKey("profissionais.id"), nullable=False, index=True)
    estabelecimento_id: Mapped[int] = mapped_column(
        ForeignKey("estabelecimentos.id"), nullable=False, index=True
    )
    queixa: Mapped[str | None] = mapped_column(Text, nullable=True)
    evolucao: Mapped[str | None] = mapped_column(Text, nullable=True)
    conduta: Mapped[str | None] = mapped_column(Text, nullable=True)


class TipoDocumento(str, enum.Enum):
    RECEITA = "RECEITA"
    ATESTADO = "ATESTADO"


class DocumentoClinico(Base):
    """Receita ou atestado emitido no atendimento. O PDF é gerado a partir de `conteudo`."""

    __tablename__ = "documentos_clinicos"

    id: Mapped[int] = mapped_column(primary_key=True)
    atendimento_id: Mapped[int] = mapped_column(
        ForeignKey("atendimentos.id", ondelete="CASCADE"), nullable=False, index=True
    )
    profissional_id: Mapped[int] = mapped_column(ForeignKey("profissionais.id"), nullable=False)
    cliente_id: Mapped[int] = mapped_column(ForeignKey("clientes.id"), nullable=False)
    estabelecimento_id: Mapped[int] = mapped_column(
        ForeignKey("estabelecimentos.id"), nullable=False, index=True
    )
    tipo: Mapped[TipoDocumento] = mapped_column(Enum(TipoDocumento, name="tipo_documento"), nullable=False)
    conteudo: Mapped[dict] = mapped_column(JSONB, nullable=False)
    codigo: Mapped[str] = mapped_column(String(16), unique=True, nullable=False)
    emitido_em: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class PapelTimbrado(Base):
    """Identidade da unidade nos documentos clinicos: logo, marca-d'agua e rodape. Um por unidade."""

    __tablename__ = "papeis_timbrados"

    estabelecimento_id: Mapped[int] = mapped_column(
        ForeignKey("estabelecimentos.id", ondelete="CASCADE"), primary_key=True
    )
    logo: Mapped[bytes | None] = mapped_column(LargeBinary, nullable=True)
    marca_dagua: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true", nullable=False)
    rodape: Mapped[str | None] = mapped_column(String(300), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
