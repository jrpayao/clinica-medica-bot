"""Relatórios gerenciais e satisfação (T94, T102).

GET /v1/relatorios/ocupacao
GET /v1/relatorios/confirmacao
GET /v1/relatorios/sintomas
GET /v1/relatorios/custo-por-agendamento
GET /v1/relatorios/fila-espera
GET /v1/admin/avaliacoes
GET /v1/admin/avaliacoes/nps

Parâmetros: inicio, fim (datas, inclusive; padrão: últimos 30 dias) e profissional_id opcional.
RBAC: ADMIN_ESTABELECIMENTO e ADMIN_GLOBAL (com unidade selecionada).
"""

from dataclasses import dataclass
from datetime import date, timedelta
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.dependencies import require_estabelecimento, require_role
from app.core import cache
from app.core.database import get_db
from app.core.tempo import fuso_do_estabelecimento, hoje_local
from app.services import relatorio_service
from app.services.avaliacao_service import listar_avaliacoes, resumo_nps

ROLES_RELATORIOS = ("ADMIN_GLOBAL", "ADMIN_ESTABELECIMENTO")
PERIODO_PADRAO_DIAS = 30
PERIODO_MAXIMO_DIAS = 366

router = APIRouter(tags=["Relatórios"])


@dataclass
class Filtro:
    estabelecimento_id: int
    inicio: date
    fim: date
    profissional_id: int | None
    atualizar: bool = False

    def chave(self, nome: str, *extra: object) -> str:
        partes = [nome, self.estabelecimento_id, self.inicio, self.fim, self.profissional_id, *extra]
        return "relatorio:" + ":".join(str(p) for p in partes)


async def filtro(
    _: Annotated[dict, Depends(require_role(*ROLES_RELATORIOS))],
    estabelecimento_id: Annotated[int, Depends(require_estabelecimento)],
    inicio: date | None = Query(None, description="Primeiro dia do período"),
    fim: date | None = Query(None, description="Último dia do período"),
    profissional_id: int | None = Query(None, alias="profissional_id"),
    medico_id: int | None = Query(None, description="Sinônimo de profissional_id"),
    atualizar: bool = Query(False, description="Ignora o cache e recalcula"),
    db: AsyncSession = Depends(get_db),
) -> Filtro:
    hoje = hoje_local(await fuso_do_estabelecimento(db, estabelecimento_id))
    fim = fim or hoje
    inicio = inicio or fim - timedelta(days=PERIODO_PADRAO_DIAS - 1)
    if inicio > fim:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="O início é depois do fim")
    if (fim - inicio).days > PERIODO_MAXIMO_DIAS:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Período máximo de um ano")
    return Filtro(estabelecimento_id, inicio, fim, profissional_id or medico_id, atualizar)


async def _em_cache(f: Filtro, nome: str, calcular, *extra: object):
    """Relatórios ficam TTL_RELATORIO em cache; Atualizar (atualizar=true) recalcula e renova."""
    chave = f.chave(nome, *extra)
    if not f.atualizar:
        return await cache.lembrar(chave, cache.TTL_RELATORIO, calcular)
    valor = await calcular()
    await cache.gravar(chave, valor, cache.TTL_RELATORIO)
    return valor


_Filtro = Annotated[Filtro, Depends(filtro)]


def _com_periodo(f: Filtro, dados: dict) -> dict:
    return {"inicio": str(f.inicio), "fim": str(f.fim), **dados}


@router.get("/relatorios/ocupacao", summary="Ocupação da agenda por profissional")
async def relatorio_ocupacao(f: _Filtro, db: AsyncSession = Depends(get_db)) -> dict:
    return _com_periodo(f, await _em_cache(f, "ocupacao", lambda: relatorio_service.ocupacao(
        db, f.estabelecimento_id, f.inicio, f.fim, f.profissional_id)))


@router.get("/relatorios/confirmacao", summary="Comparecimento, faltas e cancelamentos")
async def relatorio_confirmacao(f: _Filtro, db: AsyncSession = Depends(get_db)) -> dict:
    return _com_periodo(f, await _em_cache(f, "confirmacao", lambda: relatorio_service.confirmacao(
        db, f.estabelecimento_id, f.inicio, f.fim, f.profissional_id)))


@router.get("/relatorios/sintomas", summary="Sintomas mais citados e especialidades procuradas")
async def relatorio_sintomas(f: _Filtro, db: AsyncSession = Depends(get_db)) -> dict:
    return _com_periodo(f, await _em_cache(f, "sintomas", lambda: relatorio_service.sintomas(
        db, f.estabelecimento_id, f.inicio, f.fim, f.profissional_id)))


@router.get("/relatorios/custo-por-agendamento", summary="Custo de IA por agendamento feito no chat")
async def relatorio_custo(f: _Filtro, db: AsyncSession = Depends(get_db)) -> dict:
    return _com_periodo(f, await _em_cache(f, "custo", lambda: relatorio_service.custo_por_agendamento(
        db, f.estabelecimento_id, f.inicio, f.fim)))


@router.get("/relatorios/fila-espera", summary="Lista de espera: entradas, conversão e tempo de espera")
async def relatorio_fila(f: _Filtro, db: AsyncSession = Depends(get_db)) -> dict:
    return _com_periodo(f, await _em_cache(f, "fila", lambda: relatorio_service.fila_espera(
        db, f.estabelecimento_id, f.inicio, f.fim)))


@router.get("/admin/avaliacoes", summary="Últimas avaliações dos clientes")
async def avaliacoes(
    f: _Filtro, limite: int = Query(50, ge=1, le=200), db: AsyncSession = Depends(get_db)
) -> list[dict]:
    return await _em_cache(f, "avaliacoes", lambda: listar_avaliacoes(
        db, f.estabelecimento_id, f.inicio, f.fim, f.profissional_id, limite), limite)


@router.get("/admin/avaliacoes/nps", summary="NPS, distribuição das notas e ranking de profissionais")
async def nps(f: _Filtro, db: AsyncSession = Depends(get_db)) -> dict:
    return _com_periodo(f, await _em_cache(f, "nps", lambda: resumo_nps(
        db, f.estabelecimento_id, f.inicio, f.fim, f.profissional_id)))
