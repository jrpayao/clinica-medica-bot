"""Testes — telefone, pendências de resposta no WhatsApp e aviso à recepção (base do G15)."""

from unittest.mock import AsyncMock, patch

import pytest

from app.services import mensageria
from app.services.mensageria import (
    chave_telefone,
    limpar_pendencia,
    normalizar_telefone,
    obter_pendencia,
    registrar_pendencia,
)
from tests.fabrica import RedisFalso, criar_estabelecimento


@pytest.mark.parametrize(
    ("entrada", "esperado"),
    [
        ("(11) 98888-7777", "5511988887777"),
        ("11988887777", "5511988887777"),
        ("5511988887777", "5511988887777"),
        ("+55 11 98888-7777", "5511988887777"),
        ("1133334444", "551133334444"),
    ],
)
def test_normalizar_telefone_poe_no_formato_internacional(entrada, esperado):
    assert normalizar_telefone(entrada) == esperado


@pytest.mark.parametrize("entrada", [None, "", "123", "abc"])
def test_normalizar_telefone_invalido_devolve_none(entrada):
    assert normalizar_telefone(entrada) is None


def test_chave_telefone_ignora_o_nono_digito():
    """O WhatsApp entrega alguns números sem o 9: a chave precisa ser a mesma nos dois formatos."""
    assert chave_telefone("5531988887777") == chave_telefone("553188887777")
    assert chave_telefone("(31) 98888-7777") == chave_telefone("553188887777@s.whatsapp.net")


def test_chave_telefone_distingue_numeros_diferentes():
    assert chave_telefone("11988887777") != chave_telefone("11988887778")
    assert chave_telefone("11988887777") != chave_telefone("21988887777")


async def test_pendencia_e_recuperada_pelo_telefone_em_outro_formato():
    redis = RedisFalso()
    await registrar_pendencia(redis, "(11) 98888-7777", {"tipo": "fila", "fila_id": 7}, ttl=1800)

    assert await obter_pendencia(redis, "5511988887777") == {"tipo": "fila", "fila_id": 7}
    assert list(redis.ttl.values()) == [1800]


async def test_pendencia_limpa_nao_e_mais_devolvida():
    redis = RedisFalso()
    await registrar_pendencia(redis, "11988887777", {"tipo": "avaliacao"}, ttl=60)
    await limpar_pendencia(redis, "11988887777")

    assert await obter_pendencia(redis, "11988887777") is None


async def test_pendencia_sem_telefone_valido_nao_registra():
    redis = RedisFalso()
    assert await registrar_pendencia(redis, None, {"tipo": "fila"}, ttl=60) is False
    assert redis.dados == {}


async def test_enviar_whatsapp_usa_o_provedor_configurado():
    provedor = AsyncMock()
    provedor.enviar_mensagem = AsyncMock(return_value=True)
    with patch.object(mensageria, "get_whatsapp_provider", return_value=provedor):
        assert await mensageria.enviar_whatsapp("(11) 98888-7777", "oi") is True

    provedor.enviar_mensagem.assert_awaited_once_with("5511988887777", "oi")


async def test_enviar_whatsapp_sem_telefone_nao_chama_o_provedor():
    provedor = AsyncMock()
    with patch.object(mensageria, "get_whatsapp_provider", return_value=provedor):
        assert await mensageria.enviar_whatsapp(None, "oi") is False
    provedor.enviar_mensagem.assert_not_called()


async def test_notificar_recepcao_envia_para_o_email_da_unidade(db_session):
    est = await criar_estabelecimento(db_session, email="recepcao@clinica.com")
    with (
        patch.object(mensageria, "enviar_email", new=AsyncMock(return_value=True)) as enviar,
        patch.object(mensageria.settings, "sendgrid_api_key", "chave"),
    ):
        assert await mensageria.notificar_recepcao(db_session, est.id, "Assunto", "Corpo") is True

    assert enviar.await_args.kwargs["destinatario"] == "recepcao@clinica.com"


async def test_notificar_recepcao_sem_email_configurado_nao_envia(db_session):
    est = await criar_estabelecimento(db_session, email=None)
    with patch.object(mensageria, "enviar_email", new=AsyncMock(return_value=True)) as enviar:
        assert await mensageria.notificar_recepcao(db_session, est.id, "Assunto", "Corpo") is False
    enviar.assert_not_called()
