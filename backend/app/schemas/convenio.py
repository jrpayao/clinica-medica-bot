from datetime import datetime

from pydantic import BaseModel, Field


class ConvenioCreate(BaseModel):
    nome: str = Field(..., max_length=100)
    codigo_ans: str | None = Field(None, max_length=20)
    cnpj: str | None = Field(None, max_length=14)
    telefone_autorizacao: str | None = None
    email: str | None = None
    website: str | None = None


class ConvenioUpdate(BaseModel):
    nome: str | None = None
    codigo_ans: str | None = None
    cnpj: str | None = None
    telefone_autorizacao: str | None = None
    email: str | None = None
    website: str | None = None
    ativo: bool | None = None


class ConvenioOut(BaseModel):
    id: int
    nome: str
    codigo_ans: str | None
    cnpj: str | None
    telefone_autorizacao: str | None
    email: str | None
    website: str | None
    ativo: bool
    estabelecimento_id: int
    created_at: datetime
    model_config = {"from_attributes": True}


class ConvenioResumo(BaseModel):
    id: int
    nome: str
    ativo: bool
    model_config = {"from_attributes": True}
