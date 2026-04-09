"""Endpoint de dashboard administrativo — KPIs gerenciais (G19).

GET /v1/admin/dashboard

Response:
  total_consultas, consultas_agendadas, realizadas, canceladas
  taxa_ocupacao: {slots_ocupados, total_slots, percentual}
  proximas_consultas: list[{consulta_id, hora_inicio, paciente_nome,
                             medico_nome, especialidade_nome, urgencia, status}]
  alertas: list[{tipo, mensagem, contagem, link}]
  custo_ia_total, limite_diario, uso_modelos

RBAC:
  ADMIN_ESTABELECIMENTO → filtro pelo estabelecimento_id do JWT (row-level)
  ADMIN_GLOBAL          → global; filtra via ?estabelecimento_id=N
"""

from datetime import date, datetime, time, timezone
from typing import Annotated

import structlog
from fastapi import APIRouter, Depends, Query
from sqlalchemy import Date, cast, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.dependencies import get_estabelecimento_id_opcional, require_role
from app.core.config import settings
from app.core.database import get_db
from app.models.atendimento import Atendimento, AtendimentoStatus, AtendimentoUrgencia
from app.models.especialidade import Especialidade
from app.models.profissional import Profissional
from app.models.cliente import Cliente
from app.models.slot import Slot, SlotStatus
from app.services.ia.billing import obter_custo_diario_total, obter_resumo_por_modelo

log = structlog.get_logger(__name__)

router = APIRouter(prefix="/admin", tags=["Admin Dashboard"])

_ROLES_ADMIN = ("ADMIN_GLOBAL", "ADMIN_ESTABELECIMENTO")


# ── Queries extraídas (testáveis) ─────────────────────────────────────────────

async def obter_proximas_consultas(
    db: AsyncSession,
    data: date,
    hora_atual: time,
    estabelecimento_id: int | None,
) -> list[dict]:
    """Retorna até 5 consultas AGENDADA com hora_inicio >= hora_atual.

    Quando estabelecimento_id=None (ADMIN_GLOBAL modo global) retorna []
    para não expor PII (nomes de pacientes e médicos) entre clínicas.
    """
    if estabelecimento_id is None:
        return []

    q = (
        select(
            Atendimento.id,
            Slot.hora_inicio,
            Cliente.nome,
            Profissional.nome,
            Especialidade.nome,
            Atendimento.urgencia,
            Atendimento.status,
        )
        .join(Slot,          Atendimento.slot_id          == Slot.id)
        .join(Cliente,       Atendimento.cliente_id       == Cliente.id)
        .join(Profissional,  Atendimento.profissional_id  == Profissional.id)
        .join(Especialidade, Atendimento.especialidade_id == Especialidade.id)
        .where(
            Slot.data == data,
            Slot.hora_inicio >= hora_atual,
            Atendimento.status == AtendimentoStatus.AGENDADA,
            Slot.estabelecimento_id == estabelecimento_id,
        )
        .order_by(Slot.hora_inicio)
        .limit(5)
    )

    result = await db.execute(q)
    return [
        {
            "atendimento_id":     row[0],
            "hora_inicio":        row[1].strftime("%H:%M"),
            "cliente_nome":       row[2],
            "profissional_nome":  row[3],
            "especialidade_nome": row[4],
            "urgencia":           row[5].value if hasattr(row[5], "value") else row[5],
            "status":             row[6].value if hasattr(row[6], "value") else row[6],
        }
        for row in result.all()
    ]


async def obter_taxa_ocupacao(
    db: AsyncSession,
    data: date,
    estabelecimento_id: int | None,
) -> dict:
    """Retorna taxa de ocupação dos slots do dia.

    Slots BLOQUEADOS não entram no total — representam indisponibilidade
    administrativa, não capacidade real.
    """
    q = (
        select(Slot.status, func.count(Slot.id))
        .where(Slot.data == data)
        .group_by(Slot.status)
    )
    if estabelecimento_id is not None:
        q = q.where(Slot.estabelecimento_id == estabelecimento_id)

    result = await db.execute(q)
    contagens: dict[str, int] = {row[0]: row[1] for row in result.all()}

    ocupados = contagens.get(SlotStatus.AGENDADO, 0) + contagens.get(SlotStatus.ENCAIXE, 0)
    disponiveis = contagens.get(SlotStatus.DISPONIVEL, 0)
    reservados = contagens.get(SlotStatus.RESERVADO, 0)
    total = ocupados + disponiveis + reservados

    return {
        "slots_ocupados": ocupados,
        "total_slots":    total,
        "percentual":     round(ocupados / total * 100, 1) if total > 0 else 0.0,
    }


