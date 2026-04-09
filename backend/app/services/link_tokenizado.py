"""Servico de links tokenizados para acoes de consulta.

Gera JWT com TTL para confirmar ou cancelar consultas
via link unico (enviado por WhatsApp/email).
"""

from datetime import datetime, timedelta, timezone

import structlog
from jose import JWTError, jwt

from app.core.config import settings

log = structlog.get_logger(__name__)

ALGORITHM = "HS256"
DEFAULT_TTL_HORAS = 48


class TokenAcaoInvalidoError(Exception):
    pass


class TokenAcaoExpiradoError(Exception):
    pass


def criar_token_acao(
    consulta_id: int,
    acao: str,
    ttl_horas: int = DEFAULT_TTL_HORAS,
) -> str:
    """Cria JWT para acao sobre consulta.

    Args:
        consulta_id: ID da consulta.
        acao: "confirmar" ou "cancelar".
        ttl_horas: Tempo de vida em horas (default 48h).

    Returns:
        Token JWT assinado.
    """
    now = datetime.now(timezone.utc)
    payload = {
        "consulta_id": consulta_id,
        "acao": acao,
        "type": "acao_consulta",
        "iat": now,
        "exp": now + timedelta(hours=ttl_horas),
    }

    token = jwt.encode(payload, settings.secret_key, algorithm=ALGORITHM)
    log.info(
        "token_acao_criado",
        consulta_id=consulta_id,
        acao=acao,
        ttl_horas=ttl_horas,
    )
    return token


def validar_token_acao(token: str) -> dict:
    """Valida e decodifica token de acao.

    Returns:
        Dict com consulta_id e acao.

    Raises:
        TokenAcaoExpiradoError: Token expirado.
        TokenAcaoInvalidoError: Token invalido ou corrompido.
    """
    if not token:
        raise TokenAcaoInvalidoError("Token vazio")

    try:
        payload = jwt.decode(token, settings.secret_key, algorithms=[ALGORITHM])
    except jwt.ExpiredSignatureError:
        raise TokenAcaoExpiradoError("Token expirado")
    except JWTError:
        raise TokenAcaoInvalidoError("Token invalido")

    if payload.get("type") != "acao_consulta":
        raise TokenAcaoInvalidoError("Token nao e de acao")

    return {
        "consulta_id": payload["consulta_id"],
        "acao": payload["acao"],
    }
