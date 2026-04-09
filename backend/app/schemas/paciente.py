import re
from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator


class PacienteBase(BaseModel):
    nome: str = Field(..., min_length=2, max_length=200)
    cpf: str = Field(..., description="CPF com 11 digitos numericos")

    @field_validator("cpf")
    @classmethod
    def validar_cpf(cls, v: str) -> str:
        cpf = re.sub(r"\D", "", v)
        if len(cpf) != 11:
            raise ValueError("CPF deve conter 11 digitos")
        return cpf


class PacienteCreate(PacienteBase):
    data_nascimento: date | None = None
    telefone: str | None = None
    email: str | None = None
    convenio: str | None = None
    numero_carteirinha: str | None = None


class PacienteUpdate(BaseModel):
    nome: str | None = Field(None, min_length=2, max_length=200)
    telefone: str | None = None
    email: str | None = None
    convenio: str | None = None
    numero_carteirinha: str | None = None


class PacienteResponse(PacienteBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    data_nascimento: date | None
    telefone: str | None
    email: str | None
    convenio: str | None
    numero_carteirinha: str | None
    ativo: bool
    created_at: datetime

    @field_validator("cpf")
    @classmethod
    def mascarar_cpf(cls, v: str) -> str:
        """Seguranca: CPF sempre mascarado na resposta."""
        if len(v) == 11:
            return f"{v[:3]}.***.***-{v[9:]}"
        return v
