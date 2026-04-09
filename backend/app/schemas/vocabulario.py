from pydantic import BaseModel, Field


class VocabularioUpdate(BaseModel):
    label_profissional: str | None = Field(None, max_length=50)
    label_atendimento: str | None = Field(None, max_length=50)
    label_cliente: str | None = Field(None, max_length=50)
    label_especialidade: str | None = Field(None, max_length=50)


class VocabularioOut(BaseModel):
    label_profissional: str
    label_atendimento: str
    label_cliente: str
    label_especialidade: str
    model_config = {"from_attributes": True}
