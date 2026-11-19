"""Operação da recepção (G23): fila do dia, check-in e avanço de status do atendimento.

O cancelamento não passa por aqui — tem endpoint próprio em /agenda, porque libera o slot.
"""

from datetime import date

import structlog
from sqlalchemy import func, select
from sqlalchemy.orm import aliased
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.atendimento import Atendimento, AtendimentoStatus, AtendimentoUrgencia
from app.models.atendimento_historico import AtendimentoStatusHistorico
from app.models.cliente import Cliente
from app.models.cliente_convenio import ClienteConvenio
from app.models.convenio import Convenio
from app.models.especialidade import Especialidade
from app.models.profissional import Profissional
from app.models.slot import Slot

log = structlog.get_logger(__name__)

_S = AtendimentoStatus

# Fluxo operado pela recepção. A ordem de cada lista é a ordem em que as ações são oferecidas na tela.
TRANSICOES_RECEPCAO: dict[AtendimentoStatus, list[AtendimentoStatus]] = {
    _S.AGENDADA:                [_S.PRESENTE, _S.CONFIRMADA, _S.FALTA],
    _S.CONFIRMADA:              [_S.PRESENTE, _S.FALTA],
    _S.PRESENTE:                [_S.EM_ATENDIMENTO],
    _S.AGUARDANDO_PROFISSIONAL: [_S.EM_ATENDIMENTO],
    _S.EM_ATENDIMENTO:          [_S.REALIZADA],
    _S.FALTA:                   [_S.PRESENTE],
}

# O profissional só conduz o próprio atendimento: chegada, confirmação e falta são da recepção.
TRANSICOES_PROFISSIONAL: dict[AtendimentoStatus, list[AtendimentoStatus]] = {
    _S.PRESENTE:                [_S.EM_ATENDIMENTO],
    _S.AGUARDANDO_PROFISSIONAL: [_S.EM_ATENDIMENTO],
    _S.EM_ATENDIMENTO:          [_S.REALIZADA],
}


def _transicoes(perfil: str | None) -> dict[AtendimentoStatus, list[AtendimentoStatus]]:
    return TRANSICOES_PROFISSIONAL if perfil == "MEDICO" else TRANSICOES_RECEPCAO


_A_CHEGAR = {_S.AGENDADA, _S.CONFIRMADA}
_NA_RECEPCAO = {
    _S.PRESENTE, _S.AGUARDANDO_ANAMNESE, _S.ANAMNESE_PREENCHIDA, _S.FICHA_CONCLUIDA,
    _S.AGUARDANDO_PAGAMENTO, _S.PAGO, _S.AGUARDANDO_PROFISSIONAL,
}
_URGENCIAS_CRITICAS = {AtendimentoUrgencia.ALTA.value, AtendimentoUrgencia.EMERGENCIA.value}


class AtendimentoNaoEncontradoError(Exception):
    pass


class TransicaoInvalidaError(Exception):
    pass


def _valor(v) -> str | None:
    return v.value if hasattr(v, "value") else v


def transicao_permitida(
    atual: AtendimentoStatus, novo: AtendimentoStatus, perfil: str | None = None
) -> bool:
    return novo in _transicoes(perfil).get(atual, [])


def proximas_acoes(atual: AtendimentoStatus | str, perfil: str | None = None) -> list[str]:
    """Status para os quais a recepção pode levar o atendimento a partir do atual."""
    return [s.value for s in _transicoes(perfil).get(AtendimentoStatus(_valor(atual)), [])]


def mascarar_cpf(cpf: str | None) -> str:
    if not cpf or len(cpf) < 11:
        return "***"
    return f"{cpf[:3]}.***.***-{cpf[-2:]}"


def montar_resumo(itens: list[dict]) -> dict:
    """Contadores do dia por etapa. Cancelados ficam fora do total; urgentes só contam enquanto não atendidos."""
    a_chegar = {s.value for s in _A_CHEGAR}
    na_recepcao = {s.value for s in _NA_RECEPCAO}
    pendentes = a_chegar | na_recepcao

    def contar(grupo: set[str]) -> int:
        return sum(1 for i in itens if i["status"] in grupo)

    cancelados = contar({_S.CANCELADA.value})
    return {
        "total": len(itens) - cancelados,
        "a_chegar": contar(a_chegar),
        "na_recepcao": contar(na_recepcao),
        "em_atendimento": contar({_S.EM_ATENDIMENTO.value}),
        "realizados": contar({_S.REALIZADA.value}),
        "faltas": contar({_S.FALTA.value}),
        "cancelados": cancelados,
        "urgentes": sum(
            1 for i in itens if i["status"] in pendentes and i["urgencia"] in _URGENCIAS_CRITICAS
        ),
    }


