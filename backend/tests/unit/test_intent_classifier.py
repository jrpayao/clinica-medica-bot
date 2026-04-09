"""Testes do classificador de intencao (T51).

TDAD: testes escritos ANTES da implementacao.
"""

import pytest

from app.services.ia.intent_classifier import (
    TipoIntencao,
    classificar_intencao,
)


# ============================================================
# Intencao: saude
# ============================================================

def test_sintoma_dor_de_cabeca_e_saude():
    """RF: mensagem com sintoma fisico deve ser classificada como saude."""
    resultado = classificar_intencao("Estou com dor de cabeca forte")
    assert resultado["tipo"] == TipoIntencao.SAUDE


def test_sintoma_febre_e_saude():
    """RF: febre e sintoma de saude."""
    resultado = classificar_intencao("Tenho febre ha dois dias")
    assert resultado["tipo"] == TipoIntencao.SAUDE


def test_sintoma_nausea_e_saude():
    """RF: nausea e sintoma de saude."""
    resultado = classificar_intencao("Sinto nausea e tontura")
    assert resultado["tipo"] == TipoIntencao.SAUDE


def test_sintoma_dor_no_peito_e_saude():
    """RF: dor no peito e saude (mesmo sendo emergencia - triagem decide urgencia)."""
    resultado = classificar_intencao("Estou sentindo dor no peito")
    assert resultado["tipo"] == TipoIntencao.SAUDE


def test_descricao_sintoma_longo_e_saude():
    """RF: descricao detalhada de sintomas e saude."""
    resultado = classificar_intencao("Ha tres dias estou com tosse seca e cansaco excessivo")
    assert resultado["tipo"] == TipoIntencao.SAUDE


# ============================================================
# Intencao: agendamento
# ============================================================

def test_quero_marcar_consulta_e_agendamento():
    """RF: pedido direto de agendamento e agendamento."""
    resultado = classificar_intencao("Quero marcar uma consulta")
    assert resultado["tipo"] == TipoIntencao.AGENDAMENTO


def test_agendar_com_medico_e_agendamento():
    """RF: mencao de agendar com medico e agendamento."""
    resultado = classificar_intencao("Preciso agendar com um cardiologista")
    assert resultado["tipo"] == TipoIntencao.AGENDAMENTO


def test_ver_horarios_e_agendamento():
    """RF: pedido de horarios disponiveis e agendamento."""
    resultado = classificar_intencao("Quais horarios estao disponiveis?")
    assert resultado["tipo"] == TipoIntencao.AGENDAMENTO


def test_cancelar_consulta_e_agendamento():
    """RF: cancelamento e agendamento."""
    resultado = classificar_intencao("Preciso cancelar minha consulta de amanha")
    assert resultado["tipo"] == TipoIntencao.AGENDAMENTO


# ============================================================
# Intencao: geral
# ============================================================

def test_ola_e_geral():
    """RF: saudacao simples e geral."""
    resultado = classificar_intencao("Ola, boa tarde!")
    assert resultado["tipo"] == TipoIntencao.GERAL


def test_pergunta_generica_e_geral():
    """Edge case: pergunta sem contexto medico e geral."""
    resultado = classificar_intencao("Quanto custa uma consulta?")
    assert resultado["tipo"] == TipoIntencao.GERAL


def test_fora_de_escopo_e_geral():
    """Edge case: mensagem fora de escopo medico e geral."""
    resultado = classificar_intencao("Qual e a previsao do tempo?")
    assert resultado["tipo"] == TipoIntencao.GERAL


def test_mensagem_vazia_e_geral():
    """Edge case: mensagem vazia classifica como geral."""
    resultado = classificar_intencao("")
    assert resultado["tipo"] == TipoIntencao.GERAL


# ============================================================
# Estrutura do resultado
# ============================================================

def test_resultado_contem_tipo_e_confianca():
    """RF: resultado deve ter tipo e confianca."""
    resultado = classificar_intencao("Estou com dor")
    assert "tipo" in resultado
    assert "confianca" in resultado
    assert isinstance(resultado["confianca"], float)
    assert 0.0 <= resultado["confianca"] <= 1.0


def test_case_insensitive():
    """RF: classificacao e case-insensitive."""
    resultado_lower = classificar_intencao("dor de cabeca")
    resultado_upper = classificar_intencao("DOR DE CABECA")
    assert resultado_lower["tipo"] == resultado_upper["tipo"]
