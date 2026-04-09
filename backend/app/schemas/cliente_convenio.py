from datetime import date, datetime

from pydantic import BaseModel, Field


class ClienteConvenioCreate(BaseModel):
    convenio_id: int
    plano_id: int | None = None
    numero_carteirinha: str = Field(..., max_length=50)
    nome_titular: str | None = None
    validade: date | None = None
    principal: bool = False


class ClienteConvenioUpdate(BaseModel):
    plano_id: int | None = None
    numero_carteirinha: str | None = None
    nome_titular: str | None = None
    validade: date | None = None
    principal: bool | None = None
    ativo: bool | None = None


class ClienteConvenioOut(BaseModel):
    id: int
    cliente_id: int
    convenio_id: int
    plano_id: int | None
    numero_carteirinha: str
    nome_titular: str | None
    validade: date | None
    principal: bool
    ativo: bool
    created_at: datetime
    model_config = {"from_attributes": True}
