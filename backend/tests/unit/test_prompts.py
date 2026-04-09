"""Testes dos prompts estruturados e parametros LLM por modelo (T53).

TDAD: testes escritos ANTES da implementacao.
"""

import pytest
from unittest.mock import patch

from app.services.ia.prompts import (
    ESPECIALIDADES_WHITELIST,
    SYSTEM_PROMPT_CONVERSA,
    SYSTEM_PROMPT_TRIAGEM,
    obter_params_llm,
    obter_prompt_sistema,
)


# ============================================================
# Prompts distintos por contexto
# ============================================================

def test_prompt_triagem_contem_instrucao_json():
    """RF: prompt de triagem deve exigir resposta em JSON estruturado."""
    assert "json" in SYSTEM_PROMPT_TRIAGEM.lower() or "JSON" in SYSTEM_PROMPT_TRIAGEM


def test_prompt_triagem_contem_campos_esperados():
    """RF: prompt de triagem deve mencionar os campos fase, pergunta, especialidades."""
    assert "fase" in SYSTEM_PROMPT_TRIAGEM
    assert "especialidades" in SYSTEM_PROMPT_TRIAGEM


def test_prompt_triagem_contem_regra_sem_diagnostico():
    """RF: triagem nunca deve dar diagnostico definitivo."""
    texto_lower = SYSTEM_PROMPT_TRIAGEM.lower()
    assert "diagnostico" in texto_lower or "diagnóstico" in texto_lower


def test_prompt_conversa_e_diferente_do_triagem():
    """RF: prompts devem ser distintos por contexto."""
    assert SYSTEM_PROMPT_CONVERSA != SYSTEM_PROMPT_TRIAGEM


def test_prompt_conversa_menciona_samu():
    """RF: todo prompt de conversa deve mencionar emergencia/SAMU."""
    assert "SAMU" in SYSTEM_PROMPT_CONVERSA or "192" in SYSTEM_PROMPT_CONVERSA


# ============================================================
# obter_prompt_sistema
# ============================================================

def test_obter_prompt_triagem_clinica():
    """RF: feature triagem_clinica usa prompt de triagem."""
    prompt = obter_prompt_sistema("triagem_clinica")
    assert prompt == SYSTEM_PROMPT_TRIAGEM


def test_obter_prompt_rag():
    """RF: feature rag_protocolo usa prompt de triagem."""
    prompt = obter_prompt_sistema("rag_protocolo")
    assert prompt == SYSTEM_PROMPT_TRIAGEM


def test_obter_prompt_saudacao():
    """RF: feature saudacao usa prompt de conversa."""
    prompt = obter_prompt_sistema("saudacao")
    assert prompt == SYSTEM_PROMPT_CONVERSA


def test_obter_prompt_agendamento():
    """RF: feature agendamento usa prompt de conversa."""
    prompt = obter_prompt_sistema("agendamento")
    assert prompt == SYSTEM_PROMPT_CONVERSA


def test_obter_prompt_feature_desconhecida():
    """Edge case: feature desconhecida usa prompt de conversa."""
    prompt = obter_prompt_sistema("feature_desconhecida")
    assert prompt == SYSTEM_PROMPT_CONVERSA


# ============================================================
# Parametros LLM por modelo (T53)
# ============================================================

def test_params_llama_temperature_0_6():
    """RF: LLaMA deve ter temperature=0.6 (conversacao)."""
    params = obter_params_llm("llama3.1:8b")
    assert params["temperature"] == 0.6


def test_params_biomistral_temperature_0_2():
    """RF: BioMistral deve ter temperature=0.2 (triagem clinica)."""
    params = obter_params_llm("cniongolo/biomistral:latest")
    assert params["temperature"] == 0.2


def test_params_biomistral_top_p():
    """RF: BioMistral deve ter top_p=0.9."""
    params = obter_params_llm("cniongolo/biomistral:latest")
    assert params.get("top_p") == 0.9


def test_params_biomistral_repeat_penalty():
    """RF: BioMistral deve ter repeat_penalty=1.1."""
    params = obter_params_llm("cniongolo/biomistral:latest")
    assert params.get("repeat_penalty") == 1.1


def test_params_modelo_desconhecido_usa_defaults():
    """Edge case: modelo desconhecido usa parametros conservadores."""
    params = obter_params_llm("modelo-inexistente")
    assert "temperature" in params
    assert 0.0 <= params["temperature"] <= 1.0


# ============================================================
# Whitelist de especialidades
# ============================================================

def test_whitelist_contem_clinica_geral():
    """RF: whitelist deve conter clinica geral como fallback."""
    nomes_lower = [e.lower() for e in ESPECIALIDADES_WHITELIST]
    assert any("cl" in e and "geral" in e for e in nomes_lower)


def test_whitelist_contem_cardiologia():
    """RF: whitelist deve conter cardiologia."""
    assert "Cardiologia" in ESPECIALIDADES_WHITELIST


def test_whitelist_contem_neurologia():
    """RF: whitelist deve conter neurologia."""
    assert "Neurologia" in ESPECIALIDADES_WHITELIST


def test_whitelist_nao_esta_vazia():
    """RF: whitelist deve ter ao menos 5 especialidades."""
    assert len(ESPECIALIDADES_WHITELIST) >= 5
