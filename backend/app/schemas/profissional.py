from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class ProfissionalBase(BaseModel):
    registro_profissional: str = Field(..., min_length=4, max_length=20)
    nome: str = Field(..., min_length=2, max_length=200)
    especialidade_id: int
    email: str | None = None
    telefone: str | None = None
    duracao_atendimento_min: int = Field(default=30, ge=10, le=120)


class ProfissionalCreate(ProfissionalBase):
    pass


class ProfissionalUpdate(BaseModel):
    nome: str | None = Field(None, min_length=2, max_length=200)
    email: str | None = None
    telefone: str | None = None
    duracao_atendimento_min: int | None = Field(None, ge=10, le=120)
    ativo: bool | None = None


class ProfissionalResponse(ProfissionalBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    ativo: bool
    created_at: datetime


class ProfissionalOut(ProfissionalBase):
    id: int
    ativo: bool
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)


class ProfissionalResumo(BaseModel):
    id: int
    nome: str
    registro_profissional: str
    especialidade_id: int
    duracao_atendimento_min: int
    model_config = ConfigDict(from_attributes=True)


class GerarSlotsRequest(BaseModel):
    """Request para gerar slots de agenda para um profissional."""

    data_inicio: str = Field(..., description="Data inicio YYYY-MM-DD")
    data_fim: str = Field(..., description="Data fim YYYY-MM-DD")
    hora_inicio: str = Field(default="08:00", description="Hora inicio HH:MM")
    hora_fim: str = Field(default="18:00", description="Hora fim HH:MM")
    intervalo_almoco_inicio: str | None = Field(default="12:00")
    intervalo_almoco_fim: str | None = Field(default="13:00")
    dias_semana: list[int] = Field(
        default=[0, 1, 2, 3, 4],
        description="Dias da semana (0=seg, 6=dom)",
    )
