"""Servico de integracao com WhatsApp via Evolution API.

Responsavel por:
- Parsing de payloads do webhook Evolution API
- Envio de mensagens de resposta via Evolution API
- Templates de mensagem para notificacoes
"""

from datetime import date, time

import httpx
import structlog

from app.core.config import settings

log = structlog.get_logger(__name__)


def extrair_mensagem_evolution(payload: dict) -> dict | None:
    """Extrai mensagem do payload Evolution API.

    Retorna None se:
    - Evento nao e mensagem
    - Mensagem e do proprio bot (fromMe=True)
    """
    evento = payload.get("event", "")
    if evento != "messages.upsert":
        return None

    data = payload.get("data", {})
    key = data.get("key", {})

    # Ignorar mensagens enviadas pelo bot
    if key.get("fromMe", False):
        return None

    # Extrair telefone (remover @s.whatsapp.net)
    remote_jid = key.get("remoteJid", "")
    telefone = remote_jid.split("@")[0]

    # Extrair texto da mensagem
    message = data.get("message", {})
    mensagem = message.get("conversation")

    if not mensagem:
        extended = message.get("extendedTextMessage", {})
        mensagem = extended.get("text")

    if not mensagem:
        return None

    return {
        "telefone": telefone,
        "mensagem": mensagem,
        "from_me": False,
        "message_id": key.get("id"),
    }


async def enviar_mensagem_whatsapp(
    telefone: str,
    mensagem: str,
) -> bool:
    """Envia mensagem de texto via Evolution API.

    Returns:
        True se enviada com sucesso, False caso contrario.
    """
    url = f"{settings.evolution_api_url}/message/sendText/{settings.whatsapp_instance}"

    headers = {
        "Content-Type": "application/json",
        "apikey": settings.evolution_api_key,
    }

    payload = {
        "number": telefone,
        "text": mensagem,
    }

    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(url, json=payload, headers=headers)

        if response.status_code == 200:
            log.info(
                "whatsapp_mensagem_enviada",
                telefone=telefone[:5] + "***",
            )
            return True

        log.warning(
            "whatsapp_envio_falhou",
            status_code=response.status_code,
            telefone=telefone[:5] + "***",
        )
        return False

    except httpx.HTTPError as e:
        log.error(
            "whatsapp_erro_envio",
            erro=str(e),
            telefone=telefone[:5] + "***",
        )
        return False


# ============================================================
# Templates de mensagem
# ============================================================

def _formatar_data(d: date) -> str:
    return d.strftime("%d/%m/%Y")


def _formatar_hora(h: time) -> str:
    return h.strftime("%H:%M")


def template_confirmacao_consulta(
    paciente_nome: str,
    medico_nome: str,
    especialidade: str,
    data: date,
    hora: time,
    link_cancelamento: str | None = None,
) -> str:
    """Template de confirmacao de agendamento."""
    msg = (
        f"Ola {paciente_nome}! Sua consulta foi confirmada.\n\n"
        f"Medico: {medico_nome}\n"
        f"Especialidade: {especialidade}\n"
        f"Data: {_formatar_data(data)}\n"
        f"Horario: {_formatar_hora(hora)}\n"
    )
    if link_cancelamento:
        msg += f"\nPara cancelar: {link_cancelamento}"
    return msg


def template_lembrete_consulta(
    paciente_nome: str,
    medico_nome: str,
    especialidade: str,
    data: date,
    hora: time,
    link_confirmacao: str | None = None,
    link_cancelamento: str | None = None,
) -> str:
    """Template de lembrete de consulta (D-1 / H-2)."""
    msg = (
        f"Ola {paciente_nome}! Lembrete da sua consulta:\n\n"
        f"Medico: {medico_nome}\n"
        f"Especialidade: {especialidade}\n"
        f"Data: {_formatar_data(data)}\n"
        f"Horario: {_formatar_hora(hora)}\n"
    )
    if link_confirmacao:
        msg += f"\nConfirmar presenca: {link_confirmacao}"
    if link_cancelamento:
        msg += f"\nCancelar: {link_cancelamento}"
    return msg


def template_cancelamento_consulta(
    paciente_nome: str,
    medico_nome: str,
    data: date,
    hora: time,
) -> str:
    """Template de confirmacao de cancelamento."""
    return (
        f"Ola {paciente_nome}! Sua consulta foi cancelada.\n\n"
        f"Medico: {medico_nome}\n"
        f"Data: {_formatar_data(data)}\n"
        f"Horario: {_formatar_hora(hora)}\n\n"
        f"Para reagendar, acesse nosso portal ou inicie uma conversa."
    )
