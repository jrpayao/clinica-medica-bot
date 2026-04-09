"""Schemas Pydantic v2 — Licenca."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, computed_field

from app.models.licenca import LicencaStatus


class PlanoQuotaInfo(BaseModel):
    """Limites do plano + uso atual do estabelecimento."""

    max_medicos: int | None
    max_consultas_mes: int | None
    whatsapp: bool
    medicos_ativos: int
    consultas_mes_atual: int


class LicencaResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    estabelecimento_id: int
    plano: str
    status: LicencaStatus
    modalidade: str
    trial_expira_em: datetime | None
    licenca_expira_em: datetime | None
    suspensa_em: datetime | None
    motivo_suspensao: str | None
    gateway_customer_id: str | None
    created_at: datetime
    updated_at: datetime

    # Preenchido pelo endpoint (não vem diretamente do model)
    dias_restantes: int | None = None
    quota_info: PlanoQuotaInfo | None = None


class AdminLicencaUpdate(BaseModel):
    """Atualização manual de licença pelo ADMIN_GLOBAL."""

    plano: str | None = Field(None, pattern="^(basico|pro|enterprise)$")
    status: LicencaStatus | None = None
    modalidade: str | None = Field(None, pattern="^(mensal|anual)$")
    meses_adicionais: int | None = Field(None, ge=1, le=24, description="Meses a adicionar à validade")
    motivo_suspensao: str | None = Field(None, max_length=500)