async def listar_atendimentos_do_dia(
    db: AsyncSession,
    data: date,
    estabelecimento_id: int,
    profissional_id: int | None = None,
    perfil: str | None = None,
) -> list[dict]:
    """Atendimentos do dia da unidade, em ordem de horário, com as ações disponíveis para cada um.

    O convênio vem da carteirinha usada no atendimento; sem ela, do cadastro do cliente (agendamento pelo chat).
    """
    convenio_do_cadastro = aliased(Convenio)
    q = (
        select(
            Atendimento.id,
            Slot.hora_inicio,
            Slot.hora_fim,
            Cliente.nome,
            Cliente.cpf,
            Cliente.telefone,
            Profissional.nome,
            Especialidade.nome,
            Atendimento.status,
            Atendimento.urgencia,
            Atendimento.canal_origem,
            func.coalesce(Convenio.nome, convenio_do_cadastro.nome),
            Atendimento.observacoes,
            Atendimento.modalidade,
        )
        .join(Slot, Atendimento.slot_id == Slot.id)
        .join(Cliente, Atendimento.cliente_id == Cliente.id)
        .join(Profissional, Atendimento.profissional_id == Profissional.id)
        .join(Especialidade, Atendimento.especialidade_id == Especialidade.id)
        .outerjoin(ClienteConvenio, Atendimento.cliente_convenio_id == ClienteConvenio.id)
        .outerjoin(Convenio, ClienteConvenio.convenio_id == Convenio.id)
        .outerjoin(convenio_do_cadastro, Cliente.convenio_id == convenio_do_cadastro.id)
        .where(Atendimento.estabelecimento_id == estabelecimento_id, Slot.data == data)
        .order_by(Slot.hora_inicio, Cliente.nome)
    )
    if profissional_id is not None:
        q = q.where(Atendimento.profissional_id == profissional_id)
    linhas = (await db.execute(q)).all()

    return [
        {
            "atendimento_id": at_id,
            "hora_inicio": hora_ini.strftime("%H:%M"),
            "hora_fim": hora_fim.strftime("%H:%M"),
            "cliente_nome": cli_nome,
            "cliente_cpf_mascarado": mascarar_cpf(cpf),
            "cliente_telefone": telefone,
            "profissional_nome": prof_nome,
            "especialidade_nome": esp_nome,
            "status": _valor(status),
            "urgencia": _valor(urgencia),
            "canal_origem": _valor(canal),
            "convenio_nome": convenio,
            "observacoes": observacoes,
            "modalidade": _valor(resto[0]) if resto else "PRESENCIAL",
            "acoes": proximas_acoes(status, perfil),
        }
        for (at_id, hora_ini, hora_fim, cli_nome, cpf, telefone, prof_nome, esp_nome,
             status, urgencia, canal, convenio, observacoes, *resto) in linhas
    ]


async def mudar_status(
    db: AsyncSession,
    atendimento_id: int,
    status_novo: AtendimentoStatus,
    estabelecimento_id: int,
    usuario_id: int | None,
    observacao: str | None = None,
    profissional_id: int | None = None,
    perfil: str | None = None,
) -> Atendimento:
    """Avança o status do atendimento da unidade e registra a transição no histórico."""
    consulta = select(Atendimento).where(
        Atendimento.id == atendimento_id,
        Atendimento.estabelecimento_id == estabelecimento_id,
    )
    if profissional_id is not None:
        consulta = consulta.where(Atendimento.profissional_id == profissional_id)
    resultado = await db.execute(consulta)
    atendimento = resultado.scalar_one_or_none()
    if atendimento is None:
        raise AtendimentoNaoEncontradoError("Atendimento não encontrado")

    anterior = atendimento.status
    if not transicao_permitida(anterior, status_novo, perfil):
        raise TransicaoInvalidaError(
            f"Não é possível passar de {_valor(anterior)} para {_valor(status_novo)}"
        )

    atendimento.status = status_novo
    db.add(
        AtendimentoStatusHistorico(
            atendimento_id=atendimento.id,
            status_anterior=anterior,
            status_novo=status_novo,
            usuario_id=usuario_id,
            observacao=observacao,
        )
    )
    await db.flush()

    log.info(
        "atendimento_status_alterado",
        atendimento_id=atendimento.id,
        de=_valor(anterior),
        para=_valor(status_novo),
        usuario_id=usuario_id,
    )
    return atendimento
