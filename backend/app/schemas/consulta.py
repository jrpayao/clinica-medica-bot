from datetime import date, datetime, time

from pydantic import BaseModel, ConfigDict, Field

from app.models.consulta import ConsultaCanal, ConsultaStatus, ConsultaTipo, ConsultaUrgencia
from app.models.slot import SlotStatus


class SlotResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    medico_id: int
    data: date
    hora_inicio: time
    hora_fim: time
    status: SlotStatus


class ConsultaCreate(BaseModel):
    slot_id: int
    paciente_id: int
    medico_id: int
    especialidade_id: int
    tipo: ConsultaTipo = ConsultaTipo.EXTERNO
    canal_origem: ConsultaCanal = ConsultaCanal.PORTAL
    triagem_resumo: dict | None = None
    urgencia: ConsultaUrgencia = ConsultaUrgencia.BAIXA
    observacoes: str | None = None


class ConsultaCancelar(BaseModel):
    motivo: str = Field(..., min_length=3, max_length=500)


class ConsultaResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    slot_id: int
    paciente_id: int
    medico_id: int
    especialidade_id: int
    tipo: ConsultaTipo
    status: ConsultaStatus
    triagem_resumo: dict | None
    urgencia: ConsultaUrgencia
    canal_origem: ConsultaCanal
    observacoes: str | None
    created_at: datetime
    updated_at: datetime


class DisponibilidadeQuery(BaseModel):
    especialidade_id: int | None = None
    medico_id: int | None = None
    data_inicio: date | None = None
    data_fim: date | None = None
