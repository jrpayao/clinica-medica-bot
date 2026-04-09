"""Service de Licenciamento — ciclo de vida da licença por estabelecimento.

Responsabilidades:
- Criar trial ao criar estabelecimento
- Verificar validade (status efetivo, lazy check de expiração)
- Ativar/renovar plano manualmente pelo ADMIN_GLOBAL
- Suspender/reativar licença
- Verificar quotas por plano (médicos, consultas/mês)
"""

from datetime import UTC, datetime, timedelta

import structlog
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import PLANO_QUOTAS, TRIAL_DIAS
from app.models.consulta import Consulta, ConsultaStatus
from app.models.licenca import Licenca, LicencaStatus
from app.models.medico_estabelecimento import MedicoEstabelecimento

log = structlog.get_logger(__name__)


class LicencaExpiradaError(Exception):
    pass


class LicencaSuspensaError(Exception):
    pass


class LicencaNaoEncontradaError(Exception):
    pass


class QuotaMedicosExcedidaError(Exception):
    def __init__(self, limite: int, atual: int) -> None:
        self.limite = limite
        self.atual = atual
        super().__init__(f"Quota de médicos excedida: {atual}/{limite}")


class QuotaConsultasExcedidaError(Exception):
    def __init__(self, limite: int, atual: int) -> None:
        self.limite = limite
        self.atual = atual
        super().__init__(f"Quota de consultas/mês excedida: {atual}/{limite}")


