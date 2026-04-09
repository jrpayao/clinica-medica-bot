"""Service de histórico clínico de sessões (T86)."""

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.sessao_historico import SessaoHistorico

log = structlog.get_logger(__name__)

MAX_HISTORICO = 3


class SessaoHistoricoService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def salvar(
        self,
        paciente_id: int,
        sessao_id: int | None,
        sintomas_relatados: list,
        especialidade_sugerida: str | None,
        urgencia: str | None,
        resumo_triagem: str | None,
    ) -> SessaoHistorico:
        """Persiste o histórico de triagem de uma sessão."""
        historico = SessaoHistorico(
            paciente_id=paciente_id,
            sessao_id=sessao_id,
            sintomas_relatados=sintomas_relatados,
            especialidade_sugerida=especialidade_sugerida,
            urgencia=urgencia,
            resumo_triagem=resumo_triagem,
        )
        self.db.add(historico)
        await self.db.flush()
        log.info("historico_salvo", paciente_id=paciente_id)
        return historico

    async def buscar_por_paciente(self, paciente_id: int) -> list[SessaoHistorico]:
        """Retorna as últimas MAX_HISTORICO sessões do paciente (mais recentes primeiro)."""
        result = await self.db.execute(
            select(SessaoHistorico)
            .where(SessaoHistorico.paciente_id == paciente_id)
            .order_by(SessaoHistorico.created_at.desc())
            .limit(MAX_HISTORICO)
        )
        return result.scalars().all()
