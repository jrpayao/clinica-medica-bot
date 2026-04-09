"""Testes da maquina de estados do chat (T52).

TDAD: testes escritos ANTES da implementacao.
"""

import pytest

from app.services.ia.state_machine import (
    ChatEstado,
    InvalidTransitionError,
    avancar_estado,
    pode_transitar,
    estado_inicial,
)


# ============================================================
# Valores dos estados
# ============================================================

def test_estados_sao_strings():
    """RF: estados devem ser strings para serializar no Redis."""
    assert isinstance(ChatEstado.START, str)
    assert isinstance(ChatEstado.COLETANDO_SINTOMAS, str)
    assert isinstance(ChatEstado.FINALIZADO, str)


def test_estado_inicial_e_start():
    """RF: toda sessao comeca no estado START."""
    assert estado_inicial() == ChatEstado.START


# ============================================================
# Transicoes validas
# ============================================================

def test_start_para_coletando_nome():
    """RF: START avanca para COLETANDO_NOME (fluxo guiado v2)."""
    assert pode_transitar(ChatEstado.START, ChatEstado.COLETANDO_NOME) is True


def test_start_nao_avanca_para_coletando_sintomas():
    """Fluxo v1 (COLETANDO_SINTOMAS) não é mais alcançável via START."""
    assert pode_transitar(ChatEstado.START, ChatEstado.COLETANDO_SINTOMAS) is False


def test_coletando_para_triagem():
    """RF: COLETANDO_SINTOMAS pode avancar para TRIAGEM."""
    assert pode_transitar(ChatEstado.COLETANDO_SINTOMAS, ChatEstado.TRIAGEM) is True


def test_triagem_para_sugestao():
    """RF: TRIAGEM pode avancar para SUGESTAO_ESPECIALIDADE."""
    assert pode_transitar(ChatEstado.TRIAGEM, ChatEstado.SUGESTAO_ESPECIALIDADE) is True


def test_sugestao_para_escolha_especialidade():
    """RF: SUGESTAO_ESPECIALIDADE -> ESCOLHA_ESPECIALIDADE."""
    assert pode_transitar(
        ChatEstado.SUGESTAO_ESPECIALIDADE, ChatEstado.ESCOLHA_ESPECIALIDADE
    ) is True


def test_escolha_especialidade_para_escolha_medico():
    """RF: ESCOLHA_ESPECIALIDADE -> ESCOLHA_MEDICO."""
    assert pode_transitar(
        ChatEstado.ESCOLHA_ESPECIALIDADE, ChatEstado.ESCOLHA_MEDICO
    ) is True


def test_escolha_medico_para_escolha_horario():
    """RF: ESCOLHA_MEDICO -> ESCOLHA_HORARIO."""
    assert pode_transitar(ChatEstado.ESCOLHA_MEDICO, ChatEstado.ESCOLHA_HORARIO) is True


def test_escolha_horario_para_confirmacao():
    """RF: ESCOLHA_HORARIO -> CONFIRMACAO."""
    assert pode_transitar(ChatEstado.ESCOLHA_HORARIO, ChatEstado.CONFIRMACAO) is True


def test_confirmacao_para_finalizado():
    """RF: CONFIRMACAO -> FINALIZADO."""
    assert pode_transitar(ChatEstado.CONFIRMACAO, ChatEstado.FINALIZADO) is True


# ============================================================
# Transicoes invalidas
# ============================================================

def test_start_para_finalizado_e_invalido():
    """RF: nao e possivel pular estados."""
    assert pode_transitar(ChatEstado.START, ChatEstado.FINALIZADO) is False


def test_finalizado_nao_tem_proximos():
    """RF: FINALIZADO nao tem transicoes de saida."""
    assert pode_transitar(ChatEstado.FINALIZADO, ChatEstado.START) is False


def test_coletando_para_confirmacao_e_invalido():
    """RF: nao pode pular TRIAGEM e SUGESTAO."""
    assert pode_transitar(
        ChatEstado.COLETANDO_SINTOMAS, ChatEstado.CONFIRMACAO
    ) is False


def test_triagem_para_escolha_medico_e_invalido():
    """RF: nao pode pular SUGESTAO_ESPECIALIDADE e ESCOLHA_ESPECIALIDADE."""
    assert pode_transitar(ChatEstado.TRIAGEM, ChatEstado.ESCOLHA_MEDICO) is False


# ============================================================
# avancar_estado
# ============================================================

def test_avancar_estado_retorna_novo_estado():
    """RF: avancar_estado retorna proximo estado valido."""
    novo = avancar_estado(ChatEstado.START, ChatEstado.COLETANDO_NOME)
    assert novo == ChatEstado.COLETANDO_NOME


def test_avancar_estado_invalido_lanca_excecao():
    """RF: transicao invalida lanca InvalidTransitionError."""
    with pytest.raises(InvalidTransitionError):
        avancar_estado(ChatEstado.START, ChatEstado.FINALIZADO)


def test_mensagem_erro_contem_estados():
    """RF: erro deve indicar de/para para debug."""
    with pytest.raises(InvalidTransitionError, match="START"):
        avancar_estado(ChatEstado.START, ChatEstado.CONFIRMACAO)


# ============================================================
# Fluxo completo
# ============================================================

def test_fluxo_completo_feliz():
    """RF: fluxo guiado v2 completo deve passar por todos os estados."""
    fluxo = [
        ChatEstado.START,
        ChatEstado.COLETANDO_NOME,
        ChatEstado.COLETANDO_CONVENIO,
        ChatEstado.OUVINDO_SINTOMAS,
        ChatEstado.SUGERINDO_ESPECIALIDADE,
        ChatEstado.APRESENTANDO_SLOTS,
        ChatEstado.COLETANDO_CONTATO,
        ChatEstado.CONFIRMANDO,
        ChatEstado.FINALIZADO,
    ]
    estado_atual = ChatEstado.START
    for proximo in fluxo[1:]:
        estado_atual = avancar_estado(estado_atual, proximo)
    assert estado_atual == ChatEstado.FINALIZADO
