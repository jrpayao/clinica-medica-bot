"""Testes das validacoes de robustez do fluxo LLM (T54).

TDAD: testes escritos ANTES da implementacao.
"""

import pytest

from app.services.ia.robustez import (
    FALLBACK_MESSAGE,
    MAX_PERGUNTAS_COLETA,
    extrair_json_llm,
    validar_especialidade,
    verificar_limite_perguntas,
)
from app.services.ia.prompts import ESPECIALIDADES_WHITELIST


# ============================================================
# extrair_json_llm — retry automatico
# ============================================================

def test_json_valido_retorna_dict():
    """RF: JSON valido retorna dict diretamente."""
    entrada = '{"fase": "coleta", "pergunta": "Quanto tempo?", "especialidades": [], "justificativa": "ok"}'
    resultado = extrair_json_llm(entrada)
    assert isinstance(resultado, dict)
    assert resultado["fase"] == "coleta"


def test_json_com_texto_extra_extrai_corretamente():
    """RF: JSON embutido em texto deve ser extraido."""
    entrada = 'Claro, aqui esta: {"fase": "sugestao", "pergunta": null, "especialidades": ["Cardiologia"], "justificativa": "dor no peito"}'
    resultado = extrair_json_llm(entrada)
    assert resultado is not None
    assert resultado["fase"] == "sugestao"


def test_json_invalido_retorna_none():
    """RF: JSON completamente invalido retorna None (trigger retry)."""
    resultado = extrair_json_llm("Desculpe, nao entendi a pergunta.")
    assert resultado is None


def test_json_mal_formado_retorna_none():
    """Edge case: JSON incompleto retorna None."""
    resultado = extrair_json_llm('{"fase": "coleta", "pergunta":')
    assert resultado is None


def test_string_vazia_retorna_none():
    """Edge case: string vazia retorna None."""
    resultado = extrair_json_llm("")
    assert resultado is None


# ============================================================
# validar_especialidade — whitelist
# ============================================================

def test_especialidade_valida_retorna_nome():
    """RF: especialidade na whitelist retorna o nome original."""
    resultado = validar_especialidade("Cardiologia")
    assert resultado == "Cardiologia"


def test_especialidade_invalida_retorna_clinica_geral():
    """RF: especialidade fora da whitelist retorna Clinica Geral."""
    resultado = validar_especialidade("Homeopatia")
    assert resultado == "Clinica Geral"


def test_especialidade_vazia_retorna_clinica_geral():
    """Edge case: especialidade vazia retorna Clinica Geral."""
    resultado = validar_especialidade("")
    assert resultado == "Clinica Geral"


def test_especialidade_case_insensitive():
    """RF: validacao e case-insensitive."""
    resultado = validar_especialidade("cardiologia")
    assert resultado == "Cardiologia"


def test_lista_especialidades_todas_validas():
    """RF: todas as especialidades da whitelist sao validas."""
    for esp in ESPECIALIDADES_WHITELIST:
        assert validar_especialidade(esp) == esp


# ============================================================
# verificar_limite_perguntas
# ============================================================

def test_limite_maximo_e_3():
    """RF: limite de perguntas na fase COLETANDO_SINTOMAS e 3."""
    assert MAX_PERGUNTAS_COLETA == 3


def test_abaixo_do_limite_pode_perguntar():
    """RF: abaixo do limite, pode fazer mais perguntas."""
    assert verificar_limite_perguntas(2) is True


def test_no_limite_pode_ainda_perguntar():
    """RF: exatamente no limite (3), ainda pode fazer a terceira."""
    assert verificar_limite_perguntas(3) is True


def test_acima_do_limite_deve_avancar():
    """RF: acima do limite, nao pode mais perguntar — deve avancar de estado."""
    assert verificar_limite_perguntas(4) is False


def test_zero_perguntas_pode_perguntar():
    """Edge case: sem perguntas ainda, sempre pode perguntar."""
    assert verificar_limite_perguntas(0) is True


# ============================================================
# Mensagem de fallback
# ============================================================

def test_fallback_message_nao_vazia():
    """RF: fallback deve ter mensagem util ao paciente."""
    assert len(FALLBACK_MESSAGE) > 10


def test_fallback_message_e_string():
    """RF: fallback deve ser string."""
    assert isinstance(FALLBACK_MESSAGE, str)
