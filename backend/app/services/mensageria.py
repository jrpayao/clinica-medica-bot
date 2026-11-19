"""Mensagens que o sistema inicia (fila de espera, reagendamento, avaliação, resumo ao profissional).

Concentra três coisas usadas por todos esses fluxos:
- telefone em formato único, para enviar e para reconhecer quem respondeu;
- "pendência" por telefone no Redis: a pergunta que o sistema fez e cuja resposta o webhook deve tratar;
- aviso à recepção por e-mail.
"""

import json
import re

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.services.notificacao_service import enviar_email
from app.services.whatsapp.factory import get_whatsapp_provider

log = structlog.get_logger(__name__)

_PREFIXO_PENDENCIA = "wa:pendente:"


def normalizar_telefone(telefone: str | None) -> str | None:
    """Só dígitos, com o código do país: '(11) 98888-7777' → '5511988887777'."""
    digitos = re.sub(r"\D", "", (telefone or "").split("@")[0]).lstrip("0")
    if len(digitos) in (10, 11):
        return "55" + digitos
    if len(digitos) in (12, 13) and digitos.startswith("55"):
        return digitos
    return None


def chave_telefone(telefone: str | None) -> str | None:
    """Identidade do número independente do nono dígito (o WhatsApp entrega alguns sem ele)."""
    numero = normalizar_telefone(telefone)
    if numero is None:
        return None
    return numero[:4] + numero[-8:]


def mascarar_telefone(telefone: str | None) -> str:
    numero = normalizar_telefone(telefone) or ""
    return (numero[:4] + "*****" + numero[-2:]) if numero else "***"


async def enviar_whatsapp(telefone: str | None, mensagem: str) -> bool:
    """Envia pelo provedor configurado em WHATSAPP_PROVIDER. False se não há número ou o envio falhou."""
    numero = normalizar_telefone(telefone)
    if numero is None:
        return False
    return bool(await get_whatsapp_provider().enviar_mensagem(numero, mensagem))


async def registrar_pendencia(redis, telefone: str | None, dados: dict, ttl: int) -> bool:
    """Guarda a pergunta em aberto para o número. Uma por número: a mais recente substitui a anterior."""
    chave = chave_telefone(telefone)
    if chave is None:
        return False
    await redis.set(_PREFIXO_PENDENCIA + chave, json.dumps(dados), ex=ttl)
    return True


async def obter_pendencia(redis, telefone: str | None) -> dict | None:
    chave = chave_telefone(telefone)
    if chave is None:
        return None
    bruto = await redis.get(_PREFIXO_PENDENCIA + chave)
    if not bruto:
        return None
    try:
        return json.loads(bruto)
    except (TypeError, ValueError):
        return None


async def limpar_pendencia(redis, telefone: str | None) -> None:
    chave = chave_telefone(telefone)
    if chave is not None:
        await redis.delete(_PREFIXO_PENDENCIA + chave)


async def notificar_recepcao(
    db: AsyncSession, estabelecimento_id: int, assunto: str, corpo_html: str
) -> bool:
    """E-mail para a unidade (ou para o responsável, se a unidade não tem e-mail)."""
    from app.models.estabelecimento import EstabelecimentoSaude

    linha = (
        await db.execute(
            select(EstabelecimentoSaude.email, EstabelecimentoSaude.responsavel_email).where(
                EstabelecimentoSaude.id == estabelecimento_id
            )
        )
    ).first()
    destinatario = (linha[0] or linha[1]) if linha else None
    if not destinatario or not settings.sendgrid_api_key:
        log.warning(
            "recepcao_nao_notificada",
            estabelecimento_id=estabelecimento_id,
            assunto=assunto,
            motivo="sem_email" if not destinatario else "email_nao_configurado",
        )
        return False
    return await enviar_email(destinatario=destinatario, assunto=assunto, corpo_html=corpo_html)
