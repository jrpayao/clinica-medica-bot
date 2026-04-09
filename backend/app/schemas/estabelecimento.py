"""Schemas Pydantic v2 — EstabelecimentoSaude."""

import re
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.models.estabelecimento import TipoEstabelecimento


class EstabelecimentoBase(BaseModel):
    nome: str = Field(..., min_length=2, max_length=200)
    cnpj: str = Field(..., description="CNPJ com 14 dígitos numéricos")
    slug: str = Field(..., min_length=2, max_length=100, description="Identificador único URL-friendly")
    tipo: TipoEstabelecimento
    plano: str = Field(default="basico", description="basico | pro | enterprise")

    # Contato
    email: str | None = Field(None, max_length=254)
    telefone: str | None = Field(None, max_length=20)
    endereco: str | None = Field(None, max_length=500)
    cidade: str | None = Field(None, max_length=100)
    estado: str | None = Field(None, min_length=2, max_length=2, description="UF ex: DF, SP")
    cep: str | None = Field(None, description="CEP com 8 dígitos numéricos")

    # Responsável legal
    responsavel_nome: str | None = Field(None, max_length=200)
    responsavel_cpf: str | None = Field(None, description="CPF com 11 dígitos numéricos")
    responsavel_email: str | None = Field(None, max_length=254)
    responsavel_telefone: str | None = Field(None, max_length=20)
    responsavel_cargo: str | None = Field(None, max_length=100)

    @field_validator("cnpj")
    @classmethod
    def validar_cnpj(cls, v: str) -> str:
        cnpj = re.sub(r"\D", "", v)
        if len(cnpj) != 14:
            raise ValueError("CNPJ deve conter 14 dígitos")
        return cnpj

    @field_validator("slug")
    @classmethod
    def validar_slug(cls, v: str) -> str:
        if not re.match(r"^[a-z0-9-]+$", v):
            raise ValueError("Slug deve conter apenas letras minúsculas, números e hífens")
        return v

    @field_validator("cep")
    @classmethod
    def validar_cep(cls, v: str | None) -> str | None:
        if v is None:
            return v
        cep = re.sub(r"\D", "", v)
        if len(cep) != 8:
            raise ValueError("CEP deve conter 8 dígitos")
        return cep

    @field_validator("responsavel_cpf")
    @classmethod
    def validar_responsavel_cpf(cls, v: str | None) -> str | None:
        if v is None:
            return v
        cpf = re.sub(r"\D", "", v)
        if len(cpf) != 11:
            raise ValueError("CPF do responsável deve conter 11 dígitos")
        return cpf

    @field_validator("estado")
    @classmethod
    def validar_estado(cls, v: str | None) -> str | None:
        if v is None:
            return v
        return v.upper()


class EstabelecimentoCreate(EstabelecimentoBase):
    pass


class EstabelecimentoUpdate(BaseModel):
    nome: str | None = Field(None, min_length=2, max_length=200)
    plano: str | None = None
    ativo: bool | None = None

    # Contato
    email: str | None = Field(None, max_length=254)
    telefone: str | None = Field(None, max_length=20)
    endereco: str | None = Field(None, max_length=500)
    cidade: str | None = Field(None, max_length=100)
    estado: str | None = Field(None, min_length=2, max_length=2)
    cep: str | None = None

    # Responsável legal
    responsavel_nome: str | None = Field(None, max_length=200)
    responsavel_cpf: str | None = None
    responsavel_email: str | None = Field(None, max_length=254)
    responsavel_telefone: str | None = Field(None, max_length=20)
    responsavel_cargo: str | None = Field(None, max_length=100)


class EstabelecimentoResponse(EstabelecimentoBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    ativo: bool
    created_at: datetime
