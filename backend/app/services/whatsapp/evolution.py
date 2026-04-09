"""EvolutionProvider — implementação do WhatsAppProvider via Evolution API."""

import httpx
import structlog

from app.core.config import settings

log = structlog.get_logger(__name__)


class EvolutionProvider:
    """Provedor WhatsApp baseado na Evolution API (self-hosted)."""

    async def enviar_mensagem(self, telefone: str, mensagem: str) -> bool:
        url = f"{settings.evolution_api_url}/message/sendText/{settings.whatsapp_instance}"
        headers = {
            "Content-Type": "application/json",
            "apikey": settings.evolution_api_key,
        }
        payload = {"number": telefone, "text": mensagem}

        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(url, json=payload, headers=headers)

            if response.status_code == 200:
                log.info("whatsapp_mensagem_enviada", telefone=telefone[:5] + "***")
                return True

            log.warning(
                "whatsapp_envio_falhou",
                status_code=response.status_code,
                telefone=telefone[:5] + "***",
            )
            return False

        except httpx.HTTPError as e:
            log.error("whatsapp_erro_envio", erro=str(e), telefone=telefone[:5] + "***")
            return False

    def extrair_mensagem(self, payload: dict) -> dict | None:
        """Extrai mensagem do payload do webhook Evolution API."""
        if payload.get("event") != "messages.upsert":
            return None

        data = payload.get("data", {})
        key = data.get("key", {})

        if key.get("fromMe", False):
            return None

        remote_jid = key.get("remoteJid", "")
        telefone = remote_jid.split("@")[0]

        message = data.get("message", {})
        mensagem = message.get("conversation")

        if not mensagem:
            extended = message.get("extendedTextMessage", {})
            mensagem = extended.get("text")

        if not mensagem:
            return None

        return {
            "telefone": telefone,
            "mensagem": mensagem,
            "from_me": False,
            "message_id": key.get("id"),
        }
