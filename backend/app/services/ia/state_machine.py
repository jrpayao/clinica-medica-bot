"""Maquina de estados formal do fluxo de chat — Fluxo Guiado v2.

Define os estados do fluxo guiado de agendamento e as transicoes validas.

Fluxo principal:
  START
  → COLETANDO_NOME
  → COLETANDO_CONVENIO
  → OUVINDO_SINTOMAS
  → SUGERINDO_ESPECIALIDADE
  → APRESENTANDO_SLOTS
  → COLETANDO_CONTATO
  → CONFIRMANDO
  → FINALIZADO

Estados legados mantidos para retrocompatibilidade de sessoes existentes:
  COLETANDO_SINTOMAS, TRIAGEM, SUGESTAO_ESPECIALIDADE,
  ESCOLHA_ESPECIALIDADE, ESCOLHA_MEDICO, ESCOLHA_HORARIO, CONFIRMACAO
"""

from enum import StrEnum

import structlog

log = structlog.get_logger(__name__)


class ChatEstado(StrEnum):
    # Fluxo guiado (v2)
    START = "START"
    COLETANDO_NOME = "COLETANDO_NOME"
    COLETANDO_CONVENIO = "COLETANDO_CONVENIO"
    OUVINDO_SINTOMAS = "OUVINDO_SINTOMAS"
    SUGERINDO_ESPECIALIDADE = "SUGERINDO_ESPECIALIDADE"
    APRESENTANDO_SLOTS = "APRESENTANDO_SLOTS"
    COLETANDO_CONTATO = "COLETANDO_CONTATO"
    CONFIRMANDO = "CONFIRMANDO"
    FINALIZADO = "FINALIZADO"

    # Legado (v1) — mantidos para sessões em andamento
    COLETANDO_SINTOMAS = "COLETANDO_SINTOMAS"
    TRIAGEM = "TRIAGEM"
    SUGESTAO_ESPECIALIDADE = "SUGESTAO_ESPECIALIDADE"
    ESCOLHA_ESPECIALIDADE = "ESCOLHA_ESPECIALIDADE"
    ESCOLHA_MEDICO = "ESCOLHA_MEDICO"
    ESCOLHA_HORARIO = "ESCOLHA_HORARIO"
    CONFIRMACAO = "CONFIRMACAO"


class InvalidTransitionError(Exception):
    """Lancada quando uma transicao de estado invalida e tentada."""


# Transicoes permitidas: de → {conjunto de proximos validos}
_VALID_TRANSITIONS: dict[ChatEstado, set[ChatEstado]] = {
    # Fluxo guiado (v2)
    ChatEstado.START: {ChatEstado.COLETANDO_NOME},
    ChatEstado.COLETANDO_NOME: {ChatEstado.COLETANDO_CONVENIO},
    ChatEstado.COLETANDO_CONVENIO: {ChatEstado.OUVINDO_SINTOMAS},
    ChatEstado.OUVINDO_SINTOMAS: {ChatEstado.SUGERINDO_ESPECIALIDADE},
    ChatEstado.SUGERINDO_ESPECIALIDADE: {ChatEstado.APRESENTANDO_SLOTS},
    ChatEstado.APRESENTANDO_SLOTS: {ChatEstado.COLETANDO_CONTATO},
    ChatEstado.COLETANDO_CONTATO: {ChatEstado.CONFIRMANDO},
    ChatEstado.CONFIRMANDO: {ChatEstado.FINALIZADO},
    ChatEstado.FINALIZADO: set(),

    # Fluxo legado (v1) — retrocompatibilidade
    ChatEstado.COLETANDO_SINTOMAS: {ChatEstado.TRIAGEM},
    ChatEstado.TRIAGEM: {ChatEstado.SUGESTAO_ESPECIALIDADE},
    ChatEstado.SUGESTAO_ESPECIALIDADE: {ChatEstado.ESCOLHA_ESPECIALIDADE},
    ChatEstado.ESCOLHA_ESPECIALIDADE: {ChatEstado.ESCOLHA_MEDICO},
    ChatEstado.ESCOLHA_MEDICO: {ChatEstado.ESCOLHA_HORARIO},
    ChatEstado.ESCOLHA_HORARIO: {ChatEstado.CONFIRMACAO},
    ChatEstado.CONFIRMACAO: {ChatEstado.FINALIZADO},
}


def estado_inicial() -> ChatEstado:
    """Retorna o estado inicial de toda nova sessao."""
    return ChatEstado.START


def pode_transitar(de: ChatEstado, para: ChatEstado) -> bool:
    proximos = _VALID_TRANSITIONS.get(de, set())
    return para in proximos


def avancar_estado(estado_atual: ChatEstado, proximo: ChatEstado) -> ChatEstado:
    """Avanca para o proximo estado se a transicao for valida.

    Raises:
        InvalidTransitionError: Se a transicao nao for permitida.
    """
    if not pode_transitar(estado_atual, proximo):
        raise InvalidTransitionError(
            f"Transicao invalida: {estado_atual} → {proximo}. "
            f"Transicoes validas de {estado_atual}: {_VALID_TRANSITIONS.get(estado_atual, set())}"
        )

    log.info("estado_chat_avancado", de=estado_atual, para=proximo)
    return proximo
