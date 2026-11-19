"""Avaliação pós-atendimento e NPS (T99–T102).

24 horas depois de um atendimento realizado, o cliente recebe no WhatsApp um pedido de nota de 1 a 5,
seguido de um comentário opcional. Nota abaixo de 3 avisa a recepção.
"""

import re
from datetime import date, datetime, timedelta, timezone

import structlog
from sqlalchemy import Date, cast, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.atendimento import Atendimento, AtendimentoStatus
from app.models.atendimento_historico import AtendimentoStatusHistorico
from app.models.avaliacao import Avaliacao, AvaliacaoCanal
from app.models.cliente import Cliente
from app.models.profissional import Profissional
from app.models.slot import Slot
from app.services.mensageria import (
    enviar_whatsapp,
    notificar_recepcao,
    obter_pendencia,
    registrar_pendencia,
)

log = structlog.get_logger(__name__)

ESPERA_H = 24           # tempo entre o atendimento e o pedido de avaliação
JANELA_H = 48           # depois disso o pedido não é mais enviado nem a resposta esperada
NOTA_QUE_ALERTA = 3     # abaixo disso a recepção é avisada
PRAZO_COMENTARIO_S = 3600
MAX_COMENTARIO = 1000

PEDIDO_DE_NOTA = "Responda com uma nota de 1 a 5 (1 = muito ruim, 5 = excelente)."
_NOTA = re.compile(r"(?<!\d)([1-5])(?!\d)")
_QUALQUER_NUMERO = re.compile(r"\d+")


def calcular_nps(notas: list[int]) -> dict:
    """NPS em escala de 1 a 5: nota 5 é promotor, 4 é neutro, 1 a 3 é detrator."""
    total = len(notas)
    promotores = sum(1 for n in notas if n == 5)
    neutros = sum(1 for n in notas if n == 4)
    detratores = total - promotores - neutros
    return {
        "total": total,
        "promotores": promotores,
        "neutros": neutros,
        "detratores": detratores,
        "nps": round((promotores - detratores) * 100 / total) if total else None,
        "media": round(sum(notas) / total, 1) if total else None,
    }


async def solicitar_avaliacoes(
    db: AsyncSession, redis, agora_utc: datetime | None = None, enviar=enviar_whatsapp
) -> dict:
    """Pede a nota a quem foi atendido entre 24 e 72 horas atrás e ainda não avaliou."""
    agora_utc = agora_utc or datetime.now(timezone.utc)
    realizado_em = (
        select(
            AtendimentoStatusHistorico.atendimento_id.label("atendimento_id"),
            func.max(AtendimentoStatusHistorico.created_at).label("quando"),
        )
        .where(AtendimentoStatusHistorico.status_novo == AtendimentoStatus.REALIZADA)
        .group_by(AtendimentoStatusHistorico.atendimento_id)
        .subquery()
    )
    quando = func.coalesce(realizado_em.c.quando, Atendimento.updated_at)
    linhas = (
        await db.execute(
            select(Atendimento, Cliente, Profissional.nome, Slot.data)
            .join(Cliente, Atendimento.cliente_id == Cliente.id)
            .join(Profissional, Atendimento.profissional_id == Profissional.id)
            .join(Slot, Atendimento.slot_id == Slot.id)
            .outerjoin(realizado_em, realizado_em.c.atendimento_id == Atendimento.id)
            .outerjoin(Avaliacao, Avaliacao.atendimento_id == Atendimento.id)
            .where(
                Atendimento.status == AtendimentoStatus.REALIZADA,
                Atendimento.avaliacao_solicitada_em.is_(None),
                Avaliacao.id.is_(None),
                quando <= agora_utc - timedelta(hours=ESPERA_H),
                quando >= agora_utc - timedelta(hours=ESPERA_H + JANELA_H),
            )
            .order_by(quando)
        )
    ).all()

    enviados = 0
    for atendimento, cliente, profissional, data in linhas:
        if not cliente.telefone or await obter_pendencia(redis, cliente.telefone):
            continue
        primeiro_nome = (cliente.nome or "").split()[0] if cliente.nome else ""
        texto = (
            f"Olá, {primeiro_nome}! Como foi o seu atendimento com {profissional} "
            f"em {data.strftime('%d/%m/%Y')}?\n\n{PEDIDO_DE_NOTA}"
        )
        if not await enviar(cliente.telefone, texto):
            continue
        atendimento.avaliacao_solicitada_em = agora_utc
        await registrar_pendencia(
            redis, cliente.telefone,
            {"tipo": "avaliacao", "atendimento_id": atendimento.id},
            ttl=JANELA_H * 3600,
        )
        enviados += 1

    await db.flush()
    return {"enviados": enviados}


