"""Roteador de modelos IA por feature.

Seleciona o modelo LLM correto baseado no contexto/feature da mensagem.
Regras definidas em app/core/config.py ROUTING_RULES.
"""

import structlog

from app.core.config import ROUTING_RULES, settings

log = structlog.get_logger(__name__)


def selecionar_modelo(feature: str) -> str:
    """Seleciona modelo LLM baseado na feature.

    Args:
        feature: Tipo de interacao (saudacao, coleta_dados, triagem_clinica, etc.)

    Returns:
        Nome do modelo no OpenRouter.
    """
    modelo = ROUTING_RULES.get(feature, settings.model_economico)
    log.info("modelo_selecionado", feature=feature, modelo=modelo)
    return modelo


def obter_base_url() -> str:
    """Retorna a base URL do OpenRouter."""
    return settings.openrouter_base_url


def obter_api_key() -> str:
    """Retorna a API key do OpenRouter.

    Raises:
        ValueError: Se a API key nao estiver configurada.
    """
    if not settings.openrouter_api_key:
        raise ValueError(
            "OPENROUTER_API_KEY nao configurada. Defina no .env"
        )
    return settings.openrouter_api_key
