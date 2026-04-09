"""Endpoint publico para acoes via link tokenizado.

GET /v1/acoes/{token} — confirmar ou cancelar consulta via link
"""

import structlog
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.services.agenda_service import AgendaService, ConsultaNaoEncontradaError
from app.services.link_tokenizado import (
    TokenAcaoExpiradoError,
    TokenAcaoInvalidoError,
    validar_token_acao,
)

log = structlog.get_logger(__name__)

router = APIRouter(prefix="/acoes", tags=["Ações"])


@router.get(
    "/{token}",
    summary="Executar acao via link tokenizado",
)
async def executar_acao(
    token: str,
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Executa acao de confirmar ou cancelar consulta via token JWT."""
    try:
        dados = validar_token_acao(token)
    except TokenAcaoExpiradoError:
        raise HTTPException(
            status_code=status.HTTP_410_GONE,
            detail="Link expirado. Solicite um novo link.",
        )
    except TokenAcaoInvalidoError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Link invalido.",
        )

    consulta_id = dados["consulta_id"]
    acao = dados["acao"]
    agenda = AgendaService(db)

    if acao == "confirmar":
        consulta = await agenda.buscar_consulta_por_id(consulta_id)
        if not consulta:
            raise HTTPException(status_code=404, detail="Consulta nao encontrada")
        return {
            "acao": "confirmada",
            "consulta_id": consulta_id,
            "mensagem": "Presenca confirmada com sucesso!",
        }

    if acao == "cancelar":
        try:
            await agenda.cancelar_consulta(consulta_id, motivo="Cancelado via link")
        except ConsultaNaoEncontradaError:
            raise HTTPException(status_code=404, detail="Consulta nao encontrada")
        return {
            "acao": "cancelada",
            "consulta_id": consulta_id,
            "mensagem": "Consulta cancelada com sucesso.",
        }

    raise HTTPException(status_code=400, detail=f"Acao desconhecida: {acao}")
