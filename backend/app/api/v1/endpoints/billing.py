"""Endpoints de billing — dashboard + export CSV + ranking por estabelecimento.

Controle de acesso (RBAC):
  ADMIN_GLOBAL       → vê tudo; pode filtrar por ?estabelecimento_id=N
  ADMIN_ESTABELECIMENTO → vê apenas o próprio estabelecimento (extraído do JWT)

GET  /v1/billing/config                  — leitura de limites (ambos os roles)
PATCH /v1/billing/config                 — atualizar limites (ambos os roles)
GET  /v1/billing/dashboard               — resumo diário com filtro RBAC
GET  /v1/billing/export                  — CSV com filtro RBAC
GET  /v1/billing/por-estabelecimento     — ranking por tenant (ADMIN_GLOBAL)
"""

import csv
import io
from datetime import date
from typing import Annotated

import structlog
from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.dependencies import get_current_user, require_role
from app.core.config import settings
from app.core.database import get_db
from app.services.ia.billing import (
    listar_registros,
    obter_custo_diario_total,
    obter_ranking_por_estabelecimento,
    obter_resumo_diario,
    obter_resumo_por_feature,
    obter_resumo_por_modelo,
)

log = structlog.get_logger(__name__)

router = APIRouter(prefix="/billing", tags=["Billing"])

_ROLES_ADMIN = ("ADMIN_GLOBAL", "ADMIN_ESTABELECIMENTO")


class BillingConfigUpdate(BaseModel):
    daily_limit_usd: float | None = Field(None, ge=0.01)
    monthly_limit_usd: float | None = Field(None, ge=0.01)
    alert_threshold: float | None = Field(None, ge=0.01, le=1.0)


def _resolver_estabelecimento_id(
    current_user: dict,
    estabelecimento_id_param: int | None,
) -> int | None:
    """Resolve qual estabelecimento_id usar nas queries de billing.

    - ADMIN_ESTABELECIMENTO: sempre o do JWT, ignora param (segurança)
    - ADMIN_GLOBAL: usa o param se fornecido, senão None (dados globais)
    """
    role = current_user.get("role", "")
    if role == "ADMIN_ESTABELECIMENTO":
        return current_user.get("estabelecimento_id")
    # ADMIN_GLOBAL
    return estabelecimento_id_param


@router.get(
    "/config",
    summary="Configurações de limites de billing",
    dependencies=[Depends(require_role(*_ROLES_ADMIN))],
)
async def obter_config() -> dict:
    """Retorna limites de custo configurados."""
    return {
        "daily_limit_usd": settings.daily_limit_usd,
        "monthly_limit_usd": settings.monthly_limit_usd,
        "alert_threshold": settings.alert_threshold_pct / 100,
    }


@router.patch(
    "/config",
    summary="Atualizar limites de billing (runtime)",
    dependencies=[Depends(require_role(*_ROLES_ADMIN))],
)
async def atualizar_config(dados: BillingConfigUpdate) -> dict:
    """Atualiza limites de custo em memória (reset ao reiniciar)."""
    if dados.daily_limit_usd is not None:
        settings.daily_limit_usd = dados.daily_limit_usd
    if dados.monthly_limit_usd is not None:
        settings.monthly_limit_usd = dados.monthly_limit_usd
    if dados.alert_threshold is not None:
        settings.alert_threshold_pct = int(dados.alert_threshold * 100)
    log.info(
        "billing_config_atualizado",
        daily_limit=settings.daily_limit_usd,
        monthly_limit=settings.monthly_limit_usd,
        alert_threshold_pct=settings.alert_threshold_pct,
    )
    return {
        "daily_limit_usd": settings.daily_limit_usd,
        "monthly_limit_usd": settings.monthly_limit_usd,
        "alert_threshold": settings.alert_threshold_pct / 100,
    }


