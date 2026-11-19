"""Relatórios gerenciais da unidade (T94): ocupação, comparecimento, sintomas, custo de IA e fila de espera.

Todos recebem o período (datas inclusive) e ficam restritos ao estabelecimento informado.
"""

from collections import Counter
from datetime import date

from sqlalchemy import Date, cast, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.atendimento import Atendimento, AtendimentoCanal, AtendimentoStatus
from app.models.especialidade import Especialidade
from app.models.fila_espera import FilaEspera, FilaEsperaStatus
from app.models.profissional import Profissional
from app.models.slot import Slot, SlotStatus
from app.models.token_usage import TokenUsage

_OCUPADOS = (SlotStatus.AGENDADO, SlotStatus.ENCAIXE)


def _taxa(parte: int, total: int) -> float | None:
    return round(parte * 100 / total, 1) if total else None


def _valor(v) -> str:
    return v.value if hasattr(v, "value") else v


async def ocupacao(
    db: AsyncSession, estabelecimento_id: int, inicio: date, fim: date, profissional_id: int | None = None
) -> dict:
    """Horários ocupados sobre horários abertos (bloqueados ficam fora), por profissional."""
    consulta = (
        select(Profissional.id, Profissional.nome, Slot.status, func.count(Slot.id))
        .join(Profissional, Slot.profissional_id == Profissional.id)
        .where(
            Slot.estabelecimento_id == estabelecimento_id,
            Slot.data >= inicio,
            Slot.data <= fim,
            Slot.status != SlotStatus.BLOQUEADO,
        )
        .group_by(Profissional.id, Profissional.nome, Slot.status)
    )
    if profissional_id is not None:
        consulta = consulta.where(Slot.profissional_id == profissional_id)

    por_profissional: dict[int, dict] = {}
    for prof_id, nome, status, quantidade in (await db.execute(consulta)).all():
        item = por_profissional.setdefault(
            prof_id, {"profissional_id": prof_id, "profissional_nome": nome, "total_slots": 0, "ocupados": 0}
        )
        item["total_slots"] += quantidade
        if status in _OCUPADOS:
            item["ocupados"] += quantidade

    profissionais = sorted(por_profissional.values(), key=lambda p: p["profissional_nome"])
    for item in profissionais:
        item["taxa"] = _taxa(item["ocupados"], item["total_slots"]) or 0.0

    total = sum(p["total_slots"] for p in profissionais)
    ocupados = sum(p["ocupados"] for p in profissionais)
    return {
        "geral": {"total_slots": total, "ocupados": ocupados, "taxa": _taxa(ocupados, total) or 0.0},
        "profissionais": profissionais,
    }


def _atendimentos_do_periodo(colunas, estabelecimento_id, inicio, fim, profissional_id):
    consulta = (
        select(*colunas)
        .join(Slot, Atendimento.slot_id == Slot.id)
        .where(
            Atendimento.estabelecimento_id == estabelecimento_id,
            Slot.data >= inicio,
            Slot.data <= fim,
        )
    )
    if profissional_id is not None:
        consulta = consulta.where(Atendimento.profissional_id == profissional_id)
    return consulta


async def confirmacao(
    db: AsyncSession, estabelecimento_id: int, inicio: date, fim: date, profissional_id: int | None = None
) -> dict:
    """Comparecimento (realizados sobre realizados + faltas) e cancelamentos, com o motivo."""
    linhas = (
        await db.execute(
            _atendimentos_do_periodo(
                (Atendimento.status, Atendimento.motivo_cancelamento, func.count(Atendimento.id)),
                estabelecimento_id, inicio, fim, profissional_id,
            ).group_by(Atendimento.status, Atendimento.motivo_cancelamento)
        )
    ).all()

    por_status: Counter = Counter()
    motivos: dict[str, int] = {}
    for status, motivo, quantidade in linhas:
        por_status[_valor(status)] += quantidade
        if _valor(status) == AtendimentoStatus.CANCELADA.value:
            chave = _valor(motivo) if motivo is not None else "NAO_INFORMADO"
            motivos[chave] = motivos.get(chave, 0) + quantidade

    total = sum(por_status.values())
    realizados = por_status[AtendimentoStatus.REALIZADA.value]
    faltas = por_status[AtendimentoStatus.FALTA.value]
    cancelados = por_status[AtendimentoStatus.CANCELADA.value]
    return {
        "total": total,
        "realizados": realizados,
        "faltas": faltas,
        "cancelados": cancelados,
        "em_aberto": total - realizados - faltas - cancelados,
        "taxa_comparecimento": _taxa(realizados, realizados + faltas),
        "taxa_cancelamento": _taxa(cancelados, total),
        "cancelamentos_por_motivo": motivos,
    }


async def sintomas(
    db: AsyncSession, estabelecimento_id: int, inicio: date, fim: date, profissional_id: int | None = None
) -> dict:
    """Sintomas mais citados nas triagens do chat e especialidades mais procuradas."""
    linhas = (
        await db.execute(
            _atendimentos_do_periodo(
                (Atendimento.triagem_resumo, Especialidade.nome),
                estabelecimento_id, inicio, fim, profissional_id,
            ).join(Especialidade, Atendimento.especialidade_id == Especialidade.id)
        )
    ).all()

    citados: Counter = Counter()
    especialidades: Counter = Counter()
    triagens = 0
    for resumo, especialidade in linhas:
        especialidades[especialidade] += 1
        if isinstance(resumo, dict):
            triagens += 1
            citados.update(c for c in (resumo.get("categorias") or []) if isinstance(c, str))

    return {
        "total_triagens": triagens,
        "sintomas": [{"rotulo": r, "total": t} for r, t in citados.most_common(10)],
        "especialidades": [{"nome": n, "total": t} for n, t in especialidades.most_common(10)],
    }


async def custo_por_agendamento(db: AsyncSession, estabelecimento_id: int, inicio: date, fim: date) -> dict:
    """Gasto de IA do período dividido pelos agendamentos que vieram do chat (portal e WhatsApp)."""
    custo, tokens, chamadas = (
        await db.execute(
            select(
                func.coalesce(func.sum(TokenUsage.cost_usd), 0),
                func.coalesce(func.sum(TokenUsage.total_tokens), 0),
                func.count(TokenUsage.id),
            ).where(
                TokenUsage.estabelecimento_id == estabelecimento_id,
                cast(TokenUsage.created_at, Date) >= inicio,
                cast(TokenUsage.created_at, Date) <= fim,
            )
        )
    ).one()
    agendamentos = (
        await db.execute(
            select(func.count(Atendimento.id)).where(
                Atendimento.estabelecimento_id == estabelecimento_id,
                Atendimento.canal_origem.in_((AtendimentoCanal.PORTAL, AtendimentoCanal.WHATSAPP)),
                cast(Atendimento.created_at, Date) >= inicio,
                cast(Atendimento.created_at, Date) <= fim,
            )
        )
    ).scalar_one()
    custo = float(custo)
    return {
        "custo_total_usd": round(custo, 4),
        "total_tokens": int(tokens),
        "chamadas": chamadas,
        "agendamentos_chat": agendamentos,
        "custo_por_agendamento_usd": round(custo / agendamentos, 4) if agendamentos else None,
    }


async def fila_espera(db: AsyncSession, estabelecimento_id: int, inicio: date, fim: date) -> dict:
    """Entradas na fila no período: situação atual, conversão em agendamento e espera até a oferta."""
    linhas = (
        await db.execute(
            select(FilaEspera.status, FilaEspera.created_at, FilaEspera.notificado_em).where(
                FilaEspera.estabelecimento_id == estabelecimento_id,
                cast(FilaEspera.created_at, Date) >= inicio,
                cast(FilaEspera.created_at, Date) <= fim,
            )
        )
    ).all()
    por_status = Counter(_valor(status) for status, _, _ in linhas)
    esperas = [
        (notificado - criado).total_seconds() / 3600
        for _, criado, notificado in linhas
        if notificado is not None and criado is not None
    ]
    entradas = len(linhas)
    agendados = por_status[FilaEsperaStatus.AGENDADO.value]
    return {
        "entradas": entradas,
        "aguardando": por_status[FilaEsperaStatus.AGUARDANDO.value],
        "notificados": por_status[FilaEsperaStatus.NOTIFICADO.value],
        "agendados": agendados,
        "cancelados": por_status[FilaEsperaStatus.CANCELADO.value],
        "taxa_conversao": _taxa(agendados, entradas),
        "espera_media_horas": round(sum(esperas) / len(esperas), 1) if esperas else None,
    }
