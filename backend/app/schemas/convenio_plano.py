from datetime import datetime

from pydantic import BaseModel, Field


class ConvenioPlanoCreate(BaseModel):
    nome: str = Field(..., max_length=100)


class ConvenioPlanoUpdate(BaseModel):
    nome: str | None = None
    ativo: bool | None = None


class ConvenioPlanoOut(BaseModel):
    id: int
    convenio_id: int
    nome: str
    ativo: bool
    created_at: datetime
    model_config = {"from_attributes": True}