@router.get(
    "/dashboard",
    summary="Dashboard de billing com RBAC por estabelecimento",
    dependencies=[Depends(require_role(*_ROLES_ADMIN))],
)
async def dashboard(
    current_user: Annotated[dict, Depends(get_current_user)],
    data: date | None = Query(None, description="Data para o resumo (default: hoje)"),
    estabelecimento_id: int | None = Query(
        None,
        description="Filtrar por estabelecimento (somente ADMIN_GLOBAL)",
    ),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Retorna resumo de billing do dia.

    - ADMIN_GLOBAL: dados globais ou filtrado por estabelecimento_id
    - ADMIN_ESTABELECIMENTO: sempre escopo do próprio estabelecimento
    """
    est_id = _resolver_estabelecimento_id(current_user, estabelecimento_id)

    resumo = await obter_resumo_diario(db, data=data, estabelecimento_id=est_id)
    por_modelo = await obter_resumo_por_modelo(db, data=data, estabelecimento_id=est_id)
    por_feature = await obter_resumo_por_feature(db, data=data, estabelecimento_id=est_id)
    custo_total = await obter_custo_diario_total(db, data=data, estabelecimento_id=est_id)

    return {
        "resumo": resumo,
        "por_modelo": por_modelo,
        "por_feature": por_feature,
        "filtro_estabelecimento_id": est_id,
        "limites": {
            "diario_usd": settings.daily_limit_usd,
            "mensal_usd": settings.monthly_limit_usd,
            "custo_atual_usd": float(custo_total),
            "percentual_usado": float(custo_total) / settings.daily_limit_usd * 100
            if settings.daily_limit_usd > 0
            else 0,
        },
    }


@router.get(
    "/por-estabelecimento",
    summary="Ranking de custo por estabelecimento (ADMIN_GLOBAL)",
    dependencies=[Depends(require_role("ADMIN_GLOBAL"))],
)
async def ranking_por_estabelecimento(
    data: date | None = Query(None, description="Data do ranking (default: hoje)"),
    db: AsyncSession = Depends(get_db),
) -> list[dict]:
    """Retorna custo agregado por estabelecimento ordenado por custo desc.

    Exclusivo para ADMIN_GLOBAL — visão de toda a plataforma.
    """
    return await obter_ranking_por_estabelecimento(db, data=data)


@router.get(
    "/export",
    summary="Exportar billing em CSV com RBAC",
    dependencies=[Depends(require_role(*_ROLES_ADMIN))],
)
async def export_csv(
    current_user: Annotated[dict, Depends(get_current_user)],
    inicio: date | None = Query(None, description="Data inicio"),
    fim: date | None = Query(None, description="Data fim"),
    estabelecimento_id: int | None = Query(
        None,
        description="Filtrar por estabelecimento (somente ADMIN_GLOBAL)",
    ),
    db: AsyncSession = Depends(get_db),
) -> StreamingResponse:
    """Exporta registros de token_usage em formato CSV.

    ADMIN_ESTABELECIMENTO exporta apenas os dados do próprio estabelecimento.
    """
    est_id = _resolver_estabelecimento_id(current_user, estabelecimento_id)
    registros = await listar_registros(
        db, data_inicio=inicio, data_fim=fim, estabelecimento_id=est_id
    )

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow([
        "id", "session_id", "estabelecimento_id", "modelo", "feature",
        "prompt_tokens", "completion_tokens", "total_tokens",
        "cost_usd", "user_type", "created_at",
    ])

    for r in registros:
        writer.writerow([
            r.id, r.session_id, r.estabelecimento_id,
            r.modelo,
            r.feature.value if hasattr(r.feature, "value") else r.feature,
            r.prompt_tokens, r.completion_tokens, r.total_tokens,
            str(r.cost_usd), r.user_type,
            r.created_at.isoformat() if r.created_at else "",
        ])

    output.seek(0)
    suffix = f"_est{est_id}" if est_id else ""
    filename = f"billing{suffix}_{inicio or 'all'}_{fim or 'all'}.csv"

    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )
