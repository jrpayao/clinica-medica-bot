import re

from pydantic import BaseModel, Field, field_validator


class SMSRequestSchema(BaseModel):
    """Solicitacao de codigo SMS para autenticacao de paciente."""

    cpf: str = Field(..., description="CPF com 11 digitos numericos")

    @field_validator("cpf")
    @classmethod
    def validar_cpf(cls, v: str) -> str:
        cpf = re.sub(r"\D", "", v)
        if len(cpf) != 11:
            raise ValueError("CPF deve conter 11 digitos")
        return cpf


class SMSVerifySchema(BaseModel):
    """Verificacao do codigo SMS recebido."""

    cpf: str = Field(..., description="CPF com 11 digitos numericos")
    codigo: str = Field(..., min_length=6, max_length=6, description="Codigo SMS de 6 digitos")

    @field_validator("cpf")
    @classmethod
    def validar_cpf(cls, v: str) -> str:
        cpf = re.sub(r"\D", "", v)
        if len(cpf) != 11:
            raise ValueError("CPF deve conter 11 digitos")
        return cpf

    @field_validator("codigo")
    @classmethod
    def validar_codigo(cls, v: str) -> str:
        if not v.isdigit():
            raise ValueError("Codigo deve conter apenas digitos")
        return v


class LoginSchema(BaseModel):
    """Login interno via email + senha."""

    email: str = Field(..., description="Email do usuario interno")
    senha: str = Field(..., min_length=6, description="Senha do usuario")


class TokenResponse(BaseModel):
    """Resposta com tokens JWT."""

    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class RefreshTokenSchema(BaseModel):
    """Solicitacao de renovacao de token."""

    refresh_token: str


class SMSResponse(BaseModel):
    """Resposta da solicitacao de SMS."""

    mensagem: str
    ttl_segundos: int = 300
    dev_codigo: str | None = None  # exposto apenas em DEBUG=true
