"""Servico de notificacao por e-mail via SendGrid HTTP API.

Envia emails transacionais (confirmacao, lembrete, cancelamento).
Usa httpx direto — sem dependencia extra de sendgrid SDK.
"""

from datetime import date, time

import httpx
import structlog

from app.core.config import settings

log = structlog.get_logger(__name__)

SENDGRID_API_URL = "https://api.sendgrid.com/v3/mail/send"


def _formatar_data(d: date) -> str:
    return d.strftime("%d/%m/%Y")


def _formatar_hora(h: time) -> str:
    return h.strftime("%H:%M")


async def enviar_email(
    destinatario: str,
    assunto: str,
    corpo_html: str,
) -> bool:
    """Envia email via SendGrid HTTP API.

    Returns:
        True se enviado com sucesso (202), False caso contrario.
    """
    headers = {
        "Authorization": f"Bearer {settings.sendgrid_api_key}",
        "Content-Type": "application/json",
    }

    payload = {
        "personalizations": [
            {"to": [{"email": destinatario}]}
        ],
        "from": {"email": settings.sendgrid_from_email or "noreply@medbot.app"},
        "subject": assunto,
        "content": [
            {"type": "text/html", "value": corpo_html}
        ],
    }

    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                SENDGRID_API_URL,
                json=payload,
                headers=headers,
            )

        if response.status_code == 202:
            log.info("email_enviado", destinatario=destinatario, assunto=assunto)
            return True

        log.warning(
            "email_envio_falhou",
            status_code=response.status_code,
            destinatario=destinatario,
        )
        return False

    except httpx.HTTPError as e:
        log.error("email_erro_envio", erro=str(e), destinatario=destinatario)
        return False


# ============================================================
# Templates de email
# ============================================================

def template_email_confirmacao(
    paciente_nome: str,
    medico_nome: str,
    especialidade: str,
    data: date,
    hora: time,
    link_cancelamento: str | None = None,
) -> tuple[str, str]:
    """Template de confirmacao de consulta.

    Returns:
        Tuple (assunto, corpo_html)
    """
    assunto = "MedBot - Consulta Confirmada"

    corpo = f"""
    <h2>Consulta Confirmada</h2>
    <p>Ola {paciente_nome}!</p>
    <p>Sua consulta foi agendada com sucesso.</p>
    <table>
        <tr><td><strong>Medico:</strong></td><td>{medico_nome}</td></tr>
        <tr><td><strong>Especialidade:</strong></td><td>{especialidade}</td></tr>
        <tr><td><strong>Data:</strong></td><td>{_formatar_data(data)}</td></tr>
        <tr><td><strong>Horario:</strong></td><td>{_formatar_hora(hora)}</td></tr>
    </table>
    """
    if link_cancelamento:
        corpo += f'<p><a href="{link_cancelamento}">Cancelar consulta</a></p>'

    return assunto, corpo


def template_email_lembrete(
    paciente_nome: str,
    medico_nome: str,
    especialidade: str,
    data: date,
    hora: time,
    link_confirmacao: str | None = None,
    link_cancelamento: str | None = None,
) -> tuple[str, str]:
    """Template de lembrete de consulta.

    Returns:
        Tuple (assunto, corpo_html)
    """
    assunto = "MedBot - Lembrete de Consulta"

    corpo = f"""
    <h2>Lembrete de Consulta</h2>
    <p>Ola {paciente_nome}!</p>
    <p>Sua consulta esta chegando.</p>
    <table>
        <tr><td><strong>Medico:</strong></td><td>{medico_nome}</td></tr>
        <tr><td><strong>Especialidade:</strong></td><td>{especialidade}</td></tr>
        <tr><td><strong>Data:</strong></td><td>{_formatar_data(data)}</td></tr>
        <tr><td><strong>Horario:</strong></td><td>{_formatar_hora(hora)}</td></tr>
    </table>
    """
    if link_confirmacao:
        corpo += f'<p><a href="{link_confirmacao}">Confirmar presenca</a></p>'
    if link_cancelamento:
        corpo += f'<p><a href="{link_cancelamento}">Cancelar consulta</a></p>'

    return assunto, corpo
