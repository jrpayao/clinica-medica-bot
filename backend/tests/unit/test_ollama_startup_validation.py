"""Testes da validacao de modelos Ollama no startup."""

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

from app.main import _obter_tags_url_ollama, validar_modelos_ollama


def test_obter_tags_url_ollama_remove_sufixo_v1():
    url = _obter_tags_url_ollama("http://localhost:11434/v1")
    assert url == "http://localhost:11434/api/tags"


async def test_validacao_ignora_quando_nao_e_ollama_local():
    mock_settings = SimpleNamespace(
        openrouter_base_url="https://openrouter.ai/api/v1",
        model_economico="llama3.1:8b",
        model_medico="cniongolo/biomistral:latest",
        model_premium="llama3.1:8b",
        model_rag="cniongolo/biomistral:latest",
    )
    with patch("app.main.settings", mock_settings):
        resultado = await validar_modelos_ollama()
    assert resultado["status"] == "skipped"
    assert resultado["missing"] == []


async def test_validacao_detecta_modelos_faltando():
    mock_settings = SimpleNamespace(
        openrouter_base_url="http://localhost:11434/v1",
        model_economico="llama3.1:8b",
        model_medico="cniongolo/biomistral:latest",
        model_premium="llama3.1:8b",
        model_rag="cniongolo/biomistral:latest",
    )
    mock_response = MagicMock()
    mock_response.raise_for_status = MagicMock()
    mock_response.json.return_value = {
        "models": [{"name": "llama3.1:8b"}],
    }

    with (
        patch("app.main.settings", mock_settings),
        patch("app.main.httpx.AsyncClient") as mock_client_cls,
    ):
        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_response)
        mock_client_cls.return_value.__aenter__.return_value = mock_client

        resultado = await validar_modelos_ollama()

    assert resultado["status"] == "missing"
    assert resultado["missing"] == ["cniongolo/biomistral:latest"]


async def test_validacao_retorna_ok_quando_modelos_existem():
    mock_settings = SimpleNamespace(
        openrouter_base_url="http://localhost:11434/v1",
        model_economico="llama3.1:8b",
        model_medico="cniongolo/biomistral:latest",
        model_premium="llama3.1:8b",
        model_rag="cniongolo/biomistral:latest",
    )
    mock_response = MagicMock()
    mock_response.raise_for_status = MagicMock()
    mock_response.json.return_value = {
        "models": [
            {"name": "llama3.1:8b"},
            {"name": "cniongolo/biomistral:latest"},
        ],
    }

    with (
        patch("app.main.settings", mock_settings),
        patch("app.main.httpx.AsyncClient") as mock_client_cls,
    ):
        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_response)
        mock_client_cls.return_value.__aenter__.return_value = mock_client

        resultado = await validar_modelos_ollama()

    assert resultado["status"] == "ok"
    assert resultado["missing"] == []
