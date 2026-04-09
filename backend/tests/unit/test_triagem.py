"""Testes do servico de triagem (T17)."""

import pytest

from app.models.consulta import ConsultaUrgencia
from app.services.ia.triagem import (
    MENSAGEM_EMERGENCIA,
    classificar_urgencia,
    detectar_emergencia,
)


# ============================================================
# Deteccao de emergencia
# ============================================================

def test_detectar_dor_no_peito():
    """RF: 'dor no peito' e EMERGENCIA."""
    assert detectar_emergencia("Estou com dor no peito forte") is True


def test_detectar_falta_de_ar():
    """RF: 'falta de ar' e EMERGENCIA."""
    assert detectar_emergencia("Tenho falta de ar constante") is True


def test_detectar_avc():
    """RF: 'AVC' e EMERGENCIA."""
    assert detectar_emergencia("Acho que estou tendo um AVC") is True


def test_detectar_convulsao():
    """RF: 'convulsao' e EMERGENCIA."""
    assert detectar_emergencia("Meu filho teve convulsao") is True


def test_detectar_sangramento_intenso():
    """RF: 'sangramento intenso' e EMERGENCIA."""
    assert detectar_emergencia("Estou com sangramento intenso") is True


def test_detectar_desmaio():
    """RF: 'desmaiei' e EMERGENCIA."""
    assert detectar_emergencia("Eu desmaiei agora ha pouco") is True


def test_detectar_paralisia():
    """RF: 'paralisia' e EMERGENCIA."""
    assert detectar_emergencia("Sinto paralisia no braco") is True


def test_nao_detectar_sintomas_normais():
    """Edge case: sintomas comuns NAO sao emergencia."""
    assert detectar_emergencia("Estou com dor de cabeca leve") is False


def test_deteccao_case_insensitive():
    """RF: deteccao funciona com qualquer case."""
    assert detectar_emergencia("DOR NO PEITO") is True
    assert detectar_emergencia("Dor No Peito") is True


# ============================================================
# Classificacao de urgencia
# ============================================================

def test_emergencia_bloqueia_agendamento():
    """RF: EMERGENCIA bloqueia agendamento e exibe SAMU 192."""
    resultado = classificar_urgencia("Estou com dor no peito intensa")

    assert resultado["urgencia"] == ConsultaUrgencia.EMERGENCIA
    assert resultado["pode_agendar"] is False
    assert "192" in resultado["mensagem"]
    assert "SAMU" in resultado["mensagem"]


def test_urgencia_baixa_para_checkup():
    """RF: Check-up simples tem urgencia BAIXA."""
    resultado = classificar_urgencia("Quero fazer um check-up geral")

    assert resultado["urgencia"] == ConsultaUrgencia.BAIXA
    assert resultado["pode_agendar"] is True


def test_urgencia_alta_intensidade_8():
    """RF: Intensidade >= 8 classifica como ALTA."""
    resultado = classificar_urgencia(
        "Dor de cabeca", intensidade=8
    )

    assert resultado["urgencia"] == ConsultaUrgencia.ALTA
    assert resultado["priorizar_mesmo_dia"] is True


def test_urgencia_media_intensidade_5():
    """RF: Intensidade >= 5 classifica como MEDIA."""
    resultado = classificar_urgencia(
        "Dor nas costas", intensidade=5
    )

    assert resultado["urgencia"] == ConsultaUrgencia.MEDIA


def test_urgencia_alta_febre_alta():
    """RF: 'febre alta' classifica como ALTA."""
    resultado = classificar_urgencia("Estou com febre alta ha 2 dias")

    assert resultado["urgencia"] == ConsultaUrgencia.ALTA
    assert resultado["priorizar_mesmo_dia"] is True


def test_urgencia_media_sintoma_recente():
    """RF: Sintoma com menos de 1 dia eleva para MEDIA."""
    resultado = classificar_urgencia(
        "Comecou hoje uma dor no joelho", duracao_dias=0
    )

    assert resultado["urgencia"] == ConsultaUrgencia.MEDIA
