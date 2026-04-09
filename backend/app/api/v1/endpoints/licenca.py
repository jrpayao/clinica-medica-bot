"""Endpoints de Licenciamento.

GET  /v1/licenca/minha                  — status da licença do tenant logado
PATCH /v1/admin/licenca/{est_id}        — ADMIN_GLOBAL gerencia licença manualmente
"""

import structlog
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.dependencies import get_estabelecimento_id, get_current_user, require_role
from app.core.config import PLANO_QUOTAS
from app.core.database import get_db
from app.schemas.licenca import AdminLicencaUpdate, LicencaResponse, PlanoQuotaInfo
from app.services.licenca_service import (
    LicencaNaoEncontradaError,
    LicencaService,
)

log = structlog.get_logger(__name__)

router = APIRouter(tags=["Licença"])


@router.get(
    "/licenca/minha",
    response_model=LicencaResponse,
    summary="Status da licença do estabelecimento logado",
)
async def minha_licenca(
    estabelecimento_id: int = Depends(get_estabelecimento_id),
    db: AsyncSession = Depends(get_db),
) -> LicencaResponse:
    """Retorna licença com status atual, dias restantes e uso de quotas.

    Acessível mesmo quando a licença está expirada (não usa verificar_licenca_ativa).
    """
    service = LicencaService(db)
    licenca = await service.buscar_por_estabelecimento(estabelecimento_id)

    if not licenca:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Licença não encontrada para este estabelecimento.",
        )

    quota_cfg = PLANO_QUOTAS.get(licenca.plano, PLANO_QUOTAS["basico"])
    medicos_ativos = await service.contar_medicos_ativos(estabelecimento_id)
    consultas_mes = await service.contar_consultas_mes(estabelecimento_id)

    response = LicencaResponse.model_validate(licenca)
    response.dias_restantes = service.calcular_dias_restantes(licenca)
    response.quota_info = PlanoQuotaInfo(
        max_medicos=quota_cfg["max_medicos"],
        max_consultas_mes=quota_cfg["max_consultas_mes"],
        whatsapp=quota_cfg["whatsapp"],
        medicos_ativos=medicos_ativos,
        consultas_mes_atual=consultas_mes,
    )

    return response


@router.patch(
    "/admin/licenca/{estabelecimento_id}",
    response_model=LicencaResponse,
    summary="Gerenciar licença manualmente (ADMIN_GLOBAL)",
)
async def gerenciar_licenca(
    estabelecimento_id: int,
    dados: AdminLicencaUpdate,
    current_user: dict = Depends(require_role("ADMIN_GLOBAL")),
    db: AsyncSession = Depends(get_db),
) -> LicencaResponse:
    """ADMIN_GLOBAL pode ativar, renovar, suspender ou reativar a licença de qualquer tenant.

    Lógica:
    - status=SUSPENSA + motivo → suspender()
    - status=ATIVA + plano + meses_adicionais → ativar_plano()
    - status=ATIVA sem plano → reativar()
    - Apenas plano/modalidade → atualiza plano via ativar_plano() com meses_adicionais=1
    """
    service = LicencaService(db)
    admin_id = int(current_user.get("sub", 0))

    try:
        if dados.status and dados.status.value == "SUSPENSA":
            licenca = await service.suspender(
                estabelecimento_id=estabelecimento_id,
                admin_id=admin_id,
                motivo=dados.motivo_suspensao or "Suspenso pelo administrador",
            )

        elif dados.status and dados.status.value == "ATIVA" and not dados.plano:
            licenca = await service.reativar(estabelecimento_id)

        else:
            # Ativar/renovar plano
            plano = dados.plano or "basico"
            modalidade = dados.modalidade or "mensal"
            meses = dados.meses_adicionais or (12 if modalidade == "anual" else 1)
            licenca = await service.ativar_plano(
                estabelecimento_id=estabelecimento_id,
                plano=plano,
                modalidade=modalidade,
                meses=meses,
                admin_id=admin_id,
            )

    except LicencaNaoEncontradaError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))

    await db.commit()

    quota_cfg = PLANO_QUOTAS.get(licenca.plano, PLANO_QUOTAS["basico"])
    medicos_ativos = await service.contar_medicos_ativos(estabelecimento_id)
    consultas_mes = await service.contar_consultas_mes(estabelecimento_id)

    response = LicencaResponse.model_validate(licenca)
    response.dias_restantes = service.calcular_dias_restantes(licenca)
    response.quota_info = PlanoQuotaInfo(
        max_medicos=quota_cfg["max_medicos"],
        max_consultas_mes=quota_cfg["max_consultas_mes"],
        whatsapp=quota_cfg["whatsapp"],
        medicos_ativos=medicos_ativos,
        consultas_mes_atual=consultas_mes,
    )

    log.info(
        "licenca_atualizada",
        estabelecimento_id=estabelecimento_id,
        plano=licenca.plano,
        status=licenca.status.value,
        admin_id=admin_id,
    )

    return response
