from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.dependencies import require_estabelecimento
from app.core.database import get_db
from app.schemas.convenio import ConvenioResponse
from app.services.convenio_service import ConvenioService

router = APIRouter(prefix="/convenios", tags=["Convênios"])


@router.get(
    "/",
    response_model=list[ConvenioResponse],
    summary="Listar convênios ativos do estabelecimento",
)
async def listar_convenios(
    db: AsyncSession = Depends(get_db),
    estabelecimento_id: Annotated[int, Depends(require_estabelecimento)] = ...,
) -> list[ConvenioResponse]:
    """Lista convênios ativos do estabelecimento logado."""
    service = ConvenioService(db)
    return await service.listar_ativos(estabelecimento_id)
