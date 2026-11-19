from datetime import date, datetime, time

from pydantic import BaseModel, ConfigDict, Field

from app.models.atendimento import (
    AtendimentoCanal,
    AtendimentoStatus,
    AtendimentoTipo,
    AtendimentoUrgencia,
    MotivoCancelamento,
)
from app.models.slot import SlotStatus


class SlotResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    profissional_id: int
    data: date
    hora_inicio: time
    hora_fim: time
    status: SlotStatus


class AtendimentoCreate(BaseModel):
    slot_id: int
    cliente_id: int
    profissional_id: int
    especialidade_id: int
    tipo: AtendimentoTipo = AtendimentoTipo.EXTERNO
    urgencia: AtendimentoUrgencia = AtendimentoUrgencia.BAIXA
    canal_origem: AtendimentoCanal = AtendimentoCanal.PORTAL
    triagem_resumo: dict | None = None
    observacoes: str | None = None
    cliente_convenio_id: int | None = None
    estabelecimento_id: int | None = None


class AtendimentoCancelar(BaseModel):
    motivo: str = Field(..., min_length=3, max_length=500)
    # Quem originou o cancelamento. MEDICO e ESTABELECIMENTO fazem o cliente receber novos horários.
    origem: MotivoCancelamento | None = None


class AtendimentoOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    slot_id: int
    cliente_id: int
    profissional_id: int
    especialidade_id: int
    tipo: AtendimentoTipo
    status: AtendimentoStatus
    triagem_resumo: dict | None
    urgencia: AtendimentoUrgencia
    canal_origem: AtendimentoCanal
    observacoes: str | None
    motivo_cancelamento: MotivoCancelamento | None = None
    created_at: datetime
    updated_at: datetime


class AtendimentoResumo(BaseModel):
    id: int
    cliente_id: int
    profissional_id: int
    status: AtendimentoStatus
    urgencia: AtendimentoUrgencia
    model_config = ConfigDict(from_attributes=True)


class AtendimentoFiltros(BaseModel):
    profissional_id: int | None = None
    status: AtendimentoStatus | None = None
    data: str | None = None


class TransicaoStatusRequest(BaseModel):
    status_novo: AtendimentoStatus
    observacao: str | None = None


class DisponibilidadeQuery(BaseModel):
    especialidade_id: int | None = None
    profissional_id: int | None = None
    data_inicio: date | None = None
    data_fim: date | None = None
