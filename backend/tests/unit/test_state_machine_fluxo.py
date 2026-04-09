"""Testes unitários — FSM fluxo guiado de 7 etapas.

Cobre:
- Novos estados existem em ChatEstado
- Fluxo guiado: START → COLETANDO_NOME → COLETANDO_CONVENIO →
  OUVINDO_SINTOMAS → SUGERINDO_ESPECIALIDADE →
  APRESENTANDO_SLOTS → COLETANDO_CONTATO → CONFIRMANDO → FINALIZADO
- Transições válidas do fluxo guiado funcionam
- Transições inválidas levantam InvalidTransitionError
- estado_inicial() retorna START
"""

import pytest

from app.services.ia.state_machine import (
    ChatEstado,
    InvalidTransitionError,
    avancar_estado,
    estado_inicial,
    pode_transitar,
)


class TestNovosEstados:
    def test_coletando_nome_existe(self):
        assert ChatEstado.COLETANDO_NOME == "COLETANDO_NOME"

    def test_coletando_convenio_existe(self):
        assert ChatEstado.COLETANDO_CONVENIO == "COLETANDO_CONVENIO"

    def test_ouvindo_sintomas_existe(self):
        assert ChatEstado.OUVINDO_SINTOMAS == "OUVINDO_SINTOMAS"

    def test_sugerindo_especialidade_existe(self):
        assert ChatEstado.SUGERINDO_ESPECIALIDADE == "SUGERINDO_ESPECIALIDADE"

    def test_apresentando_slots_existe(self):
        assert ChatEstado.APRESENTANDO_SLOTS == "APRESENTANDO_SLOTS"

    def test_coletando_contato_existe(self):
        assert ChatEstado.COLETANDO_CONTATO == "COLETANDO_CONTATO"

    def test_confirmando_existe(self):
        assert ChatEstado.CONFIRMANDO == "CONFIRMANDO"


class TestFluxoGuiadoTransicoes:
    def test_start_para_coletando_nome(self):
        resultado = avancar_estado(ChatEstado.START, ChatEstado.COLETANDO_NOME)
        assert resultado == ChatEstado.COLETANDO_NOME

    def test_coletando_nome_para_coletando_convenio(self):
        resultado = avancar_estado(ChatEstado.COLETANDO_NOME, ChatEstado.COLETANDO_CONVENIO)
        assert resultado == ChatEstado.COLETANDO_CONVENIO

    def test_coletando_convenio_para_ouvindo_sintomas(self):
        resultado = avancar_estado(ChatEstado.COLETANDO_CONVENIO, ChatEstado.OUVINDO_SINTOMAS)
        assert resultado == ChatEstado.OUVINDO_SINTOMAS

    def test_ouvindo_sintomas_para_sugerindo_especialidade(self):
        resultado = avancar_estado(ChatEstado.OUVINDO_SINTOMAS, ChatEstado.SUGERINDO_ESPECIALIDADE)
        assert resultado == ChatEstado.SUGERINDO_ESPECIALIDADE

    def test_sugerindo_especialidade_para_apresentando_slots(self):
        resultado = avancar_estado(ChatEstado.SUGERINDO_ESPECIALIDADE, ChatEstado.APRESENTANDO_SLOTS)
        assert resultado == ChatEstado.APRESENTANDO_SLOTS

    def test_apresentando_slots_para_coletando_contato(self):
        resultado = avancar_estado(ChatEstado.APRESENTANDO_SLOTS, ChatEstado.COLETANDO_CONTATO)
        assert resultado == ChatEstado.COLETANDO_CONTATO

    def test_coletando_contato_para_confirmando(self):
        resultado = avancar_estado(ChatEstado.COLETANDO_CONTATO, ChatEstado.CONFIRMANDO)
        assert resultado == ChatEstado.CONFIRMANDO

    def test_confirmando_para_finalizado(self):
        resultado = avancar_estado(ChatEstado.CONFIRMANDO, ChatEstado.FINALIZADO)
        assert resultado == ChatEstado.FINALIZADO

    def test_fluxo_completo_ponta_a_ponta(self):
        fluxo = [
            ChatEstado.COLETANDO_NOME,
            ChatEstado.COLETANDO_CONVENIO,
            ChatEstado.OUVINDO_SINTOMAS,
            ChatEstado.SUGERINDO_ESPECIALIDADE,
            ChatEstado.APRESENTANDO_SLOTS,
            ChatEstado.COLETANDO_CONTATO,
            ChatEstado.CONFIRMANDO,
            ChatEstado.FINALIZADO,
        ]
        estado = ChatEstado.START
        for proximo in fluxo:
            estado = avancar_estado(estado, proximo)
        assert estado == ChatEstado.FINALIZADO


class TestTransicoesInvalidas:
    def test_start_nao_pula_para_ouvindo_sintomas(self):
        with pytest.raises(InvalidTransitionError):
            avancar_estado(ChatEstado.START, ChatEstado.OUVINDO_SINTOMAS)

    def test_finalizado_nao_aceita_transicao(self):
        with pytest.raises(InvalidTransitionError):
            avancar_estado(ChatEstado.FINALIZADO, ChatEstado.START)

    def test_coletando_nome_nao_pula_convenio(self):
        with pytest.raises(InvalidTransitionError):
            avancar_estado(ChatEstado.COLETANDO_NOME, ChatEstado.OUVINDO_SINTOMAS)

    def test_estado_inicial_e_start(self):
        assert estado_inicial() == ChatEstado.START
