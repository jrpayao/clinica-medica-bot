"""Testes do link tokenizado para confirmacao/cancelamento (T33)."""

import pytest
from datetime import timedelta
from unittest.mock import patch

from app.services.link_tokenizado import (
    criar_token_acao,
    validar_token_acao,
    TokenAcaoInvalidoError,
    TokenAcaoExpiradoError,
)


# ============================================================
# Criar token de acao
# ============================================================

def test_criar_token_confirmacao():
    """RF: Token de confirmacao contem consulta_id e acao."""
    token = criar_token_acao(consulta_id=42, acao="confirmar")

    assert token is not None
    assert isinstance(token, str)
    assert len(token) > 20


def test_criar_token_cancelamento():
    """RF: Token de cancelamento contem consulta_id e acao."""
    token = criar_token_acao(consulta_id=42, acao="cancelar")

    assert token is not None


# ============================================================
# Validar token de acao
# ============================================================

def test_validar_token_correto():
    """RF: Token valido retorna consulta_id e acao."""
    token = criar_token_acao(consulta_id=99, acao="confirmar")

    dados = validar_token_acao(token)

    assert dados["consulta_id"] == 99
    assert dados["acao"] == "confirmar"


def test_validar_token_cancelar():
    """RF: Token de cancelamento e valido."""
    token = criar_token_acao(consulta_id=50, acao="cancelar")

    dados = validar_token_acao(token)

    assert dados["consulta_id"] == 50
    assert dados["acao"] == "cancelar"


def test_validar_token_expirado():
    """RF: Token expirado lanca erro."""
    from datetime import datetime, timezone
    from jose import jwt as jose_jwt
    from app.core.config import settings

    # Criar token com exp no passado
    payload = {
        "consulta_id": 42,
        "acao": "confirmar",
        "type": "acao_consulta",
        "iat": datetime.now(timezone.utc) - timedelta(hours=2),
        "exp": datetime.now(timezone.utc) - timedelta(hours=1),
    }
    token = jose_jwt.encode(payload, settings.secret_key, algorithm="HS256")

    with pytest.raises(TokenAcaoExpiradoError):
        validar_token_acao(token)


def test_validar_token_invalido():
    """Edge case: Token corrompido lanca erro."""
    with pytest.raises(TokenAcaoInvalidoError):
        validar_token_acao("token-invalido-corrompido")


def test_validar_token_vazio():
    """Edge case: Token vazio lanca erro."""
    with pytest.raises(TokenAcaoInvalidoError):
        validar_token_acao("")
