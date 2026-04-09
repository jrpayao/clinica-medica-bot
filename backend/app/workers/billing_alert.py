"""Job Celery para alertas de custo de billing.

Verifica se custo diario atingiu 80% ou 100% do limite.
- 80%: envia alerta de warning
- 100%: desativa modelo premium e envia alerta critico
"""

from decimal import Decimal

import structlog

from app.core.config import settings
from app.workers.celery_app import celery_app

log = structlog.get_logger(__name__)

ALERTA_80_MSG = "ALERTA: Custo de IA atingiu {percentual:.0f}% do limite diario (${custo_atual:.4f} de ${limite:.2f})"
ALERTA_100_MSG = "CRITICO: Custo de IA atingiu {percentual:.0f}% do limite! Modelo premium DESATIVADO. (${custo_atual:.4f} de ${limite:.2f})"


async def verificar_limites_custo(
    custo_atual: Decimal,
    limite_diario: Decimal,
) -> dict:
    """Verifica se custo atingiu thresholds de alerta.

    Returns:
        dict com alerta (bool), nivel, mensagem, percentual, desativar_premium
    """
    if limite_diario <= 0:
        return {
            "alerta": False,
            "nivel": None,
            "mensagem": None,
            "percentual": 0,
            "desativar_premium": False,
            "acao": None,
        }

    percentual = float(custo_atual / limite_diario * 100)

    if percentual >= 100:
        mensagem = ALERTA_100_MSG.format(
            percentual=percentual,
            custo_atual=custo_atual,
            limite=limite_diario,
        )
        log.critical(
            "billing_limite_atingido",
            percentual=percentual,
            custo_atual=str(custo_atual),
        )
        return {
            "alerta": True,
            "nivel": "critical",
            "mensagem": mensagem,
            "percentual": percentual,
            "desativar_premium": True,
            "acao": "desativar_premium",
        }

    threshold = settings.alert_threshold_pct  # default 80
    if percentual >= threshold:
        mensagem = ALERTA_80_MSG.format(
            percentual=percentual,
            custo_atual=custo_atual,
            limite=limite_diario,
        )
        log.warning(
            "billing_alerta_threshold",
            percentual=percentual,
            custo_atual=str(custo_atual),
        )
        return {
            "alerta": True,
            "nivel": "warning",
            "mensagem": mensagem,
            "percentual": percentual,
            "desativar_premium": False,
            "acao": "notificar_admin",
        }

    return {
        "alerta": False,
        "nivel": None,
        "mensagem": None,
        "percentual": percentual,
        "desativar_premium": False,
        "acao": None,
    }


@celery_app.task(name="verificar_billing_diario")
def verificar_billing_diario() -> dict:
    """Task Celery que verifica limites de custo diario.

    Executada periodicamente via beat schedule.
    """
    import asyncio

    from app.core.database import AsyncSessionLocal
    from app.services.ia.billing import obter_custo_diario_total

    async def _check():
        async with AsyncSessionLocal() as db:
            custo = await obter_custo_diario_total(db)
            resultado = await verificar_limites_custo(
                custo_atual=custo,
                limite_diario=Decimal(str(settings.daily_limit_usd)),
            )

            if resultado["alerta"]:
                log.warning(
                    "billing_alerta_disparado",
                    nivel=resultado["nivel"],
                    mensagem=resultado["mensagem"],
                )

            return resultado

    return asyncio.get_event_loop().run_until_complete(_check())