def calcular_alertas(
    urgencias_criticas: int,
    pendentes_confirmacao: int,
    custo_atual: float,
    daily_limit: float,
) -> list[dict]:
    """Gera lista de alertas operacionais. Retorna [] se tudo estiver bem."""
    alertas: list[dict] = []

    if urgencias_criticas > 0:
        alertas.append({
            "tipo":      "urgencia_alta",
            "mensagem":  f"{urgencias_criticas} consulta(s) com urgência ALTA ou EMERGÊNCIA hoje",
            "contagem":  urgencias_criticas,
            "link":      "/consultas",
        })

    if pendentes_confirmacao > 0:
        alertas.append({
            "tipo":      "pendente_confirmacao",
            "mensagem":  f"{pendentes_confirmacao} consulta(s) sem confirmação",
            "contagem":  pendentes_confirmacao,
            "link":      "/consultas",
        })

    if daily_limit > 0 and custo_atual >= daily_limit * 0.8:
        pct = round(custo_atual / daily_limit * 100, 1)
        alertas.append({
            "tipo":      "custo_alto",
            "mensagem":  f"Custo IA em {pct}% do limite diário",
            "contagem":  1,
            "link":      "/billing",
        })

    return alertas


# ── Endpoint ──────────────────────────────────────────────────────────────────

@router.get(
    "/dashboard",
    summary="KPIs do dashboard administrativo",
    dependencies=[Depends(require_role(*_ROLES_ADMIN))],
)
async def admin_dashboard(
    data: date | None = Query(None, description="Data do resumo (default: hoje)"),
    db: AsyncSession = Depends(get_db),
    estabelecimento_id: Annotated[int | None, Depends(get_estabelecimento_id_opcional)] = None,
) -> dict:
    """KPIs gerenciais: consultas + ocupação + alertas + próximas + custo IA.

    RBAC via get_estabelecimento_id_opcional:
    - ADMIN_ESTABELECIMENTO → lê est_id do JWT (row-level isolation)
    - ADMIN_GLOBAL + JWT escopado → lê est_id do JWT
    - ADMIN_GLOBAL + modo global + filtro → lê est_id do header X-Estabelecimento-ID
    - ADMIN_GLOBAL + modo global sem filtro → None (agrega todas as clínicas)
    """
    if data is None:
        data = date.today()

    est_id = estabelecimento_id
    hora_atual = datetime.now(tz=timezone.utc).time()

    # ── Contagens de consultas ────────────────────────────────────
    q_status = (
        select(Atendimento.status, func.count(Atendimento.id))
        .where(cast(Atendimento.created_at, Date) == data)
        .group_by(Atendimento.status)
    )
    if est_id is not None:
        q_status = q_status.where(Atendimento.estabelecimento_id == est_id)

    res_status = await db.execute(q_status)
    contagens: dict[str, int] = {row[0]: row[1] for row in res_status.all()}

    agendadas  = contagens.get(AtendimentoStatus.AGENDADA,  0)
    realizadas = contagens.get(AtendimentoStatus.REALIZADA, 0)
    canceladas = contagens.get(AtendimentoStatus.CANCELADA, 0)

    # ── Urgências críticas (ALTA + EMERGENCIA, não canceladas) ────
    q_urg = (
        select(func.count(Atendimento.id))
        .where(
            cast(Atendimento.created_at, Date) == data,
            Atendimento.urgencia.in_([AtendimentoUrgencia.ALTA, AtendimentoUrgencia.EMERGENCIA]),
            Atendimento.status != AtendimentoStatus.CANCELADA,
        )
    )
    if est_id is not None:
        q_urg = q_urg.where(Atendimento.estabelecimento_id == est_id)
    urgencias_criticas = (await db.execute(q_urg)).scalar() or 0

    # ── Billing ───────────────────────────────────────────────────
    custo_atual = float(await obter_custo_diario_total(db, data=data, estabelecimento_id=est_id))
    uso_modelos = await obter_resumo_por_modelo(db, data=data, estabelecimento_id=est_id)

    # ── Taxa de ocupação + próximas consultas ─────────────────────
    taxa = await obter_taxa_ocupacao(db, data=data, estabelecimento_id=est_id)
    proximas = await obter_proximas_consultas(
        db, data=data, hora_atual=hora_atual, estabelecimento_id=est_id
    )

    # ── Alertas ───────────────────────────────────────────────────
    alertas = calcular_alertas(
        urgencias_criticas=urgencias_criticas,
        pendentes_confirmacao=0,          # sem query adicional por ora
        custo_atual=custo_atual,
        daily_limit=settings.daily_limit_usd,
    )

    log.info(
        "admin_dashboard_carregado",
        data=str(data),
        est_id=est_id,
        alertas=len(alertas),
    )

    return {
        "data":                     str(data),
        "filtro_estabelecimento_id": est_id,
        "total_consultas":          agendadas + realizadas + canceladas,
        "consultas_agendadas":      agendadas,
        "consultas_realizadas":     realizadas,
        "consultas_canceladas":     canceladas,
        "taxa_ocupacao":            taxa,
        "proximas_consultas":       proximas,
        "alertas":                  alertas,
        "custo_ia_total":           custo_atual,
        "limite_diario":            settings.daily_limit_usd,
        "uso_modelos":              uso_modelos,
    }