class LicencaService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    # ── Leitura ─────────────────────────────────────────────────────────────

    async def buscar_por_estabelecimento(
        self, estabelecimento_id: int
    ) -> Licenca | None:
        """Retorna a licença do tenant ou None se não existir."""
        result = await self.db.execute(
            select(Licenca).where(Licenca.estabelecimento_id == estabelecimento_id)
        )
        return result.scalar_one_or_none()

    def verificar_validade(self, licenca: Licenca) -> tuple[LicencaStatus, bool]:
        """Retorna (status_efetivo, valida).

        Faz lazy check: se status=TRIAL e trial_expira_em < now → EXPIRADA.
        Não persiste — apenas informa ao caller.
        """
        agora = datetime.now(UTC)

        if licenca.status == LicencaStatus.SUSPENSA:
            return LicencaStatus.SUSPENSA, False

        if licenca.status == LicencaStatus.TRIAL:
            if licenca.trial_expira_em and licenca.trial_expira_em < agora:
                return LicencaStatus.EXPIRADA, False
            return LicencaStatus.TRIAL, True

        if licenca.status == LicencaStatus.ATIVA:
            if licenca.licenca_expira_em and licenca.licenca_expira_em < agora:
                return LicencaStatus.EXPIRADA, False
            return LicencaStatus.ATIVA, True

        return LicencaStatus.EXPIRADA, False

    def calcular_dias_restantes(self, licenca: Licenca) -> int | None:
        """Dias restantes da licença ativa ou trial. None se expirada/suspensa."""
        agora = datetime.now(UTC)
        expira = (
            licenca.trial_expira_em
            if licenca.status == LicencaStatus.TRIAL
            else licenca.licenca_expira_em
        )
        if expira is None:
            return None
        delta = (expira - agora).days
        return max(0, delta)

    # ── Criação / Ciclo de vida ──────────────────────────────────────────────

    async def ativar_trial(
        self, estabelecimento_id: int, plano: str = "basico"
    ) -> Licenca:
        """Cria licença TRIAL ao criar estabelecimento.
        Chamado por EstabelecimentoService.criar() na mesma transação.
        """
        trial_expira_em = datetime.now(UTC) + timedelta(days=TRIAL_DIAS)
        licenca = Licenca(
            estabelecimento_id=estabelecimento_id,
            plano=plano,
            status=LicencaStatus.TRIAL,
            modalidade="mensal",
            trial_expira_em=trial_expira_em,
        )
        self.db.add(licenca)
        await self.db.flush()
        await self.db.refresh(licenca)
        log.info(
            "licenca_trial_criada",
            estabelecimento_id=estabelecimento_id,
            plano=plano,
            expira_em=trial_expira_em.isoformat(),
        )
        return licenca

    async def ativar_plano(
        self,
        estabelecimento_id: int,
        plano: str,
        modalidade: str,
        meses: int,
        admin_id: int,
    ) -> Licenca:
        """Ativa plano pago manualmente pelo ADMIN_GLOBAL.

        Status → ATIVA, calcula licenca_expira_em = now + meses.
        Sincroniza plano em EstabelecimentoSaude.
        """
        licenca = await self.buscar_por_estabelecimento(estabelecimento_id)
        if not licenca:
            raise LicencaNaoEncontradaError(
                f"Licença não encontrada para estabelecimento {estabelecimento_id}"
            )

        agora = datetime.now(UTC)
        # Se já existe licença ativa, estende a partir da expiração atual
        base = (
            licenca.licenca_expira_em
            if licenca.licenca_expira_em and licenca.licenca_expira_em > agora
            else agora
        )

        licenca.plano = plano
        licenca.status = LicencaStatus.ATIVA
        licenca.modalidade = modalidade
        licenca.licenca_expira_em = base + timedelta(days=30 * meses)
        licenca.suspensa_por = None
        licenca.suspensa_em = None
        licenca.motivo_suspensao = None

        # Sincronizar plano no estabelecimento
        from app.models.estabelecimento import EstabelecimentoSaude
        result = await self.db.execute(
            select(EstabelecimentoSaude).where(EstabelecimentoSaude.id == estabelecimento_id)
        )
        est = result.scalar_one_or_none()
        if est:
            est.plano = plano

        await self.db.flush()
        await self.db.refresh(licenca)
        log.info(
            "licenca_ativada",
            estabelecimento_id=estabelecimento_id,
            plano=plano,
            modalidade=modalidade,
            meses=meses,
            expira_em=licenca.licenca_expira_em.isoformat(),
            admin_id=admin_id,
        )
        return licenca

    async def suspender(
        self, estabelecimento_id: int, admin_id: int, motivo: str
    ) -> Licenca:
        """ADMIN_GLOBAL suspende a licença manualmente."""
        licenca = await self.buscar_por_estabelecimento(estabelecimento_id)
        if not licenca:
            raise LicencaNaoEncontradaError(
                f"Licença não encontrada para estabelecimento {estabelecimento_id}"
            )

        licenca.status = LicencaStatus.SUSPENSA
        licenca.suspensa_por = admin_id
        licenca.suspensa_em = datetime.now(UTC)
        licenca.motivo_suspensao = motivo

        await self.db.flush()
        await self.db.refresh(licenca)
        log.info(
            "licenca_suspensa",
            estabelecimento_id=estabelecimento_id,
            admin_id=admin_id,
            motivo=motivo,
        )
        return licenca

    async def reativar(self, estabelecimento_id: int) -> Licenca:
        """Reativa licença SUSPENSA.

        Se licenca_expira_em > now → ATIVA.
        Se ainda dentro do trial → TRIAL.
        Caso contrário → mantém EXPIRADA (não reativa sem validade).
        """
        licenca = await self.buscar_por_estabelecimento(estabelecimento_id)
        if not licenca:
            raise LicencaNaoEncontradaError(
                f"Licença não encontrada para estabelecimento {estabelecimento_id}"
            )

        agora = datetime.now(UTC)

        if licenca.trial_expira_em and licenca.trial_expira_em > agora:
            licenca.status = LicencaStatus.TRIAL
        elif licenca.licenca_expira_em and licenca.licenca_expira_em > agora:
            licenca.status = LicencaStatus.ATIVA
        else:
            licenca.status = LicencaStatus.EXPIRADA

        licenca.suspensa_por = None
        licenca.suspensa_em = None
        licenca.motivo_suspensao = None

        await self.db.flush()
        await self.db.refresh(licenca)
        log.info(
            "licenca_reativada",
            estabelecimento_id=estabelecimento_id,
            novo_status=licenca.status.value,
        )
        return licenca

    # ── Quotas ──────────────────────────────────────────────────────────────

    async def verificar_quota_medicos(
        self, estabelecimento_id: int, plano: str
    ) -> None:
        """Levanta QuotaMedicosExcedidaError se o limite foi atingido."""
        quota = PLANO_QUOTAS.get(plano, PLANO_QUOTAS["basico"])
        max_medicos: int | None = quota["max_medicos"]

        if max_medicos is None:
            return  # enterprise — ilimitado

        result = await self.db.execute(
            select(func.count()).where(
                MedicoEstabelecimento.estabelecimento_id == estabelecimento_id,
                MedicoEstabelecimento.ativo == True,  # noqa: E712
            )
        )
        atual = result.scalar_one()

        if atual >= max_medicos:
            raise QuotaMedicosExcedidaError(limite=max_medicos, atual=atual)

    async def verificar_quota_consultas_mes(
        self, estabelecimento_id: int, plano: str
    ) -> None:
        """Levanta QuotaConsultasExcedidaError se o limite mensal foi atingido."""
        quota = PLANO_QUOTAS.get(plano, PLANO_QUOTAS["basico"])
        max_consultas: int | None = quota["max_consultas_mes"]

        if max_consultas is None:
            return  # enterprise — ilimitado

        agora = datetime.now(UTC)
        inicio_mes = agora.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

        result = await self.db.execute(
            select(func.count()).where(
                Consulta.estabelecimento_id == estabelecimento_id,
                Consulta.status != ConsultaStatus.CANCELADA,
                Consulta.created_at >= inicio_mes,
            )
        )
        atual = result.scalar_one()

        if atual >= max_consultas:
            raise QuotaConsultasExcedidaError(limite=max_consultas, atual=atual)

    async def contar_medicos_ativos(self, estabelecimento_id: int) -> int:
        """Conta médicos ativos no estabelecimento."""
        result = await self.db.execute(
            select(func.count()).where(
                MedicoEstabelecimento.estabelecimento_id == estabelecimento_id,
                MedicoEstabelecimento.ativo == True,  # noqa: E712
            )
        )
        return result.scalar_one()

    async def contar_consultas_mes(self, estabelecimento_id: int) -> int:
        """Conta consultas não canceladas no mês corrente."""
        agora = datetime.now(UTC)
        inicio_mes = agora.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

        result = await self.db.execute(
            select(func.count()).where(
                Consulta.estabelecimento_id == estabelecimento_id,
                Consulta.status != ConsultaStatus.CANCELADA,
                Consulta.created_at >= inicio_mes,
            )
        )
        return result.scalar_one()
