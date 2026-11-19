"""Lista de espera e remarcações pendentes (T90, T96–T98).

POST   /v1/fila-espera                         — recepção coloca um cliente na fila
GET    /v1/fila-espera                         — fila da unidade (também em /v1/admin/fila-espera)
DELETE /v1/fila-espera/{id}                    — tira da fila
GET    /v1/reagendamentos/pendencias           — cancelados pela unidade que ainda precisam de contato
POST   /v1/reagendamentos/{id}/resolver        — recepção marca que já falou com o cliente

RBAC: RECEPCIONISTA, ADMIN_ESTABELECIMENTO e ADMIN_GLOBAL (com unidade selecionada).
"""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.dependencies import require_estabelecimento, require_role
from app.core.database import get_db
from app.models.cliente import Cliente
from app.models.convenio import Convenio
from app.models.especialidade import Especialidade
from app.services.fila_espera_service import FilaEsperaService, listar_fila, remover_da_fila
from app.services.reagendamento_service import listar_pendencias, resolver_pendencia

ROLES_FILA = ("ADMIN_GLOBAL", "ADMIN_ESTABELECIMENTO", "RECEPCIONISTA")

router = APIRouter(tags=["Lista de espera"])

_Staff = Annotated[dict, Depends(require_role(*ROLES_FILA))]
_Unidade = Annotated[int, Depends(require_estabelecimento)]


class EntrarNaFilaRequest(BaseModel):
    cliente_id: int
    especialidade_id: int | None = None
    convenio_id: int | None = None


async def _da_unidade(db: AsyncSession, modelo, registro_id: int | None, unidade: int, nome: str) -> None:
    if registro_id is None:
        return
    existe = (
        await db.execute(
            select(modelo.id).where(modelo.id == registro_id, modelo.estabelecimento_id == unidade)
        )
    ).scalar_one_or_none()
    if existe is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"{nome} não encontrado nesta unidade")


@router.get("/fila-espera", summary="Fila de espera da unidade")
@router.get("/admin/fila-espera", summary="Fila de espera da unidade", include_in_schema=False)
async def fila_da_unidade(_: _Staff, unidade: _Unidade, db: AsyncSession = Depends(get_db)) -> list[dict]:
    return await listar_fila(db, unidade)


@router.post("/fila-espera", status_code=status.HTTP_201_CREATED, summary="Colocar cliente na fila")
async def entrar_na_fila(
    dados: EntrarNaFilaRequest, _: _Staff, unidade: _Unidade, db: AsyncSession = Depends(get_db)
) -> dict:
    await _da_unidade(db, Cliente, dados.cliente_id, unidade, "Cliente")
    await _da_unidade(db, Especialidade, dados.especialidade_id, unidade, "Especialidade")
    await _da_unidade(db, Convenio, dados.convenio_id, unidade, "Convênio")
    entrada = await FilaEsperaService(db).entrar_sem_duplicar(
        dados.cliente_id, unidade, dados.especialidade_id, dados.convenio_id
    )
    await db.commit()
    return {"id": entrada.id, "status": entrada.status.value}


@router.delete("/fila-espera/{fila_id}", status_code=status.HTTP_204_NO_CONTENT, summary="Tirar da fila")
async def sair_da_fila(fila_id: int, _: _Staff, unidade: _Unidade, db: AsyncSession = Depends(get_db)) -> None:
    if not await remover_da_fila(db, fila_id, unidade):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Entrada não encontrada na fila")
    await db.commit()


@router.get("/reagendamentos/pendencias", summary="Remarcações que precisam de contato")
async def remarcacoes_pendentes(_: _Staff, unidade: _Unidade, db: AsyncSession = Depends(get_db)) -> list[dict]:
    return await listar_pendencias(db, unidade)


@router.post(
    "/reagendamentos/{oferta_id}/resolver",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Marcar remarcação como resolvida",
)
async def resolver_remarcacao(
    oferta_id: int, _: _Staff, unidade: _Unidade, db: AsyncSession = Depends(get_db)
) -> None:
    if not await resolver_pendencia(db, oferta_id, unidade):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Pendência não encontrada")
    await db.commit()
