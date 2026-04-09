"""UazapiProvider — stub para integração futura com UazAPI.

Implementação placeholder. Para ativar:
1. Instalar UazAPI (https://uazapi.com)
2. Implementar os métodos conforme a API do provedor
3. Configurar WHATSAPP_PROVIDER=uazapi no .env
"""

import structlog

log = structlog.get_logger(__name__)


class UazapiProvider:
    """Provedor WhatsApp via UazAPI — stub (não implementado)."""

    async def enviar_mensagem(self, telefone: str, mensagem: str) -> bool:
        log.warning(
            "uazapi_nao_implementado",
            telefone=telefone[:5] + "***",
        )
        return False

    def extrair_mensagem(self, payload: dict) -> dict | None:
        log.warning("uazapi_extrair_nao_implementado")
        return None
