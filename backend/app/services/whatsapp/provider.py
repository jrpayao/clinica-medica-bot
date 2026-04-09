"""Protocolo WhatsAppProvider — contrato que todo provedor deve satisfazer."""

from typing import Protocol, runtime_checkable


@runtime_checkable
class WhatsAppProvider(Protocol):
    async def enviar_mensagem(self, telefone: str, mensagem: str) -> bool:
        """Envia mensagem de texto para o número informado.

        Returns:
            True se enviada com sucesso, False caso contrário.
        """
        ...

    def extrair_mensagem(self, payload: dict) -> dict | None:
        """Extrai dados da mensagem recebida pelo webhook do provedor.

        Returns:
            Dict com {telefone, mensagem, from_me, message_id} ou None
            se o payload não representar uma mensagem de entrada válida.
        """
        ...
