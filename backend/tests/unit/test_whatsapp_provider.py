"""T103 — Testes unitários da abstração WhatsAppProvider.

TDAD: testes RED escritos antes da implementação.
"""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock


# ── Imports da abstração (ainda não existe → RED) ──────────────────────────
from app.services.whatsapp.provider import WhatsAppProvider
from app.services.whatsapp.evolution import EvolutionProvider
from app.services.whatsapp.uazapi import UazapiProvider
from app.services.whatsapp.factory import get_whatsapp_provider


# ──────────────────────────────────────────────────────────────────────────
# 1. Protocolo / contrato
# ──────────────────────────────────────────────────────────────────────────

class TestWhatsAppProviderProtocol:
    def test_evolution_satisfaz_protocolo(self):
        """EvolutionProvider deve satisfazer o WhatsAppProvider Protocol."""
        provider = EvolutionProvider()
        assert isinstance(provider, WhatsAppProvider)

    def test_uazapi_satisfaz_protocolo(self):
        """UazapiProvider deve satisfazer o WhatsAppProvider Protocol."""
        provider = UazapiProvider()
        assert isinstance(provider, WhatsAppProvider)


# ──────────────────────────────────────────────────────────────────────────
# 2. EvolutionProvider — enviar_mensagem
# ──────────────────────────────────────────────────────────────────────────

class TestEvolutionProviderEnviar:
    @pytest.mark.asyncio
    async def test_envio_bem_sucedido_retorna_true(self):
        mock_response = MagicMock()
        mock_response.status_code = 200

        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.post = AsyncMock(return_value=mock_response)

        with patch("app.services.whatsapp.evolution.httpx.AsyncClient", return_value=mock_client):
            provider = EvolutionProvider()
            result = await provider.enviar_mensagem("5511999999999", "Olá")

        assert result is True

    @pytest.mark.asyncio
    async def test_envio_com_erro_http_retorna_false(self):
        mock_response = MagicMock()
        mock_response.status_code = 500

        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.post = AsyncMock(return_value=mock_response)

        with patch("app.services.whatsapp.evolution.httpx.AsyncClient", return_value=mock_client):
            provider = EvolutionProvider()
            result = await provider.enviar_mensagem("5511999999999", "Olá")

        assert result is False

    @pytest.mark.asyncio
    async def test_envio_com_excecao_retorna_false(self):
        import httpx

        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.post = AsyncMock(side_effect=httpx.HTTPError("timeout"))

        with patch("app.services.whatsapp.evolution.httpx.AsyncClient", return_value=mock_client):
            provider = EvolutionProvider()
            result = await provider.enviar_mensagem("5511999999999", "Olá")

        assert result is False


# ──────────────────────────────────────────────────────────────────────────
# 3. EvolutionProvider — extrair_mensagem
# ──────────────────────────────────────────────────────────────────────────

class TestEvolutionProviderExtrair:
    def setup_method(self):
        self.provider = EvolutionProvider()

    def test_extrai_mensagem_valida(self):
        payload = {
            "event": "messages.upsert",
            "data": {
                "key": {"remoteJid": "5511999999999@s.whatsapp.net", "fromMe": False, "id": "ABC123"},
                "message": {"conversation": "Quero agendar"},
            },
        }
        result = self.provider.extrair_mensagem(payload)
        assert result is not None
        assert result["telefone"] == "5511999999999"
        assert result["mensagem"] == "Quero agendar"
        assert result["from_me"] is False

    def test_ignora_mensagem_do_bot(self):
        payload = {
            "event": "messages.upsert",
            "data": {
                "key": {"remoteJid": "5511999999999@s.whatsapp.net", "fromMe": True, "id": "XYZ"},
                "message": {"conversation": "Olá!"},
            },
        }
        assert self.provider.extrair_mensagem(payload) is None

    def test_ignora_evento_nao_mensagem(self):
        payload = {"event": "connection.update", "data": {}}
        assert self.provider.extrair_mensagem(payload) is None

    def test_extrai_extended_text_message(self):
        payload = {
            "event": "messages.upsert",
            "data": {
                "key": {"remoteJid": "5511111111111@s.whatsapp.net", "fromMe": False, "id": "DEF"},
                "message": {"extendedTextMessage": {"text": "Texto longo"}},
            },
        }
        result = self.provider.extrair_mensagem(payload)
        assert result is not None
        assert result["mensagem"] == "Texto longo"

    def test_retorna_none_sem_texto(self):
        payload = {
            "event": "messages.upsert",
            "data": {
                "key": {"remoteJid": "5511111111111@s.whatsapp.net", "fromMe": False, "id": "GHI"},
                "message": {"imageMessage": {}},
            },
        }
        assert self.provider.extrair_mensagem(payload) is None


# ──────────────────────────────────────────────────────────────────────────
# 4. UazapiProvider — comportamento stub
# ──────────────────────────────────────────────────────────────────────────

class TestUazapiProvider:
    @pytest.mark.asyncio
    async def test_enviar_retorna_false_stub(self):
        """UazapiProvider é stub — retorna False e não levanta exceção."""
        provider = UazapiProvider()
        result = await provider.enviar_mensagem("5511999999999", "Olá")
        assert result is False

    def test_extrair_retorna_none_stub(self):
        provider = UazapiProvider()
        assert provider.extrair_mensagem({"event": "messages.upsert"}) is None


# ──────────────────────────────────────────────────────────────────────────
# 5. Factory
# ──────────────────────────────────────────────────────────────────────────

class TestGetWhatsAppProvider:
    def test_padrao_retorna_evolution(self):
        with patch("app.services.whatsapp.factory.settings") as mock_settings:
            mock_settings.whatsapp_provider = "evolution"
            provider = get_whatsapp_provider()
        assert isinstance(provider, EvolutionProvider)

    def test_uazapi_retorna_uazapi(self):
        with patch("app.services.whatsapp.factory.settings") as mock_settings:
            mock_settings.whatsapp_provider = "uazapi"
            provider = get_whatsapp_provider()
        assert isinstance(provider, UazapiProvider)

    def test_provider_desconhecido_usa_evolution(self):
        """Provedor desconhecido deve fallback para evolution."""
        with patch("app.services.whatsapp.factory.settings") as mock_settings:
            mock_settings.whatsapp_provider = "provedor_inexistente"
            provider = get_whatsapp_provider()
        assert isinstance(provider, EvolutionProvider)
