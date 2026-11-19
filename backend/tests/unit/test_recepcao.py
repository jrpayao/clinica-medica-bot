"""Testes unitários — Painel da recepção (G23 / T143).

Cobre:
- transicao_permitida / proximas_acoes: fluxo de status operado pela recepção
- montar_resumo: contadores do dia por etapa do fluxo
- listar_atendimentos_do_dia: formato, CPF mascarado, isolamento por unidade
- mudar_status: grava histórico, bloqueia transição inválida e atendimento de outra unidade
- RBAC do router: RECEPCIONISTA entra, MEDICO não
"""

from datetime import date, time
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.models.atendimento import AtendimentoStatus as S
from app.services.recepcao_service import (
    AtendimentoNaoEncontradoError,
    TransicaoInvalidaError,
    listar_atendimentos_do_dia,
    montar_resumo,
    mudar_status,
    proximas_acoes,
    transicao_permitida,
)


# ============================================================
# Fluxo de status
# ============================================================

@pytest.mark.parametrize(
    ("atual", "novo"),
    [
        (S.AGENDADA, S.CONFIRMADA),
        (S.AGENDADA, S.PRESENTE),
        (S.AGENDADA, S.FALTA),
        (S.CONFIRMADA, S.PRESENTE),
        (S.CONFIRMADA, S.FALTA),
        (S.PRESENTE, S.EM_ATENDIMENTO),
        (S.EM_ATENDIMENTO, S.REALIZADA),
        (S.FALTA, S.PRESENTE),  # chegou atrasado depois de marcada a falta
    ],
)
def test_transicoes_do_fluxo_da_recepcao_sao_permitidas(atual, novo):
    assert transicao_permitida(atual, novo) is True


@pytest.mark.parametrize(
    ("atual", "novo"),
    [
        (S.AGENDADA, S.REALIZADA),       # não pula o check-in
        (S.AGENDADA, S.EM_ATENDIMENTO),
        (S.REALIZADA, S.PRESENTE),       # estado final
        (S.CANCELADA, S.PRESENTE),       # estado final
        (S.PRESENTE, S.PRESENTE),
        (S.AGENDADA, S.CANCELADA),       # cancelamento tem endpoint próprio (libera o slot)
    ],
)
def test_transicoes_fora_do_fluxo_sao_bloqueadas(atual, novo):
    assert transicao_permitida(atual, novo) is False


def test_proximas_acoes_de_estado_final_e_vazia():
    assert proximas_acoes(S.REALIZADA) == []
    assert proximas_acoes(S.CANCELADA) == []


def test_proximas_acoes_agendada_oferece_checkin_primeiro():
    assert proximas_acoes(S.AGENDADA)[0] == "PRESENTE"


# ============================================================
# Resumo do dia
# ============================================================

def _item(status, urgencia="BAIXA"):
    return {"status": status, "urgencia": urgencia}


def test_resumo_conta_cada_etapa_do_fluxo():
    itens = [
        _item("AGENDADA"), _item("CONFIRMADA"),
        _item("PRESENTE"), _item("AGUARDANDO_PROFISSIONAL"),
        _item("EM_ATENDIMENTO"),
        _item("REALIZADA"), _item("REALIZADA"),
        _item("FALTA"),
        _item("CANCELADA"),
    ]

    resumo = montar_resumo(itens)

    assert resumo == {
        "total": 8,              # canceladas não entram no total do dia
        "a_chegar": 2,
        "na_recepcao": 2,
        "em_atendimento": 1,
        "realizados": 2,
        "faltas": 1,
        "cancelados": 1,
        "urgentes": 0,
    }


def test_resumo_conta_urgentes_apenas_enquanto_nao_atendidos():
    itens = [
        _item("AGENDADA", "ALTA"),
        _item("PRESENTE", "EMERGENCIA"),
        _item("REALIZADA", "ALTA"),      # já atendido — não é mais alerta
        _item("CANCELADA", "EMERGENCIA"),
        _item("AGENDADA", "MEDIA"),
    ]

    assert montar_resumo(itens)["urgentes"] == 2


def test_resumo_de_dia_vazio_zera_tudo():
    resumo = montar_resumo([])

    assert resumo["total"] == 0
    assert all(v == 0 for v in resumo.values())


# ============================================================
# Lista do dia
# ============================================================

@pytest.fixture
def mock_db():
    db = AsyncMock()
    db.add = MagicMock()
    return db


