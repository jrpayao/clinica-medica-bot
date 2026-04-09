from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class EspecialidadeBase(BaseModel):
    nome: str = Field(..., min_length=2, max_length=200)
    descricao: str | None = None
    cor_hex: str | None = Field(None, pattern=r"^#[0-9A-Fa-f]{6}$")
    icone: str | None = Field(None, max_length=50)


class EspecialidadeCreate(EspecialidadeBase):
    pass


class EspecialidadeUpdate(BaseModel):
    nome: str | None = Field(None, min_length=2, max_length=200)
    descricao: str | None = None
    cor_hex: str | None = Field(None, pattern=r"^#[0-9A-Fa-f]{6}$")
    icone: str | None = Field(None, max_length=50)
    ativo: bool | None = None


class EspecialidadeResponse(EspecialidadeBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    ativo: bool
    created_at: datetime
