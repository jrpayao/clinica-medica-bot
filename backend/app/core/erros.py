"""Envio de erros ao GlitchTip (ou Sentry), sem dados pessoais.

Liga com SENTRY_DSN; vazio, nada é enviado. Antes de qualquer evento sair do servidor, `limpar_evento`
mascara CPF, e-mail, telefone, o código do link da teleconsulta e tokens de acesso em todo o evento
(mensagem, exceção, URL, cabeçalhos, rastros), e descarta corpo de requisição e cookies (LGPD).
O SDK também roda sem variáveis locais e sem identificação do usuário.
"""

import re
from typing import Any

import sentry_sdk
import structlog
from sentry_sdk.integrations.celery import CeleryIntegration
from sentry_sdk.integrations.fastapi import FastApiIntegration
from sentry_sdk.integrations.starlette import StarletteIntegration

from app.core.config import settings

log = structlog.get_logger(__name__)

OCULTO = "[oculto]"

# Ordem importa: primeiro o que contém outros padrões (links e tokens), depois os dados soltos
_PADROES: tuple[tuple[re.Pattern, str], ...] = (
    # erros do SQLAlchemy trazem os valores da consulta (nome, CPF, código da sala...): saem inteiros
    (re.compile(r"\[parameters: .*?\](?=\s*(?:\n|\(Background|$))", re.S), "[parameters: " + OCULTO + "]"),
    (re.compile(r"(/teleconsulta/)[^/?#\s\"']+"), r"\1" + OCULTO),
    (re.compile(r"\beyJ[\w-]*\.[\w-]+\.[\w-]*"), OCULTO),                                   # JWT
    (re.compile(r"((?:jwt|token|access_token|senha|password|secret)=)[^&\s\"']+", re.I), r"\1" + OCULTO),
    (re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+"), OCULTO),                                  # e-mail
    (re.compile(r"\b\d{3}\.?\d{3}\.?\d{3}-?\d{2}\b"), OCULTO),                              # CPF
    (re.compile(r"(?<!\d)(?:\+?55\s?)?\(?\d{2}\)?\s?9?\d{4}-?\d{4}(?!\d)"), OCULTO),        # telefone
    (re.compile(r"(?<!\d)55\d{10,11}(?!\d)"), OCULTO),                                      # telefone internacional
)
_CABECALHOS_SENSIVEIS = {"authorization", "cookie", "x-api-key", "apikey", "proxy-authorization"}


def mascarar(texto: str) -> str:
    for padrao, troca in _PADROES:
        texto = padrao.sub(troca, texto)
    return texto


def _limpar(valor: Any) -> Any:
    if isinstance(valor, str):
        return mascarar(valor)
    if isinstance(valor, dict):
        return {chave: _limpar(item) for chave, item in valor.items()}
    if isinstance(valor, list | tuple):
        return [_limpar(item) for item in valor]
    return valor


def limpar_evento(evento: dict, _hint: dict | None = None) -> dict:
    """Remove dado pessoal e segredo de um evento (erro ou transação) antes do envio."""
    requisicao = evento.get("request")
    if isinstance(requisicao, dict):
        requisicao.pop("data", None)
        requisicao.pop("cookies", None)
        cabecalhos = requisicao.get("headers")
        if isinstance(cabecalhos, dict):
            requisicao["headers"] = {
                nome: valor for nome, valor in cabecalhos.items() if nome.lower() not in _CABECALHOS_SENSIVEIS
            }
    return _limpar(evento)


def _limpar_rastro(rastro: dict, _hint: dict | None = None) -> dict:
    return _limpar(rastro)


def iniciar(componente: str, transporte: Any = None) -> bool:
    """Liga o envio de erros para a API ou para o worker do Celery. Devolve se ficou ligado."""
    if not settings.sentry_dsn:
        return False
    sentry_sdk.init(
        dsn=settings.sentry_dsn,
        environment=settings.sentry_ambiente,
        server_name=componente,
        traces_sample_rate=settings.sentry_amostragem_traces,
        send_default_pii=False,
        include_local_variables=False,
        max_request_body_size="never",
        before_send=limpar_evento,
        before_send_transaction=limpar_evento,
        before_breadcrumb=_limpar_rastro,
        integrations=[StarletteIntegration(), FastApiIntegration(), CeleryIntegration()],
        transport=transporte,
    )
    log.info("envio_de_erros_ligado", componente=componente, ambiente=settings.sentry_ambiente)
    return True
