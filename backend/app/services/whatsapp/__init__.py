"""Abstração de provedores WhatsApp.

Uso:
    from app.services.whatsapp.factory import get_whatsapp_provider
    provider = get_whatsapp_provider()
    await provider.enviar_mensagem(telefone, texto)
"""
