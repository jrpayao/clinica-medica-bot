"""Testes do roteador de modelos IA (T15)."""

import pytest
from unittest.mock import patch

from app.core.config import settings
from app.services.ia.router import selecionar_modelo, obter_api_key


def test_saudacao_usa_modelo_economico():
    """RF: feature=saudacao usa llama."""
    modelo = selecionar_modelo("saudacao")
    assert modelo == settings.model_economico


def test_coleta_dados_usa_modelo_economico():
    """RF: feature=coleta_dados usa llama."""
    modelo = selecionar_modelo("coleta_dados")
    assert modelo == settings.model_economico


def test_triagem_clinica_usa_modelo_medico():
    """RF: feature=triagem_clinica usa biomistral."""
    modelo = selecionar_modelo("triagem_clinica")
    assert modelo == settings.model_medico


def test_rag_protocolo_usa_modelo_rag():
    """RF: feature=rag_protocolo usa modelo RAG configurado."""
    modelo = selecionar_modelo("rag_protocolo")
    assert modelo == settings.model_rag


def test_caso_complexo_usa_claude():
    """RF: feature=caso_complexo usa claude-sonnet."""
    modelo = selecionar_modelo("caso_complexo")
    assert modelo == settings.model_premium


def test_agendamento_usa_llama():
    """RF: feature=agendamento usa llama."""
    modelo = selecionar_modelo("agendamento")
    assert modelo == settings.model_economico


def test_feature_desconhecida_usa_default():
    """Edge case: feature desconhecida usa modelo economico."""
    modelo = selecionar_modelo("feature_inexistente")
    assert modelo == settings.model_economico


def test_obter_api_key_vazia_lanca_erro():
    """Seguranca: API key vazia lanca ValueError."""
    with patch("app.services.ia.router.settings") as mock_settings:
        mock_settings.openrouter_api_key = ""
        with pytest.raises(ValueError, match="OPENROUTER_API_KEY"):
            obter_api_key()
