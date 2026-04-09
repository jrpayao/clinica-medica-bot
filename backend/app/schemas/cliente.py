import re
from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.models.cliente import ModalidadePagamento


class ClienteBase(BaseModel):
    cpf: str = Field(..., description="CPF com 11 digitos numericos")
    nome: str = Field(..., min_length=2, max_length=200)

    @field_validator("cpf")
    @classmethod
    def validar_cpf(cls, v: str) -> str:
        cpf = re.sub(r"\D", "", v)
        if len(cpf) != 11:
            raise ValueError("CPF deve conter 11 digitos")
        return cpf


class ClienteCreate(ClienteBase):
    data_nascimento: date | None = None
    telefone: str | None = None
    email: str | None = None
    convenio: str | None = None
    numero_carteirinha: str | None = None
    modalidade_pagamento: ModalidadePagamento | None = None
    convenio_id: int | None = None
    estabelecimento_id: int | None = None


class ClienteUpdate(BaseModel):
    nome: str | None = Field(None, min_length=2, max_length=200)
    telefone: str | None = None
    email: str | None = None
    convenio: str | None = None
    numero_carteirinha: str | None = None
    modalidade_pagamento: ModalidadePagamento | None = None
    convenio_id: int | None = None
    ativo: bool | None = None


class ClienteOut(ClienteBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    data_nascimento: date | None
    telefone: str | None
    email: str | None
    convenio: str | None
    numero_carteirinha: str | None
    modalidade_pagamento: ModalidadePagamento | None
    convenio_id: int | None
    ativo: bool
    created_at: datetime
    estabelecimento_id: int | None

    @field_validator("cpf")
    @classmethod
    def mascarar_cpf(cls, v: str) -> str:
        """Seguranca: CPF sempre mascarado na resposta."""
        if len(v) == 11:
            return f"{v[:3]}.***.***-{v[9:]}"
        return v