async def test_lista_do_dia_formata_e_mascara_cpf(mock_db):
    resultado = MagicMock()
    resultado.all.return_value = [
        (42, time(9, 30), time(10, 0), "João Silva", "12345678901", "(11) 99999-0000",
         "Dr. Carlos", "Cardiologia", S.AGENDADA, "MEDIA", "PORTAL", "Unimed", None),
    ]
    mock_db.execute = AsyncMock(return_value=resultado)

    itens = await listar_atendimentos_do_dia(mock_db, data=date(2026, 11, 19), estabelecimento_id=2)

    assert itens == [{
        "atendimento_id": 42,
        "hora_inicio": "09:30",
        "hora_fim": "10:00",
        "cliente_nome": "João Silva",
        "cliente_cpf_mascarado": "123.***.***-01",
        "cliente_telefone": "(11) 99999-0000",
        "profissional_nome": "Dr. Carlos",
        "especialidade_nome": "Cardiologia",
        "status": "AGENDADA",
        "urgencia": "MEDIA",
        "canal_origem": "PORTAL",
        "convenio_nome": "Unimed",
        "observacoes": None,
        "acoes": ["PRESENTE", "CONFIRMADA", "FALTA"],
    }]


async def test_lista_do_dia_filtra_pela_unidade_e_pela_data(mock_db):
    resultado = MagicMock()
    resultado.all.return_value = []
    mock_db.execute = AsyncMock(return_value=resultado)

    await listar_atendimentos_do_dia(mock_db, data=date(2026, 11, 19), estabelecimento_id=7)

    sql = str(mock_db.execute.call_args[0][0].compile(compile_kwargs={"literal_binds": True}))
    assert "atendimentos.estabelecimento_id = 7" in sql
    assert "2026-11-19" in sql


# ============================================================
# Mudança de status
# ============================================================

def _db_com_atendimento(mock_db, atendimento):
    resultado = MagicMock()
    resultado.scalar_one_or_none.return_value = atendimento
    mock_db.execute = AsyncMock(return_value=resultado)


async def test_mudar_status_atualiza_e_grava_historico(mock_db):
    atendimento = MagicMock(id=42, status=S.AGENDADA)
    _db_com_atendimento(mock_db, atendimento)

    retorno = await mudar_status(
        mock_db, atendimento_id=42, status_novo=S.PRESENTE,
        estabelecimento_id=2, usuario_id=9, observacao="chegou 10 min antes",
    )

    assert retorno is atendimento
    assert atendimento.status == S.PRESENTE
    historico = mock_db.add.call_args[0][0]
    assert historico.atendimento_id == 42
    assert historico.status_anterior == S.AGENDADA
    assert historico.status_novo == S.PRESENTE
    assert historico.usuario_id == 9
    assert historico.observacao == "chegou 10 min antes"


async def test_mudar_status_bloqueia_transicao_invalida_sem_gravar(mock_db):
    atendimento = MagicMock(id=42, status=S.AGENDADA)
    _db_com_atendimento(mock_db, atendimento)

    with pytest.raises(TransicaoInvalidaError):
        await mudar_status(
            mock_db, atendimento_id=42, status_novo=S.REALIZADA,
            estabelecimento_id=2, usuario_id=9,
        )

    assert atendimento.status == S.AGENDADA
    mock_db.add.assert_not_called()


async def test_mudar_status_de_outra_unidade_nao_encontra(mock_db):
    _db_com_atendimento(mock_db, None)

    with pytest.raises(AtendimentoNaoEncontradoError):
        await mudar_status(
            mock_db, atendimento_id=42, status_novo=S.PRESENTE,
            estabelecimento_id=99, usuario_id=9,
        )

    sql = str(mock_db.execute.call_args[0][0].compile(compile_kwargs={"literal_binds": True}))
    assert "atendimentos.estabelecimento_id = 99" in sql


# ============================================================
# RBAC
# ============================================================

def test_recepcionista_esta_entre_os_perfis_do_painel():
    from app.api.v1.endpoints.recepcao import ROLES_RECEPCAO

    assert "RECEPCIONISTA" in ROLES_RECEPCAO
    assert "ADMIN_ESTABELECIMENTO" in ROLES_RECEPCAO
    assert "ADMIN_GLOBAL" in ROLES_RECEPCAO
    assert "MEDICO" not in ROLES_RECEPCAO


def test_rotas_da_recepcao_estao_registradas():
    from app.main import app

    rotas = {(r.path, tuple(sorted(r.methods))) for r in app.routes if hasattr(r, "methods")}
    assert ("/v1/recepcao/painel", ("GET",)) in rotas
    assert ("/v1/recepcao/atendimentos/{atendimento_id}/status", ("PATCH",)) in rotas
