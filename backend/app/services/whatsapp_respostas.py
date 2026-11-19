"""Resposta do cliente a uma pergunta que o sistema fez pelo WhatsApp.

O webhook chama `tratar_resposta_pendente` antes de entregar a mensagem ao chat de agendamento:
se há uma pergunta em aberto para o número (oferta da fila, reagendamento, avaliação), a mensagem
é a resposta a ela.
"""

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.avaliacao_service import PRAZO_COMENTARIO_S, registrar_comentario, registrar_nota
from app.services.fila_espera_service import responder_oferta_fila
from app.services.ia.triagem import MENSAGEM_EMERGENCIA, detectar_emergencia
from app.services.mensageria import limpar_pendencia, obter_pendencia, registrar_pendencia
from app.services.reagendamento_service import responder_reagendamento

log = structlog.get_logger(__name__)


async def tratar_resposta_pendente(db: AsyncSession, redis, telefone: str, mensagem: str) -> str | None:
    """Devolve o texto a enviar ao cliente, ou None se não havia pergunta em aberto para o número."""
    pendencia = await obter_pendencia(redis, telefone)
    if not pendencia:
        return None

    # Regra de ouro do chat vale aqui também: emergência vem antes de qualquer fluxo
    if detectar_emergencia(mensagem):
        return MENSAGEM_EMERGENCIA

    tipo = pendencia.get("tipo")
    log.info("whatsapp_resposta_pendente", tipo=tipo)

    if tipo == "fila":
        texto, encerrada = await responder_oferta_fila(db, pendencia["fila_id"], mensagem)
    elif tipo == "reagendamento":
        texto, encerrada = await responder_reagendamento(db, pendencia["oferta_id"], mensagem)
    elif tipo == "avaliacao":
        texto, proxima = await registrar_nota(db, pendencia["atendimento_id"], mensagem)
        if isinstance(proxima, dict):
            await registrar_pendencia(redis, telefone, proxima, ttl=PRAZO_COMENTARIO_S)
            return texto
        encerrada = proxima != "manter"
    elif tipo == "avaliacao_comentario":
        texto, encerrada = await registrar_comentario(db, pendencia["avaliacao_id"], mensagem), True
    else:
        await limpar_pendencia(redis, telefone)
        return None

    if encerrada:
        await limpar_pendencia(redis, telefone)
    return texto
