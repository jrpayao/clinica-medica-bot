"""Service de auditoria de ações administrativas (T132)."""

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.auditoria import AuditoriaAcao, TipoAuditoria

log = structlog.get_logger(__name__)


class AuditoriaService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def registrar(
        self,
        acao: TipoAuditoria,
        usuario_id: int,
        usuario_role: str,
        estabelecimento_id: int | None = None,
        entidade: str | None = None,
        entidade_id: int | None = None,
        detalhes: dict | None = None,
        ip_origem: str | None = None,
    ) -> None:
        """Persiste evento de auditoria. Nunca propaga exceção."""
        try:
            evento = AuditoriaAcao(
                usuario_id=usuario_id,
                usuario_role=usuario_role,
                acao=acao,
                estabelecimento_id=estabelecimento_id,
                entidade=entidade,
                entidade_id=entidade_id,
                detalhes=detalhes,
                ip_origem=ip_origem,
            )
            self.db.add(evento)
            await self.db.flush()
            log.info(
                "auditoria_registrada",
                acao=acao,
                usuario_id=usuario_id,
                estabelecimento_id=estabelecimento_id,
            )
        except Exception as exc:
            log.error("auditoria_falhou", acao=acao, erro=str(exc))

    async def listar(
        self,
        limit: int = 50,
        offset: int = 0,
        estabelecimento_id: int | None = None,
        acao: TipoAuditoria | None = None,
    ) -> list[AuditoriaAcao]:
        """Retorna eventos de auditoria paginados, mais recentes primeiro."""
        q = (
            select(AuditoriaAcao)
            .order_by(AuditoriaAcao.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        if estabelecimento_id is not None:
            q = q.where(AuditoriaAcao.estabelecimento_id == estabelecimento_id)
        if acao is not None:
            q = q.where(AuditoriaAcao.acao == acao)

        result = await self.db.execute(q)
        return list(result.scalars().all())