async def registrar_nota(
    db: AsyncSession,
    atendimento_id: int,
    mensagem: str,
    canal: AvaliacaoCanal = AvaliacaoCanal.WHATSAPP,
    avisar=notificar_recepcao,
):
    """Grava a nota respondida.

    Devolve (texto, próxima pendência): um dict para pedir o comentário, "manter" quando a
    resposta não foi uma nota, ou None quando não há mais o que perguntar.
    """
    numeros = _QUALQUER_NUMERO.findall(mensagem)
    encontrada = _NOTA.search(mensagem)
    if encontrada is None or len(numeros) != 1:
        return (f"Não entendi a nota. {PEDIDO_DE_NOTA}", "manter")
    nota = int(encontrada.group(1))

    atendimento = (
        await db.execute(select(Atendimento).where(Atendimento.id == atendimento_id))
    ).scalar_one_or_none()
    if atendimento is None:
        return ("Não encontrei o atendimento para registrar a avaliação.", None)
    existente = (
        await db.execute(select(Avaliacao.id).where(Avaliacao.atendimento_id == atendimento_id))
    ).scalar_one_or_none()
    if existente is not None:
        return ("Sua avaliação deste atendimento já foi registrada. Obrigado!", None)

    avaliacao = Avaliacao(
        atendimento_id=atendimento.id,
        cliente_id=atendimento.cliente_id,
        profissional_id=atendimento.profissional_id,
        estabelecimento_id=atendimento.estabelecimento_id,
        nota=nota,
        canal=canal,
    )
    db.add(avaliacao)
    await db.flush()
    log.info("avaliacao_registrada", atendimento_id=atendimento.id, nota=nota)

    if nota < NOTA_QUE_ALERTA:
        cliente = (await db.execute(select(Cliente).where(Cliente.id == atendimento.cliente_id))).scalar_one()
        await avisar(
            db,
            atendimento.estabelecimento_id,
            f"Avaliação baixa ({nota} de 5)",
            f"<p><strong>{cliente.nome}</strong> avaliou o atendimento com nota {nota} de 5.</p>"
            f"<p>Telefone: {cliente.telefone or 'não informado'}.</p>",
        )

    return (
        "Obrigado pela avaliação! Quer deixar um comentário? Escreva aqui ou responda *pular*.",
        {"tipo": "avaliacao_comentario", "avaliacao_id": avaliacao.id},
    )


async def registrar_comentario(db: AsyncSession, avaliacao_id: int, mensagem: str) -> str:
    texto = mensagem.strip()
    if texto.lower().strip(".! ") not in ("pular", "nao", "não", "sem comentario", "sem comentário"):
        avaliacao = (
            await db.execute(select(Avaliacao).where(Avaliacao.id == avaliacao_id))
        ).scalar_one_or_none()
        if avaliacao is not None and texto:
            avaliacao.comentario = texto[:MAX_COMENTARIO]
            await db.flush()
    return "Obrigado! Sua opinião ajuda a melhorar o atendimento."


def _no_periodo(consulta, estabelecimento_id: int, inicio: date, fim: date, profissional_id: int | None):
    consulta = consulta.where(
        Avaliacao.estabelecimento_id == estabelecimento_id,
        cast(Avaliacao.created_at, Date) >= inicio,
        cast(Avaliacao.created_at, Date) <= fim,
    )
    if profissional_id is not None:
        consulta = consulta.where(Avaliacao.profissional_id == profissional_id)
    return consulta


async def listar_avaliacoes(
    db: AsyncSession,
    estabelecimento_id: int,
    inicio: date,
    fim: date,
    profissional_id: int | None = None,
    limite: int = 50,
) -> list[dict]:
    consulta = _no_periodo(
        select(Avaliacao, Cliente.nome, Profissional.nome)
        .join(Cliente, Avaliacao.cliente_id == Cliente.id)
        .join(Profissional, Avaliacao.profissional_id == Profissional.id),
        estabelecimento_id, inicio, fim, profissional_id,
    ).order_by(Avaliacao.created_at.desc(), Avaliacao.id.desc()).limit(limite)
    return [
        {
            "id": avaliacao.id,
            "atendimento_id": avaliacao.atendimento_id,
            "nota": avaliacao.nota,
            "comentario": avaliacao.comentario,
            "canal": avaliacao.canal.value,
            "cliente_nome": cliente,
            "profissional_nome": profissional,
            "created_at": avaliacao.created_at.isoformat() if avaliacao.created_at else None,
        }
        for avaliacao, cliente, profissional in (await db.execute(consulta)).all()
    ]


async def resumo_nps(
    db: AsyncSession,
    estabelecimento_id: int,
    inicio: date,
    fim: date,
    profissional_id: int | None = None,
) -> dict:
    """NPS geral, distribuição das notas e ranking dos profissionais no período."""
    linhas = (
        await db.execute(
            _no_periodo(
                select(Avaliacao.nota, Avaliacao.profissional_id, Profissional.nome).join(
                    Profissional, Avaliacao.profissional_id == Profissional.id
                ),
                estabelecimento_id, inicio, fim, profissional_id,
            )
        )
    ).all()

    notas = [nota for nota, _, _ in linhas]
    por_profissional: dict[int, dict] = {}
    for nota, prof_id, nome in linhas:
        por_profissional.setdefault(prof_id, {"nome": nome, "notas": []})["notas"].append(nota)

    profissionais = [
        {"profissional_id": prof_id, "profissional_nome": dados["nome"], **calcular_nps(dados["notas"])}
        for prof_id, dados in por_profissional.items()
    ]
    profissionais.sort(key=lambda p: (-(p["media"] or 0), -p["total"], p["profissional_nome"]))

    return {
        "geral": calcular_nps(notas),
        "distribuicao": {str(n): notas.count(n) for n in range(1, 6)},
        "profissionais": profissionais,
    }
