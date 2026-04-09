from pydantic import BaseModel


class ConvenioResponse(BaseModel):
    id: int
    nome: str
    ativo: bool
    estabelecimento_id: int

    model_config = {"from_attributes": True}
