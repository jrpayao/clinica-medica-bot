"""Factory para instanciar o WhatsAppProvider conforme WHATSAPP_PROVIDER do .env."""

import structlog

from app.core.config import settings
from app.services.whatsapp.evolution import EvolutionProvider
from app.services.whatsapp.provider import WhatsAppProvider
from app.services.whatsapp.uazapi import UazapiProvider

log = structlog.get_logger(__name__)

_PROVIDERS: dict[str, type] = {
    "evolution": EvolutionProvider,
    "uazapi": UazapiProvider,
}


def get_whatsapp_provider() -> WhatsAppProvider:
    """Retorna o provider configurado em WHATSAPP_PROVIDER (default: evolution)."""
    provider_name = settings.whatsapp_provider
    provider_class = _PROVIDERS.get(provider_name)

    if provider_class is None:
        log.warning(
            "whatsapp_provider_desconhecido",
            provider=provider_name,
            fallback="evolution",
        )
        provider_class = EvolutionProvider

    return provider_class()
