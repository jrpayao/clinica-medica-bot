from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, Field


class TipoAtendimentoCreate(BaseModel):
    nome: str = Field(..., max_length=100)
    descricao: str | None = None
    duracao_min: int = 30
    preco: Decimal | None = None


class TipoAtendimentoUpdate(BaseModel):
    nome: str | None = None
    descricao: str | None = None
    duracao_min: int | None = None
    preco: Decimal | None = None
    ativo: bool | None = None


class TipoAtendimentoOut(BaseModel):
    id: int
    estabelecimento_id: int
    nome: str
    descricao: str | None
    duracao_min: int
    preco: Decimal | None
    ativo: bool
    created_at: datetime
    model_config = {"from_attributes": True}


class TipoAtendimentoResumo(BaseModel):
    id: int
    nome: str
    duracao_min: int
    ativo: bool
    model_config = {"from_attributes": True}
