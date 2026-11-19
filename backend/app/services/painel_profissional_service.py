"""Consultas do painel do profissional (G24): pacientes que ele atende e unidades onde trabalha."""

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.atendimento import Atendimento, AtendimentoStatus
from app.models.cliente import Cliente
from app.models.convenio import Convenio
from app.models.estabelecimento import EstabelecimentoSaude
from app.models.profissional_estabelecimento import ProfissionalEstabelecimento
from app.models.slot import Slot
from app.services.recepcao_service import mascarar_cpf


async def listar_clientes_do_profissional(
    db: AsyncSession, profissional_id: int, estabelecimento_id: int
) -> list[dict]:
    """Clientes com atendimento (não cancelado) com o profissional na unidade, do mais recente ao mais antigo."""
    ultimo = func.max(Slot.data)
    q = (
        select(
            Cliente.id,
            Cliente.nome,
            Cliente.cpf,
            Cliente.telefone,
            func.count(Atendimento.id),
            ultimo,
            Convenio.nome,
        )
        .join(Atendimento, Atendimento.cliente_id == Cliente.id)
        .join(Slot, Atendimento.slot_id == Slot.id)
        .outerjoin(Convenio, Cliente.convenio_id == Convenio.id)
        .where(
            Atendimento.profissional_id == profissional_id,
            Atendimento.estabelecimento_id == estabelecimento_id,
            Atendimento.status != AtendimentoStatus.CANCELADA,
        )
        .group_by(Cliente.id, Cliente.nome, Cliente.cpf, Cliente.telefone, Convenio.nome)
        .order_by(ultimo.desc(), Cliente.nome)
    )
    linhas = (await db.execute(q)).all()
    return [
        {
            "cliente_id": cliente_id,
            "nome": nome,
            "cpf_mascarado": mascarar_cpf(cpf),
            "telefone": telefone,
            "total_atendimentos": total,
            "ultimo_atendimento": str(ultima_data) if ultima_data else None,
            "convenio_nome": convenio,
        }
        for cliente_id, nome, cpf, telefone, total, ultima_data, convenio in linhas
    ]


async def unidades_do_profissional(db: AsyncSession, profissional_id: int) -> list[dict]:
    """Unidades ativas onde o profissional tem vínculo ativo."""
    q = (
        select(EstabelecimentoSaude.id, EstabelecimentoSaude.nome)
        .join(
            ProfissionalEstabelecimento,
            ProfissionalEstabelecimento.estabelecimento_id == EstabelecimentoSaude.id,
        )
        .where(
            ProfissionalEstabelecimento.profissional_id == profissional_id,
            ProfissionalEstabelecimento.ativo == True,  # noqa: E712
            EstabelecimentoSaude.ativo == True,  # noqa: E712
        )
        .order_by(EstabelecimentoSaude.nome)
    )
    return [{"id": est_id, "nome": nome} for est_id, nome in (await db.execute(q)).all()]


async def triagens_dos_atendimentos(db: AsyncSession, atendimento_ids: list[int]) -> dict[int, dict]:
    """Resumo de triagem (texto, origem e triagens anteriores) de cada atendimento que veio do chat."""
    if not atendimento_ids:
        return {}
    from app.models.atendimento import Atendimento
    from app.services.ia.resumo_triagem import texto_do_resumo

    linhas = (
        await db.execute(
            select(Atendimento.id, Atendimento.triagem_resumo).where(
                Atendimento.id.in_(atendimento_ids), Atendimento.triagem_resumo.isnot(None)
            )
        )
    ).all()
    triagens = {}
    for atendimento_id, resumo in linhas:
        texto = texto_do_resumo(resumo)
        if texto is None:
            continue
        triagens[atendimento_id] = {
            "texto": texto,
            "origem": resumo.get("origem"),
            "categorias": resumo.get("categorias") or [],
            "historico": [h for h in (resumo.get("historico") or []) if isinstance(h, dict)],
        }
    return triagens
