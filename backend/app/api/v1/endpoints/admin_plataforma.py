"""Endpoints exclusivos para ADMIN_GLOBAL — visão de plataforma.

GET /v1/admin/plataforma/dashboard  — métricas agregadas (sem PII)
GET /v1/admin/licencas              — lista todas as licenças
GET /v1/admin/usuarios/contagem     — contagem de usuários por role
GET /v1/admin/auditoria             — log de ações paginado
"""

from datetime import date, datetime
from typing import Annotated

import structlog
from fastapi import APIRouter, Depends, Query
from sqlalchemy import Date, cast, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.dependencies import get_current_user, require_role
from app.core.database import get_db
from app.models.auditoria import AuditoriaAcao, TipoAuditoria
from app.models.atendimento import Atendimento, AtendimentoStatus
from app.models.estabelecimento import EstabelecimentoSaude
from app.models.licenca import Licenca, LicencaStatus
from app.models.usuario import Usuario, UsuarioRole
from app.services.auditoria_service import AuditoriaService

log = structlog.get_logger(__name__)

router = APIRouter(prefix="/admin", tags=["Admin Plataforma"])

_ROLE_GLOBAL = "ADMIN_GLOBAL"


# ── Queries extraídas (testáveis) ─────────────────────────────────────────────

async def _contagem_licencas_por_status(db: AsyncSession) -> dict[str, int]:
    result = await db.execute(
        select(Licenca.status, func.count(Licenca.id)).group_by(Licenca.status)
    )
    return {row[0] if isinstance(row[0], str) else row[0].value: row[1] for row in result.all()}


async def _contagem_usuarios_por_role(db: AsyncSession) -> dict[str, int]:
    result = await db.execute(
        select(Usuario.role, func.count(Usuario.id))
        .where(Usuario.ativo == True)  # noqa: E712
        .group_by(Usuario.role)
    )
    return {row[0] if isinstance(row[0], str) else row[0].value: row[1] for row in result.all()}


async def _total_consultas_hoje(db: AsyncSession, data: date) -> dict[str, int]:
    result = await db.execute(
        select(Atendimento.status, func.count(Atendimento.id))
        .where(cast(Atendimento.created_at, Date) == data)
        .group_by(Atendimento.status)
    )
    contagens = {row[0] if isinstance(row[0], str) else row[0].value: row[1] for row in result.all()}
    return {
        "agendadas":  contagens.get(AtendimentoStatus.AGENDADA,  0),
        "realizadas": contagens.get(AtendimentoStatus.REALIZADA, 0),
        "canceladas": contagens.get(AtendimentoStatus.CANCELADA, 0),
    }


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.get(
    "/plataforma/dashboard",
    summary="KPIs de plataforma para ADMIN_GLOBAL",
    dependencies=[Depends(require_role(_ROLE_GLOBAL))],
)
async def dashboard_plataforma(
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Métricas agregadas de toda a plataforma — sem PII."""
    hoje = date.today()

    # Estabelecimentos
    total_estab = (await db.execute(select(func.count(EstabelecimentoSaude.id)))).scalar() or 0
    ativos = (await db.execute(
        select(func.count(EstabelecimentoSaude.id)).where(EstabelecimentoSaude.ativo == True)  # noqa: E712
    )).scalar() or 0

    licencas  = await _contagem_licencas_por_status(db)
    usuarios  = await _contagem_usuarios_por_role(db)
    consultas = await _total_consultas_hoje(db, hoje)

    # Alertas de plataforma
    alertas: list[dict] = []
    expirando = licencas.get("TRIAL", 0) + licencas.get("EXPIRADA", 0)
    if expirando > 0:
        alertas.append({
            "tipo":     "licencas_expirando",
            "mensagem": f"{expirando} licença(s) em TRIAL ou EXPIRADA",
            "contagem": expirando,
            "link":     "/licencas",
        })
    suspensas = licencas.get("SUSPENSA", 0)
    if suspensas > 0:
        alertas.append({
            "tipo":     "licencas_suspensas",
            "mensagem": f"{suspensas} clínica(s) com licença SUSPENSA",
            "contagem": suspensas,
            "link":     "/licencas",
        })

    log.info("dashboard_plataforma_carregado", total_estab=total_estab, alertas=len(alertas))

    return {
        "data": str(hoje),
        "estabelecimentos": {"total": total_estab, "ativos": ativos, "inativos": total_estab - ativos},
        "licencas_por_status": licencas,
        "usuarios_por_role": usuarios,
        "consultas_hoje": consultas,
        "alertas": alertas,
    }


@router.get(
    "/licencas",
    summary="Lista todas as licenças da plataforma",
    dependencies=[Depends(require_role(_ROLE_GLOBAL))],
)
async def listar_licencas(
    db: AsyncSession = Depends(get_db),
) -> list[dict]:
    """Retorna todas as licenças com status, plano, datas e nome do estabelecimento."""
    result = await db.execute(
        select(
            Licenca.id,
            Licenca.estabelecimento_id,
            EstabelecimentoSaude.nome,
            Licenca.plano,
            Licenca.status,
            Licenca.licenca_expira_em,
            Licenca.created_at,
        )
        .join(EstabelecimentoSaude, Licenca.estabelecimento_id == EstabelecimentoSaude.id)
        .order_by(Licenca.status, EstabelecimentoSaude.nome)
    )
    rows = result.all()
    return [
        {
            "id":                   row[0],
            "estabelecimento_id":   row[1],
            "estabelecimento_nome": row[2],
            "plano":                row[3],
            "status":               row[4].value if hasattr(row[4], "value") else row[4],
            "expira_em":            row[5].isoformat() if row[5] else None,
            "criada_em":            row[6].isoformat() if row[6] else None,
        }
        for row in rows
    ]


@router.get(
    "/usuarios/contagem",
    summary="Contagem de usuários por role",
    dependencies=[Depends(require_role(_ROLE_GLOBAL))],
)
async def contagem_usuarios(
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Retorna contagem de usuários ativos agrupada por role."""
    return await _contagem_usuarios_por_role(db)


@router.get(
    "/auditoria",
    summary="Log de auditoria de ações administrativas",
    dependencies=[Depends(require_role(_ROLE_GLOBAL))],
)
async def listar_auditoria(
    db: AsyncSession = Depends(get_db),
    estabelecimento_id: int | None = Query(None),
    acao: TipoAuditoria | None = Query(None),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
) -> list[dict]:
    """Log paginado de ações administrativas. Somente ADMIN_GLOBAL."""
    service = AuditoriaService(db)
    eventos = await service.listar(
        limit=limit,
        offset=offset,
        estabelecimento_id=estabelecimento_id,
        acao=acao,
    )
    return [
        {
            "id":                 evento.id,
            "usuario_id":         evento.usuario_id,
            "usuario_role":       evento.usuario_role,
            "acao":               evento.acao.value if hasattr(evento.acao, "value") else evento.acao,
            "estabelecimento_id": evento.estabelecimento_id,
            "entidade":           evento.entidade,
            "entidade_id":        evento.entidade_id,
            "detalhes":           evento.detalhes,
            "ip_origem":          evento.ip_origem,
            "created_at":         evento.created_at.isoformat() if evento.created_at else None,
        }
        for evento in eventos
    ]
